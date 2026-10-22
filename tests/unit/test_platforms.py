"""platforms: the MobilePlatform protocol, the fake car's caps and pose, the DeepRacer adapter."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import DeepRacerRobot
from deepracer_agent.events import EventLog
from deepracer_agent.gate import LocalEventLog
from deepracer_agent.platforms import TINY_JPEG, DeepRacerPlatform, DriveStop, MobilePlatform, SimPlatform
from deepracer_agent.transport import HeartbeatPublisher
from tests.unit._car_fakes import make_transport

CAL = Calibration()


def test_sim_platform_satisfies_the_protocol_and_the_real_driver_the_drive_stop_half(tmp_path: Path) -> None:
    sim = SimPlatform(CAL)
    assert isinstance(sim, MobilePlatform) and isinstance(sim, DriveStop)
    transport, _action, _topics = make_transport()
    robot = DeepRacerRobot(
        transport,
        calibration=CAL,
        event_log=EventLog(tmp_path, session="s", portal_url=""),
        heartbeat=HeartbeatPublisher(transport, "s"),
    )
    assert isinstance(robot, DriveStop) and not isinstance(robot, MobilePlatform)
    platform = DeepRacerPlatform(robot)
    assert isinstance(platform, MobilePlatform) and platform.name == "deepracer"


@pytest.mark.parametrize(
    ("linear", "angular", "duration", "fragment"),
    [
        (0.0, 0.5, 0.5, "cannot yaw at rest"),
        (0.4, 0.0, 0.5, "exceeds the cap"),
        (0.3, 0.0, 2.5, "exceeds max_duration"),
        (0.3, 0.0, 0.0, "must be positive"),
        (float("nan"), 0.0, 0.5, "finite number"),
        ("fast", 0.0, 0.5, "finite number"),
        (True, 0.0, 0.5, "finite number"),
    ],
)
def test_sim_platform_refusal_table(linear, angular, duration, fragment) -> None:
    sim = SimPlatform(CAL)
    result = sim.drive(linear, angular, duration)
    assert result["status"] == "error" and fragment in result["content"][0]["text"]
    assert sim.commands == [] and sim.pose == (0.0, 0.0, 0.0)


def test_sim_platform_integrates_the_bicycle_model(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="s-sim")
    sim = SimPlatform(CAL, event_log=log)
    assert sim.drive(0.3, 0.0, 2.0)["status"] == "success"
    assert sim.pose[0] == pytest.approx(0.6) and sim.pose[1] == pytest.approx(0.0)
    radius = 0.3
    quarter = (math.pi / 2) * radius / 0.25
    for _ in range(2):
        sim.drive(0.25, 0.25 / radius, quarter)
    assert sim.heading_deg == pytest.approx(180.0, abs=0.5)
    assert sim.pose[1] == pytest.approx(2 * radius, abs=0.02)  # a half circle to the left
    assert sim.drive()["status"] == "success"  # default hop
    assert sim.commands[-1]["duration"] == CAL.hop_s
    sim.stop(cause="operator")
    types = [e["type"] for e in log.read()]
    assert types.count("motion") == 8 and types[-1] == "stop" and sim.stops == ["operator"]


def test_sim_platform_frame_battery_preflight() -> None:
    sim = SimPlatform(CAL, battery=8)
    assert (
        sim.capture_frame() == TINY_JPEG
        and TINY_JPEG.startswith(b"\xff\xd8")
        and TINY_JPEG.endswith(b"\xff\xd9")
    )
    assert sim.battery() == {"level": 8, "ok": True}
    assert sim.preflight()["go"] is True
    dead = SimPlatform(CAL, battery=-1, frame=None)
    pre = dead.preflight()
    assert pre["go"] is False and len(pre["reasons"]) == 2 and dead.battery()["ok"] is False
    assert dead.capture_frame() is None


def test_sim_platform_fail_after() -> None:
    sim = SimPlatform(CAL, fail_after=1)
    assert sim.drive(0.3, 0.0, 0.5)["status"] == "success"
    failed = sim.drive(0.3, 0.0, 0.5)
    assert failed["status"] == "error" and sim.commands[-1]["failed"] is True


def test_deepracer_platform_composes_driver_console_and_preflight(tmp_path: Path) -> None:
    calls: list[str] = []

    class Driver:
        transport = object()

        def drive(self, linear=0.0, angular=0.0, duration=None, **kw):
            calls.append(f"drive {linear} {angular} {duration}")
            return {"status": "success"}

        def stop(self, tool_context=None, *, cause="operator"):
            calls.append(f"stop {cause}")
            return {"status": "success"}

    class Console:
        def capture_frame(self):
            return TINY_JPEG

    class Pre:
        def run(self):
            return {"go": True, "reasons": []}

    class Runtime:
        driver = Driver()
        console = Console()
        _preflight = Pre()

    platform = DeepRacerPlatform.from_runtime(Runtime())
    assert isinstance(platform, MobilePlatform)
    platform.drive(0.3, 0.0, 0.5)
    platform.stop(cause="deny")
    assert calls == ["drive 0.3 0.0 0.5", "stop deny"]
    assert platform.capture_frame() == TINY_JPEG and platform.preflight()["go"] is True
    assert DeepRacerPlatform(Driver()).preflight()["go"] is False
    assert DeepRacerPlatform(Driver()).capture_frame() is None
