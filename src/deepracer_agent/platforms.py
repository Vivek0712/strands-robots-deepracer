"""What a mobile platform has to offer the rover's brain, and a fake one that offers it in memory.

The earlier repo carried twelve platform adapters (rover, drone, boat, lawnmower, hospital cart,
pipeline crawler, robot arm and more) behind one nine-function protocol (report 07 section 2.5).
None was ever run on hardware, and strands-robots already has the real version of that idea: a
registry of drivers behind one ``HardwareDriver`` contract. This project's driver is a DeepRacer
and nothing else by design, so what survives here is the shape of the idea: ``MobilePlatform``
names the five verbs the beats, plans and kiosks need (drive, stop, capture a frame, read the
battery, run preflight); ``DeepRacerPlatform`` shows the real car satisfying it by composing the
Car team's driver, console and preflight; and ``SimPlatform`` is a fake car that keeps its pose
with the same bicycle model, so a plan can be executed end to end in a unit test with no sockets.
``docs/dev/platforms.md`` maps the twelve old adapters onto strands-robots. Physics stops the car;
the decider explains; a platform only moves when a gated command says so.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Protocol, runtime_checkable

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import rest_command_error, twist_to_servo
from deepracer_agent.plans import Step, simulate_path

logger = logging.getLogger(__name__)

#: A syntactically valid 1x1 JPEG skeleton, the frame ``SimPlatform`` serves by default.
TINY_JPEG = (
    b"\xff\xd8"
    + bytes([0xFF, 0xC0, 0x00, 0x11, 0x08, 0x00, 0x01, 0x00, 0x01, 0x03, 1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    + b"\xff\xda\x00\x02\x12\x34\xff\xd9"
)


@runtime_checkable
class DriveStop(Protocol):
    """The two verbs ``execute_plan`` needs; ``DeepRacerRobot`` satisfies this directly."""

    def drive(
        self,
        linear: float = 0.0,
        angular: float = 0.0,
        duration: float | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def stop(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...


@runtime_checkable
class MobilePlatform(DriveStop, Protocol):
    """Drive, stop, capture a frame, read the battery, run preflight: what every beat relies on."""

    name: str

    def capture_frame(self) -> bytes | None: ...

    def battery(self) -> dict[str, Any]: ...

    def preflight(self) -> dict[str, Any]: ...


class DeepRacerPlatform:
    """The real car as a :class:`MobilePlatform`: the driver, the console and preflight, composed.

    Built from an ``AgentRuntime`` with :meth:`from_runtime`; nothing here bypasses the gate, the
    driver's own caps or the zero pair in ``finally``.
    """

    name = "deepracer"

    def __init__(self, driver: Any, console: Any = None, preflight: Any = None) -> None:
        self.driver = driver
        self.console = console
        self._preflight = preflight

    @classmethod
    def from_runtime(cls, runtime: Any) -> DeepRacerPlatform:
        return cls(runtime.driver, getattr(runtime, "console", None), getattr(runtime, "_preflight", None))

    def drive(
        self, linear: float = 0.0, angular: float = 0.0, duration: float | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return self.driver.drive(linear=linear, angular=angular, duration=duration, **kwargs)

    def stop(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.driver.stop(*args, **kwargs)

    def capture_frame(self) -> bytes | None:
        capture = getattr(self.console, "capture_frame", None)
        return capture() if callable(capture) else None

    def battery(self) -> dict[str, Any]:
        from deepracer_agent.tools import battery_level

        return battery_level(self.driver.transport)

    def preflight(self) -> dict[str, Any]:
        if self._preflight is None:
            return {"go": False, "reasons": ["no preflight configured"]}
        return self._preflight.run()


class SimPlatform:
    """A fake car in memory: the driver's caps and refusals, the bicycle model for its pose.

    Every ``drive`` is checked like the real driver would (finite numbers, the speed and duration
    caps, no yaw at rest), then integrated into ``pose`` with :func:`simulate_path`; ``commands``
    remembers each call and ``stops`` each zero pair. ``fail_after`` makes the n-th drive fail so an
    executor's error path can be tested. Nothing sleeps: a hop takes no wall time.
    """

    name = "sim"

    def __init__(
        self,
        calibration: Calibration | None = None,
        *,
        battery: int = 8,
        frame: bytes | None = TINY_JPEG,
        event_log: Any = None,
        fail_after: int | None = None,
    ) -> None:
        self.calibration = calibration or Calibration()
        self.battery_level = int(battery)
        self.frame = frame
        self.event_log = event_log
        self.fail_after = fail_after
        self.pose: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.commands: list[dict[str, Any]] = []
        self.stops: list[str] = []
        self.request_id: str | None = None
        self.enabled = False

    def _emit(self, type: str, payload: dict[str, Any]) -> None:
        if self.event_log is not None:
            try:
                self.event_log.emit(type, payload, source="sim")
            except Exception as exc:
                logger.debug("sim event failed: %s", exc)

    def refusal(self, linear: Any, angular: Any, duration: Any) -> str | None:
        cal = self.calibration
        for name, value in (("linear", linear), ("angular", angular), ("duration", duration)):
            if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
                return f"drive: {name} must be a finite number, got {value!r}"
        if duration <= 0:
            return f"drive: duration {duration} s must be positive"
        if duration > cal.max_duration_s:
            return f"drive: duration {duration} s exceeds max_duration {cal.max_duration_s} s"
        if abs(linear) > cal.max_speed_mps + 1e-9:
            return f"drive: |linear| {abs(linear)} exceeds the cap {cal.max_speed_mps} m/s"
        return rest_command_error(linear, angular)

    def drive(
        self, linear: float = 0.0, angular: float = 0.0, duration: float | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        if duration is None:
            duration = self.calibration.hop_s
        reason = self.refusal(linear, angular, duration)
        if reason:
            return {"status": "error", "content": [{"text": reason}]}
        self.enabled = True
        if self.fail_after is not None and len(self.commands) >= self.fail_after:
            self.commands.append({"linear": linear, "angular": angular, "duration": duration, "failed": True})
            return {"status": "error", "content": [{"text": "drive: simulated link failure"}]}
        angle, throttle = twist_to_servo(linear, angular, self.calibration)
        self.commands.append({"linear": linear, "angular": angular, "duration": duration})
        self._emit(
            "motion",
            {
                "request_id": self.request_id,
                "state": "start",
                "angle": angle,
                "throttle": throttle,
                "duration_s": duration,
                "messages": round(duration * self.calibration.publish_rate_hz),
            },
        )
        x0, y0, h0 = self.pose
        path = simulate_path([Step(linear, angular, duration)], samples_per_step=8)
        dx, dy, dh = path[-1]
        # rotate the body-frame displacement into the world frame
        self.pose = (
            x0 + dx * math.cos(h0) - dy * math.sin(h0),
            y0 + dx * math.sin(h0) + dy * math.cos(h0),
            h0 + dh,
        )
        self._emit(
            "motion",
            {
                "request_id": self.request_id,
                "state": "end",
                "angle": angle,
                "throttle": throttle,
                "duration_s": duration,
                "messages": round(duration * self.calibration.publish_rate_hz),
            },
        )
        return {
            "status": "success",
            "content": [
                {"text": f"DRIVE DONE: sim moved {duration} s (angle {angle:+.2f}, throttle {throttle:+.2f})"}
            ],
        }

    def stop(self, tool_context: Any = None, *, cause: str = "operator") -> dict[str, Any]:
        self.stops.append(cause)
        self._emit("stop", {"request_id": self.request_id, "cause": cause, "latency_ms": 0})
        return {"status": "success", "content": [{"text": "sim: zero pair sent"}]}

    def capture_frame(self) -> bytes | None:
        return self.frame

    def battery(self) -> dict[str, Any]:
        return {"level": self.battery_level, "ok": self.battery_level >= 1}

    def preflight(self) -> dict[str, Any]:
        reasons: list[str] = []
        if self.battery_level < 1:
            reasons.append("battery pack not seen or too low")
        if self.frame is None:
            reasons.append("no camera frame")
        payload = {
            "battery": self.battery_level,
            "camera_fps": 15.0 if self.frame is not None else None,
            "link_rtt_ms": 0.0,
            "mode": 0,
            "enabled": self.enabled,
            "deadman": "armed",
            "decider_latency_ms": None,
            "calibration": "ok",
            "pwm_outputs": "unknown",
            "go": not reasons,
            "reasons": reasons,
            "ts": time.time(),
        }
        self._emit("preflight", {k: v for k, v in payload.items() if k != "ts"})
        return payload

    @property
    def heading_deg(self) -> float:
        return math.degrees(self.pose[2])

    @property
    def distance_from_start_m(self) -> float:
        return math.hypot(self.pose[0], self.pose[1])


__all__ = ["TINY_JPEG", "DeepRacerPlatform", "DriveStop", "MobilePlatform", "SimPlatform"]
