"""Unit tests for the Pit Wall backend (portal/backend): events in, events out, ops to the runtime.

Uses FastAPI's TestClient with an injected recorder runtime and a tmp run dir; no sockets to a
car, no console, no model. The refusal table lists every malformed event the portal rejects and the
reason it gives. Physics stops the car; the decider explains; these tests check the window.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # portal/ is a plain package at the repo root, not installed
    sys.path.insert(0, str(REPO_ROOT))

from portal.backend.app import create_app  # noqa: E402
from portal.backend.console import ConsoleStream  # noqa: E402
from portal.backend.fake_runtime import FakeRuntime  # noqa: E402
from portal.backend.schema import validate_event  # noqa: E402

TS = "2026-10-14T06:52:01.123Z"
THOUGHT = {"ts": TS, "type": "thought", "payload": {}}


def verdict_event(rid: str, stage: str, action: str, reason: str) -> dict[str, Any]:
    return make_event("verdict", {"request_id": rid, "stage": stage, "action": action, "reason": reason})


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


def make_event(etype: str = "thought", payload: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    event = {"ts": TS, "type": etype, "source": "test", "payload": payload or {"text": "hello"}}
    event.update(extra)
    return event


class RecorderRuntime:
    """Stand-in for the runtime adapter: records every call the portal makes."""

    name = "recorder"

    def __init__(self) -> None:
        self.body = "sim"
        self.calls: list[tuple[Any, ...]] = []

    async def submit(self, text: str, *, beat: str | None = None) -> str:
        self.calls.append(("submit", text, beat))
        return "req-test"

    async def stop_all(self) -> None:
        self.calls.append(("stop_all",))

    async def preflight(self) -> dict[str, Any]:
        self.calls.append(("preflight",))
        return {"go": True, "battery": 8, "reasons": []}

    def status(self) -> dict[str, Any]:
        return {"body": self.body, "armed": False, "deadman": "idle", "battery": 8, "last_verdict": None}

    def resolve_approval(self, request_id: str, approved: bool) -> bool:
        self.calls.append(("approve", request_id, approved))
        return request_id == "req-known"

    async def set_body(self, active: str) -> None:
        self.body = active
        self.calls.append(("body", active))

    async def voice_ptt(self, state: str) -> None:
        self.calls.append(("ptt", state))

    async def voice_audio(self, pcm: bytes) -> None:
        self.calls.append(("audio", len(pcm)))

    async def aclose(self) -> None:
        self.calls.append(("aclose",))


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs" / "s-test"


@pytest.fixture
def recorder() -> RecorderRuntime:
    return RecorderRuntime()


@pytest.fixture
def client(run_dir: Path, recorder: RecorderRuntime, tmp_path: Path) -> TestClient:
    console = ConsoleStream(base_url="http://127.0.0.1:1", password="")
    app = create_app(run_dir=run_dir, runtime=recorder, console=console, frontend_dist=tmp_path / "nodist")
    with TestClient(app) as tc:
        yield tc


def recv_until(ws: Any, pred: Any, limit: int = 50) -> dict[str, Any]:
    for _ in range(limit):
        msg = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("expected message did not arrive")


# ----- HTTP -----------------------------------------------------------------------------------


def test_health_and_state(client: TestClient) -> None:
    assert client.get("/health").json()["ok"] is True
    state = client.get("/api/state").json()
    assert state["session"] == "s-test"
    assert state["runtime"] == "recorder"
    assert state["body"] == "sim"
    assert state["safety"] == "physics stops the car; the decider explains"
    assert state["events"] == 0 and state["pending_approvals"] == []


def test_post_event_persists_and_assigns_seq(client: TestClient, run_dir: Path) -> None:
    resp = client.post("/api/events", json=make_event())
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] is True and body["seq"] == 1 and body["persisted"] is True
    lines = (run_dir / "events.jsonl").read_text().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["type"] == "thought" and stored["session"] == "s-test" and stored["seq"] == 1


def test_post_event_from_eventlog_is_not_double_written(client: TestClient, run_dir: Path) -> None:
    resp = client.post("/api/events", json=make_event(seq=7), headers={"X-Deepracer-Source": "eventlog"})
    assert resp.status_code == 202 and resp.json()["persisted"] is False
    assert not (run_dir / "events.jsonl").exists()
    assert client.get("/api/state").json()["events"] == 1


def test_post_event_with_seq_is_assumed_written_by_its_eventlog(client: TestClient, run_dir: Path) -> None:
    resp = client.post("/api/events", json=make_event(seq=3))
    assert resp.status_code == 202 and resp.json() == {"accepted": True, "seq": 3, "persisted": False}
    assert not (run_dir / "events.jsonl").exists()
    # the hub continues numbering after the highest seq it has seen
    assert client.post("/api/events", json=make_event()).json()["seq"] == 4


def test_event_from_other_session_lands_in_that_sessions_file(client: TestClient, run_dir: Path) -> None:
    client.post("/api/events", json=make_event(session="s-other"))
    assert (run_dir.parent / "s-other" / "events.jsonl").exists()


def test_placeholder_when_dist_missing(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200 and "make portal-build" in resp.text
    assert "physics stops the car; the decider explains" in resp.text


# ----- WebSocket ------------------------------------------------------------------------------


def test_ws_snapshot_on_connect_is_capped_at_200(client: TestClient) -> None:
    for i in range(205):
        client.post("/api/events", json=make_event(payload={"text": f"t{i}"}))
    with client.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
    assert snap["op"] == "snapshot"
    assert len(snap["events"]) == 200
    assert snap["events"][0]["payload"]["text"] == "t5"
    assert snap["events"][-1]["seq"] == 205
    assert snap["state"]["events"] == 205


def test_post_event_rebroadcasts_to_ws_client(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["op"] == "snapshot"
        client.post(
            "/api/events",
            json=make_event(
                "verdict", {"request_id": "r1", "stage": "frame", "action": "Deny", "reason": "person"}
            ),
        )
        msg = ws.receive_json()
    assert msg["op"] == "event"
    assert msg["event"]["type"] == "verdict" and msg["event"]["payload"]["action"] == "Deny"


def test_confirm_verdict_tracks_pending_approval(client: TestClient) -> None:
    client.post(
        "/api/events",
        json=make_event(
            "verdict", {"request_id": "r9", "stage": "envelope", "action": "Confirm", "reason": "fast"}
        ),
    )
    pending = client.get("/api/state").json()["pending_approvals"]
    assert [p["request_id"] for p in pending] == ["r9"]
    client.post(
        "/api/events",
        json=make_event("approval", {"request_id": "r9", "decision": "approved", "by": "operator"}),
    )
    assert client.get("/api/state").json()["pending_approvals"] == []


def test_ws_command_routes_to_runtime(client: TestClient, recorder: RecorderRuntime) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"op": "command", "text": "  go forward  ", "beat": "marshal"})
        ack = ws.receive_json()
    assert ack == {"op": "ack", "for": "command", "request_id": "req-test"}
    assert ("submit", "go forward", "marshal") in recorder.calls


def test_ws_approve_routes_to_runtime_adapter(client: TestClient, recorder: RecorderRuntime) -> None:
    client.post(
        "/api/events",
        json=make_event(
            "verdict", {"request_id": "req-known", "stage": "envelope", "action": "Confirm", "reason": "x"}
        ),
    )
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"op": "approve", "request_id": "req-known", "approved": True})
        ack = ws.receive_json()
        ws.send_json({"op": "approve", "request_id": "req-unknown", "approved": False})
        ack2 = ws.receive_json()
    assert ack["resolved"] is True and ack2["resolved"] is False
    assert ("approve", "req-known", True) in recorder.calls
    assert ("approve", "req-unknown", False) in recorder.calls
    assert client.get("/api/state").json()["pending_approvals"] == []


def test_ws_stop_all_preflight_body_ptt_audio(client: TestClient, recorder: RecorderRuntime) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"op": "stop_all"})
        assert ws.receive_json() == {"op": "ack", "for": "stop_all"}
        ws.send_json({"op": "preflight"})
        assert ws.receive_json() == {"op": "ack", "for": "preflight", "go": True}
        ws.send_json({"op": "body", "active": "car"})
        assert ws.receive_json()["active"] == "car"
        ws.send_json({"op": "ptt", "state": "down"})
        assert ws.receive_json()["state"] == "down"
        ws.send_json({"op": "audio", "pcm_b64": "AAAAAA=="})  # 4 bytes, no ack
        ws.send_json({"op": "ptt", "state": "up"})
        assert ws.receive_json()["state"] == "up"
    assert ("stop_all",) in recorder.calls
    assert ("preflight",) in recorder.calls
    assert ("body", "car") in recorder.calls
    assert ("audio", 4) in recorder.calls
    assert client.get("/api/state").json()["body"] == "car"


@pytest.mark.parametrize(
    ("msg", "reason_part"),
    [
        ({"op": "command", "text": "   "}, "empty"),
        ({"op": "approve", "request_id": 1, "approved": True}, "request_id"),
        ({"op": "approve", "request_id": "r", "approved": "yes"}, "approved"),
        ({"op": "body", "active": "mujoco"}, "car"),
        ({"op": "ptt", "state": "held"}, "down"),
        ({"op": "audio", "pcm_b64": "***"}, "base64"),
        ({"op": "audio"}, "pcm_b64"),
        ({"op": "dance"}, "unknown op"),
        ({"nope": 1}, "string op"),
    ],
)
def test_ws_refuses_bad_ops(client: TestClient, msg: dict[str, Any], reason_part: str) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json(msg)
        reply = ws.receive_json()
    assert reply["op"] == "error"
    assert reason_part in reply["reason"]


# ----- frames ---------------------------------------------------------------------------------


def test_frames_endpoint_serves_jpeg_and_refuses_escape(client: TestClient, run_dir: Path) -> None:
    frames = run_dir / "frames"
    frames.mkdir(parents=True)
    (frames / "000123.jpg").write_bytes(JPEG)
    ok = client.get("/api/runs/s-test/frames/000123.jpg")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg" and ok.content == JPEG
    assert client.get("/api/runs/s-test/frames/000999.jpg").status_code == 404
    assert client.get("/api/runs/s-test/frames/..%2F..%2Fevents.jsonl").status_code in (400, 404)
    assert client.get("/api/runs/..%2Fs-test/frames/000123.jpg").status_code in (400, 404)


# ----- refusal table --------------------------------------------------------------------------

REFUSALS = [
    pytest.param({"ts": TS, "payload": {}}, "missing type", id="missing-type"),
    pytest.param({"ts": TS, "type": "dance", "payload": {}}, "unknown type", id="unknown-type"),
    pytest.param({"ts": TS, "type": 7, "payload": {}}, "unknown type", id="non-string-type"),
    pytest.param({"type": "thought", "payload": {}}, "missing ts", id="missing-ts"),
    pytest.param({"ts": "yesterday", "type": "thought", "payload": {}}, "bad ts", id="ts-not-iso"),
    pytest.param({"ts": "2026-10-14T06:52:01", "type": "thought", "payload": {}}, "bad ts", id="ts-no-zone"),
    pytest.param({"ts": 1760000000, "type": "thought", "payload": {}}, "bad ts", id="ts-epoch-number"),
    pytest.param(
        {"ts": TS, "type": "thought", "payload": "hello"}, "payload must be an object", id="payload-str"
    ),
    pytest.param({**THOUGHT, "seq": -1}, "seq must be", id="seq-negative"),
    pytest.param({**THOUGHT, "seq": "1"}, "seq must be", id="seq-string"),
    pytest.param({**THOUGHT, "session": "../x"}, "session must be", id="session-dots"),
    pytest.param({**THOUGHT, "session": ""}, "session must be", id="session-empty"),
    pytest.param({**THOUGHT, "beat": 3}, "beat must be", id="beat-int"),
    pytest.param({**THOUGHT, "source": None}, "source must be", id="source-null"),
    pytest.param([make_event()], "must be a JSON object", id="list-not-object"),
]


@pytest.mark.parametrize(("event", "reason_part"), REFUSALS)
def test_refusal_table_validate_event(event: Any, reason_part: str) -> None:
    parsed, reason = validate_event(event)
    assert parsed is None
    assert reason is not None and reason_part in reason


@pytest.mark.parametrize(("event", "reason_part"), REFUSALS)
def test_refusal_table_http_422_with_reason(
    client: TestClient, event: Any, reason_part: str, run_dir: Path
) -> None:
    resp = client.post("/api/events", json=event)
    assert resp.status_code == 422
    body = resp.json()
    assert body["accepted"] is False and reason_part in body["reason"]
    assert not (run_dir / "events.jsonl").exists()


def test_post_event_not_json(client: TestClient) -> None:
    resp = client.post("/api/events", content=b"not json", headers={"content-type": "application/json"})
    assert resp.status_code == 422 and "not JSON" in resp.json()["reason"]


def test_validate_event_accepts_every_contract_type_and_defaults() -> None:
    for etype in (
        "thought",
        "command",
        "verdict",
        "approval",
        "motion",
        "stop",
        "heartbeat",
        "preflight",
        "frame",
        "voice",
        "led",
        "body",
        "error",
    ):
        parsed, reason = validate_event({"ts": "2026-10-14T06:52:01+00:00", "type": etype})
        assert reason is None and parsed is not None
        assert parsed["payload"] == {} and parsed["beat"] is None and parsed["source"] == "unknown"


# ----- fake runtime through the real app ------------------------------------------------------


def test_fake_runtime_full_sequence_for_a_clear_hop(run_dir: Path, tmp_path: Path) -> None:
    console = ConsoleStream(base_url="http://127.0.0.1:1", password="")
    app = create_app(
        run_dir=run_dir,
        runtime_factory=lambda emit: FakeRuntime(emit, speed=0.0),
        console=console,
        frontend_dist=tmp_path / "nodist",
    )
    with TestClient(app) as tc, tc.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"op": "command", "text": "go forward", "beat": "marshal"})
        stop = recv_until(ws, lambda m: m["op"] == "event" and m["event"]["type"] == "stop", limit=40)
        assert stop["event"]["payload"]["cause"] == "trailing_zero"
        assert stop["event"]["beat"] == "marshal"
    lines = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    types = [e["type"] for e in lines]
    assert types[:4] == ["thought", "command", "verdict", "verdict"]
    verdicts = [e["payload"] for e in lines if e["type"] == "verdict"]
    assert [v["stage"] for v in verdicts] == ["envelope", "frame"]
    assert all(v["action"] == "Proceed" for v in verdicts)
    assert [e["payload"]["state"] for e in lines if e["type"] == "motion"] == ["start", "end"]
    assert types[-1] == "stop" and lines[-1]["payload"]["cause"] == "trailing_zero"
    assert lines[-1]["session"] == "s-test" and lines[-1]["seq"] == len(lines)


def test_fake_runtime_person_denies_and_stops() -> None:
    import asyncio

    events: list[dict[str, Any]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        ev = {"type": etype, "payload": payload}
        events.append(ev)
        return ev

    async def run() -> None:
        fake = FakeRuntime(emit, speed=0.0)
        await fake.submit("go forward, there is a person ahead")
        await asyncio.sleep(0.05)
        await fake.aclose()

    asyncio.run(run())
    verdict = next(e for e in events if e["type"] == "verdict" and e["payload"]["stage"] == "frame")
    assert verdict["payload"]["action"] == "Deny" and verdict["payload"]["class"] == "person_in_frame"
    assert [e["payload"]["cause"] for e in events if e["type"] == "stop"] == ["deny"]
    assert not any(e["type"] == "motion" for e in events)
    assert [e["payload"]["label"] for e in events if e["type"] == "led"] == ["red"]


def test_fake_runtime_confirm_waits_for_operator_then_moves() -> None:
    import asyncio

    events: list[dict[str, Any]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        ev = {"type": etype, "payload": payload}
        events.append(ev)
        return ev

    async def run() -> None:
        fake = FakeRuntime(emit, speed=0.0, approval_timeout_s=100.0)
        rid = await fake.submit("go forward fast")
        for _ in range(50):
            await asyncio.sleep(0.001)
            if rid in fake.status()["pending_approvals"]:
                break
        assert fake.resolve_approval(rid, True) is True
        await asyncio.sleep(0.05)
        await fake.aclose()

    asyncio.run(run())
    types = [e["type"] for e in events]
    assert types.index("approval") < types.index("motion")
    approval = next(e for e in events if e["type"] == "approval")["payload"]
    assert approval["decision"] == "approved" and approval["by"] == "operator"
    assert events[-1]["type"] == "stop" and events[-1]["payload"]["cause"] == "trailing_zero"


def test_fake_runtime_preflight_and_ptt_barge_in() -> None:
    import asyncio

    events: list[dict[str, Any]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        ev = {"type": etype, "payload": payload}
        events.append(ev)
        return ev

    async def run() -> None:
        fake = FakeRuntime(emit, speed=0.0)
        payload = await fake.preflight()
        assert payload["go"] is True and "battery" in payload
        fake._motion = {"request_id": "req-x", "beat": None, "stopped": False}  # pretend a hop is rolling
        await fake.voice_ptt("down")
        await fake.stop_all()
        await fake.aclose()

    asyncio.run(run())
    assert any(e["type"] == "preflight" and e["payload"]["go"] for e in events)
    voice = [e["payload"]["event"] for e in events if e["type"] == "voice"]
    assert voice == ["ptt_down", "barge_in"]
    causes = [e["payload"]["cause"] for e in events if e["type"] == "stop"]
    assert causes == ["barge_in", "operator"]
