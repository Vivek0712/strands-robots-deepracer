"""shapes: every shape validates at a sane size and is refused at a pen-breaking one; closed loops close."""

from __future__ import annotations

import math

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.plans import Pen, validate_plan
from deepracer_agent.shapes import (
    DEFAULT_SIZE_M,
    SHAPE_NAMES,
    TURN_RADIUS_FACTOR,
    TURN_SPEED_MPS,
    Geometry,
    canonical_shape,
    parse_shape_request,
    parse_size,
    propose,
)

CAL = Calibration()
G = Geometry.from_calibration(CAL)

#: shape -> (sane size, pen-breaking size)
SIZES: dict[str, tuple[float, float]] = {
    "straight": (0.6, 1.5),
    "back": (0.4, 1.5),
    "circle": (0.6, 1.5),
    "oval": (1.0, 1.5),
    "u_turn": (0.6, 1.5),
    "figure_8": (0.6, 0.8),
    "square": (0.6, 1.0),
    "triangle": (0.4, 1.0),
    "pentagon": (0.3, 0.6),
    "hexagon": (0.25, 0.6),
    "slalom": (1.0, 2.0),
}


def test_the_table_covers_every_shape() -> None:
    assert set(SIZES) == set(SHAPE_NAMES) == set(DEFAULT_SIZE_M)


@pytest.mark.parametrize("shape", SHAPE_NAMES)
def test_every_shape_validates_at_a_sane_size(shape: str) -> None:
    proposal = propose(shape, SIZES[shape][0])
    assert proposal.ok, proposal.validation.reasons
    plan = proposal.plan
    assert plan is not None and plan.shape == shape
    for step in plan.steps:
        assert abs(step.linear) <= CAL.max_speed_mps and 0 < step.duration <= CAL.max_duration_s
        assert not (abs(step.linear) < 1e-3 and step.angular)  # never yaw at rest
        radius = step.radius_m
        assert radius is None or radius >= CAL.bicycle_min_turn_radius_m * TURN_RADIUS_FACTOR - 1e-6
    assert "Plan:" in proposal.narration() and "gated hops" in proposal.narration()


@pytest.mark.parametrize("shape", SHAPE_NAMES)
def test_every_shape_is_refused_at_a_pen_breaking_size(shape: str) -> None:
    proposal = propose(shape, SIZES[shape][1])
    assert not proposal.ok
    assert "footprint" in proposal.validation.codes, proposal.validation.codes
    assert "does not fit the usable pen" in " ".join(proposal.validation.reasons)
    assert proposal.narration().startswith("I will not drive")


@pytest.mark.parametrize("shape", SHAPE_NAMES)
def test_default_sizes_validate(shape: str) -> None:
    assert propose(shape, DEFAULT_SIZE_M[shape]).ok


@pytest.mark.parametrize(
    ("shape", "expected_turn_deg", "expected_net_deg"),
    [
        ("circle", 360, 360),
        ("oval", 360, 360),
        ("square", 360, 360),
        ("triangle", 360, 360),
        ("pentagon", 360, 360),
        ("hexagon", 360, 360),
        ("u_turn", 180, 180),
        ("figure_8", 720, 0),
        ("slalom", 180, 0),
        ("straight", 0, 0),
        ("back", 0, 0),
    ],
)
def test_closed_loop_rotation_check(shape: str, expected_turn_deg: float, expected_net_deg: float) -> None:
    plan = propose(shape, SIZES[shape][0]).plan
    assert plan is not None
    assert math.degrees(plan.turn_rad) == pytest.approx(expected_turn_deg, abs=1.0)
    assert math.degrees(plan.net_heading_rad) == pytest.approx(expected_net_deg, abs=1.0)
    assert plan.expected_turn_rad == pytest.approx(math.radians(expected_turn_deg), abs=1e-6)


def test_a_broken_closed_loop_is_refused_by_the_validator() -> None:
    plan = propose("square", 0.6).plan
    assert plan is not None
    three_corners = plan.steps[:-1]  # drop the last corner: 270 degrees
    from dataclasses import replace

    broken = replace(plan, steps=three_corners)
    result = validate_plan(broken, CAL, Pen())
    assert {"rotation_mismatch", "net_heading_mismatch"} <= set(result.codes)


def test_right_turns_mirror_left() -> None:
    left = propose("circle", 0.6, left=True).plan
    right = propose("circle", 0.6, left=False).plan
    assert left is not None and right is not None
    assert all(s.angular > 0 for s in left.steps) and all(s.angular < 0 for s in right.steps)
    assert right.expected_net_heading_rad == pytest.approx(-2 * math.pi)


def test_geometry_is_derived_from_calibration_not_hardcoded() -> None:
    assert G.min_radius_m == pytest.approx(0.284, abs=0.001)  # agrees with report 07's measured 0.28 m
    assert G.turn_radius_m == pytest.approx(G.min_radius_m * TURN_RADIUS_FACTOR)
    assert G.cruise_mps == CAL.max_speed_mps and G.turn_mps == TURN_SPEED_MPS
    wide = Calibration(max_steering_rad=0.3)
    assert Geometry.from_calibration(wide).min_radius_m > G.min_radius_m
    assert not propose("circle", 0.6, calibration=wide).ok  # a car that steers less cannot draw it


def test_too_tight_shapes_are_geometry_refusals() -> None:
    for shape in ("circle", "u_turn", "figure_8"):
        p = propose(shape, 0.4)
        assert p.validation.codes == ("geometry",) and "smallest" in p.validation.reasons[0]
    oval = propose("oval", 0.6)
    assert oval.validation.codes == ("geometry",) and "circle" in oval.validation.reasons[0]
    slalom = propose("slalom", 0.1)
    assert slalom.validation.codes == ("geometry",)


def test_steps_are_split_under_the_hop_cap() -> None:
    plan = propose("circle", 1.2).plan  # quarter arcs of 3.77 s each must split
    assert plan is not None
    assert all(s.duration <= CAL.max_duration_s for s in plan.steps) and len(plan.steps) == 8
    assert plan.steps[0].label.endswith("1/2")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("square", "square"),
        ("Figure-8", "figure_8"),
        ("figure 8", "figure_8"),
        ("U-turn", "u_turn"),
        ("u turn", "u_turn"),
        ("forward", "straight"),
        ("reverse", "back"),
        ("loop", "circle"),
        ("nonagon", None),
    ],
)
def test_canonical_shape(name: str, expected: str | None) -> None:
    assert canonical_shape(name) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("drive a square with 60 cm sides", ("square", 0.6)),
        ("a circle one and a half metres across", ("circle", 1.5)),
        ("figure 8 half a metre", ("figure_8", 0.5)),
        ("do a u-turn", ("u_turn", 0.6)),
        ("slalom 1.2 m", ("slalom", 1.2)),
        ("go straight 80 centimetres", ("straight", 0.8)),
        ("back up 40cm", ("back", 0.4)),
        ("hexagon", ("hexagon", 0.25)),
        ("what is your battery", None),
    ],
)
def test_parse_shape_request(text: str, expected: tuple[str, float] | None) -> None:
    assert parse_shape_request(text) == expected


@pytest.mark.parametrize(
    ("text", "size"),
    [
        ("60 cm", 0.6),
        ("0.6 m", 0.6),
        ("1.5 metres", 1.5),
        ("half a metre", 0.5),
        ("two metres", 2.0),
        ("600 mm", 0.6),
        ("big", None),
    ],
)
def test_parse_size(text: str, size: float | None) -> None:
    assert parse_size(text) == size
