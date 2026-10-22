"""The numbers the driver trusts about this particular car, in one place, read-only.

Wheelbase, the speed we call full throttle, the steering lock, the hop length and
the longest single move all live in one dataclass so a presenter can point at it
and say "these are the limits". They come from the research bundle (report 02 for
geometry, report 07 for the measured constants, CONTRACTS section 0 for the PWM
readings) and can be overridden from a JSON file for a different car. Nothing in
this module ever writes calibration to the car: the on-car calibration file is
read by preflight and never touched without the user's explicit approval.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Forward sign on the ROS servo path. Report 07 measured HTTP ``throttle < 0`` as
#: forward; the webserver negates both fields on the way to ROS, so the ROS path
#: is ``+1`` until a wheels-on test says otherwise (CONTRACTS section 0).
THROTTLE_FORWARD_SIGN = 1

CALIBRATION_FILE_ENV = "DEEPRACER_CALIBRATION_FILE"
DEFAULT_CALIBRATION_FILE = Path(os.path.expanduser("~/.config/deepracer/calibration.json"))


@dataclass(frozen=True)
class Calibration:
    """Measured and chosen constants for the stock DeepRacer on the ROS path.

    Attributes:
        throttle_forward_sign: ``+1`` or ``-1``; multiplies the throttle so that
            a positive ``linear`` drives forward.
        wheelbase_m: Front-to-rear axle distance (URDF, report 02: 0.164 m).
        max_speed_mps: Linear speed mapped to full throttle AND the clamp on
            ``linear``. 0.3 m/s is the showcase cap (CONTRACTS section 6).
        max_steering_rad: Steering angle mapped to full servo deflection
            (30 degrees, the stock action space).
        throttle_at_max_speed: Servo throttle sent for ``linear == max_speed_mps``.
            On the ROS path servo throttle 1.0 is the ESC's minimum PWM (several
            m/s); the hop proven on this car used 0.3, so the envelope cap maps
            to 0.3 and nothing the agent can say reaches more than that.
        hop_s: Default drive duration when the agent names none.
        max_duration_s: Longest single drive; longer requests are refused.
        publish_rate_hz: Servo command stream rate.
        neutral_throttle_pwm_ns: Throttle PWM observed at rest (CONTRACTS 0).
        throttle_0_3_pwm_ns: Throttle PWM observed for ``throttle=0.3``.
        min_turn_radius_m: Report 07 measured full-lock radius, for the tool
            description; the bicycle model uses ``wheelbase_m / tan(max_steering_rad)``.
    """

    throttle_forward_sign: int = THROTTLE_FORWARD_SIGN
    wheelbase_m: float = 0.164
    max_speed_mps: float = 0.3
    max_steering_rad: float = 0.5236
    throttle_at_max_speed: float = 0.3
    hop_s: float = 0.5
    max_duration_s: float = 2.0
    publish_rate_hz: float = 20.0
    neutral_throttle_pwm_ns: int = 1446000
    throttle_0_3_pwm_ns: int = 1405500
    min_turn_radius_m: float = 0.28

    def validate(self) -> list[str]:
        """Every reason this calibration cannot be used, empty when it can."""
        problems: list[str] = []
        if self.throttle_forward_sign not in (1, -1):
            problems.append(f"throttle_forward_sign must be +1 or -1, got {self.throttle_forward_sign!r}")
        for name in (
            "wheelbase_m",
            "max_speed_mps",
            "max_steering_rad",
            "throttle_at_max_speed",
            "hop_s",
            "max_duration_s",
            "publish_rate_hz",
            "min_turn_radius_m",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or value <= 0
            ):
                problems.append(f"{name} must be a positive finite number, got {value!r}")
        if not problems:
            if self.hop_s > self.max_duration_s:
                problems.append(f"hop_s {self.hop_s} exceeds max_duration_s {self.max_duration_s}")
            if self.max_steering_rad >= math.pi / 2:
                problems.append(f"max_steering_rad {self.max_steering_rad} must be below pi/2")
            if self.throttle_at_max_speed > 1.0:
                problems.append(
                    f"throttle_at_max_speed {self.throttle_at_max_speed} must be <= 1.0 (servo units)"
                )
        for name in ("neutral_throttle_pwm_ns", "throttle_0_3_pwm_ns"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 20_000_000:
                problems.append(f"{name} must be a PWM duty in nanoseconds (0..20000000), got {value!r}")
        return problems

    @property
    def bicycle_min_turn_radius_m(self) -> float:
        return self.wheelbase_m / math.tan(self.max_steering_rad)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Calibration:
        """Defaults, overlaid with a JSON file when one is given or ``$DEEPRACER_CALIBRATION_FILE`` is set.

        With the variable unset, ``~/.config/deepracer/calibration.json`` is used when it exists;
        set but empty means defaults only, which is how the test suite stays clear of the
        operator's saved throttle.

        Raises:
            ValueError: on an unknown key, a malformed file or a value outside
                the domain :meth:`validate` describes. A bad calibration is
                refused loudly rather than clamped.
        """
        env = os.environ.get(CALIBRATION_FILE_ENV)
        if path is not None:
            source: str | Path | None = path
        elif env is not None:
            source = env or None  # set but empty: defaults only, ignore the home file (tests)
        elif DEFAULT_CALIBRATION_FILE.is_file():
            source = DEFAULT_CALIBRATION_FILE  # the portal's Throttle setting persists here
        else:
            source = None
        if source is None:
            return cls()
        file = Path(source)
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"calibration file {file} is unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"calibration file {file} must hold a JSON object")
        known = {f.name for f in dataclasses.fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"calibration file {file} has unknown keys {unknown}; known: {sorted(known)}")
        cal = cls(**data)
        problems = cal.validate()
        if problems:
            raise ValueError(f"calibration file {file} refused: " + "; ".join(problems))
        return cal


__all__ = ["CALIBRATION_FILE_ENV", "THROTTLE_FORWARD_SIGN", "Calibration"]
