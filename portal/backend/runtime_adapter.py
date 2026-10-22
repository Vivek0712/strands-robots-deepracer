"""Runtime adapter: the portal speaks one small interface, whether the real agent or the fake answers.

The portal needs five things from the agent runtime (CONTRACTS section 5): submit a command, stop
everything, run pre-flight, report status and resolve an approval. This module imports
``deepracer_agent.runtime`` lazily; when it is not importable yet, or cannot be constructed, it
falls back to :class:`portal.backend.fake_runtime.FakeRuntime` and says so in the state. Voice is
``deepracer_agent.voice`` on Nova Sonic fed by ``deepracer_agent.voice_pcm.PcmInputStream``: the
browser's 16 kHz PCM frames and push-to-talk arrive here, the voice agent is started on the first
press (and stopped again after ``PORTAL_VOICE_IDLE_S`` without one), and the rover's spoken audio
fans out through ``audio_sink`` to every open ``/ws/audio`` socket. ``PORTAL_VOICE=0`` turns the
cloud voice off (PTT markers still reach the screen). Physics stops the car; the decider explains;
this adapter only carries the operator's intent to whichever agent is running.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import logging
import os
import threading
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from .fake_runtime import FakeRuntime

DECIDER_KEEPALIVE_S = 240.0  # the booth model answered in 144 ms warm, 3475 ms after an idle hour

log = logging.getLogger("portal.runtime")

Emit = Callable[..., Awaitable[dict[str, Any]]]
#: ``(voice_agent, pcm_stream)`` builder; the adapter runs the agent with ``run_pcm`` on the first press.
VoiceFactory = Callable[[], tuple[Any, Any]]
VOICE_START_TIMEOUT_S = 20.0
VOICE_IDLE_S = float(os.environ.get("PORTAL_VOICE_IDLE_S", "300"))


@runtime_checkable
class RuntimeLike(Protocol):
    """What the portal calls. ``FakeRuntime`` implements it directly; ``RealRuntime`` wraps the agent."""

    name: str
    body: str

    async def submit(self, text: str, *, beat: str | None = None) -> str: ...
    async def stop_all(self) -> None: ...
    async def preflight(self) -> dict[str, Any]: ...
    def status(self) -> dict[str, Any]: ...
    def resolve_approval(self, request_id: str, approved: bool) -> bool: ...
    async def set_body(self, active: str) -> None: ...
    async def voice_ptt(self, state: str) -> None: ...
    async def voice_audio(self, pcm: bytes) -> None: ...
    async def aclose(self) -> None: ...


class RealRuntime:
    """Wraps ``deepracer_agent.runtime.AgentRuntime`` (+ optional ``deepracer_agent.voice``)."""

    name = "deepracer_agent"

    def __init__(
        self,
        runtime: Any,
        approval: Any,
        voice: Any | None,
        emit: Emit,
        body: str,
        *,
        poster: InProcessPoster | None = None,
        event_log: Any | None = None,
        voice_factory: VoiceFactory | None = None,
        audio_sink: Any | None = None,
        voice_idle_s: float = VOICE_IDLE_S,
    ) -> None:
        self._rt = runtime
        self._approval = approval
        self._voice = voice
        self._emit = emit
        self._poster = poster
        self._event_log = event_log
        self.body = body
        self._voice_factory = voice_factory
        #: The rover's spoken PCM fans out here (``attach(on_audio, on_barge_in)``); ``/ws/audio`` listens.
        self.audio_sink = audio_sink
        self._voice_idle_s = voice_idle_s
        self._pcm: Any | None = None
        self._voice_task: asyncio.Task[Any] | None = None
        self._voice_state = "off" if voice_factory is None and voice is None else "idle"
        self._voice_error: str | None = None
        self._idle_handle: asyncio.TimerHandle | None = None
        self._pressed = False
        self._keepalive: asyncio.Task[Any] | None = None

    def _bind(self) -> None:
        if self._poster is not None:
            self._poster.bind(asyncio.get_running_loop())

    async def start(self) -> None:
        """Called from the app's lifespan: flush events the EventLog emitted before the loop existed."""
        self._bind()
        if self._keepalive is None:
            self._keepalive = asyncio.create_task(self._decider_keepalive(), name="decider-keepalive")

    async def _decider_keepalive(self) -> None:
        """One cheap question every ``DECIDER_KEEPALIVE_S`` so the decider never goes cold mid-show."""
        while True:
            await asyncio.sleep(DECIDER_KEEPALIVE_S)
            gate = getattr(self._rt, "gate", None)
            decider = getattr(gate, "decider", None)
            if decider is None:
                continue
            try:
                gate_mod = importlib.import_module("deepracer_agent.gate")
                ms = await asyncio.to_thread(gate_mod.warm_gate, decider, timeout_s=30.0)
                if max(ms.values(), default=0) > 1000:
                    log.info("decider keepalive took %s (it had gone cold)", ms)
            except Exception as exc:
                log.warning("decider keepalive failed: %s", exc)

    async def submit(self, text: str, *, beat: str | None = None) -> str:
        self._bind()
        return await self._rt.submit(text, beat=beat)

    @property
    def camera(self) -> Any | None:
        """The runtime's shared :class:`deepracer_agent.camera.CameraStream`, when the body is the car."""
        return getattr(self._rt, "camera", None)

    async def reconnect(self) -> None:
        """After ``connect.connect()`` moved the car's address: new sockets, same session and log."""
        await self._stop_voice()
        rebind = getattr(self._rt, "rebind", None)
        if callable(rebind):
            await asyncio.to_thread(rebind)
        gate = getattr(self._rt, "gate", None)
        tools_by_name = {getattr(t, "tool_name", None): t for t in getattr(self._rt, "tools", [])}
        capture = tools_by_name.get("capture_frame") or getattr(
            getattr(self._rt, "console", None), "capture_frame", None
        )
        if gate is not None and capture is not None:
            gate.frame_source = capture
        with contextlib.suppress(Exception):
            look_mod = importlib.import_module("deepracer_agent.look")
            look_mod.configure_look(capture, event_log=self._event_log)
            for t in (look_mod.look, look_mod.why_stopped):
                if t not in self._rt.tools:
                    self._rt.tools.append(t)
        with contextlib.suppress(Exception):
            plans_mod = importlib.import_module("deepracer_agent.plans")
            plans_mod.configure_plans(event_log=self._event_log)
            if plans_mod.plan_deepracer not in self._rt.tools:
                self._rt.tools.append(plans_mod.plan_deepracer)

    async def stop_all(self) -> None:
        self._bind()
        await self._rt.stop_all()

    async def preflight(self) -> dict[str, Any]:
        self._bind()
        return await self._rt.preflight()

    def status(self) -> dict[str, Any]:
        status = dict(self._rt.status())
        status["runtime"] = self.name
        status["gate_mode"] = str(getattr(getattr(self._rt, "gate", None), "mode", "none"))
        status["voice"] = self.voice_status()
        return status

    def voice_status(self) -> dict[str, Any]:
        """``{"state": off|idle|starting|live|error, "error", "pressed", "stats"}`` for the screen."""
        pcm = self._pcm
        return {
            "state": self._voice_state,
            "error": self._voice_error,
            "pressed": self._pressed,
            "stats": pcm.stats() if pcm is not None and hasattr(pcm, "stats") else None,
            "listeners": getattr(self.audio_sink, "listener_count", 0),
        }

    def resolve_approval(self, request_id: str, approved: bool) -> bool:
        try:
            self._approval.resolve(request_id, approved)
            return True
        except KeyError:
            return False

    async def set_body(self, active: str) -> None:
        self._bind()
        setter = getattr(self._rt, "set_body", None)
        if setter is not None:
            result = setter(active)
            if inspect.isawaitable(result):
                await result
        self.body = active
        await self._emit("body", {"active": active}, source="runtime")

    async def voice_ptt(self, state: str) -> None:
        self._bind()
        self._pressed = state == "down"
        if state == "down" and self._voice_factory is not None:
            # The press is stamped at once (the PcmInputStream buffers audio while the cloud
            # connection comes up); the voice agent starts on the first press and idles out later.
            self._cancel_idle()
            self._ensure_voice()
            if self._pcm is not None:
                self._pcm.down()
                return
        if state == "up" and self._pcm is not None:
            self._pcm.up()
            self._arm_idle()
            return
        fn = getattr(self._voice, f"ptt_{state}", None) if self._voice is not None else None
        if fn is None:
            # No VoiceAgent attached: still put the PTT markers on the one screen contract.
            await self._emit("voice", {"event": f"ptt_{state}", "text": None, "t_ms": 0}, source="voice")
            return
        result = fn()
        if inspect.isawaitable(result):
            await result

    async def voice_audio(self, pcm: bytes) -> None:
        if self._pcm is not None:
            self._pcm.feed(pcm)
            return
        if self._voice is None:
            return
        fn = getattr(self._voice, "feed_audio", None) or getattr(self._voice, "audio", None)
        if fn is None:
            return
        result = fn(pcm)
        if inspect.isawaitable(result):
            await result

    # -- voice lifecycle -----------------------------------------------------------------------

    def _ensure_voice(self) -> None:
        """Build the voice agent and start ``run_pcm`` in the background, once."""
        if self._voice_task is not None and not self._voice_task.done():
            return
        if self._voice_factory is None:
            return
        try:
            voice, pcm = self._voice_factory()
        except Exception as exc:
            self._voice_state, self._voice_error = "error", f"{type(exc).__name__}: {exc}"
            log.warning("voice agent not built: %s", exc)
            asyncio.get_running_loop().create_task(
                self._emit("error", {"where": "portal.voice", "message": self._voice_error}, source="voice")
            )
            return
        self._voice, self._pcm = voice, pcm
        self._voice_state, self._voice_error = "starting", None
        outputs = [self.audio_sink] if self.audio_sink is not None else []
        self._voice_task = asyncio.get_running_loop().create_task(
            voice.run_pcm(pcm, outputs=outputs), name="portal-voice"
        )
        self._voice_task.add_done_callback(self._voice_done)
        asyncio.get_running_loop().create_task(self._watch_voice_start(pcm))

    async def _watch_voice_start(self, pcm: Any) -> None:
        deadline = asyncio.get_running_loop().time() + VOICE_START_TIMEOUT_S
        while asyncio.get_running_loop().time() < deadline:
            if self._pcm is not pcm or self._voice_task is None or self._voice_task.done():
                return
            if getattr(pcm, "started", False):
                self._voice_state = "live"
                await self._emit(
                    "thought", {"text": "voice: Nova Sonic connected, push-to-talk live"}, source="voice"
                )
                return
            await asyncio.sleep(0.05)
        if self._voice_state == "starting":
            self._voice_state = "error"
            self._voice_error = f"voice agent did not connect within {VOICE_START_TIMEOUT_S:g} s"
            await self._emit("error", {"where": "portal.voice", "message": self._voice_error}, source="voice")

    def _voice_done(self, task: asyncio.Task[Any]) -> None:
        self._pcm = None
        self._voice_task = None
        if task.cancelled():
            self._voice_state = "idle"
            return
        exc = task.exception()
        if exc is None:
            self._voice_state = "idle"
            return
        self._voice_state, self._voice_error = "error", f"{type(exc).__name__}: {exc}"
        log.warning("voice agent ended: %s", self._voice_error)
        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop().create_task(
                self._emit("error", {"where": "portal.voice", "message": self._voice_error}, source="voice")
            )

    def _arm_idle(self) -> None:
        self._cancel_idle()
        if self._voice_idle_s and self._voice_task is not None:
            loop = asyncio.get_running_loop()
            self._idle_handle = loop.call_later(
                self._voice_idle_s, lambda: loop.create_task(self._stop_voice())
            )

    def _cancel_idle(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None

    async def _stop_voice(self) -> None:
        """End the Nova Sonic connection (idle timeout or shutdown); the next press starts a new one."""
        self._cancel_idle()
        task = self._voice_task
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        self._voice_state = "idle"

    async def aclose(self) -> None:
        if self._keepalive is not None:
            self._keepalive.cancel()
            self._keepalive = None
        await self._stop_voice()
        closer = getattr(self._rt, "aclose", None) or getattr(self._rt, "close", None)
        if closer is not None:
            result = closer()
            if inspect.isawaitable(result):
                await result


class InProcessPoster:
    """EventLog ``poster`` that hands events to the hub directly instead of HTTP-posting to ourselves.

    The agent's EventLog has already written the line to ``events.jsonl``, so the hub only
    broadcasts (``persist=False``). The poster runs on the EventLog's daemon thread; events that
    arrive before the app loop is known are buffered and flushed on the first loop-side call.
    """

    def __init__(self, publish: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        self._publish = publish
        self._loop: asyncio.AbstractEventLoop | None = None
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop
            pending, self._buffer = self._buffer, []
        for event in pending:
            asyncio.run_coroutine_threadsafe(self._publish(event), loop)

    def __call__(self, _url: str, event: dict[str, Any]) -> None:
        with self._lock:
            loop = self._loop
            if loop is None or loop.is_closed():
                self._buffer.append(event)
                return
        asyncio.run_coroutine_threadsafe(self._publish(event), loop)


def _try_real(
    emit: Emit,
    publish: Callable[[dict[str, Any]], Awaitable[Any]] | None,
    body: str,
    run_dir: str,
    session: str,
) -> RuntimeLike | None:
    """Build the real runtime the way ``deepracer_agent.voice._load_runtime_pieces`` does; else None."""
    try:
        rt_mod = importlib.import_module("deepracer_agent.runtime")
        ev_mod = importlib.import_module("deepracer_agent.events")
    except ImportError as exc:
        log.info("deepracer_agent.runtime not importable (%s); using FakeRuntime", exc)
        return None
    try:
        poster = InProcessPoster(publish) if publish is not None else None
        event_log = ev_mod.EventLog(run_dir or None, session=session or None, source="agent", poster=poster)
        approval = rt_mod.ApprovalBroker()
        gate = None
        try:
            gate_mod = importlib.import_module("deepracer_agent.gate")
            dc_mod = importlib.import_module("deepracer_agent.decider_client")
            decider = dc_mod.DeciderClient(
                timeout_s=float(os.environ.get("DEEPRACER_DECIDER_TIMEOUT_S", "2.5"))
            )
            gate = gate_mod.DeciderGate(decider, None, event_log=event_log, approval=approval)
            wanted = os.environ.get("PORTAL_GATE", "advisory").strip().lower()
            if wanted in gate_mod.GATE_MODES:
                gate.mode = wanted  # the talk starts in advisory; enforce for the vision beats
            try:
                # A question the decider has not seen costs 2-4 s on MPS (prefix cache), over the
                # gate's budget, and the gate then denies with "vision unavailable". Warm with the
                # gate's OWN questions here, and again from RealRuntime's keepalive.
                log.info("decider warm-up with the gate's questions: %s", gate_mod.warm_gate(decider))
            except Exception as exc:
                log.warning("decider warm-up failed (the gate denies until it answers): %s", exc)
        except Exception as exc:
            log.warning("no decider gate (%s); the runtime will refuse gated tools", exc)
        extra_tools: list[Any] = []
        runtime = rt_mod.AgentRuntime(body=body, event_log=event_log, gate=gate, approval=approval)
        # The capture_frame TOOL saves the JPEG under the run dir and emits a `frame` event with its
        # frame_ref, so the Stage view can freeze the frame the gate judged; the bare console grab
        # returns bytes only.
        tools_by_name = {getattr(t, "tool_name", None): t for t in getattr(runtime, "tools", [])}
        capture = tools_by_name.get("capture_frame") or getattr(
            getattr(runtime, "console", None), "capture_frame", None
        )
        if gate is not None and capture is not None:
            gate.frame_source = capture
        try:
            look_mod = importlib.import_module("deepracer_agent.look")
            look_mod.configure_look(capture, event_log=event_log)
            extra_tools = [look_mod.look, look_mod.why_stopped]
            runtime.tools.extend(t for t in extra_tools if t not in runtime.tools)
        except Exception as exc:
            log.info("look tools not attached (%s)", exc)
        try:
            plans_mod = importlib.import_module("deepracer_agent.plans")
            plans_mod.configure_plans(event_log=event_log)  # the shape planner the maneuvers use
            if plans_mod.plan_deepracer not in runtime.tools:
                runtime.tools.append(plans_mod.plan_deepracer)
        except Exception as exc:
            log.info("plan tool not attached (%s)", exc)
        voice_factory, sink = _voice_pieces(runtime, gate, event_log)
        return RealRuntime(
            runtime,
            approval,
            None,
            emit,
            body,
            poster=poster,
            event_log=event_log,
            voice_factory=voice_factory,
            audio_sink=sink,
        )
    except Exception as exc:
        log.warning("deepracer_agent.runtime present but not constructible (%s); using FakeRuntime", exc)
        return None


def voice_enabled() -> bool:
    """``PORTAL_VOICE`` unset, ``1``, ``on`` or ``nova`` means the browser PTT reaches Nova Sonic."""
    return os.environ.get("PORTAL_VOICE", "1").strip().lower() not in ("", "0", "off", "false", "no")


def _voice_pieces(runtime: Any, gate: Any, event_log: Any) -> tuple[VoiceFactory | None, Any | None]:
    """A lazy Nova Sonic ``VoiceAgent`` over the runtime's gated tools plus the shared ``AudioSink``."""
    if not voice_enabled():
        log.info("PORTAL_VOICE is off; push-to-talk marks the screen only")
        return None, None
    try:
        voice_mod = importlib.import_module("deepracer_agent.voice")
        pcm_mod = importlib.import_module("deepracer_agent.voice_pcm")
    except ImportError as exc:
        log.info("voice modules not importable (%s)", exc)
        return None, None
    sink = pcm_mod.AudioSink(keep_audio=False)

    def make() -> tuple[Any, Any]:
        tools = list(getattr(runtime, "tools", None) or [])
        voice = voice_mod.make_voice_agent(tools, gate, runtime, event_log=event_log)
        return voice, pcm_mod.PcmInputStream(event_log)

    return make, sink


def build_runtime(
    emit: Emit,
    *,
    publish: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
    body: str | None = None,
    run_dir: str = "",
    session: str = "",
    frame_grabber: Callable[[], Awaitable[str | None]] | None = None,
    prefer_fake: bool | None = None,
) -> RuntimeLike:
    """Return the real runtime when available, else the fake. ``PORTAL_FAKE_RUNTIME=1`` forces the fake."""
    body = body or os.environ.get("DEEPRACER_BODY", "sim")
    if prefer_fake is None:
        prefer_fake = os.environ.get("PORTAL_FAKE_RUNTIME", "") not in ("", "0", "false")
    if not prefer_fake:
        real = _try_real(emit, publish, body, run_dir, session)
        if real is not None:
            return real
    return FakeRuntime(emit, body=body, frame_grabber=frame_grabber)
