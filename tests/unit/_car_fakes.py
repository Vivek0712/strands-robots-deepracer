"""Transport stand-ins for the Car team's unit tests (upstream's recorder pattern, no sockets)."""

from __future__ import annotations

import json
from typing import Any

OK: dict[str, Any] = {"status": "success", "content": [{"text": "ok"}]}


def ok(text: str = "ok") -> dict[str, Any]:
    return {"status": "success", "content": [{"text": text}]}


def err(text: str) -> dict[str, Any]:
    return {"status": "error", "content": [{"text": text}]}


def service_ok(body: dict[str, Any]) -> dict[str, Any]:
    """What ``rosbridge_action("service_call")`` renders on success."""
    return ok("response:\n" + json.dumps(body, indent=2))


class FakeTopic:
    """A ``roslibpy.Topic`` stand-in recording publishes and holding one subscriber."""

    def __init__(self, name: str, type: str) -> None:
        self.name = name
        self.type = type
        self.published: list[dict[str, Any]] = []
        self.callback: Any = None
        self.unadvertised = False
        self.unsubscribed = False
        self.fail = False
        self.advertised = 0

    def advertise(self) -> None:
        self.advertised += 1

    def publish(self, message: Any) -> None:
        if self.fail:
            raise ConnectionError("socket closed")
        self.published.append(dict(message))

    def subscribe(self, callback: Any) -> None:
        self.callback = callback

    def unsubscribe(self) -> None:
        self.unsubscribed = True

    def unadvertise(self) -> None:
        self.unadvertised = True

    def deliver(self, data: str) -> None:
        assert self.callback is not None
        self.callback({"data": data})


class FakeAction:
    """Stand-in for ``rosbridge_action``: records calls, consults the gate like the real one.

    ``service_results`` maps a service name to a queue of result envelopes (popped
    per call; the last one repeats). ``publish_result`` is returned for every
    publish unless ``publish_raises`` is set.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.publish_result: dict[str, Any] = OK
        self.publish_results: list[dict[str, Any]] = []
        self.publish_raises: Exception | None = None
        self.service_results: dict[str, list[dict[str, Any]]] = {}
        self.status_result: dict[str, Any] = ok("backend: roslibpy; connected to ws://127.0.0.1:9091")
        self.topics_result: dict[str, Any] = ok(
            "/a [x/A]\n/webserver_pkg/manual_drive [deepracer_interfaces_pkg/ServoCtrlMsg]"
        )
        self.echo_result: dict[str, Any] = ok("echo /x:\n[]")

    def __call__(self, action: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"action": action, **kwargs})
        gate = kwargs.get("gate")
        if action in ("publish", "service_call") and gate is not None:
            target = kwargs.get("topic") if action == "publish" else kwargs.get("service")
            refusal = gate(action, target)
            if refusal is not None:
                return err("use_rosbridge: " + refusal)
        if action == "publish":
            if self.publish_raises is not None:
                raise self.publish_raises
            if self.publish_results:
                return self.publish_results.pop(0)
            return self.publish_result
        if action == "service_call":
            queue = self.service_results.get(kwargs["service"])
            if not queue:
                return service_ok({"error": 0})
            return queue.pop(0) if len(queue) > 1 else queue[0]
        if action == "status":
            return self.status_result
        if action == "list_topics":
            return self.topics_result
        if action == "echo":
            return self.echo_result
        return err(f"unknown action {action}")

    def of(self, action: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["action"] == action]

    @property
    def publishes(self) -> list[dict[str, Any]]:
        return self.of("publish")

    @property
    def services(self) -> list[dict[str, Any]]:
        return self.of("service_call")


def topic_factory(registry: dict[str, FakeTopic]):
    def _open(host: str, port: int, name: str, type: str, timeout: float) -> FakeTopic:
        registry.setdefault(name, FakeTopic(name, type))
        return registry[name]

    return _open


def make_transport(action: FakeAction | None = None, topics: dict[str, FakeTopic] | None = None):
    from deepracer_agent.transport import RosbridgeTransport

    action = action or FakeAction()
    topics = topics if topics is not None else {}
    transport = RosbridgeTransport("127.0.0.1", 9091, action=action, topic_factory=topic_factory(topics))
    return transport, action, topics


def tiny_jpeg(width: int = 4, height: int = 3) -> bytes:
    """A syntactically valid JPEG skeleton with an SOF0 naming ``width x height``."""
    sof = bytes([0xFF, 0xC0, 0x00, 0x11, 0x08, height >> 8, height & 0xFF, width >> 8, width & 0xFF, 0x03])
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    return b"\xff\xd8" + sof + b"\xff\xda\x00\x02" + b"\x12\x34" + b"\xff\xd9"
