"""The seven live beats, each a short scripted scene the rover plays in the sim or the pen.

A beat is a small script: it tells the agent runtime what the presenter would say, nudges
the simulated world when it runs against the fake car (a foot steps into frame, a hand covers
the lens, a sign is held up, the router loses power), watches the event log for what the
rover did, and prints a pass/fail summary with the latencies that matter. Pre-flight, Marshal,
Apology, Blindfold, Sign, Red Light and Pull the Plug all run on the one spine; a beat costs a
prompt and a screen card. Physics stops the car; the decider explains; the beats are where we
prove both in front of people.

Run one with ``python -m beats <name> --body sim|car [--text]``. The ``AgentRuntime`` comes
from ``deepracer_agent.runtime`` (Car team, CONTRACTS section 5) and is imported lazily so the
beats can be tested against a fake runtime before it lands.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from deepracer_agent.gate import BargeInStop, EventSink, resolve_event_log, voice_clock, wall_ms

logger = logging.getLogger(__name__)

BEAT_NAMES: tuple[str, ...] = (
    "preflight",
    "marshal",
    "apology",
    "blindfold",
    "sign",
    "red_light",
    "pull_the_plug",
)
#: Booth beats run on request, not in the stage arc (``python -m beats all`` is the seven above).
BOOTH_BEAT_NAMES: tuple[str, ...] = ("shapes",)
#: Pre-recorded beats (report 11): filmed once, played from tape at the booth; never in ``all``.
RECORDED_BEAT_NAMES: tuple[str, ...] = ("two_bodies",)
SIM_CONTROL_URL = os.environ.get("DEEPRACER_SIM_CONTROL_URL", "http://127.0.0.1:8092")
DEFAULT_STEP_TIMEOUT_S = (
    60.0  # Bedrock first-token latency spiked to 16 s in rehearsal; 20 s cancelled live turns
)
SETTLE_S = 0.5


class BeatError(RuntimeError):
    """A beat could not run at all (missing runtime, unreachable sim)."""


# -- results ----------------------------------------------------------------------------------


@dataclass
class Step:
    label: str
    ok: bool
    detail: str = ""
    latency_ms: int | None = None

    def line(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        lat = f" ({self.latency_ms} ms)" if self.latency_ms is not None else ""
        detail = f": {self.detail}" if self.detail else ""
        return f"  [{mark}] {self.label}{lat}{detail}"


@dataclass
class BeatResult:
    name: str
    body: str
    steps: list[Step] = field(default_factory=list)
    latencies: dict[str, int | float | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    started_ms: int = field(default_factory=wall_ms)

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(s.ok for s in self.steps)

    def step(self, label: str, ok: bool, detail: str = "", latency_ms: int | None = None) -> Step:
        s = Step(label, bool(ok), detail, latency_ms)
        self.steps.append(s)
        return s

    def summary(self) -> str:
        head = f"beat {self.name} on {self.body}: {'PASS' if self.passed else 'FAIL'}"
        lines = [head, *(s.line() for s in self.steps)]
        if self.latencies:
            lat = ", ".join(f"{k}={v}" for k, v in self.latencies.items() if v is not None)
            if lat:
                lines.append(f"  latencies: {lat}")
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


# -- sim control ------------------------------------------------------------------------------


class SimControl:
    """The fake car's HTTP control endpoint (CONTRACTS section 8): frame label, battery, restart.

    ``heartbeat(enabled)`` targets a proposed ``/heartbeat?enabled=`` route; the Pull the Plug
    beat prefers ``runtime.pause_heartbeat()`` and only falls back to this.
    """

    def __init__(
        self, base_url: str = SIM_CONTROL_URL, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=2.0, transport=transport)

    def _get(self, path: str, **params: Any) -> Any:
        try:
            response = self._client.get(path, params=params or None)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BeatError(f"sim control {self.base_url}{path} failed: {exc}") from exc
        try:
            return response.json()
        except ValueError:
            return response.text

    def state(self) -> Any:
        return self._get("/state")

    def set_frame(self, label: str) -> Any:
        return self._get("/frame", label=label)

    def battery(self, level: int) -> Any:
        return self._get("/battery", level=level)

    def restart(self) -> Any:
        return self._get("/restart")

    def heartbeat(self, enabled: bool) -> Any:
        return self._get("/heartbeat", enabled=str(enabled).lower())

    def deadman(self, enabled: bool) -> Any:
        """Turn the fake car's on-car deadman emulation on or off (the real car always has one)."""
        return self._get("/deadman", enabled=str(enabled).lower())


# -- context ----------------------------------------------------------------------------------


class BeatContext:
    """Everything a beat script needs: the runtime, the event log, the sim knobs and a voice."""

    def __init__(
        self,
        name: str,
        *,
        runtime: Any,
        events: EventSink,
        body: str = "sim",
        sim: SimControl | None = None,
        text: bool = True,
        out: Callable[[str], None] = print,
        barge_in: BargeInStop | None = None,
        gate: Any = None,
    ) -> None:
        self.name = name
        self.runtime = runtime
        self.events = events
        self.body = body
        self.sim = sim
        self.text = text
        self.out = out
        self.gate = gate
        self.barge_in = barge_in or BargeInStop(runtime, events, beat=name)
        self.result = BeatResult(name, body)
        #: Per-turn wait; a beat that asks for many tool calls in one turn (shapes) raises it.
        self.step_timeout_s = DEFAULT_STEP_TIMEOUT_S
        self._turn_done = False

    # -- speaking -------------------------------------------------------------------

    def think(self, text: str) -> None:
        """One line for the screen's thought panel."""
        self.events.emit("thought", {"text": text}, beat=self.name)
        self.out(f"rover thinks> {text}")

    def say(self, text: str) -> None:
        self.events.emit("thought", {"text": f"rover: {text}"}, beat=self.name)
        self.out(f"rover> {text}")

    # -- commanding -----------------------------------------------------------------

    async def submit(self, text: str) -> str:
        """Hand the presenter's words to the runtime (CONTRACTS section 5 ``submit``)."""
        self.out(f"you> {text}")
        voice_clock.mark()  # the presenter's words are the press: voice t_ms counts from here
        self._turn_done = False
        result = self.runtime.submit(text, beat=self.name)
        if inspect.isawaitable(result):
            result = await result
        request_id = str(result)
        # The real runtime returns at once and runs the turn in a task; wait for it when it can.
        wait = getattr(self.runtime, "wait", None)
        if callable(wait):
            try:
                await wait(request_id, timeout=self.step_timeout_s)
            except Exception as exc:  # a cut-off or failed turn is content for the beat
                self.result.notes.append(f"turn {request_id} ended with {type(exc).__name__}: {exc}")
        self._turn_done = True
        return request_id

    def last_seq(self) -> int:
        events = _read(self.events)
        return int(events[-1].get("seq", 0)) if events else 0

    def events_after(self, seq: int, type: str | None = None) -> list[dict[str, Any]]:
        return [
            e
            for e in _read(self.events)
            if int(e.get("seq", 0)) > seq and (type is None or e.get("type") == type)
        ]

    async def outcome_after(self, seq: int, *, timeout_s: float | None = None) -> dict[str, Any]:
        """Wait for a hop to resolve: a motion end, a stop, or a denying/confirming verdict.

        Once the submitted turn has finished (``submit`` awaited the runtime's ``wait``), only a
        short settle window is used, so a turn that produced no motion resolves at once.
        """
        if timeout_s is None:
            timeout_s = SETTLE_S if self._turn_done else DEFAULT_STEP_TIMEOUT_S

        def resolved() -> bool:
            new = self.events_after(seq)
            for e in new:
                p = e.get("payload") or {}
                if e.get("type") == "motion" and p.get("state") == "end":
                    return True
                if e.get("type") == "stop":
                    return True
                if e.get("type") == "verdict" and p.get("action") in ("Deny", "Confirm"):
                    return True
                if e.get("type") == "error":
                    return True
            return False

        await wait_for(resolved, timeout_s)
        new = self.events_after(seq)
        verdicts = [e for e in new if e.get("type") == "verdict"]
        stops = [e for e in new if e.get("type") == "stop"]
        motions = [e for e in new if e.get("type") == "motion"]
        commands = [e for e in new if e.get("type") == "command"]
        thoughts = [e for e in new if e.get("type") == "thought"]
        final = verdicts[-1]["payload"] if verdicts else None
        deny = next((v["payload"] for v in reversed(verdicts) if v["payload"].get("action") == "Deny"), None)
        return {
            "events": new,
            "verdicts": verdicts,
            "stops": stops,
            "motions": motions,
            "commands": commands,
            "thoughts": thoughts,
            "final_verdict": deny or final,
            "moved": any((m.get("payload") or {}).get("state") == "start" for m in motions),
            "verdict_latency_ms": sum(int((v.get("payload") or {}).get("latency_ms") or 0) for v in verdicts),
        }

    def status(self) -> dict[str, Any]:
        try:
            return dict(self.runtime.status())
        except Exception as exc:
            return {"error": str(exc)}


def _read(events: Any) -> list[dict[str, Any]]:
    reader = getattr(events, "read", None)
    if callable(reader):
        return list(reader())
    return []


async def wait_for(
    predicate: Callable[[], bool | Awaitable[bool]], timeout_s: float, poll_s: float = 0.02
) -> bool:
    deadline = time.monotonic() + timeout_s
    while True:
        ok = predicate()
        if inspect.isawaitable(ok):
            ok = await ok
        if ok:
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(poll_s)


# -- loading ----------------------------------------------------------------------------------


def load_beat(name: str) -> Callable[[BeatContext], Awaitable[BeatResult]]:
    if name not in BEAT_NAMES and name not in BOOTH_BEAT_NAMES and name not in RECORDED_BEAT_NAMES:
        raise BeatError(
            f"unknown beat {name!r}; choose one of {', '.join(BEAT_NAMES)}, a booth beat "
            f"({', '.join(BOOTH_BEAT_NAMES)}) or a recorded beat ({', '.join(RECORDED_BEAT_NAMES)})"
        )
    module = importlib.import_module(f"beats.{name}")
    return module.run


def load_runtime(
    body: str,
    *,
    beat: str,
    events: EventSink,
    gate: Any = None,
    approval: Any = None,
    transport: Any = None,
) -> Any:
    """Import ``deepracer_agent.runtime.AgentRuntime`` lazily; a clear message when it is absent.

    ``transport`` replaces the rosbridge transport (the Two Bodies beat passes a ``TwinTransport``).
    """
    try:
        from deepracer_agent.runtime import AgentRuntime, ApprovalBroker
    except ImportError as exc:
        raise BeatError(
            "deepracer_agent.runtime.AgentRuntime is not available yet (Car team, CONTRACTS section 5); "
            "the beats run against it, or against a fake runtime in tests"
        ) from exc
    from deepracer_agent.look import configure_look, look, why_stopped
    from deepracer_agent.plans import Pen, configure_plans, plan_deepracer

    approval = approval or ApprovalBroker()
    if gate is None:
        from deepracer_agent.decider_client import DeciderClient, DeciderUnavailable
        from deepracer_agent.gate import DeciderGate

        decider = DeciderClient()
        try:
            # One long-budget ask before the gate's 1.5 s budget applies: a cold model on MPS
            # takes about 2 s for its first pass, and a request landing on top of a cold one
            # aborts the server (decider_client.warm). Failure is not fatal: the gate denies.
            from deepracer_agent.gate import warm_gate

            logger.info("decider warm-up at %s: %s", decider.base_url, warm_gate(decider))
        except DeciderUnavailable as exc:
            logger.warning("decider warm-up failed (gate will deny until it answers): %s", exc)
        gate = DeciderGate(decider, None, event_log=events, approval=approval, beat=beat)
    runtime = AgentRuntime(
        body=body,
        event_log=events,
        gate=gate,
        approval=approval,
        tools=[look, why_stopped, plan_deepracer],
        transport=transport,
    )
    configure_plans(
        calibration=runtime.driver.calibration,
        pen=Pen(),
        envelope=getattr(gate, "envelope", None),
        event_log=events,
        beat=beat,
    )
    capture = capture_frame_source(runtime)
    if capture is not None and getattr(gate, "frame_source", None) is None:
        gate.frame_source = capture
    configure_look(capture, event_log=events)
    return runtime


def capture_frame_source(runtime: Any) -> Callable[[], Any] | None:
    """The runtime's ``capture_frame`` tool (saves the JPEG, emits ``frame``, returns the dict).

    Falls back to ``runtime.console.capture_frame`` (raw bytes) when the tool is not registered.
    """
    for tool in getattr(runtime, "tools", None) or []:
        if getattr(tool, "tool_name", None) == "capture_frame":
            return tool
    console = getattr(runtime, "console", None)
    capture = getattr(console, "capture_frame", None)
    return capture if callable(capture) else None


def make_context(
    name: str,
    *,
    body: str = "sim",
    text: bool = True,
    runtime: Any = None,
    events: EventSink | None = None,
    sim: SimControl | None = None,
    out: Callable[[str], None] = print,
) -> BeatContext:
    events = resolve_event_log(events, beat=name) if events is None else events
    if sim is None and body == "sim":
        sim = SimControl()
    if sim is not None and body == "sim":
        try:  # the real car always has its deadman; the fake car's emulation has to be switched on
            sim.deadman(True)
        except BeatError as exc:
            print(f"[beats] sim deadman not enabled: {exc}", file=sys.stderr)
    if runtime is None:
        runtime = load_runtime(body, beat=name, events=events)
    return BeatContext(name, runtime=runtime, events=events, body=body, sim=sim, text=text, out=out)


__all__ = [
    "BEAT_NAMES",
    "BOOTH_BEAT_NAMES",
    "DEFAULT_STEP_TIMEOUT_S",
    "RECORDED_BEAT_NAMES",
    "BeatContext",
    "BeatError",
    "BeatResult",
    "SimControl",
    "Step",
    "load_beat",
    "load_runtime",
    "make_context",
    "wait_for",
]
