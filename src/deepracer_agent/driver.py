"""The DeepRacer as a strands robot: drive and stop, gated, with a zero pair in finally.

``DeepRacerRobot`` is upstream's ``MobileBaseRobot`` with the three things a stock
DeepRacer needs: the manual-mode handshake (vehicle_state 0, then enable_state),
a bicycle model that turns "0.3 m/s, 0.5 rad/s" into the servo pair the car
understands, and a heartbeat that runs beside every command stream so the on-car
deadman knows the laptop is alive. Every motion goes through the shared operator
gate; every timed drive ends with a zero servo pair from ``finally``; a trailing
stop that does not land is the drive's error, not a warning. Physics stops the
car; the decider explains; this driver only ever asks for small, bounded moves.
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from typing import Any

from strands import tool
from strands.types.tools import AgentTool, ToolContext
from strands_robots._command_gate import BYPASS_CONSENT_ENV, COMMAND_ALLOW_ENV, match_blocklist
from strands_robots.drivers.base import refuse
from strands_robots.drivers.ros._mobile_base import MobileBaseRobot, ServiceCapable

from deepracer_agent.calibration import Calibration
from deepracer_agent.events import EventLog
from deepracer_agent.transport import SERVO_TYPE, HeartbeatPublisher, RosbridgeTransport, result_text

logger = logging.getLogger(__name__)

SERVO_TOPIC = "/webserver_pkg/manual_drive"
VEHICLE_STATE_SERVICE = "/ctrl_pkg/vehicle_state"
VEHICLE_STATE_TYPE = "deepracer_interfaces_pkg/ActiveStateSrv"
ENABLE_STATE_SERVICE = "/ctrl_pkg/enable_state"
ENABLE_STATE_TYPE = "deepracer_interfaces_pkg/EnableStateSrv"
MANUAL_MODE = 0
HANDSHAKE_RETRIES = 3
HANDSHAKE_TIMEOUT_S = 25.0

#: Below this |linear| the car is at rest; an Ackermann car cannot yaw at rest.
REST_VELOCITY_EPS = 1e-3

MANUAL_HANDSHAKE: list[dict[str, Any]] = [
    {"service": VEHICLE_STATE_SERVICE, "type": VEHICLE_STATE_TYPE, "fields": {"state": MANUAL_MODE}},
    {"service": ENABLE_STATE_SERVICE, "type": ENABLE_STATE_TYPE, "fields": {"is_active": True}},
]


def twist_to_servo(linear: float, angular: float, cal: Calibration) -> tuple[float, float]:
    """Bicycle model: ``(linear m/s, angular rad/s)`` to ``(angle, throttle)`` in [-1, 1].

    Steering angle ``atan(L * w / |v|)`` normalised by the lock, mirrored for
    reverse so backing up steers the mirrored way (upstream's fix); throttle is
    ``v / max_speed`` scaled by ``throttle_at_max_speed`` and the forward sign.
    """
    v = float(linear)
    if abs(v) < REST_VELOCITY_EPS:
        return (0.0, 0.0)
    delta = math.atan2(cal.wheelbase_m * float(angular), abs(v))
    if v < 0:
        delta = -delta
    delta = max(-cal.max_steering_rad, min(cal.max_steering_rad, delta))
    throttle = (v / cal.max_speed_mps) * cal.throttle_at_max_speed * cal.throttle_forward_sign
    throttle = max(-1.0, min(1.0, throttle))
    return (round(delta / cal.max_steering_rad, 6), round(throttle, 6))


def rest_command_error(linear: float, angular: float) -> str | None:
    """Why a command that asks for yaw at rest is refused, or ``None``."""
    if abs(float(linear)) >= REST_VELOCITY_EPS:
        return None
    if float(angular):
        return (
            f"drive_deepracer: angular={float(angular)} rad/s with linear={float(linear)} m/s asks the car "
            "to turn on the spot; an Ackermann car steers its front wheels and cannot yaw at rest. Give the "
            "turn a linear speed (for example linear=0.2), or call stop_deepracer to hold still."
        )
    if float(linear):
        return (
            f"drive_deepracer: linear={float(linear)} m/s is below the rest threshold {REST_VELOCITY_EPS} "
            "m/s and would send the same zero servo pair a stop does. Command at least that speed or call "
            "stop_deepracer."
        )
    return None


def pregranted(topic: str) -> bool:
    """Whether the shared gate will allow ``topic`` without asking anyone."""
    if os.environ.get(BYPASS_CONSENT_ENV, "").lower() == "true":
        return True
    raw = os.environ.get(COMMAND_ALLOW_ENV)
    if raw is None:
        return False
    allowed = frozenset(entry.strip() for entry in raw.split(",") if entry.strip())
    return match_blocklist(topic, allowed)


class DeepRacerRobot(MobileBaseRobot):
    """The stock DeepRacer over rosbridge, as a strands ``MobileBaseRobot``.

    Args:
        transport: The rosbridge transport (or a stand-in in tests).
        calibration: Limits and geometry; defaults to :meth:`Calibration.load`.
        event_log: Where command / motion / stop / approval events go.
        heartbeat: The heartbeat publisher toggled around every command stream.
        node_name: Tool suffix; ``deepracer`` yields the fixed names
            ``drive_deepracer`` and ``stop_deepracer``.
        handshake_retries: Attempts for the manual-mode handshake.
        handshake_timeout_s: Per-call timeout for the handshake services.
    """

    def __init__(
        self,
        transport: RosbridgeTransport,
        *,
        calibration: Calibration | None = None,
        event_log: EventLog | None = None,
        heartbeat: HeartbeatPublisher | None = None,
        node_name: str = "deepracer",
        handshake_retries: int = HANDSHAKE_RETRIES,
        handshake_timeout_s: float = HANDSHAKE_TIMEOUT_S,
    ) -> None:
        cal = calibration or Calibration.load()
        problems = cal.validate()
        if problems:
            raise ValueError("calibration refused: " + "; ".join(problems))
        self.calibration = cal
        self.event_log = event_log
        self.heartbeat = heartbeat
        self.handshake_retries = int(handshake_retries)
        self.handshake_timeout_s = float(handshake_timeout_s)
        self.request_id: str | None = None
        self._stop_cause = "trailing_zero"
        self.last_handshake: dict[str, Any] | None = None
        super().__init__(
            node_name,
            SERVO_TOPIC,
            transport,
            cmd_vel_type=SERVO_TYPE,
            max_linear=cal.max_speed_mps,
            max_duration=cal.max_duration_s,
            publish_rate=cal.publish_rate_hz,
            init_services=[dict(item) for item in MANUAL_HANDSHAKE],
        )

    # -- events ----------------------------------------------------------------

    def _emit(self, type: str, payload: dict[str, Any]) -> None:
        if self.event_log is not None:
            self.event_log.emit(type, payload, source="driver")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # -- kinematics seam ---------------------------------------------------------

    def _cmd_fields(self, linear: float, angular: float, lateral: float = 0.0) -> dict[str, Any]:
        angle, throttle = twist_to_servo(linear, angular, self.calibration)
        return {"angle": angle, "throttle": throttle}

    # -- handshake with retries --------------------------------------------------

    def enable(self, tool_context: ToolContext | None = None) -> dict[str, Any]:
        """Manual mode (state 0) then enable, retried up to ``handshake_retries`` times.

        Right after a stack restart the first service call can time out; each
        attempt re-runs the whole pair so the car is never left in mode 0 but
        disabled by a half-finished handshake.
        """
        if self._enabled:
            return {"status": "success", "content": [{"text": f"{self.node_name}: already enabled"}]}
        transport = self.transport
        assert isinstance(transport, ServiceCapable)
        last: dict[str, Any] = refuse("handshake never ran")
        for attempt in range(1, self.handshake_retries + 1):
            ok = True
            for item in self.init_services:
                kwargs: dict[str, Any] = {
                    "service": item["service"],
                    "type": item["type"],
                    "fields": item.get("fields", {}),
                    "tool_context": tool_context,
                }
                if isinstance(transport, RosbridgeTransport):
                    kwargs["timeout"] = self.handshake_timeout_s
                last = transport.service_call(**kwargs)
                if last.get("status") != "success":
                    ok = False
                    self._emit(
                        "error",
                        {
                            "where": "handshake",
                            "message": f"attempt {attempt}/{self.handshake_retries} {item['service']}: "
                            + result_text(last),
                        },
                    )
                    break
            if ok:
                self._enabled = True
                self.last_handshake = {"attempts": attempt, "mode": MANUAL_MODE, "enabled": True}
                warm = getattr(transport, "warm", None)
                if callable(warm):
                    warm(
                        self.cmd_vel_topic, self.cmd_vel_type
                    )  # the stop's zero pair must not pay the settle
                return {
                    "status": "success",
                    "content": [{"text": f"{self.node_name}: manual mode armed (attempt {attempt})"}],
                }
            text = result_text(last)
            if "declined by the operator" in text or "operator approval" in text:
                break  # a refusal is not a timeout; retrying would nag the operator
        self.last_handshake = {"attempts": self.handshake_retries, "mode": None, "enabled": False}
        return last

    # -- publish seam: events + heartbeat around every command stream ----------

    def _publish_cmd(
        self, linear: float, angular: float, count: int, tool_context: ToolContext | None = None
    ) -> dict[str, Any]:
        fields = self._cmd_fields(linear, angular)
        moving = bool(fields["angle"] or fields["throttle"])
        request_id = self.request_id
        t0 = time.monotonic()
        if moving:
            if pregranted(self.cmd_vel_topic):
                self._emit("approval", {"request_id": request_id, "decision": "approved", "by": "pregrant"})
            self._emit(
                "motion",
                {
                    "request_id": request_id,
                    "state": "start",
                    "angle": fields["angle"],
                    "throttle": fields["throttle"],
                    "duration_s": round(count / self.publish_rate, 3),
                    "messages": count,
                },
            )
            if self.heartbeat is not None:
                self.heartbeat.set_active(True)
        try:
            result = self.transport.publish(
                topic=self.cmd_vel_topic,
                type=self.cmd_vel_type,
                fields=fields,
                count=count,
                rate=self.publish_rate,
                tool_context=tool_context,
            )
        finally:
            if moving and self.heartbeat is not None:
                self.heartbeat.set_active(False)
        success = result.get("status") == "success"
        if moving:
            self._emit(
                "motion",
                {
                    "request_id": request_id,
                    "state": "end",
                    "angle": fields["angle"],
                    "throttle": fields["throttle"],
                    "duration_s": round((time.monotonic() - t0), 3),
                    "messages": count if success else 0,
                },
            )
            if not success:
                self._emit("error", {"where": "drive", "message": result_text(result)})
            else:
                # Spell the outcome out for the model: the gate already ruled (it ran before this
                # tool), the hop happened, the trailing zero follows. Nothing to wait for.
                result = dict(result)
                result["content"] = [
                    {
                        "text": (
                            f"DRIVE DONE: the gate allowed it and the car moved for "
                            f"{round(time.monotonic() - t0, 2)} s (angle {fields['angle']:+.2f}, throttle "
                            f"{fields['throttle']:+.2f}, {count} messages); a zero pair follows and the "
                            "car is stopped. Report this in one sentence; do not wait for anything."
                        )
                    }
                ]
        elif success:
            self._emit(
                "stop",
                {
                    "request_id": request_id,
                    "cause": self._stop_cause,
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                },
            )
        else:
            self._emit("error", {"where": "stop", "message": result_text(result)})
        return result

    # -- drive / stop --------------------------------------------------------

    def drive(
        self,
        linear: float = 0.0,
        angular: float = 0.0,
        duration: float | None = None,
        count: int = 1,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        """One bounded move. ``duration`` defaults to the hop; yaw at rest is refused.

        The order is upstream's and pinned by tests: refuse the request, then the
        handshake, then publish, then the zero pair from ``finally``.
        """
        if duration is None:
            duration = self.calibration.hop_s
        if (
            isinstance(linear, int | float)
            and isinstance(angular, int | float)
            and not isinstance(linear, bool)
        ):
            if math.isfinite(linear) and math.isfinite(angular):
                reason = rest_command_error(linear, angular)
                if reason:
                    self._emit("error", {"where": "drive", "message": reason})
                    return refuse(reason)
        self._stop_cause = "trailing_zero"
        return super().drive(
            linear=linear, angular=angular, duration=duration, count=count, tool_context=tool_context
        )

    def stop(self, tool_context: ToolContext | None = None, *, cause: str = "operator") -> dict[str, Any]:
        """Zero pair now, heartbeat back to idle, ``stop`` event with ``cause``.

        Never gated on the handshake. The heartbeat drops to its idle rate rather
        than stopping, so the on-car deadman stays armed and the screen does not
        show a trip after every operator stop; only ``close()`` ends the
        heartbeat. If the zero pair is lost, the next drive's trailing zero or
        the deadman (on a real link loss) still covers it.
        """
        self._stop_cause = cause
        abort = getattr(self.transport, "abort_stream", None)
        if callable(abort):
            abort()  # a drive still streaming yields immediately; the zero pair below takes the topic
        try:
            return super().stop(tool_context=tool_context)
        finally:
            self._stop_cause = "trailing_zero"
            if self.heartbeat is not None:
                self.heartbeat.set_active(False)

    # -- agent tools (names fixed by CONTRACTS section 6) --------------------

    def _drive_description(self) -> str:
        cal = self.calibration
        return (
            f"Drive the DeepRacer: linear m/s in [-{cal.max_speed_mps}, {cal.max_speed_mps}] "
            f"(negative = reverse), angular rad/s (steering; the car cannot turn in place, minimum turning "
            f"radius about {cal.min_turn_radius_m} m), duration s up to {cal.max_duration_s} "
            f"(default hop {cal.hop_s}). "
            "Every move stops by itself when the duration ends. Refuses linear == 0 with angular != 0."
        )

    @property
    def tools(self) -> list[AgentTool]:
        robot = self

        @tool(name="drive_deepracer", description=self._drive_description(), context=True)
        def drive_deepracer(
            linear: float = 0.0,
            angular: float = 0.0,
            duration: float | None = None,
            tool_context: ToolContext | None = None,
        ) -> dict[str, Any]:
            request_id = robot.request_id or f"r-{uuid.uuid4().hex[:8]}"
            robot.request_id = request_id
            robot._emit(
                "command",
                {
                    "tool": "drive_deepracer",
                    "args": {"linear": linear, "angular": angular, "duration": duration},
                    "request_id": request_id,
                },
            )
            return robot.drive(linear=linear, angular=angular, duration=duration, tool_context=tool_context)

        @tool(
            name="stop_deepracer",
            description="Immediately stop the DeepRacer: zero servo pair, heartbeat off. Always allowed.",
            context=True,
        )
        def stop_deepracer(tool_context: ToolContext | None = None) -> dict[str, Any]:
            robot._emit("command", {"tool": "stop_deepracer", "args": {}, "request_id": robot.request_id})
            return robot.stop(tool_context=tool_context, cause="operator")

        return [drive_deepracer, stop_deepracer]


__all__ = [
    "ENABLE_STATE_SERVICE",
    "HANDSHAKE_RETRIES",
    "HANDSHAKE_TIMEOUT_S",
    "MANUAL_HANDSHAKE",
    "MANUAL_MODE",
    "REST_VELOCITY_EPS",
    "SERVO_TOPIC",
    "VEHICLE_STATE_SERVICE",
    "DeepRacerRobot",
    "pregranted",
    "rest_command_error",
    "twist_to_servo",
]
