"""The Two Bodies beat against two fake runtimes: one line to both, stop all halts both, labels differ."""

from __future__ import annotations

import asyncio
import importlib

import pytest

import beats
from beats import BEAT_NAMES, BOOTH_BEAT_NAMES, RECORDED_BEAT_NAMES, BeatContext, load_beat
from beats.two_bodies import body_of
from deepracer_agent.gate import LocalEventLog
from deepracer_agent.twin import BodyEventLog
from tests.unit.test_beats_dryrun import FakeRuntime, FakeSim


class FakeCarRuntime(FakeRuntime):
    """The dry-run runtime plus the ``stop`` event the real ``stop_all`` emits through the driver."""

    async def stop_all(self):
        await super().stop_all()
        self.events.emit("stop", {"request_id": None, "cause": "operator", "latency_ms": 4})


class FakeTwinTransport:
    def __init__(self) -> None:
        self.x = 0.0
        self.v = 0.0

    def pose(self) -> dict[str, float]:
        return {"x": round(self.x, 4), "y": 0.0, "yaw": 0.0, "v": self.v}


class FakeTwinRuntime(FakeCarRuntime):
    """Drives a pose forward at 0.3 m/s while a hop is in flight and emits ``body`` samples."""

    def __init__(self, events, sim: FakeSim) -> None:
        super().__init__(events, sim)
        self.transport = FakeTwinTransport()

    async def _drive(self, rid, args, beat):
        self.driving = True
        self.transport.v = 0.3
        self.events.emit(
            "motion",
            {
                "request_id": rid,
                "state": "start",
                "angle": 0.0,
                "throttle": 0.3,
                "duration_s": 0.5,
                "messages": 0,
            },
            beat=beat,
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 1.0
        last_emit = 0.0
        while self.driving and loop.time() < deadline:
            self.transport.x += 0.3 * 0.01
            if loop.time() - last_emit >= 0.1:
                last_emit = loop.time()
                self.events.emit("body", {"body": "twin", **self.transport.pose(), "t_ms": 1}, beat=beat)
            await asyncio.sleep(0.01)
        self.transport.v = 0.0
        self.events.emit("body", {"body": "twin", **self.transport.pose(), "t_ms": 2}, beat=beat)

    async def stop_all(self):
        self.transport.v = 0.0
        await super().stop_all()


@pytest.fixture
def two_bodies_ctx(tmp_path):
    log = LocalEventLog(tmp_path / "two_bodies", session="s-beat", beat="two_bodies")
    sim = FakeSim()
    car = FakeCarRuntime(log, sim)
    twin = FakeTwinRuntime(BodyEventLog(log, "twin"), sim)
    lines: list[str] = []
    ctx = BeatContext("two_bodies", runtime=car, events=log, body="sim", sim=sim, text=True, out=lines.append)
    ctx.twin = twin
    return ctx, car, twin, lines


def test_two_bodies_is_registered_as_a_recorded_beat_not_a_live_one():
    assert RECORDED_BEAT_NAMES == ("two_bodies",)
    assert "two_bodies" not in BEAT_NAMES and "two_bodies" not in BOOTH_BEAT_NAMES
    assert len(BEAT_NAMES) == 7
    module = importlib.import_module("beats.two_bodies")
    assert callable(module.run) and asyncio.iscoroutinefunction(module.run)
    assert module.__doc__ and "decider explains" in module.__doc__
    assert callable(load_beat("two_bodies"))
    with pytest.raises(beats.BeatError):
        load_beat("pit_stop")


async def test_two_bodies_passes_against_two_fake_runtimes(two_bodies_ctx):
    ctx, car, twin, lines = two_bodies_ctx
    result = await load_beat("two_bodies")(ctx)
    summary = result.summary()
    assert result.passed, summary
    assert summary.startswith("beat two_bodies on sim: PASS")
    assert car.n == 1 and twin.n == 1  # one line each, the same words
    assert car.stop_calls == 1 and twin.stop_calls == 1
    assert not car.driving and not twin.driving
    assert result.latencies["stop_all_sim_ms"] <= 1000 and result.latencies["stop_all_twin_ms"] <= 1000
    assert result.latencies["twin_travel_cm"] >= 2.0
    assert any(line == "you> Hop forward twenty centimetres.  (to both bodies)" for line in lines)
    assert any(line.startswith("rover> One word stopped two bodies") for line in lines)
    events = ctx.events.read()
    labels = {body_of(e, "sim") for e in events}
    assert labels == {"sim", "twin"}
    twin_motion = [e for e in events if e["type"] == "motion" and e["payload"].get("body") == "twin"]
    car_motion = [e for e in events if e["type"] == "motion" and "body" not in e["payload"]]
    assert twin_motion and car_motion
    poses = [e["payload"] for e in events if e["type"] == "body" and e["payload"].get("body") == "twin"]
    assert poses and poses[-1]["v"] == 0.0 and poses[-1]["x"] > poses[0]["x"]
    assert sim_calls_are_the_clear_frame(ctx)


def sim_calls_are_the_clear_frame(ctx) -> bool:
    return ctx.sim.calls[:1] == ["frame=clear"] and "deadman=True" in ctx.sim.calls


async def test_two_bodies_fails_honestly_when_the_twin_never_moves(two_bodies_ctx):
    ctx, _car, twin, _lines = two_bodies_ctx

    async def frozen_drive(rid, args, beat):
        twin.driving = True
        twin.events.emit(
            "motion",
            {
                "request_id": rid,
                "state": "start",
                "angle": 0.0,
                "throttle": 0.0,
                "duration_s": 0.5,
                "messages": 0,
            },
            beat=beat,
        )
        while twin.driving:
            await asyncio.sleep(0.01)

    twin._drive = frozen_drive
    result = await load_beat("two_bodies")(ctx)
    failed = [s.label for s in result.steps if not s.ok]
    assert failed == ["twin pose moved then froze"]
    assert twin.stop_calls == 1


def test_body_of_defaults_to_the_car_body_label():
    assert body_of({"payload": {"body": "twin"}}, "car") == "twin"
    assert body_of({"payload": {"cause": "operator"}}, "car") == "car"
    assert body_of({"payload": {"body": ""}}, "sim") == "sim"
    assert body_of({}, "sim") == "sim"
