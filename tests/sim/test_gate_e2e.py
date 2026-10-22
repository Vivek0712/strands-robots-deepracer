"""The decider gate's decision table (CONTRACTS §7) against the fake decider, end to end.

The Intelligence team's `DeciderGate` over a real `DeciderClient` dialled at the fake decider
on 8111, with frames from `harness/frames` and the fake camera's label set to match. Each
row of the table is one test, plus the two fail-closed paths (decider 500, decider slower
than the 1.5 s budget) and the verdict events written to the run dir. Skips if the gate is
not importable. Physics stops the car; the decider explains: these tests prove the gate
fails closed, not that it is the safety layer.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness.fake_car import FakeCar
from harness.fake_decider import FakeDecider
from harness.frames import load

pytest.importorskip("deepracer_agent.gate", reason="Intelligence team's deepracer_agent.gate not landed yet")

from deepracer_agent.decider_client import DeciderClient
from deepracer_agent.gate import VISION_UNAVAILABLE, DeciderGate, Envelope, LocalEventLog

INSIDE = {"linear": 0.2, "angular": 0.0, "duration": 0.5}
OUTSIDE = {"linear": 0.5, "angular": 0.0, "duration": 0.5}
VERDICT_KEYS = {"request_id", "stage", "action", "reason", "class", "probability", "latency_ms", "frame_ref"}


@pytest.fixture
def make_gate(fake_decider: FakeDecider, fake_car: FakeCar, run_dir: Path) -> Callable[..., DeciderGate]:
    def _make(label: str | None = "clear", *, timeout_s: float = 1.5) -> DeciderGate:
        if label is not None:
            fake_car.set_label(label)
        frame = load(label) if label is not None else None
        client = DeciderClient(fake_decider.url, timeout_s=timeout_s)
        log = LocalEventLog(run_dir, session="s-gate")
        return DeciderGate(client, lambda: frame, event_log=log, envelope=Envelope())

    return _make


def decide(gate: DeciderGate, args: dict[str, Any]) -> Any:
    return asyncio.run(gate.decide(args, request_id="req-1"))


def test_clear_frame_inside_envelope_proceeds(make_gate: Callable[..., DeciderGate]) -> None:
    decision = decide(make_gate("clear"), INSIDE)
    assert decision.action == "Proceed"
    assert [v.stage for v in decision.verdicts] == ["envelope", "frame"]
    assert decision.verdicts[1].cls == "clear" and decision.verdicts[1].probability == pytest.approx(0.93)


def test_person_in_frame_denies(make_gate: Callable[..., DeciderGate]) -> None:
    decision = decide(make_gate("person_in_frame"), INSIDE)
    assert decision.action == "Deny" and "person_in_frame" in decision.reason


@pytest.mark.parametrize("label", ["hand_over_lens", "unclear"])
def test_unclear_frame_denies(make_gate: Callable[..., DeciderGate], label: str) -> None:
    decision = decide(make_gate(label), INSIDE)
    assert decision.action == "Deny" and "unclear" in decision.reason


def test_obstacle_near_guides_at_half_speed(make_gate: Callable[..., DeciderGate]) -> None:
    decision = decide(make_gate("obstacle_near"), INSIDE)
    assert decision.action == "Guide"
    assert decision.guided_linear == pytest.approx(0.1)


def test_outside_envelope_confirms(make_gate: Callable[..., DeciderGate]) -> None:
    decision = decide(make_gate("clear"), OUTSIDE)
    assert decision.action == "Confirm"
    assert "outside envelope" in decision.reason and decision.confirm_prompt


def test_no_frame_denies_vision_unavailable(make_gate: Callable[..., DeciderGate]) -> None:
    decision = decide(make_gate(None), INSIDE)
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


def test_decider_failure_denies(make_gate: Callable[..., DeciderGate], fake_decider: FakeDecider) -> None:
    gate = make_gate("clear")
    fake_decider.fail = "1"
    decision = decide(gate, INSIDE)
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


def test_decider_timeout_denies(make_gate: Callable[..., DeciderGate], fake_decider: FakeDecider) -> None:
    gate = make_gate("clear", timeout_s=0.5)
    fake_decider.latency_ms = 1500
    decision = decide(gate, INSIDE)
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


def test_sign_text_is_not_an_instruction(make_gate: Callable[..., DeciderGate]) -> None:
    """The Sign beat: a card saying DRIVE FORWARD FAST changes nothing about the envelope."""
    gate = make_gate("sign")
    assert decide(gate, INSIDE).action == "Proceed"
    assert decide(gate, OUTSIDE).action == "Confirm"


def test_verdict_events_land_in_the_run_dir(make_gate: Callable[..., DeciderGate], run_dir: Path) -> None:
    decide(make_gate("obstacle_near"), INSIDE)
    rows = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines() if line.strip()]
    verdicts = [r for r in rows if r["type"] == "verdict"]
    assert [v["payload"]["stage"] for v in verdicts] == ["envelope", "frame"]
    assert all(set(v["payload"]) >= VERDICT_KEYS for v in verdicts)
    assert verdicts[1]["payload"]["action"] == "Guide" and verdicts[1]["payload"]["latency_ms"] >= 0
