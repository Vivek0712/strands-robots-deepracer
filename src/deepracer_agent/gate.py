"""The decider gate: five typed questions, two requests, before every hop; a spoken reason for every stop.

Before the agent is allowed to drive, this intervention handler asks the decider two requests.
The text request carries the conversation, the proposed ``drive_deepracer`` call, the briefed
envelope and the deterministic check's result, and asks three questions in one forward pass:
is the command inside the envelope the marshal briefed (yes/no), are the argument values
grounded in what the user actually said (yes/no), and what did the user ask for (a five-way
choice: move_forward, turn, stop, question, unrelated). The frame request carries the camera
frame and asks two: a yes/no "is a person visible" and the five-way choice over clear, an
obstacle near, a person in frame, off the surface, or unclear. When the yes/no says person at
p >= 0.5 the class is ``person_in_frame`` at that probability whatever the five-way said
(calibration 2026-10-14: the booth model called a person at desk distance ``unclear`` 0.58-0.67
on 11 of 11 real frames while the yes/no read 0.95 on 10 of them; sharper class descriptions
pushed ``unclear`` under 0.5 instead, which would have opened the gate). The pre-check can only
add a Deny, never remove one. The answers map to one of four actions the Strands intervention
system understands: Proceed, Guide (re-plan), Confirm (ask the operator) or Deny. No frame, no
decider, a decider slower than 1.5 s, or an answer that is not a probability in [0, 1] over a
known class means Deny: the gate fails closed. Every decision is written to the event log with
its latency, so the screen can show the number and "why did you stop?" can be answered from the
record. The two grounding questions need the user's words: ``before_tool_call`` renders them
from the agent's messages; a ``decide()`` called without a conversation (the Simon Says kiosk, a
plan step) asks the envelope question and the frame pair only.

Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb). The decider
explains. This module is the explanation layer, never the safety layer.

Decision table (docs/dev/CONTRACTS.md section 7; rows are checked in this order and the first
matching row is the action; YES = 0.65, NO = 0.35, PERSON = 0.5, UNCLEAR = 0.65):

    1  decider unreachable, timeout (> 1.5 s), malformed answer -> Deny("vision unavailable")
    2  no frame                                                -> Deny("vision unavailable")
    3  person yes/no p >= 0.5, or frame class person_in_frame  -> Deny (person in frame)
    4  frame class off_surface                                 -> Deny (off the surface)
    5  frame class unclear with p >= 0.65                      -> Deny (cannot see clearly)
    6  intent stop with p >= 0.65                              -> Deny (the user asked to stop)
    7  deterministic envelope check fails (code, not the model) -> Confirm (the marshal's thumb;
                                                                  the drop-in recipe says Guide)
    8  inside_envelope < 0.35                                  -> Guide (re-plan inside the envelope)
    9  args_grounded < 0.35                                    -> Guide (ask the user for the values)
    10 intent question or unrelated with p >= 0.65             -> Guide (answer the user instead)
    11 frame class obstacle_near                               -> Guide (halve linear, re-plan)
    12 inside_envelope or args_grounded in [0.35, 0.65)        -> Confirm (operator)
    13 otherwise                                               -> Proceed

On the car both requests report a failure as "vision unavailable": that is the string the
Apology beat, ``why_stopped`` and the sim suite read back, and the car has one word for "I
cannot judge, so I will not move".

Also here: ``BargeInStop``, the bidi hook for the Red Light beat. When the presenter speaks
over the rover mid-sentence, Nova Sonic reports a barge-in; the hook calls the runtime's
``stop_all`` and writes the barge-in and stop timestamps, in milliseconds, to the event log.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as _dt
import inspect
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from strands.hooks import BeforeToolCallEvent, HookRegistry
from strands.interventions import Confirm, Deny, Guide, InterventionHandler, OnError, Proceed, Transform

from .decider_client import DeciderClient, DeciderUnavailable

logger = logging.getLogger(__name__)

GATED_TOOLS: tuple[str, ...] = ("drive_deepracer",)
FRAME_CLASSES: tuple[str, ...] = ("clear", "obstacle_near", "person_in_frame", "off_surface", "unclear")
FRAME_CLASS_DESCRIPTIONS: dict[str, str] = {
    "clear": "the pen floor ahead is empty and the car can move",
    "obstacle_near": "an object is close in front of the bumper",
    "person_in_frame": "a person, or part of one (foot, leg, hand), is in the camera view",
    "off_surface": "the car is at or past the edge of the pen surface",
    "unclear": "the image is dark, blurred, blocked or otherwise unreadable",
}
#: Frame classes that deny. ``person_in_frame`` at or above ``deny_threshold``, ``unclear`` at or
#: above ``UNCLEAR_THRESHOLD``, ``off_surface`` whenever it is the chosen class (rows 3 to 5).
DENY_CLASSES: tuple[str, ...] = ("person_in_frame", "off_surface", "unclear")
VISION_UNAVAILABLE = "vision unavailable"
UNCLEAR_THRESHOLD = 0.65
#: Text-question thresholds (rows 6, 8, 9, 10, 12): a probability at or above YES is a confident
#: yes, below NO a confident no, between them the operator is asked. The policy knob, owned by
#: the code; the same number the drop-in recipe uses (patterns/strands/tool_call_intervention.py).
YES = 0.65
NO = round(1.0 - YES, 6)
#: How much of the conversation rides in the text request: the newest messages, newest characters.
RENDER_MAX_MESSAGES = 12
RENDER_MAX_CHARS = 2000
GateMode = Literal["enforce", "advisory", "off"]
GATE_MODES: tuple[str, ...] = ("enforce", "advisory", "off")
GATE_OFF = "gate off by operator: no decider check on this hop"
PLAIN_REASON = {
    "person_in_frame": "someone is in front of me",
    "unclear": "I cannot see clearly, the frame cannot be judged",
    "off_surface": "the floor ahead is not the pen surface",
    "obstacle_near": "something is close ahead",
}
ENVELOPE_QUESTION = "Is this drive command inside the briefed envelope?"
#: Asked in the same text request as ENVELOPE_QUESTION (one forward pass answers all three). The
#: wording and criteria are those of the drop-in recipe, patterns/strands/tool_call_intervention.py.
GROUNDED_QUESTION = "Are the tool's argument values grounded in what the user actually said?"
GROUNDED_CRITERIA: dict[str, str] = {
    "true": "every argument value traces back to something the user said",
    "false": "an argument value was guessed or invented, not stated by the user",
}
INTENT_QUESTION = "What did the user most recently ask the robot to do?"
INTENT_CLASS_DESCRIPTIONS: dict[str, str] = {
    "move_forward": "drive straight ahead by some distance",
    "turn": "change heading, with or without moving",
    "stop": "stop, halt, wait, do not move",
    "question": "ask something about the robot or the room; no movement requested",
    "unrelated": "something that is not about the robot moving at all",
}
INTENT_CLASSES: tuple[str, ...] = tuple(INTENT_CLASS_DESCRIPTIONS)
FRAME_QUESTION = "What is directly in front of the car in this camera frame?"
#: Asked in the same request as FRAME_QUESTION, over the same frame. Pinned by
#: tests/unit/test_gate.py; re-run ``python -m deepracer_agent.calibrate_frames`` before changing
#: any of these three strings or FRAME_CLASS_DESCRIPTIONS.
PERSON_QUESTION = "Is a person (any part of a human body) visible in this camera frame?"

Action = Literal["Proceed", "Guide", "Confirm", "Deny"]


# -- envelope ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Envelope:
    """What the marshal briefed: how fast, how long, which way.

    ``allowed_directions`` is any subset of ``("forward", "backward")``. The deterministic
    check in :meth:`violations` runs next to the decider's yes/no so a numeric overshoot is never
    left to a classifier alone (robots-decider doctrine: deterministic checks live in code).
    """

    max_linear: float = 0.3
    max_duration_s: float = 2.0
    allowed_directions: tuple[str, ...] = ("forward", "backward")
    max_angular: float = 1.0

    def describe(self) -> str:
        dirs = " or ".join(self.allowed_directions) if self.allowed_directions else "no direction"
        return (
            f"|linear| <= {self.max_linear:g} m/s, |angular| <= {self.max_angular:g} rad/s, "
            f"duration <= {self.max_duration_s:g} s, directions: {dirs}"
        )

    @staticmethod
    def direction(linear: float) -> str:
        if linear > 0:
            return "forward"
        if linear < 0:
            return "backward"
        return "none"

    def violations(self, linear: float, angular: float, duration: float) -> list[str]:
        out: list[str] = []
        if abs(linear) > self.max_linear:
            out.append(f"|linear| {abs(linear):g} > {self.max_linear:g} m/s")
        if abs(angular) > self.max_angular:
            out.append(f"|angular| {abs(angular):g} > {self.max_angular:g} rad/s")
        if duration > self.max_duration_s:
            out.append(f"duration {duration:g} > {self.max_duration_s:g} s")
        if duration <= 0:
            out.append("duration must be positive")
        direction = self.direction(linear)
        if direction != "none" and direction not in self.allowed_directions:
            out.append(f"direction {direction} not allowed")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_linear": self.max_linear,
            "max_duration_s": self.max_duration_s,
            "allowed_directions": list(self.allowed_directions),
            "max_angular": self.max_angular,
        }


def envelope_context(envelope: Envelope, linear: float, angular: float, duration: float) -> dict[str, Any]:
    """The state sent with :data:`ENVELOPE_QUESTION`: the command, the briefed envelope and the
    deterministic check's result. The gate and ``bench_decider`` build it from here so the
    benchmark measures exactly what the gate asks."""
    violations = envelope.violations(linear, angular, duration)
    return {
        "command": {
            "tool": "drive_deepracer",
            "linear": linear,
            "angular": angular,
            "duration": duration,
        },
        "envelope": envelope.describe(),
        "deterministic_check": "ok" if not violations else "; ".join(violations),
    }


# -- the text questions -----------------------------------------------------------------------


def render_conversation(
    messages: list[dict[str, Any]] | None,
    *,
    max_messages: int = RENDER_MAX_MESSAGES,
    max_chars: int = RENDER_MAX_CHARS,
) -> str:
    """Flatten a Strands message list to plain text for the text request: the human-readable
    blocks of the newest ``max_messages`` messages, cut to the newest ``max_chars`` characters."""
    lines: list[str] = []
    for message in (messages or [])[-max_messages:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "unknown")
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and "text" in block:
                lines.append(f"{role}: {block['text']}")
    text = "\n".join(lines) if lines else "(no conversation yet)"
    if len(text) > max_chars:
        text = "..." + text[-(max_chars - 3) :]
    return text


def text_questions() -> dict[str, dict[str, Any]]:
    """The three questions of the text request, in System One shape, built from the module
    constants so the gate, the warm-up and the benchmark ask exactly the same thing."""
    return {
        "inside_envelope": {"type": "noul", "instructions": ENVELOPE_QUESTION},
        "args_grounded": {
            "type": "noul",
            "instructions": GROUNDED_QUESTION,
            "criteria": dict(GROUNDED_CRITERIA),
        },
        "intent": {
            "type": "choice",
            "instructions": INTENT_QUESTION,
            "criteria": dict(INTENT_CLASS_DESCRIPTIONS),
        },
    }


@dataclass(frozen=True)
class TextAnswers:
    """The text request's answers. ``grounded``, ``intent`` and ``intent_p`` are ``None`` when only
    the envelope question was asked (no conversation, or a decider without ``ask_many``)."""

    inside: float
    grounded: float | None
    intent: str | None
    intent_p: float | None
    latency_ms: int

    @property
    def asked_grounding(self) -> bool:
        return self.grounded is not None and self.intent is not None and self.intent_p is not None


def ask_text_questions(
    decider: Any,
    envelope: Envelope,
    linear: float,
    angular: float,
    duration: float,
    conversation: str | None,
) -> TextAnswers:
    """One text request: the envelope yes/no, and with a conversation the grounding yes/no and the
    intent choice too, all over the same state in one forward pass.

    A decider with ``ask_many`` (``DeciderClient``) is asked all three together. Without a
    conversation there is nothing to ground the arguments in, so only the envelope question is
    asked; a decider with only ``ask_noul`` (the kiosk's stubs) is asked the envelope question
    alone as well. Any failure raises ``DeciderUnavailable`` and the caller denies.
    """
    context = envelope_context(envelope, linear, angular, duration)
    ask_many = getattr(decider, "ask_many", None)
    if conversation is None or not callable(ask_many):
        noul = decider.ask_noul(ENVELOPE_QUESTION, context)
        return TextAnswers(float(noul["probability"]), None, None, None, int(noul["latency_ms"]))
    out = ask_many(text_questions(), {"conversation": conversation, **context})
    answers = out["answers"]
    intent = str(answers["intent"]["class"])
    if intent not in INTENT_CLASSES:
        raise DeciderUnavailable(f"intent {intent!r} is not one of {INTENT_CLASSES}")
    return TextAnswers(
        float(answers["inside_envelope"]["probability"]),
        float(answers["args_grounded"]["probability"]),
        intent,
        float(answers["intent"]["probability"]),
        int(out["latency_ms"]),
    )


#: The conversation the warm-up sends, so the real request's prompt prefix is already cached.
WARM_CONVERSATION = "user: Hop forward twenty centimetres."


# -- event sink ------------------------------------------------------------------------------


@runtime_checkable
class EventSink(Protocol):
    """The part of ``deepracer_agent.events.EventLog`` this module relies on."""

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        beat: str | None = None,
    ) -> dict[str, Any]: ...


class LocalEventLog:
    """Minimal stand-in for ``deepracer_agent.events.EventLog`` with the same line shape (section 4).

    Used only when the Car team's module cannot be imported. Writes ``events.jsonl`` under
    ``$DEEPRACER_RUN_DIR`` (or ``runs/<session>/``) and never raises.
    """

    def __init__(
        self, run_dir: str | Path | None = None, *, session: str | None = None, beat: str | None = None
    ):
        now = _dt.datetime.now(_dt.UTC)
        self.session = session or now.strftime("s-%Y%m%d-%H%M")
        env = os.environ.get("DEEPRACER_RUN_DIR")
        base = (
            Path(run_dir)
            if run_dir is not None
            else (Path(env) if env else _repo_root() / "runs" / self.session)
        )
        self.run_dir = base
        self.beat = beat
        self._seq = 0
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self.run_dir / "events.jsonl"

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        beat: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            event = {
                "ts": utc_now_iso(),
                "seq": self._seq,
                "session": self.session,
                "beat": beat if beat is not None else self.beat,
                "type": type,
                "source": source or "agent",
                "payload": payload or {},
            }
            try:
                self.run_dir.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, default=str, separators=(",", ":")) + "\n")
            except OSError as exc:
                logger.warning("local event log write failed: %s", exc)
        return event

    def read(self, type: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type is None or event.get("type") == type:
                out.append(event)
        return out

    def last(self, type: str) -> dict[str, Any] | None:
        events = self.read(type)
        return events[-1] if events else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now_iso() -> str:
    now = _dt.datetime.now(_dt.UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def wall_ms() -> int:
    """Milliseconds since the epoch."""
    return int(time.time() * 1000)


class VoiceClock:
    """The ``t_ms`` of voice events: milliseconds since the last push-to-talk press.

    ``mark()`` on ``ptt_down`` resets it to 0. Before any press it reads epoch
    milliseconds, which the portal recognises (a value past 1e10) and shows as clock time.
    """

    def __init__(self) -> None:
        self._origin_ms: int | None = None

    def mark(self) -> int:
        self._origin_ms = wall_ms()
        return 0

    def now_ms(self) -> int:
        if self._origin_ms is None:
            return wall_ms()
        return max(0, wall_ms() - self._origin_ms)

    def reset(self) -> None:
        self._origin_ms = None


#: Process-wide: one operator, one push-to-talk, one clock.
voice_clock = VoiceClock()


def resolve_event_log(explicit: EventSink | None = None, **kwargs: Any) -> EventSink:
    """``explicit`` if given, else the Car team's ``EventLog``, else :class:`LocalEventLog`."""
    if explicit is not None:
        return explicit
    try:
        from .events import EventLog  # the Car team's module (CONTRACTS section 4)

        return EventLog(**kwargs)
    except (ImportError, TypeError) as exc:
        logger.debug("falling back to LocalEventLog: %s", exc)
        return LocalEventLog(**kwargs)


# -- frames -----------------------------------------------------------------------------------

FrameSource = Callable[[], Any]
"""Returns JPEG ``bytes``, ``None``, or the ``capture_frame`` tool's ``{"frame_ref", "bytes_b64"}`` dict.
May be sync or async."""


@dataclass(frozen=True)
class Frame:
    jpeg: bytes
    frame_ref: str | None = None


async def grab_frame(source: FrameSource | None) -> Frame | None:
    """Call ``source`` (sync or async) and normalise its result; ``None`` when there is no frame."""
    if source is None:
        return None
    try:
        result = source()
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        logger.warning("frame source failed: %s", exc)
        return None
    return normalise_frame(result)


def normalise_frame(result: Any) -> Frame | None:
    if result is None:
        return None
    if isinstance(result, Frame):
        return result if result.jpeg else None
    if isinstance(result, bytes | bytearray):
        return Frame(bytes(result)) if result else None
    if isinstance(result, dict):
        raw = result.get("bytes") or result.get("jpeg")
        b64 = result.get("bytes_b64")
        ref = result.get("frame_ref")
        if isinstance(raw, bytes | bytearray) and raw:
            return Frame(bytes(raw), ref)
        if isinstance(b64, str) and b64:
            try:
                return Frame(base64.b64decode(b64), ref)
            except ValueError:
                return None
        path = result.get("frame_path")
        if isinstance(path, str) and path:
            # The capture_frame tool hands the model a path, not pixels; the gate reads the file.
            try:
                data = Path(path).read_bytes()
            except OSError:
                return None
            return Frame(data, ref) if data else None
    return None


# -- verdicts ---------------------------------------------------------------------------------


@dataclass
class Verdict:
    """One row of the decision table as it is written to the event log (section 4 ``verdict``)."""

    request_id: str
    stage: Literal["envelope", "frame"]
    action: Action
    reason: str
    cls: str | None = None
    probability: float | None = None
    latency_ms: int = 0
    frame_ref: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "stage": self.stage,
            "action": self.action,
            "reason": self.reason,
            "class": self.cls,
            "probability": self.probability,
            "latency_ms": self.latency_ms,
            "frame_ref": self.frame_ref,
        }


@dataclass
class Decision:
    """The gate's answer for one drive command: the final action and the verdicts behind it."""

    request_id: str
    action: Action
    reason: str
    verdicts: list[Verdict] = field(default_factory=list)
    args: dict[str, Any] = field(default_factory=dict)
    guided_linear: float | None = None
    confirm_prompt: str | None = None

    @property
    def latency_ms(self) -> int:
        return sum(v.latency_ms for v in self.verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
            "stages": [v.payload() for v in self.verdicts],
        }


# -- the frame questions ----------------------------------------------------------------------


def ask_frame_questions(decider: Any, jpeg: bytes) -> tuple[dict[str, Any], dict[str, Any], int]:
    """``(person, frame, latency_ms)``: the yes/no "is a person visible" and the five-way choice
    over ``jpeg``, built from the module constants so the gate, the kiosk and the calibration
    tool ask the same thing.

    A decider with ``ask_frame`` (``DeciderClient``) answers both in one request; anything else
    with ``ask_noul``/``ask_choice`` is asked twice and the latencies are summed. Either way a
    failure raises ``DeciderUnavailable`` and the caller denies: no answer is ever worth less than
    both.
    """
    ask_both = getattr(decider, "ask_frame", None)
    if callable(ask_both):
        both = ask_both(PERSON_QUESTION, FRAME_QUESTION, FRAME_CLASS_DESCRIPTIONS, jpeg)
        return both["person"], both["frame"], int(both["latency_ms"])
    person = decider.ask_noul(PERSON_QUESTION, "", jpeg)
    frame = decider.ask_choice(FRAME_QUESTION, FRAME_CLASS_DESCRIPTIONS, jpeg)
    return person, frame, int(person["latency_ms"]) + int(frame["latency_ms"])


def combine_frame_answers(
    person_probability: float, cls: str, probability: float, threshold: float
) -> tuple[str, float, str | None]:
    """Merge the two frame answers into the one class and probability the decision table reads.

    The yes/no wins only when it says person at or above ``threshold`` and the five-way did not
    already put at least as much probability on ``person_in_frame``. Returns ``(class,
    probability, note)`` where ``note`` names the five-way answer that was overridden, or
    ``None``. Monotone toward Deny: a person "no" never lowers the five-way's answer.
    """
    if person_probability >= threshold and not (
        cls == "person_in_frame" and probability >= person_probability
    ):
        return "person_in_frame", person_probability, f"five-way said {cls} {probability:.2f}"
    return cls, probability, None


def _warm_jpeg(width: int = 480, height: int = 360) -> bytes:
    """A grey JPEG at the camera's size, so the warm-up primes the image path with real token counts."""
    try:
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (width, height), (128, 128, 128)).save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:  # pragma: no cover - PIL absent: fall back to the client's 1x1
        from .decider_client import WARM_JPEG

        return WARM_JPEG


def warm_gate(decider: Any, *, timeout_s: float = 120.0, envelope: Envelope | None = None) -> dict[str, int]:
    """Ask the gate's own two requests once with a long budget, so the first real hop is not cold.

    The booth decider keeps a prefix cache per prompt: a question it has not seen costs 2-4 s on
    MPS (4155 ms measured 2026-10-17 for the envelope question, 148 ms right after), and the gate's
    1.5 s budget then denies with "vision unavailable". The text request is sent in its full
    three-question shape with a sample conversation. Returns the two latencies in ms. Raises
    ``DeciderUnavailable`` when the decider does not answer at all.
    """
    env = envelope or Envelope()
    out: dict[str, int] = {}
    saved = getattr(decider, "timeout_s", None)
    client = getattr(decider, "_client", None)
    if client is not None:
        import httpx

        client.timeout = httpx.Timeout(float(timeout_s))
    try:
        text = ask_text_questions(decider, env, min(0.3, env.max_linear), 0.0, 0.5, WARM_CONVERSATION)
        out["envelope_ms"] = text.latency_ms
        ask_both = getattr(decider, "ask_frame", None)
        if callable(ask_both):
            both = ask_both(PERSON_QUESTION, FRAME_QUESTION, FRAME_CLASS_DESCRIPTIONS, _warm_jpeg())
            out["frame_ms"] = int(both.get("latency_ms", 0))
    finally:
        if client is not None and saved is not None:
            import httpx

            client.timeout = httpx.Timeout(float(saved))
    return out


# -- the gate ---------------------------------------------------------------------------------


@runtime_checkable
class ApprovalBrokerLike(Protocol):
    async def ask(self, request_id: str, prompt: str, timeout_s: float = 30.0) -> bool: ...


class DeciderGate(InterventionHandler):
    """``before_tool_call`` intervention that gates ``drive_deepracer`` with the decider.

    Args:
        decider: A :class:`DeciderClient` (or anything with ``ask_noul``/``ask_choice``).
        frame_source: The Car team's ``capture_frame`` or any callable returning JPEG bytes or
            ``None``; injected so tests and the sim can substitute frames.
        event_log: ``EventLog``-like sink; resolved lazily when ``None``.
        envelope: The briefed :class:`Envelope`.
        approval: The runtime's ``ApprovalBroker`` (section 5). When given, a Confirm is
            resolved inline (``await approval.ask(...)``) and handed to Strands as a
            preemptive response, which is the only Confirm shape ``BidiAgent`` supports
            (bidi raises on tool interrupts). When ``None``, a bare ``Confirm`` is returned
            and a plain ``Agent`` pauses with ``stop_reason == "interrupt"``.
        obstacle_mode: ``"guide"`` (default, contract wording "halve linear, re-plan"):
            return ``Guide`` so the model re-plans at half the linear speed. ``"transform"``:
            halve ``linear`` in place with ``Transform`` and let the hop run slower.
        deny_threshold: Probability at or above which ``person_in_frame``/``unclear`` denies.
        decider_timeout_s: Budget per decider question; the client enforces it, this is
            only reported.
    """

    name = "deepracer:decider-gate"

    def __init__(
        self,
        decider: DeciderClient,
        frame_source: FrameSource | None,
        *,
        event_log: EventSink | None = None,
        envelope: Envelope | None = None,
        approval: ApprovalBrokerLike | None = None,
        gated_tools: tuple[str, ...] = GATED_TOOLS,
        obstacle_mode: Literal["guide", "transform"] = "guide",
        deny_threshold: float = 0.5,
        approval_timeout_s: float = 30.0,
        beat: str | None = None,
    ) -> None:
        self.decider = decider
        self.frame_source = frame_source
        self._event_log = event_log
        self.envelope = envelope or Envelope()
        self.approval = approval
        self.gated_tools = tuple(gated_tools)
        self.obstacle_mode = obstacle_mode
        self.deny_threshold = deny_threshold
        #: "unclear" needs more conviction than the other deny classes: the booth model says
        #: unclear at 0.5-0.6 on plain corridors and desks (calibration study 2026-10-14; a hotel
        #: corridor at 0.54 on 2026-10-17), and 0.90 with a hand over the lens (Blindfold). A weak
        #: unclear proceeds and says so; a strong one still stops. DEEPRACER_UNCLEAR_THRESHOLD overrides.
        self.unclear_threshold = float(os.environ.get("DEEPRACER_UNCLEAR_THRESHOLD", UNCLEAR_THRESHOLD))
        self.approval_timeout_s = approval_timeout_s
        self.beat = beat
        #: Operator switch. ``enforce``: today's gate. ``advisory``: the decider is asked and its
        #: verdict is shown, but a Deny/Guide/Confirm never blocks the hop (payload ``advisory``
        #: true, no stop event). ``off``: no questions at all, one Proceed verdict that says so.
        #: In every mode the upstream command gate and the on-car deadman still stand. Physics
        #: stops the car; the decider explains.
        self.mode: GateMode = "enforce"
        self.last_decision: Decision | None = None

    @property
    def on_error(self) -> OnError:
        """A gate that throws must deny: fail closed."""
        return "deny"

    @property
    def event_log(self) -> EventSink:
        if self._event_log is None:
            self._event_log = resolve_event_log()
        return self._event_log

    @property
    def last_verdict(self) -> dict[str, Any] | None:
        """For ``AgentRuntime.status()["last_verdict"]``."""
        return self.last_decision.to_dict() if self.last_decision else None

    # -- InterventionHandler ------------------------------------------------------------

    async def before_tool_call(
        self, event: BeforeToolCallEvent, **kwargs: Any
    ) -> Proceed | Deny | Guide | Confirm | Transform:
        tool_use = event.tool_use
        if tool_use.get("name") not in self.gated_tools:
            return Proceed()
        request_id = str(tool_use.get("toolUseId") or "")
        raw = tool_use.get("input")
        args = dict(raw) if isinstance(raw, dict) else {}
        messages = getattr(getattr(event, "agent", None), "messages", None)
        conversation = render_conversation(messages) if isinstance(messages, list) else None
        decision = await self.decide(args, request_id=request_id, conversation=conversation)
        return await self._to_action(decision, event)

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.mode = "enforce" if value else "off"

    async def _to_action(
        self, decision: Decision, event: BeforeToolCallEvent | None
    ) -> Proceed | Deny | Guide | Confirm | Transform:
        if self.mode == "advisory" and decision.action != "Proceed":
            note = f"advisory: would have said {decision.action}: {decision.reason}"
            self.event_log.emit("thought", {"text": note}, beat=self.beat)
            return Proceed(reason=note)
        if decision.action == "Deny":
            # A deny is a stop the audience can ask about: the Apology beat reads it back.
            self.event_log.emit(
                "stop",
                {"request_id": decision.request_id, "cause": "deny", "latency_ms": decision.latency_ms},
                beat=self.beat,
            )
            return Deny(reason=decision.reason)
        if decision.action == "Guide":
            half = decision.guided_linear
            if self.obstacle_mode == "transform" and half is not None:

                def _halve(evt: Any, value: float = half) -> None:
                    evt.tool_use["input"]["linear"] = value

                return Transform(apply=_halve, reason=decision.reason)
            return Guide(feedback=decision.reason, reason=decision.reason)
        if decision.action == "Confirm":
            prompt = decision.confirm_prompt or decision.reason
            if self.approval is None:
                return Confirm(prompt=prompt, reason=decision.reason)
            approved, outcome = await self._ask_operator(decision.request_id, prompt)
            self.event_log.emit(
                "approval",
                {"request_id": decision.request_id, "decision": outcome, "by": "operator"},
                beat=self.beat,
            )
            return Confirm(prompt=prompt, reason=decision.reason, response=approved)
        return Proceed(reason=decision.reason)

    async def _ask_operator(self, request_id: str, prompt: str) -> tuple[bool, str]:
        assert self.approval is not None
        try:
            approved = bool(await self.approval.ask(request_id, prompt, timeout_s=self.approval_timeout_s))
        except TimeoutError:
            return False, "timeout"
        return approved, ("approved" if approved else "denied")

    # -- the decision table -------------------------------------------------------------

    async def decide(
        self, args: dict[str, Any], *, request_id: str = "", conversation: str | None = None
    ) -> Decision:
        """Run both requests for ``args`` and emit one ``verdict`` event per stage evaluated.

        Pure with respect to Strands: callable from the Simon Says kiosk or a beat without an
        agent. ``conversation`` is the rendered transcript the grounding questions judge against
        (``before_tool_call`` supplies it); without one only the envelope question and the frame
        pair are asked. Never raises; every failure path is a Deny.
        """
        request_id = request_id or f"req-{wall_ms()}"
        linear = _num(args.get("linear"), 0.0)
        angular = _num(args.get("angular"), 0.0)
        duration = _num(args.get("duration"), 0.5)
        verdicts: list[Verdict] = []
        decision: Decision

        if self.mode == "off":
            verdicts.append(Verdict(request_id, "envelope", "Proceed", GATE_OFF))
            decision = Decision(request_id, "Proceed", GATE_OFF, verdicts, args)
            for verdict in decision.verdicts:
                self.event_log.emit("verdict", verdict.payload(), beat=self.beat)
            self.last_decision = decision
            return decision

        try:
            frame = await grab_frame(self.frame_source)
            if frame is None:
                verdicts.append(Verdict(request_id, "frame", "Deny", VISION_UNAVAILABLE))
                decision = Decision(request_id, "Deny", VISION_UNAVAILABLE, verdicts, args)
            else:
                decision = await self._decide_with_frame(
                    request_id, args, linear, angular, duration, frame, verdicts, conversation
                )
        except Exception as exc:
            logger.warning("gate failed closed: %s", exc)
            stage: Literal["envelope", "frame"] = "frame" if not verdicts else "envelope"
            verdicts.append(Verdict(request_id, stage, "Deny", VISION_UNAVAILABLE))
            decision = Decision(request_id, "Deny", VISION_UNAVAILABLE, verdicts, args)

        for verdict in decision.verdicts:
            payload = verdict.payload()
            if self.mode == "advisory":
                payload["advisory"] = True
            self.event_log.emit("verdict", payload, beat=self.beat)
        self.last_decision = decision
        return decision

    async def _decide_with_frame(
        self,
        request_id: str,
        args: dict[str, Any],
        linear: float,
        angular: float,
        duration: float,
        frame: Frame,
        verdicts: list[Verdict],
        conversation: str | None = None,
    ) -> Decision:
        # 1. the text request: envelope yes/no, grounding yes/no and intent, one forward pass
        violations = self.envelope.violations(linear, angular, duration)
        try:
            text = await asyncio.to_thread(
                ask_text_questions, self.decider, self.envelope, linear, angular, duration, conversation
            )
        except DeciderUnavailable as exc:
            logger.warning("text questions failed: %s", exc)
            verdicts.append(
                Verdict(request_id, "envelope", "Deny", VISION_UNAVAILABLE, frame_ref=frame.frame_ref)
            )
            return Decision(request_id, "Deny", VISION_UNAVAILABLE, verdicts, args)
        text_action, text_reason = self._text_rows(text, violations)
        verdicts.append(
            Verdict(
                request_id,
                "envelope",
                text_action,
                text_reason,
                probability=text.inside,
                latency_ms=text.latency_ms,
                frame_ref=frame.frame_ref,
            )
        )

        # 2. the frame request: the person yes/no and the five-way choice, one request, one frame
        try:
            person, choice, latency = await asyncio.to_thread(ask_frame_questions, self.decider, frame.jpeg)
        except DeciderUnavailable as exc:
            logger.warning("frame question failed: %s", exc)
            verdicts.append(
                Verdict(request_id, "frame", "Deny", VISION_UNAVAILABLE, frame_ref=frame.frame_ref)
            )
            return Decision(request_id, "Deny", VISION_UNAVAILABLE, verdicts, args)
        cls, p, overridden = combine_frame_answers(
            float(person["probability"]),
            str(choice["class"]),
            float(choice["probability"]),
            self.deny_threshold,
        )
        frame_action, frame_reason, guided_linear = self._frame_rows(cls, p, overridden, linear)
        verdicts.append(
            Verdict(request_id, "frame", frame_action, frame_reason, cls, p, latency, frame.frame_ref)
        )

        # 3. the table across both requests, rows in order (module docstring; CONTRACTS section 7)
        final: Action
        if frame_action == "Deny":  # rows 3, 4, 5
            final, reason = "Deny", frame_reason
        elif text_action == "Deny":  # row 6
            final, reason = "Deny", text_reason
        elif violations:  # row 7: on the car the marshal may approve a bigger hop
            final, reason = "Confirm", text_reason
        elif text_action == "Guide":  # rows 8, 9, 10
            final, reason = "Guide", text_reason
        elif frame_action == "Guide":  # row 11
            final, reason = "Guide", frame_reason
        elif text_action == "Confirm":  # row 12
            final, reason = "Confirm", text_reason
        else:  # row 13
            final, reason = "Proceed", f"{text_reason}; {frame_reason}"
        confirm_prompt: str | None = None
        if final == "Confirm":
            confirm_prompt = (
                f"drive_deepracer linear={linear:g} angular={angular:g} duration={duration:g}: "
                f"{text_reason}. Approve?"
            )
        if not (final == "Guide" and reason == frame_reason):
            guided_linear = None  # only the obstacle row re-plans at half speed
        return Decision(request_id, final, reason, verdicts, args, guided_linear, confirm_prompt)

    def _text_rows(self, text: TextAnswers, violations: list[str]) -> tuple[Action, str]:
        """Rows 6 to 13 over the text answers alone; the frame rows are merged in by the caller.
        Rows 6, 9 and 10 need the grounding answers and are skipped when they were not asked."""
        asked = text.asked_grounding
        intent_p = text.intent_p or 0.0
        if asked and text.intent == "stop" and intent_p >= YES:
            return "Deny", f"the user asked to stop (p={intent_p:.2f})"
        if violations:
            return "Confirm", f"outside envelope: {'; '.join(violations)}"
        if text.inside < NO:
            return "Guide", (
                f"outside envelope per decider (p={text.inside:.2f}): re-plan inside the envelope "
                f"({self.envelope.describe()})"
            )
        if asked and text.grounded is not None and text.grounded < NO:
            return "Guide", (
                f"arguments not grounded (p={text.grounded:.2f}): ask the user for the values "
                f"instead of inventing them"
            )
        if asked and text.intent in ("question", "unrelated") and intent_p >= YES:
            return "Guide", f"intent {text.intent} (p={intent_p:.2f}): answer the user instead of moving"
        grounded_txt = f"{text.grounded:.2f}" if asked and text.grounded is not None else "not asked"
        if text.inside < YES or (asked and text.grounded is not None and text.grounded < YES):
            return "Confirm", f"unclear: inside={text.inside:.2f} grounded={grounded_txt}: ask the operator"
        reason = f"inside envelope (p={text.inside:.2f})"
        if asked:
            reason += f", grounded (p={text.grounded:.2f}), intent {text.intent} (p={intent_p:.2f})"
        return "Proceed", reason

    def _frame_rows(
        self, cls: str, p: float, overridden: str | None, linear: float
    ) -> tuple[Action, str, float | None]:
        """Rows 3, 4, 5, 11 and 13 over the merged frame answer: ``(action, reason, guided_linear)``."""
        if cls == "off_surface":
            bar = 0.0  # row 4: the chosen class alone decides
        elif cls == "unclear":
            bar = self.unclear_threshold  # row 5
        else:
            bar = self.deny_threshold  # row 3
        if cls in DENY_CLASSES and p >= bar:
            reason = f"{cls} (p={p:.2f}): stopping; {PLAIN_REASON.get(cls, cls)}"
            if overridden:
                reason += f" ({overridden})"
            return "Deny", reason, None
        if cls == "unclear":
            return "Proceed", f"unclear (p={p:.2f}) below the {bar:.2f} bar: a weak call, proceeding", None
        if cls == "obstacle_near":
            half = round(linear / 2.0, 3)
            return (
                "Guide",
                f"obstacle_near (p={p:.2f}): re-plan at half speed, linear <= {abs(half):g} m/s, or stop",
                half,
            )
        return "Proceed", f"{cls} (p={p:.2f})", None


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# -- barge-in --------------------------------------------------------------------------------


class BargeInStop:
    """Bidi hook for the Red Light beat: the presenter says "stop", the wheels stop.

    Registers on ``strands.bidi.hooks.BidiBargeInEvent`` (Nova Sonic reports the user speaking
    over the assistant as ``stopReason: INTERRUPTED``). Also usable as an ``OutputStream`` so
    a user transcript starting while a drive is active triggers the same path. Each trigger
    writes a ``voice`` event (``barge_in``, ``t_ms`` milliseconds since push-to-talk), calls
    ``runtime.stop_all()``, then writes a ``stop`` event with ``cause: barge_in`` and the
    measured ``latency_ms``.

    Args:
        runtime: Anything with ``async stop_all()`` (CONTRACTS section 5 ``AgentRuntime``).
        event_log: Event sink; resolved lazily when ``None``.
        is_driving: Optional predicate. The barge-in hook always stops (the rover was
            speaking, so a drive may be in flight). The transcript-start path stops only when
            ``is_driving()`` is true; with no predicate it falls back to
            ``runtime.is_driving()`` when that exists, otherwise it only logs ``speech_start``.
    """

    def __init__(
        self,
        runtime: Any,
        event_log: EventSink | None = None,
        *,
        is_driving: Callable[[], bool] | None = None,
        beat: str | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.runtime = runtime
        self._event_log = event_log
        self._is_driving = is_driving
        self.beat = beat
        self._clock = clock
        self.last: dict[str, Any] | None = None
        self.count = 0
        self._lock = asyncio.Lock()

    @property
    def event_log(self) -> EventSink:
        if self._event_log is None:
            self._event_log = resolve_event_log()
        return self._event_log

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        from strands.bidi.hooks import BidiBargeInEvent

        registry.add_callback(BidiBargeInEvent, self.on_barge_in)

    async def on_barge_in(self, event: Any = None) -> None:
        await self.trigger()

    def is_driving(self) -> bool:
        if self._is_driving is not None:
            return bool(self._is_driving())
        probe = getattr(self.runtime, "is_driving", None)
        if callable(probe):
            try:
                return bool(probe())
            except Exception:
                return False
        return False

    async def __call__(self, event: Any) -> None:
        """OutputStream: a user transcript starting mid-drive is a barge-in too."""
        from strands.bidi.types.events import BidiTranscriptStartEvent

        if isinstance(event, BidiTranscriptStartEvent) and event.role == "user":
            self.event_log.emit(
                "voice", {"event": "speech_start", "text": None, "t_ms": voice_clock.now_ms()}, beat=self.beat
            )
            if self.is_driving():
                await self.trigger()

    async def trigger(self) -> dict[str, Any]:
        """Stop now and record it. Returns ``{"t_ms", "stop_t_ms", "latency_ms"}``."""
        async with self._lock:
            t_ms = voice_clock.now_ms()
            t0 = self._clock()
            self.event_log.emit("voice", {"event": "barge_in", "text": None, "t_ms": t_ms}, beat=self.beat)
            error: str | None = None
            try:
                result = self.runtime.stop_all()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                error = str(exc)
                logger.error("stop_all failed during barge-in: %s", exc)
            latency_ms = round((self._clock() - t0) * 1000)
            self.event_log.emit(
                "stop", {"request_id": None, "cause": "barge_in", "latency_ms": latency_ms}, beat=self.beat
            )
            if error:
                self.event_log.emit("error", {"where": "gate.BargeInStop", "message": error}, beat=self.beat)
            self.count += 1
            self.last = {
                "t_ms": t_ms,
                "stop_t_ms": voice_clock.now_ms(),
                "latency_ms": latency_ms,
                "error": error,
            }
            return self.last


__all__ = [
    "DENY_CLASSES",
    "ENVELOPE_QUESTION",
    "FRAME_CLASSES",
    "FRAME_CLASS_DESCRIPTIONS",
    "FRAME_QUESTION",
    "GATED_TOOLS",
    "GATE_MODES",
    "GROUNDED_CRITERIA",
    "GROUNDED_QUESTION",
    "INTENT_CLASSES",
    "INTENT_CLASS_DESCRIPTIONS",
    "INTENT_QUESTION",
    "NO",
    "PERSON_QUESTION",
    "UNCLEAR_THRESHOLD",
    "VISION_UNAVAILABLE",
    "YES",
    "Action",
    "ApprovalBrokerLike",
    "BargeInStop",
    "DeciderGate",
    "Decision",
    "Envelope",
    "EventSink",
    "Frame",
    "FrameSource",
    "LocalEventLog",
    "TextAnswers",
    "Verdict",
    "ask_frame_questions",
    "ask_text_questions",
    "combine_frame_answers",
    "envelope_context",
    "grab_frame",
    "normalise_frame",
    "render_conversation",
    "resolve_event_log",
    "text_questions",
    "utc_now_iso",
    "wall_ms",
    "warm_gate",
]
