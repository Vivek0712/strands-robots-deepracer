"""Push-to-talk voice for the rover on ``strands.bidi``, with a text console that is the same agent.

The presenter holds a key, speaks, and lets go; Nova Sonic hears the words, the Strands bidi
agent calls the same gated tools the text console uses, and the rover answers in its own
voice. Every press and release is written to the event log with a millisecond stamp, so the
screen can show when the human spoke. If the presenter talks over the rover mid-sentence,
the ``BargeInStop`` hook stops the wheels and records the barge-in and stop times (the Red
Light beat). ``--text`` drives the identical agent from stdin and prints the identical
transcript, which is the fallback when the hall's internet dies. Physics stops the car; the
decider explains; this file is how the room talks to it.

Classes used from ``strands.bidi`` (never ``strands.experimental.bidi``): ``BidiAgent``,
``models.bedrock.BedrockNovaSonicModel`` (model id ``amazon.nova-2-5-sonic``), ``io.AudioIO``
(lazy; needs ``strands-agents[bidi-pyaudio]`` and PortAudio) or, without a microphone device,
:class:`deepracer_agent.voice_pcm.PcmInputStream` (the portal's browser PTT and the rehearsal
script feed it 16 kHz PCM), ``hooks.BidiBargeInEvent`` and the ``types.events`` output events.
The decider gate is attached with
``strands.interventions.registry.InterventionRegistry`` because ``BidiAgent`` has no
``interventions=`` argument; Confirm is resolved inline through the ``ApprovalBroker`` since
bidi does not support tool interrupts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import AsyncGenerator, Callable, Iterable
from typing import Any

from strands.bidi import BidiAgent
from strands.bidi.models.model import BidiModel
from strands.bidi.types.content import BidiMessage
from strands.bidi.types.events import (
    BidiBargeInEvent,
    BidiConnectionStartEvent,
    BidiOutputEvent,
    BidiResponseStartEvent,
    BidiResponseStopEvent,
    BidiTextBlockEvent,
    BidiTextDeltaEvent,
    BidiTextStartEvent,
    BidiTextStopEvent,
    BidiToolUseBlocksEvent,
    BidiTranscriptBlockEvent,
    BidiTranscriptStartEvent,
)
from strands.bidi.types.media import AudioDelta
from strands.interventions import InterventionHandler
from strands.interventions.registry import InterventionRegistry
from strands.types.tools import ToolResultBlock, ToolSpec, ToolUse

from .events import one_line
from .gate import BargeInStop, EventSink, resolve_event_log, voice_clock
from .prompts import system_prompt_for
from .voice_pcm import PcmInputStream

logger = logging.getLogger(__name__)

NOVA_SONIC_MODEL_ID = "amazon.nova-2-5-sonic"
DEFAULT_REGION = "us-east-1"
RESPONSE_TIMEOUT_S = 60.0

Printer = Callable[[str], None]


# -- transcript -------------------------------------------------------------------------------


class TranscriptPrinter:
    """OutputStream that prints ``you>`` / ``rover>`` lines and logs ``voice`` transcript events.

    Used unchanged in audio and text mode so the two render the identical transcript.
    """

    def __init__(self, event_log: EventSink, out: Printer = print, *, beat: str | None = None) -> None:
        self.event_log = event_log
        self.out = out
        self.beat = beat
        self.lines: list[tuple[str, str]] = []
        self._open: dict[str, str] = {}

    async def start(self, agent: BidiAgent) -> None:
        return

    async def stop(self) -> None:
        return

    def _say(self, role: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        prefix = "you" if role == "user" else "rover"
        self.lines.append((prefix, text))
        self.out(f"{prefix}> {text}")
        if role == "user":
            self.event_log.emit(
                "voice", {"event": "transcript", "text": text, "t_ms": voice_clock.now_ms()}, beat=self.beat
            )
        else:
            self.event_log.emit("thought", {"text": one_line(f"rover: {text}")}, beat=self.beat)

    async def __call__(self, event: BidiOutputEvent) -> None:
        if isinstance(event, BidiTranscriptStartEvent | BidiTextStartEvent):
            self._open[event.content_id] = getattr(event, "role", "assistant")
        elif isinstance(event, BidiTranscriptBlockEvent):
            self._open.pop(event.content_id, None)
            self._say(event.role, event.transcript)
        elif isinstance(event, BidiTextBlockEvent):
            self._open.pop(event.content_id, None)
            self._say("assistant", event.text)
        elif isinstance(event, BidiToolUseBlocksEvent):
            for tool_use in event.tool_uses:
                args = json.dumps(tool_use.get("input", {}), separators=(",", ":"))
                self.out(f"tool> {tool_use['name']} {args}")
                self.event_log.emit("thought", {"text": f"calling {tool_use['name']} {args}"}, beat=self.beat)
        elif isinstance(event, BidiBargeInEvent):
            self.out("-- barge-in --")


# -- push to talk -----------------------------------------------------------------------------


class PushToTalk:
    """Wraps an audio ``InputStream`` so microphone audio reaches the model only while pressed.

    ``down()``/``up()`` write ``voice`` ``ptt_down``/``ptt_up`` events; ``t_ms`` counts from the press.
    """

    def __init__(self, inner: Any, event_log: EventSink, *, beat: str | None = None) -> None:
        self._inner = inner
        self.event_log = event_log
        self.beat = beat
        self.pressed = asyncio.Event()

    def down(self) -> int:
        t = voice_clock.mark()
        self.pressed.set()
        self.event_log.emit("voice", {"event": "ptt_down", "text": None, "t_ms": t}, beat=self.beat)
        return t

    def up(self) -> int:
        t = voice_clock.now_ms()
        self.pressed.clear()
        self.event_log.emit("voice", {"event": "ptt_up", "text": None, "t_ms": t}, beat=self.beat)
        return t

    async def start(self, agent: BidiAgent) -> None:
        start = getattr(self._inner, "start", None)
        if start:
            await start(agent)

    async def stop(self) -> None:
        stop = getattr(self._inner, "stop", None)
        if stop:
            await stop()

    async def __call__(self) -> Any:
        while True:
            chunk = await self._inner()
            if self.pressed.is_set():
                return chunk
            # Not pressed: drop the chunk and keep the device draining.


# -- the agent --------------------------------------------------------------------------------


class VoiceAgent:
    """One ``BidiAgent`` plus the gate, the barge-in hook, PTT markers and a transcript."""

    def __init__(
        self,
        agent: BidiAgent,
        *,
        gate: InterventionHandler | None,
        barge_in: BargeInStop,
        event_log: EventSink,
        beat: str | None = None,
        out: Printer = print,
    ) -> None:
        self.agent = agent
        self.gate = gate
        self.barge_in = barge_in
        self.event_log = event_log
        self.beat = beat
        self.transcript = TranscriptPrinter(event_log, out, beat=beat)
        self._registry = InterventionRegistry([gate], agent.hooks) if gate is not None else None
        self._events: AsyncGenerator[BidiOutputEvent, None] | None = None
        self._ptt_text_pressed = False
        self._audio_primed = False
        #: Attached by :meth:`run_pcm`; the portal's PTT and audio frames go through it.
        self.pcm: PcmInputStream | None = None

    # PTT markers (text mode and the portal button use these; mic audio mode uses PushToTalk).
    # With a PcmInputStream attached (run_pcm) the press also opens the audio path.
    def ptt_down(self) -> int:
        self._ptt_text_pressed = True
        if self.pcm is not None:
            return self.pcm.down()
        t = voice_clock.mark()
        self.event_log.emit("voice", {"event": "ptt_down", "text": None, "t_ms": t}, beat=self.beat)
        return t

    def ptt_up(self) -> int:
        self._ptt_text_pressed = False
        if self.pcm is not None:
            return self.pcm.up()
        t = voice_clock.now_ms()
        self.event_log.emit("voice", {"event": "ptt_up", "text": None, "t_ms": t}, beat=self.beat)
        return t

    def feed_audio(self, pcm: bytes) -> int:
        """16 kHz mono 16-bit PCM from the browser; heard only while PTT is down. Returns bytes taken."""
        if self.pcm is None:
            return 0
        return self.pcm.feed(pcm)

    async def start(self) -> None:
        await self.agent.start()
        self._events = self.agent.receive()

    async def stop(self) -> None:
        if self._events is not None:
            await self._events.aclose()
            self._events = None
        await self.agent.stop()

    async def __aenter__(self) -> VoiceAgent:
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def say(self, text: str, *, timeout_s: float = RESPONSE_TIMEOUT_S) -> list[str]:
        """Text mode turn: PTT down, send ``text``, PTT up, return the rover's spoken lines.

        Waits for the response to stop; when the response requested tools, waits for the
        follow-up response the tool results trigger.
        """
        if self._events is None:
            raise RuntimeError("voice agent not started")
        self.ptt_down()
        self.transcript._say("user", text)
        await self._prime_audio()
        await self.agent.send(text)
        self.ptt_up()
        before = len(self.transcript.lines)
        responses_needed = 1
        async with asyncio.timeout(timeout_s):
            while responses_needed > 0:
                event = await anext(self._events)
                await self.transcript(event)
                await self.barge_in(event)
                if isinstance(event, BidiToolUseBlocksEvent):
                    # The tool results trigger one more model response; wait for it too.
                    responses_needed += 1
                elif isinstance(event, BidiResponseStopEvent):
                    responses_needed -= 1
        return [line for role, line in self.transcript.lines[before:] if role == "rover"]

    async def _prime_audio(self) -> None:
        """Open Nova Sonic's audio input stream with a sliver of silence before a text-only turn.

        The one live smoke call (2026-10-14) showed Nova Sonic timing out on a text turn with no
        audio content open ("Timed out waiting for audio bytes or interactive content"); AudioIO
        never hits this because the mic stream is open. Only applies to ``BedrockNovaSonicModel``;
        scripted and other models are left alone. Unverified live since the smoke budget was spent.
        """
        if type(self.agent.model).__name__ != "BedrockNovaSonicModel" or self._audio_primed:
            return
        from strands.bidi.types.media import AudioDelta

        rate = self.agent.model.get_audio_config()["input"]["sample_rate"]
        silence = bytes(int(rate * 0.1) * 2)  # 100 ms of 16-bit mono silence
        await self.agent.send(AudioDelta(format="pcm", source={"bytes": silence}))
        self._audio_primed = True

    async def run_text(self, lines: Iterable[str] | None = None, *, out: Printer | None = None) -> list[str]:
        """Drive the agent from ``lines`` (default stdin) and print the transcript. Returns rover lines."""
        if out is not None:
            self.transcript.out = out
        spoken: list[str] = []
        source = lines if lines is not None else _stdin_lines()
        async with self:
            for line in source:
                text = line.strip()
                if not text:
                    continue
                if text in {"/quit", "/exit"}:
                    break
                if text == "/stop":
                    await self.barge_in.trigger()
                    continue
                spoken.extend(await self.say(text))
        return spoken

    async def run_audio(self, *, audio_io: Any = None) -> PushToTalk:
        """Audio mode: mic to Nova Sonic while PTT is pressed, speaker out, barge-in wired.

        Returns the :class:`PushToTalk` so a caller (CLI, portal) can press and release it.
        """
        if audio_io is None:
            from strands.bidi.io import AudioIO  # needs strands-agents[bidi-pyaudio,bidi-io] + PortAudio

            audio_io = AudioIO()
        ptt = PushToTalk(audio_io.input(), self.event_log, beat=self.beat)
        self._ptt = ptt
        await self.agent.run(inputs=[ptt], outputs=[audio_io.output(), self.transcript, self.barge_in])
        return ptt

    async def run_pcm(
        self, pcm: PcmInputStream | None = None, *, outputs: Iterable[Any] = ()
    ) -> PcmInputStream:
        """Audio mode without a microphone device: PCM frames in, the rover's audio to ``outputs``.

        The portal and the rehearsal script feed ``pcm`` (``feed_audio``/``ptt_down``/``ptt_up``
        on this object reach it); ``outputs`` is typically one :class:`~.voice_pcm.AudioSink`.
        Runs until cancelled or the connection ends; the transcript and barge-in hook are wired.
        """
        self.pcm = pcm or PcmInputStream(self.event_log, beat=self.beat)
        try:
            await self.agent.run(inputs=[self.pcm], outputs=[*outputs, self.transcript, self.barge_in])
        finally:
            self.pcm = None
        return pcm or self.pcm or PcmInputStream(self.event_log, beat=self.beat)


def _stdin_lines() -> Iterable[str]:
    yield from sys.stdin


# -- factory ----------------------------------------------------------------------------------


def make_nova_sonic_model(model_id: str | None = None, *, voice: str | None = None) -> BidiModel:
    """``BedrockNovaSonicModel`` on ``$AWS_PROFILE``/``us-east-1`` (imported lazily)."""
    import boto3
    from strands.bidi.models.bedrock import BedrockNovaSonicModel

    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE") or None,
        region_name=os.environ.get("AWS_REGION", DEFAULT_REGION),
    )
    return BedrockNovaSonicModel(
        boto_session=session,
        model_id=model_id or os.environ.get("DEEPRACER_SONIC_MODEL_ID", NOVA_SONIC_MODEL_ID),
        voice=voice or os.environ.get("DEEPRACER_SONIC_VOICE", "matthew"),
    )


def make_voice_agent(
    tools: list[Any],
    gate: InterventionHandler | None,
    runtime: Any,
    *,
    model: BidiModel | str | None = None,
    system_prompt: str | None = None,
    event_log: EventSink | None = None,
    beat: str | None = None,
    out: Printer = print,
) -> VoiceAgent:
    """Build the rover's voice agent.

    Args:
        tools: The gated tool set (``drive_deepracer``, ``stop_deepracer``, ``look`` ...).
        gate: The :class:`~deepracer_agent.gate.DeciderGate` (or ``None`` in a kiosk that only talks).
        runtime: The Car team's ``AgentRuntime``; only ``stop_all()`` is used here, by the barge-in hook.
        model: A ``BidiModel`` (tests pass :class:`ScriptedBidiModel`), a Bedrock model id, or
            ``None`` for Nova Sonic ``amazon.nova-2-5-sonic`` on the ``heisenberg`` profile.
        system_prompt: Defaults to :func:`deepracer_agent.prompts.system_prompt_for`.
    """
    log = resolve_event_log(event_log)
    if model is None or isinstance(model, str):
        model = make_nova_sonic_model(model if isinstance(model, str) else None)
    barge_in = BargeInStop(runtime, log, beat=beat)
    agent = BidiAgent(
        model=model,
        tools=list(tools),
        system_prompt=system_prompt or system_prompt_for(beat),
        hooks=[barge_in],
        name="rover",
    )
    return VoiceAgent(agent, gate=gate, barge_in=barge_in, event_log=log, beat=beat, out=out)


# -- a scripted model for dry runs and tests -------------------------------------------------


class ScriptedBidiModel(BidiModel):
    """A ``BidiModel`` that answers from a script, so the text console runs with no cloud.

    ``script`` maps a lowercase substring of the user's text to either a reply string or a
    ``(tool_name, args, reply)`` tuple: the model first requests the tool, then, when the tool
    result arrives, speaks ``reply``. Unmatched text is echoed. ``barge_in_on`` lists substrings
    that make the model emit a barge-in event before replying (Red Light rehearsal).
    """

    def __init__(
        self,
        script: dict[str, str | tuple[str, dict[str, Any], str]] | None = None,
        *,
        barge_in_on: Iterable[str] = (),
        model_id: str = "scripted",
        audio_transcripts: Iterable[str] = (),
    ) -> None:
        self._config = {"model_id": model_id, "params": None, "connection": {}}
        self.script = {k.lower(): v for k, v in (script or {}).items()}
        self.barge_in_on = tuple(s.lower() for s in barge_in_on)
        #: Fake ASR: each spoken utterance (non-silent PCM followed by silence) is "heard" as the
        #: next of these strings, emitted as a user transcript and answered from the script.
        self.audio_transcripts: list[str] = list(audio_transcripts)
        self.audio_bytes = 0
        self.utterances = 0
        self._in_speech = False
        self._queue: asyncio.Queue[BidiOutputEvent | None] = asyncio.Queue()
        self._pending_reply: dict[str, str] = {}
        self.sent: list[Any] = []
        self.system_prompt: str | None = None
        self.tool_specs: list[ToolSpec] = []
        self._started = False

    def get_config(self) -> Any:
        return self._config

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    async def start(
        self, system_prompt: str | None = None, tools: list[ToolSpec] | None = None, messages=None, **kw
    ):
        self._started = True
        self.system_prompt = system_prompt
        self.tool_specs = list(tools or [])
        self._queue = asyncio.Queue()
        await self._queue.put(BidiConnectionStartEvent(connection_id=uuid.uuid4().hex, model=self.model_id))

    async def stop(self) -> None:
        self._started = False
        await self._queue.put(None)

    async def receive(self) -> AsyncGenerator[BidiOutputEvent, None]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    async def send(self, content: Any) -> None:
        self.sent.append(content)
        if isinstance(content, AudioDelta):
            await self._audio(content.source.get("bytes") or b"")
            return
        if isinstance(content, BidiMessage):
            first = content.content[0] if content.content else None
            if isinstance(first, ToolResultBlock):
                for block in content.content:
                    if isinstance(block, ToolResultBlock):
                        await self._tool_result(block)
                return
            text = " ".join(getattr(b, "text", "") for b in content.content).strip()
            await self._user_text(text)

    async def _audio(self, pcm: bytes) -> None:
        """Fake ASR: speech is any non-zero sample; the first silent frame after speech ends the utterance."""
        self.audio_bytes += len(pcm)
        if any(pcm):
            self._in_speech = True
            return
        if not self._in_speech:
            return
        self._in_speech = False
        self.utterances += 1
        text = self.audio_transcripts.pop(0) if self.audio_transcripts else "(unrecognised)"
        content_id = uuid.uuid4().hex
        await self._queue.put(BidiTranscriptStartEvent("user", content_id))
        await self._queue.put(BidiTranscriptBlockEvent(text, "user", content_id))
        await self._user_text(text)

    async def _speak(self, text: str) -> None:
        content_id = uuid.uuid4().hex
        await self._queue.put(BidiTextStartEvent(content_id))
        await self._queue.put(BidiTextDeltaEvent(text, content_id))
        await self._queue.put(BidiTextStopEvent(content_id))

    async def _user_text(self, text: str) -> None:
        low = text.lower()
        response_id = uuid.uuid4().hex
        if any(s in low for s in self.barge_in_on):
            await self._queue.put(BidiBargeInEvent())
        await self._queue.put(BidiResponseStartEvent(response_id))
        matched: str | tuple[str, dict[str, Any], str] | None = None
        for key, value in self.script.items():
            if key in low:
                matched = value
                break
        if isinstance(matched, tuple):
            tool_name, args, reply = matched
            tool_use_id = f"tooluse_{uuid.uuid4().hex[:8]}"
            self._pending_reply[tool_use_id] = reply
            tool_use: ToolUse = {"toolUseId": tool_use_id, "name": tool_name, "input": dict(args)}
            await self._queue.put(BidiToolUseBlocksEvent([tool_use]))
        elif isinstance(matched, str):
            await self._speak(matched)
        else:
            await self._speak(f"You said: {text}")
        await self._queue.put(BidiResponseStopEvent(response_id))

    async def _tool_result(self, block: ToolResultBlock) -> None:
        reply = self._pending_reply.pop(block.tool_use_id, "Done.")
        result_text = " ".join(
            str(c.get("text", "")) for c in (block.content or []) if isinstance(c, dict)
        ).strip()
        response_id = uuid.uuid4().hex
        await self._queue.put(BidiResponseStartEvent(response_id))
        if block.status == "error" or result_text.startswith(("DENIED", "GUIDANCE", "CONFIRMATION_FAILED")):
            await self._speak(f"The gate said: {result_text}")
        else:
            await self._speak(reply if not result_text else f"{reply} {result_text}".strip())
        await self._queue.put(BidiResponseStopEvent(response_id))


DEFAULT_SCRIPT: dict[str, str | tuple[str, dict[str, Any], str]] = {
    "forward": ("drive_deepracer", {"linear": 0.3, "angular": 0.0, "duration": 0.5}, "Hopping forward."),
    "back": ("drive_deepracer", {"linear": -0.3, "angular": 0.0, "duration": 0.5}, "Hopping back."),
    "why": ("why_stopped", {}, ""),
    "see": ("look", {"question": "What do you see?"}, ""),
    "stop": ("stop_deepracer", {}, "Stopped."),
}


# -- CLI --------------------------------------------------------------------------------------


def _load_runtime_pieces(beat: str | None) -> tuple[Any, list[Any], InterventionHandler | None, EventSink]:
    """Import the Car team's runtime lazily; a clear message when it is not there yet."""
    try:
        from .runtime import AgentRuntime, ApprovalBroker  # Car team, CONTRACTS section 5
    except ImportError as exc:  # pragma: no cover - depends on the Car team's module
        raise SystemExit(
            "deepracer_agent.runtime is not available yet (Car team, CONTRACTS section 5). "
            "Run with --fake for a scripted dry run."
        ) from exc
    from .decider_client import DeciderClient
    from .gate import DeciderGate

    log = resolve_event_log(beat=beat)
    approval = ApprovalBroker()
    gate = DeciderGate(DeciderClient(), None, event_log=log, approval=approval, beat=beat)
    from .look import configure_look, look, why_stopped

    runtime = AgentRuntime(
        body=os.environ.get("DEEPRACER_BODY", "sim"),
        event_log=log,
        gate=gate,
        approval=approval,
        tools=[look, why_stopped],
    )
    tools = list(getattr(runtime, "tools", None) or [])
    # The runtime's capture_frame tool saves the JPEG, emits `frame` and returns {frame_ref, bytes_b64}.
    capture = next((t for t in tools if getattr(t, "tool_name", None) == "capture_frame"), None)
    if capture is None:
        capture = getattr(getattr(runtime, "console", None), "capture_frame", None)
    if capture is not None:
        gate.frame_source = capture
    configure_look(capture, event_log=log)
    return runtime, tools, gate, log


class _NullRuntime:
    """Dry-run stand-in: ``stop_all`` only logs; ``hops`` records what the fake drive tool was asked."""

    def __init__(self, log: EventSink) -> None:
        self.log = log
        self.stops = 0
        self.hops: list[dict[str, float]] = []

    async def stop_all(self) -> None:
        self.stops += 1
        self.log.emit("stop", {"request_id": None, "cause": "operator", "latency_ms": 0})


class _ClearDecider:
    """Dry-run decider: always inside the envelope, never a person, always a clear frame."""

    def ask_noul(
        self, question: str, context: Any, image_bytes: bytes | None = None, **kw: Any
    ) -> dict[str, Any]:
        if image_bytes is not None:  # the gate's person yes/no rides with the frame
            return {"yes": False, "probability": 0.05, "latency_ms": 1}
        return {"yes": True, "probability": 0.95, "latency_ms": 1}

    def ask_choice(
        self, question: str, classes: Any, image_bytes: bytes | None = None, **kw: Any
    ) -> dict[str, Any]:
        return {"class": "clear", "probability": 0.93, "latency_ms": 1, "probabilities": {"clear": 0.93}}


def _fake_pieces(log: EventSink, beat: str | None) -> tuple[_NullRuntime, list[Any], InterventionHandler]:
    """Scripted model, fake tools, a real DeciderGate over a fake decider and a frame.

    No cloud, no car.
    """
    from strands import tool

    from .gate import DeciderGate
    from .look import configure_look, look, why_stopped

    runtime = _NullRuntime(log)

    @tool
    def drive_deepracer(linear: float, angular: float = 0.0, duration: float = 0.5) -> str:
        """Drive the (imaginary) car for a bounded hop."""
        runtime.hops.append({"linear": linear, "angular": angular, "duration": duration})
        log.emit(
            "motion",
            {
                "request_id": None,
                "state": "start",
                "angle": 0.0,
                "throttle": 0.3,
                "duration_s": duration,
                "messages": 0,
            },
            beat=beat,
        )
        log.emit(
            "motion",
            {
                "request_id": None,
                "state": "end",
                "angle": 0.0,
                "throttle": 0.0,
                "duration_s": duration,
                "messages": int(duration * 20),
            },
            beat=beat,
        )
        return f"hopped linear={linear} angular={angular} for {duration}s (dry run)"

    @tool
    def stop_deepracer() -> str:
        """Stop the (imaginary) car."""
        runtime.stops += 1
        return "stopped (dry run)"

    class _FakeVLM:
        def converse(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "output": {"message": {"content": [{"text": "A grey pen floor and a white wall (dry run)."}]}}
            }

    jpeg = b"\xff\xd8" + b"\x00" * 64 + b"\xff\xd9"
    configure_look(lambda: jpeg, converse_client=_FakeVLM(), event_log=log)
    gate = DeciderGate(_ClearDecider(), lambda: jpeg, event_log=log, beat=beat)
    return runtime, [drive_deepracer, stop_deepracer, look, why_stopped], gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m deepracer_agent.voice", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument(
        "--text", action="store_true", help="drive the same agent from stdin, print the transcript"
    )
    parser.add_argument(
        "--fake", action="store_true", help="scripted model and no car: a dry run with no cloud"
    )
    parser.add_argument("--beat", default=None, help="append this beat's prompt snippet")
    parser.add_argument("--model", default=None, help="Bedrock bidi model id (default amazon.nova-2-5-sonic)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARNING"))

    if args.fake:
        log = resolve_event_log(beat=args.beat)
        runtime, tools, gate = _fake_pieces(log, args.beat)
        model: BidiModel | str | None = ScriptedBidiModel(DEFAULT_SCRIPT, barge_in_on=("stop",))
        va = make_voice_agent(tools, gate, runtime, model=model, event_log=log, beat=args.beat)
    else:
        runtime, tools, gate, log = _load_runtime_pieces(args.beat)
        va = make_voice_agent(tools, gate, runtime, model=args.model, event_log=log, beat=args.beat)

    if args.text:
        print("text mode: type a line and press Enter; /stop fires the barge-in path; /quit exits")
        asyncio.run(va.run_text())
        return 0

    async def _audio() -> None:
        async with va:
            print("audio mode: press Enter to toggle push-to-talk; Ctrl-C to exit")
            loop = asyncio.get_running_loop()

            async def toggler(ptt: PushToTalk) -> None:
                while True:
                    await loop.run_in_executor(None, sys.stdin.readline)
                    if ptt.pressed.is_set():
                        ptt.up()
                        print("[ptt up]")
                    else:
                        ptt.down()
                        print("[ptt down]")

            from strands.bidi.io import AudioIO

            audio_io = AudioIO()
            ptt = PushToTalk(audio_io.input(), va.event_log, beat=va.beat)
            toggle_task = asyncio.create_task(toggler(ptt))
            try:
                await va.agent.run(inputs=[ptt], outputs=[audio_io.output(), va.transcript, va.barge_in])
            finally:
                toggle_task.cancel()

    asyncio.run(_audio())
    return 0


__all__ = [
    "DEFAULT_SCRIPT",
    "NOVA_SONIC_MODEL_ID",
    "PushToTalk",
    "ScriptedBidiModel",
    "TranscriptPrinter",
    "VoiceAgent",
    "main",
    "make_nova_sonic_model",
    "make_voice_agent",
]

if __name__ == "__main__":
    sys.exit(main())
