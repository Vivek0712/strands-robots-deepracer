"""The portal's binary audio socket (``WS /ws/audio``) and the adapter's lazy voice, against fakes.

A recorder runtime stands in for the agent; a fake voice agent stands in for Nova Sonic. No cloud,
no microphone, no sockets to a car. Physics stops the car; the decider explains; these tests check
that the browser's push-to-talk audio reaches the runtime only as the contract says.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # portal/ is a plain package at the repo root, not installed
    sys.path.insert(0, str(REPO_ROOT))

from deepracer_agent.gate import LocalEventLog, voice_clock  # noqa: E402
from deepracer_agent.voice_pcm import AudioSink, PcmInputStream  # noqa: E402
from portal.backend.app import MAX_AUDIO_FRAME, create_app  # noqa: E402
from portal.backend.console import ConsoleStream  # noqa: E402
from portal.backend.runtime_adapter import RealRuntime  # noqa: E402

FRAME = b"\x01\x00" * 1600  # 100 ms of 16 kHz mono int16, not silence


class AudioRecorder:
    """Runtime stand-in with an ``audio_sink`` the route can attach to and a ``voice_status``."""

    name = "recorder"

    def __init__(self) -> None:
        self.body = "sim"
        self.calls: list[tuple[Any, ...]] = []
        self.audio_sink = AudioSink(keep_audio=False)
        self.audio_sink.sample_rate = 24000

    async def submit(self, text: str, *, beat: str | None = None) -> str:
        self.calls.append(("submit", text, beat))
        return "req-test"

    async def stop_all(self) -> None:
        self.calls.append(("stop_all",))

    async def preflight(self) -> dict[str, Any]:
        return {"go": True}

    def status(self) -> dict[str, Any]:
        return {"body": self.body}

    def voice_status(self) -> dict[str, Any]:
        return {"state": "live", "error": None, "pressed": False}

    def resolve_approval(self, request_id: str, approved: bool) -> bool:
        return True

    async def set_body(self, active: str) -> None:
        self.body = active

    async def voice_ptt(self, state: str) -> None:
        self.calls.append(("ptt", state))

    async def voice_audio(self, pcm: bytes) -> None:
        self.calls.append(("audio", len(pcm)))

    async def aclose(self) -> None:
        self.calls.append(("aclose",))


@pytest.fixture
def recorder() -> AudioRecorder:
    return AudioRecorder()


@pytest.fixture
def client(tmp_path: Path, recorder: AudioRecorder) -> TestClient:
    console = ConsoleStream(base_url="http://127.0.0.1:1", password="")
    app = create_app(
        run_dir=tmp_path / "runs" / "s-audio",
        runtime=recorder,
        console=console,
        frontend_dist=tmp_path / "nodist",
    )
    with TestClient(app) as tc:
        yield tc


def test_audio_socket_greets_with_rate_and_voice_status(client: TestClient) -> None:
    with client.websocket_connect("/ws/audio") as ws:
        hello = ws.receive_json()
    assert hello["op"] == "audio_ready"
    assert hello["sample_rate"] == 24000 and hello["max_frame"] == MAX_AUDIO_FRAME
    assert hello["voice"]["state"] == "live"


def test_binary_frames_reach_voice_audio_and_ptt_rides_the_same_socket(
    client: TestClient, recorder: AudioRecorder
) -> None:
    with client.websocket_connect("/ws/audio") as ws:
        ws.receive_json()
        ws.send_json({"op": "ptt", "state": "down"})
        ack = ws.receive_json()
        assert ack["op"] == "ack" and ack["for"] == "ptt" and ack["state"] == "down"
        assert ack["voice"]["state"] == "live"
        ws.send_bytes(FRAME)
        ws.send_bytes(FRAME)
        ws.send_bytes(b"")  # an empty frame is ignored, not an error
        ws.send_json({"op": "ptt", "state": "up"})
        assert ws.receive_json()["state"] == "up"
        ws.send_json({"op": "ping"})
        assert ws.receive_json()["op"] == "pong"
    calls = [c for c in recorder.calls if c[0] in ("ptt", "audio")]
    assert calls == [("ptt", "down"), ("audio", 3200), ("audio", 3200), ("ptt", "up")]


def test_oversize_frame_bad_json_and_unknown_ops_are_refused(
    client: TestClient, recorder: AudioRecorder
) -> None:
    with client.websocket_connect("/ws/audio") as ws:
        ws.receive_json()
        ws.send_bytes(b"\x00" * (MAX_AUDIO_FRAME + 2))
        big = ws.receive_json()
        ws.send_text("not json")
        bad = ws.receive_json()
        ws.send_json({"op": "ptt", "state": "held"})
        held = ws.receive_json()
        ws.send_json({"op": "dance"})
        unknown = ws.receive_json()
    assert big["op"] == "error" and "over" in big["reason"]
    assert bad["op"] == "error" and "JSON" in bad["reason"]
    assert held["op"] == "error" and "down" in held["reason"]
    assert unknown["op"] == "error" and "unknown op" in unknown["reason"]
    assert not any(c[0] == "audio" for c in recorder.calls)


def test_rover_audio_fans_out_to_the_browser_and_barge_in_flushes(
    client: TestClient, recorder: AudioRecorder
) -> None:
    import base64

    from strands.bidi.types.events import BidiAudioDeltaEvent, BidiBargeInEvent

    sink = recorder.audio_sink
    pcm = b"\x10\x00" * 240
    with client.websocket_connect("/ws/audio") as ws:
        ws.receive_json()
        assert sink.listener_count == 1
        # the sink runs on the app's loop (the voice task would call it there); the portal does the same
        client.portal.call(sink, BidiAudioDeltaEvent(base64.b64encode(pcm).decode(), "pcm", 24000, 1, "c1"))
        assert ws.receive_bytes() == pcm
        client.portal.call(sink, BidiBargeInEvent())
        assert ws.receive_json() == {"op": "barge_in"}
    assert sink.listener_count == 0  # detached on close


def test_disconnect_mid_press_releases_ptt(client: TestClient, recorder: AudioRecorder) -> None:
    with client.websocket_connect("/ws/audio") as ws:
        ws.receive_json()
        ws.send_json({"op": "ptt", "state": "down"})
        ws.receive_json()
        ws.send_bytes(FRAME)
    # the socket closed while held: the route releases so the agent is not left listening to nothing
    assert recorder.calls[-1] == ("ptt", "up")


def test_main_socket_audio_op_still_works(client: TestClient, recorder: AudioRecorder) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"op": "audio", "pcm_b64": "AAAAAA=="})
        ws.send_json({"op": "ping"})
        assert ws.receive_json()["op"] == "pong"
    assert ("audio", 4) in recorder.calls


# -- the adapter's lazy voice --------------------------------------------------------------------


class FakeVoice:
    """Stands in for ``VoiceAgent``: ``run_pcm`` marks the stream started and waits to be cancelled."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.pcm: PcmInputStream | None = None
        self.outputs: list[Any] = []
        self.runs = 0

    async def run_pcm(self, pcm: PcmInputStream, *, outputs=()) -> PcmInputStream:
        self.runs += 1
        self.pcm = pcm
        self.outputs = list(outputs)
        if self.fail is not None:
            raise self.fail
        await pcm.start(type("Agent", (), {"model": object()})())
        try:
            await asyncio.Event().wait()
        finally:
            self.pcm = None
        return pcm


class InnerRuntime:
    def status(self) -> dict[str, Any]:
        return {"body": "sim"}

    def close(self) -> None:
        return


async def test_real_runtime_starts_voice_on_first_press_feeds_pcm_and_idles_out(tmp_path: Path) -> None:
    voice_clock.reset()
    log = LocalEventLog(tmp_path, session="s-adapter")
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        events.append((etype, payload))
        return {"type": etype, "payload": payload}

    fake = FakeVoice()
    sink = AudioSink(keep_audio=False)
    made: list[PcmInputStream] = []

    def factory():
        pcm = PcmInputStream(log)
        made.append(pcm)
        return fake, pcm

    rt = RealRuntime(
        InnerRuntime(), None, None, emit, "sim", voice_factory=factory, audio_sink=sink, voice_idle_s=0.05
    )
    assert rt.voice_status()["state"] == "idle"
    await rt.voice_ptt("down")
    assert rt.voice_status()["state"] == "starting" and rt.voice_status()["pressed"] is True
    await asyncio.sleep(0)  # the voice task gets its first turn
    assert fake.runs == 1
    await rt.voice_audio(FRAME)  # buffered by the pressed stream even before the connection is up
    for _ in range(100):
        await asyncio.sleep(0.005)
        if rt.voice_status()["state"] == "live":
            break
    assert rt.voice_status()["state"] == "live" and fake.outputs == [sink]
    assert made[0].fed_bytes == len(FRAME) and made[0].pressed.is_set()
    await rt.voice_ptt("up")
    assert not made[0].pressed.is_set()
    voice_events = [e["payload"]["event"] for e in log.read("voice")]
    assert voice_events == ["ptt_down", "ptt_up"]
    assert ("thought", {"text": "voice: Nova Sonic connected, push-to-talk live"}) in events
    # idle: the connection is dropped and the next press opens a new one
    for _ in range(100):
        await asyncio.sleep(0.01)
        if rt.voice_status()["state"] == "idle":
            break
    assert rt.voice_status()["state"] == "idle" and fake.pcm is None
    await rt.voice_ptt("down")
    await asyncio.sleep(0)
    assert fake.runs == 2 and len(made) == 2
    await rt.aclose()
    assert rt.voice_status()["state"] == "idle"


async def test_real_runtime_reports_a_voice_that_fails_to_start(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="s-adapter-err")
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        events.append((etype, payload))
        return {}

    fake = FakeVoice(fail=RuntimeError("AccessDeniedException: no Nova Sonic for you"))
    rt = RealRuntime(
        InnerRuntime(), None, None, emit, "sim", voice_factory=lambda: (fake, PcmInputStream(log))
    )
    await rt.voice_ptt("down")
    for _ in range(100):
        await asyncio.sleep(0.005)
        if rt.voice_status()["state"] == "error":
            break
    status = rt.voice_status()
    assert status["state"] == "error" and "AccessDeniedException" in status["error"]
    assert any(e[0] == "error" and e[1]["where"] == "portal.voice" for e in events)
    await rt.voice_ptt("up")  # no stream any more: the marker still reaches the screen
    assert ("voice", {"event": "ptt_up", "text": None, "t_ms": 0}) in events
    await rt.aclose()


async def test_real_runtime_without_voice_marks_ptt_only(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def emit(etype: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        events.append((etype, payload))
        return {}

    rt = RealRuntime(InnerRuntime(), None, None, emit, "sim")
    assert rt.voice_status()["state"] == "off"
    await rt.voice_ptt("down")
    await rt.voice_audio(FRAME)
    await rt.voice_ptt("up")
    assert [e[1]["event"] for e in events if e[0] == "voice"] == ["ptt_down", "ptt_up"]
    assert rt.status()["voice"]["state"] == "off"
