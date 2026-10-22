"""How the laptop reaches the car: one rosbridge WebSocket, a heartbeat and a deadman echo.

The driver never opens a socket itself. :class:`RosbridgeTransport` implements the
upstream strands-robots ``Transport`` and ``ServiceCapable`` protocols on top of
``strands_robots.rosbridge.rosbridge_action``, so every publish and every service
call that can move the car passes through the shared operator gate
(``strands_robots._command_gate.gate_command``), exactly as a direct ``use_rosbridge``
tool call would. Beside it, :class:`HeartbeatPublisher` ticks ``std_msgs/Header`` on
``/deepracer_agent/heartbeat`` at 20 Hz while a drive is active and 10 Hz while a
session is armed, and :class:`DeadmanMonitor` listens to the on-car deadman's
``/deepracer_agent/deadman_state`` and mirrors it into ``heartbeat`` events. Physics
stops the car; this module is how the car learns the laptop is still there.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

from strands.types.tools import ToolContext
from strands_robots._command_gate import gate_command
from strands_robots.rosbridge import GATE_TOOL, never_gated, rosbridge_action

from deepracer_agent.events import EventLog

logger = logging.getLogger(__name__)

SERVO_TYPE = "deepracer_interfaces_pkg/ServoCtrlMsg"
HEARTBEAT_TOPIC = "/deepracer_agent/heartbeat"
HEARTBEAT_TYPE = "std_msgs/Header"
DEADMAN_STATE_TOPIC = "/deepracer_agent/deadman_state"
DEADMAN_STATE_TYPE = "std_msgs/String"
DEADMAN_STATES = frozenset({"idle", "armed", "tripped"})

HEARTBEAT_ACTIVE_HZ = 20.0
HEARTBEAT_IDLE_HZ = 10.0  # 100 ms gap: 5 Hz left ~100 ms margin and tripped the 300 ms deadman over Wi-Fi
HEARTBEAT_EVENT_MAX_HZ = 2.0
#: ``rosbridge_action`` sleeps this long after every ``advertise`` so DDS matches the new
#: publisher before the first message. A persistent publisher pays it once per topic, not on
#: every stop (wheels-off 2026-10-14: 230 of the 234 ms stop latency was this path).
PUBLISHER_SETTLE_S = 0.2

ActionFn = Callable[..., dict[str, Any]]


def env_host() -> str:
    """``DEEPRACER_HOST``; on ``car`` an ``auto`` or stale value is resolved by :mod:`.discover`."""
    from deepracer_agent.discover import resolve_host

    return resolve_host("127.0.0.1")


def env_port() -> int:
    body = os.environ.get("DEEPRACER_BODY", "sim")
    default = "9090" if body == "car" else "9091"
    return int(os.environ.get("DEEPRACER_ROSBRIDGE_PORT", default))


def result_text(result: dict[str, Any]) -> str:
    """Flatten a strands tool-result envelope to its text."""
    return " ".join(
        str(block.get("text", "")) for block in result.get("content", []) if isinstance(block, dict)
    ).strip()


def parse_service_response(result: dict[str, Any]) -> dict[str, Any] | None:
    """The JSON body ``rosbridge_action("service_call")`` renders after ``response:``.

    Returns ``None`` for an error envelope or an unparsable body.
    """
    if result.get("status") != "success":
        return None
    text = result_text(result)
    _, _, body = text.partition("response:")
    try:
        parsed = json.loads(body.strip() or "null")
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class TopicHandle(Protocol):
    """A persistent publisher/subscriber on one topic (``roslibpy.Topic`` shape)."""

    def advertise(self) -> None: ...

    def publish(self, message: Any) -> None: ...

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None: ...

    def unsubscribe(self) -> None: ...

    def unadvertise(self) -> None: ...


#: Twisted's reconnecting factory doubles its delay on every failed dial (roslibpy caps it at an hour).
#: A bridge that was away for a minute must not cost the show minutes more; 5 s is the ceiling here.
RECONNECT_MAX_DELAY_S = 5.0


def cap_reconnect_delay(max_delay_s: float = RECONNECT_MAX_DELAY_S) -> None:
    try:
        from roslibpy.comm.comm_autobahn import AutobahnRosBridgeClientFactory

        AutobahnRosBridgeClientFactory.set_max_delay(max_delay_s)
    except Exception as exc:  # pragma: no cover - roslibpy absent or renamed
        logger.debug("reconnect delay not capped: %s", exc)


def kick_reconnect(host: str, port: int) -> bool:
    """Ask upstream's shared connection to ``host:port`` to re-dial now instead of after its backoff.

    Upstream keeps one ``roslibpy.Ros`` per address for the whole process and never discards it;
    after an SSH tunnel was replaced the factory may be sleeping out a long delay. Returns True when
    a re-dial was requested, False when there is no such connection or it is already connected.
    """
    try:
        from strands_robots.rosbridge import _backend
    except Exception:
        return False
    with _backend.lock:
        ros = getattr(_backend, "_connections", {}).get((host, int(port)))
    if ros is None or getattr(ros, "is_connected", False):
        return False
    factory = getattr(ros, "factory", None)
    connector = getattr(factory, "connector", None)
    if factory is None or connector is None:
        return False

    def redial() -> None:
        try:
            factory.resetDelay()
            connector.connect()
        except Exception as exc:  # a dial already in flight raises; the factory's own retry stands
            logger.debug("re-dial not started: %s", exc)

    try:
        from twisted.internet import reactor

        reactor.callFromThread(redial)
    except Exception as exc:  # pragma: no cover
        logger.debug("re-dial not scheduled: %s", exc)
        return False
    return True


def _roslibpy_topic(host: str, port: int, topic: str, type: str, timeout: float) -> TopicHandle:
    """A ``roslibpy.Topic`` on the process-wide connection upstream already keeps."""
    import roslibpy
    from strands_robots.rosbridge import _backend

    with _backend.lock:
        ros = _backend.connect(host, port, timeout)
    return roslibpy.Topic(ros, topic, type)


class RosbridgeTransport:
    """Upstream ``Transport`` + ``ServiceCapable`` over ``rosbridge_action``.

    Args:
        host: rosbridge host; defaults to ``$DEEPRACER_HOST`` (sim: 127.0.0.1).
        port: rosbridge port; defaults to ``$DEEPRACER_ROSBRIDGE_PORT`` (9090 on
            the car, 9091 for the fake car).
        timeout: Seconds for the dial and for a service call unless overridden.
        action: Replacement for ``rosbridge_action`` (tests inject a recorder).
        topic_factory: Replacement for the persistent-topic opener.
        preemptible: Publish on persistent, pre-advertised topics (default when no
            ``action`` is injected). Every count goes this way, so a stop's zero pair
            does not pay ``rosbridge_action``'s advertise and settle.
        settle_s: Seconds to wait after advertising a new topic, once per topic.
    """

    twist_type = SERVO_TYPE

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        timeout: float = 5.0,
        action: ActionFn | None = None,
        topic_factory: Callable[[str, str, str, str, float], TopicHandle] | None = None,
        preemptible: bool | None = None,
        settle_s: float = PUBLISHER_SETTLE_S,
    ) -> None:
        self.host = host or env_host()
        self.port = int(port if port is not None else env_port())
        self.timeout = float(timeout)
        self._action: ActionFn = action or rosbridge_action
        self._topic_factory = topic_factory or _roslibpy_topic
        # Streams of more than one message go out on a persistent topic, one message at a
        # time, so a stop can interrupt them. ``rosbridge_action`` holds one process-wide lock
        # for a whole count/rate stream, which made a laptop-side stop wait for the drive to end.
        self.preemptible = action is None if preemptible is None else bool(preemptible)
        self.settle_s = max(0.0, float(settle_s))
        self._stream_generation = 0
        self._stream_lock = threading.Lock()
        # One advertised publisher per topic for the life of the transport. The zero pair of a
        # stop rides the same publisher the drive did, so nothing is advertised on the way down.
        self._handles: dict[str, TopicHandle] = {}
        self._handles_lock = threading.Lock()

    # -- gate ----------------------------------------------------------------

    @staticmethod
    def operator_gate(tool_context: ToolContext | None) -> Callable[[str, str], str | None]:
        """The shared command gate keyed on the rosbridge tool label.

        One label for the whole project, so a drive from the agent and a drive
        from a script file one interrupt id and one audit source.
        """
        return lambda kind, target: gate_command(kind, target, tool_context=tool_context, tool=GATE_TOOL)

    # -- Transport protocol ----------------------------------------------------

    def publish(
        self,
        *,
        topic: str,
        type: str,
        fields: dict[str, Any],
        count: int,
        rate: float,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        if self.preemptible:
            return self._stream(
                topic=topic, type=type, fields=fields, count=count, rate=rate, tool_context=tool_context
            )
        return self._action(
            "publish",
            host=self.host,
            port=self.port,
            topic=topic,
            type=type,
            fields=fields,
            count=count,
            rate=rate,
            timeout=self.timeout,
            gate=self.operator_gate(tool_context),
        )

    def abort_stream(self) -> None:
        """Interrupt the command stream in flight; the caller's zero pair follows on a new generation."""
        with self._stream_lock:
            self._stream_generation += 1

    # -- persistent publishers ---------------------------------------------------

    def warm(self, topic: str, type: str) -> bool:
        """Advertise ``topic`` now, so the first command (or the first stop) pays no settle."""
        if not self.preemptible:
            return False
        try:
            self._handle(topic, type)
        except Exception as exc:
            logger.warning("warm %s failed: %s", topic, exc)
            return False
        return True

    def close(self) -> None:
        """Unadvertise every persistent publisher (best effort)."""
        with self._handles_lock:
            handles, self._handles = list(self._handles.values()), {}
        for handle in handles:
            try:
                handle.unadvertise()
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug("unadvertise failed: %s", exc)

    def _handle(self, topic: str, type: str) -> TopicHandle:
        with self._handles_lock:
            handle = self._handles.get(topic)
            if handle is None:
                handle = self._topic_factory(self.host, self.port, topic, type, self.timeout)
                handle.advertise()
                if self.settle_s > 0:
                    time.sleep(self.settle_s)
                self._handles[topic] = handle
            return handle

    def _drop_handle(self, topic: str, handle: TopicHandle) -> None:
        with self._handles_lock:
            if self._handles.get(topic) is handle:
                del self._handles[topic]
        try:
            handle.unadvertise()
        except Exception:  # pragma: no cover - the link is already gone
            pass

    def _stream(
        self,
        *,
        topic: str,
        type: str,
        fields: dict[str, Any],
        count: int,
        rate: float,
        tool_context: ToolContext | None,
    ) -> dict[str, Any]:
        refusal = self.operator_gate(tool_context)("publish", topic)
        if refusal is not None:
            return {"status": "error", "content": [{"text": f"use_rosbridge: {refusal}"}]}
        with self._stream_lock:
            generation = self._stream_generation
        period = 1.0 / float(rate)
        sent = 0
        aborted = False
        # One retry, only before anything was sent: a cached publisher whose socket died since
        # the last drive is dropped and a fresh one opened. Mid-stream failures are reported.
        for attempt in (1, 2):
            try:
                handle = self._handle(topic, type)
            except Exception as exc:
                return {
                    "status": "error",
                    "content": [{"text": f"use_rosbridge: stream to {topic} failed to open: {exc}"}],
                }
            try:
                next_tick = time.monotonic()
                for _ in range(count):
                    with self._stream_lock:
                        if self._stream_generation != generation:
                            aborted = True
                            break
                    handle.publish(dict(fields))
                    sent += 1
                    next_tick += period
                    delay = next_tick - time.monotonic()
                    # A stream lasts count/rate seconds (the hop's duration); a single message,
                    # the stop's zero pair, returns at once.
                    if delay > 0 and count > 1:
                        time.sleep(delay)
                break
            except Exception as exc:
                self._drop_handle(topic, handle)
                if sent == 0 and attempt == 1:
                    logger.warning(
                        "publisher on %s failed before the first message; reopening: %s", topic, exc
                    )
                    continue
                return {
                    "status": "error",
                    "content": [
                        {"text": f"use_rosbridge: stream to {topic} failed after {sent} message(s): {exc}"}
                    ],
                }
        text = f"published {sent} message(s) to {topic}" + (" (interrupted by stop)" if aborted else "")
        return {"status": "success", "content": [{"text": text}], "sent": sent, "aborted": aborted}

    def echo(self, *, topic: str, type: str | None, count: int, timeout: float) -> dict[str, Any]:
        return self._action(
            "echo",
            host=self.host,
            port=self.port,
            topic=topic,
            type=type,
            count=count,
            timeout=timeout,
            gate=never_gated,
        )

    # -- ServiceCapable protocol ---------------------------------------------

    def service_call(
        self,
        *,
        service: str,
        type: str,
        fields: dict[str, Any],
        tool_context: ToolContext | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return self._action(
            "service_call",
            host=self.host,
            port=self.port,
            service=service,
            type=type,
            fields=fields,
            timeout=self.timeout if timeout is None else float(timeout),
            gate=self.operator_gate(tool_context),
        )

    # -- reads ---------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """``rosbridge_action("status")`` plus the round trip it took, in ms.

        ``connected`` is read from the status text; ``rtt_ms`` is ``None`` when
        the bridge did not answer.
        """
        t0 = time.monotonic()
        result = self._action(
            "status", host=self.host, port=self.port, timeout=self.timeout, gate=never_gated
        )
        rtt_ms = (time.monotonic() - t0) * 1000.0
        text = result_text(result)
        connected = (
            result.get("status") == "success" and "connected to" in text and "not connected" not in text
        )
        return {"connected": connected, "rtt_ms": round(rtt_ms, 1) if connected else None, "text": text}

    def list_topics(self) -> list[str]:
        result = self._action(
            "list_topics", host=self.host, port=self.port, timeout=self.timeout, gate=never_gated
        )
        if result.get("status") != "success":
            return []
        return [line.split(" [", 1)[0] for line in result_text(result).splitlines() if line.strip()]

    def topic(self, name: str, type: str) -> TopicHandle:
        """A persistent topic handle for the heartbeat and the deadman echo."""
        return self._topic_factory(self.host, self.port, name, type, self.timeout)


# -- heartbeat ----------------------------------------------------------------


def header_message(session: str, now: float | None = None) -> dict[str, Any]:
    """A ``std_msgs/Header`` with the laptop clock and the session as ``frame_id``."""
    t = time.time() if now is None else now
    sec = int(t)
    return {"stamp": {"sec": sec, "nanosec": int((t - sec) * 1e9)}, "frame_id": session}


class HeartbeatPublisher:
    """Ticks ``/deepracer_agent/heartbeat`` so the on-car deadman stays armed.

    20 Hz while :meth:`set_active` is true (a drive is in flight), 5 Hz otherwise,
    nothing at all once :meth:`stop` has run - which is how a laptop-side stop
    hands the car to the deadman on purpose.

    Args:
        transport: Where to open the topic.
        session: Session id carried in ``frame_id``.
        active_hz: Rate while a drive is active.
        idle_hz: Rate while merely armed.
        clock: Replacement for ``time.time`` (tests).
    """

    def __init__(
        self,
        transport: RosbridgeTransport,
        session: str,
        *,
        active_hz: float = HEARTBEAT_ACTIVE_HZ,
        idle_hz: float = HEARTBEAT_IDLE_HZ,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not (active_hz > 0 and idle_hz > 0):
            raise ValueError("heartbeat rates must be positive")
        self.transport = transport
        self.session = session
        self.active_hz = float(active_hz)
        self.idle_hz = float(idle_hz)
        self._clock = clock
        self._active = threading.Event()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._topic: TopicHandle | None = None
        self.sent = 0
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def start(self) -> None:
        """Open the topic and start ticking at the idle rate. Idempotent."""
        if self.running:
            return
        self._stop.clear()
        self._topic = self.transport.topic(HEARTBEAT_TOPIC, HEARTBEAT_TYPE)
        self._thread = threading.Thread(target=self._run, name="deepracer-heartbeat", daemon=True)
        self._thread.start()

    def set_active(self, active: bool) -> None:
        if active:
            self._active.set()
        else:
            self._active.clear()
        self._wake.set()

    def stop(self) -> None:
        """Stop ticking. The deadman trips 300 ms later unless the car is already still."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(2.0)
        self._thread = None
        topic, self._topic = self._topic, None
        if topic is not None:
            try:
                topic.unadvertise()
            except Exception as exc:
                logger.debug("heartbeat unadvertise failed: %s", exc)
        self._active.clear()

    def tick(self) -> bool:
        """Publish one heartbeat now. Returns False when the publish failed."""
        if self._topic is None:
            return False
        try:
            self._topic.publish(header_message(self.session, self._clock()))
        except Exception as exc:
            self.last_error = str(exc)
            return False
        self.sent += 1
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            self.tick()
            period = 1.0 / (self.active_hz if self._active.is_set() else self.idle_hz)
            self._wake.wait(period)
            self._wake.clear()


# -- deadman echo -------------------------------------------------------------


def parse_deadman_state(message: dict[str, Any] | str) -> dict[str, Any] | None:
    """The deadman's JSON ``{"state", "gap_ms", "since", "trips"}`` or ``None`` when malformed."""
    data = message.get("data") if isinstance(message, dict) else message
    if not isinstance(data, str):
        return None
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or parsed.get("state") not in DEADMAN_STATES:
        return None
    try:
        gap_ms = int(parsed.get("gap_ms", 0))
        trips = int(parsed.get("trips", 0))
    except (TypeError, ValueError):
        return None
    return {"state": parsed["state"], "gap_ms": gap_ms, "since": parsed.get("since"), "trips": trips}


class DeadmanMonitor:
    """Subscribes to ``/deepracer_agent/deadman_state`` and mirrors it as ``heartbeat`` events.

    Events are rate-limited to 2 Hz except on a state change, which is emitted at
    once. :attr:`state` is ``"unknown"`` until the first message arrives, which
    preflight treats as a reason not to go.
    """

    def __init__(
        self,
        transport: RosbridgeTransport,
        event_log: EventLog | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_event_hz: float = HEARTBEAT_EVENT_MAX_HZ,
    ) -> None:
        self.transport = transport
        self.event_log = event_log
        self._clock = clock
        self._min_period = 1.0 / max_event_hz
        self._topic: TopicHandle | None = None
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self.last: dict[str, Any] | None = None
        self.last_seen: float | None = None
        self._last_emit: float | None = None
        self.on_trip: Callable[[dict[str, Any]], None] | None = None

    @property
    def state(self) -> str:
        return self.last["state"] if self.last else "unknown"

    def start(self) -> None:
        if self._topic is not None:
            return
        self._topic = self.transport.topic(DEADMAN_STATE_TOPIC, DEADMAN_STATE_TYPE)
        self._topic.subscribe(self.on_message)

    def stop(self) -> None:
        topic, self._topic = self._topic, None
        if topic is not None:
            try:
                topic.unsubscribe()
            except Exception as exc:
                logger.debug("deadman unsubscribe failed: %s", exc)

    def on_message(self, message: dict[str, Any] | str) -> None:
        parsed = parse_deadman_state(message)
        if parsed is None:
            if self.event_log is not None:
                self.event_log.emit(
                    "error",
                    {"where": "deadman_monitor", "message": f"malformed deadman_state: {message!r}"[:300]},
                )
            return
        now = self._clock()
        with self._changed:
            previous = self.last["state"] if self.last else None
            self.last = parsed
            self.last_seen = now
            changed = parsed["state"] != previous
            due = self._last_emit is None or (now - self._last_emit) >= self._min_period
            if (changed or due) and self.event_log is not None:
                self.event_log.emit(
                    "heartbeat", {"state": parsed["state"], "gap_ms": parsed["gap_ms"]}, source="deadman"
                )
                self._last_emit = now
            self._changed.notify_all()
        if changed and parsed["state"] == "tripped":
            if self.event_log is not None:
                self.event_log.emit(
                    "stop",
                    {"request_id": None, "cause": "deadman", "latency_ms": parsed["gap_ms"]},
                    source="deadman",
                )
            if self.on_trip is not None:
                self.on_trip(parsed)

    def wait_for(self, state: str, timeout: float) -> bool:
        """Block until the deadman reports ``state`` (for install verification and tests)."""
        deadline = self._clock() + timeout
        with self._changed:
            while self.state != state:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return False
                self._changed.wait(min(remaining, 0.25))
            return True


def check_deadman(
    hold_s: float = 3.0, trip_wait_s: float = 3.0, host: str | None = None, port: int | None = None
) -> int:
    """Live check: heartbeats for ``hold_s``, then silence; expect ``armed`` then ``tripped`` and zeros.

    Read-only apart from the heartbeat topic and an ``echo`` of ``/ctrl_pkg/servo_msg``; it never
    publishes a servo command. Returns a process exit code and prints what it saw.
    """
    transport = RosbridgeTransport(host, port)
    status = transport.status()
    print(f"rosbridge: {status['text']}")
    if not status["connected"]:
        return 2
    monitor = DeadmanMonitor(transport)
    monitor.start()
    heartbeat = HeartbeatPublisher(transport, "deadman-check")
    heartbeat.start()
    heartbeat.set_active(True)
    armed = monitor.wait_for("armed", hold_s)
    print(f"armed within {hold_s}s: {armed} (state {monitor.last})")
    time.sleep(hold_s)
    heartbeat.stop()
    t0 = time.monotonic()
    servo = transport.echo(topic="/ctrl_pkg/servo_msg", type=SERVO_TYPE, count=3, timeout=trip_wait_s)
    tripped = monitor.wait_for("tripped", max(0.1, trip_wait_s - (time.monotonic() - t0)))
    print(f"tripped within {trip_wait_s}s: {tripped} (state {monitor.last})")
    print("servo_msg after silence:", result_text(servo).replace("\n", " ")[:300])
    monitor.stop()
    zeros = '"angle": 0.0' in result_text(servo) and '"throttle": 0.0' in result_text(servo)
    print(f"zeros seen on /ctrl_pkg/servo_msg: {zeros}")
    return 0 if (armed and tripped and zeros) else 1


if __name__ == "__main__":  # pragma: no cover - live check against a car or the fake car
    import argparse

    parser = argparse.ArgumentParser(description="Live deadman check: heartbeats, silence, expect zeros.")
    parser.add_argument("--check-deadman", action="store_true", required=True)
    parser.add_argument("--hold", type=float, default=3.0)
    parser.add_argument("--wait", type=float, default=3.0)
    args = parser.parse_args()
    raise SystemExit(check_deadman(args.hold, args.wait))


__all__ = [
    "DEADMAN_STATES",
    "DEADMAN_STATE_TOPIC",
    "DEADMAN_STATE_TYPE",
    "HEARTBEAT_TOPIC",
    "HEARTBEAT_TYPE",
    "SERVO_TYPE",
    "DeadmanMonitor",
    "HeartbeatPublisher",
    "RosbridgeTransport",
    "TopicHandle",
    "check_deadman",
    "env_host",
    "env_port",
    "header_message",
    "parse_deadman_state",
    "parse_service_response",
    "result_text",
]

cap_reconnect_delay()
