"""Contract smoke: the arming and drive contract against the fake car, with upstream alone.

Uses only `strands_robots.rosbridge.rosbridge_action` (not the Car team's driver, which may not
exist yet), so this suite is green the moment the harness is, and stays the floor every later
layer stands on: arm, hop at 20 Hz, trailing zero, and the deadman tripping within 400 ms when
the heartbeat stops. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
import pytest

from harness.fake_car import HEARTBEAT, MANUAL_DRIVE, FakeCar
from harness.stack import SimStack
from harness.testing import result_text

SERVO_TYPE = "deepracer_interfaces_pkg/ServoCtrlMsg"
HEADER_TYPE = "std_msgs/Header"
HOP_THROTTLE = 0.3
HOP_MESSAGES = 10  # 0.5 s at 20 Hz


def arm(rosbridge: Any) -> None:
    for service, type_, fields in (
        ("/ctrl_pkg/vehicle_state", "deepracer_interfaces_pkg/ActiveStateSrv", {"state": 0}),
        ("/ctrl_pkg/enable_state", "deepracer_interfaces_pkg/EnableStateSrv", {"is_active": True}),
    ):
        r = rosbridge("service_call", service=service, type=type_, fields=fields, timeout=25)
        assert r["status"] == "success", result_text(r)


def hop(rosbridge: Any, throttle: float, count: int) -> dict[str, Any]:
    try:
        return rosbridge(
            "publish",
            topic=MANUAL_DRIVE,
            type=SERVO_TYPE,
            fields={"angle": 0.0, "throttle": throttle},
            count=count,
            rate=20,
        )
    finally:
        # The car has no watchdog: the zero pair is the drive's responsibility, every time.
        z = rosbridge(
            "publish", topic=MANUAL_DRIVE, type=SERVO_TYPE, fields={"angle": 0.0, "throttle": 0.0}, count=1
        )
        assert z["status"] == "success", result_text(z)


def test_arm_hop_and_trailing_zero(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.set_calibration_profile("uninitialised")
    assert fake_car.state()["armed"] is False
    arm(rosbridge)
    assert fake_car.state()["armed"] is True

    r = hop(rosbridge, HOP_THROTTLE, HOP_MESSAGES)
    assert r["status"] == "success", result_text(r)

    relayed = fake_car.servo_history("relay")
    assert len(relayed) == HOP_MESSAGES + 1
    burst, zero = relayed[:HOP_MESSAGES], relayed[-1]
    assert all(row["throttle"] == pytest.approx(HOP_THROTTLE) and row["angle"] == 0.0 for row in burst)
    assert burst[-1]["ts"] - burst[0]["ts"] == pytest.approx(0.45, abs=0.15)  # 10 messages at 20 Hz
    assert zero == {**zero, "angle": 0.0, "throttle": 0.0, "source": "relay"}
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}
    assert fake_car.last_pwm()["throttle_ns"] == 1_446_000  # neutral, as measured on the car
    assert fake_car.state()["drops"] == {
        "not_armed": 0,
        "out_of_range": 0,
        "malformed": 0,
        "unknown_topic": 0,
    }


def test_hop_without_arming_never_reaches_the_servo(fake_car: FakeCar, rosbridge: Any) -> None:
    r = hop(rosbridge, HOP_THROTTLE, HOP_MESSAGES)
    assert r["status"] == "success"
    assert fake_car.servo_history("relay") == []
    assert fake_car.state()["drops"]["not_armed"] == HOP_MESSAGES + 1


def test_stream_without_heartbeat_trips_deadman_within_400ms(fake_car: FakeCar, rosbridge: Any) -> None:
    fake_car.set_deadman(True)
    arm(rosbridge)
    r = rosbridge("publish", topic=HEARTBEAT, type=HEADER_TYPE, fields={"frame_id": "s-smoke"}, count=1)
    assert r["status"] == "success"
    # A drive stream with no heartbeat beside it: 12 messages, 0.6 s.
    r = rosbridge(
        "publish",
        topic=MANUAL_DRIVE,
        type=SERVO_TYPE,
        fields={"angle": 0.0, "throttle": HOP_THROTTLE},
        count=12,
        rate=20,
    )
    assert r["status"] == "success"
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and fake_car.deadman_state()["state"] != "tripped":
        time.sleep(0.02)
    dm = fake_car.deadman_state()
    assert dm["state"] == "tripped" and dm["trips"] == 1
    assert dm["last_trip_gap_ms"] <= 400, dm
    assert fake_car.led() == {"red": 10_000_000, "green": 0, "blue": 0}
    assert len(fake_car.servo_history("deadman")) == 10
    time.sleep(0.6)  # let the burst and the stream both finish
    zeros = fake_car.servo_history("deadman")
    assert len(zeros) == 10 and zeros[-1]["ts"] - zeros[0]["ts"] == pytest.approx(0.45, abs=0.15)
    # The burst is ten zero pairs (CONTRACTS section 3), the same as the on-car node. A drive
    # stream that outlives the burst takes the servo back, on the real car too: the stream
    # must stop with its own zero pair, which is the drive's job, deadman or not.
    r = rosbridge(
        "publish", topic=MANUAL_DRIVE, type=SERVO_TYPE, fields={"angle": 0.0, "throttle": 0.0}, count=1
    )
    assert r["status"] == "success"
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}
    # The state is visible over the bridge too, as the laptop will read it.
    r = rosbridge("echo", topic="/deepracer_agent/deadman_state", count=1, timeout=3)
    assert r["status"] == "success", result_text(r)
    sample = json.loads(json.loads(result_text(r).split(":\n", 1)[1])[0]["data"])
    assert sample["state"] == "tripped" and set(sample) == {"state", "gap_ms", "since", "trips"}


def test_stream_without_heartbeat_and_no_deadman_latches(fake_car: FakeCar, rosbridge: Any) -> None:
    """The real car without the deadman installed: the last value stays. The zero pair is ours."""
    arm(rosbridge)
    rosbridge(
        "publish",
        topic=MANUAL_DRIVE,
        type=SERVO_TYPE,
        fields={"angle": 0.0, "throttle": HOP_THROTTLE},
        count=4,
        rate=20,
    )
    time.sleep(0.5)
    assert fake_car.deadman_state()["state"] == "idle"
    assert fake_car.last_servo()["throttle"] == pytest.approx(HOP_THROTTLE)


def test_restart_recovery_with_retries(fake_car: FakeCar, rosbridge: Any) -> None:
    """CONTRACTS §0: right after a stack restart the first service call can time out; retry."""
    fake_car.restart()
    outcomes = []
    for _ in range(3):
        r = rosbridge(
            "service_call",
            service="/ctrl_pkg/vehicle_state",
            type="deepracer_interfaces_pkg/ActiveStateSrv",
            fields={"state": 0},
            timeout=1,
        )
        outcomes.append(r["status"])
        if r["status"] == "success":
            break
    assert outcomes == ["error", "success"]


def test_console_and_decider_are_up(sim_stack: SimStack, fake_car: FakeCar) -> None:
    with httpx.Client(base_url=sim_stack.console.url, timeout=5) as c:
        csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', c.get("/login").text).group(1)
        assert c.post("/login", data={"password": "x"}, headers={"X-CSRFToken": csrf}).json() == {
            "redirect": "/home"
        }
        assert c.get("/api/get_battery_level").json()["battery_level"] == 10
        fake_car.set_battery(-1)
        assert c.get("/api/get_battery_level").json()["battery_level"] == -1
    with httpx.Client(base_url=sim_stack.decider.url, timeout=5) as d:
        assert d.get("/health").json()["status"] == "ok"
        fake_car.set_label("person_in_frame")
        body = d.post(
            "/v1/systemone",
            json={
                "state": "frame",
                "images": ["AAAA"],
                "questions": {
                    "frame": {
                        "type": "choice",
                        "instructions": "class?",
                        "criteria": dict.fromkeys(
                            ["clear", "obstacle_near", "person_in_frame", "off_surface", "unclear"]
                        ),
                    }
                },
            },
        ).json()
        assert body["answers"]["frame"]["choice"] == "person_in_frame"
