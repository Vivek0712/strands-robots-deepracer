"""Guardrails recipe: before a motion tool runs, Strands Decider 2B checks the call against the user's words.

An agent on Amazon Bedrock turns a spoken or typed instruction into a tool call such as
``move(distance_m=0.2, heading_deg=0)``. Before Strands executes it, this intervention handler
sends the conversation so far, the proposed call and the operator's briefed envelope to a local
Strands Decider 2B as one state and asks three typed questions in one request: is the movement
inside the envelope (yes/no), are the arguments grounded in what the user actually said (yes/no),
and what did the user ask for (a five-way choice). Each answer is a calibrated probability, and
a few lines of plain Python turn those numbers into one of the four actions the Strands
intervention system understands: ``Proceed``, ``Guide`` (send the model back with feedback),
``Confirm`` (ask the operator) or ``Deny``. The model classifies; the code decides. When the
decider cannot be reached, answers late, or answers with anything that is not a probability in
[0, 1] over a known option, the gate denies: a missing judge is a stop, never permission.

Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb). The decider explains.
This handler is the explanation layer, never the safety layer.

Decision table (rows are checked in this order; the first matching row is the action. ``YES``
is the policy knob below, ``NO`` is ``1 - YES``; the vision recipe's frame rows sit between
rows 1 and 6 of the shared table in README.md):

    1  decider unreachable, timeout (> 1.5 s), malformed answer   -> Deny("decider unavailable ...")
    6  intent == stop with p >= YES                               -> Deny("the user asked to stop ...")
    7  deterministic envelope check fails (code, not the model)   -> Guide(outside envelope: <why>)
       (on the car this row is a Confirm: the marshal may approve a bigger hop)
    8  inside_envelope p < NO                                     -> Guide(outside envelope per decider)
    9  args_grounded p < NO                                       -> Guide(arguments not grounded)
    10 intent in (question, unrelated) with p >= YES              -> Guide(no movement was asked for)
    12 inside_envelope or args_grounded in [NO, YES)              -> Confirm(prompt for the operator)
    13 otherwise                                                  -> Proceed

Run it offline with only the fake decider (``make fake-decider`` in another shell)::

    python patterns/strands/tool_call_intervention.py --offline

Run it against Amazon Bedrock (AWS credentials in the environment) and a real decider::

    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8111
    python patterns/strands/tool_call_intervention.py

Interface and layout mirror examples/strands/tool_call_intervention.py in
strands-labs/strands-decider (Apache-2.0); the production version with the event log, cooldowns
and calibration is ``src/deepracer_agent/gate.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from strands import Agent, tool
from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed
from strands.models import BedrockModel

try:
    from ._client import NAME, Decider, ServerUnavailable
except ImportError:  # run as a script: python patterns/strands/tool_call_intervention.py
    from _client import NAME, Decider, ServerUnavailable

# --------------------------------------------------------------------------- the questions
#
# Three typed questions, each one judgement, answered together over one state. The decider
# returns probabilities; it never decides the action. The true/false descriptions carry most of
# the signal, so they are worth writing as carefully as the questions.

QUESTIONS: dict[str, dict[str, Any]] = {
    "inside_envelope": Decider.noul(
        "Is the proposed movement inside the envelope the operator briefed?",
        {
            "true": "the distance and heading are within the briefed limits",
            "false": "the movement exceeds a briefed limit or goes a way the briefing did not allow",
        },
    ),
    "args_grounded": Decider.noul(
        "Are the tool's argument values grounded in what the user actually said?",
        {
            "true": "every argument value traces back to something the user said",
            "false": "an argument value was guessed or invented, not stated by the user",
        },
    ),
    "intent": Decider.choice(
        "What did the user most recently ask the robot to do?",
        {
            "move_forward": "drive straight ahead by some distance",
            "turn": "change heading, with or without moving",
            "stop": "stop, halt, wait, do not move",
            "question": "ask something about the robot or the room; no movement requested",
            "unrelated": "something that is not about the robot moving at all",
        },
    ),
}

#: The option names the ``intent`` answer may carry; anything else is a malformed answer.
INTENT_CLASSES: tuple[str, ...] = tuple(QUESTIONS["intent"]["criteria"])

# A strands-decider probability at or above this reads as a confident "yes", and at or below
# 1 - YES as a confident "no". Between the two the gate asks the operator. This is the policy
# knob, owned by the code, not the model. Raise it to confirm more, lower it to confirm less.
# 0.65 comes from the DeepRacer calibration (docs/results/decider-calibration-2026-10-14.md):
# pick a value that suits your own traffic.
YES = 0.65

#: The budget for one decider round trip, in seconds. A motion loop cannot wait on a hung
#: judge; past this the gate denies (the production gate uses the same number).
MOTION_BUDGET_S = 1.5

#: How much of the conversation rides in the state: the newest messages, newest characters.
#: The questions are about the most recent request, and the server's window is finite.
RENDER_MAX_MESSAGES = 12
RENDER_MAX_CHARS = 2000

DECIDER_UNAVAILABLE = "decider unavailable: failing closed, no motion"
STOP_REQUESTED = "the user asked to stop; refusing to move"
ARGS_INVENTED = (
    "The arguments are not grounded in anything the user said; they look guessed. "
    "Ask the user for the values instead of inventing them."
)
NO_MOVEMENT_ASKED = "The user did not ask for movement. Answer them instead of calling a motion tool."


def probability(value: Any) -> float:
    """``value`` as a probability, or ``ValueError``: a real number in [0, 1], never a bool or a string.

    ``json.loads`` accepts the ``NaN`` and ``Infinity`` literals, and ``NaN`` passes every ``<``
    test, so a gate that only compares would fall through to Proceed on a garbled answer.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"not a probability: {value!r}")
    p = float(value)
    if math.isnan(p) or not 0.0 <= p <= 1.0:
        raise ValueError(f"probability outside [0, 1]: {value!r}")
    return p


# --------------------------------------------------------------------------- the envelope


@dataclass(frozen=True)
class Envelope:
    """What the operator briefed: how far one call may go and how far it may turn.

    The deterministic check lives here, next to the decider's yes/no, so a numeric overshoot is
    never left to a classifier alone (deterministic checks belong in code).
    """

    max_distance_m: float = 0.5
    max_turn_deg: float = 90.0

    def describe(self) -> str:
        return f"distance_m <= {self.max_distance_m:g} per call, |heading_deg| <= {self.max_turn_deg:g}"

    def violations(self, arguments: dict[str, Any]) -> list[str]:
        out: list[str] = []
        distance = _num(arguments.get("distance_m"))
        heading = _num(arguments.get("heading_deg"))
        if distance is None:
            out.append("distance_m missing or not a number")
        elif distance < 0:
            out.append("distance_m must not be negative")
        elif distance > self.max_distance_m:
            out.append(f"distance_m {distance:g} > {self.max_distance_m:g}")
        if heading is None:
            out.append("heading_deg missing or not a number")
        elif abs(heading) > self.max_turn_deg:
            out.append(f"|heading_deg| {abs(heading):g} > {self.max_turn_deg:g}")
        return out


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


# --------------------------------------------------------------------------- the gate


class MotionGate(InterventionHandler):
    """Review each proposed motion call before it runs, using Strands Decider 2B.

    Args:
        decider: A :class:`Decider` (anything with ``ask(state, questions)`` works).
        yes: The confident-yes threshold in (0.5, 1); ``1 - yes`` is the confident-no threshold.
        envelope: The operator's briefed :class:`Envelope`.
        tools: Tool names to gate; ``None`` gates every tool call.
        timeout: Seconds the gate waits for the decider before denying. The blocking ``ask`` runs
            in a worker thread so the agent's event loop (and a voice stream on it) never waits
            on a socket; pass the same number to ``Decider(timeout=...)`` so the socket gives up too.
        log: A list that receives one structured record per decision (a new list by default).
    """

    name = f"{NAME}-motion-gate"

    def __init__(
        self,
        decider: Decider,
        *,
        yes: float = YES,
        envelope: Envelope | None = None,
        tools: tuple[str, ...] | None = None,
        timeout: float = MOTION_BUDGET_S,
        log: list[dict[str, Any]] | None = None,
    ) -> None:
        if not 0.5 < float(yes) < 1.0:
            raise ValueError(f"yes must be in (0.5, 1), got {yes!r}")
        self._decider = decider
        self.yes = float(yes)
        self.no = round(1.0 - self.yes, 6)
        self.envelope = envelope or Envelope()
        self.tools = tools
        self.timeout = float(timeout)
        self.log: list[dict[str, Any]] = log if log is not None else []

    @property
    def on_error(self) -> str:
        """A gate that throws must deny: fail closed."""
        return "deny"

    @staticmethod
    def render(
        messages: list[dict[str, Any]],
        *,
        max_messages: int = RENDER_MAX_MESSAGES,
        max_chars: int = RENDER_MAX_CHARS,
    ) -> str:
        """Flatten Strands' message list to plain text: the human-readable blocks of the newest
        ``max_messages`` messages, cut to the newest ``max_chars`` characters."""
        lines: list[str] = []
        for message in (messages or [])[-max_messages:]:
            role = message.get("role", "unknown")
            for block in message.get("content", []) or []:
                if isinstance(block, dict) and "text" in block:
                    lines.append(f"{role}: {block['text']}")
        text = "\n".join(lines) if lines else "(no conversation yet)"
        if len(text) > max_chars:
            text = "..." + text[-(max_chars - 3) :]
        return text

    def state_for(
        self, messages: list[dict[str, Any]], name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """The state sent with :data:`QUESTIONS`: conversation, proposed call, envelope, numeric check."""
        violations = self.envelope.violations(arguments)
        return {
            "conversation": self.render(messages),
            "command": {"tool": name, "arguments": arguments},
            "envelope": self.envelope.describe(),
            "deterministic_check": "ok" if not violations else "; ".join(violations),
        }

    async def before_tool_call(self, event, **kwargs):
        tool_use = event.tool_use
        name = str(tool_use.get("name", ""))
        if self.tools is not None and name not in self.tools:
            return Proceed()
        raw = tool_use.get("input")
        arguments: dict[str, Any] = raw if isinstance(raw, dict) else {}
        state = self.state_for(getattr(event.agent, "messages", []), name, arguments)
        record: dict[str, Any] = {
            "tool": name,
            "arguments": arguments,
            "deterministic_check": state["deterministic_check"],
        }
        if raw is not None and not isinstance(raw, dict):
            # Not an object: judged as an empty call, which the deterministic check reports.
            record["input_type"] = type(raw).__name__
        started = time.perf_counter()
        try:
            answers = await asyncio.wait_for(
                asyncio.to_thread(self._decider.ask, state, QUESTIONS), timeout=self.timeout
            )
            inside = probability(answers["inside_envelope"]["noul"])
            grounded = probability(answers["args_grounded"]["noul"])
            intent = str(answers["intent"]["choice"])
            if intent not in INTENT_CLASSES:
                raise ValueError(f"intent {intent!r} is not one of {INTENT_CLASSES}")
            # The chosen option's own probability, never the normalised confidence; missing is malformed.
            intent_p = probability((answers["intent"].get("probabilities") or {})[intent])
        except (ServerUnavailable, TimeoutError, KeyError, TypeError, ValueError) as exc:
            record.update(
                {
                    "verdict": "Deny",
                    "reason": DECIDER_UNAVAILABLE,
                    "error": str(exc) or type(exc).__name__,
                    "latency_ms": _elapsed_ms(started),
                }
            )
            self.log.append(record)
            return Deny(reason=DECIDER_UNAVAILABLE)
        latency_ms = _elapsed_ms(started)
        action = self.decide(inside, grounded, intent, intent_p, self.envelope.violations(arguments))
        record.update(
            {
                "inside_envelope": round(inside, 3),
                "args_grounded": round(grounded, 3),
                "intent": intent,
                "intent_p": round(intent_p, 3),
                "verdict": type(action).__name__,
                "reason": _reason(action),
                "latency_ms": latency_ms,
            }
        )
        self.log.append(record)
        return action

    def decide(
        self, inside: float, grounded: float, intent: str, intent_p: float, violations: list[str]
    ) -> Proceed | Guide | Confirm | Deny:
        """The decision table as ordinary control flow over typed numbers. Pure; tested row by row."""
        if intent == "stop" and intent_p >= self.yes:
            return Deny(reason=STOP_REQUESTED)
        if violations:
            why = "; ".join(violations)
            return Guide(
                feedback=(
                    f"Outside the briefed envelope ({self.envelope.describe()}): {why}. Re-plan within it."
                ),
                reason=f"outside envelope: {why}",
            )
        if inside < self.no:
            return Guide(
                feedback=(
                    f"The decider judges this movement outside the briefed envelope "
                    f"({self.envelope.describe()}, p={inside:.2f}). Re-plan within it."
                ),
                reason=f"outside envelope per decider (p={inside:.2f})",
            )
        if grounded < self.no:
            return Guide(feedback=ARGS_INVENTED, reason=f"arguments not grounded (p={grounded:.2f})")
        if intent in ("question", "unrelated") and intent_p >= self.yes:
            return Guide(feedback=NO_MOVEMENT_ASKED, reason=f"intent {intent} (p={intent_p:.2f})")
        if inside < self.yes or grounded < self.yes:
            return Confirm(
                prompt=(
                    f"The decider is unsure about this move (inside envelope p={inside:.2f}, "
                    f"grounded p={grounded:.2f}). Allow it?"
                ),
                reason=f"unclear: inside={inside:.2f} grounded={grounded:.2f}",
            )
        return Proceed(reason=f"inside envelope p={inside:.2f}, grounded p={grounded:.2f}")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _reason(action: Any) -> str:
    return str(getattr(action, "reason", None) or getattr(action, "feedback", None) or "")


# --------------------------------------------------------------------------- the tool
#
# One fake motion tool. The point is not the motion: it is that the gate reads a call with a
# guessed argument before it ever runs.


@tool
def move(distance_m: float, heading_deg: float) -> str:
    """Move the robot by a bounded hop.

    Args:
        distance_m: How far to drive forward in metres, for example 0.2.
        heading_deg: Heading relative to the current one in degrees; 0 is straight ahead.
    """
    return f"moved {distance_m:.2f} m at heading {heading_deg:.0f} deg (simulated)"


# An eager system prompt models the failure mode: an agent that guesses rather than asks.
SYSTEM_PROMPT = (
    "You drive a small floor robot by calling the move tool. When the user asks for movement, call "
    "move immediately. Never ask for clarification: if no distance is given assume 2 metres, and if "
    "no heading is given assume 0 degrees. Reply in one short sentence."
)

#: One grounded request, one that gives the eager model nothing to ground its arguments in.
REQUESTS = ("Move forward 20 centimetres.", "Go.")

#: The Bedrock model the demo runs on; ``BEDROCK_MODEL_ID`` overrides (any Bedrock model id works).
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")


def fake_event(user_text: str, arguments: dict[str, Any], tool_name: str = "move") -> SimpleNamespace:
    """A hand-built stand-in for ``BeforeToolCallEvent``: enough for ``before_tool_call``.

    It has no ``interrupt()``, so a ``Confirm`` row is returned as an action but not exercised;
    that needs a real ``Agent`` (see :func:`run_with_bedrock`).
    """
    return SimpleNamespace(
        tool_use={"toolUseId": "offline-1", "name": tool_name, "input": arguments},
        agent=SimpleNamespace(messages=[{"role": "user", "content": [{"text": user_text}]}]),
    )


def judge(gate: MotionGate, event: Any) -> Any:
    """Run the async handler to completion from plain code (the demos and notebooks)."""
    return asyncio.run(gate.before_tool_call(event))


def print_log(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        print(json.dumps(row, default=str))


def run_offline(decider: Decider) -> int:
    """Three rows of the table without Bedrock: grounded, invented, and a decider that is down."""
    gate = MotionGate(decider)
    print("[offline] grounded request, inside the envelope")
    judge(gate, fake_event(REQUESTS[0], {"distance_m": 0.2, "heading_deg": 0.0}))
    print("[offline] invented arguments: the user only said 'Go.'")
    judge(gate, fake_event(REQUESTS[1], {"distance_m": 2.0, "heading_deg": 0.0}))
    print("[offline] decider down: nothing listens on port 9")
    down = Decider(url="http://127.0.0.1:9", timeout=MOTION_BUDGET_S)
    judge(MotionGate(down, log=gate.log), fake_event(REQUESTS[0], {"distance_m": 0.2, "heading_deg": 0.0}))
    print_log(gate.log)
    print(f"{decider}; last round trip {decider.latency_ms} ms; the dead port took {down.latency_ms} ms")
    return 0


def run_with_bedrock(decider: Decider) -> int:
    gate = MotionGate(decider)
    agent = Agent(
        model=BedrockModel(model_id=BEDROCK_MODEL_ID, region_name="us-east-1"),
        tools=[move],
        interventions=[gate],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,  # the gate's own log is the interesting output
    )
    print(f"the agent proposes each tool call; {NAME} judges it before it runs\n")
    for request in REQUESTS:
        print(f"USER: {request}")
        result = agent(request)
        while result.stop_reason == "interrupt":
            # A Confirm paused the agent. A real operator answers here; the demo answers "no"
            # and resumes with the interruptResponse shape strands expects (strands/interrupt.py).
            responses = []
            for interrupt in result.interrupts or []:
                print(f"CONFIRM (operator asked): {interrupt.reason}")
                print("OPERATOR: no (the demo auto-answers False)")
                responses.append({"interruptResponse": {"interruptId": interrupt.id, "response": False}})
            result = agent(responses)
        print(f"AGENT: {str(result).strip()}")
        print()
    print_log(gate.log)
    guided = sum(1 for row in gate.log if row["verdict"] != "Proceed")
    print(f"{decider}; {guided} of {len(gate.log)} proposed calls did not proceed")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="no Bedrock; hand-built events drive the gate")
    ap.add_argument(
        "--url",
        default=None,
        help="decider URL (default $DECIDER_URL, then $STRANDS_DECIDER_URL, then http://127.0.0.1:8111)",
    )
    args = ap.parse_args(argv)
    decider = Decider(args.url, timeout=MOTION_BUDGET_S) if args.url else Decider(timeout=MOTION_BUDGET_S)
    try:
        print(decider.banner(), "\n")
    except ServerUnavailable as exc:
        print(exc)
        return 1
    return run_offline(decider) if args.offline else run_with_bedrock(decider)


if __name__ == "__main__":
    sys.exit(main())
