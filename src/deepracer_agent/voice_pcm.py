"""PCM push-to-talk for the rover's bidi voice agent: audio from a queue, not from PortAudio.

The browser (Pit Wall portal) and the rehearsal script both produce 16 kHz mono 16-bit PCM and
have no microphone device the ``strands.bidi.io.AudioIO`` class could open. ``PcmInputStream``
is the ``strands.bidi`` ``InputStream`` that stands in for the microphone: callers ``feed()`` it
raw PCM, it hands the agent ``AudioDelta`` frames of a fixed length, and it does so only while
push-to-talk is pressed. Between presses it streams paced silence, exactly as an open microphone
in a quiet room would, which is what Nova Sonic needs to end-point the utterance (its
server-side turn detection looks for silence after speech) and what keeps the audio content
open so a stop said over the rover's narration is heard as a barge-in. Every press and release
is written to the event log as ``voice`` ``ptt_down``/``ptt_up`` with ``t_ms`` counted from the
press (``gate.voice_clock``, CONTRACTS section 4).

``FilePcmInput`` plays a WAV or raw PCM file into the stream at real time (press, frames at
100 ms, release). ``AudioSink`` is the matching ``OutputStream`` that collects the rover's spoken
audio, knows whether the rover is speaking right now, fans the PCM out to listeners (the browser)
and can save a WAV for the evidence folder. Physics stops the car; the decider explains; this
file only carries the room's voice to the agent and the agent's voice back.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import threading
import time
import wave
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from strands.bidi.types.events import (
    BidiAudioDeltaEvent,
    BidiAudioStartEvent,
    BidiAudioStopEvent,
    BidiBargeInEvent,
    BidiOutputEvent,
    BidiResponseStopEvent,
    BidiTextStartEvent,
)
from strands.bidi.types.media import AudioDelta

from .gate import EventSink, resolve_event_log, voice_clock

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1
FRAME_MS = 100
MAX_FEED_BYTES = 64 * 1024  # one browser frame is 3200 bytes; anything bigger is a bug, not audio

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


def frame_bytes(frame_ms: int = FRAME_MS, sample_rate: int = SAMPLE_RATE) -> int:
    """Bytes in one frame of 16-bit mono PCM."""
    return int(sample_rate * frame_ms / 1000) * SAMPLE_WIDTH * CHANNELS


def rms_level(pcm: bytes) -> float:
    """Root-mean-square level of 16-bit PCM, 0.0 (silence) to 1.0 (full scale)."""
    n = len(pcm) // SAMPLE_WIDTH
    if n == 0:
        return 0.0
    import array

    samples = array.array("h")
    samples.frombytes(pcm[: n * SAMPLE_WIDTH])
    acc = 0
    for s in samples:
        acc += s * s
    return min(1.0, (acc / n) ** 0.5 / 32768.0)


def load_pcm(path: str | Path) -> bytes:
    """Read a WAV (must be 16 kHz mono 16-bit) or a raw ``.pcm``/``.raw`` file as PCM bytes."""
    p = Path(path)
    if p.suffix.lower() != ".wav":
        return p.read_bytes()
    with wave.open(str(p), "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        if (rate, channels, width) != (SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH):
            raise ValueError(
                f"{p.name}: need {SAMPLE_RATE} Hz mono 16-bit PCM, got {rate} Hz, "
                f"{channels} channel(s), {width * 8}-bit "
                f"(macOS: say -o x.wav --file-format=WAVE --data-format=LEI16@16000 'text')"
            )
        return wav.readframes(wav.getnframes())


def save_wav(path: str | Path, pcm: bytes, *, sample_rate: int = SAMPLE_RATE) -> Path:
    """Write mono 16-bit PCM to a WAV file (evidence: the rover's spoken audio)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return p


# -- input ------------------------------------------------------------------------------------


class PcmInputStream:
    """``strands.bidi`` ``InputStream`` fed by ``feed()`` with 16 kHz mono 16-bit PCM.

    The agent's input task awaits ``__call__`` in a loop; each call returns one ``AudioDelta``:

    * pressed and at least a frame buffered: the next ``frame_ms`` of fed audio;
    * pressed, buffer short: waits for more audio (``feed`` wakes it);
    * released with a partial frame left: that remainder, so the end of the word is not lost;
    * released and empty: one frame of silence, paced at ``frame_ms`` real time.

    ``feed`` while released drops the bytes and returns 0: push-to-talk means nothing is heard
    until the key is down. ``down()``/``up()`` write the ``voice`` events and mark
    ``gate.voice_clock`` so every later voice stamp counts from the press.

    Args:
        event_log: Event sink; resolved lazily when ``None``.
        beat: Beat name stamped on the events.
        frame_ms: Frame length handed to the model (100 ms is what the browser sends).
        sample_rate: Must match the model's input rate (Nova Sonic default 16 kHz).
        clock / sleep: Injectable for tests (a fake clock makes the silence pacing instant).
    """

    def __init__(
        self,
        event_log: EventSink | None = None,
        *,
        beat: str | None = None,
        frame_ms: int = FRAME_MS,
        sample_rate: int = SAMPLE_RATE,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._event_log = event_log
        self.beat = beat
        self.frame_ms = frame_ms
        self.sample_rate = sample_rate
        self.frame_bytes = frame_bytes(frame_ms, sample_rate)
        self._clock = clock
        self._sleep = sleep
        self.pressed = asyncio.Event()
        self._buffer = bytearray()
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_silence_at: float | None = None
        self.started = False
        self.fed_bytes = 0
        self.dropped_bytes = 0
        self.frames_out = 0
        self.silence_frames_out = 0
        self.level = 0.0
        self.presses = 0

    @property
    def event_log(self) -> EventSink:
        if self._event_log is None:
            self._event_log = resolve_event_log()
        return self._event_log

    # -- push to talk -------------------------------------------------------------------

    def down(self) -> int:
        """Press: the voice clock restarts at 0 and audio starts to flow."""
        t = voice_clock.mark()
        self.pressed.set()
        self.presses += 1
        self._wake.set()
        self.event_log.emit("voice", {"event": "ptt_down", "text": None, "t_ms": t}, beat=self.beat)
        return t

    def up(self) -> int:
        """Release: the tail of the buffer is flushed, then silence resumes."""
        t = voice_clock.now_ms()
        self.pressed.clear()
        self._wake.set()
        self.event_log.emit("voice", {"event": "ptt_up", "text": None, "t_ms": t}, beat=self.beat)
        return t

    def feed(self, pcm: bytes) -> int:
        """Queue ``pcm`` for the model. Returns the bytes accepted (0 while released).

        Safe to call from another thread once the stream has started (the agent's loop is used).
        """
        if not pcm:
            return 0
        if len(pcm) > MAX_FEED_BYTES:
            raise ValueError(f"audio chunk of {len(pcm)} bytes exceeds {MAX_FEED_BYTES}")
        if len(pcm) % SAMPLE_WIDTH:
            pcm = pcm[: len(pcm) - 1]  # a torn 16-bit sample is never audio
        loop = self._loop
        if loop is not None and not _in_loop(loop):
            loop.call_soon_threadsafe(self._feed_in_loop, bytes(pcm))
            return len(pcm)
        return self._feed_in_loop(bytes(pcm))

    def _feed_in_loop(self, pcm: bytes) -> int:
        if not self.pressed.is_set():
            self.dropped_bytes += len(pcm)
            return 0
        self._buffer += pcm
        self.fed_bytes += len(pcm)
        self.level = rms_level(pcm)
        self._wake.set()
        return len(pcm)

    # -- InputStream ----------------------------------------------------------------------

    async def start(self, agent: Any) -> None:
        """Check the model takes PCM at our rate (models without an audio config are left alone)."""
        self._loop = asyncio.get_running_loop()
        get_config = getattr(getattr(agent, "model", None), "get_audio_config", None)
        if callable(get_config):
            cfg = get_config()["input"]
            fmt, rate, channels = cfg.get("format"), cfg.get("sample_rate"), cfg.get("channels", 1)
            if fmt != "pcm":
                raise ValueError(f"PcmInputStream sends signed 16-bit PCM, the model wants {fmt}")
            if rate != self.sample_rate:
                raise ValueError(f"PcmInputStream is {self.sample_rate} Hz; the model takes {rate} Hz")
            if channels != CHANNELS:
                raise ValueError(f"PcmInputStream is mono; the model's input wants {channels} channels")
        self.started = True
        self._next_silence_at = None

    async def stop(self) -> None:
        self.started = False
        self._buffer.clear()
        self._wake.set()

    async def __call__(self) -> AudioDelta:
        while True:
            if self.pressed.is_set():
                if len(self._buffer) >= self.frame_bytes:
                    return self._take(self.frame_bytes)
                self._wake.clear()
                await self._wake.wait()
                continue
            if self._buffer:
                return self._take(len(self._buffer))  # the tail of the word after release
            await self._pace_silence()
            if self.pressed.is_set() or self._buffer:
                continue  # a press landed during the wait; speech comes first
            self.silence_frames_out += 1
            self.level = 0.0
            return AudioDelta(format="pcm", source={"bytes": bytes(self.frame_bytes)})

    def _take(self, n: int) -> AudioDelta:
        chunk = bytes(self._buffer[:n])
        del self._buffer[:n]
        self.frames_out += 1
        self._next_silence_at = None
        return AudioDelta(format="pcm", source={"bytes": chunk})

    async def _pace_silence(self) -> None:
        """Hold one frame's worth of real time between silence frames, interruptible by a press."""
        now = self._clock()
        if self._next_silence_at is None or self._next_silence_at < now - 1.0:
            self._next_silence_at = now
        wait = self._next_silence_at - now
        self._next_silence_at += self.frame_ms / 1000
        if wait <= 0:
            return
        if self._sleep is not asyncio.sleep:
            await self._sleep(wait)  # tests: a fake clock advances instead of waiting
            return
        self._wake.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._wake.wait(), wait)  # a press cuts the wait short

    def stats(self) -> dict[str, Any]:
        return {
            "fed_bytes": self.fed_bytes,
            "dropped_bytes": self.dropped_bytes,
            "frames_out": self.frames_out,
            "silence_frames_out": self.silence_frames_out,
            "presses": self.presses,
            "pressed": self.pressed.is_set(),
        }


def _in_loop(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


# -- file player --------------------------------------------------------------------------------


class FilePcmInput:
    """Plays a WAV or raw PCM file into a :class:`PcmInputStream` at real time.

    ``play`` presses, feeds one ``frame_ms`` frame every ``frame_ms`` of wall time (so Nova Sonic
    sees speech at the pace a person speaks it), then releases. ``tail_ms`` of silence is
    appended before the release so the model's end-pointer sees the word end while the key
    is still down, like a presenter who pauses before letting go.
    """

    def __init__(
        self,
        stream: PcmInputStream,
        *,
        frame_ms: int = FRAME_MS,
        tail_ms: int = 300,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.stream = stream
        self.frame_ms = frame_ms
        self.tail_ms = tail_ms
        self._clock = clock
        self._sleep = sleep
        self.played: list[dict[str, Any]] = []

    async def play(
        self, source: str | Path | bytes, *, press: bool = True, label: str | None = None
    ) -> dict[str, Any]:
        """Stream ``source`` (a path or PCM bytes) at real time; returns the play record."""
        pcm = source if isinstance(source, bytes | bytearray) else load_pcm(source)
        pcm = bytes(pcm)
        if self.tail_ms:
            pcm += bytes(frame_bytes(self.tail_ms, self.stream.sample_rate))
        size = frame_bytes(self.frame_ms, self.stream.sample_rate)
        frames = [pcm[i : i + size] for i in range(0, len(pcm), size)]
        t_down = self.stream.down() if press else None
        start = self._clock()
        sent = 0
        for i, frame in enumerate(frames):
            target = start + i * self.frame_ms / 1000
            now = self._clock()
            if target > now:
                await self._sleep(target - now)
            sent += self.stream.feed(frame)
        elapsed = self._clock() - start
        t_up = self.stream.up() if press else None
        record = {
            "label": label or (str(source) if not isinstance(source, bytes | bytearray) else "bytes"),
            "frames": len(frames),
            "bytes": sent,
            "duration_s": round(len(pcm) / (self.stream.sample_rate * SAMPLE_WIDTH), 3),
            "elapsed_s": round(elapsed, 3),
            "ptt_down_t_ms": t_down,
            "ptt_up_t_ms": t_up,
        }
        self.played.append(record)
        return record


# -- output -------------------------------------------------------------------------------------

Listener = Callable[[bytes], Any]


class AudioSink:
    """``OutputStream`` for the rover's voice: collects PCM, tracks speaking, fans out to listeners.

    ``speaking`` is set from the first audio (or text) of a response to its stop or a barge-in,
    so a script can wait for "the rover is talking" before speaking over it. ``listeners`` get
    every raw PCM chunk (the portal sends them to the browser as binary frames); on a barge-in
    they get ``on_barge_in`` so they can flush their playback. ``wav_path`` saves everything
    heard to one WAV at ``stop()``.
    """

    def __init__(self, *, wav_path: str | Path | None = None, keep_audio: bool = True) -> None:
        self.wav_path = Path(wav_path) if wav_path else None
        self.keep_audio = keep_audio or wav_path is not None
        self.chunks: list[bytes] = []
        self.bytes_heard = 0
        self.sample_rate = SAMPLE_RATE
        self.speaking = asyncio.Event()
        self.spoke_once = asyncio.Event()
        self.responses = 0
        self.barge_ins = 0
        self.audio_starts = 0  # one per spoken response: wait for a *new* one before talking over it
        self._listeners: dict[int, Listener] = {}
        self._barge_listeners: dict[int, Callable[[], Any]] = {}
        self._next = 0
        self._lock = threading.Lock()
        self.last_audio_at: float | None = None

    def attach(self, on_audio: Listener, on_barge_in: Callable[[], Any] | None = None) -> int:
        with self._lock:
            self._next += 1
            self._listeners[self._next] = on_audio
            if on_barge_in is not None:
                self._barge_listeners[self._next] = on_barge_in
            return self._next

    def detach(self, token: int) -> None:
        with self._lock:
            self._listeners.pop(token, None)
            self._barge_listeners.pop(token, None)

    @property
    def listener_count(self) -> int:
        return len(self._listeners)

    async def start(self, agent: Any) -> None:
        get_config = getattr(getattr(agent, "model", None), "get_audio_config", None)
        if callable(get_config):
            self.sample_rate = int(get_config()["output"].get("sample_rate", SAMPLE_RATE))

    async def stop(self) -> None:
        self.speaking.clear()
        if self.wav_path is not None and self.chunks:
            save_wav(self.wav_path, b"".join(self.chunks), sample_rate=self.sample_rate)

    async def __call__(self, event: BidiOutputEvent) -> None:
        if isinstance(event, BidiAudioDeltaEvent):
            pcm = base64.b64decode(event.audio)
            self.bytes_heard += len(pcm)
            self.last_audio_at = time.monotonic()
            if self.keep_audio:
                self.chunks.append(pcm)
            if not self.speaking.is_set():
                self.speaking.set()
                self.spoke_once.set()
            await self._fan_out(pcm)
        elif isinstance(event, BidiAudioStartEvent | BidiTextStartEvent):
            self.audio_starts += 1
            self.speaking.set()
            self.spoke_once.set()
        elif isinstance(event, BidiBargeInEvent):
            self.barge_ins += 1
            self.speaking.clear()
            for cb in list(self._barge_listeners.values()):
                await _call(cb)
        elif isinstance(event, BidiAudioStopEvent | BidiResponseStopEvent):
            if isinstance(event, BidiResponseStopEvent):
                self.responses += 1
            self.speaking.clear()

    async def _fan_out(self, pcm: bytes) -> None:
        dead: list[int] = []
        for token, cb in list(self._listeners.items()):
            try:
                await _call(cb, pcm)
            except Exception as exc:
                logger.debug("audio listener %s failed: %s", token, exc)
                dead.append(token)
        for token in dead:
            self.detach(token)

    def pcm(self) -> bytes:
        return b"".join(self.chunks)

    def seconds_heard(self) -> float:
        return self.bytes_heard / (self.sample_rate * SAMPLE_WIDTH)


async def _call(cb: Callable[..., Any], *args: Any) -> None:
    result = cb(*args)
    if asyncio.iscoroutine(result) or isinstance(result, asyncio.Future):
        await result


__all__ = [
    "CHANNELS",
    "FRAME_MS",
    "MAX_FEED_BYTES",
    "SAMPLE_RATE",
    "SAMPLE_WIDTH",
    "AudioSink",
    "FilePcmInput",
    "PcmInputStream",
    "frame_bytes",
    "load_pcm",
    "rms_level",
    "save_wav",
]
