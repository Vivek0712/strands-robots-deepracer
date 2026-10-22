"""plans: the refusal table over every validator rule, the footprint geometry, execute_plan, the tool."""

from __future__ import annotations

import math
from typing import Any

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.gate import Decision, Envelope, LocalEventLog
from deepracer_agent.plans import (
    REFUSAL_CODES,
    Advice,
    Pen,
    Plan,
    Proposal,
    Step,
    ValidationResult,
    configure_plans,
    execute_plan,
    footprint,
    last_proposal,
    plan_deepracer,
    propose,
    reset_plans,
    simulate_path,
    validate_plan,
)
from deepracer_agent.platforms import SimPlatform

CAL = Calibration()
PEN = Pen()
HOP = Step(0.3, 0.0, 0.5, "hop")


def plan_of(*steps: Step, shape: str = "custom", **kw: Any) -> Plan:
    return Plan(shape, 0.5, tuple(steps), **kw)


# -- refusal table -------------------------------------------------------------------------------------

REFUSALS: list[tuple[str, Plan, str]] = [
    ("empty", plan_of(), "empty"),
    ("too_many_steps", plan_of(*([HOP] * 25)), "too_many_steps"),
    ("not_a_number", plan_of(Step(float("nan"), 0.0, 0.5)), "not_a_number"),
    ("not_a_number_str", plan_of(Step("fast", 0.0, 0.5)), "not_a_number"),  # type: ignore[arg-type]
    ("linear_cap", plan_of(Step(0.31, 0.0, 0.5)), "linear_cap"),
    ("duration_cap", plan_of(Step(0.3, 0.0, 2.01)), "duration_cap"),
    ("duration_nonpositive", plan_of(Step(0.3, 0.0, 0.0)), "duration_nonpositive"),
    ("yaw_at_rest", plan_of(Step(0.0, 0.5, 0.5)), "yaw_at_rest"),
    ("zero_step", plan_of(Step(0.0, 0.0, 0.5)), "zero_step"),
    ("below_min_turn_radius", plan_of(Step(0.2, 1.0, 0.5)), "below_min_turn_radius"),  # radius 0.2 m
    ("envelope_direction", plan_of(Step(-0.3, 0.0, 0.5)), "envelope"),  # forward-only envelope below
    (
        "rotation_mismatch",
        plan_of(*([Step(0.25, 0.8, 1.0)] * 4), expected_turn_rad=2 * math.pi),
        "rotation_mismatch",
    ),
    (
        "net_heading_mismatch",
        plan_of(Step(0.25, 0.8, 1.0), Step(0.25, -0.8, 1.0), expected_net_heading_rad=1.6),
        "net_heading_mismatch",
    ),
    ("total_time", plan_of(*([Step(0.1, 0.0, 2.0)] * 16)), "total_time"),  # 32 s, 3.2 m, fits the pen
    ("total_distance", plan_of(*([Step(0.3, 0.9, 2.0)] * 12)), "total_distance"),  # circles: 7.2 m
    ("footprint", plan_of(*([Step(0.3, 0.0, 2.0)] * 3)), "footprint"),  # 1.8 m straight
    ("no_terminal_stop", plan_of(HOP, terminal_stop=False), "no_terminal_stop"),
]


@pytest.mark.parametrize(("label", "plan", "code"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_refusal_table(label: str, plan: Plan, code: str) -> None:
    envelope = Envelope(allowed_directions=("forward",)) if label == "envelope_direction" else None
    result = validate_plan(plan, CAL, PEN, envelope)
    assert not result.ok
    assert code in result.codes, (result.codes, result.reasons)
    assert all(reason for reason in result.reasons)
    assert code in REFUSAL_CODES


def test_every_refusal_code_is_exercised_or_geometry() -> None:
    covered = {code for _, _, code in REFUSALS} | {"geometry"}
    assert covered == set(REFUSAL_CODES)


def test_geometry_code_comes_from_the_shape_library() -> None:
    assert propose("circle", 0.4).validation.codes == ("geometry",)
    assert propose("nonagon", 0.4).validation.codes == ("geometry",)
    assert propose("square", -1).validation.codes == ("geometry",)


def test_a_good_plan_passes_with_metrics() -> None:
    result = validate_plan(plan_of(HOP, Step(0.25, 0.8, 1.0)), CAL, PEN)
    assert result.ok and result.codes == () and result.reasons == ()
    assert result.metrics["steps"] == 2
    assert result.metrics["total_time_s"] == 1.5
    assert result.metrics["total_distance_m"] == pytest.approx(0.4, abs=0.01)
    assert result.summary().startswith("ok: 2 steps")


def test_all_reasons_are_collected_not_just_the_first() -> None:
    result = validate_plan(plan_of(Step(0.5, 0.0, 3.0), Step(0.0, 1.0, 0.5)), CAL, PEN)
    assert {"linear_cap", "duration_cap", "yaw_at_rest", "envelope"} <= set(result.codes)


# -- geometry -------------------------------------------------------------------------------------------


def test_simulate_path_closes_a_circle_and_a_straight_is_a_line() -> None:
    circle = [Step(0.25, 0.25 / 0.3, (math.pi / 2) * 0.3 / 0.25)] * 4
    x, y, heading = simulate_path(circle)[-1]
    assert abs(x) < 0.02 and abs(y) < 0.02 and heading == pytest.approx(2 * math.pi, abs=0.01)
    assert footprint(circle) == (pytest.approx(0.6, abs=0.02), pytest.approx(0.6, abs=0.02))
    assert footprint([Step(0.3, 0.0, 2.0)]) == (pytest.approx(0.6), pytest.approx(0.0))


def test_reverse_arcs_steer_the_mirrored_way_like_the_driver() -> None:
    fwd = simulate_path([Step(0.25, 0.5, 1.0)])[-1]
    back = simulate_path([Step(-0.25, 0.5, 1.0)])[-1]
    assert fwd[2] == pytest.approx(back[2])  # same heading change
    assert fwd[0] > 0 > back[0]  # opposite travel


def test_pen_usable_and_dict() -> None:
    assert PEN.usable_m == (1.4, 1.4)
    assert Pen(width_m=3, depth_m=2, margin_m=0.5).usable_m == (2.0, 1.0)
    assert PEN.to_dict()["max_steps"] == 24


def test_step_and_plan_describe() -> None:
    assert Step(0.3, 0.0, 0.5).describe().startswith("forward 0.15 m")
    assert "arc left 90 deg" in Step(0.25, 0.8333, 1.885).describe()
    assert "arc right" in Step(0.25, -0.8, 1.0).describe()
    plan = propose("square", 0.6).plan
    assert plan is not None and plan.to_dict()["expected_turn_deg"] == 360.0
    assert plan.turn_rad == pytest.approx(2 * math.pi, abs=0.01)


# -- execute_plan: one gated hop per step --------------------------------------------------------------


class ScriptGate:
    """Answers a scripted action per call (the last one repeats)."""

    def __init__(self, *actions: str):
        self.actions = list(actions)
        self.calls: list[tuple[dict[str, Any], str]] = []

    async def decide(self, args: dict[str, Any], *, request_id: str = "") -> Decision:
        self.calls.append((dict(args), request_id))
        action = self.actions.pop(0) if len(self.actions) > 1 else self.actions[0]
        return Decision(request_id, action, f"scripted {action}", [], dict(args))  # type: ignore[arg-type]


@pytest.fixture
def log(tmp_path):
    return LocalEventLog(tmp_path, session="s-plan")


async def test_execute_plan_drives_every_hop_through_the_gate_and_ends_with_a_stop(log) -> None:
    proposal = propose("square", 0.6)
    assert proposal.plan is not None
    sim = SimPlatform(CAL, event_log=log)
    gate = ScriptGate("Proceed")
    run = await execute_plan(sim, proposal.plan, log, gate=gate, beat="shapes")
    assert run.done and run.completed == 8 and run.aborted_at is None
    assert len(gate.calls) == 8 and len(sim.commands) == 8
    assert [c[0] for c in gate.calls] == [s.args() for s in proposal.plan.steps]
    assert sim.stops == ["trailing_zero"]  # the plan's terminal stop
    types = [e["type"] for e in log.read()]
    assert types.count("command") == 8 and types[-1] == "stop"
    assert sim.heading_deg == pytest.approx(360.0, abs=3.0)
    assert sim.distance_from_start_m < 0.1  # the square closes
    assert any("plan square 60 cm complete" in e["payload"]["text"] for e in log.read("thought"))


async def test_execute_plan_stops_at_the_first_non_proceed(log) -> None:
    plan = propose("square", 0.6).plan
    assert plan is not None
    sim = SimPlatform(CAL)
    gate = ScriptGate("Proceed", "Proceed", "Deny", "Proceed")
    run = await execute_plan(sim, plan, log, gate=gate)
    assert run.completed == 2 and run.aborted_at == 3 and not run.done
    assert run.reason == "Deny: scripted Deny"
    assert len(sim.commands) == 2 and sim.stops == ["deny"]
    assert len(gate.calls) == 3  # nothing after the deny
    assert any("abandoned at step 3/8" in e["payload"]["text"] for e in log.read("thought"))


@pytest.mark.parametrize("action", ["Guide", "Confirm"])
async def test_execute_plan_without_a_policy_is_strict(log, action: str) -> None:
    plan = propose("straight", 0.6).plan
    assert plan is not None
    sim = SimPlatform(CAL)
    run = await execute_plan(sim, plan, log, gate=ScriptGate(action))
    assert run.aborted_at == 1 and run.completed == 0 and sim.commands == [] and sim.stops == ["operator"]


async def test_execute_plan_refuses_an_invalid_plan_before_any_motion(log) -> None:
    sim = SimPlatform(CAL)
    bad = plan_of(Step(0.0, 1.0, 0.5))
    run = await execute_plan(sim, bad, log, gate=ScriptGate("Proceed"))
    assert run.aborted_at == 0 and sim.commands == [] and "yaw" in (run.reason or "")
    assert sim.stops == []  # nothing moved, nothing to stop beyond the validator's no


async def test_execute_plan_aborts_on_a_drive_error_and_still_stops(log) -> None:
    plan = propose("straight", 1.2).plan
    assert plan is not None and len(plan.steps) == 2
    sim = SimPlatform(CAL, fail_after=1)
    run = await execute_plan(sim, plan, log, gate=ScriptGate("Proceed"))
    assert run.completed == 1 and run.aborted_at == 2 and "simulated link failure" in (run.reason or "")
    assert sim.stops == ["error"]
    assert any(e["payload"]["where"] == "plans.execute_plan" for e in log.read("error"))


async def test_execute_plan_follows_a_policy_replan(log) -> None:
    plan = propose("straight", 1.2).plan
    assert plan is not None

    class Halver:
        def advise(self, decision, index, steps):
            if decision.action == "Guide":
                slow = [Step(s.linear / 2, s.angular, s.duration, s.label + " slow") for s in steps]
                return Advice("replan", "half speed", slow)
            return Advice("continue")

    sim = SimPlatform(CAL)
    run = await execute_plan(sim, plan, log, gate=ScriptGate("Guide", "Proceed"), policy=Halver())
    assert run.done and run.replans == 1 and len(sim.commands) == 2
    assert all(c["linear"] == pytest.approx(0.15) for c in sim.commands)


async def test_execute_plan_accepts_a_runtime_like_object_with_a_driver(log) -> None:
    class RuntimeLike:
        def __init__(self):
            self.driver = SimPlatform(CAL)

    plan = propose("back", 0.4).plan
    assert plan is not None
    rt = RuntimeLike()
    run = await execute_plan(rt, plan, log, gate=ScriptGate("Proceed"))
    assert run.done and rt.driver.commands[0]["linear"] < 0


async def test_execute_plan_without_a_gate_still_drives_and_stops(log) -> None:
    sim = SimPlatform(CAL)
    plan = propose("straight", 0.3).plan
    assert plan is not None
    run = await execute_plan(sim, plan, log)
    assert run.done and sim.stops == ["trailing_zero"]


# -- the tool ------------------------------------------------------------------------------------------


def test_plan_deepracer_tool_returns_the_validated_plan_and_records_it(tmp_path) -> None:
    log = LocalEventLog(tmp_path, session="s-tool")
    configure_plans(calibration=CAL, pen=PEN, event_log=log, beat="shapes")
    try:
        out = plan_deepracer("square", 0.6)
        assert out["ok"] and len(out["drive_calls"]) == 8 and out["drive_calls"][0]["linear"] == 0.3
        assert out["narration"].startswith("Plan: a square")
        assert "Narrate it" in out["note"] and "square" in out["shapes"]
        last = last_proposal()
        assert isinstance(last, Proposal) and last.ok
        thought = log.read("thought")[-1]
        assert (
            thought["payload"]["text"].startswith("plan square 60 cm: ok: 8 steps")
            and thought["beat"] == "shapes"
        )
        refused = plan_deepracer("circle", 1.5)
        assert not refused["ok"] and "drive_calls" not in refused and refused["note"].startswith("Refused")
        assert "footprint" in refused["validation"]["codes"]
        assert log.read("thought")[-1]["payload"]["text"].startswith("plan circle 1.5 m: refused")
        bad = plan_deepracer("square", "big")  # type: ignore[arg-type]
        assert not bad["ok"] and bad["validation"]["codes"] == ["geometry"]
    finally:
        reset_plans()
    assert last_proposal() is None


def test_validation_result_helpers() -> None:
    refused = ValidationResult.refused("footprint", "too big", footprint_m=[2, 2])
    assert (
        not refused.ok
        and refused.summary() == "refused: too big"
        and refused.to_dict()["metrics"] == {"footprint_m": [2, 2]}
    )
