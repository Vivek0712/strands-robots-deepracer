"""Vision recipe: before a motion tool runs, Strands Decider 2B reads the camera frame and says what is ahead.

The guardrails recipe next door checks the words; this one checks the world. Before Strands
executes a motion tool, the handler grabs the latest camera frame and sends it to a local
Strands Decider 2B served with ``--vision``, with two typed questions in one request: a yes/no
"is a person visible in the frame?" and a five-way choice over clear, obstacle near, person in
frame, off the surface and unclear. The two answers are merged toward the safer one: when the
yes/no says person at 0.5 or above the class is ``person_in_frame`` whatever the five-way said
(the DeepRacer calibration of 2026-10-14 found the five-way softer on people than the yes/no).
Code then maps the result to a Strands action: a person or the edge of the surface is a
``Deny``, a strong ``unclear`` is a ``Deny``, an obstacle is a ``Guide`` to halve the speed and
re-plan, and no frame, no decider, a late decider or an answer that is not a probability over a
known class is a ``Deny``: a blind robot does not move. The model classifies; the code decides.

Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb). The decider explains.
This handler is the explanation layer, never the safety layer.

Decision table (rows are checked in this order; the first matching row is the action. The row
numbers are those of the shared table in README.md, whose text rows the guardrails recipe fills):

    1  decider unreachable, timeout (> 1.5 s), malformed answer, unknown class -> Deny("vision unavailable")
    2  no frame                                                              -> Deny("vision unavailable")
    3  person yes/no p >= 0.5, or five-way class person_in_frame             -> Deny("person in frame")
    4  five-way class off_surface                                            -> Deny("off the surface")
    5  five-way class unclear with p >= 0.65                                 -> Deny("cannot see clearly")
    11 five-way class obstacle_near                                          -> Guide(halve speed, re-plan)
    13 otherwise (clear, or a weak unclear)                                  -> Proceed

Run it offline (``make fake-decider`` in another shell) over the drawn frames in
``harness/frames/``; no real person appears in any of them::

    python patterns/strands/frame_intervention.py

Against a real decider the same code reads the pixels::

    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8111

The production version with the event log, cooldowns and calibration is
``src/deepracer_agent/gate.py``; the class names and descriptions here are copied from it.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

try:
    from ._client import NAME, Decider, ServerUnavailable
except ImportError:  # run as a script: python patterns/strands/frame_intervention.py
    from _client import NAME, Decider, ServerUnavailable

# --------------------------------------------------------------------------- the questions

#: The five classes, named and described exactly as src/deepracer_agent/gate.py spells them.
FRAME_CLASS_DESCRIPTIONS: dict[str, str] = {
    "clear": "the pen floor ahead is empty and the car can move",
    "obstacle_near": "an object is close in front of the bumper",
    "person_in_frame": "a person, or part of one (foot, leg, hand), is in the camera view",
    "off_surface": "the car is at or past the edge of the pen surface",
    "unclear": "the image is dark, blurred, blocked or otherwise unreadable",
}
FRAME_CLASSES: tuple[str, ...] = tuple(FRAME_CLASS_DESCRIPTIONS)

FRAME_QUESTIONS: dict[str, dict[str, Any]] = {
    "person": Decider.noul(
        "Is a person visible in the frame?",
        {
            "true": "a person, or any part of a human body, is in the camera view",
            "false": "no part of a person is in the camera view",
        },
    ),
    "frame": Decider.choice(
        "What is directly in front of the car in this camera frame?", FRAME_CLASS_DESCRIPTIONS
    ),
}
#: The upstream example calls its question set ``QUESTIONS``; same dict, second name.
QUESTIONS = FRAME_QUESTIONS

#: A person yes/no at or above this is a person, whatever the five-way said.
PERSON_THRESHOLD = 0.5
#: "unclear" needs more conviction than the other classes: plain floors read weakly unclear
#: (0.5-0.6), a covered lens about 0.75 on the drawn frame (docs/results/decider-calibration-2026-10-14.md).
UNCLEAR_THRESHOLD = 0.65
#: The budget for one decider round trip, in seconds; past it the gate denies.
MOTION_BUDGET_S = 1.5

VISION_UNAVAILABLE = "vision unavailable"
PERSON_IN_FRAME = "person in frame"
OFF_SURFACE = "off the surface"
CANNOT_SEE = "cannot see clearly"
OBSTACLE_NEAR = "something is close ahead: halve the speed and re-plan the hop"

FrameSource = Callable[[], bytes | None]


def probability(value: Any) -> float:
    """``value`` as a probability, or ``ValueError``: a real number in [0, 1], never a bool or a string.

    ``json.loads`` accepts the ``NaN`` literal, and ``NaN`` passes every ``<`` test, so a gate
    that only compares would fall through to Proceed on a garbled answer.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"not a probability: {value!r}")
    p = float(value)
    if math.isnan(p) or not 0.0 <= p <= 1.0:
        raise ValueError(f"probability outside [0, 1]: {value!r}")
    return p


# --------------------------------------------------------------------------- the gate


class FrameGate(InterventionHandler):
    """Ask the decider what the camera sees before a motion tool runs.

    Args:
        decider: A :class:`Decider` against a server started with ``--vision``.
        frame_source: Returns the latest JPEG bytes, or ``None`` when there is no frame.
        tools: Tool names to gate; ``None`` gates every tool call.
        person: Threshold for the person yes/no.
        unclear: Threshold at or above which ``unclear`` denies the move.
        timeout: Seconds the gate waits for the decider before denying; the blocking ``ask`` runs
            in a worker thread. Pass the same number to ``Decider(timeout=...)``.
        log: A list that receives one structured record per decision.
    """

    name = f"{NAME}-frame-gate"

    def __init__(
        self,
        decider: Decider,
        frame_source: FrameSource,
        *,
        tools: tuple[str, ...] | None = None,
        person: float = PERSON_THRESHOLD,
        unclear: float = UNCLEAR_THRESHOLD,
        timeout: float = MOTION_BUDGET_S,
        log: list[dict[str, Any]] | None = None,
    ) -> None:
        self._decider = decider
        self.frame_source = frame_source
        self.tools = tools
        self.person = float(person)
        self.unclear = float(unclear)
        self.timeout = float(timeout)
        self.log: list[dict[str, Any]] = log if log is not None else []

    @property
    def on_error(self) -> str:
        """A gate that throws must deny: fail closed."""
        return "deny"

    async def before_tool_call(self, event, **kwargs):
        tool_use = event.tool_use
        name = str(tool_use.get("name", ""))
        if self.tools is not None and name not in self.tools:
            return Proceed()
        raw = tool_use.get("input")
        arguments: dict[str, Any] = raw if isinstance(raw, dict) else {}
        record: dict[str, Any] = {"tool": name, "arguments": arguments}
        if raw is not None and not isinstance(raw, dict):
            record["input_type"] = type(raw).__name__
        try:
            frame = self.frame_source()
        except Exception as exc:  # a camera that throws is a camera that is gone
            record["error"] = str(exc)
            frame = None
        if not isinstance(frame, bytes | bytearray) or not frame:
            record.update(
                {"verdict": "Deny", "reason": VISION_UNAVAILABLE, "frame_bytes": 0, "latency_ms": 0.0}
            )
            if frame is not None and not isinstance(frame, bytes | bytearray):
                record["error"] = f"frame_source returned {type(frame).__name__}, not bytes"
            self.log.append(record)
            return Deny(reason=VISION_UNAVAILABLE)
        frame = bytes(frame)
        record["frame_bytes"] = len(frame)
        state = {
            "situation": (
                "The robot's forward camera frame is attached. The agent proposes a motion tool call."
            ),
            "proposed_call": {"tool": name, "arguments": arguments},
        }
        started = time.perf_counter()
        try:
            answers = await asyncio.wait_for(
                asyncio.to_thread(self._decider.ask, state, FRAME_QUESTIONS, [frame]), timeout=self.timeout
            )
            person_p = probability(answers["person"]["noul"])
            cls = str(answers["frame"]["choice"])
            if cls not in FRAME_CLASSES:
                raise ValueError(f"class {cls!r} is not one of {FRAME_CLASSES}")
            # The chosen class's own probability, never the normalised confidence; missing is malformed.
            p = probability((answers["frame"].get("probabilities") or {})[cls])
        except (ServerUnavailable, TimeoutError, KeyError, TypeError, ValueError) as exc:
            record.update(
                {
                    "verdict": "Deny",
                    "reason": VISION_UNAVAILABLE,
                    "error": str(exc) or type(exc).__name__,
                    "latency_ms": _elapsed_ms(started),
                }
            )
            self.log.append(record)
            return Deny(reason=VISION_UNAVAILABLE)
        latency_ms = _elapsed_ms(started)
        action = self.decide(person_p, cls, p)
        record.update(
            {
                "person": round(person_p, 3),
                "class": cls,
                "probability": round(p, 3),
                "verdict": type(action).__name__,
                "reason": str(getattr(action, "reason", None) or getattr(action, "feedback", "")),
                "latency_ms": latency_ms,
            }
        )
        self.log.append(record)
        return action

    def decide(self, person_p: float, cls: str, p: float) -> Proceed | Guide | Confirm | Deny:
        """The decision table over the two answers. Pure; tested row by row."""
        if person_p >= self.person or cls == "person_in_frame":
            return Deny(reason=PERSON_IN_FRAME)
        if cls == "off_surface":
            return Deny(reason=OFF_SURFACE)
        if cls == "unclear" and p >= self.unclear:
            return Deny(reason=f"{CANNOT_SEE} (p={p:.2f})")
        if cls == "obstacle_near":
            return Guide(feedback=OBSTACLE_NEAR, reason=f"obstacle_near (p={p:.2f})")
        return Proceed(reason=f"{cls} (p={p:.2f})")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


# --------------------------------------------------------------------------- offline demo


def fake_event(arguments: dict[str, Any] | None = None, tool_name: str = "move") -> SimpleNamespace:
    """A hand-built stand-in for ``BeforeToolCallEvent``: enough for ``before_tool_call``."""
    return SimpleNamespace(
        tool_use={"toolUseId": "offline-1", "name": tool_name, "input": arguments or {"distance_m": 0.2}},
        agent=SimpleNamespace(
            messages=[{"role": "user", "content": [{"text": "Move forward 20 centimetres."}]}]
        ),
    )


def judge(gate: FrameGate, event: Any) -> Any:
    """Run the async handler to completion from plain code (the demo and notebooks)."""
    return asyncio.run(gate.before_tool_call(event))


def _point_fake_camera(url: str, label: str) -> None:
    """The fake decider (harness/fake_decider.py) answers from the fake camera's label, not from
    pixels; a real ``--vision`` server reads the JPEG. This flips the label so each drawn frame
    gets the answer the real model gave on the equivalent real frame."""
    query = urllib.parse.urlencode({"label": label})
    with urllib.request.urlopen(f"{url}/control?{query}", timeout=5) as response:
        response.read()


#: Drawn frames from harness/frames.py and the label the fake decider answers them with.
DEMO_LABELS = ("clear", "obstacle_near", "person_in_frame", "off_surface", "hand_over_lens")


def main() -> int:
    from harness import frames  # drawn 480x360 JPEGs; no real person appears in any of them

    decider = Decider(timeout=MOTION_BUDGET_S)
    try:
        health = decider.health()
        print(decider.banner(), "\n")
    except ServerUnavailable as exc:
        print(exc)
        return 1
    is_fake = health.get("model") == "fake-decider"
    gate = FrameGate(decider, lambda: None)
    for label in DEMO_LABELS:
        jpeg = frames.load(label)
        if is_fake:
            _point_fake_camera(decider.url, label)
        gate.frame_source = lambda jpeg=jpeg: jpeg
        print(f"[frame] {label}.jpg ({len(jpeg)} bytes)")
        judge(gate, fake_event())
    print("[frame] no frame at all")
    gate.frame_source = lambda: None
    judge(gate, fake_event())
    print("[frame] decider down: nothing listens on port 9")
    down = Decider(url="http://127.0.0.1:9", timeout=MOTION_BUDGET_S)
    judge(FrameGate(down, lambda: frames.load("clear"), log=gate.log), fake_event())
    if is_fake:
        _point_fake_camera(decider.url, "clear")
    for row in gate.log:
        print(json.dumps(row, default=str))
    print(f"{decider}; last round trip {decider.latency_ms} ms; the dead port took {down.latency_ms} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
