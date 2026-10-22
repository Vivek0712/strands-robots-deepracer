"""The shape library: circle, square, figure-8 and friends as plans of small gated hops.

Ask the rover for a square of sixty centimetres and this module turns it into hops: straight
runs at the hop speed and rounded corners at the gentlest radius the front wheels allow,
because an Ackermann car cannot pivot. Every shape is parameterised by one size in metres
(the diameter of a circle, the side of a polygon, the length of a straight, an oval or a
slalom), built from the calibration's bicycle model, and handed to the plan validator; a
shape that does not fit the pen or the car comes back as a refusal with the reason, never as a
smaller shape the rover chose for itself. Physics stops the car; the decider explains; this
module only proposes.

Where the numbers come from. Measured on this car (report 07, HTTP path, full lock): minimum
turning radius 0.28 m. From the bicycle model in ``calibration.py``: wheelbase 0.164 m (URDF,
report 02) and a 30 degree lock (stock action space) give 0.284 m, within 2 percent of the
measurement, so the model is used and the measurement is its check. Assumed, not measured:
the turn speed (0.25 m/s, report 07 also turned slower than it drove straight), the 5 percent
margin off full lock so the steering servo never saturates, and that ``linear = 0.3 m/s`` is
what servo throttle 0.3 produces on the ROS path (the proven hop value; the real speed waits
for a wheels-on measurement). Not reused: report 07's "90 degrees in 1.5 s" rotation
calibration, measured through the HTTP console's quantised throttle and steering; the ROS path
must be re-measured and the bicycle model is what we trust until then.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from deepracer_agent.calibration import Calibration
from deepracer_agent.gate import Envelope
from deepracer_agent.plans import Pen, Plan, Proposal, Step, ValidationResult, validate_plan

#: Assumed: arcs are driven slower than straights (report 07 did the same: 0.25 vs 0.40 m/s).
TURN_SPEED_MPS = 0.25
#: Assumed: planned arcs stay 5 percent off full lock so the servo never saturates mid-arc.
TURN_RADIUS_FACTOR = 1.05
#: Assumed: lead-in and lead-out of a U-turn.
U_TURN_LEAD_M = 0.2
#: Assumed: each slalom gate is an S of two 45 degree arcs.
SLALOM_GATE_RAD = math.radians(45.0)
#: Default size when a request names a shape but no size.
DEFAULT_SIZE_M: dict[str, float] = {
    "straight": 0.6,
    "back": 0.4,
    "circle": 0.6,
    "oval": 1.0,
    "u_turn": 0.6,
    "figure_8": 0.6,
    "square": 0.6,
    "triangle": 0.4,
    "pentagon": 0.3,
    "hexagon": 0.25,
    "slalom": 1.0,
}


class ShapeError(ValueError):
    """The shape cannot be drawn at this size by this car (a geometry refusal, code ``geometry``)."""


@dataclass(frozen=True)
class Geometry:
    """The per-car numbers every generator uses, derived once from a :class:`Calibration`."""

    cruise_mps: float
    turn_mps: float
    turn_radius_m: float
    min_radius_m: float
    max_step_s: float

    @classmethod
    def from_calibration(
        cls,
        cal: Calibration,
        *,
        cruise_mps: float | None = None,
        turn_mps: float | None = None,
        max_step_s: float | None = None,
    ) -> Geometry:
        min_radius = cal.bicycle_min_turn_radius_m
        return cls(
            cruise_mps=min(cal.max_speed_mps, cruise_mps or cal.max_speed_mps),
            turn_mps=min(cal.max_speed_mps, turn_mps or TURN_SPEED_MPS),
            turn_radius_m=min_radius * TURN_RADIUS_FACTOR,
            min_radius_m=min_radius,
            max_step_s=min(cal.max_duration_s, max_step_s or cal.max_duration_s),
        )


# -- primitives --------------------------------------------------------------------------------------


def _split(linear: float, angular: float, total_s: float, label: str, max_step_s: float) -> list[Step]:
    """Cut one movement into equal hops no longer than ``max_step_s``."""
    if total_s <= 0:
        return []
    n = max(1, math.ceil(total_s / max_step_s - 1e-9))
    d = round(total_s / n, 3)
    if n == 1:
        return [Step(round(linear, 4), round(angular, 4), d, label)]
    return [Step(round(linear, 4), round(angular, 4), d, f"{label} {k + 1}/{n}") for k in range(n)]


def straight(g: Geometry, length_m: float, label: str = "forward", *, reverse: bool = False) -> list[Step]:
    if length_m <= 0:
        raise ShapeError(f"a straight needs a positive length, got {length_m:g} m")
    v = -g.cruise_mps if reverse else g.cruise_mps
    return _split(v, 0.0, length_m / g.cruise_mps, label, g.max_step_s)


def arc(g: Geometry, radius_m: float, angle_rad: float, label: str, *, left: bool = True) -> list[Step]:
    """A constant-radius arc through ``angle_rad`` at the turn speed."""
    if radius_m < g.min_radius_m * (1 - 1e-9):
        raise ShapeError(
            f"an arc of radius {radius_m:.2f} m is tighter than the wheels can steer ({g.min_radius_m:.2f} m)"
        )
    w = g.turn_mps / radius_m
    total = abs(angle_rad) * radius_m / g.turn_mps
    return _split(g.turn_mps, w if left else -w, total, label, g.max_step_s)


def _check_radius(g: Geometry, radius_m: float, what: str, size_m: float) -> None:
    if radius_m < g.turn_radius_m - 1e-9:
        raise ShapeError(
            f"a {size_m:g} m {what} needs a {radius_m:.2f} m radius; this car's gentlest planned turn is "
            f"{g.turn_radius_m:.2f} m (full lock {g.min_radius_m:.2f} m), so the smallest {what} is "
            f"{2 * g.turn_radius_m:.2f} m across"
        )


def _sign(left: bool) -> float:
    return 1.0 if left else -1.0


# -- shapes ------------------------------------------------------------------------------------------


def shape_straight(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    steps = straight(g, size_m, "forward")
    return Plan("straight", size_m, tuple(steps), 0.0, 0.0, f"a straight run of {size_m:g} m")


def shape_back(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    steps = straight(g, size_m, "back", reverse=True)
    return Plan("back", size_m, tuple(steps), 0.0, 0.0, f"backing up {size_m:g} m")


def shape_circle(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    radius = size_m / 2
    _check_radius(g, radius, "circle", size_m)
    steps: list[Step] = []
    for q in range(4):
        steps += arc(g, radius, math.pi / 2, f"quarter {q + 1}", left=left)
    side = "left" if left else "right"
    return Plan(
        "circle",
        size_m,
        tuple(steps),
        2 * math.pi,
        _sign(left) * 2 * math.pi,
        f"a {size_m:g} m circle to the {side} (radius {radius:.2f} m)",
    )


def shape_oval(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    radius = g.turn_radius_m
    run = size_m - 2 * radius
    if run < 0.1:
        raise ShapeError(
            f"an oval of {size_m:g} m is a circle at this car's turn radius; ask for a circle or an oval of "
            f"at least {2 * radius + 0.1:.2f} m"
        )
    steps: list[Step] = []
    for half in (1, 2):
        steps += straight(g, run, f"side {half}")
        steps += arc(g, radius, math.pi / 2, f"end {half}a", left=left)
        steps += arc(g, radius, math.pi / 2, f"end {half}b", left=left)
    return Plan(
        "oval",
        size_m,
        tuple(steps),
        2 * math.pi,
        _sign(left) * 2 * math.pi,
        f"a {size_m:g} m by {2 * radius:.2f} m oval",
    )


def shape_u_turn(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    radius = size_m / 2
    _check_radius(g, radius, "U-turn", size_m)
    steps = straight(g, U_TURN_LEAD_M, "lead in")
    steps += arc(g, radius, math.pi / 2, "turn a", left=left)
    steps += arc(g, radius, math.pi / 2, "turn b", left=left)
    steps += straight(g, U_TURN_LEAD_M, "lead out")
    side = "left" if left else "right"
    return Plan(
        "u_turn",
        size_m,
        tuple(steps),
        math.pi,
        _sign(left) * math.pi,
        f"a U-turn to the {side}, {size_m:g} m across",
    )


def shape_figure_8(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    radius = size_m / 2
    _check_radius(g, radius, "figure-8 lobe", size_m)
    steps: list[Step] = []
    for q in range(4):
        steps += arc(g, radius, math.pi / 2, f"first loop {q + 1}", left=left)
    for q in range(4):
        steps += arc(g, radius, math.pi / 2, f"second loop {q + 1}", left=not left)
    return Plan(
        "figure_8",
        size_m,
        tuple(steps),
        4 * math.pi,
        0.0,
        f"a figure-8 with {size_m:g} m lobes (one loop each way)",
    )


def _polygon(name: str, sides: int) -> Callable[..., Plan]:
    def build(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
        if size_m <= 0:
            raise ShapeError(f"a {name} needs a positive side, got {size_m:g} m")
        turn = 2 * math.pi / sides
        steps: list[Step] = []
        for i in range(sides):
            steps += straight(g, size_m, f"side {i + 1}")
            steps += arc(g, g.turn_radius_m, turn, f"corner {i + 1}", left=left)
        return Plan(
            name,
            size_m,
            tuple(steps),
            2 * math.pi,
            _sign(left) * 2 * math.pi,
            f"a {name} with {size_m:g} m sides and rounded corners (radius {g.turn_radius_m:.2f} m)",
        )

    return build


def shape_slalom(g: Geometry, size_m: float, *, left: bool = True) -> Plan:
    radius = g.turn_radius_m
    gate_len = 2 * radius * math.sin(SLALOM_GATE_RAD)
    gates = round(size_m / gate_len)
    if gates < 1:
        raise ShapeError(f"a slalom needs at least {gate_len:.2f} m of course (one gate), got {size_m:g} m")
    steps: list[Step] = []
    first_left = left
    for gate in range(gates):
        steps += arc(g, radius, SLALOM_GATE_RAD, f"gate {gate + 1} in", left=first_left)
        steps += arc(g, radius, SLALOM_GATE_RAD, f"gate {gate + 1} out", left=not first_left)
        first_left = not first_left
    return Plan(
        "slalom",
        size_m,
        tuple(steps),
        gates * 2 * SLALOM_GATE_RAD,
        0.0,
        f"a slalom of {gates} gate{'s' if gates != 1 else ''} over about {gates * gate_len:.2f} m",
    )


SHAPES: dict[str, Callable[..., Plan]] = {
    "straight": shape_straight,
    "back": shape_back,
    "circle": shape_circle,
    "oval": shape_oval,
    "u_turn": shape_u_turn,
    "figure_8": shape_figure_8,
    "square": _polygon("square", 4),
    "triangle": _polygon("triangle", 3),
    "pentagon": _polygon("pentagon", 5),
    "hexagon": _polygon("hexagon", 6),
    "slalom": shape_slalom,
}
SHAPE_NAMES: tuple[str, ...] = tuple(SHAPES)

ALIASES: dict[str, str] = {
    "figure-8": "figure_8",
    "figure8": "figure_8",
    "figure eight": "figure_8",
    "figure 8": "figure_8",
    "eight": "figure_8",
    "u-turn": "u_turn",
    "uturn": "u_turn",
    "u turn": "u_turn",
    "turn around": "u_turn",
    "forward": "straight",
    "line": "straight",
    "reverse": "back",
    "backward": "back",
    "backwards": "back",
    "loop": "circle",
    "lap": "circle",
}


def canonical_shape(name: str) -> str | None:
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    if key in SHAPES:
        return key
    alias = ALIASES.get(str(name).strip().lower())
    if alias:
        return alias
    return ALIASES.get(key.replace("_", " "))


# -- the entry point ---------------------------------------------------------------------------------


def propose(
    shape: str,
    size_m: float,
    *,
    calibration: Calibration | None = None,
    pen: Pen | None = None,
    envelope: Envelope | None = None,
    left: bool = True,
    cruise_mps: float | None = None,
    turn_mps: float | None = None,
    max_step_s: float | None = None,
) -> Proposal:
    """Build the named shape at ``size_m`` and validate it; never raises for a bad request."""
    name = canonical_shape(shape)
    if name is None:
        return Proposal(
            str(shape),
            float(size_m),
            None,
            ValidationResult.refused("geometry", f"unknown shape {shape!r}; I know {', '.join(SHAPE_NAMES)}"),
        )
    cal = calibration or Calibration()
    size = float(size_m)
    if not math.isfinite(size) or size <= 0:
        reason = f"size must be a positive number of metres, got {size_m!r}"
        return Proposal(name, size, None, ValidationResult.refused("geometry", reason))
    g = Geometry.from_calibration(cal, cruise_mps=cruise_mps, turn_mps=turn_mps, max_step_s=max_step_s)
    try:
        plan = SHAPES[name](g, size, left=left)
    except ShapeError as exc:
        return Proposal(name, size, None, ValidationResult.refused("geometry", str(exc)))
    return Proposal(name, size, plan, validate_plan(plan, cal, pen, envelope))


# -- typed requests ----------------------------------------------------------------------------------

_NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "half": 0.5,
    "quarter": 0.25,
}
_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(cm|centimet(?:re|er)s?|mm|millimet(?:re|er)s?|m\b|met(?:re|er)s?)", re.IGNORECASE
)
_WORD_RE = re.compile(
    r"\b(one and a half|half a|a half|half|quarter|a|an|one|two|three)\s*"
    r"(cm|centimet(?:re|er)s?|m\b|met(?:re|er)s?)",
    re.IGNORECASE,
)
_SHAPE_WORDS: tuple[tuple[str, str], ...] = (
    ("figure 8", "figure_8"),
    ("figure-8", "figure_8"),
    ("figure eight", "figure_8"),
    ("figure_8", "figure_8"),
    ("u-turn", "u_turn"),
    ("u turn", "u_turn"),
    ("uturn", "u_turn"),
    ("u_turn", "u_turn"),
    ("turn around", "u_turn"),
    ("square", "square"),
    ("triangle", "triangle"),
    ("pentagon", "pentagon"),
    ("hexagon", "hexagon"),
    ("oval", "oval"),
    ("slalom", "slalom"),
    ("circle", "circle"),
    ("loop", "circle"),
    ("straight", "straight"),
    ("back up", "back"),
    ("reverse", "back"),
    ("backward", "back"),
)


def parse_size(text: str) -> float | None:
    """The first size in metres named in ``text`` (``60 cm``, ``0.6 m``, ``half a metre``, ``1.5 metres``)."""
    low = text.lower()
    m = _UNIT_RE.search(low)
    if m:
        value = float(m.group(1))
        unit = m.group(2)
        if unit.startswith("c"):
            return value / 100
        if unit.startswith("mm") or unit.startswith("milli"):
            return value / 1000
        return value
    w = _WORD_RE.search(low)
    if w:
        phrase, unit = w.group(1), w.group(2)
        value = 1.5 if phrase == "one and a half" else _NUMBER_WORDS.get(phrase.split()[0], None)
        if phrase in ("half a", "a half"):
            value = 0.5
        if value is None:
            return None
        return value / 100 if unit.startswith("c") else value
    return None


def parse_shape_request(text: str) -> tuple[str, float] | None:
    """``(shape, size_m)`` for a typed request, or ``None`` when no shape is named."""
    low = text.lower()
    for word, shape in _SHAPE_WORDS:
        if word in low:
            size = parse_size(low)
            return shape, (size if size is not None else DEFAULT_SIZE_M[shape])
    return None


__all__ = [
    "ALIASES",
    "DEFAULT_SIZE_M",
    "SHAPES",
    "SHAPE_NAMES",
    "SLALOM_GATE_RAD",
    "TURN_RADIUS_FACTOR",
    "TURN_SPEED_MPS",
    "U_TURN_LEAD_M",
    "Geometry",
    "ShapeError",
    "arc",
    "canonical_shape",
    "parse_shape_request",
    "parse_size",
    "propose",
    "straight",
]
