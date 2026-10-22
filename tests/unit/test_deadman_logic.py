"""The on-car deadman rule (car/deadman/deepracer_deadman/deadman_logic.py), tested here without rclpy."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_LOGIC = Path(__file__).resolve().parents[2] / "car" / "deadman" / "deepracer_deadman" / "deadman_logic.py"
_spec = importlib.util.spec_from_file_location("deadman_logic", _LOGIC)
assert _spec and _spec.loader
logic = importlib.util.module_from_spec(_spec)
sys.modules["deadman_logic"] = logic
_spec.loader.exec_module(logic)

ZERO, LED_RED = logic.ACTION_ZERO, logic.ACTION_LED_RED
LED_GREEN, PUBLISH = logic.ACTION_LED_GREEN, logic.ACTION_PUBLISH_STATE
LED_OFF = logic.ACTION_LED_OFF


def _armed(t0: float = 100.0) -> Any:
    dm = logic.DeadmanLogic(t0, wall=1_700_000_000.0)
    assert dm.on_heartbeat(t0, 1_700_000_000.0) == [LED_GREEN, PUBLISH]  # first arm: green, "go"
    assert dm.state == "armed"
    return dm


def _tripped(t0: float = 0.0) -> Any:
    dm = _armed(t0)
    assert dm.tick(t0 + 0.31) == [ZERO, LED_RED, PUBLISH]
    assert dm.state == "tripped"
    return dm


def test_constants_match_contract() -> None:
    assert logic.GAP_TRIP_S == 0.3 and logic.RESUME_S == 1.0 and logic.IDLE_AFTER_S == 30.0
    assert logic.ZERO_COUNT == 10 and logic.ZERO_RATE_HZ == 20.0


def test_idle_does_nothing_without_a_heartbeat() -> None:
    dm = logic.DeadmanLogic(0.0)
    for t in (0.5, 5.0, 60.0):
        assert dm.tick(t) == []
    assert dm.state == "idle" and dm.trips == 0
    assert dm.state_dict(60.0) == {"state": "idle", "gap_ms": 0, "since": logic.iso_utc(0.0), "trips": 0}


def test_first_heartbeat_arms() -> None:
    dm = _armed()
    assert dm.state_dict(100.05)["gap_ms"] == 50


def test_steady_heartbeats_never_trip() -> None:
    dm = _armed()
    t = 100.0
    for _ in range(200):  # 10 s at 20 Hz
        t += 0.05
        assert dm.on_heartbeat(t) == []
        assert dm.tick(t + 0.01) == []
    assert dm.state == "armed" and dm.trips == 0


@pytest.mark.parametrize("gap", [0.301, 0.35, 0.5, 2.0, 29.5])
def test_gap_over_300ms_trips_once_with_zeros_and_red(gap: float) -> None:
    dm = _armed()
    assert dm.tick(100.0 + 0.3) == [], "exactly 300 ms is not yet a trip"
    assert dm.tick(100.0 + gap) == [ZERO, LED_RED, PUBLISH]
    assert dm.state == "tripped" and dm.trips == 1
    assert dm.tick(100.0 + gap + 0.1) == [], "tripped is latched; the zeros are not repeated"
    assert dm.state_dict(100.0 + gap)["gap_ms"] == round(gap * 1000)


def test_tripped_latches_until_heartbeats_resume_for_one_second() -> None:
    dm = _armed()
    dm.tick(101.0)
    assert dm.state == "tripped"
    t = 101.0
    # a lone heartbeat does not re-arm
    assert dm.on_heartbeat(t) == [] and dm.state == "tripped"
    # heartbeats with a 400 ms hole restart the resume clock
    base = t + 0.4
    assert dm.on_heartbeat(base) == [] and dm.state == "tripped"
    for i in range(1, 20):  # 0.95 s steady at 20 Hz: still not enough
        assert dm.on_heartbeat(base + i * 0.05) == []
    assert dm.state == "tripped"
    t = base + 20 * 0.05  # 1.0 s steady
    assert dm.on_heartbeat(t) == [LED_GREEN, PUBLISH]
    assert dm.state == "armed" and dm.trips == 1
    # and it can trip again
    assert dm.tick(t + 0.31) == [ZERO, LED_RED, PUBLISH] and dm.trips == 2


def test_no_heartbeat_for_30s_goes_idle_from_tripped_and_from_armed() -> None:
    dm = _armed()
    dm.tick(101.0)
    assert dm.state == "tripped"
    assert dm.tick(129.99) == []
    # the red trip LED must not stay on an unattended car: idle turns it off
    assert dm.tick(130.0) == [LED_OFF, PUBLISH] and dm.state == "idle"
    assert dm.tick(500.0) == []
    # back from idle on the next heartbeat: armed, and the LED says "go" (green)
    assert dm.on_heartbeat(500.0) == [LED_GREEN, PUBLISH] and dm.state == "armed"
    # from armed, a 30 s silence seen in one tick goes idle without a trip: there is nothing to zero
    dm2 = _armed(0.0)
    assert dm2.tick(30.0) == [LED_OFF, PUBLISH] and dm2.state == "idle" and dm2.trips == 0


def test_state_json_shape_matches_contract() -> None:
    dm = _armed(10.0)
    dm.tick(10.5)
    payload = json.loads(json.dumps(dm.state_dict(10.6)))
    assert set(payload) == {"state", "gap_ms", "since", "trips"}
    assert payload["state"] == "tripped" and payload["gap_ms"] == 600 and payload["trips"] == 1
    assert payload["since"].endswith("Z") and "T" in payload["since"]


def test_zero_and_led_fields() -> None:
    assert logic.zero_servo_fields() == {"angle": 0.0, "throttle": 0.0}
    assert logic.red_led_fields() == {"red": 10000000, "green": 0, "blue": 0}
    assert logic.green_led_fields() == {"red": 0, "green": 10000000, "blue": 0}
    assert logic.off_led_fields() == {"red": 0, "green": 0, "blue": 0}


def test_manual_drive_while_tripped_is_zeroed_again() -> None:
    """A command that outlives its heartbeat meets another zero burst, as often as it arrives."""
    dm = _tripped()
    assert dm.on_manual_drive(0.35, 0.0, 0.3) == [ZERO]
    assert dm.on_manual_drive(0.40, 0.2, 0.0) == [ZERO]
    assert dm.rezeros == 2 and dm.trips == 1 and dm.state == "tripped"


def test_zero_pairs_never_rezero() -> None:
    """The node hears its own zeros on manual_drive; they must not feed back into a burst."""
    dm = _tripped()
    assert dm.on_manual_drive(0.35, 0.0, 0.0) == []
    assert dm.rezeros == 0


@pytest.mark.parametrize("state", ["idle", "armed"])
def test_manual_drive_is_ignored_unless_tripped(state: str) -> None:
    dm = logic.DeadmanLogic(0.0) if state == "idle" else _armed(0.0)
    assert dm.on_manual_drive(0.1, 0.0, 0.3) == []
    assert dm.rezeros == 0 and dm.state == state


def test_rezero_does_not_delay_rearm() -> None:
    """Re-zeroing is a reflex, not a state change: steady heartbeats still re-arm after 1 s."""
    dm = _tripped()
    t = 0.5
    actions: list[str] = []
    for i in range(25):
        dm.on_manual_drive(t + i * 0.05, 0.0, 0.3)
        actions += dm.on_heartbeat(t + i * 0.05)
    assert LED_GREEN in actions and dm.state == "armed"
    assert dm.on_manual_drive(t + 25 * 0.05, 0.0, 0.3) == []  # armed again: the laptop is in charge


def test_led_sequence_trip_rearm_idle() -> None:
    """Green on arm, red on trip, green on re-arm, off on idle: the LED says what the deadman did."""
    dm = logic.DeadmanLogic(0.0, wall=1_700_000_000.0)
    leds = [a for a in dm.on_heartbeat(0.0, 1_700_000_000.0) if a.startswith("led_")]
    leds += [a for a in dm.tick(0.5) if a.startswith("led_")]
    t = 0.5
    for i in range(0, 25):  # 1.2 s of steady heartbeats re-arms
        leds += [a for a in dm.on_heartbeat(t + i * 0.05) if a.startswith("led_")]
    leds += [a for a in dm.tick(t + 25 * 0.05 + 31.0) if a.startswith("led_")]
    assert leds == [LED_GREEN, LED_RED, LED_GREEN, LED_OFF]
    assert dm.state == "idle"


@pytest.mark.parametrize(
    "sequence,expected_state,expected_trips",
    [
        ([("hb", 0.0), ("tick", 0.2), ("tick", 0.29)], "armed", 0),
        ([("hb", 0.0), ("tick", 0.31)], "tripped", 1),
        ([("hb", 0.0), ("hb", 0.05), ("hb", 0.10), ("tick", 0.45)], "tripped", 1),
        ([("hb", 0.0), ("tick", 0.31), ("hb", 0.4), ("hb", 0.45), ("tick", 0.5)], "tripped", 1),
        ([("hb", 0.0), ("tick", 0.31), ("tick", 31.0)], "idle", 1),
        ([("tick", 1.0), ("tick", 100.0)], "idle", 0),
        ([("hb", 0.0), ("tick", 0.31), ("tick", 0.32), ("tick", 0.33)], "tripped", 1),
        ([("hb", 0.0), ("drive", 0.1), ("drive", 0.2), ("tick", 0.29)], "armed", 0),
        ([("hb", 0.0), ("tick", 0.31), ("zero", 0.35), ("zero", 0.40)], "tripped", 1),
    ],
)
def test_refusal_table_transitions(
    sequence: list[tuple[str, float]], expected_state: str, expected_trips: int
) -> None:
    """Which sequences do NOT move the car: only a 300 ms gap while armed produces zeros, and only once.

    ``drive`` is a non-zero manual_drive, ``zero`` a zero pair; neither adds a zero burst here.
    """
    dm = logic.DeadmanLogic(0.0)
    zeros = 0
    for kind, t in sequence:
        if kind == "hb":
            actions = dm.on_heartbeat(t)
        elif kind == "tick":
            actions = dm.tick(t)
        elif kind == "drive":
            actions = dm.on_manual_drive(t, 0.0, 0.3)
        else:
            actions = dm.on_manual_drive(t, 0.0, 0.0)
        zeros += actions.count(ZERO)
    assert dm.state == expected_state and dm.trips == expected_trips
    assert zeros == expected_trips


def test_module_is_python38_compatible_syntax() -> None:
    """No match, no X | Y at runtime, no list[str] outside annotations (CONTRACTS section 0)."""
    source = _LOGIC.read_text()
    assert "match " not in source.replace("match_", "")
    assert " | None" not in source and "list[" not in source and "dict[" not in source
    assert "from __future__ import annotations" in source
    node = (_LOGIC.parent / "deadman_node.py").read_text()
    assert " | None" not in node and "match " not in node.replace("match_", "")
