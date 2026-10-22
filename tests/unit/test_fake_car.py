"""Protocol-level tests of the fake car through roslibpy and upstream's `rosbridge_action`.

Every test talks to the fake car the way the laptop will: over the rosbridge WebSocket, with
the real command gate in front of `publish` and `service_call`.
"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

import pytest
import roslibpy
from websockets.sync.client import connect

from harness.fake_car import CALIBRATION_PROFILES, HEARTBEAT, MANUAL_DRIVE, SERVO_MSG, FakeCar
from harness.testing import result_text

SERVO_TYPE = "deepracer_interfaces_pkg/ServoCtrlMsg"
VEHICLE_STATE = ("/ctrl_pkg/vehicle_state", "deepracer_interfaces_pkg/ActiveStateSrv")
ENABLE_STATE = ("/ctrl_pkg/enable_state", "deepracer_interfaces_pkg/EnableStateSrv")


def arm(rosbridge: Any) -> None:
    r = rosbridge(
        "service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 0}, timeout=5
    )
    assert r["status"] == "success", result_text(r)
    r = rosbridge(
        "service_call", service=ENABLE_STATE[0], type=ENABLE_STATE[1], fields={"is_active": True}, timeout=5
    )
    assert r["status"] == "success", result_text(r)


def servo(
    rosbridge: Any, angle: float, throttle: float, count: int = 1, rate: float = 20.0
) -> dict[str, Any]:
    return rosbridge(
        "publish",
        topic=MANUAL_DRIVE,
        type=SERVO_TYPE,
        fields={"angle": angle, "throttle": throttle},
        count=count,
        rate=rate,
    )


# --------------------------------------------------------------------- graph


def test_status_connects(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge("status", timeout=5)
    assert r["status"] == "success"
    assert "connected to ws://127.0.0.1:9091" in result_text(r)


def test_list_topics_reports_ros2_types(fake_car: FakeCar, rosbridge: Any) -> None:
    text = result_text(rosbridge("list_topics", timeout=5))
    assert f"{MANUAL_DRIVE} [deepracer_interfaces_pkg/msg/ServoCtrlMsg]" in text
    assert f"{SERVO_MSG} [deepracer_interfaces_pkg/msg/ServoCtrlMsg]" in text
    assert f"{HEARTBEAT} [std_msgs/msg/Header]" in text
    assert "/deepracer_agent/deadman_state [std_msgs/msg/String]" in text


def test_list_services_includes_ctrl_and_rosapi(fake_car: FakeCar, rosbridge: Any) -> None:
    text = result_text(rosbridge("list_services", timeout=5))
    for name in (
        "/ctrl_pkg/vehicle_state",
        "/ctrl_pkg/enable_state",
        "/i2c_pkg/battery_level",
        "/servo_pkg/set_led_state",
        "/servo_pkg/get_calibration",
        "/rosapi/topics",
        "/rosapi/topic_type",
        "/rosapi/service_type",
    ):
        assert name in text


def test_rosapi_service_type_and_topics_for_type(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge(
        "service_call",
        service="/rosapi/service_type",
        type="rosapi/ServiceType",
        fields={"service": "/ctrl_pkg/vehicle_state"},
        timeout=5,
    )
    assert "deepracer_interfaces_pkg/srv/ActiveStateSrv" in result_text(r)
    r = rosbridge(
        "service_call",
        service="/rosapi/topics_for_type",
        type="rosapi/TopicsForType",
        fields={"type": SERVO_TYPE},
        timeout=5,
    )
    assert MANUAL_DRIVE in result_text(r) and SERVO_MSG in result_text(r)


# -------------------------------------------------------------------- arming


def test_boots_in_manual_and_disabled(fake_car: FakeCar) -> None:
    s = fake_car.state()
    assert s["mode"] == 0 and s["enabled"] is False and s["armed"] is False


def test_publish_before_arm_is_dropped(fake_car: FakeCar, rosbridge: Any) -> None:
    r = servo(rosbridge, 0.0, 0.3, count=3)
    assert r["status"] == "success"  # the bridge accepts it; the ctrl node does not relay it
    assert fake_car.servo_history("relay") == []
    assert fake_car.state()["drops"]["not_armed"] == 3
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}


def test_arm_then_relay_at_20hz(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.set_calibration_profile("uninitialised")
    arm(rosbridge)
    assert fake_car.state()["armed"] is True
    t0 = time.monotonic()
    r = servo(rosbridge, 0.0, 0.3, count=10, rate=20.0)
    assert r["status"] == "success"
    relayed = fake_car.servo_history("relay")
    assert len(relayed) == 10
    assert all(row["throttle"] == pytest.approx(0.3) and row["angle"] == 0.0 for row in relayed)
    assert relayed[-1]["ts"] - relayed[0]["ts"] == pytest.approx(0.45, abs=0.15)
    assert time.monotonic() - t0 < 2.0
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": pytest.approx(0.3)}
    # Measured on the car: throttle 0.3 -> 1405500 ns from neutral 1446000 ns.
    assert fake_car.last_pwm() == {"throttle_ns": 1405500, "steering_ns": 1450000}


def test_mode_change_disables_and_zeroes(fake_car: FakeCar, rosbridge: Any) -> None:
    arm(rosbridge)
    servo(rosbridge, 0.0, 0.3)
    r = rosbridge(
        "service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 1}, timeout=5
    )
    assert r["status"] == "success"
    s = fake_car.state()
    assert s["mode"] == 1 and s["enabled"] is False
    assert fake_car.servo_history("mode_change")[-1]["throttle"] == 0.0
    servo(rosbridge, 0.0, 0.3)
    assert fake_car.last_servo()["throttle"] == 0.0
    assert fake_car.state()["drops"]["not_armed"] >= 1


def test_invalid_state_is_an_error_response(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge(
        "service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 7}, timeout=5
    )
    assert r["status"] == "success" and '"error": 1' in result_text(r)
    assert fake_car.state()["mode"] == 0


# ------------------------------------------------------------- refusal table


@pytest.mark.parametrize(
    ("mode", "enabled", "msg", "reason"),
    [
        (0, True, {"angle": 1.5, "throttle": 0.0}, "angle 1.5 out of range [-1, 1]"),
        (0, True, {"angle": 0.0, "throttle": -2}, "throttle -2 out of range [-1, 1]"),
        (0, True, {"angle": "left", "throttle": 0.0}, "angle is not a number"),
        (0, True, {"angle": True, "throttle": 0.0}, "angle is not a number"),
        (0, True, {"angle": 0.0}, "throttle missing from ServoCtrlMsg"),
        (0, True, {"angle": math.nan, "throttle": 0.0}, "angle is not finite"),
        (0, True, {"angle": 0.0, "throttle": math.inf}, "throttle is not finite"),
        (
            1,
            True,
            {"angle": 0.0, "throttle": 0.3},
            "vehicle_state is 1, not 0 (manual); ctrl node does not relay",
        ),
        (
            2,
            True,
            {"angle": 0.0, "throttle": 0.3},
            "vehicle_state is 2, not 0 (manual); ctrl node does not relay",
        ),
        (
            0,
            False,
            {"angle": 0.0, "throttle": 0.3},
            "enable_state is_active is false; ctrl node does not relay",
        ),
    ],
)
def test_manual_drive_refusals(
    fake_car: FakeCar, mode: int, enabled: bool, msg: dict[str, Any], reason: str
) -> None:
    fake_car.mode = mode
    fake_car.enabled = enabled
    assert fake_car.handle_manual_drive(msg) == reason
    assert fake_car.servo_history("relay") == []


def test_manual_drive_accepts_bounds(fake_car: FakeCar) -> None:
    fake_car.mode, fake_car.enabled = 0, True
    assert fake_car.handle_manual_drive({"angle": -1.0, "throttle": 1.0}) is None
    assert fake_car.handle_manual_drive({"angle": 1, "throttle": -1}) is None
    assert len(fake_car.servo_history("relay")) == 2


def test_out_of_range_dropped_over_protocol(fake_car: FakeCar, rosbridge: Any) -> None:
    arm(rosbridge)
    servo(rosbridge, 0.0, 0.3)
    servo(rosbridge, 0.0, 1.7)
    assert fake_car.last_servo()["throttle"] == pytest.approx(0.3)
    assert fake_car.state()["drops"]["out_of_range"] == 1


# ------------------------------------------------------------- no watchdog


def test_last_value_latches_without_watchdog(fake_car: FakeCar, rosbridge: Any) -> None:
    arm(rosbridge)
    servo(rosbridge, 0.1, 0.3, count=3)
    time.sleep(0.5)
    assert fake_car.last_servo() == {"angle": pytest.approx(0.1), "throttle": pytest.approx(0.3)}
    assert fake_car.deadman_state()["state"] == "idle"
    servo(rosbridge, 0.0, 0.0)
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}


# --------------------------------------------------------------------- echo


def test_echo_servo_msg_sees_relayed_messages(
    fake_car: FakeCar, rosbridge: Any, ros_client: roslibpy.Ros
) -> None:
    arm(rosbridge)
    pub = roslibpy.Topic(ros_client, MANUAL_DRIVE, SERVO_TYPE)
    pub.advertise()

    def burst() -> None:
        time.sleep(0.3)
        for _ in range(5):
            pub.publish(roslibpy.Message({"angle": 0.2, "throttle": 0.25}))
            time.sleep(0.05)

    worker = threading.Thread(target=burst)
    worker.start()
    try:
        r = rosbridge("echo", topic=SERVO_MSG, count=2, timeout=5)
    finally:
        worker.join()
        pub.unadvertise()
    assert r["status"] == "success", result_text(r)
    text = result_text(r)
    assert "deepracer_interfaces_pkg/msg/ServoCtrlMsg" in text
    samples = json.loads(text.split(":\n", 1)[1].split("\n(no messages")[0])
    assert len(samples) == 2 and samples[0]["throttle"] == pytest.approx(0.25)


# ------------------------------------------------------------------ services


def test_service_response_carries_request_id(fake_car: FakeCar) -> None:
    with connect(fake_car.url) as ws:
        ws.send(
            json.dumps(
                {
                    "op": "call_service",
                    "id": "call_service:/i2c_pkg/battery_level:7",
                    "service": "/i2c_pkg/battery_level",
                    "args": {},
                }
            )
        )
        reply = json.loads(ws.recv(timeout=5))
    assert reply == {
        "op": "service_response",
        "service": "/i2c_pkg/battery_level",
        "id": "call_service:/i2c_pkg/battery_level:7",
        "values": {"level": 10},
        "result": True,
    }


def test_unknown_service_is_a_result_false(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge("service_call", service="/nope", type="x/Y", fields={}, timeout=3)
    assert r["status"] == "error"
    assert "Service /nope does not exist" in result_text(r)


def test_restart_times_out_first_call_only(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.restart()
    t0 = time.monotonic()
    r = rosbridge(
        "service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 0}, timeout=1
    )
    assert r["status"] == "error" and "No service response received" in result_text(r)
    assert 0.9 <= time.monotonic() - t0 < 3.0
    r = rosbridge(
        "service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 0}, timeout=5
    )
    assert r["status"] == "success"
    assert fake_car.state()["restart_timeouts"] == 1 and fake_car.state()["restart_pending"] is False


def test_battery_service_and_http_control(fake_car: FakeCar, rosbridge: Any) -> None:
    import urllib.request

    with urllib.request.urlopen("http://127.0.0.1:8092/battery?level=4", timeout=3) as resp:
        assert json.loads(resp.read()) == {"ok": True, "battery": 4}
    r = rosbridge(
        "service_call",
        service="/i2c_pkg/battery_level",
        type="deepracer_interfaces_pkg/BatteryLevelSrv",
        fields={},
        timeout=5,
    )
    assert '"level": 4' in result_text(r)
    with urllib.request.urlopen("http://127.0.0.1:8092/state", timeout=3) as resp:
        state = json.loads(resp.read())
    assert state["battery"] == 4 and state["mode"] == 0
    with urllib.request.urlopen("http://127.0.0.1:8092/frame?label=sign", timeout=3) as resp:
        assert json.loads(resp.read())["label"] == "sign"
    assert fake_car.state()["label"] == "sign"
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen("http://127.0.0.1:8092/frame?label=cat", timeout=3)


def test_led_service_records_colour(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge(
        "service_call",
        service="/servo_pkg/set_led_state",
        type="deepracer_interfaces_pkg/SetLedCtrlSrv",
        fields={"red": 0, "green": 10_000_000, "blue": 0},
        timeout=5,
    )
    assert '"error": 0' in result_text(r)
    assert fake_car.led() == {"red": 0, "green": 10_000_000, "blue": 0}
    r = rosbridge(
        "service_call",
        service="/servo_pkg/set_led_state",
        type="deepracer_interfaces_pkg/SetLedCtrlSrv",
        fields={"red": 99_999_999, "green": 0, "blue": 0},
        timeout=5,
    )
    assert '"error": 1' in result_text(r)
    assert fake_car.led()["green"] == 10_000_000


@pytest.mark.parametrize("profile", sorted(CALIBRATION_PROFILES))
def test_calibration_profiles_switch(fake_car: FakeCar, rosbridge: Any, profile: str) -> None:
    fake_car.set_calibration_profile(profile)
    r = rosbridge(
        "service_call",
        service="/servo_pkg/get_calibration",
        type="deepracer_interfaces_pkg/GetCalibrationSrv",
        fields={"cal_type": 1},
        timeout=5,
    )
    body = json.loads(result_text(r).split("response:\n", 1)[1])
    expected = CALIBRATION_PROFILES[profile][1]
    assert body == {**expected, "error": 0}
    assert body["mid"] == 1_446_000


def test_set_calibration_is_refused(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge(
        "service_call",
        service="/servo_pkg/set_calibration",
        type="deepracer_interfaces_pkg/SetCalibrationSrv",
        fields={"cal_type": 1, "max": 1, "mid": 1, "min": 1, "polarity": 1},
        timeout=5,
    )
    assert '"error": 1' in result_text(r)
    assert fake_car.service_calls()[-1]["refused"]


# ----------------------------------------------------------------- heartbeat


def test_heartbeats_are_counted(fake_car: FakeCar, rosbridge: Any) -> None:
    r = rosbridge(
        "publish",
        topic=HEARTBEAT,
        type="std_msgs/Header",
        fields={"stamp": {"sec": 1, "nanosec": 0}, "frame_id": "s-test"},
        count=4,
        rate=20,
    )
    assert r["status"] == "success"
    assert fake_car.heartbeat_count() == 4
    assert fake_car.state()["heartbeat_frame_id"] == "s-test"


def test_deadman_absent_leaves_value_latched(fake_car: FakeCar, rosbridge: Any) -> None:
    arm(rosbridge)
    rosbridge("publish", topic=HEARTBEAT, type="std_msgs/Header", fields={"frame_id": "s"}, count=1)
    servo(rosbridge, 0.0, 0.3, count=4)
    time.sleep(0.5)
    dm = fake_car.deadman_state()
    assert dm["enabled"] is False and dm["state"] == "idle" and dm["trips"] == 0
    assert fake_car.last_servo()["throttle"] == pytest.approx(0.3)


def test_deadman_present_trips_after_gap(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.set_deadman(True)
    arm(rosbridge)
    rosbridge("publish", topic=HEARTBEAT, type="std_msgs/Header", fields={"frame_id": "s"}, count=1)
    servo(rosbridge, 0.0, 0.3, count=2)
    time.sleep(0.6)
    dm = fake_car.deadman_state()
    assert dm["state"] == "tripped" and dm["trips"] == 1
    assert dm["last_trip_gap_ms"] <= 400
    assert fake_car.led() == {"red": 10_000_000, "green": 0, "blue": 0}
    assert len(fake_car.servo_history("deadman")) == 10
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}


def test_deadman_rearms_after_heartbeats_resume(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.set_deadman(True)
    rosbridge("publish", topic=HEARTBEAT, type="std_msgs/Header", fields={"frame_id": "s"}, count=1)
    time.sleep(0.5)
    assert fake_car.deadman_state()["state"] == "tripped"
    rosbridge("publish", topic=HEARTBEAT, type="std_msgs/Header", fields={"frame_id": "s"}, count=30, rate=20)
    assert fake_car.deadman_state()["state"] == "armed"


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def ros_client(sim_stack: Any) -> Any:
    ros = roslibpy.Ros(sim_stack.host, sim_stack.car.port)
    ros.run(timeout=5)
    yield ros
    ros.close()
