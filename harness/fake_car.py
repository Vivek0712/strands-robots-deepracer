"""A DeepRacer you can crash into as often as you like: the car's control stack, emulated.

This is a rosbridge v2 protocol server (`ws://127.0.0.1:9091`) that behaves like the stock Foxy
car's `ctrl_pkg`, `servo_pkg`, `i2c_pkg` and the project's on-car deadman: it refuses to relay a
drive command until the agent has armed it with `vehicle_state {state: 0}` and
`enable_state {is_active: true}`, drops any angle or throttle outside [-1, 1], latches the last
servo value forever because the real car has no watchdog, answers battery, LED and calibration
services, counts heartbeats, trips an optional emulated deadman after a 300 ms gap, and times
out the first service call after `restart()` the way the real stack does. Physics stops the
car; the decider explains: this fake exists so the drive loop's zero pair, the deadman and the
gate are exercised in CI before the wheels ever touch the floor.

Protocol surface (what `strands_robots.rosbridge.rosbridge_action` and roslibpy send):
`advertise`, `unadvertise`, `publish`, `subscribe`, `unsubscribe`, `call_service` (answered with
`service_response` carrying the request `id`), `set_level` and `auth` (accepted, ignored), and
the rosapi services `/rosapi/topics`, `/rosapi/services`, `/rosapi/topic_type`,
`/rosapi/service_type`, `/rosapi/topics_for_type`, `/rosapi/services_for_type`, `/rosapi/nodes`,
`/rosapi/get_time`. The fake never sends `op: status` unless asked (`send_status=True`): roslibpy
2.1 has no handler for it and logs an exception per status frame.

Run it: `python -m harness.fake_car` (Ctrl-C to stop). Control it over HTTP on
`http://127.0.0.1:8092`: `/state`, `/battery?level=`, `/restart`, `/frame?label=`,
`/deadman?enabled=`, `/calibration?profile=`, `/reset`.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import Server, ServerConnection, serve

from harness import CONTROL_PORT, ROSBRIDGE_PORT
from harness.frames import LABELS
from harness.shared import SharedState

logger = logging.getLogger("harness.fake_car")

MANUAL_DRIVE = "/webserver_pkg/manual_drive"
SERVO_MSG = "/ctrl_pkg/servo_msg"
HEARTBEAT = "/deepracer_agent/heartbeat"
DEADMAN_STATE = "/deepracer_agent/deadman_state"
SERVO_TYPE = "deepracer_interfaces_pkg/msg/ServoCtrlMsg"

#: Deadman rule from CONTRACTS §3.
DEADMAN_GAP_S = 0.300
DEADMAN_RESUME_S = 1.0
DEADMAN_IDLE_S = 30.0
DEADMAN_ZERO_BURST = 10
DEADMAN_BURST_HZ = 20.0

LED_MAX = 10_000_000
LED_RED = {"red": LED_MAX, "green": 0, "blue": 0}

#: servo_mgr.hpp compile-time defaults: what an uninitialised car reports. The measured car
#: (throttle 0.3 -> 1405500 ns from mid 1446000) matches this motor profile exactly.
CALIBRATION_PROFILES: dict[str, dict[int, dict[str, int]]] = {
    "uninitialised": {
        0: {"min": 1_200_000, "mid": 1_450_000, "max": 1_700_000, "polarity": 1},
        1: {"min": 1_311_000, "mid": 1_446_000, "max": 1_603_500, "polarity": -1},
    },
    "calibrated": {
        0: {"min": 1_230_000, "mid": 1_470_000, "max": 1_690_000, "polarity": 1},
        1: {"min": 1_335_000, "mid": 1_446_000, "max": 1_580_000, "polarity": -1},
    },
}

#: The stock graph the car exposes through rosapi (ROS 2 three-segment type names, as Foxy's
#: rosapi reports them). The project's two `/deepracer_agent/` names are listed as the deadman
#: node would register them.
STOCK_TOPICS: dict[str, str] = {
    MANUAL_DRIVE: SERVO_TYPE,
    "/webserver_pkg/calibration_drive": SERVO_TYPE,
    SERVO_MSG: SERVO_TYPE,
    "/ctrl_pkg/raw_pwm": SERVO_TYPE,
    "/camera_pkg/display_mjpeg": "sensor_msgs/msg/Image",
    "/camera_pkg/video_mjpeg": "deepracer_interfaces_pkg/msg/CameraMsg",
    "/sensor_fusion_pkg/sensor_msg": "deepracer_interfaces_pkg/msg/EvoSensorMsg",
    "/deepracer_systems_pkg/network_connection_status": (
        "deepracer_interfaces_pkg/msg/NetworkConnectionStatus"
    ),
    HEARTBEAT: "std_msgs/msg/Header",
    DEADMAN_STATE: "std_msgs/msg/String",
    "/rosout": "rcl_interfaces/msg/Log",
    "/parameter_events": "rcl_interfaces/msg/ParameterEvent",
}

STOCK_SERVICES: dict[str, str] = {
    "/ctrl_pkg/vehicle_state": "deepracer_interfaces_pkg/srv/ActiveStateSrv",
    "/ctrl_pkg/enable_state": "deepracer_interfaces_pkg/srv/EnableStateSrv",
    "/ctrl_pkg/get_ctrl_modes": "deepracer_interfaces_pkg/srv/GetCtrlModesSrv",
    "/ctrl_pkg/autonomous_throttle": "deepracer_interfaces_pkg/srv/NavThrottleSrv",
    "/i2c_pkg/battery_level": "deepracer_interfaces_pkg/srv/BatteryLevelSrv",
    "/servo_pkg/set_led_state": "deepracer_interfaces_pkg/srv/SetLedCtrlSrv",
    "/servo_pkg/get_led_state": "deepracer_interfaces_pkg/srv/GetLedCtrlSrv",
    "/servo_pkg/get_calibration": "deepracer_interfaces_pkg/srv/GetCalibrationSrv",
    "/servo_pkg/set_calibration": "deepracer_interfaces_pkg/srv/SetCalibrationSrv",
    "/servo_pkg/servo_gpio": "deepracer_interfaces_pkg/srv/ServoGPIOSrv",
    "/device_info_pkg/get_device_info": "deepracer_interfaces_pkg/srv/GetDeviceInfoSrv",
    "/sensor_fusion_pkg/sensor_data_status": "deepracer_interfaces_pkg/srv/SensorStatusCheckSrv",
    "/camera_pkg/media_state": "deepracer_interfaces_pkg/srv/VideoStateSrv",
    "/rosapi/topics": "rosapi/srv/Topics",
    "/rosapi/services": "rosapi/srv/Services",
    "/rosapi/topic_type": "rosapi/srv/TopicType",
    "/rosapi/service_type": "rosapi/srv/ServiceType",
    "/rosapi/topics_for_type": "rosapi/srv/TopicsForType",
    "/rosapi/services_for_type": "rosapi/srv/ServicesForType",
    "/rosapi/nodes": "rosapi/srv/Nodes",
    "/rosapi/get_time": "rosapi/srv/GetTime",
}

STOCK_NODES = (
    "/ctrl_pkg/control_node",
    "/servo_pkg/servo_node",
    "/i2c_pkg/battery_node",
    "/webserver_pkg/webserver_publisher_node",
    "/camera_pkg/camera_node",
    "/device_info_pkg/device_info_node",
    "/deepracer_agent/deadman",
    "/rosapi",
    "/rosbridge_websocket",
)


def canonical_type(type_name: str, kind: str = "msg") -> str:
    """`pkg/Name` -> `pkg/msg/Name` (ROS 2 spelling); three-segment names pass through."""
    parts = type_name.split("/")
    if len(parts) == 2:
        return f"{parts[0]}/{kind}/{parts[1]}"
    return type_name


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class FakeCar:
    """The emulated car. Thread-safe; every public method may be called from any thread."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = ROSBRIDGE_PORT,
        control_port: int | None = CONTROL_PORT,
        *,
        shared: SharedState | None = None,
        deadman: bool = False,
        battery: int = 10,
        calibration: str = "calibrated",
        send_status: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.control_port = control_port
        self.shared = shared or SharedState()
        self.send_status = send_status
        self._lock = threading.RLock()
        self._server: Server | None = None
        self._server_thread: threading.Thread | None = None
        self._control: ThreadingHTTPServer | None = None
        self._control_thread: threading.Thread | None = None
        self._deadman_thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._conns: set[ServerConnection] = set()
        self._subs: dict[str, dict[ServerConnection, set[str]]] = {}
        self._adverts: dict[ServerConnection, dict[str, str]] = {}
        self._topics: dict[str, str] = dict(STOCK_TOPICS)
        self._boot_battery = battery
        self._boot_calibration = calibration
        self._boot_deadman = deadman
        self._init_state(battery=battery, calibration=calibration, deadman=deadman)

    # ------------------------------------------------------------------ state
    def _init_state(self, *, battery: int, calibration: str, deadman: bool) -> None:
        with self._lock:
            self.mode = 0
            self.enabled = False
            self.battery = battery
            self.calibration = calibration
            self._led: dict[str, int] = {"red": 0, "green": 0, "blue": 0}
            self._led_history: list[dict[str, Any]] = []
            self._last_servo: dict[str, float] = {"angle": 0.0, "throttle": 0.0}
            self._history: list[dict[str, Any]] = []
            self._manual_drive_seen = 0
            self._drops = {"not_armed": 0, "out_of_range": 0, "malformed": 0, "unknown_topic": 0}
            self._hb_count = 0
            self._hb_last: float | None = None
            self._hb_frame_id: str | None = None
            self._restart_pending = False
            self._restart_timeouts = 0
            self._restarts = 0
            self._service_calls: list[dict[str, Any]] = []
            self._dm_enabled = deadman
            self._dm_state = "idle"
            self._dm_since = _now_iso()
            self._dm_trips = 0
            self._dm_last_trip_gap_ms: int | None = None
            self._dm_resume_since: float | None = None
            self._dm_last_pub = 0.0
            self.shared.set(battery=battery, calibration=calibration)

    def reset(self) -> None:
        """Back to the boot state (mode 0, disabled, history cleared); connections stay."""
        self._init_state(
            battery=self._boot_battery, calibration=self._boot_calibration, deadman=self._boot_deadman
        )
        self.shared.set(label="clear")
        with self._lock:
            self._topics = dict(STOCK_TOPICS)
            for adverts in self._adverts.values():
                self._topics.update(adverts)

    def restart(self) -> None:
        """Emulate `systemctl restart deepracer-core`: the next service call times out once."""
        with self._lock:
            self.mode = 0
            self.enabled = False
            self._last_servo = {"angle": 0.0, "throttle": 0.0}
            self._restart_pending = True
            self._restarts += 1

    # inspection ---------------------------------------------------------
    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode,
                "enabled": self.enabled,
                "armed": self.mode == 0 and self.enabled,
                "battery": self.battery,
                "calibration": self.calibration,
                "label": self.shared.get("label"),
                "led": dict(self._led),
                "last_servo": dict(self._last_servo),
                "last_pwm": self.last_pwm(),
                "servo_count": len(self._history),
                "manual_drive_seen": self._manual_drive_seen,
                "drops": dict(self._drops),
                "heartbeat_count": self._hb_count,
                "heartbeat_frame_id": self._hb_frame_id,
                "heartbeat_gap_ms": self._gap_ms(),
                "deadman": self.deadman_state(),
                "restart_pending": self._restart_pending,
                "restart_timeouts": self._restart_timeouts,
                "restarts": self._restarts,
                "connections": len(self._conns),
                "subscriptions": {t: len(c) for t, c in self._subs.items() if c},
                "topics": sorted(self._topics),
            }

    def last_servo(self) -> dict[str, float]:
        with self._lock:
            return dict(self._last_servo)

    def servo_history(self, source: str | None = None) -> list[dict[str, Any]]:
        """Every write to `/ctrl_pkg/servo_msg`: `{ts, angle, throttle, source}`.

        `source` is `relay` (ctrl node forwarded a manual_drive), `mode_change` (ctrl node's zero
        on deactivate), `deadman` (trip burst) or `direct` (a client published to servo_msg).
        """
        with self._lock:
            rows = [dict(r) for r in self._history]
        return [r for r in rows if source is None or r["source"] == source]

    def heartbeat_count(self) -> int:
        with self._lock:
            return self._hb_count

    def led(self) -> dict[str, int]:
        with self._lock:
            return dict(self._led)

    def led_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._led_history]

    def service_calls(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._service_calls]

    def last_pwm(self) -> dict[str, int]:
        """The duty cycle the servo node would have written, in ns, under the current profile."""
        with self._lock:
            prof = CALIBRATION_PROFILES[self.calibration]
            return {
                "throttle_ns": self._duty(self._last_servo["throttle"], prof[1]),
                "steering_ns": self._duty(self._last_servo["angle"], prof[0]),
            }

    @staticmethod
    def _duty(value: float, cal: dict[str, int]) -> int:
        adj = value * cal["polarity"]
        if adj < 0:
            return int(cal["mid"] + adj * (cal["mid"] - cal["min"]))
        if adj > 0:
            return int(cal["mid"] + adj * (cal["max"] - cal["mid"]))
        return cal["mid"]

    # control ------------------------------------------------------------
    def set_battery(self, level: int) -> None:
        with self._lock:
            self.battery = int(level)
        self.shared.set(battery=int(level))

    def set_label(self, label: str) -> None:
        if label not in LABELS:
            raise ValueError(f"unknown frame label {label!r}; known: {', '.join(LABELS)}")
        self.shared.set(label=label)

    def set_calibration_profile(self, profile: str) -> None:
        if profile not in CALIBRATION_PROFILES:
            raise ValueError(f"unknown calibration profile {profile!r}")
        with self._lock:
            self.calibration = profile
        self.shared.set(calibration=profile)

    def set_deadman(self, enabled: bool) -> None:
        with self._lock:
            self._dm_enabled = bool(enabled)
            if not enabled:
                self._dm_state = "idle"
                self._dm_since = _now_iso()
                self._dm_resume_since = None

    def deadman_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._dm_enabled,
                "state": self._dm_state,
                "gap_ms": self._gap_ms(),
                "since": self._dm_since,
                "trips": self._dm_trips,
                "last_trip_gap_ms": self._dm_last_trip_gap_ms,
            }

    def _gap_ms(self) -> int:
        if self._hb_last is None:
            return -1
        return int((time.monotonic() - self._hb_last) * 1000)

    # ------------------------------------------------------------ lifecycle
    def start(self) -> FakeCar:
        if self._server is not None:
            return self
        self._stopping.clear()
        self._server = serve(
            self._handle, self.host, self.port, compression=None, logger=logger.getChild("ws")
        )
        self._server_thread = threading.Thread(
            target=self._server.serve_forever, name="fake-car-ws", daemon=True
        )
        self._server_thread.start()
        if self.control_port is not None:
            self._control = ThreadingHTTPServer((self.host, self.control_port), _control_handler(self))
            self._control.daemon_threads = True
            self._control_thread = threading.Thread(
                target=self._control.serve_forever, name="fake-car-control", daemon=True
            )
            self._control_thread.start()
        self._deadman_thread = threading.Thread(
            target=self._deadman_loop, name="fake-car-deadman", daemon=True
        )
        self._deadman_thread.start()
        logger.info(
            "fake car on ws://%s:%d (control http://%s:%s)",
            self.host,
            self.port,
            self.host,
            self.control_port,
        )
        return self

    def stop(self) -> None:
        self._stopping.set()
        if self._control is not None:
            self._control.shutdown()
            self._control.server_close()
            self._control = None
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._server_thread is not None:
            self._server_thread.join(timeout=5)
            self._server_thread = None
        if self._deadman_thread is not None:
            self._deadman_thread.join(timeout=2)
            self._deadman_thread = None

    def __enter__(self) -> FakeCar:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    # ------------------------------------------------------------ protocol
    def _send(self, conn: ServerConnection, payload: dict[str, Any]) -> None:
        try:
            conn.send(json.dumps(payload))
        except ConnectionClosed:
            self._forget(conn)
        except OSError as exc:  # pragma: no cover - socket torn down under us
            logger.debug("send failed: %s", exc)

    def _status(self, conn: ServerConnection, level: str, msg: str, req_id: str | None = None) -> None:
        logger.info("status %s: %s", level, msg)
        if not self.send_status:
            return
        payload: dict[str, Any] = {"op": "status", "level": level, "msg": msg}
        if req_id is not None:
            payload["id"] = req_id
        self._send(conn, payload)

    def _forget(self, conn: ServerConnection) -> None:
        with self._lock:
            self._conns.discard(conn)
            for subs in self._subs.values():
                subs.pop(conn, None)
            adverts = self._adverts.pop(conn, {})
            for topic in adverts:
                still = any(topic in a for a in self._adverts.values())
                if topic not in STOCK_TOPICS and not still:
                    self._topics.pop(topic, None)

    def _handle(self, conn: ServerConnection) -> None:
        with self._lock:
            self._conns.add(conn)
        try:
            for raw in conn:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                try:
                    msg = json.loads(raw)
                except ValueError:
                    self._status(conn, "error", "message is not valid JSON")
                    continue
                if not isinstance(msg, dict) or "op" not in msg:
                    self._status(conn, "error", "message has no op")
                    continue
                try:
                    self._dispatch(conn, msg)
                except Exception:
                    logger.exception("fake car failed on %s", msg)
        except ConnectionClosed:
            pass
        finally:
            self._forget(conn)

    def _dispatch(self, conn: ServerConnection, msg: dict[str, Any]) -> None:
        op = msg["op"]
        req_id = msg.get("id")
        if op == "advertise":
            topic, type_ = msg.get("topic"), msg.get("type")
            if not topic or not type_:
                self._status(conn, "error", "advertise needs topic and type", req_id)
                return
            with self._lock:
                self._topics.setdefault(topic, canonical_type(type_))
                self._adverts.setdefault(conn, {})[topic] = canonical_type(type_)
        elif op == "unadvertise":
            topic = msg.get("topic")
            with self._lock:
                adverts = self._adverts.get(conn, {})
                adverts.pop(topic, None)
                still = any(topic in a for a in self._adverts.values())
                if topic and topic not in STOCK_TOPICS and not still:
                    self._topics.pop(topic, None)
        elif op == "subscribe":
            topic = msg.get("topic")
            if not topic:
                self._status(conn, "error", "subscribe needs topic", req_id)
                return
            with self._lock:
                if topic not in self._topics and msg.get("type"):
                    self._topics[topic] = canonical_type(msg["type"])
                self._subs.setdefault(topic, {}).setdefault(conn, set()).add(req_id or topic)
        elif op == "unsubscribe":
            topic = msg.get("topic")
            with self._lock:
                subs = self._subs.get(topic, {})
                ids = subs.get(conn)
                if ids is not None:
                    if req_id is None:
                        ids.clear()
                    else:
                        ids.discard(req_id)
                    if not ids:
                        subs.pop(conn, None)
        elif op == "publish":
            self._on_publish(conn, msg)
        elif op == "call_service":
            self._on_call_service(conn, msg)
        elif op in {"set_level", "auth", "advertise_service", "unadvertise_service", "fragment", "png"}:
            logger.debug("accepted %s", op)
        else:
            self._status(conn, "error", f"unknown op {op!r}", req_id)

    # publish ------------------------------------------------------------
    def _on_publish(self, conn: ServerConnection, msg: dict[str, Any]) -> None:
        topic = msg.get("topic")
        body = msg.get("msg")
        if not topic or not isinstance(body, dict):
            with self._lock:
                self._drops["malformed"] += 1
            self._status(conn, "error", "publish needs topic and a msg object", msg.get("id"))
            return
        with self._lock:
            known = topic in self._topics
        if not known:
            with self._lock:
                self._drops["unknown_topic"] += 1
            self._status(conn, "error", f"publish to unadvertised topic {topic}", msg.get("id"))
            return
        # Every subscriber of the raw topic sees the message, like any ROS topic.
        self._publish(topic, body, exclude=None)
        if topic == MANUAL_DRIVE:
            reason = self.handle_manual_drive(body)
            if reason:
                logger.debug("manual_drive dropped: %s", reason)
        elif topic == SERVO_MSG:
            reason = self._range_reason(body)
            if reason:
                with self._lock:
                    self._drops["out_of_range" if "range" in reason else "malformed"] += 1
            else:
                self._write_servo(float(body["angle"]), float(body["throttle"]), "direct", relay=False)
        elif topic == HEARTBEAT:
            with self._lock:
                self._hb_count += 1
                self._hb_last = time.monotonic()
                frame_id = body.get("frame_id")
                self._hb_frame_id = str(frame_id) if frame_id is not None else None

    @staticmethod
    def _range_reason(body: dict[str, Any]) -> str | None:
        for key in ("angle", "throttle"):
            if key not in body:
                return f"{key} missing from ServoCtrlMsg"
            value = body[key]
            if isinstance(value, bool) or not isinstance(value, int | float):
                return f"{key} is not a number"
            if math.isnan(value) or math.isinf(value):
                return f"{key} is not finite"
            if value < -1.0 or value > 1.0:
                return f"{key} {value} out of range [-1, 1]"
        return None

    def handle_manual_drive(self, body: dict[str, Any]) -> str | None:
        """Apply the ctrl node's rules to one `/webserver_pkg/manual_drive` message.

        Returns `None` when the message was relayed to `/ctrl_pkg/servo_msg`, otherwise the
        reason it was dropped (the refusal table in `tests/unit/test_fake_car.py` lists them).
        """
        with self._lock:
            self._manual_drive_seen += 1
            reason = self._range_reason(body)
            if reason is not None:
                self._drops["out_of_range" if "range" in reason else "malformed"] += 1
                return reason
            if self.mode != 0:
                self._drops["not_armed"] += 1
                return f"vehicle_state is {self.mode}, not 0 (manual); ctrl node does not relay"
            if not self.enabled:
                self._drops["not_armed"] += 1
                return "enable_state is_active is false; ctrl node does not relay"
        self._write_servo(float(body["angle"]), float(body["throttle"]), "relay")
        return None

    def _write_servo(self, angle: float, throttle: float, source: str, *, relay: bool = True) -> None:
        row = {"ts": time.monotonic(), "angle": angle, "throttle": throttle, "source": source}
        with self._lock:
            self._last_servo = {"angle": angle, "throttle": throttle}
            self._history.append(row)
        if relay:
            self._publish(SERVO_MSG, {"angle": angle, "throttle": throttle}, exclude=None)

    def _publish(self, topic: str, body: dict[str, Any], *, exclude: ServerConnection | None) -> None:
        with self._lock:
            targets = [c for c in self._subs.get(topic, {}) if c is not exclude]
        payload = {"op": "publish", "topic": topic, "msg": body}
        for conn in targets:
            self._send(conn, payload)

    # services -----------------------------------------------------------
    def _on_call_service(self, conn: ServerConnection, msg: dict[str, Any]) -> None:
        service = msg.get("service")
        req_id = msg.get("id")
        args = msg.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        with self._lock:
            self._service_calls.append({"service": service, "args": dict(args), "ts": time.monotonic()})
            if self._restart_pending:
                self._restart_pending = False
                self._restart_timeouts += 1
                logger.info("restart emulation: swallowing %s so the client times out once", service)
                return
        handler = _SERVICES.get(service or "")
        if handler is None:
            self._send(
                conn,
                {
                    "op": "service_response",
                    "service": service,
                    "id": req_id,
                    "values": f"Service {service} does not exist",
                    "result": False,
                },
            )
            return
        values = handler(self, args)
        self._send(
            conn,
            {"op": "service_response", "service": service, "id": req_id, "values": values, "result": True},
        )

    def _svc_vehicle_state(self, args: dict[str, Any]) -> dict[str, Any]:
        state = args.get("state")
        if state not in (0, 1, 2):
            return {"error": 1}
        with self._lock:
            # ctrl_node.stateHdl: deactivate the current state (zero pair on servo_msg), switch.
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

    def _svc_get_ctrl_modes(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"modes": [0, 1, 2], "error": 0}

    def _svc_autonomous_throttle(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"error": 0}

    def _svc_battery(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        with self._lock:
            return {"level": int(self.battery)}

    def _svc_set_led(self, args: dict[str, Any]) -> dict[str, Any]:
        values = {}
        for key in ("red", "green", "blue"):
            v = args.get(key)
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= LED_MAX:
                return {"error": 1}
            values[key] = v
        self._set_led(values, "service")
        return {"error": 0}

    def _set_led(self, values: dict[str, int], source: str) -> None:
        with self._lock:
            self._led = dict(values)
            self._led_history.append({"ts": time.monotonic(), "source": source, **values})

    def _svc_get_led(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        with self._lock:
            return {**self._led, "error": 0}

    def _svc_get_calibration(self, args: dict[str, Any]) -> dict[str, Any]:
        cal_type = args.get("cal_type")
        if cal_type not in (0, 1):
            return {"max": 0, "mid": 0, "min": 0, "polarity": 0, "error": 1}
        with self._lock:
            cal = CALIBRATION_PROFILES[self.calibration][cal_type]
        return {
            "max": cal["max"],
            "mid": cal["mid"],
            "min": cal["min"],
            "polarity": cal["polarity"],
            "error": 0,
        }

    def _svc_set_calibration(self, args: dict[str, Any]) -> dict[str, Any]:
        # Calibration is read, never written, without explicit approval (CONTRACTS §9): the
        # fake records the attempt and refuses, so a test can prove nothing writes it.
        with self._lock:
            self._service_calls[-1]["refused"] = "calibration writes are refused by the fake car"
        del args
        return {"error": 1}

    def _svc_servo_gpio(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"error": 0}

    def _svc_device_info(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"hardware_version": "R2.1", "software_version": "2.0.383.0", "error": 0}

    def _svc_sensor_status(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"lidar_status": 1, "single_camera_status": 0, "stereo_camera_status": 1, "error": 0}

    def _svc_media_state(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"error": 0}

    # rosapi
    def _svc_rosapi_topics(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        with self._lock:
            names = sorted(self._topics)
            return {"topics": names, "types": [self._topics[n] for n in names]}

    def _svc_rosapi_services(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"services": sorted(STOCK_SERVICES)}

    def _svc_rosapi_topic_type(self, args: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return {"type": self._topics.get(str(args.get("topic", "")), "")}

    def _svc_rosapi_service_type(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"type": STOCK_SERVICES.get(str(args.get("service", "")), "")}

    def _svc_rosapi_topics_for_type(self, args: dict[str, Any]) -> dict[str, Any]:
        wanted = canonical_type(str(args.get("type", "")))
        with self._lock:
            return {"topics": sorted(n for n, t in self._topics.items() if t == wanted)}

    def _svc_rosapi_services_for_type(self, args: dict[str, Any]) -> dict[str, Any]:
        wanted = canonical_type(str(args.get("type", "")), "srv")
        return {"services": sorted(n for n, t in STOCK_SERVICES.items() if t == wanted)}

    def _svc_rosapi_nodes(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"nodes": list(STOCK_NODES)}

    def _svc_rosapi_get_time(self, args: dict[str, Any]) -> dict[str, Any]:
        del args
        now = time.time()
        return {"time": {"sec": int(now), "nanosec": int((now - int(now)) * 1e9)}}

    # deadman ------------------------------------------------------------
    def _deadman_loop(self) -> None:
        while not self._stopping.is_set():
            time.sleep(0.02)
            trip = False
            with self._lock:
                if not self._dm_enabled:
                    continue
                now = time.monotonic()
                gap = None if self._hb_last is None else now - self._hb_last
                state = self._dm_state
                new = state
                if gap is None or gap > DEADMAN_IDLE_S:
                    new = "idle"
                    self._dm_resume_since = None
                elif state == "idle":
                    new = "armed"
                elif state == "armed":
                    if gap > DEADMAN_GAP_S:
                        new = "tripped"
                        trip = True
                elif state == "tripped":
                    if gap > DEADMAN_GAP_S:
                        self._dm_resume_since = None
                    else:
                        if self._dm_resume_since is None:
                            self._dm_resume_since = now
                        if now - self._dm_resume_since >= DEADMAN_RESUME_S:
                            new = "armed"
                            self._dm_resume_since = None
                changed = new != state
                if changed:
                    self._dm_state = new
                    self._dm_since = _now_iso()
                    if trip:
                        self._dm_trips += 1
                        self._dm_last_trip_gap_ms = int((gap or 0.0) * 1000)
                due = now - self._dm_last_pub >= 0.5
            if changed or due:
                self._publish_deadman_state()
            if trip:
                self._trip()

    def _publish_deadman_state(self) -> None:
        with self._lock:
            self._dm_last_pub = time.monotonic()
            body = {
                "state": self._dm_state,
                "gap_ms": max(self._gap_ms(), 0),
                "since": self._dm_since,
                "trips": self._dm_trips,
            }
        self._publish(DEADMAN_STATE, {"data": json.dumps(body)}, exclude=None)

    def _trip(self) -> None:
        """CONTRACTS §3: LED red (best effort), then ten zero pairs at 20 Hz on both topics."""
        self._set_led(LED_RED, "deadman")
        period = 1.0 / DEADMAN_BURST_HZ
        for _ in range(DEADMAN_ZERO_BURST):
            self._write_servo(0.0, 0.0, "deadman")
            self._publish(MANUAL_DRIVE, {"angle": 0.0, "throttle": 0.0}, exclude=None)
            time.sleep(period)


_SERVICES = {
    "/ctrl_pkg/vehicle_state": FakeCar._svc_vehicle_state,
    "/ctrl_pkg/enable_state": FakeCar._svc_enable_state,
    "/ctrl_pkg/get_ctrl_modes": FakeCar._svc_get_ctrl_modes,
    "/ctrl_pkg/autonomous_throttle": FakeCar._svc_autonomous_throttle,
    "/i2c_pkg/battery_level": FakeCar._svc_battery,
    "/servo_pkg/set_led_state": FakeCar._svc_set_led,
    "/servo_pkg/get_led_state": FakeCar._svc_get_led,
    "/servo_pkg/get_calibration": FakeCar._svc_get_calibration,
    "/servo_pkg/set_calibration": FakeCar._svc_set_calibration,
    "/servo_pkg/servo_gpio": FakeCar._svc_servo_gpio,
    "/device_info_pkg/get_device_info": FakeCar._svc_device_info,
    "/sensor_fusion_pkg/sensor_data_status": FakeCar._svc_sensor_status,
    "/camera_pkg/media_state": FakeCar._svc_media_state,
    "/rosapi/topics": FakeCar._svc_rosapi_topics,
    "/rosapi/services": FakeCar._svc_rosapi_services,
    "/rosapi/topic_type": FakeCar._svc_rosapi_topic_type,
    "/rosapi/service_type": FakeCar._svc_rosapi_service_type,
    "/rosapi/topics_for_type": FakeCar._svc_rosapi_topics_for_type,
    "/rosapi/services_for_type": FakeCar._svc_rosapi_services_for_type,
    "/rosapi/nodes": FakeCar._svc_rosapi_nodes,
    "/rosapi/get_time": FakeCar._svc_rosapi_get_time,
}


def _control_handler(car: FakeCar) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "FakeCarControl/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("control " + fmt, *args)

        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/state":
                    self._json(200, car.state())
                elif url.path == "/battery":
                    car.set_battery(int(q["level"]))
                    self._json(200, {"ok": True, "battery": car.state()["battery"]})
                elif url.path == "/restart":
                    car.restart()
                    self._json(200, {"ok": True, "restart_pending": True})
                elif url.path == "/frame":
                    car.set_label(q["label"])
                    self._json(200, {"ok": True, "label": q["label"]})
                elif url.path == "/deadman":
                    enabled = q.get("enabled", "1").lower() in {"1", "true", "yes", "on"}
                    car.set_deadman(enabled)
                    self._json(200, {"ok": True, "deadman": car.deadman_state()})
                elif url.path == "/calibration":
                    car.set_calibration_profile(q["profile"])
                    self._json(200, {"ok": True, "calibration": q["profile"]})
                elif url.path == "/reset":
                    car.reset()
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"ok": False, "error": f"no route {url.path}"})
            except (KeyError, ValueError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})

        do_POST = do_GET

    return Handler


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=ROSBRIDGE_PORT)
    ap.add_argument("--control-port", type=int, default=CONTROL_PORT)
    ap.add_argument("--deadman", action="store_true", help="start with the deadman emulation on")
    ap.add_argument("--battery", type=int, default=10)
    ap.add_argument("--calibration", choices=sorted(CALIBRATION_PROFILES), default="calibrated")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(name)s %(message)s")
    car = FakeCar(
        port=a.port,
        control_port=a.control_port,
        deadman=a.deadman,
        battery=a.battery,
        calibration=a.calibration,
    )
    with car:
        print(f"fake car: {car.url}  control: http://{car.host}:{car.control_port}/state  (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
