"""Four ways a plan can come to the rover, all of them answering to the same gate.

The earlier repo had a NavigationPolicy with Nova, Mock and Replay flavours (report 07 section
2.3) and a CameraPolicy that watched the camera between steps (section 2.4). Here the idea is
re-expressed on this runtime and kept thin. A policy does two things: ``plan(request)`` turns
words into a validated plan, and ``advise(decision, index, steps)`` says what to do after the
gate has ruled on a hop: continue, re-plan the rest, or stop. ``MockPolicy`` scripts plans for
tests and rehearsals; ``ReplayPolicy`` replays the drive commands of a recorded run, one gated
hop at a time; ``VisionPolicy`` is the adaptive loop, and it fails closed: Proceed continues,
Guide re-plans the remaining hops at half speed, everything else, including no verdict at all,
stops the plan. ``ModelPolicy`` is the agent itself, which asks ``plan_deepracer`` and drives.
None of them can move the car; only a gated ``drive_deepracer`` can. Physics stops the car; the
decider explains; the policy only decides what to ask for next.
"""

from __future__ import annotations

import inspect
import json
import logging
import math
from collections.abc import Awaitable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from deepracer_agent.calibration import Calibration
from deepracer_agent.gate import Envelope
from deepracer_agent.plans import (
    Advice,
    Pen,
    Plan,
    Proposal,
    Step,
    ValidationResult,
    default_advice,
    last_proposal,
    validate_plan,
)

logger = logging.getLogger(__name__)

#: Report 07: the earlier executor allowed three re-plans per run. Kept.
MAX_REPLANS = 3
#: The fail-closed table of :class:`VisionPolicy`, action -> advice. Tests cover every row.
VISION_TABLE: dict[str | None, str] = {
    "Proceed": "continue",
    "Guide": "replan",
    "Confirm": "stop",
    "Deny": "stop",
    None: "stop",
}


@runtime_checkable
class NavigationPolicy(Protocol):
    """What a policy is: a name, a way to plan, and a way to advise after a verdict."""

    name: str

    def plan(self, request: str) -> Proposal | Awaitable[Proposal]: ...

    def advise(self, decision: Any, index: int, steps: Sequence[Step]) -> Advice: ...


async def resolve_plan(policy: NavigationPolicy, request: str) -> Proposal:
    """``policy.plan`` whether it is sync or async."""
    result = policy.plan(request)
    if inspect.isawaitable(result):
        result = await result
    return result


def _refused(shape: str, reason: str, source: str) -> Proposal:
    return Proposal(shape, 0.0, None, ValidationResult.refused("geometry", reason), source=source)


# -- mock ---------------------------------------------------------------------------------------------


class MockPolicy:
    """Scripted plans: one plan for every request, or a mapping of keyword to plan.

    With no script it falls back to the shape library, so a test can type "square of 60 cm" and get
    the real plan without a model. The validator runs on every plan it hands out.
    """

    name = "mock"

    def __init__(
        self,
        plans: Mapping[str, Plan | Proposal] | Plan | Proposal | None = None,
        *,
        calibration: Calibration | None = None,
        pen: Pen | None = None,
        envelope: Envelope | None = None,
    ) -> None:
        self.plans = plans
        self.calibration = calibration
        self.pen = pen
        self.envelope = envelope
        self.requests: list[str] = []

    def _wrap(self, item: Plan | Proposal) -> Proposal:
        if isinstance(item, Proposal):
            return item
        return Proposal(
            item.shape,
            item.size_m,
            item,
            validate_plan(item, self.calibration, self.pen, self.envelope),
            self.name,
        )

    def plan(self, request: str) -> Proposal:
        self.requests.append(request)
        if isinstance(self.plans, Plan | Proposal):
            return self._wrap(self.plans)
        if isinstance(self.plans, Mapping):
            low = request.lower()
            for key, item in self.plans.items():
                if key.lower() in low:
                    return self._wrap(item)
            return _refused("unknown", f"no scripted plan matches {request!r}", self.name)
        from deepracer_agent.shapes import parse_shape_request, propose

        parsed = parse_shape_request(request)
        if parsed is None:
            return _refused("unknown", f"no shape named in {request!r}", self.name)
        shape, size = parsed
        proposal = propose(shape, size, calibration=self.calibration, pen=self.pen, envelope=self.envelope)
        proposal.source = self.name
        return proposal

    def advise(self, decision: Any, index: int, steps: Sequence[Step]) -> Advice:
        return default_advice(decision, index, steps)


# -- replay -------------------------------------------------------------------------------------------


class ReplayPolicy:
    """Replay the ``drive_deepracer`` commands of a recorded ``events.jsonl`` through the gate.

    Each recorded command becomes one step; a command without a duration is the default hop. The
    whole sequence is validated like any plan (a recording that broke a cap is refused, not
    replayed), and when it runs every hop is gated again on today's frame: a replay is a proposal,
    never a privilege.
    """

    name = "replay"

    def __init__(
        self,
        path: str | Path,
        *,
        beat: str | None = None,
        max_steps: int | None = None,
        calibration: Calibration | None = None,
        pen: Pen | None = None,
        envelope: Envelope | None = None,
    ) -> None:
        self.path = Path(path)
        self.beat = beat
        self.max_steps = max_steps
        self.calibration = calibration or Calibration()
        self.pen = pen
        self.envelope = envelope

    def commands(self) -> list[dict[str, Any]]:
        """The recorded ``command`` events for ``drive_deepracer`` (optionally one beat), in order."""
        out: list[dict[str, Any]] = []
        if not self.path.exists():
            return out
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "command":
                continue
            payload = event.get("payload") or {}
            if payload.get("tool") != "drive_deepracer":
                continue
            if self.beat is not None and event.get("beat") != self.beat:
                continue
            out.append(event)
        return out

    def steps(self) -> list[Step]:
        steps: list[Step] = []
        for i, event in enumerate(self.commands(), start=1):
            args = (event.get("payload") or {}).get("args") or {}
            duration = args.get("duration")
            steps.append(
                Step(
                    _num(args.get("linear")),
                    _num(args.get("angular")),
                    self.calibration.hop_s if duration is None else _num(duration),
                    f"replay {i} (seq {event.get('seq')})",
                )
            )
            if self.max_steps is not None and len(steps) >= self.max_steps:
                break
        return steps

    def plan(self, request: str = "") -> Proposal:
        steps = self.steps()
        if not steps:
            return _refused("replay", f"no drive_deepracer commands recorded in {self.path}", self.name)
        plan = Plan(
            "replay",
            0.0,
            tuple(steps),
            None,
            None,
            f"replay of {len(steps)} recorded hops from {self.path.name}",
        )
        return Proposal(
            "replay", 0.0, plan, validate_plan(plan, self.calibration, self.pen, self.envelope), self.name
        )

    def advise(self, decision: Any, index: int, steps: Sequence[Step]) -> Advice:
        return default_advice(decision, index, steps)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


# -- vision -------------------------------------------------------------------------------------------


class VisionPolicy:
    """Phase-3 adaptive navigation on this runtime: look at every hop, then continue, re-plan or stop.

    The looking is the gate's (``DeciderGate.decide`` takes a fresh frame before every hop); this
    policy only answers the gate's verdict. Guide ("obstacle near, halve linear") re-plans the
    remaining hops at half speed with the same geometry, at most ``max_replans`` times, and the new
    hops are gated again. Anything that is not Proceed or Guide stops: Deny, Confirm (an operator is
    not in a plan's loop), an exception, or no verdict at all. The earlier repo's ``safe_continue``
    on timeout is the one behaviour deliberately reversed here (report 07 section 2.4).
    """

    name = "vision"

    def __init__(
        self,
        base: NavigationPolicy | None = None,
        *,
        max_replans: int = MAX_REPLANS,
        calibration: Calibration | None = None,
        pen: Pen | None = None,
        envelope: Envelope | None = None,
    ) -> None:
        self.base = base
        self.max_replans = int(max_replans)
        self.calibration = calibration or Calibration()
        self.pen = pen
        self.envelope = envelope
        self.replans = 0
        self.history: list[dict[str, Any]] = []

    def plan(self, request: str) -> Proposal | Awaitable[Proposal]:
        if self.base is None:
            return _refused("unknown", "VisionPolicy has no base policy to plan with", self.name)
        return self.base.plan(request)

    def advise(self, decision: Any, index: int, steps: Sequence[Step]) -> Advice:
        try:
            action = getattr(decision, "action", None)
            reason = str(getattr(decision, "reason", "") or "")
            if action not in VISION_TABLE:
                action = None
            verdict = VISION_TABLE[action]
            if verdict == "continue":
                advice = Advice("continue", reason)
            elif verdict == "replan":
                advice = self._replan(decision, index, steps, reason)
            else:
                why = f"{action}: {reason}" if action else "no verdict from the gate; failing closed"
                advice = Advice("stop", why)
        except Exception as exc:  # any surprise is a stop, never a continue
            advice = Advice("stop", f"policy error, failing closed: {type(exc).__name__}: {exc}")
        self.history.append({"index": index, "action": advice.action, "reason": advice.reason})
        return advice

    def _replan(self, decision: Any, index: int, steps: Sequence[Step], reason: str) -> Advice:
        if self.replans >= self.max_replans:
            return Advice("stop", f"Guide again after {self.replans} re-plans; stopping: {reason}")
        cap = self.calibration.max_duration_s
        new_steps: list[Step] = list(steps[:index])
        for step in steps[index:]:
            # Half the speed, same radius (angular halves too), so the geometry survives; a hop that
            # would now outlast the cap is split in two.
            total = step.duration * 2
            parts = max(1, math.ceil(total / cap - 1e-9))
            d = round(total / parts, 3)
            for k in range(parts):
                suffix = f" slow {k + 1}/{parts}" if parts > 1 else " slow"
                new_steps.append(
                    Step(round(step.linear / 2, 4), round(step.angular / 2, 4), d, step.label + suffix)
                )
        candidate = Plan("replan", 0.0, tuple(new_steps), None, None, "re-plan at half speed")
        validation = validate_plan(candidate, self.calibration, self.pen, self.envelope)
        if not validation.ok:
            return Advice("stop", f"re-plan refused: {'; '.join(validation.reasons)}")
        self.replans += 1
        return Advice(
            "replan", f"obstacle near, re-planning the remaining hops at half speed ({reason})", new_steps
        )


# -- model --------------------------------------------------------------------------------------------


class ModelPolicy:
    """The agent itself: ask it to call ``plan_deepracer`` and read back what the tool recorded.

    ``plan`` submits a plan-only instruction to the runtime, waits for the turn, and returns the
    tool's last proposal (``plans.last_proposal``), so the plan the rover narrated is exactly the
    plan that is validated and driven. Driving is left to the agent too: its ``drive_deepracer``
    calls run through the decider gate like anyone else's.
    """

    name = "model"

    def __init__(self, runtime: Any, *, beat: str | None = None, timeout_s: float = 60.0) -> None:
        self.runtime = runtime
        self.beat = beat
        self.timeout_s = float(timeout_s)
        self.last_text: str | None = None

    async def plan(self, request: str) -> Proposal:
        from deepracer_agent.plans import _state  # the tool's last proposal, reset for this turn

        _state.last = None
        text = (
            f"Plan only, do not drive: {request}. Call plan_deepracer with the shape and size, then read its "
            "narration back in one sentence."
        )
        request_id = self.runtime.submit(text, beat=self.beat)
        if inspect.isawaitable(request_id):
            request_id = await request_id
        wait = getattr(self.runtime, "wait", None)
        if callable(wait):
            try:
                self.last_text = await wait(request_id, timeout=self.timeout_s)
            except Exception as exc:
                logger.warning("model plan turn ended with %s: %s", type(exc).__name__, exc)
        proposal = last_proposal()
        if proposal is None:
            return _refused("unknown", "the model did not call plan_deepracer", self.name)
        proposal.source = self.name
        return proposal

    def advise(self, decision: Any, index: int, steps: Sequence[Step]) -> Advice:
        return default_advice(decision, index, steps)


__all__ = [
    "MAX_REPLANS",
    "VISION_TABLE",
    "MockPolicy",
    "ModelPolicy",
    "NavigationPolicy",
    "ReplayPolicy",
    "VisionPolicy",
    "resolve_plan",
]
