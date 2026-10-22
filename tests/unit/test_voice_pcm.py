"""PcmInputStream, FilePcmInput and AudioSink: the microphone-less audio path for the bidi voice agent.

No cloud, no PortAudio, no sockets. A fake clock drives the pacing so the real-time player and the
silence frames run instantly. Physics stops the car; the decider explains; these tests check that
the room's voice reaches the agent only while the key is down and that every press is stamped.
"""

from __future__ import annotations

import asyncio
import base64
import wave
from pathlib import Path

import pytest
from strands.bidi.types.events import (
    BidiAudioDeltaEvent,
    BidiAudioStartEvent,
    BidiBargeInEvent,
    BidiResponseStopEvent,
)
from strands.bidi.types.media import AudioDelta

from deepracer_agent.gate import LocalEventLog, voice_clock
from deepracer_agent.voice_pcm import (
    FRAME_MS,
    MAX_FEED_BYTES,
    SAMPLE_RATE,
    AudioSink,
    FilePcmInput,
    PcmInputStream,
    frame_bytes,
    load_pcm,
    rms_level,
    save_wav,
)

FRAME = frame_bytes()  # 3200 bytes = 100 ms at 16 kHz mono int16


class FakeClock:
    """A clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.sleeps.append(round(s, 4))
        self.t += s
        await asyncio.sleep(0)


class FakeModel:
    def get_audio_config(self):
        return {
            "input": {"sample_rate": 16000, "channels": 1, "format": "pcm"},
            "output": {"sample_rate": 24000, "channels": 1, "format": "pcm"},
        }


class FakeAgent:
    model = FakeModel()


def tone(n_bytes: int, value: int = 1000) -> bytes:
    return value.to_bytes(2, "little", signed=True) * (n_bytes // 2)


@pytest.fixture
def log(tmp_path):
    voice_clock.reset()
    return LocalEventLog(tmp_path, session="s-pcm")


@pytest.fixture
def stream(log):
    clock = FakeClock()
    s = PcmInputStream(log, beat="red_light", clock=clock, sleep=clock.sleep)
    s.clock = clock  # type: ignore[attr-defined]
    return s


async def next_delta(stream: PcmInputStream, timeout: float = 1.0) -> AudioDelta:
    return await asyncio.wait_for(stream(), timeout)


# -- chunking and gating -----------------------------------------------------------------------


async def test_fed_audio_is_rechunked_into_frames_while_pressed(stream, log):
    await stream.start(FakeAgent())
    stream.down()
    assert stream.feed(tone(7000)) == 7000
    d1, d2 = await next_delta(stream), await next_delta(stream)
    assert isinstance(d1, AudioDelta) and d1.format == "pcm"
    assert len(d1.source["bytes"]) == FRAME and len(d2.source["bytes"]) == FRAME
    # the remaining 600 bytes wait for more audio while the key is down
    pending = asyncio.ensure_future(stream())
    await asyncio.sleep(0.01)
    assert not pending.done()
    stream.up()  # release flushes the tail of the word
    tail = await asyncio.wait_for(pending, 1.0)
    assert len(tail.source["bytes"]) == 600
    assert stream.frames_out == 3 and stream.fed_bytes == 7000


async def test_released_key_drops_audio_and_streams_paced_silence(stream, log):
    await stream.start(FakeAgent())
    assert stream.feed(tone(FRAME)) == 0
    assert stream.dropped_bytes == FRAME
    first = await next_delta(stream)
    second = await next_delta(stream)
    assert first.source["bytes"] == bytes(FRAME) and second.source["bytes"] == bytes(FRAME)
    # the second silence frame waited one frame of (fake) real time; the first went out at once
    assert stream.clock.sleeps == [pytest.approx(FRAME_MS / 1000)]
    assert stream.silence_frames_out == 2 and stream.frames_out == 0
    assert log.read("voice") == []  # silence is not an event


async def test_press_interrupts_silence_and_speech_goes_first(stream):
    await stream.start(FakeAgent())
    await next_delta(stream)  # one silence frame, pacing armed
    stream.down()
    stream.feed(tone(FRAME))
    delta = await next_delta(stream)
    assert delta.source["bytes"] == tone(FRAME)


async def test_feed_rejects_oversize_and_trims_torn_samples(stream):
    await stream.start(FakeAgent())
    stream.down()
    with pytest.raises(ValueError, match="exceeds"):
        stream.feed(b"\x00" * (MAX_FEED_BYTES + 2))
    assert stream.feed(b"\x01\x02\x03") == 2  # a torn 16-bit sample is dropped
    assert stream.feed(b"") == 0


async def test_start_checks_the_models_audio_config():
    class Model8k:
        def get_audio_config(self):
            return {"input": {"sample_rate": 8000, "channels": 1, "format": "pcm"}}

    class Agent8k:
        model = Model8k()

    s = PcmInputStream(LocalEventLog(Path("/dev/null").parent, session="x"))
    with pytest.raises(ValueError, match="8000"):
        await s.start(Agent8k())

    class NoAudio:  # a scripted model: no audio config, no complaint
        model = object()

    await s.start(NoAudio())
    assert s.started


async def test_feed_from_another_thread_lands_on_the_loop(stream):
    await stream.start(FakeAgent())
    stream.down()
    await asyncio.to_thread(stream.feed, tone(FRAME))
    delta = await next_delta(stream)
    assert len(delta.source["bytes"]) == FRAME


# -- voice events ------------------------------------------------------------------------------


async def test_ptt_events_count_from_the_press(stream, log):
    t0 = stream.down()
    t1 = stream.up()
    voice = [e["payload"] for e in log.read("voice")]
    assert [v["event"] for v in voice] == ["ptt_down", "ptt_up"]
    assert t0 == 0 == voice[0]["t_ms"] and voice[0]["text"] is None
    assert 0 <= t1 == voice[1]["t_ms"] < 5_000
    assert all(e["beat"] == "red_light" for e in log.read("voice"))
    assert stream.presses == 1 and voice_clock.now_ms() < 5_000  # the clock is marked for later stamps


# -- file player --------------------------------------------------------------------------------


def write_wav(path: Path, pcm: bytes, rate: int = SAMPLE_RATE, channels: int = 1) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return path


def test_load_pcm_reads_16k_mono_wav_and_raw_and_refuses_other_rates(tmp_path):
    pcm = tone(FRAME * 3)
    assert load_pcm(write_wav(tmp_path / "ok.wav", pcm)) == pcm
    (tmp_path / "raw.pcm").write_bytes(pcm)
    assert load_pcm(tmp_path / "raw.pcm") == pcm
    with pytest.raises(ValueError, match="48000 Hz"):
        load_pcm(write_wav(tmp_path / "bad.wav", pcm, rate=48000))
    with pytest.raises(ValueError, match="2 channel"):
        load_pcm(write_wav(tmp_path / "stereo.wav", pcm, channels=2))


def test_save_wav_round_trips(tmp_path):
    pcm = tone(FRAME)
    p = save_wav(tmp_path / "out" / "rover.wav", pcm, sample_rate=24000)
    with wave.open(str(p)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
        assert w.readframes(w.getnframes()) == pcm


async def test_file_player_presses_paces_frames_and_releases(stream, log, tmp_path):
    await stream.start(FakeAgent())
    pcm = tone(FRAME * 10)  # 1.0 s of "speech"
    path = write_wav(tmp_path / "hop.wav", pcm)
    clock = stream.clock
    player = FilePcmInput(stream, tail_ms=300, clock=clock, sleep=clock.sleep)

    deltas: list[AudioDelta] = []

    async def drain():
        while True:
            deltas.append(await stream())

    drainer = asyncio.create_task(drain())
    record = await player.play(path, label="hop")
    play_sleeps = list(clock.sleeps)  # after release the stream paces silence on the same clock
    await asyncio.sleep(0.01)
    drainer.cancel()

    assert record["frames"] == 13 and record["bytes"] == FRAME * 13  # 10 speech + 3 tail frames
    assert record["duration_s"] == pytest.approx(1.3)
    # real-time pacing: 12 waits of one frame each (the first frame goes out at t=0)
    assert len(play_sleeps) == 12 and all(s == pytest.approx(0.1) for s in play_sleeps)
    assert record["elapsed_s"] == pytest.approx(1.2)
    assert record["ptt_down_t_ms"] == 0 and record["ptt_up_t_ms"] >= 0
    speech = [d for d in deltas if any(d.source["bytes"])]
    silence_tail = [d for d in deltas if not any(d.source["bytes"])]
    assert b"".join(d.source["bytes"] for d in speech) == pcm
    assert len(silence_tail) >= 3  # the tail frames, then possibly paced silence after release
    assert [e["payload"]["event"] for e in log.read("voice")] == ["ptt_down", "ptt_up"]
    assert player.played[0]["label"] == "hop"


async def test_file_player_can_stream_without_pressing(stream):
    await stream.start(FakeAgent())
    clock = stream.clock
    player = FilePcmInput(stream, tail_ms=0, clock=clock, sleep=clock.sleep)
    record = await player.play(tone(FRAME * 2), press=False)
    assert record["bytes"] == 0 and record["ptt_down_t_ms"] is None  # released: nothing is heard
    assert stream.dropped_bytes == FRAME * 2


# -- rms ------------------------------------------------------------------------------------------


def test_rms_level():
    assert rms_level(b"") == 0.0
    assert rms_level(bytes(FRAME)) == 0.0
    assert rms_level(tone(FRAME, 16384)) == pytest.approx(0.5, abs=0.001)
    assert rms_level(tone(FRAME, 32767)) == pytest.approx(1.0, abs=0.001)


# -- audio sink -------------------------------------------------------------------------------------


async def test_audio_sink_collects_tracks_speaking_and_fans_out(tmp_path):
    sink = AudioSink(wav_path=tmp_path / "rover.wav")
    await sink.start(FakeAgent())
    assert sink.sample_rate == 24000
    heard: list[bytes] = []
    flushed: list[str] = []
    token = sink.attach(heard.append, lambda: flushed.append("barge"))
    pcm = tone(480)
    await sink(BidiAudioStartEvent("c1"))
    assert sink.speaking.is_set()
    await sink(BidiAudioDeltaEvent(base64.b64encode(pcm).decode(), "pcm", 24000, 1, "c1"))
    await sink(BidiAudioDeltaEvent(base64.b64encode(pcm).decode(), "pcm", 24000, 1, "c1"))
    assert heard == [pcm, pcm] and sink.bytes_heard == 960
    assert sink.seconds_heard() == pytest.approx(960 / 48000)
    await sink(BidiBargeInEvent())
    assert not sink.speaking.is_set() and flushed == ["barge"] and sink.barge_ins == 1
    await sink(BidiResponseStopEvent("r1"))
    assert sink.responses == 1 and sink.spoke_once.is_set()
    sink.detach(token)
    assert sink.listener_count == 0
    await sink.stop()
    with wave.open(str(tmp_path / "rover.wav")) as w:
        assert w.getframerate() == 24000 and w.readframes(w.getnframes()) == pcm + pcm


async def test_audio_sink_drops_a_failing_listener():
    sink = AudioSink(keep_audio=False)

    def bad(_pcm: bytes) -> None:
        raise RuntimeError("socket closed")

    sink.attach(bad)
    await sink(BidiAudioDeltaEvent(base64.b64encode(tone(32)).decode(), "pcm", 16000, 1, "c"))
    assert sink.listener_count == 0 and sink.chunks == []


# -- through the VoiceAgent with the scripted model ------------------------------------------------


async def test_voice_agent_run_pcm_hears_only_pressed_audio_and_the_fake_asr_answers(log, tmp_path):
    from strands import tool

    from deepracer_agent.voice import ScriptedBidiModel, make_voice_agent

    class Runtime:
        stops = 0

        async def stop_all(self):
            self.stops += 1

    runtime = Runtime()

    @tool
    def stop_deepracer() -> str:
        """Stop (fake)."""
        return "stopped"

    model = ScriptedBidiModel({"stop": ("stop_deepracer", {}, "Stopped.")}, audio_transcripts=["stop"])
    lines: list[str] = []
    va = make_voice_agent([stop_deepracer], None, runtime, model=model, event_log=log, out=lines.append)
    clock = FakeClock()
    pcm = PcmInputStream(log, clock=clock, sleep=clock.sleep)
    sink = AudioSink(keep_audio=False)
    task = asyncio.create_task(va.run_pcm(pcm, outputs=[sink]))
    for _ in range(100):
        await asyncio.sleep(0.005)
        if pcm.started and va.pcm is pcm:
            break
    assert va.feed_audio(tone(FRAME)) == 0  # released: dropped
    va.ptt_down()
    assert va.feed_audio(tone(FRAME)) == FRAME
    va.ptt_up()
    # the ScriptedBidiModel "hears" the utterance once the silence after it arrives
    for _ in range(200):
        await asyncio.sleep(0.005)
        if any(line.startswith("rover>") for line in lines):
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "you> stop" in lines and any("Stopped." in line for line in lines)
    assert model.utterances == 1 and model.audio_bytes >= FRAME
    voice = [e["payload"]["event"] for e in log.read("voice")]
    assert voice[:2] == ["ptt_down", "ptt_up"] and "transcript" in voice
    assert va.pcm is None  # detached once the run ends
