"""The DeepRacer's second body: a kinematic twin that answers the car's own ROS graph.

:class:`TwinTransport` implements the same upstream ``Transport`` and ``ServiceCapable``
protocols :class:`~deepracer_agent.transport.RosbridgeTransport` does, so
``DeepRacerRobot(TwinTransport())`` drives it unchanged: the same handshake
(``/ctrl_pkg/vehicle_state`` then ``/ctrl_pkg/enable_state``), the same
``ServoCtrlMsg`` stream on ``/webserver_pkg/manual_drive``, the same zero pair at the end,
the same heartbeat and the same ``deadman_state`` echo. Behind the seam there is no
WebSocket: a bicycle model integrates the servo pair with the constants in
:mod:`deepracer_agent.calibration`, **holding the last command with no watchdog exactly
like the stock car**, and an emulated deadman (the on-car ``deadman_logic`` imported by
path, the same 300 ms rule) zeros it when the heartbeat stops. This is a pure kinematic
twin, not MuJoCo: instantaneous velocity, no slip, no ESC ramp; its honesty is in the
geometry and the no-watchdog hold, not in tyre physics.

The operator gate **is** consulted here, unlike upstream's MuJoCo twin. In this project
the twin is a second command surface the same agent talks to, and a demo that says
"stop all halts both bodies" must show both bodies answering to the same
``STRANDS_ROS2_COMMAND_ALLOW`` and the same approval path. Pose samples leave as ``body``
events (``{"body": "twin", "x", "y", "yaw", "v", "t_ms"}``, at most 10 Hz while moving,
one more when it comes to rest) so the Pit Wall can draw the trail. Physics stops the
car; the decider explains; the twin is a picture of the physics, never a safety layer.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import math
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands.types.tools import ToolContext
from strands_robots._command_gate import gate_command
from strands_robots.rosbridge import GATE_TOOL

from deepracer_agent.calibration import Calibration
from deepracer_agent.transport import (
    DEADMAN_STATE_TOPIC,
    DEADMAN_STATE_TYPE,
    HEARTBEAT_TOPIC,
    HEARTBEAT_TYPE,
    SERVO_TYPE,
    TopicHandle,
)

logger = logging.getLogger(__name__)

MANUAL_DRIVE_TOPIC = "/webserver_pkg/manual_drive"
SERVO_MSG_TOPIC = "/ctrl_pkg/servo_msg"
TWIN_ENDPOINT = "sim://deepracer-twin"
TWIN_BODY = "twin"

#: Integration step of the background ticker (50 Hz; the command stream is 20 Hz).
TICK_S = 0.02
#: ``body`` pose events while moving: at most this many per second.
BODY_EVENT_MAX_HZ = 10.0
#: Below this |v| (m/s) the twin is at rest and stops sampling.
REST_EPS = 1e-6

LED_MAX = 10_000_000

#: The twin's graph, as ``list_topics`` reports it (the stock names the driver touches plus
#: the project's two ``/deepracer_agent/`` names).
TWIN_GRAPH: tuple[tuple[str, str], ...] = (
    (MANUAL_DRIVE_TOPIC, SERVO_TYPE),
    (SERVO_MSG_TOPIC, SERVO_TYPE),
    (HEARTBEAT_TOPIC, HEARTBEAT_TYPE),
    (DEADMAN_STATE_TOPIC, DEADMAN_STATE_TYPE),
    ("/parameter_events", "rcl_interfaces/ParameterEvent"),
    ("/rosout", "rcl_interfaces/Log"),
)

TWIN_SERVICES: tuple[str, ...] = (
    "/ctrl_pkg/vehicle_state",
    "/ctrl_pkg/enable_state",
    "/i2c_pkg/battery_level",
    "/servo_pkg/set_led_state",
    "/servo_pkg/get_led_state",
    "/servo_pkg/get_calibration",
)

#: ``GetCalibrationSrv`` answers for a calibrated car (the fake car's ``calibrated`` profile).
CALIBRATION_ANSWERS: dict[int, dict[str, int]] = {
    0: {"max": 1575000, "mid": 1450000, "min": 1325000, "polarity": 1},  # steering
    1: {"max": 1500000, "mid": 1446000, "min": 1400000, "polarity": -1},  # throttle
}

_DEADMAN_LOGIC_PATH = (
    Path(__file__).resolve().parents[2] / "car" / "deadman" / "deepracer_deadman" / "deadman_logic.py"
)


def load_deadman_logic() -> Any:
    """The on-car deadman rule, imported by path (it is a ROS package, not a laptop module).

    The same import the unit tests use, so the twin and the car run one copy of the rule.
    """
    cached = sys.modules.get("deepracer_deadman_logic")
    if cached is not None:
        return cached
    if not _DEADMAN_LOGIC_PATH.exists():
        raise ImportError(
            f"deadman_logic.py not found at {_DEADMAN_LOGIC_PATH}; the twin needs the repo checkout"
        )
    spec = importlib.util.spec_from_file_location("deepracer_deadman_logic", _DEADMAN_LOGIC_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["deepracer_deadman_logic"] = module
    spec.loader.exec_module(module)
    return module


def _ok(text: str, **extra: Any) -> dict[str, Any]:
    return {"status": "success", "content": [{"text": text}], **extra}


def _err(text: str) -> dict[str, Any]:
    return {"status": "error", "content": [{"text": f"twin: {text}"}]}


def _service_text(service: str, values: dict[str, Any]) -> str:
    """The shape ``rosbridge_action("service_call")`` renders, so ``parse_service_response`` reads it."""
    return f"service {service} response:\n{json.dumps(values, indent=2)}"


def servo_to_twist(angle: float, throttle: float, cal: Calibration) -> tuple[float, float]:
    """Inverse of :func:`deepracer_agent.driver.twist_to_servo`: ``(v m/s, steering delta rad)``.

    ``throttle_at_max_speed`` maps to ``max_speed_mps`` and the forward sign is undone, so the
    pair the driver sends for ``linear=0.3`` comes back as 0.3 m/s. The steering servo value is
    the fraction of the lock.
    """
    v = (float(throttle) * cal.throttle_forward_sign / cal.throttle_at_max_speed) * cal.max_speed_mps
    delta = max(-1.0, min(1.0, float(angle))) * cal.max_steering_rad
    return (v, delta)


def range_reason(fields: dict[str, Any]) -> str | None:
    """Why the ctrl node drops a ``ServoCtrlMsg`` (missing, non-numeric, non-finite, out of [-1, 1])."""
    for key in ("angle", "throttle"):
        if key not in fields:
            return f"{key} missing from ServoCtrlMsg"
        value = fields[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            return f"{key} is not a number"
        if math.isnan(value) or math.isinf(value):
            return f"{key} is not finite"
        if value < -1.0 or value > 1.0:
            return f"{key} {value} out of range [-1, 1]"
    return None


class TwinTopic:
    """A persistent topic handle on the twin (the ``roslibpy.Topic`` shape the heartbeat and echo use)."""

    def __init__(self, twin: TwinTransport, name: str, type: str) -> None:
        self.twin = twin
        self.name = name
        self.type = type
        self.callback: Callable[[dict[str, Any]], None] | None = None

    def advertise(self) -> None:
        self.twin._advertised.add(self.name)

    def publish(self, message: Any) -> None:
        self.twin._deliver(self.name, dict(message or {}))

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self.callback = callback
        self.twin._subscribe(self.name, self)

    def unsubscribe(self) -> None:
        self.twin._unsubscribe(self.name, self)
        self.callback = None

    def unadvertise(self) -> None:
        self.twin._advertised.discard(self.name)


class TwinTransport:
    """Upstream ``Transport`` + ``ServiceCapable`` answered by a kinematic bicycle model.

    Args:
        calibration: The car's constants; defaults to :meth:`Calibration.load`.
        event_log: Where ``body`` pose events go (``None`` keeps the twin silent).
        deadman: Run the on-car deadman rule against the heartbeat (default on: the real
            car always has one).
        realtime: Sleep each publish period out and run a background ticker so a 0.5 s hop
            takes 0.5 s and the hold integrates while nothing is published. ``False`` for tests,
            which drive :meth:`advance` with their own clock.
        clock: Monotonic seconds (tests inject one).
        wall: Wall clock seconds for ``since`` and ``t_ms`` stamps.
        sleep: Replacement for ``time.sleep`` (tests).
        start: Initial ``(x, y, yaw)`` in metres and radians; the pen centre faces +x.
        battery: ``/i2c_pkg/battery_level`` answer (0..10, -1 for pack not seen).
    """

    twist_type = SERVO_TYPE

    def __init__(
        self,
        *,
        calibration: Calibration | None = None,
        event_log: Any | None = None,
        deadman: bool = True,
        realtime: bool = True,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        start: tuple[float, float, float] = (0.0, 0.0, 0.0),
        battery: int = 10,
    ) -> None:
        cal = calibration or Calibration.load()
        problems = cal.validate()
        if problems:
            raise ValueError("calibration refused: " + "; ".join(problems))
        self.calibration = cal
        self.event_log = event_log
        self.realtime = bool(realtime)
        self._clock = clock
        self._wall = wall
        self._sleep = sleep
        self.host = "twin"
        self.port = 0
        self.preemptible = True
        self._lock = threading.RLock()
        # ctrl node state: mode 0 (manual) and disabled at boot, like the stock car after a restart.
        self.mode = 0
        self.enabled = False
        self.battery = int(battery)
        self.led: dict[str, int] = {"red": 0, "green": 0, "blue": 0}
        self.led_history: list[dict[str, Any]] = []
        # servo node state: the last pair written. There is no watchdog; it stays until replaced.
        self.servo: dict[str, float] = {"angle": 0.0, "throttle": 0.0}
        self.servo_history: list[dict[str, Any]] = []
        self.drops: dict[str, int] = {"not_armed": 0, "out_of_range": 0, "malformed": 0}
        self.manual_drive_seen = 0
        self.heartbeats = 0
        # pose
        self.x, self.y, self.yaw = (float(start[0]), float(start[1]), float(start[2]))
        self.v = 0.0
        self.odometer_m = 0.0
        self._t_last = clock()
        self._last_body_emit: float | None = None
        self._was_moving = False
        # graph plumbing
        self._advertised: set[str] = set()
        self._subscribers: dict[str, list[TwinTopic]] = {}
        self._published: dict[str, list[dict[str, Any]]] = {}
        self._stream_generation = 0
        self._stream_lock = threading.Lock()
        # deadman emulation (the on-car rule, by import path)
        self._dm: Any | None = None
        self._dm_logic: Any | None = None
        if deadman:
            self._dm_logic = load_deadman_logic()
            self._dm = self._dm_logic.DeadmanLogic(self._t_last, wall=wall())
            self._dm_last_pub = self._t_last
        # background ticker (realtime only)
        self._ticker: threading.Thread | None = None
        self._stop_ticker = threading.Event()

    # -- gate (the same call RosbridgeTransport makes) ------------------------------------------

    @staticmethod
    def operator_gate(tool_context: ToolContext | None) -> Callable[[str, str], str | None]:
        return lambda kind, target: gate_command(kind, target, tool_context=tool_context, tool=GATE_TOOL)

    # -- Transport protocol ----------------------------------------------------------------------

    def publish(
        self,
        *,
        topic: str,
        type: str,
        fields: dict[str, Any],
        count: int,
        rate: float,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        refusal = self.operator_gate(tool_context)("publish", topic)
        if refusal is not None:
            return _err(refusal)
        count = max(1, int(count))
        period = 1.0 / float(rate) if rate and rate > 0 else 0.0
        with self._stream_lock:
            generation = self._stream_generation
        self._ensure_ticker()
        sent = 0
        aborted = False
        for _ in range(count):
            with self._stream_lock:
                if self._stream_generation != generation:
                    aborted = True
                    break
            self._deliver(topic, dict(fields))
            sent += 1
            if self.realtime and count > 1 and period > 0:
                self._sleep(period)
        self.advance()
        text = f"published {sent} message(s) to {topic}" + (" (interrupted by stop)" if aborted else "")
        return _ok(text, sent=sent, aborted=aborted)

    def abort_stream(self) -> None:
        """Interrupt the command stream in flight; the caller's zero pair follows on a new generation."""
        with self._stream_lock:
            self._stream_generation += 1

    def warm(self, topic: str, type: str) -> bool:
        self._advertised.add(topic)
        return True

    def echo(self, *, topic: str, type: str | None, count: int, timeout: float) -> dict[str, Any]:
        self.advance()
        count = max(1, int(count))
        if topic == DEADMAN_STATE_TOPIC:
            samples: list[dict[str, Any]] = [{"data": json.dumps(self.deadman_state())}] * count
        elif topic in (MANUAL_DRIVE_TOPIC, SERVO_MSG_TOPIC):
            with self._lock:
                samples = [dict(self.servo)] * count
        else:
            with self._lock:
                samples = list(self._published.get(topic, [])[-count:])
        return _ok(f"echo {topic}:\n{json.dumps(samples)}")

    # -- ServiceCapable protocol -----------------------------------------------------------------

    def service_call(
        self,
        *,
        service: str,
        type: str,
        fields: dict[str, Any],
        tool_context: ToolContext | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        refusal = self.operator_gate(tool_context)("service_call", service)
        if refusal is not None:
            return _err(refusal)
        handler = _SERVICES.get(service)
        if handler is None:
            return _err(f"service {service} does not exist on the twin")
        values = handler(self, dict(fields or {}))
        return _ok(_service_text(service, values))

    # -- services (ctrl_pkg, i2c_pkg, servo_pkg) -------------------------------------------------

    def _svc_vehicle_state(self, args: dict[str, Any]) -> dict[str, Any]:
        state = args.get("state")
        if isinstance(state, bool) or state not in (0, 1, 2):
            return {"error": 1}
        with self._lock:
            # ctrl_node.stateHdl: deactivate the current state (zero pair), then switch.
            self.enabled = False
            self.mode = int(state)
        self._write_servo(0.0, 0.0, "mode_change")
        return {"error": 0}

    def _svc_enable_state(self, args: dict[str, Any]) -> dict[str, Any]:
        is_active = args.get("is_active")
        if not isinstance(is_active, bool):
            return {"error": 1}
        with self._lock:
            self.enabled = is_active
        if not is_active:
            self._write_servo(0.0, 0.0, "mode_change")
        return {"error": 0}

    def _svc_battery(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"level": int(self.battery)}

    def _svc_set_led(self, args: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, int] = {}
        for key in ("red", "green", "blue"):
            value = args.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= LED_MAX:
                return {"error": 1}
            values[key] = value
        self._set_led(values, "service")
        return {"error": 0}

    def _svc_get_led(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        with self._lock:
            return {**self.led, "error": 0}

    def _svc_get_calibration(self, args: dict[str, Any]) -> dict[str, Any]:
        cal_type = args.get("cal_type")
        if isinstance(cal_type, bool) or cal_type not in (0, 1):
            return {"max": 0, "mid": 0, "min": 0, "polarity": 0, "error": 1}
        return {**CALIBRATION_ANSWERS[int(cal_type)], "error": 0}

    def _set_led(self, values: dict[str, int], source: str) -> None:
        with self._lock:
            self.led = dict(values)
            self.led_history.append({"t": self._clock(), "source": source, **values})

    # -- reads -------------------------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        text = f"backend: kinematic twin; connected to {TWIN_ENDPOINT}"
        return {"connected": True, "rtt_ms": 0.0, "text": text}

    def list_topics(self) -> list[str]:
        return [name for name, _ in TWIN_GRAPH]

    def topic(self, name: str, type: str) -> TopicHandle:
        """A persistent topic handle for the heartbeat and the deadman echo."""
        self._ensure_ticker()
        return TwinTopic(self, name, type)

    def pose(self) -> dict[str, float]:
        """``{x, y, yaw, v}`` now (metres, radians, m/s), integrated up to this instant."""
        self.advance()
        with self._lock:
            return {
                "x": round(self.x, 4),
                "y": round(self.y, 4),
                "yaw": round(self.yaw, 4),
                "v": round(self.v, 4),
            }

    def deadman_state(self) -> dict[str, Any]:
        if self._dm is None:
            return {"state": "idle", "gap_ms": 0, "since": None, "trips": 0}
        with self._lock:
            return dict(self._dm.state_dict(self._clock()))

    def state(self) -> dict[str, Any]:
        """Inspection, in the fake car's shape plus the pose."""
        self.advance()
        with self._lock:
            return {
                "mode": self.mode,
                "enabled": self.enabled,
                "armed": self.mode == 0 and self.enabled,
                "battery": self.battery,
                "led": dict(self.led),
                "last_servo": dict(self.servo),
                "servo_count": len(self.servo_history),
                "manual_drive_seen": self.manual_drive_seen,
                "drops": dict(self.drops),
                "heartbeat_count": self.heartbeats,
                "deadman": self.deadman_state(),
                "pose": {"x": self.x, "y": self.y, "yaw": self.yaw, "v": self.v},
                "odometer_m": self.odometer_m,
            }

    # -- graph plumbing ----------------------------------------------------------------------------

    def _deliver(self, topic: str, message: dict[str, Any]) -> None:
        """A message published on ``topic`` reaches the twin's nodes."""
        with self._lock:
            history = self._published.setdefault(topic, [])
            history.append(message)
            if len(history) > 200:
                del history[:-200]
        if topic == MANUAL_DRIVE_TOPIC:
            self.handle_manual_drive(message)
        elif topic == HEARTBEAT_TOPIC:
            self.on_heartbeat()
        elif topic == SERVO_MSG_TOPIC:
            reason = range_reason(message)
            if reason is None:
                self._write_servo(float(message["angle"]), float(message["throttle"]), "direct")
        self._fanout(topic, message)

    def _subscribe(self, topic: str, handle: TwinTopic) -> None:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(handle)
        if topic == DEADMAN_STATE_TOPIC:
            self._publish_deadman_state()

    def _unsubscribe(self, topic: str, handle: TwinTopic) -> None:
        with self._lock:
            handles = self._subscribers.get(topic, [])
            if handle in handles:
                handles.remove(handle)

    def _fanout(self, topic: str, message: dict[str, Any]) -> None:
        with self._lock:
            handles = list(self._subscribers.get(topic, []))
        for handle in handles:
            callback = handle.callback
            if callback is None:
                continue
            try:
                callback(dict(message))
            except Exception as exc:  # a bad subscriber must not stop the twin
                logger.warning("twin subscriber on %s failed: %s", topic, exc)

    # -- ctrl node + servo node ---------------------------------------------------------------------

    def handle_manual_drive(self, fields: dict[str, Any]) -> str | None:
        """Apply the ctrl node's rules to one ``manual_drive``; ``None`` when relayed, else the reason."""
        now = self._clock()
        with self._lock:
            self.manual_drive_seen += 1
            reason = range_reason(fields)
            if reason is not None:
                self.drops["out_of_range" if "range" in reason else "malformed"] += 1
                return reason
            if self.mode != 0:
                self.drops["not_armed"] += 1
                return f"vehicle_state is {self.mode}, not 0 (manual); ctrl node does not relay"
            if not self.enabled:
                self.drops["not_armed"] += 1
                return "enable_state is_active is false; ctrl node does not relay"
            angle, throttle = float(fields["angle"]), float(fields["throttle"])
            actions = self._dm.on_manual_drive(now, angle, throttle) if self._dm is not None else []
        self._write_servo(angle, throttle, "relay")
        if actions:
            self._apply_deadman_actions(actions, now)
        return None

    def _write_servo(self, angle: float, throttle: float, source: str) -> None:
        self.advance()  # integrate the old command up to now before the new one takes over
        with self._lock:
            self.servo = {"angle": angle, "throttle": throttle}
            self.servo_history.append(
                {"t": self._clock(), "angle": angle, "throttle": throttle, "source": source}
            )
            if len(self.servo_history) > 2000:
                del self.servo_history[:-2000]
            self.v, _ = servo_to_twist(angle, throttle, self.calibration)
        self._emit_body(force=abs(self.v) < REST_EPS)

    # -- heartbeat + deadman -------------------------------------------------------------------------

    def on_heartbeat(self) -> None:
        now = self._clock()
        with self._lock:
            self.heartbeats += 1
            actions = self._dm.on_heartbeat(now, self._wall()) if self._dm is not None else []
        if actions:
            self._apply_deadman_actions(actions, now)

    def _apply_deadman_actions(self, actions: list[str], now: float) -> None:
        logic = self._dm_logic
        assert logic is not None
        for action in actions:
            if action == logic.ACTION_ZERO:
                # Ten zero pairs at 20 Hz on the car; the twin's servo is a value, one write is the burst.
                self._write_servo(0.0, 0.0, "deadman")
                self._fanout(MANUAL_DRIVE_TOPIC, {"angle": 0.0, "throttle": 0.0})
            elif action == logic.ACTION_LED_RED:
                self._set_led(dict(logic.red_led_fields()), "deadman")
            elif action == logic.ACTION_LED_GREEN:
                self._set_led(dict(logic.green_led_fields()), "deadman")
            elif action == logic.ACTION_LED_OFF:
                self._set_led(dict(logic.off_led_fields()), "deadman")
            elif action == logic.ACTION_PUBLISH_STATE:
                self._publish_deadman_state()
        self._dm_last_pub = now

    def _publish_deadman_state(self) -> None:
        if self._dm is None:
            return
        self._fanout(DEADMAN_STATE_TOPIC, {"data": json.dumps(self.deadman_state())})

    # -- integration -------------------------------------------------------------------------------

    def advance(self, now: float | None = None) -> None:
        """Integrate the held command from the last step to ``now`` and run the deadman tick."""
        now = self._clock() if now is None else float(now)
        actions: list[str] = []
        with self._lock:
            dt = now - self._t_last
            if dt <= 0:
                return
            self._t_last = now
            v = self.v
            if abs(v) >= REST_EPS:
                _, delta = servo_to_twist(self.servo["angle"], self.servo["throttle"], self.calibration)
                # Kinematic bicycle, rear-axle reference: x' = v cos(yaw), y' = v sin(yaw),
                # yaw' = v tan(delta) / L. One Euler step per tick is plenty at 50 Hz and 0.3 m/s.
                self.x += v * math.cos(self.yaw) * dt
                self.y += v * math.sin(self.yaw) * dt
                yaw = self.yaw + v * math.tan(delta) / self.calibration.wheelbase_m * dt
                self.yaw = math.atan2(math.sin(yaw), math.cos(yaw))
                self.odometer_m += abs(v) * dt
            if self._dm is not None:
                actions = list(self._dm.tick(now, self._wall()))
                if not actions and now - self._dm_last_pub >= 0.5:
                    actions = [self._dm_logic.ACTION_PUBLISH_STATE]  # 2 Hz state echo, like the node
        if actions:
            self._apply_deadman_actions(actions, now)
        self._emit_body()

    def _emit_body(self, *, force: bool = False) -> None:
        if self.event_log is None:
            return
        with self._lock:
            now = self._clock()
            moving = abs(self.v) >= REST_EPS
            stopped_now = self._was_moving and not moving
            self._was_moving = moving
            due = self._last_body_emit is None or (now - self._last_body_emit) >= 1.0 / BODY_EVENT_MAX_HZ
            if not (stopped_now or (moving and due) or (force and (moving or stopped_now))):
                return
            self._last_body_emit = now
            payload = {
                "body": TWIN_BODY,
                "x": round(self.x, 4),
                "y": round(self.y, 4),
                "yaw": round(self.yaw, 4),
                "v": round(self.v, 4),
                "t_ms": int(self._wall() * 1000),
            }
        try:
            self.event_log.emit("body", payload, source="twin")
        except Exception as exc:  # the log never stops the twin
            logger.debug("twin body emit failed: %s", exc)

    # -- ticker ------------------------------------------------------------------------------------

    def _ensure_ticker(self) -> None:
        if not self.realtime or (self._ticker is not None and self._ticker.is_alive()):
            return
        self._stop_ticker.clear()
        self._ticker = threading.Thread(target=self._run_ticker, name="deepracer-twin", daemon=True)
        self._ticker.start()

    def _run_ticker(self) -> None:
        while not self._stop_ticker.wait(TICK_S):
            try:
                self.advance()
            except Exception as exc:  # pragma: no cover - keep ticking
                logger.warning("twin tick failed: %s", exc)

    def close(self) -> None:
        """Stop the ticker. The servo keeps its last value: there is no watchdog to hide behind."""
        self._stop_ticker.set()
        ticker, self._ticker = self._ticker, None
        if ticker is not None and ticker.is_alive() and ticker is not threading.current_thread():
            ticker.join(1.0)


_SERVICES: dict[str, Callable[[TwinTransport, dict[str, Any]], dict[str, Any]]] = {
    "/ctrl_pkg/vehicle_state": TwinTransport._svc_vehicle_state,
    "/ctrl_pkg/enable_state": TwinTransport._svc_enable_state,
    "/i2c_pkg/battery_level": TwinTransport._svc_battery,
    "/servo_pkg/set_led_state": TwinTransport._svc_set_led,
    "/servo_pkg/get_led_state": TwinTransport._svc_get_led,
    "/servo_pkg/get_calibration": TwinTransport._svc_get_calibration,
}


class BodyEventLog:
    """An event log that stamps every payload with ``body: <label>`` and forwards the rest.

    Two runtimes in one process (Two Bodies) share one ``events.jsonl``; the stamp is how a
    reader tells the car body's ``motion`` from the twin's. Everything else (``session``,
    ``read``, ``save_frame``, ``flush`` ...) is the wrapped log's.
    """

    def __init__(self, inner: Any, label: str) -> None:
        self._inner = inner
        self.label = str(label)

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        beat: str | None = None,
    ) -> dict[str, Any]:
        stamped = dict(payload or {})
        stamped.setdefault("body", self.label)
        return self._inner.emit(type, stamped, source=source, beat=beat)

    @property
    def beat(self) -> str | None:
        return getattr(self._inner, "beat", None)

    @beat.setter
    def beat(self, value: str | None) -> None:
        self._inner.beat = value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


__all__ = [
    "BODY_EVENT_MAX_HZ",
    "CALIBRATION_ANSWERS",
    "MANUAL_DRIVE_TOPIC",
    "SERVO_MSG_TOPIC",
    "TICK_S",
    "TWIN_BODY",
    "TWIN_ENDPOINT",
    "TWIN_GRAPH",
    "TWIN_SERVICES",
    "BodyEventLog",
    "TwinTopic",
    "TwinTransport",
    "load_deadman_logic",
    "range_reason",
    "servo_to_twist",
]
