"""The two booth kiosks, Frame Judge and Simon Says, as functions the portal can call all day.

Frame Judge: an attendee holds anything to the camera; ``judge`` asks the decider for a class
and probability over the labels on the card (the presenter can add one live with
:class:`LabelCard`, no retraining) and, when a vision client is given, a one-line caption.
``judge_frame`` wraps it for the booth: it writes one ``verdict`` event (beat ``kiosk-judge``)
per judgement, saves the frame to the run dir and writes a ``frame`` event only when the
attendee consented, and feeds the :class:`Leaderboard` of best fools (the attendees whose
object the decider got wrong or was least sure about). Simon Says: an attendee types a command;
``simon`` turns it into one ``drive_deepracer`` call and runs the real gate, returning Proceed,
Guide, Confirm or Deny with the reason card, the slower re-plan the gate would take, and a Box
egress log (which hosts the kiosk talked to and for how long, taken from what the gate already
measured). Frames of people never leave the run dir. Physics stops the car; the decider explains;
the kiosks are the decider explaining all day, never a safety claim.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import inspect
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from deepracer_agent.decider_client import DEFAULT_DECIDER_URL, DeciderClient, DeciderUnavailable
from deepracer_agent.gate import (
    DENY_CLASSES,
    FRAME_CLASS_DESCRIPTIONS,
    FRAME_CLASSES,
    VISION_UNAVAILABLE,
    DeciderGate,
    Decision,
    Envelope,
    EventSink,
    utc_now_iso,
    wall_ms,
)
from deepracer_agent.prompts import KIOSK_FRAME_JUDGE_PROMPT

logger = logging.getLogger(__name__)

JUDGE_QUESTION = "What is the attendee holding up to the camera?"
JUDGE_BEAT = "kiosk-judge"
SIMON_BEAT = "kiosk-simon"
#: The judge is not gating motion, so it may wait longer than the gate's 1.5 s for a CPU decider.
JUDGE_DECIDER_TIMEOUT_S = 5.0
MAX_LABELS = 12
MAX_LABEL_CHARS = 32
MAX_NICKNAME_CHARS = 40
LEADERBOARD_SIZE = 10
NO_MODEL_NOTE = (
    "No model call: Simon Says parses the text locally and asks only the decider; "
    "the camera grab is listed when the kiosk timed it."
)

_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")
_LABEL_CLEAN = re.compile(r"[^a-z0-9]+")

#: Number words a typed command is likely to use ("two metres per second", "ten seconds").
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "hundred": 100,
}  # fmt: skip
_NUMBER_WORD_RE = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b")
_HALF_RE = re.compile(r"\b(?:a )?half (?:a |an )?(?=m/s|metre|meter|second|sec\b)")
_ARTICLE_UNIT_RE = re.compile(r"\b(?:a|an|one) (?=(?:metre|meter)s? per second|second\b|sec\b)")


def words_to_digits(text: str) -> str:
    """``"two metres per second for ten seconds"`` -> ``"2 metres per second for 10 seconds"``.

    Only the words the typed-command grammar needs; a phrase the table does not know is left
    alone and the parser falls back to its defaults (a 0.3 m/s hop of 0.5 s).
    """
    low = text.lower()
    low = _HALF_RE.sub("0.5 ", low)
    low = _ARTICLE_UNIT_RE.sub("1 ", low)
    return _NUMBER_WORD_RE.sub(lambda m: str(_NUMBER_WORDS[m.group(1)]), low)


def judge(
    frame_bytes: bytes,
    labels: Sequence[str] | dict[str, str | None],
    *,
    decider: DeciderClient | None = None,
    vlm: Any = None,
    caption_question: str = JUDGE_QUESTION,
) -> dict[str, Any]:
    """Frame Judge: decider class and probability over ``labels`` (plus an optional VLM caption)."""
    decider = decider or DeciderClient()
    if isinstance(labels, dict):
        criteria: dict[str, Any] = dict(labels)
    else:
        criteria = {lbl: FRAME_CLASS_DESCRIPTIONS.get(lbl) for lbl in labels}
    try:
        verdict = decider.ask_choice(JUDGE_QUESTION, criteria, image_bytes=frame_bytes)
        out: dict[str, Any] = {
            "class": verdict["class"],
            "probability": verdict["probability"],
            "latency_ms": verdict["latency_ms"],
            "probabilities": verdict["probabilities"],
            "error": None,
        }
    except (DeciderUnavailable, ValueError) as exc:
        out = {"class": None, "probability": None, "latency_ms": None, "probabilities": {}, "error": str(exc)}
    out["caption"] = None
    if vlm is not None:
        from deepracer_agent.look import describe_frame

        try:
            out["caption"] = describe_frame(
                frame_bytes, caption_question, client=vlm, system_prompt=KIOSK_FRAME_JUDGE_PROMPT
            )
        except Exception as exc:
            out["caption_error"] = str(exc)
    return out


# -- Frame Judge: the label card ---------------------------------------------------------------------


def normalise_label(label: Any) -> str:
    """``" Running Shoe "`` -> ``"running_shoe"``; raises ``ValueError`` for an empty or overlong label."""
    if not isinstance(label, str):
        raise ValueError("label must be a string")
    key = _LABEL_CLEAN.sub("_", label.strip().lower()).strip("_")
    if not key:
        raise ValueError("label is empty")
    if len(key) > MAX_LABEL_CHARS:
        raise ValueError(f"label longer than {MAX_LABEL_CHARS} characters")
    return key


class LabelCard:
    """The labels the Frame Judge asks over: the five frame classes plus what the presenter adds live.

    Adding a label changes the next question's criteria and nothing else; the decider is never
    retrained. The card never drops below two labels (a choice needs two options).
    """

    def __init__(self, labels: Iterable[str] | None = None, *, max_labels: int = MAX_LABELS) -> None:
        self.max_labels = max_labels
        self._labels: dict[str, str | None] = {}
        self._lock = threading.Lock()
        for lbl in labels if labels is not None else FRAME_CLASSES:
            self.add(lbl)

    def add(self, label: str, description: str | None = None) -> str:
        key = normalise_label(label)
        with self._lock:
            if key not in self._labels and len(self._labels) >= self.max_labels:
                raise ValueError(f"the card holds at most {self.max_labels} labels")
            desc = description.strip() if isinstance(description, str) and description.strip() else None
            self._labels[key] = desc or FRAME_CLASS_DESCRIPTIONS.get(key) or self._labels.get(key)
        return key

    def remove(self, label: str) -> bool:
        key = normalise_label(label)
        with self._lock:
            if key not in self._labels:
                return False
            if len(self._labels) <= 2:
                raise ValueError("the card needs at least two labels")
            del self._labels[key]
        return True

    def labels(self) -> list[str]:
        with self._lock:
            return list(self._labels)

    def criteria(self) -> dict[str, str | None]:
        with self._lock:
            return dict(self._labels)

    def to_list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"label": k, "description": v, "builtin": k in FRAME_CLASSES} for k, v in self._labels.items()
            ]

    def __len__(self) -> int:
        return len(self._labels)

    def __contains__(self, label: object) -> bool:
        try:
            return normalise_label(label) in self._labels
        except ValueError:
            return False


# -- Frame Judge: the leaderboard of best fools -------------------------------------------------------


@dataclass
class Judgement:
    """One Frame Judge verdict as the leaderboard scores it."""

    nickname: str
    cls: str | None
    probability: float | None
    latency_ms: int | None
    labels: list[str] = field(default_factory=list)
    expected: str | None = None
    consent: bool = False
    frame_ref: str | None = None
    ts: str = field(default_factory=utc_now_iso)
    request_id: str = ""
    error: str | None = None

    @property
    def wrong(self) -> bool:
        """The attendee said what they held and the decider picked something else."""
        return self.expected is not None and self.cls is not None and self.cls != self.expected

    @property
    def fool_score(self) -> float:
        """Wrong class beats low confidence; a decider that did not answer scores nothing."""
        if self.cls is None or self.probability is None:
            return 0.0
        return (1.0 if self.wrong else 0.0) + (1.0 - max(0.0, min(1.0, self.probability)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nickname": self.nickname,
            "class": self.cls,
            "probability": self.probability,
            "latency_ms": self.latency_ms,
            "labels": list(self.labels),
            "expected": self.expected,
            "consent": self.consent,
            "frame_ref": self.frame_ref,
            "ts": self.ts,
            "request_id": self.request_id,
            "wrong": self.wrong,
            "fool_score": round(self.fool_score, 4),
            "error": self.error,
        }

    @classmethod
    def from_verdict_event(cls, event: dict[str, Any]) -> Judgement | None:
        """Rebuild from a ``verdict`` event with beat ``kiosk-judge``; ``None`` for anything else."""
        if event.get("type") != "verdict" or event.get("beat") != JUDGE_BEAT:
            return None
        p = event.get("payload") or {}
        nickname = p.get("nickname")
        if not isinstance(nickname, str) or not nickname:
            return None
        prob = p.get("probability")
        return cls(
            nickname=nickname,
            cls=p.get("class"),
            probability=float(prob) if isinstance(prob, int | float) else None,
            latency_ms=p.get("latency_ms"),
            labels=[str(x) for x in (p.get("labels") or [])],
            expected=p.get("expected"),
            consent=bool(p.get("consent", False)),
            frame_ref=p.get("frame_ref"),
            ts=str(event.get("ts") or utc_now_iso()),
            request_id=str(p.get("request_id") or ""),
            error=None if p.get("class") is not None else str(p.get("reason") or ""),
        )


class Leaderboard:
    """Best fools: per nickname, the judgement where the decider was wrong or least sure.

    Lives in memory for the session; the record on disk is the ``verdict`` events (beat
    ``kiosk-judge``) in the run's ``events.jsonl``, which :meth:`load` reads back after a restart.
    """

    def __init__(self) -> None:
        self.judgements: list[Judgement] = []
        self._lock = threading.Lock()

    def record(self, judgement: Judgement) -> None:
        with self._lock:
            self.judgements.append(judgement)

    def __len__(self) -> int:
        return len(self.judgements)

    def top(self, n: int = LEADERBOARD_SIZE) -> list[dict[str, Any]]:
        with self._lock:
            best: dict[str, Judgement] = {}
            tries: dict[str, int] = {}
            for j in self.judgements:
                tries[j.nickname] = tries.get(j.nickname, 0) + 1
                cur = best.get(j.nickname)
                if cur is None or j.fool_score > cur.fool_score:
                    best[j.nickname] = j
        ranked = sorted(best.values(), key=lambda j: (-j.fool_score, j.ts))
        out = []
        for rank, j in enumerate(ranked[:n], start=1):
            row = j.to_dict()
            row["rank"] = rank
            row["tries"] = tries[j.nickname]
            out.append(row)
        return out

    @classmethod
    def from_events(cls, events: Iterable[dict[str, Any]]) -> Leaderboard:
        board = cls()
        for event in events:
            j = Judgement.from_verdict_event(event)
            if j is not None:
                board.record(j)
        return board

    @classmethod
    def load(cls, events_path: Path | str) -> Leaderboard:
        path = Path(events_path)
        if not path.is_file():
            return cls()
        events: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError as exc:
            logger.warning("leaderboard could not read %s: %s", path, exc)
        return cls.from_events(events)


# -- Frame Judge: one judgement with consent ----------------------------------------------------------


def decider_host(decider: Any) -> str:
    """The host:port the decider client talks to, for the egress log."""
    url = getattr(decider, "base_url", None) or DEFAULT_DECIDER_URL
    parsed = urlparse(str(url))
    return parsed.netloc or str(url)


def egress_entry(what: str, host: str, ms: int | float | None) -> dict[str, Any]:
    return {"what": what, "host": host, "ms": None if ms is None else round(ms)}


def _save_kiosk_frame(frame_bytes: bytes, run_dir: Path) -> tuple[str, int, int]:
    """Write the consented frame under ``run_dir/frames`` and return ``(frame_ref, width, height)``."""
    from deepracer_agent.events import jpeg_dimensions

    frames = run_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
    name = f"kiosk-judge-{stamp}.jpg"
    (frames / name).write_bytes(frame_bytes)
    dims = jpeg_dimensions(frame_bytes) or (0, 0)
    return f"frames/{name}", int(dims[0] or 0), int(dims[1] or 0)


def judge_frame(
    frame_bytes: bytes,
    card: LabelCard | Sequence[str] | dict[str, str | None],
    *,
    nickname: str,
    consent: bool = False,
    expected: str | None = None,
    decider: DeciderClient | None = None,
    event_log: EventSink | None = None,
    run_dir: Path | str | None = None,
    leaderboard: Leaderboard | None = None,
    vlm: Any = None,
) -> dict[str, Any]:
    """One booth judgement: ask the decider over the card, record it, keep the frame only with consent.

    Emits one ``verdict`` event (beat ``kiosk-judge``, stage ``frame``) whose payload carries the
    contract fields plus ``nickname``, ``expected``, ``labels``, ``consent`` and ``probabilities``.
    With ``consent`` the frame is written to ``run_dir/frames`` and a ``frame`` event follows;
    without it the bytes are judged in memory and this function keeps no reference to them.
    The ``action`` is what the gate's table would say about this frame (``Deny`` for a person or
    an unreadable frame, ``Guide`` for an obstacle, ``Proceed`` otherwise), an explanation, never a
    stop: nothing is driving.
    """
    nick = (nickname or "").strip()[:MAX_NICKNAME_CHARS]
    if not nick:
        raise ValueError("nickname is empty")
    if isinstance(card, LabelCard):
        criteria = card.criteria()
    elif isinstance(card, dict):
        criteria = dict(card)
    else:
        criteria = {lbl: FRAME_CLASS_DESCRIPTIONS.get(lbl) for lbl in card}
    labels = list(criteria)
    expected_key: str | None = None
    if isinstance(expected, str) and expected.strip():
        expected_key = normalise_label(expected)
    request_id = f"kiosk-judge-{wall_ms()}"
    ts = utc_now_iso()

    out = judge(frame_bytes, criteria, decider=decider, vlm=vlm)
    cls = out["class"]
    p = out["probability"]

    frame_ref: str | None = None
    frame_saved = False
    if consent and run_dir is not None and frame_bytes:
        try:
            frame_ref, width, height = _save_kiosk_frame(frame_bytes, Path(run_dir))
            frame_saved = True
            if event_log is not None:
                event_log.emit(
                    "frame",
                    {"frame_ref": frame_ref, "width": width, "height": height},
                    source="kiosk",
                    beat=JUDGE_BEAT,
                )
        except OSError as exc:
            logger.warning("kiosk frame not saved: %s", exc)
            out["frame_error"] = str(exc)

    judgement = Judgement(
        nickname=nick,
        cls=cls,
        probability=p,
        latency_ms=out["latency_ms"],
        labels=labels,
        expected=expected_key,
        consent=bool(consent),
        frame_ref=frame_ref,
        ts=ts,
        request_id=request_id,
        error=out["error"],
    )
    if cls is None:
        action, reason = "Deny", f"{nick}: {VISION_UNAVAILABLE} ({out['error']})"
    else:
        if cls in DENY_CLASSES and p is not None and p >= 0.5:
            action = "Deny"
        elif cls == "obstacle_near":
            action = "Guide"
        else:
            action = "Proceed"
        reason = f"{nick}: {cls} (p={p:.2f})"
        if expected_key is not None:
            reason += f", said {expected_key}: " + ("fooled it" if judgement.wrong else "agreed")
    if event_log is not None:
        event_log.emit(
            "verdict",
            {
                "request_id": request_id,
                "stage": "frame",
                "action": action,
                "reason": reason,
                "class": cls,
                "probability": p,
                "latency_ms": out["latency_ms"] or 0,
                "frame_ref": frame_ref,
                "nickname": nick,
                "expected": expected_key,
                "labels": labels,
                "consent": bool(consent),
                "probabilities": out["probabilities"],
            },
            source="kiosk",
            beat=JUDGE_BEAT,
        )
    if leaderboard is not None:
        leaderboard.record(judgement)

    egress = [egress_entry("decider POST /v1/systemone (choice)", decider_host(decider), out["latency_ms"])]
    return {
        **out,
        "request_id": request_id,
        "ts": ts,
        "nickname": nick,
        "expected": expected_key,
        "labels": labels,
        "consent": bool(consent),
        "frame_saved": frame_saved,
        "frame_ref": frame_ref,
        "action": action,
        "reason": reason,
        "wrong": judgement.wrong,
        "fool_score": round(judgement.fool_score, 4),
        "egress": egress,
    }


# -- Simon Says ---------------------------------------------------------------------------------------


class TimedFrameSource:
    """Wraps a frame source (sync or async) so the kiosk can say how long the camera grab took."""

    def __init__(self, source: Callable[[], Any], *, host: str) -> None:
        self.source = source
        self.host = host
        self.last_ms: int | None = None

    async def __call__(self) -> Any:
        started = time.perf_counter()
        try:
            result = self.source()
            if inspect.isawaitable(result):
                result = await result
        finally:
            self.last_ms = round((time.perf_counter() - started) * 1000)
        return result


def parse_command(text: str, envelope: Envelope | None = None) -> dict[str, Any] | None:
    """A tiny grammar for typed commands: direction, speed words or numbers, and a duration.

    Returns ``drive_deepracer`` args, or ``None`` when the text is not a motion command (the
    kiosk then answers in words). "fast" deliberately exceeds the envelope so the gate's Confirm
    and the slower re-plan show up on the card.
    """
    envelope = envelope or Envelope()
    low = words_to_digits(text)
    if not any(
        w in low
        for w in ("forward", "ahead", "back", "reverse", "drive", "go", "move", "hop", "roll", "turn")
    ):
        return None
    linear = min(envelope.max_linear, 0.3)
    if "fast" in low or "full" in low or "max" in low:
        linear = round(envelope.max_linear * 2, 3)
    elif "slow" in low or "gentl" in low or "creep" in low:
        linear = round(envelope.max_linear / 2, 3)
    speed = re.search(r"(\d+(?:\.\d+)?)\s*(?:m/s|metres? per second|meters? per second)", low)
    if speed:
        linear = float(speed.group(1))
    if "back" in low or "reverse" in low:
        linear = -abs(linear)
    angular = 0.0
    if "left" in low:
        angular = 0.5
    elif "right" in low:
        angular = -0.5
    if ("turn" in low or "spin" in low) and not any(
        w in low for w in ("forward", "ahead", "back", "roll", "drive")
    ):
        linear = 0.0  # yaw at rest; the driver refuses this and the card says why
    duration = 0.5
    dur = re.search(r"(\d+(?:\.\d+)?)\s*(?:s\b|sec|second)", low)
    if dur:
        duration = float(dur.group(1))
    return {"linear": linear, "angular": angular, "duration": duration}


def replan_for(decision: Decision, args: dict[str, Any], envelope: Envelope) -> dict[str, Any] | None:
    """The slower plan the gate's answer implies: half speed on Guide, clipped to the envelope on Confirm."""
    if decision.action == "Guide" and decision.guided_linear is not None:
        return {**args, "linear": decision.guided_linear}
    if decision.action == "Confirm":
        linear = float(args.get("linear", 0.0))
        angular = float(args.get("angular", 0.0))
        duration = float(args.get("duration", 0.5))
        sign = -1.0 if linear < 0 else 1.0
        return {
            "linear": round(sign * min(abs(linear), envelope.max_linear), 3),
            "angular": round(max(-envelope.max_angular, min(envelope.max_angular, angular)), 3),
            "duration": round(min(max(duration, 0.1), envelope.max_duration_s), 3),
        }
    return None


def _describe_plan(plan: dict[str, Any]) -> str:
    direction = "back" if plan["linear"] < 0 else "forward"
    return f"{direction} at {abs(plan['linear']):g} m/s for {plan['duration']:g} s"


def simon_egress(gate: DeciderGate, decision: Decision | None) -> list[dict[str, Any]]:
    """The outbound calls behind one Simon Says answer, from what the gate already measured."""
    out: list[dict[str, Any]] = []
    source = gate.frame_source
    if isinstance(source, TimedFrameSource) and source.last_ms is not None:
        out.append(egress_entry("camera console GET /route (one frame)", source.host, source.last_ms))
    if decision is not None:
        host = decider_host(gate.decider)
        kind = {"envelope": "noul", "frame": "person noul + choice"}
        for v in decision.verdicts:
            if v.reason == VISION_UNAVAILABLE and v.latency_ms == 0:
                out.append(egress_entry(f"decider POST /v1/systemone ({v.stage}): no answer", host, None))
            else:
                what = f"decider POST /v1/systemone ({v.stage}, {kind.get(v.stage, '?')})"
                out.append(egress_entry(what, host, v.latency_ms))
    return out


def _words_result(text: str, args: dict[str, Any] | None, action: str | None, reason: str, card: str) -> dict:
    return {
        "text": text,
        "ts": utc_now_iso(),
        "request_id": None,
        "command": args,
        "action": action,
        "reason": reason,
        "card": card,
        "latency_ms": None,
        "class": None,
        "probability": None,
        "stages": [],
        "replan": None,
        "egress": [],
        "egress_note": NO_MODEL_NOTE,
    }


async def simon_async(text: str, gate: DeciderGate, *, envelope: Envelope | None = None) -> dict[str, Any]:
    """Simon Says: parse ``text`` and run the gate's decision table. Returns the reason card."""
    envelope = envelope or gate.envelope
    args = parse_command(text, envelope)
    if args is None:
        return _words_result(
            text,
            None,
            None,
            "not a motion command",
            "That is not a drive command; try 'hop forward' or 'go forward fast for two seconds'.",
        )
    if args["linear"] == 0.0 and args["angular"] != 0.0:
        return _words_result(
            text,
            args,
            "Deny",
            "Ackermann cannot yaw at rest",
            "Deny: a car cannot turn on the spot. Ask for a rolling turn: 'roll forward and turn left'.",
        )
    request_id = f"kiosk-simon-{wall_ms()}"
    decision = await gate.decide(args, request_id=request_id)
    replan = replan_for(decision, args, envelope)
    cards = {
        "Proceed": f"Proceed: {decision.reason}.",
        "Guide": f"Guide: {decision.reason}.",
        "Confirm": f"Confirm: {decision.reason}. An operator must approve this one.",
        "Deny": f"Deny: {decision.reason}.",
    }
    card = cards[decision.action]
    if replan is not None:
        card += f" The gate would take: {_describe_plan(replan)}."
    frame = next((v for v in decision.verdicts if v.stage == "frame"), None)
    return {
        "text": text,
        "ts": utc_now_iso(),
        "request_id": request_id,
        "command": args,
        "action": decision.action,
        "reason": decision.reason,
        "card": card,
        "latency_ms": decision.latency_ms,
        "class": frame.cls if frame else None,
        "probability": frame.probability if frame else None,
        "stages": [v.payload() for v in decision.verdicts],
        "replan": replan,
        "egress": simon_egress(gate, decision),
        "egress_note": NO_MODEL_NOTE,
    }


def simon(text: str, gate: DeciderGate, *, envelope: Envelope | None = None) -> dict[str, Any]:
    """Synchronous wrapper around :func:`simon_async` for the portal's request handler."""
    return asyncio.run(simon_async(text, gate, envelope=envelope))


__all__ = [
    "JUDGE_BEAT",
    "JUDGE_DECIDER_TIMEOUT_S",
    "JUDGE_QUESTION",
    "MAX_LABELS",
    "MAX_NICKNAME_CHARS",
    "NO_MODEL_NOTE",
    "SIMON_BEAT",
    "Judgement",
    "LabelCard",
    "Leaderboard",
    "TimedFrameSource",
    "decider_host",
    "egress_entry",
    "judge",
    "judge_frame",
    "normalise_label",
    "parse_command",
    "replan_for",
    "simon",
    "simon_async",
    "simon_egress",
]


# -- Simon Says: shapes ------------------------------------------------------------------------------


def plan(text: str, *, calibration: Any = None, pen: Any = None) -> dict[str, Any]:
    """Simon Says, shapes: a typed request ("square of 60 cm") returns the validated plan or the refusal.

    Nothing moves: the card shows the hops the rover would ask for, the footprint and the time, or
    the reason the validator said no (too big for the pen, tighter than the wheels can steer).
    """
    from deepracer_agent.shapes import SHAPE_NAMES, parse_shape_request, propose

    parsed = parse_shape_request(text)
    if parsed is None:
        return {
            "shape": None,
            "size_m": None,
            "ok": False,
            "steps": [],
            "reasons": ["no shape named"],
            "card": (
                "Name a shape and a size: 'square of 60 cm', 'circle 1 m across', 'figure 8 half a metre'. "
                f"I know: {', '.join(SHAPE_NAMES)}."
            ),
        }
    shape, size_m = parsed
    proposal = propose(shape, size_m, calibration=calibration, pen=pen)
    narration = proposal.narration()
    return {
        "shape": proposal.shape,
        "size_m": proposal.size_m,
        "ok": proposal.ok,
        "steps": [s.to_dict() for s in proposal.plan.steps] if proposal.ok and proposal.plan else [],
        "reasons": list(proposal.validation.reasons),
        "metrics": proposal.validation.metrics,
        "card": narration if proposal.ok else "Refused: " + narration,
        "narration": narration,
    }


__all__ = [*__all__, "plan"]
