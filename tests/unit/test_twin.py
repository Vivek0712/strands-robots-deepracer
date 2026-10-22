"""TwinTransport: gate refusal table, mode/enable relay, no-watchdog hold, zero pair, deadman, pose."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import DeepRacerRobot, twist_to_servo
from deepracer_agent.events import EventLog
from deepracer_agent.transport import (
    DEADMAN_STATE_TOPIC,
    DEADMAN_STATE_TYPE,
    HEARTBEAT_TOPIC,
    HEARTBEAT_TYPE,
    SERVO_TYPE,
    DeadmanMonitor,
    HeartbeatPublisher,
    parse_service_response,
)
from deepracer_agent.twin import (
    MANUAL_DRIVE_TOPIC,
    TWIN_GRAPH,
    BodyEventLog,
    TwinTransport,
    load_deadman_logic,
    range_reason,
    servo_to_twist,
)

ARM = "/manual_drive,/vehicle_state,/enable_state"


class Clock:
    def __init__(self, t: float = 100.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def tick(self, dt: float) -> float:
        self.t += dt
        return self.t


@pytest.fixture(autouse=True)
def _no_pregrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRANDS_ROS2_COMMAND_ALLOW", raising=False)
    monkeypatch.delenv("BYPASS_TOOL_CONSENT", raising=False)
    monkeypatch.setenv("PORTAL_URL", "")


def make_twin(event_log: Any | None = None, **kw: Any) -> tuple[TwinTransport, Clock]:
    clock = Clock()
    twin = TwinTransport(
        realtime=False, clock=clock, wall=lambda: 1_700_000_000.0 + clock.t, event_log=event_log, **kw
    )
    return twin, clock


def arm(twin: TwinTransport) -> None:
    assert (
        twin.service_call(service="/ctrl_pkg/vehicle_state", type="t", fields={"state": 0})["status"]
        == "success"
    )
    assert (
        twin.service_call(service="/ctrl_pkg/enable_state", type="t", fields={"is_active": True})["status"]
        == "success"
    )


def drive(twin: TwinTransport, angle: float, throttle: float, count: int = 1) -> dict[str, Any]:
    return twin.publish(
        topic=MANUAL_DRIVE_TOPIC,
        type=SERVO_TYPE,
        fields={"angle": angle, "throttle": throttle},
        count=count,
        rate=20,
    )


# -- protocol --------------------------------------------------------------------------------------


def test_twin_satisfies_upstream_protocols_and_lists_the_deepracer_graph() -> None:
    from strands_robots.drivers.ros._mobile_base import ServiceCapable, Transport

    twin, _ = make_twin()
    assert isinstance(twin, Transport) and isinstance(twin, ServiceCapable)
    assert twin.twist_type == SERVO_TYPE
    assert set(twin.list_topics()) == {name for name, _ in TWIN_GRAPH}
    assert MANUAL_DRIVE_TOPIC in twin.list_topics() and DEADMAN_STATE_TOPIC in twin.list_topics()
    status = twin.status()
    assert status["connected"] is True and "twin" in status["text"]


def test_deadman_logic_is_the_on_car_module() -> None:
    logic = load_deadman_logic()
    assert logic.GAP_TRIP_S == 0.3 and logic.ZERO_COUNT == 10
    assert Path(logic.__file__).parts[-3:] == ("deadman", "deepracer_deadman", "deadman_logic.py")


# -- gate refusal table ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        ("publish", MANUAL_DRIVE_TOPIC),
        ("publish", "/manual_drive"),
        ("service_call", "/ctrl_pkg/vehicle_state"),
        ("service_call", "/ctrl_pkg/enable_state"),
    ],
)
def test_refusal_table_gate_without_operator(kind: str, target: str) -> None:
    twin, _ = make_twin()
    if kind == "publish":
        result = twin.publish(
            topic=target, type=SERVO_TYPE, fields={"angle": 0, "throttle": 0.3}, count=1, rate=20
        )
    else:
        result = twin.service_call(service=target, type="t", fields={"state": 0})
    assert result["status"] == "error"
    assert "safety-critical command surface" in result["content"][0]["text"]
    assert twin.manual_drive_seen == 0 and twin.mode == 0 and twin.enabled is False


def test_pregrant_allows_the_three_surfaces_and_reads_are_never_gated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    twin, _ = make_twin()
    assert twin.service_call(service="/i2c_pkg/battery_level", type="t", fields={})["status"] == "success"
    assert twin.echo(topic=DEADMAN_STATE_TOPIC, type=None, count=1, timeout=1.0)["status"] == "success"
    assert (
        twin.publish(topic=HEARTBEAT_TOPIC, type=HEARTBEAT_TYPE, fields={}, count=1, rate=10)["status"]
        == "success"
    )
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    arm(twin)
    assert drive(twin, 0.0, 0.3)["status"] == "success"
    assert twin.servo == {"angle": 0.0, "throttle": 0.3}


def test_bypass_consent_allows_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BYPASS_TOOL_CONSENT", "true")
    twin, _ = make_twin()
    arm(twin)
    assert drive(twin, 0.0, 0.3)["status"] == "success"


# -- ctrl node relay -----------------------------------------------------------------------------------


def test_relay_only_in_mode_0_and_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, _ = make_twin()
    # boot: mode 0, disabled -> dropped
    assert drive(twin, 0.0, 0.3)["status"] == "success"
    assert twin.servo == {"angle": 0.0, "throttle": 0.0} and twin.drops["not_armed"] == 1
    # enable alone is enough after a vehicle_state 0
    arm(twin)
    drive(twin, 0.1, 0.3)
    assert twin.servo == {"angle": 0.1, "throttle": 0.3}
    # mode 1 (autonomous): vehicle_state disables and zeros, then drops
    assert parse_service_response(
        twin.service_call(service="/ctrl_pkg/vehicle_state", type="t", fields={"state": 1})
    ) == {"error": 0}
    assert twin.servo == {"angle": 0.0, "throttle": 0.0} and twin.enabled is False
    twin.service_call(service="/ctrl_pkg/enable_state", type="t", fields={"is_active": True})
    drive(twin, 0.1, 0.3)
    assert twin.servo == {"angle": 0.0, "throttle": 0.0} and twin.drops["not_armed"] == 2
    # disable while moving writes a zero pair
    twin.service_call(service="/ctrl_pkg/vehicle_state", type="t", fields={"state": 0})
    twin.service_call(service="/ctrl_pkg/enable_state", type="t", fields={"is_active": True})
    drive(twin, 0.0, 0.3)
    assert twin.servo["throttle"] == 0.3
    twin.service_call(service="/ctrl_pkg/enable_state", type="t", fields={"is_active": False})
    assert twin.servo == {"angle": 0.0, "throttle": 0.0}


@pytest.mark.parametrize(
    ("fields", "fragment"),
    [
        ({"angle": 0.0}, "throttle missing"),
        ({"angle": "a", "throttle": 0.0}, "angle is not a number"),
        ({"angle": 0.0, "throttle": float("nan")}, "throttle is not finite"),
        ({"angle": 1.5, "throttle": 0.0}, "out of range"),
        ({"angle": 0.0, "throttle": -1.01}, "out of range"),
        ({"angle": True, "throttle": 0.0}, "angle is not a number"),
    ],
)
def test_refusal_table_servo_range(fields: dict[str, Any], fragment: str) -> None:
    assert fragment in str(range_reason(fields))
    assert range_reason({"angle": -1.0, "throttle": 1.0}) is None


@pytest.mark.parametrize(
    ("service", "fields", "expected"),
    [
        ("/ctrl_pkg/vehicle_state", {"state": 7}, {"error": 1}),
        ("/ctrl_pkg/vehicle_state", {"state": True}, {"error": 1}),
        ("/ctrl_pkg/enable_state", {"is_active": 1}, {"error": 1}),
        ("/servo_pkg/set_led_state", {"red": 10_000_001, "green": 0, "blue": 0}, {"error": 1}),
        ("/servo_pkg/set_led_state", {"red": 0, "green": 0}, {"error": 1}),
        (
            "/servo_pkg/get_calibration",
            {"cal_type": 2},
            {"max": 0, "mid": 0, "min": 0, "polarity": 0, "error": 1},
        ),
    ],
)
def test_refusal_table_services(
    monkeypatch: pytest.MonkeyPatch, service: str, fields: dict[str, Any], expected: dict[str, Any]
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, _ = make_twin()
    assert parse_service_response(twin.service_call(service=service, type="t", fields=fields)) == expected
    unknown = twin.service_call(service="/nope", type="t", fields={})
    assert unknown["status"] == "error" and "does not exist" in unknown["content"][0]["text"]


def test_read_services_answer_the_car_shapes() -> None:
    twin, _ = make_twin(battery=7)
    assert parse_service_response(
        twin.service_call(service="/i2c_pkg/battery_level", type="t", fields={})
    ) == {"level": 7}
    cal = parse_service_response(
        twin.service_call(service="/servo_pkg/get_calibration", type="t", fields={"cal_type": 1})
    )
    assert cal and set(cal) == {"max", "mid", "min", "polarity", "error"} and cal["mid"] == 1446000
    led = parse_service_response(
        twin.service_call(
            service="/servo_pkg/set_led_state", type="t", fields={"red": 0, "green": 10_000_000, "blue": 0}
        )
    )
    assert led == {"error": 0} and twin.led == {"red": 0, "green": 10_000_000, "blue": 0}
    assert parse_service_response(
        twin.service_call(service="/servo_pkg/get_led_state", type="t", fields={})
    ) == {
        "red": 0,
        "green": 10_000_000,
        "blue": 0,
        "error": 0,
    }


# -- no watchdog, zero pair stops ------------------------------------------------------------------------


def test_no_watchdog_a_stream_that_stops_holds_the_last_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, clock = make_twin(deadman=False)
    arm(twin)
    drive(twin, 0.0, 0.3, count=3)
    for _ in range(50):
        twin.advance(clock.tick(0.1))  # five seconds of silence
    assert twin.servo == {"angle": 0.0, "throttle": 0.3}
    assert twin.pose()["v"] == pytest.approx(0.3)
    assert twin.pose()["x"] == pytest.approx(1.5, abs=1e-6)  # it kept rolling: no watchdog, like the car


def test_zero_pair_stops_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, clock = make_twin(deadman=False)
    arm(twin)
    drive(twin, 0.0, 0.3)
    twin.advance(clock.tick(0.5))
    drive(twin, 0.0, 0.0)
    x_stop = twin.pose()["x"]
    twin.advance(clock.tick(2.0))
    assert twin.pose() == {**twin.pose(), "x": pytest.approx(x_stop), "v": 0.0}


def test_abort_stream_ends_a_count_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, _ = make_twin()
    arm(twin)
    twin.abort_stream()  # the stop arrives before the stream starts: nothing goes out on the old generation
    result = drive(twin, 0.0, 0.3, count=10)
    assert result["status"] == "success" and result["aborted"] is False and result["sent"] == 10
    sent: list[int] = []
    original = twin.handle_manual_drive

    def cut_after_two(fields: dict[str, Any]) -> str | None:
        sent.append(1)
        if len(sent) == 2:
            twin.abort_stream()
        return original(fields)

    twin.handle_manual_drive = cut_after_two  # type: ignore[method-assign]
    result = drive(twin, 0.0, 0.3, count=10)
    assert result["aborted"] is True and result["sent"] == 2
    assert "interrupted by stop" in result["content"][0]["text"]


# -- deadman emulation ------------------------------------------------------------------------------------


def test_deadman_trips_at_300ms_gap_and_zeros_the_servo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    log = EventLog(tmp_path, session="s-twin", portal_url="")
    twin, clock = make_twin(event_log=log)
    arm(twin)
    monitor = DeadmanMonitor(twin, log, clock=clock)
    monitor.start()
    assert monitor.state == "idle"  # the subscription gets the current state at once
    hb = twin.topic(HEARTBEAT_TOPIC, HEARTBEAT_TYPE)
    hb.advertise()
    hb.publish({"stamp": {"sec": 1, "nanosec": 0}, "frame_id": "s-twin"})
    assert monitor.state == "armed" and twin.led["green"] == 10_000_000  # green on arm
    drive(twin, 0.0, 0.3)
    for _ in range(5):
        clock.tick(0.05)
        twin.advance()
        hb.publish({"stamp": {"sec": 1, "nanosec": 0}, "frame_id": "s-twin"})
    assert twin.servo["throttle"] == 0.3 and monitor.state == "armed"
    twin.advance(clock.tick(0.29))
    assert monitor.state == "armed" and twin.servo["throttle"] == 0.3  # 290 ms: not yet
    twin.advance(clock.tick(0.02))
    assert monitor.state == "tripped" and twin.servo == {"angle": 0.0, "throttle": 0.0}
    assert twin.led == {"red": 10_000_000, "green": 0, "blue": 0}
    assert twin.pose()["v"] == 0.0
    stop = log.last("stop")
    assert stop and stop["payload"]["cause"] == "deadman"
    # a late non-zero command while tripped is re-zeroed (the node's re-zero rule)
    drive(twin, 0.0, 0.3)
    assert twin.servo == {"angle": 0.0, "throttle": 0.0}
    # heartbeats for a steady second re-arm it
    for _ in range(25):
        clock.tick(0.05)
        hb.publish({"stamp": {"sec": 1, "nanosec": 0}, "frame_id": "s-twin"})
        twin.advance()
    assert monitor.state == "armed" and twin.led["green"] == 10_000_000
    monitor.stop()


def test_heartbeat_publisher_arms_the_twin_through_the_topic_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    twin, _ = make_twin()
    hb = HeartbeatPublisher(twin, "s-twin")
    hb.start()
    hb.tick()
    hb.stop()
    assert twin.heartbeats >= 1 and twin.deadman_state()["state"] == "armed"


def test_deadman_echo_matches_the_contract_shape() -> None:
    twin, _ = make_twin()
    result = twin.echo(topic=DEADMAN_STATE_TOPIC, type=DEADMAN_STATE_TYPE, count=2, timeout=1.0)
    text = result["content"][0]["text"]
    samples = json.loads(text.split("\n", 1)[1])
    state = json.loads(samples[0]["data"])
    assert (
        len(samples) == 2 and set(state) == {"state", "gap_ms", "since", "trips"} and state["state"] == "idle"
    )


# -- pose integration -------------------------------------------------------------------------------------


def test_servo_to_twist_inverts_the_driver_model() -> None:
    cal = Calibration()
    for linear, angular in [(0.3, 0.0), (0.2, 0.5), (-0.3, 0.0), (0.1, -1.0)]:
        angle, throttle = twist_to_servo(linear, angular, cal)
        v, delta = servo_to_twist(angle, throttle, cal)
        assert v == pytest.approx(linear, abs=1e-6)
        expected_delta = math.atan2(cal.wheelbase_m * angular, abs(linear))
        if linear < 0:
            expected_delta = -expected_delta
        assert delta == pytest.approx(
            max(-cal.max_steering_rad, min(cal.max_steering_rad, expected_delta)), abs=1e-5
        )


def test_pose_straight_hop_is_fifteen_centimetres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin, clock = make_twin(deadman=False)
    arm(twin)
    drive(twin, 0.0, 0.3)
    for _ in range(25):
        twin.advance(clock.tick(0.02))  # 0.5 s at 50 Hz
    drive(twin, 0.0, 0.0)
    pose = twin.pose()
    assert pose["x"] == pytest.approx(0.15, abs=1e-6) and pose["y"] == pytest.approx(0.0, abs=1e-9)
    assert pose["yaw"] == 0.0 and pose["v"] == 0.0 and twin.odometer_m == pytest.approx(0.15, abs=1e-6)


def test_pose_turn_curves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    cal = Calibration()
    twin, clock = make_twin(deadman=False)
    arm(twin)
    angle, throttle = twist_to_servo(0.2, 0.5, cal)
    drive(twin, angle, throttle)
    for _ in range(100):
        twin.advance(clock.tick(0.02))  # 2 s
    pose = twin.pose()
    assert pose["y"] > 0.05 and 0 < pose["x"] < 0.4  # curved left
    assert pose["yaw"] == pytest.approx(0.5 * 2.0, rel=0.05)  # yaw rate 0.5 rad/s for 2 s
    assert twin.odometer_m == pytest.approx(0.4, abs=1e-6)  # 0.2 m/s for 2 s of arc
    assert math.hypot(pose["x"], pose["y"]) < 0.4  # the chord is shorter than the arc: it curved


def test_reverse_mirrors_and_full_lock_radius_matches_the_bicycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    cal = Calibration()
    twin, clock = make_twin(deadman=False)
    arm(twin)
    drive(twin, 1.0, -0.3)  # full right lock, reverse
    for _ in range(50):
        twin.advance(clock.tick(0.02))
    pose = twin.pose()
    assert pose["x"] < 0
    # arc radius at full lock = L / tan(lock); 0.3 m over the arc turns 0.3 / R rad
    radius = cal.wheelbase_m / math.tan(cal.max_steering_rad)
    assert abs(pose["yaw"]) == pytest.approx(0.3 / radius, rel=0.02)


# -- body events -----------------------------------------------------------------------------------------


def test_body_events_at_most_ten_hz_while_moving_then_one_at_rest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    log = EventLog(tmp_path, session="s-twin", portal_url="")
    twin, clock = make_twin(event_log=log, deadman=False)
    arm(twin)
    assert log.read("body") == []  # nothing while still
    drive(twin, 0.0, 0.3)
    for _ in range(100):
        twin.advance(clock.tick(0.01))  # 1 s at 100 Hz
    drive(twin, 0.0, 0.0)
    for _ in range(20):
        twin.advance(clock.tick(0.1))
    events = log.read("body")
    assert 9 <= len(events) <= 12, [e["payload"]["t_ms"] for e in events]
    payloads = [e["payload"] for e in events]
    assert all(set(p) == {"body", "x", "y", "yaw", "v", "t_ms"} and p["body"] == "twin" for p in payloads)
    assert payloads[-1]["v"] == 0.0 and payloads[-1]["x"] == pytest.approx(0.3, abs=1e-6)
    assert all(e["source"] == "twin" for e in events)
    assert payloads[0]["x"] < payloads[-2]["x"]  # it moved before it froze


def test_body_event_log_stamps_payloads_and_forwards_the_rest(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s-two", portal_url="")
    stamped = BodyEventLog(log, "twin")
    stamped.beat = "two_bodies"
    event = stamped.emit("stop", {"request_id": None, "cause": "operator", "latency_ms": 3})
    assert event["payload"] == {"request_id": None, "cause": "operator", "latency_ms": 3, "body": "twin"}
    assert event["beat"] == "two_bodies" and log.beat == "two_bodies"
    assert stamped.session == "s-two" and stamped.read("stop") == [event] and stamped.last("stop") == event
    pose = stamped.emit("body", {"body": "car", "x": 0.0})
    assert pose["payload"]["body"] == "car"  # an explicit label wins


# -- the driver drives it unchanged -------------------------------------------------------------------


def test_deepracer_robot_drives_the_twin_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    log = EventLog(tmp_path, session="s-twin", portal_url="")
    twin, clock = make_twin(event_log=log, deadman=False)
    robot = DeepRacerRobot(twin, event_log=log)
    result = robot.drive(linear=0.3, angular=0.0, duration=0.5)
    assert result["status"] == "success" and "DRIVE DONE" in result["content"][0]["text"]
    assert robot.enabled and twin.mode == 0 and twin.enabled
    sources = [row["source"] for row in twin.servo_history]
    assert sources[:2] == ["mode_change", "mode_change"] or sources[0] == "mode_change"
    assert twin.servo == {"angle": 0.0, "throttle": 0.0}  # the trailing zero pair landed
    assert twin.manual_drive_seen == 11  # 10 at 20 Hz plus the zero pair
    # realtime is off, so the whole stream landed in one instant: integrate it by hand
    relayed = [row for row in twin.servo_history if row["source"] == "relay"]
    assert relayed[0]["throttle"] == pytest.approx(0.3) and relayed[-1]["throttle"] == 0.0
    assert log.last("stop")["payload"]["cause"] == "trailing_zero"
    assert [e["type"] for e in log.read()].count("motion") == 2
    stop = robot.stop()
    assert stop["status"] == "success" and log.last("stop")["payload"]["cause"] == "operator"
    twin.advance(clock.tick(1.0))
    assert twin.pose()["v"] == 0.0


def test_driver_refused_without_pregrant_never_touches_the_twin(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s-twin", portal_url="")
    twin, _ = make_twin(event_log=log, deadman=False)
    robot = DeepRacerRobot(twin, event_log=log, handshake_retries=1)
    result = robot.drive(linear=0.3)
    assert result["status"] == "error" and "command surface" in result["content"][0]["text"]
    assert (
        twin.mode == 0 and twin.enabled is False and twin.manual_drive_seen == 0 and log.read("motion") == []
    )


def test_realtime_stream_takes_wall_time_and_the_ticker_integrates(monkeypatch: pytest.MonkeyPatch) -> None:
    """One real-time check with the thread, kept short: a 0.2 s stream moves ~6 cm and then holds."""
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", ARM)
    twin = TwinTransport(deadman=False)  # realtime, real clock
    try:
        arm(twin)
        drive(twin, 0.0, 0.3, count=4)  # 4 at 20 Hz = 0.15 s of sleeps
        twin.advance()
        moved = twin.pose()["x"]
        assert 0.03 <= moved <= 0.12, moved
        drive(twin, 0.0, 0.0)
        frozen = twin.pose()["x"]
        import time

        time.sleep(0.1)
        assert twin.pose()["x"] == frozen and twin.pose()["v"] == 0.0
    finally:
        twin.close()
