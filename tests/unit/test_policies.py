"""policies: replay from a recorded events.jsonl, the vision fail-closed table, mock and model policies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.gate import Decision, LocalEventLog
from deepracer_agent.plans import Pen, Step, execute_plan, propose
from deepracer_agent.platforms import SimPlatform
from deepracer_agent.policies import (
    MAX_REPLANS,
    VISION_TABLE,
    MockPolicy,
    ModelPolicy,
    NavigationPolicy,
    ReplayPolicy,
    VisionPolicy,
    resolve_plan,
)

CAL = Calibration()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "events-marshal-replay.jsonl"


def decision(action: str, reason: str = "") -> Decision:
    return Decision("req", action, reason or f"scripted {action}", [], {})  # type: ignore[arg-type]


# -- replay ---------------------------------------------------------------------------------------------


def test_fixture_is_a_recorded_run() -> None:
    lines = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    assert {e["type"] for e in lines} >= {"command", "verdict", "motion", "stop"}


def test_replay_policy_turns_recorded_commands_into_a_validated_plan() -> None:
    policy = ReplayPolicy(FIXTURE, calibration=CAL)
    assert isinstance(policy, NavigationPolicy)
    commands = policy.commands()
    assert len(commands) == 4 and all(c["payload"]["tool"] == "drive_deepracer" for c in commands)
    proposal = policy.plan()
    assert proposal.ok and proposal.source == "replay"
    plan = proposal.plan
    assert plan is not None and plan.shape == "replay" and len(plan.steps) == 4
    assert plan.steps[0].args() == {"linear": 0.3, "angular": 0.0, "duration": 0.5}
    assert plan.steps[2].duration == CAL.hop_s  # the recorded command had no duration
    assert plan.steps[3].angular == 0.5 and plan.steps[3].label.startswith("replay 4")


def test_replay_policy_filters_by_beat_and_caps_steps() -> None:
    assert len(ReplayPolicy(FIXTURE, beat="marshal").commands()) == 3
    assert len(ReplayPolicy(FIXTURE, beat="red_light").commands()) == 1
    assert len(ReplayPolicy(FIXTURE, max_steps=2).steps()) == 2
    assert not ReplayPolicy(FIXTURE, beat="nothing").plan().ok


def test_replay_policy_refuses_a_recording_that_broke_the_caps(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    rows = [
        {
            "seq": 1,
            "type": "command",
            "payload": {"tool": "drive_deepracer", "args": {"linear": 0.9, "duration": 5}},
        },
        {"seq": 2, "type": "command", "payload": {"tool": "stop_deepracer", "args": {}}},
        "not json",
    ]
    path.write_text("\n".join(json.dumps(r) if isinstance(r, dict) else r for r in rows) + "\n")
    proposal = ReplayPolicy(path).plan()
    assert not proposal.ok and {"linear_cap", "duration_cap"} <= set(proposal.validation.codes)
    assert not ReplayPolicy(tmp_path / "missing.jsonl").plan().ok


async def test_replay_runs_through_the_gate_one_hop_at_a_time(tmp_path: Path) -> None:
    class Gate:
        def __init__(self):
            self.n = 0

        async def decide(self, args, *, request_id=""):
            self.n += 1
            return decision("Proceed" if self.n < 3 else "Deny", "person_in_frame today")

    log = LocalEventLog(tmp_path, session="s-replay")
    sim = SimPlatform(CAL)
    proposal = ReplayPolicy(FIXTURE).plan()
    assert proposal.plan is not None
    run = await execute_plan(sim, proposal.plan, log, gate=Gate(), policy=ReplayPolicy(FIXTURE))
    assert run.completed == 2 and run.aborted_at == 3 and len(sim.commands) == 2 and sim.stops == ["deny"]


# -- vision: fail closed ----------------------------------------------------------------------------------

STEPS = [Step(0.3, 0.0, 1.0, "a"), Step(0.25, 0.8, 1.5, "b"), Step(0.3, 0.0, 2.0, "c")]


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (decision("Proceed"), "continue"),
        (decision("Guide", "obstacle_near"), "replan"),
        (decision("Confirm", "outside envelope"), "stop"),
        (decision("Deny", "person_in_frame"), "stop"),
        (decision("Transform", "unknown action"), "stop"),
        (None, "stop"),
        ("not a decision", "stop"),
        (object(), "stop"),
    ],
    ids=["proceed", "guide", "confirm", "deny", "unknown-action", "none", "string", "object"],
)
def test_vision_policy_fail_closed_table(verdict: Any, expected: str) -> None:
    policy = VisionPolicy(calibration=CAL)
    advice = policy.advise(verdict, 0, STEPS)
    assert advice.action == expected
    assert policy.history[-1]["action"] == expected
    if expected == "stop":
        assert advice.reason  # a stop always names its reason
    assert set(VISION_TABLE.values()) == {"continue", "replan", "stop"}


def test_vision_replan_halves_speed_keeps_geometry_and_respects_the_cap() -> None:
    policy = VisionPolicy(calibration=CAL)
    advice = policy.advise(decision("Guide", "obstacle_near (p=0.8)"), 1, STEPS)
    assert advice.action == "replan" and advice.steps is not None
    assert advice.steps[0] == STEPS[0]  # done steps are kept
    slow = advice.steps[1:]
    assert all(abs(s.linear) == pytest.approx(0.125) or abs(s.linear) == pytest.approx(0.15) for s in slow)
    assert all(s.duration <= CAL.max_duration_s for s in slow)
    # step b: 1.5 s at 0.25 -> 3.0 s at 0.125, split in two; radius unchanged
    assert slow[0].duration == 1.5 and slow[1].duration == 1.5
    assert slow[0].radius_m == pytest.approx(STEPS[1].radius_m)
    # step c: 2.0 s -> 4.0 s split in two
    assert len(slow) == 4 and slow[2].label.endswith("slow 1/2")
    assert policy.replans == 1


def test_vision_policy_stops_after_max_replans() -> None:
    policy = VisionPolicy(calibration=CAL, max_replans=1)
    assert policy.advise(decision("Guide"), 0, STEPS).action == "replan"
    again = policy.advise(decision("Guide"), 0, STEPS)
    assert again.action == "stop" and "re-plans" in again.reason
    assert MAX_REPLANS == 3


def test_vision_policy_stops_when_the_replan_itself_is_invalid() -> None:
    policy = VisionPolicy(calibration=CAL, pen=Pen(max_total_time_s=2.0))
    advice = policy.advise(decision("Guide"), 0, STEPS)
    assert advice.action == "stop" and "re-plan refused" in advice.reason


def test_vision_policy_plans_through_its_base_or_refuses() -> None:
    assert not VisionPolicy().plan("square of 60 cm").ok
    with_base = VisionPolicy(MockPolicy(calibration=CAL))
    assert with_base.plan("square of 60 cm").ok


async def test_vision_policy_in_execute_plan_replans_then_finishes(tmp_path: Path) -> None:
    class Gate:
        def __init__(self):
            self.n = 0

        async def decide(self, args, *, request_id=""):
            self.n += 1
            return decision("Guide" if self.n == 1 else "Proceed", "obstacle_near (p=0.7)")

    log = LocalEventLog(tmp_path, session="s-vision")
    sim = SimPlatform(CAL)
    plan = propose("straight", 0.6).plan
    assert plan is not None
    run = await execute_plan(sim, plan, log, gate=Gate(), policy=VisionPolicy(calibration=CAL))
    assert run.done and run.replans == 1
    assert len(sim.commands) == 2 and all(c["linear"] == pytest.approx(0.15) for c in sim.commands)


# -- mock ----------------------------------------------------------------------------------------------


def test_mock_policy_scripts_or_falls_back_to_shapes() -> None:
    square = propose("square", 0.6)
    fixed = MockPolicy(square)
    assert fixed.plan("anything").ok and fixed.requests == ["anything"]
    assert isinstance(fixed, NavigationPolicy)
    by_key = MockPolicy({"square": square.plan, "circle": propose("circle", 1.5)}, calibration=CAL)  # type: ignore[dict-item]
    assert by_key.plan("please drive a SQUARE").ok
    assert not by_key.plan("a circle").ok
    assert (
        not by_key.plan("hexagon").ok and "no scripted plan" in by_key.plan("hexagon").validation.reasons[0]
    )
    free = MockPolicy(calibration=CAL)
    assert free.plan("figure 8 of 60 cm").plan.shape == "figure_8"
    assert free.plan("figure 8 half a metre").validation.codes == ("geometry",)  # lobes too tight
    assert not free.plan("what is your battery").ok
    assert free.advise(decision("Guide"), 0, STEPS).action == "stop"  # mock is strict


# -- model ---------------------------------------------------------------------------------------------


async def test_model_policy_reads_back_what_the_tool_recorded(tmp_path: Path) -> None:
    from deepracer_agent.plans import configure_plans, plan_deepracer, reset_plans

    log = LocalEventLog(tmp_path, session="s-model")
    configure_plans(calibration=CAL, pen=Pen(), event_log=log)

    class FakeRuntime:
        def __init__(self, call_tool: bool):
            self.call_tool = call_tool
            self.submitted: list[str] = []

        async def submit(self, text, *, beat=None):
            self.submitted.append(text)
            if self.call_tool:
                plan_deepracer("square", 0.6)
            return "r-1"

        async def wait(self, request_id, timeout=None):
            return "Plan: a square."

    try:
        rt = FakeRuntime(True)
        proposal = await resolve_plan(ModelPolicy(rt, beat="shapes"), "a square of 60 cm")
        assert proposal.ok and proposal.source == "model" and "Plan only" in rt.submitted[0]
        silent = await resolve_plan(ModelPolicy(FakeRuntime(False)), "a square")
        assert not silent.ok and "did not call plan_deepracer" in silent.validation.reasons[0]
    finally:
        reset_plans()
