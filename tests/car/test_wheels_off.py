"""Layer 2: the real car on a stand, wheels off the ground. `make wheels-off` runs this.

Reads `~/.config/deepracer/env` (`DEEPRACER_HOST`, SSH user/key) through the Makefile; never
the repo. `tests/conftest.py` keeps the sim defaults out of this layer (body `car`, rosbridge
9090). The three command surfaces are pre-granted for this headless run via
`STRANDS_ROS2_COMMAND_ALLOW` (set in conftest, documented here). Every motion is a throttle of
at most 0.3 (0.5 is the session cap) for at most 2 s, and every test ends with a zero pair.

What is measured, with a 100 Hz sysfs sampler running on the car (`pwm_sampler.py`): the PWM
the hop produces (direction cannot be asserted remotely, so it is recorded), the stop latency
from `stop_deepracer()` to the zero pair on `/ctrl_pkg/servo_msg` and to the PWM back at
neutral, the deadman trip latency from the heartbeat cut to PWM neutral, and the barge-in path
through `AgentRuntime.stop_all`. Numbers land in `runs/wheels-off-<date>/measurements.jsonl`
and are copied into `docs/results/`. Keep a thumb on the power switch; physics stops the car,
the decider explains.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.wheels_off

HOST = os.environ.get("DEEPRACER_HOST")
PORT = int(os.environ.get("DEEPRACER_ROSBRIDGE_PORT", "9090"))
if not HOST or HOST == "127.0.0.1":
    pytest.skip(
        "DEEPRACER_HOST not set: source ~/.config/deepracer/env (make wheels-off)", allow_module_level=True
    )

os.environ.setdefault("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")
os.environ.setdefault("DEEPRACER_BODY", "car")

from strands_robots._command_gate import gate_command  # noqa: E402
from strands_robots.rosbridge import GATE_TOOL, never_gated, rosbridge_action  # noqa: E402

from deepracer_agent.driver import DeepRacerRobot  # noqa: E402
from deepracer_agent.events import EventLog  # noqa: E402
from deepracer_agent.runtime import AgentRuntime, ApprovalBroker  # noqa: E402
from deepracer_agent.tools import read_pwm_outputs  # noqa: E402
from deepracer_agent.transport import (  # noqa: E402
    SERVO_TYPE,
    DeadmanMonitor,
    HeartbeatPublisher,
    RosbridgeTransport,
)
from tests.car.pwm_sampler import PwmSampler  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CAR_SH = REPO / "car" / "connect" / "car.sh"
RESULTS_DIR = REPO / "runs" / f"wheels-off-{dt.date.today().isoformat()}"
MANUAL_DRIVE = "/webserver_pkg/manual_drive"
SERVO_MSG = "/ctrl_pkg/servo_msg"
NEUTRAL_NS = 1_446_000  # throttle PWM at rest (measured; the calibration mid)
HOP_EXPECTED_NS = 1_405_500  # measured for throttle 0.3 on this car
HOP_THROTTLE = 0.3  # the proven hop value; the session cap is 0.5
SESSION_THROTTLE_CAP = 0.5
SESSION_DURATION_CAP_S = 2.0


# -- helpers -------------------------------------------------------------------------------------


def _gate(kind: str, target: str) -> str | None:
    return gate_command(kind, target, None, tool=GATE_TOOL)


def call(action: str, **kw: Any) -> dict[str, Any]:
    g = _gate if action in ("publish", "service_call") else never_gated
    return rosbridge_action(action, host=HOST, port=PORT, gate=g, **kw)


def text(r: dict[str, Any]) -> str:
    return " ".join(c.get("text", "") for c in r.get("content", []))


def zero() -> None:
    r = call(
        "publish",
        topic=MANUAL_DRIVE,
        type=SERVO_TYPE,
        fields={"angle": 0.0, "throttle": 0.0},
        count=2,
        rate=20,
    )
    assert r["status"] == "success", text(r)


def ssh(cmd: str, timeout: float = 30) -> str:
    out = subprocess.run(
        ["bash", str(CAR_SH), "ssh", cmd], capture_output=True, text=True, timeout=timeout, check=False
    )
    return out.stdout


def arm() -> None:
    for service, type_, fields in (
        ("/ctrl_pkg/vehicle_state", "deepracer_interfaces_pkg/ActiveStateSrv", {"state": 0}),
        ("/ctrl_pkg/enable_state", "deepracer_interfaces_pkg/EnableStateSrv", {"is_active": True}),
    ):
        last = None
        for _ in range(3):  # CONTRACTS §0: the first call after a stack restart can time out
            last = call("service_call", service=service, type=type_, fields=fields, timeout=25)
            if last["status"] == "success":
                break
        assert last and last["status"] == "success", text(last)


def record(name: str, **data: Any) -> dict[str, Any]:
    """Append one measurement to ``runs/wheels-off-<date>/measurements.jsonl`` and print it."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds"), "name": name, **data}
    with (RESULTS_DIR / "measurements.jsonl").open("a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(f"\n[measure] {name}: {json.dumps(data, default=str)}")
    return row


def ms(t1: float | None, t0: float) -> float | None:
    """Laptop monotonic difference in ms, one decimal; ``None`` when ``t1`` is ``None``."""
    return None if t1 is None else round((t1 - t0) * 1000, 1)


def wait_until(pred: Callable[[], bool], timeout: float, poll: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(poll)
    return pred()


class ServoEcho:
    """Laptop-side subscription to ``/ctrl_pkg/servo_msg`` with laptop monotonic stamps."""

    def __init__(self, transport: RosbridgeTransport) -> None:
        self._topic = transport.topic(SERVO_MSG, SERVO_TYPE)
        self.messages: list[tuple[float, float, float]] = []  # (t_laptop, angle, throttle)
        self._lock = threading.Lock()

    def start(self) -> ServoEcho:
        self._topic.subscribe(self._on)
        return self

    def _on(self, msg: dict[str, Any]) -> None:
        with self._lock:
            angle, throttle = float(msg.get("angle", 0)), float(msg.get("throttle", 0))
            self.messages.append((time.monotonic(), angle, throttle))

    def stop(self) -> None:
        try:
            self._topic.unsubscribe()
        except Exception:
            pass

    def first(self, pred: Callable[[float, float], bool], after: float = 0.0) -> float | None:
        with self._lock:
            for t, a, th in self.messages:
                if t >= after and pred(a, th):
                    return t
        return None

    def seen_moving(self) -> bool:
        return self.first(lambda a, th: th != 0.0) is not None


@pytest.fixture(autouse=True)
def always_zero_on_exit() -> Iterator[None]:
    yield
    zero()


@pytest.fixture
def sampler(request: pytest.FixtureRequest) -> Iterator[PwmSampler]:
    s = PwmSampler().start()
    s.measure_one_way()
    yield s
    s.stop()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"samples-{request.node.name}.json").write_text(json.dumps(s.dump()))


# -- link, battery, PWM outputs ------------------------------------------------------------------


def test_bridge_reachable_and_graph_present() -> None:
    t0 = time.monotonic()
    status = text(call("status", timeout=10))
    rtt_ms = round((time.monotonic() - t0) * 1000, 1)
    assert "connected" in status
    topics = text(call("list_topics", timeout=15))
    assert MANUAL_DRIVE in topics and SERVO_MSG in topics
    record(
        "link",
        host=HOST,
        port=PORT,
        status_rtt_ms=rtt_ms,
        deadman_topic_present="/deepracer_agent/deadman_state" in topics,
    )


def test_battery_service_answers() -> None:
    r = call(
        "service_call",
        service="/i2c_pkg/battery_level",
        type="deepracer_interfaces_pkg/BatteryLevelSrv",
        fields={},
        timeout=25,
    )
    assert r["status"] == "success", text(r)
    level = json.loads(text(r).split("response:\n", 1)[1])["level"]
    assert -1 <= level <= 11
    record("battery", ros_level=level, note="-1 = pack not seen by the i2c monitor lead")


def test_pwm_outputs_enabled_on_the_car() -> None:
    """The stock servo node never writes pwm0/pwm1 `enable`; our oneshot must have (CONTRACTS §8a)."""
    status = read_pwm_outputs()
    unit = ssh(
        "systemctl is-active deepracer-pwm-enable 2>/dev/null; "
        "cat /sys/class/pwm/pwmchip0/pwm0/enable /sys/class/pwm/pwmchip0/pwm1/enable"
    ).split()
    record("pwm_outputs", preflight_status=status, unit_and_flags=unit)
    assert status == "ok", f"pwm outputs {status}: a correct servo_msg would move nothing ({unit})"


# -- hop: record the PWM, direction is unverifiable from here -------------------------------------


def test_hop_records_pwm_samples(sampler: PwmSampler) -> None:
    """Throttle +0.3 for 1 s. The PWM must leave neutral and the trailing zero must restore it.

    Whether that PWM is forward or reverse cannot be asserted with the wheels off the ground, so
    the samples are recorded for the floor test (`THROTTLE_FORWARD_SIGN` in calibration.py).
    """
    arm()
    assert HOP_THROTTLE <= SESSION_THROTTLE_CAP
    m_start = sampler.mark("hop_start")
    try:
        r = call(
            "publish",
            topic=MANUAL_DRIVE,
            type=SERVO_TYPE,
            fields={"angle": 0.0, "throttle": HOP_THROTTLE},
            count=20,
            rate=20,
        )
        assert r["status"] == "success", text(r)
    finally:
        m_zero = sampler.mark("zero_sent")
        zero()
    time.sleep(0.5)
    sampler.wait_mark(m_start)
    sampler.wait_mark(m_zero)
    assert m_start.t_car is not None and m_zero.t_car is not None
    during = sampler.values_between(m_start.t_car, m_zero.t_car, 0)
    assert during, "no PWM samples came back from the car during the hop"
    moved = sorted({v for v in during if v != NEUTRAL_NS})
    assert moved, f"throttle PWM never left neutral: {during[:10]}..."
    near = any(abs(v - HOP_EXPECTED_NS) <= 5_000 for v in moved)
    assert near, f"hop PWM {moved} not near {HOP_EXPECTED_NS}"

    onset = sampler.latency_ms(m_start, 0, lambda v: v != NEUTRAL_NS)
    back = sampler.latency_ms(m_zero, 0, lambda v: v == NEUTRAL_NS)
    final = sampler.samples[-1].values[0]
    assert final == NEUTRAL_NS, f"trailing zero did not restore neutral: {final}"
    record(
        "hop_pwm",
        throttle=HOP_THROTTLE,
        duration_s=1.0,
        neutral_ns=NEUTRAL_NS,
        hop_pwm_ns=moved,
        command_to_pwm_onset_ms=onset,
        zero_to_neutral_ms=back,
        steering_pwm_ns=sorted({s.values[1] for s in sampler.samples if len(s.values) > 1}),
        direction="UNVERIFIED: +0.3 drives the duty below neutral; forward/reverse needs wheels on the floor",
    )


def test_steering_sweep_records_pwm1(sampler: PwmSampler) -> None:
    """Angle +0.5 then -0.5 at zero throttle, 0.5 s each: pwm1 must swing to opposite sides of rest."""
    arm()
    rest = sampler.samples[-1].values[1] if sampler.samples else None
    excursions: dict[str, list[int]] = {}
    for label, angle in (("left", 0.5), ("right", -0.5)):
        m0 = sampler.mark(f"steer_{label}")
        try:
            r = call(
                "publish",
                topic=MANUAL_DRIVE,
                type=SERVO_TYPE,
                fields={"angle": angle, "throttle": 0.0},
                count=10,
                rate=20,
            )
            assert r["status"] == "success", text(r)
        finally:
            m1 = sampler.mark(f"steer_{label}_zero")
            zero()
        time.sleep(0.4)
        sampler.wait_mark(m0)
        sampler.wait_mark(m1)
        assert m0.t_car is not None and m1.t_car is not None
        excursions[label] = sorted({v for v in sampler.values_between(m0.t_car, m1.t_car + 0.3, 1)})
    throttle_values = sorted({s.values[0] for s in sampler.samples})
    record("steering_pwm", rest_ns=rest, excursions_ns=excursions, throttle_pwm_during_sweep=throttle_values)
    assert throttle_values == [NEUTRAL_NS], f"steering sweep moved the throttle PWM: {throttle_values}"
    assert rest is not None
    left = [v for v in excursions["left"] if v != rest]
    right = [v for v in excursions["right"] if v != rest]
    assert left and right, f"steering PWM did not move both ways: {excursions}"
    opposite = (max(left) > rest) != (max(right) > rest)
    assert opposite, f"both excursions on the same side of rest: {excursions}"


# -- stop latency through the product driver -------------------------------------------------------


def test_stop_latency_servo_echo_and_pwm(sampler: PwmSampler) -> None:
    """`stop_deepracer()` during a 2 s 0.3 drive: zero pair on servo_msg and PWM back to neutral."""
    transport = RosbridgeTransport(HOST, PORT)
    log = EventLog(RESULTS_DIR / "events-stop", session="wheels-off-stop", portal_url="")
    heartbeat = HeartbeatPublisher(transport, "wheels-off-stop")
    monitor = DeadmanMonitor(transport, log)
    echo = ServoEcho(transport).start()
    robot = DeepRacerRobot(transport, event_log=log, heartbeat=heartbeat)
    outcome: list[dict[str, Any]] = []
    try:
        monitor.start()
        heartbeat.start()
        assert monitor.wait_for("armed", 5.0), f"deadman not armed: {monitor.last}"
        assert robot.calibration.max_duration_s <= SESSION_DURATION_CAP_S
        worker = threading.Thread(
            target=lambda: outcome.append(robot.drive(linear=0.3, angular=0.0, duration=2.0)), daemon=True
        )
        worker.start()
        assert wait_until(echo.seen_moving, 30.0), "the drive never reached /ctrl_pkg/servo_msg"
        time.sleep(0.4)
        t_stop = time.monotonic()
        m_stop = sampler.mark("stop_called")
        result = robot.stop(cause="operator")
        t_stop_returned = time.monotonic()
        assert result["status"] == "success", text(result)
        worker.join(5.0)
        time.sleep(0.5)
        t_zero_echo = echo.first(lambda a, th: th == 0.0, after=t_stop)
        pwm = sampler.latency_ms(m_stop, 0, lambda v: v == NEUTRAL_NS)
        stops = [e["payload"] for e in log.read("stop")]
        operator_stop = next((s for s in stops if s.get("cause") == "operator"), None)
        drive_result = outcome[0] if outcome else None
        record(
            "stop_latency",
            drive="linear 0.3 m/s (throttle 0.3) for 2.0 s, stopped after ~0.4 s of motion",
            stop_call_to_return_ms=round((t_stop_returned - t_stop) * 1000, 1),
            stop_call_to_zero_on_servo_msg_ms=ms(t_zero_echo, t_stop),
            stop_call_to_pwm_neutral_ms=pwm,
            stop_event=operator_stop,
            drive_result_text=text(drive_result)[:160] if drive_result else None,
            servo_msgs_seen=len(echo.messages),
        )
        assert t_zero_echo is not None, "no zero pair seen on /ctrl_pkg/servo_msg after stop"
        assert pwm["raw_ms"] is not None, "PWM never returned to neutral after stop"
        assert operator_stop is not None, f"no stop event with cause operator: {stops}"
        assert (t_zero_echo - t_stop) < 1.0 and pwm["corrected_ms"] < 1000
        assert drive_result is not None, "the drive thread returned nothing"
    finally:
        robot.stop(cause="operator")
        heartbeat.stop()
        monitor.stop()
        echo.stop()


# -- barge-in path: AgentRuntime.stop_all ------------------------------------------------------------


async def test_barge_in_stop_all_during_drive(sampler: PwmSampler) -> None:
    """The Red Light path without the model: `stop_all` during a 2 s 0.3 drive.

    Measures stop_all latency to the `stop` event, to the zero pair on servo_msg and to PWM
    neutral; then, because stop_all ends the heartbeat, how long the on-car deadman takes to
    report `tripped` (the car is already still by then).
    """
    log = EventLog(RESULTS_DIR / "events-barge-in", session="wheels-off-barge-in", portal_url="")
    runtime = AgentRuntime(body="car", event_log=log, gate=None, approval=ApprovalBroker())
    echo = ServoEcho(runtime.transport).start()
    loop = asyncio.get_running_loop()
    try:
        runtime._arm()
        assert await asyncio.to_thread(runtime.deadman.wait_for, "armed", 5.0), runtime.deadman.last
        drive = loop.run_in_executor(
            None, lambda: runtime.driver.drive(linear=0.3, angular=0.0, duration=2.0)
        )
        deadline = time.monotonic() + 30.0
        while not echo.seen_moving() and time.monotonic() < deadline:
            await asyncio.sleep(0.005)
        assert echo.seen_moving(), "the drive never reached /ctrl_pkg/servo_msg"
        await asyncio.sleep(0.4)
        t0 = time.monotonic()
        m_stop = sampler.mark("stop_all")
        await runtime.stop_all()
        t1 = time.monotonic()
        tripped = await asyncio.to_thread(runtime.deadman.wait_for, "tripped", 3.0)
        t_trip = time.monotonic()
        await asyncio.wait_for(drive, 5.0)
        await asyncio.sleep(0.3)
        t_zero_echo = echo.first(lambda a, th: th == 0.0, after=t0)
        pwm = sampler.latency_ms(m_stop, 0, lambda v: v == NEUTRAL_NS)
        stop_events = [e for e in log.read("stop")]
        operator = next((e for e in stop_events if e["payload"].get("cause") == "operator"), None)
        deadman_stop = next((e for e in stop_events if e["payload"].get("cause") == "deadman"), None)
        record(
            "barge_in_stop_all",
            drive="runtime.driver.drive(linear=0.3, duration=2.0); runtime.stop_all() after ~0.4 s",
            stop_all_call_to_return_ms=round((t1 - t0) * 1000, 1),
            stop_all_to_zero_on_servo_msg_ms=ms(t_zero_echo, t0),
            stop_all_to_pwm_neutral_ms=pwm,
            stop_event_operator=operator["payload"] if operator else None,
            heartbeat_off_to_deadman_tripped_ms=round((t_trip - t1) * 1000, 1) if tripped else None,
            deadman_state=runtime.deadman.last,
            deadman_stop_event=deadman_stop["payload"] if deadman_stop else None,
            status=runtime.status(),
        )
        assert operator is not None, f"no operator stop event: {[e['payload'] for e in stop_events]}"
        assert t_zero_echo is not None and (t_zero_echo - t0) < 1.0
        assert pwm["raw_ms"] is not None and pwm["corrected_ms"] < 1000
        assert tripped, "deadman did not trip after stop_all ended the heartbeat"
    finally:
        await runtime.stop_all()
        runtime.close()
        echo.stop()


# -- pull the plug: heartbeat and stream die together, the deadman zeros the servo --------------------


def test_deadman_trip_latency_to_pwm_neutral(sampler: PwmSampler) -> None:
    """A 0.3 stream and the heartbeat stop at the same instant (the laptop vanished mid-drive).

    The servo node has no watchdog: the PWM holds the last value until the on-car deadman's zero
    burst lands. Measured: heartbeat cut to PWM neutral; cut to the first zero on servo_msg;
    the deadman's own reported gap.
    """
    arm()
    transport = RosbridgeTransport(HOST, PORT)
    heartbeat = HeartbeatPublisher(transport, "wheels-off-plug")
    monitor = DeadmanMonitor(transport)
    echo = ServoEcho(transport).start()
    handle = transport.topic(MANUAL_DRIVE, SERVO_TYPE)
    cut = threading.Event()
    sent = [0]

    def stream() -> None:
        for _ in range(int(SESSION_DURATION_CAP_S * 20)):  # 2 s hard cap
            if cut.is_set():
                break
            handle.publish({"angle": 0.0, "throttle": HOP_THROTTLE})
            sent[0] += 1
            time.sleep(0.05)

    try:
        monitor.start()
        heartbeat.start()
        heartbeat.set_active(True)
        assert monitor.wait_for("armed", 5.0), f"deadman not armed: {monitor.last}"
        handle.advertise()
        worker = threading.Thread(target=stream, daemon=True)
        worker.start()
        assert wait_until(echo.seen_moving, 5.0), "the stream never reached /ctrl_pkg/servo_msg"
        time.sleep(0.4)
        m_cut = sampler.mark("plug_pulled")
        cut.set()
        heartbeat.stop()
        t_cut = time.monotonic()
        tripped = monitor.wait_for("tripped", 2.0)
        t_trip = time.monotonic()
        worker.join(3.0)
        time.sleep(1.0)
        pwm = sampler.latency_ms(m_cut, 0, lambda v: v == NEUTRAL_NS)
        held: list[int] = []
        if m_cut.t_car is not None:
            hit = sampler.first_after(m_cut.t_car, 0, lambda v: v == NEUTRAL_NS)
            held = sampler.values_between(m_cut.t_car, hit.t_car if hit else m_cut.t_car + 2.0, 0)
        t_zero_echo = echo.first(lambda a, th: th == 0.0, after=t_cut)
        record(
            "deadman_trip_latency",
            stream=f"throttle {HOP_THROTTLE} at 20 Hz, {sent[0]} messages sent before the cut",
            cut_to_deadman_tripped_ms=round((t_trip - t_cut) * 1000, 1) if tripped else None,
            deadman_reported_gap_ms=(monitor.last or {}).get("gap_ms"),
            cut_to_zero_on_servo_msg_ms=ms(t_zero_echo, t_cut),
            cut_to_pwm_neutral_ms=pwm,
            pwm_held_after_cut_ns=sorted(set(held)),
            note="no watchdog in the servo node: the PWM held the last value until the deadman's zeros",
        )
        assert tripped, f"deadman did not trip: {monitor.last}"
        assert pwm["raw_ms"] is not None, "PWM never returned to neutral after the cut"
        assert pwm["corrected_ms"] < 1000, pwm
        assert t_zero_echo is not None
    finally:
        cut.set()
        zero()
        try:
            handle.unadvertise()
        except Exception:
            pass
        heartbeat.stop()
        monitor.stop()
        echo.stop()


def test_deadman_trips_when_heartbeat_stops() -> None:
    """The original contract check through `rosbridge_action` alone: arm, silence, trips+1."""
    topics = text(call("list_topics", timeout=15))
    if "/deepracer_agent/deadman_state" not in topics:
        pytest.skip("on-car deadman not installed (no /deepracer_agent/deadman_state)")
    arm()
    r = call("echo", topic="/deepracer_agent/deadman_state", count=1, timeout=3)
    before = json.loads(json.loads(text(r).split(":\n", 1)[1])[0]["data"])
    r = call(
        "publish",
        topic="/deepracer_agent/heartbeat",
        type="std_msgs/Header",
        fields={"frame_id": "wheels-off"},
        count=40,  # 2 s: a tripped deadman needs 1 s of steady heartbeats to re-arm first
        rate=20,
    )
    assert r["status"] == "success", text(r)
    t0 = time.monotonic()
    r = call("echo", topic="/deepracer_agent/deadman_state", count=4, timeout=3)
    assert r["status"] == "success", text(r)
    msgs = [json.loads(s["data"]) for s in json.loads(text(r).split(":\n", 1)[1])]
    states = [m["state"] for m in msgs]
    record("deadman_trip_rosbridge_only", before=before, after=msgs[-1], states=states)
    assert "tripped" in states, states
    assert msgs[-1]["trips"] == before["trips"] + 1, (before, msgs[-1])
    print(f"deadman reported tripped within {(time.monotonic() - t0) * 1000:.0f} ms of the last heartbeat")
