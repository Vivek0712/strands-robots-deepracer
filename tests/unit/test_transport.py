"""RosbridgeTransport, HeartbeatPublisher and DeadmanMonitor against the recorder stand-in."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from deepracer_agent.events import EventLog
from deepracer_agent.transport import (
    DEADMAN_STATE_TOPIC,
    HEARTBEAT_TOPIC,
    HEARTBEAT_TYPE,
    DeadmanMonitor,
    HeartbeatPublisher,
    RosbridgeTransport,
    env_port,
    header_message,
    parse_deadman_state,
    parse_service_response,
)
from tests.unit._car_fakes import FakeAction, err, make_transport, ok, service_ok


@pytest.fixture(autouse=True)
def _no_pregrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRANDS_ROS2_COMMAND_ALLOW", raising=False)
    monkeypatch.delenv("BYPASS_TOOL_CONSENT", raising=False)


# -- protocol conformance ------------------------------------------------------


def test_transport_satisfies_upstream_protocols() -> None:
    from strands_robots.drivers.ros._mobile_base import ServiceCapable, Transport

    transport, _, _ = make_transport()
    assert isinstance(transport, Transport)
    assert isinstance(transport, ServiceCapable)
    assert transport.twist_type == "deepracer_interfaces_pkg/ServoCtrlMsg"


def test_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPRACER_ROSBRIDGE_PORT", raising=False)
    monkeypatch.setenv("DEEPRACER_BODY", "sim")
    assert env_port() == 9091
    monkeypatch.setenv("DEEPRACER_BODY", "car")
    assert env_port() == 9090
    monkeypatch.setenv("DEEPRACER_ROSBRIDGE_PORT", "9999")
    assert env_port() == 9999
    monkeypatch.setenv("DEEPRACER_HOST", "10.0.0.5")
    t = RosbridgeTransport(action=FakeAction())
    assert (t.host, t.port) == ("10.0.0.5", 9999)


# -- gate ----------------------------------------------------------------------


def test_publish_to_manual_drive_without_operator_is_refused() -> None:
    transport, action, _ = make_transport()
    result = transport.publish(
        topic="/webserver_pkg/manual_drive", type="x/Y", fields={"angle": 0, "throttle": 0}, count=1, rate=20
    )
    assert result["status"] == "error"
    assert "safety-critical command surface" in result["content"][0]["text"]
    assert action.publishes[0]["topic"] == "/webserver_pkg/manual_drive"


def test_publish_pregranted_via_env_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    transport, _, _ = make_transport()
    result = transport.publish(topic="/webserver_pkg/manual_drive", type="x/Y", fields={}, count=1, rate=20)
    assert result["status"] == "success"


def test_heartbeat_topic_is_not_a_command_surface() -> None:
    transport, _, _ = make_transport()
    result = transport.publish(topic=HEARTBEAT_TOPIC, type=HEARTBEAT_TYPE, fields={}, count=1, rate=2)
    assert result["status"] == "success"


@pytest.mark.parametrize("service", ["/ctrl_pkg/vehicle_state", "/ctrl_pkg/enable_state"])
def test_arming_services_are_gated(service: str) -> None:
    transport, _, _ = make_transport()
    result = transport.service_call(service=service, type="pkg/Srv", fields={})
    assert result["status"] == "error" and "command surface" in result["content"][0]["text"]


def test_read_only_services_and_echo_are_never_gated() -> None:
    transport, action, _ = make_transport()
    assert (
        transport.service_call(service="/i2c_pkg/battery_level", type="p/S", fields={})["status"] == "success"
    )
    assert transport.echo(topic="/x", type=None, count=1, timeout=1.0)["status"] == "success"
    assert action.of("echo")[0]["gate"].__name__ == "never_gated"


def test_service_call_timeout_override_reaches_action() -> None:
    transport, action, _ = make_transport()
    transport.service_call(service="/i2c_pkg/battery_level", type="p/S", fields={}, timeout=25.0)
    transport.service_call(service="/i2c_pkg/battery_level", type="p/S", fields={})
    assert [c["timeout"] for c in action.services] == [25.0, 5.0]


# -- reads ---------------------------------------------------------------------


def test_status_reports_rtt_when_connected() -> None:
    transport, action, _ = make_transport()
    status = transport.status()
    assert status["connected"] is True and status["rtt_ms"] is not None and status["rtt_ms"] >= 0
    action.status_result = ok("backend: roslibpy; not connected - could not connect")
    status = transport.status()
    assert status["connected"] is False and status["rtt_ms"] is None


def test_list_topics_strips_types() -> None:
    transport, _, _ = make_transport()
    assert transport.list_topics() == ["/a", "/webserver_pkg/manual_drive"]


@pytest.mark.parametrize(
    "result,expected",
    [
        (service_ok({"level": 7}), {"level": 7}),
        (ok("response:\nnot json"), None),
        (ok("no response marker"), None),
        (err("timeout"), None),
        (ok("response:\n[1, 2]"), None),
    ],
)
def test_parse_service_response_table(result: dict[str, Any], expected: Any) -> None:
    assert parse_service_response(result) == expected


# -- heartbeat -----------------------------------------------------------------


def test_header_message_shape() -> None:
    msg = header_message("s-1", now=1700000000.25)
    assert msg == {"stamp": {"sec": 1700000000, "nanosec": 250000000}, "frame_id": "s-1"}


def test_heartbeat_opens_topic_ticks_and_stops() -> None:
    transport, _, topics = make_transport()
    hb = HeartbeatPublisher(transport, "s-1", active_hz=200.0, idle_hz=50.0)
    assert not hb.running
    hb.start()
    hb.start()  # idempotent
    time.sleep(0.15)
    topic = topics[HEARTBEAT_TOPIC]
    idle_count = len(topic.published)
    assert topic.type == HEARTBEAT_TYPE and 3 <= idle_count
    hb.set_active(True)
    time.sleep(0.15)
    active_count = len(topic.published) - idle_count
    assert active_count > idle_count * 1.5, (idle_count, active_count)
    assert all(m["frame_id"] == "s-1" for m in topic.published)
    hb.stop()
    assert not hb.running and topic.unadvertised and not hb.active
    n = len(topic.published)
    time.sleep(0.05)
    assert len(topic.published) == n


def test_heartbeat_publish_failure_is_recorded_not_raised() -> None:
    transport, _, topics = make_transport()
    hb = HeartbeatPublisher(transport, "s-1")
    hb.start()
    topics[HEARTBEAT_TOPIC].fail = True
    assert hb.tick() is False and hb.last_error == "socket closed"
    hb.stop()


@pytest.mark.parametrize("rates", [{"active_hz": 0}, {"idle_hz": -1}])
def test_refusal_table_heartbeat_rates(rates: dict[str, float]) -> None:
    transport, _, _ = make_transport()
    with pytest.raises(ValueError, match="positive"):
        HeartbeatPublisher(transport, "s", **rates)


# -- deadman monitor -----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"state": "armed", "gap_ms": 12, "since": "2026-10-14T00:00:00Z", "trips": 0}', "armed"),
        ({"data": '{"state": "tripped", "gap_ms": 450, "since": null, "trips": 1}'}, "tripped"),
        ('{"state": "idle", "gap_ms": 0, "since": "x", "trips": 0}', "idle"),
    ],
)
def test_parse_deadman_state_accepts_contract_shapes(raw: Any, expected: str) -> None:
    parsed = parse_deadman_state(raw)
    assert parsed and parsed["state"] == expected


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"state": "flying"}',
        '{"gap_ms": 1}',
        '{"state": "armed", "gap_ms": "lots"}',
        "[1, 2]",
        {"data": 5},
        {"nodata": "x"},
    ],
)
def test_refusal_table_parse_deadman_state(raw: Any) -> None:
    assert parse_deadman_state(raw) is None


def test_deadman_monitor_mirrors_state_changes_and_rate_limits(tmp_path: Path) -> None:
    now = [100.0]
    log = EventLog(tmp_path, session="s", portal_url="")
    transport, _, topics = make_transport()
    mon = DeadmanMonitor(transport, log, clock=lambda: now[0])
    assert mon.state == "unknown"
    mon.start()
    topic = topics[DEADMAN_STATE_TOPIC]
    topic.deliver('{"state": "armed", "gap_ms": 10, "since": "t", "trips": 0}')
    now[0] += 0.1
    topic.deliver('{"state": "armed", "gap_ms": 20, "since": "t", "trips": 0}')  # within 2 Hz window: dropped
    now[0] += 0.1
    trips: list[dict[str, Any]] = []
    mon.on_trip = trips.append
    topic.deliver('{"state": "tripped", "gap_ms": 400, "since": "t2", "trips": 1}')  # change: emitted at once
    now[0] += 0.6
    topic.deliver('{"state": "tripped", "gap_ms": 900, "since": "t2", "trips": 1}')  # due: emitted
    events = log.read("heartbeat")
    assert [e["payload"] for e in events] == [
        {"state": "armed", "gap_ms": 10},
        {"state": "tripped", "gap_ms": 400},
        {"state": "tripped", "gap_ms": 900},
    ]
    assert all(e["source"] == "deadman" for e in events)
    assert mon.state == "tripped" and mon.last["trips"] == 1 and trips[0]["gap_ms"] == 400
    topic.deliver("garbage")
    assert log.last("error")["payload"]["where"] == "deadman_monitor"
    mon.stop()
    assert topic.unsubscribed


def test_deadman_wait_for_times_out_and_succeeds() -> None:
    transport, _, topics = make_transport()
    mon = DeadmanMonitor(transport)
    mon.start()
    assert mon.wait_for("armed", 0.05) is False
    topics[DEADMAN_STATE_TOPIC].deliver('{"state": "armed", "gap_ms": 1, "since": "t", "trips": 0}')
    assert mon.wait_for("armed", 0.5) is True


# -- persistent publishers (stop latency) -----------------------------------------------------


def _preemptible(monkeypatch: pytest.MonkeyPatch | None = None):
    from tests.unit._car_fakes import topic_factory

    topics: dict[str, Any] = {}
    transport = RosbridgeTransport(
        "127.0.0.1", 9091, topic_factory=topic_factory(topics), preemptible=True, settle_s=0.0
    )
    return transport, topics


def test_single_publish_uses_a_persistent_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    """The zero pair of a stop rides the publisher the drive advertised: one advertise, no unadvertise."""
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    transport, topics = _preemptible()
    fields = {"angle": 0.0, "throttle": 0.3}
    assert (
        transport.publish(topic="/webserver_pkg/manual_drive", type="T", fields=fields, count=3, rate=200.0)[
            "status"
        ]
        == "success"
    )
    result = transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.0},
        count=1,
        rate=20.0,
    )
    assert result["status"] == "success" and result["sent"] == 1
    assert "published 1 message(s) to /webserver_pkg/manual_drive" in result["content"][0]["text"]
    topic = topics["/webserver_pkg/manual_drive"]
    assert topic.advertised == 1 and not topic.unadvertised
    assert len(topic.published) == 4 and topic.published[-1] == {"angle": 0.0, "throttle": 0.0}
    transport.close()
    assert topic.unadvertised and transport._handles == {}


def test_persistent_publish_is_still_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRANDS_ROS2_COMMAND_ALLOW", raising=False)
    transport, topics = _preemptible()
    result = transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.3},
        count=1,
        rate=20.0,
    )
    assert result["status"] == "error" and "use_rosbridge" in result["content"][0]["text"]
    assert topics == {}  # nothing advertised on a refusal


def test_warm_advertises_before_the_first_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    transport, topics = _preemptible()
    assert transport.warm("/webserver_pkg/manual_drive", "T") is True
    assert topics["/webserver_pkg/manual_drive"].advertised == 1
    transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.0},
        count=1,
        rate=20.0,
    )
    assert topics["/webserver_pkg/manual_drive"].advertised == 1  # reused, not reopened


def test_dead_publisher_is_reopened_once_before_the_first_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cached publisher whose socket died since the last drive is dropped and replaced."""
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    from tests.unit._car_fakes import FakeTopic

    topics: dict[str, Any] = {}
    made: list[FakeTopic] = []

    def factory(host: str, port: int, name: str, type: str, timeout: float) -> FakeTopic:
        t = FakeTopic(name, type)
        t.fail = len(made) == 0  # the first handle is dead on arrival
        made.append(t)
        topics[name] = t
        return t

    transport = RosbridgeTransport("127.0.0.1", 9091, topic_factory=factory, preemptible=True, settle_s=0.0)
    result = transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.0},
        count=1,
        rate=20.0,
    )
    assert result["status"] == "success" and len(made) == 2 and made[0].unadvertised
    assert made[1].published == [{"angle": 0.0, "throttle": 0.0}]


def test_mid_stream_failure_is_reported_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once a message has gone out, a failure is the drive's error (the zero pair follows from finally)."""
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    transport, topics = _preemptible()
    transport.warm("/webserver_pkg/manual_drive", "T")
    topic = topics["/webserver_pkg/manual_drive"]
    original = topic.publish

    def flaky(message: Any) -> None:
        if len(topic.published) == 2:
            raise ConnectionError("socket closed")
        original(message)

    topic.publish = flaky  # type: ignore[method-assign]
    result = transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.3},
        count=5,
        rate=500.0,
    )
    assert result["status"] == "error" and "after 2 message(s)" in result["content"][0]["text"]
    assert topic.unadvertised and "/webserver_pkg/manual_drive" not in transport._handles


def test_default_settle_matches_upstream_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 200 ms DDS settle upstream pays per publish is paid once per topic here."""
    from deepracer_agent.transport import PUBLISHER_SETTLE_S

    assert PUBLISHER_SETTLE_S == 0.2
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    from tests.unit._car_fakes import topic_factory

    topics: dict[str, Any] = {}
    transport = RosbridgeTransport(
        "127.0.0.1", 9091, topic_factory=topic_factory(topics), preemptible=True, settle_s=0.05
    )
    t0 = time.perf_counter()
    transport.warm("/webserver_pkg/manual_drive", "T")
    first = time.perf_counter() - t0
    t0 = time.perf_counter()
    transport.publish(
        topic="/webserver_pkg/manual_drive",
        type="T",
        fields={"angle": 0.0, "throttle": 0.0},
        count=1,
        rate=20.0,
    )
    second = time.perf_counter() - t0
    assert first >= 0.05 and second < 0.02
