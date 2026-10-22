"""DeepRacerRobot: bicycle model, refusals, handshake retries, zero pair in finally, events, tool names."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import (
    ENABLE_STATE_SERVICE,
    SERVO_TOPIC,
    VEHICLE_STATE_SERVICE,
    DeepRacerRobot,
    pregranted,
    rest_command_error,
    twist_to_servo,
)
from deepracer_agent.events import EventLog
from deepracer_agent.transport import HEARTBEAT_TOPIC, HeartbeatPublisher
from tests.unit._car_fakes import FakeAction, err, make_transport, service_ok

CAL = Calibration()


@pytest.fixture(autouse=True)
def _pregrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Driver tests run headless: the three command surfaces are pre-granted, as quick_hop does."""
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")
    monkeypatch.delenv("BYPASS_TOOL_CONSENT", raising=False)


def _robot(
    tmp_path: Path, action: FakeAction | None = None, **kw: Any
) -> tuple[DeepRacerRobot, FakeAction, EventLog]:
    transport, action, _topics = make_transport(action)
    log = EventLog(tmp_path, session="s-test", portal_url="")
    hb = HeartbeatPublisher(transport, "s-test")
    robot = DeepRacerRobot(transport, calibration=CAL, event_log=log, heartbeat=hb, **kw)
    return robot, action, log


# -- bicycle model -------------------------------------------------------------


@pytest.mark.parametrize(
    "linear,angular,angle,throttle",
    [
        (0.3, 0.0, 0.0, 0.3),
        (-0.3, 0.0, 0.0, -0.3),
        (0.15, 0.0, 0.0, 0.15),
        (0.3, 100.0, 1.0, 0.3),  # steering saturates at the lock
        (0.3, -100.0, -1.0, 0.3),
        (-0.3, 100.0, -1.0, -0.3),  # reverse mirrors the steering sign
        (0.0, 0.0, 0.0, 0.0),
        (0.9, 0.0, 0.0, 0.9),  # the base clamps linear before this is reached; the model itself is linear
    ],
)
def test_twist_to_servo_table(linear: float, angular: float, angle: float, throttle: float) -> None:
    assert twist_to_servo(linear, angular, CAL) == pytest.approx((angle, throttle), abs=1e-6)


def test_twist_to_servo_bicycle_geometry() -> None:
    """At 0.3 m/s a yaw of 0.5 rad/s wants atan(L*w/v) of steering, normalised by the lock."""
    angle, _ = twist_to_servo(0.3, 0.5, CAL)
    assert angle == pytest.approx(math.atan2(0.164 * 0.5, 0.3) / 0.5236, abs=1e-5)


def test_forward_sign_flips_throttle_only() -> None:
    cal = Calibration(throttle_forward_sign=-1)
    assert twist_to_servo(0.3, 0.5, cal)[1] == pytest.approx(-0.3)
    assert twist_to_servo(0.3, 0.5, cal)[0] == twist_to_servo(0.3, 0.5, CAL)[0]


def test_envelope_cap_maps_to_the_proven_servo_throttle(tmp_path: Path) -> None:
    """linear == max_speed sends servo throttle 0.3 (the hop proven on the car), never 1.0."""
    robot, action, _ = _robot(tmp_path)
    robot.drive(linear=5.0, duration=0.1)  # clamped to 0.3 m/s by the base
    assert action.publishes[0]["fields"] == {"angle": 0.0, "throttle": 0.3}


# -- refusal table -------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"linear": 0.0, "angular": 0.5}, "cannot yaw at rest"),
        ({"linear": 0.0, "angular": -0.1, "duration": 0.5}, "cannot yaw at rest"),
        ({"linear": 0.0005, "angular": 0.0}, "below the rest threshold"),
        ({"linear": float("nan"), "angular": 0.0}, "linear must be a finite number"),
        ({"linear": 0.3, "angular": float("inf")}, "angular must be a finite number"),
        ({"linear": 0.3, "duration": 2.5}, "exceeds max_duration 2.0s"),
        ({"linear": 0.3, "duration": 0.0}, "duration"),
        ({"linear": 0.3, "duration": -1.0}, "duration"),
        ({"linear": "fast"}, "linear"),
    ],
)
def test_refusal_table_drive(tmp_path: Path, kwargs: dict[str, Any], reason: str) -> None:
    robot, action, _ = _robot(tmp_path)
    result = robot.drive(**kwargs)
    assert result["status"] == "error"
    assert reason in result["content"][0]["text"]
    assert action.publishes == [] and action.services == [], "a refused request must have no side effect"


def test_rest_command_error_wording() -> None:
    assert rest_command_error(0.3, 0.0) is None
    assert rest_command_error(0.0, 0.0) is None
    assert "stop_deepracer" in (rest_command_error(0.0, 1.0) or "")


def test_calibration_refused_at_construction(tmp_path: Path) -> None:
    transport, _, _ = make_transport()
    with pytest.raises(ValueError, match="hop_s"):
        DeepRacerRobot(transport, calibration=Calibration(hop_s=3.0))


# -- handshake -----------------------------------------------------------------


def test_handshake_order_then_stream_then_zero_pair(tmp_path: Path) -> None:
    robot, action, _log = _robot(tmp_path)
    result = robot.drive(linear=0.3, angular=0.0, duration=0.5)
    assert result["status"] == "success"
    assert [(c["service"], c["fields"]) for c in action.services] == [
        (VEHICLE_STATE_SERVICE, {"state": 0}),
        (ENABLE_STATE_SERVICE, {"is_active": True}),
    ]
    assert all(c["timeout"] == 25.0 for c in action.services)
    pubs = action.publishes
    assert len(pubs) == 2 and all(p["topic"] == SERVO_TOPIC for p in pubs)
    assert (
        pubs[0]["count"] == 10
        and pubs[0]["rate"] == 20.0
        and pubs[0]["fields"] == {"angle": 0.0, "throttle": 0.3}
    )
    assert pubs[1] == {**pubs[1], "count": 1, "fields": {"angle": 0.0, "throttle": 0.0}}
    assert robot.enabled and robot.last_handshake == {"attempts": 1, "mode": 0, "enabled": True}
    # second drive does not repeat the handshake
    robot.drive(linear=0.2, duration=0.1)
    assert len(action.services) == 2


def test_handshake_retries_after_first_timeout(tmp_path: Path) -> None:
    action = FakeAction()
    action.service_results[VEHICLE_STATE_SERVICE] = [
        err("service call failed: timeout"),
        service_ok({"error": 0}),
    ]
    robot, action, log = _robot(tmp_path, action)
    assert robot.drive(linear=0.3, duration=0.1)["status"] == "success"
    assert [c["service"] for c in action.services] == [
        VEHICLE_STATE_SERVICE,
        VEHICLE_STATE_SERVICE,
        ENABLE_STATE_SERVICE,
    ]
    assert robot.last_handshake["attempts"] == 2
    assert "attempt 1/3" in log.read("error")[0]["payload"]["message"]


def test_handshake_gives_up_after_three_attempts_and_never_publishes(tmp_path: Path) -> None:
    action = FakeAction()
    action.service_results[ENABLE_STATE_SERVICE] = [err("timeout")]
    robot, action, _ = _robot(tmp_path, action)
    result = robot.drive(linear=0.3, duration=0.1)
    assert result["status"] == "error" and "timeout" in result["content"][0]["text"]
    assert len(action.services) == 6  # 3 x (vehicle_state ok, enable_state fail)
    assert action.publishes == [] and not robot.enabled


def test_handshake_refused_by_operator_does_not_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")  # arming not pre-granted, no operator
    robot, action, _ = _robot(tmp_path)
    result = robot.drive(linear=0.3, duration=0.1)
    assert result["status"] == "error" and "operator approval" in result["content"][0]["text"]
    assert len(action.services) == 1 and action.publishes == []


# -- zero pair and failed halt ---------------------------------------------------


def test_zero_pair_sent_even_when_publish_raises(tmp_path: Path) -> None:
    action = FakeAction()
    robot, action, _ = _robot(tmp_path, action)
    robot.enable()
    action.publish_raises = ConnectionError("socket died")
    with pytest.raises(ConnectionError):
        robot.drive(linear=0.3, duration=0.5)
    assert len(action.publishes) == 2 and action.publishes[-1]["fields"] == {"angle": 0.0, "throttle": 0.0}


def test_failed_trailing_stop_is_the_drives_error(tmp_path: Path) -> None:
    action = FakeAction()
    action.publish_results = [
        {"status": "success", "content": [{"text": "published 10"}]},
        err("bridge dropped"),
    ]
    robot, action, log = _robot(tmp_path, action)
    result = robot.drive(linear=0.3, duration=0.5)
    assert result["status"] == "error"
    assert "trailing stop failed" in result["content"][0]["text"]
    assert "bridge dropped" in result["content"][0]["text"]
    assert log.last("error")["payload"]["where"] == "stop"
    assert log.read("stop") == []


def test_zero_drive_is_a_hold_with_no_trailing_stop(tmp_path: Path) -> None:
    robot, action, _ = _robot(tmp_path)
    assert robot.drive(linear=0.0, angular=0.0, duration=0.2)["status"] == "success"
    assert len(action.publishes) == 1 and action.publishes[0]["fields"] == {"angle": 0.0, "throttle": 0.0}


# -- events and heartbeat ----------------------------------------------------------


def test_drive_emits_approval_motion_and_stop_events(tmp_path: Path) -> None:
    robot, _, log = _robot(tmp_path)
    robot.request_id = "r-42"
    robot.drive(linear=0.3, angular=0.5, duration=0.5)
    types = [e["type"] for e in log.read()]
    assert types == ["approval", "motion", "motion", "stop"]
    approval, start, end, stop = (e["payload"] for e in log.read())
    assert approval == {"request_id": "r-42", "decision": "approved", "by": "pregrant"}
    assert start["state"] == "start" and start["messages"] == 10 and start["duration_s"] == 0.5
    assert start["throttle"] == pytest.approx(0.3) and 0 < start["angle"] <= 1
    assert end["state"] == "end" and end["messages"] == 10
    assert stop["cause"] == "trailing_zero" and stop["request_id"] == "r-42" and stop["latency_ms"] >= 0
    assert all(e["source"] == "driver" for e in log.read())


def test_heartbeat_goes_active_during_the_stream(tmp_path: Path) -> None:
    seen: list[bool] = []
    action = FakeAction()
    robot, action, _ = _robot(tmp_path, action)
    hb = robot.heartbeat
    original = action.__call__

    def spy(name: str, **kw: Any) -> dict[str, Any]:
        if name == "publish":
            seen.append(hb.active)
        return original(name, **kw)

    robot.transport._action = spy  # type: ignore[attr-defined]
    robot.drive(linear=0.3, duration=0.1)
    assert seen == [True, False]  # active for the stream, idle for the zero pair
    assert not hb.active


def test_stop_emits_operator_cause_and_idles_heartbeat(tmp_path: Path) -> None:
    # The heartbeat drops to idle but keeps running, so the on-car deadman stays
    # armed and the screen does not show a trip after every operator stop.
    robot, action, log = _robot(tmp_path)
    robot.heartbeat.start()
    robot.heartbeat.set_active(True)
    assert robot.heartbeat.running and robot.heartbeat.active
    result = robot.stop()
    assert result["status"] == "success"
    assert action.services == [], "stop never needs the handshake"
    assert action.publishes[0]["fields"] == {"angle": 0.0, "throttle": 0.0}
    assert log.last("stop")["payload"]["cause"] == "operator"
    assert robot.heartbeat.running and not robot.heartbeat.active
    # the next trailing zero is back to its own cause
    robot.drive(linear=0.3, duration=0.1)
    assert log.last("stop")["payload"]["cause"] == "trailing_zero"


def test_stop_failure_is_an_error_event_not_a_stop_event(tmp_path: Path) -> None:
    action = FakeAction()
    action.publish_result = err("bridge down")
    robot, action, log = _robot(tmp_path, action)
    assert robot.stop()["status"] == "error"
    assert log.read("stop") == [] and log.last("error")["payload"]["where"] == "stop"


# -- tools ---------------------------------------------------------------------


def test_tool_names_are_fixed_by_contract(tmp_path: Path) -> None:
    robot, _, _ = _robot(tmp_path)
    names = [t.tool_name for t in robot.tools]
    assert names == ["drive_deepracer", "stop_deepracer"]
    spec = robot.tools[0].tool_spec
    props = spec["inputSchema"]["json"]["properties"]
    assert set(props) == {"linear", "angular", "duration"}
    assert "cannot turn in place" in spec["description"]


def test_drive_tool_emits_command_event_and_default_hop(tmp_path: Path) -> None:
    robot, action, log = _robot(tmp_path)
    drive = robot.tools[0]
    result = drive(linear=0.3, angular=0.0)  # direct call through the strands tool wrapper
    assert result["status"] == "success"
    command = log.read("command")[0]["payload"]
    assert command["tool"] == "drive_deepracer" and command["args"] == {
        "linear": 0.3,
        "angular": 0.0,
        "duration": None,
    }
    assert command["request_id"].startswith("r-")
    assert action.publishes[0]["count"] == 10  # hop 0.5 s at 20 Hz


def test_stop_tool_never_gated_on_handshake(tmp_path: Path) -> None:
    robot, action, log = _robot(tmp_path)
    assert robot.tools[1]()["status"] == "success"
    assert action.services == [] and log.read("command")[0]["payload"]["tool"] == "stop_deepracer"


def test_pregranted_matches_bare_and_namespaced(monkeypatch: pytest.MonkeyPatch) -> None:
    assert pregranted("/webserver_pkg/manual_drive")
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/cmd_vel")
    assert not pregranted("/webserver_pkg/manual_drive")
    monkeypatch.delenv("STRANDS_ROS2_COMMAND_ALLOW")
    assert not pregranted(HEARTBEAT_TOPIC)
    monkeypatch.setenv("BYPASS_TOOL_CONSENT", "true")
    assert pregranted("/webserver_pkg/manual_drive")
