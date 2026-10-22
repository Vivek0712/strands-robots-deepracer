"""End to end through the Car team's driver against the fake car: handshake, hop, zero, heartbeat.

The real `DeepRacerRobot` over a real `RosbridgeTransport` dialled at the fake car on 9091,
with upstream's command gate pre-granted for the test process. What the fake car records is
what the wire carried: the arming pair in order, ten relayed ServoCtrlMsg for a 0.5 s hop, the
trailing zero pair, the heartbeat that keeps the emulated deadman armed. Skips if the driver
is not importable. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness.fake_car import FakeCar
from harness.testing import result_text

pytest.importorskip("deepracer_agent.driver", reason="Car team's deepracer_agent.driver not landed yet")

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import DeepRacerRobot
from deepracer_agent.tools import battery_level
from deepracer_agent.transport import HeartbeatPublisher, RosbridgeTransport


@pytest.fixture
def transport(fake_car: FakeCar) -> RosbridgeTransport:
    return RosbridgeTransport(
        os.environ["DEEPRACER_HOST"], int(os.environ["DEEPRACER_ROSBRIDGE_PORT"]), timeout=5.0
    )


@pytest.fixture
def robot(transport: RosbridgeTransport, fake_car: FakeCar, run_dir: Path) -> Iterator[DeepRacerRobot]:
    bot = DeepRacerRobot(transport, calibration=Calibration(), handshake_timeout_s=2.0)
    yield bot
    bot.stop()


def settle(fake_car: FakeCar, quiet_s: float = 0.1, timeout_s: float = 1.0) -> None:
    """Wait until the fake car's servo history has stopped growing: publishes are asynchronous."""
    deadline = time.monotonic() + timeout_s
    last = len(fake_car.servo_history())
    quiet_since = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.02)
        n = len(fake_car.servo_history())
        if n != last:
            last, quiet_since = n, time.monotonic()
        elif time.monotonic() - quiet_since >= quiet_s:
            return


def moving(fake_car: FakeCar) -> list[dict[str, Any]]:
    settle(fake_car)
    return [r for r in fake_car.servo_history("relay") if r["throttle"] != 0.0 or r["angle"] != 0.0]


def test_enable_runs_the_arming_pair_in_order(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    r = robot.enable()
    assert r["status"] == "success", result_text(r)
    s = fake_car.state()
    assert s["mode"] == 0 and s["enabled"] is True
    calls = [c["service"] for c in fake_car.service_calls()]
    assert calls.index("/ctrl_pkg/vehicle_state") < calls.index("/ctrl_pkg/enable_state")
    assert robot.last_handshake == {"attempts": 1, "mode": 0, "enabled": True}


def test_hop_relays_ten_messages_and_ends_with_zero(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    fake_car.set_calibration_profile("uninitialised")
    r = robot.drive(linear=0.3, angular=0.0, duration=0.5)
    assert r["status"] == "success", result_text(r)
    assert fake_car.state()["armed"] is True, "drive runs the handshake first"
    burst = moving(fake_car)
    assert len(burst) == 10, "0.5 s at 20 Hz"
    assert all(row["throttle"] == pytest.approx(0.3, abs=1e-6) and row["angle"] == 0.0 for row in burst)
    assert fake_car.servo_history("relay")[-1]["throttle"] == 0.0, "trailing zero pair"
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}
    assert fake_car.last_pwm()["throttle_ns"] == 1_446_000
    assert fake_car.state()["drops"]["out_of_range"] == 0


def test_turn_steers_and_backs_up_mirrored(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    robot.drive(linear=0.2, angular=0.5, duration=0.25)
    left = moving(fake_car)
    assert left and all(row["angle"] > 0 for row in left)
    robot.drive(linear=-0.2, angular=0.5, duration=0.25)
    back = moving(fake_car)[len(left) :]
    assert back and all(row["angle"] < 0 and row["throttle"] < 0 for row in back)


def test_yaw_at_rest_is_refused_before_any_publish(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    r = robot.drive(linear=0.0, angular=0.5, duration=0.5)
    assert r["status"] == "error"
    assert "cannot yaw at rest" in result_text(r)
    assert moving(fake_car) == []


def test_over_cap_is_refused(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    r = robot.drive(linear=0.3, angular=0.0, duration=3.0)
    assert r["status"] == "error", result_text(r)
    assert moving(fake_car) == []


def test_stop_zeroes_even_when_not_moving(robot: DeepRacerRobot, fake_car: FakeCar) -> None:
    robot.enable()
    r = robot.stop()
    assert r["status"] == "success", result_text(r)
    assert fake_car.last_servo() == {"angle": 0.0, "throttle": 0.0}


def test_battery_tool_reads_the_car(transport: RosbridgeTransport, fake_car: FakeCar) -> None:
    fake_car.set_battery(-1)
    assert battery_level(transport) == {"level": -1, "ok": False}
    fake_car.set_battery(9)
    assert battery_level(transport) == {"level": 9, "ok": True}


def test_handshake_survives_restart_timeout(
    transport: RosbridgeTransport, fake_car: FakeCar, run_dir: Path
) -> None:
    bot = DeepRacerRobot(transport, calibration=Calibration(), handshake_timeout_s=1.0)
    fake_car.restart()
    t0 = time.monotonic()
    r = bot.enable()
    assert r["status"] == "success", result_text(r)
    assert 0.9 <= time.monotonic() - t0 < 5.0
    assert bot.last_handshake["attempts"] == 2
    assert fake_car.state()["armed"] is True and fake_car.state()["restart_timeouts"] == 1
    bot.stop()


def test_heartbeat_keeps_the_deadman_armed_and_its_stop_trips_it(
    transport: RosbridgeTransport, fake_car: FakeCar
) -> None:
    fake_car.set_deadman(True)
    hb = HeartbeatPublisher(transport, "s-e2e", idle_hz=10.0)
    hb.start()
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and fake_car.deadman_state()["state"] != "armed":
            time.sleep(0.05)
        assert fake_car.deadman_state()["state"] == "armed"
        assert fake_car.heartbeat_count() >= 1 and fake_car.state()["heartbeat_frame_id"] == "s-e2e"
    finally:
        hb.stop()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and fake_car.deadman_state()["state"] != "tripped":
        time.sleep(0.02)
    dm = fake_car.deadman_state()
    assert dm["state"] == "tripped" and dm["last_trip_gap_ms"] <= 400
