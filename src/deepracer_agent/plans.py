"""Shape plans the rover narrates before it drives, and the validator that refuses the bad ones.

A plan is a short list of steps, and each step is a hop the rover could have asked for on its
own: a linear speed, a steering rate and a duration. Before anything moves, the validator
checks every step against the car's calibration (the speed cap, the two second hop cap, no
turning on the spot, no arc tighter than the front wheels can steer), adds the steps up
against the pen (total time, total distance, the footprint of the path) and, for a closed
shape, checks that the headings add up to a full turn. A plan that fails is refused with every
reason named. A plan that passes is still only a proposal: it is driven as one gated
``drive_deepracer`` call per step, with a decider verdict before each hop and the plan
abandoned at the first verdict that is not Proceed. There is no sleep-and-stop loop here and
a plan is never one long command. Physics stops the car; the decider explains; the plan is
what the rover says it intends to do.

Ported from the phase-1/phase-2 planner of the earlier repo (report 07 section 2.3): the
terminal stop, the per-step cap and the closed-loop rotation check survive; the 5 s step cap
became the 2 s hop cap, the rotation warning became a refusal, and the HTTP-path constants
were replaced by the bicycle model in ``calibration.py``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from strands import tool

from deepracer_agent.calibration import Calibration
from deepracer_agent.driver import REST_VELOCITY_EPS, rest_command_error
from deepracer_agent.gate import Envelope

logger = logging.getLogger(__name__)

#: Report 07's rotation tolerance (5 degrees) was a warning; here it is a refusal.
ROTATION_TOLERANCE_RAD = math.radians(5.0)
#: Points sampled along each step when the path footprint is computed.
FOOTPRINT_SAMPLES_PER_STEP = 24
#: Below this |angular| a step is a straight line.
STRAIGHT_EPS = 1e-6

Action = Literal["Proceed", "Guide", "Confirm", "Deny"]

# -- the pen ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pen:
    """The 2 m by 2 m booth pen and the totals one plan may spend inside it.

    ``margin_m`` keeps the path's bounding box away from the lip: half a car (the DeepRacer body is
    about 0.3 m long) plus the same again for the stop-latency budget report 11 names (10 to 20 cm
    of travel between a verdict and a still car).
    """

    width_m: float = 2.0
    depth_m: float = 2.0
    margin_m: float = 0.3
    max_total_time_s: float = 30.0
    max_total_distance_m: float = 6.0
    max_steps: int = 24

    @property
    def usable_m(self) -> tuple[float, float]:
        """Width and depth the path's footprint may occupy."""
        return (self.width_m - 2 * self.margin_m, self.depth_m - 2 * self.margin_m)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_m": self.width_m,
            "depth_m": self.depth_m,
            "margin_m": self.margin_m,
            "usable_m": list(self.usable_m),
            "max_total_time_s": self.max_total_time_s,
            "max_total_distance_m": self.max_total_distance_m,
            "max_steps": self.max_steps,
        }


# -- steps and plans ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One hop: ``drive_deepracer(linear, angular, duration)`` and a label for the screen."""

    linear: float
    angular: float
    duration: float
    label: str = ""

    def args(self) -> dict[str, float]:
        return {"linear": self.linear, "angular": self.angular, "duration": self.duration}

    @property
    def heading_change_rad(self) -> float:
        return self.angular * self.duration

    @property
    def distance_m(self) -> float:
        return abs(self.linear) * self.duration

    @property
    def radius_m(self) -> float | None:
        """Arc radius, or ``None`` for a straight step or a step at rest."""
        if abs(self.angular) < STRAIGHT_EPS or abs(self.linear) < REST_VELOCITY_EPS:
            return None
        return abs(self.linear / self.angular)

    def to_dict(self) -> dict[str, Any]:
        return {
            "linear": self.linear,
            "angular": self.angular,
            "duration": self.duration,
            "label": self.label,
        }

    def describe(self) -> str:
        if abs(self.angular) < STRAIGHT_EPS:
            way = "forward" if self.linear > 0 else "back"
            return f"{way} {self.distance_m:.2f} m ({self.linear:+.2f} m/s, {self.duration:.2f} s)"
        side = "left" if self.angular > 0 else "right"
        deg = abs(math.degrees(self.heading_change_rad))
        radius = self.radius_m
        arc = f" radius {radius:.2f} m" if radius is not None else ""
        return (
            f"arc {side} {deg:.0f} deg{arc} "
            f"({self.linear:+.2f} m/s, {self.angular:+.2f} rad/s, {self.duration:.2f} s)"
        )


@dataclass(frozen=True)
class Plan:
    """A named shape as a sequence of hops, with the heading the shape must close to.

    ``expected_turn_rad`` is the sum of the absolute heading changes a correct plan makes (a
    closed loop: 2 pi; a figure-8: 4 pi; a U-turn: pi; a straight: 0) and
    ``expected_net_heading_rad`` the signed sum. Either may be ``None`` for a free-form plan.
    ``terminal_stop`` is the phase-1 rule that every plan ends with a stop; the executor sends
    it from ``finally`` and the validator refuses a plan that opts out.
    """

    shape: str
    size_m: float
    steps: tuple[Step, ...]
    expected_turn_rad: float | None = None
    expected_net_heading_rad: float | None = None
    description: str = ""
    terminal_stop: bool = True

    @property
    def total_time_s(self) -> float:
        return sum(s.duration for s in self.steps)

    @property
    def total_distance_m(self) -> float:
        return sum(s.distance_m for s in self.steps)

    @property
    def turn_rad(self) -> float:
        return sum(abs(s.heading_change_rad) for s in self.steps)

    @property
    def net_heading_rad(self) -> float:
        return sum(s.heading_change_rad for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape": self.shape,
            "size_m": self.size_m,
            "steps": [s.to_dict() for s in self.steps],
            "expected_turn_deg": None
            if self.expected_turn_rad is None
            else round(math.degrees(self.expected_turn_rad), 1),
            "expected_net_heading_deg": None
            if self.expected_net_heading_rad is None
            else round(math.degrees(self.expected_net_heading_rad), 1),
            "description": self.description,
            "terminal_stop": self.terminal_stop,
        }


# -- geometry ----------------------------------------------------------------------------------------


def simulate_path(
    steps: Sequence[Step], samples_per_step: int = FOOTPRINT_SAMPLES_PER_STEP
) -> list[tuple[float, float, float]]:
    """Dead-reckon the bicycle model from the origin facing +x. Returns ``(x, y, heading)`` samples.

    Each step is integrated as an exact arc (or a straight line), sampled so the footprint of a
    curve is its real extent and not just its end points. Reverse steps steer the mirrored way,
    exactly as the driver sends them, so ``(v, w)`` has the same meaning in both directions.
    """
    x = y = heading = 0.0
    points = [(0.0, 0.0, 0.0)]
    n = max(1, int(samples_per_step))
    for step in steps:
        v, w = float(step.linear), float(step.angular)
        dt = float(step.duration) / n
        for _ in range(n):
            if abs(w) < STRAIGHT_EPS:
                x += v * math.cos(heading) * dt
                y += v * math.sin(heading) * dt
            else:
                radius = v / w
                new_heading = heading + w * dt
                x += radius * (math.sin(new_heading) - math.sin(heading))
                y -= radius * (math.cos(new_heading) - math.cos(heading))
                heading = new_heading
            points.append((x, y, heading))
    return points


def footprint(steps: Sequence[Step]) -> tuple[float, float]:
    """Bounding-box extent ``(along, across)`` of the path in metres, start pose at the origin."""
    pts = simulate_path(steps)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(xs) - min(xs), max(ys) - min(ys))


# -- validation --------------------------------------------------------------------------------------

#: Every refusal code the validator can return, with the rule in one line. Tests cover each row.
REFUSAL_CODES: dict[str, str] = {
    "empty": "a plan needs at least one step",
    "too_many_steps": "more steps than the pen limit",
    "not_a_number": "a step value is not a finite number",
    "linear_cap": "|linear| above the calibration speed cap",
    "duration_cap": "a step longer than the hop cap",
    "duration_nonpositive": "a step with zero or negative duration",
    "yaw_at_rest": "a turn with no linear speed (an Ackermann car cannot yaw at rest)",
    "zero_step": "a step that neither moves nor turns",
    "below_min_turn_radius": "an arc tighter than the front wheels can steer",
    "envelope": "a step outside the briefed envelope",
    "rotation_mismatch": "the headings do not add up to the shape's total turn",
    "net_heading_mismatch": "the signed headings do not close the shape",
    "total_time": "the plan takes longer than the pen allows",
    "total_distance": "the plan drives further than the pen allows",
    "footprint": "the path does not fit the usable pen",
    "no_terminal_stop": "every plan ends with a stop",
    "geometry": "the shape cannot be drawn at this size by this car",
}


@dataclass
class ValidationResult:
    """Why a plan may or may not be driven, with the numbers behind it."""

    ok: bool
    codes: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def refused(cls, code: str, reason: str, **metrics: Any) -> ValidationResult:
        return cls(False, (code,), (reason,), dict(metrics))

    def summary(self) -> str:
        if self.ok:
            m = self.metrics
            return (
                f"ok: {m.get('steps')} steps, {m.get('total_distance_m')} m, {m.get('total_time_s')} s, "
                f"footprint {m.get('footprint_m', ['?', '?'])[0]} x {m.get('footprint_m', ['?', '?'])[1]} m, "
                f"turn {m.get('turn_deg')} deg"
            )
        return "refused: " + "; ".join(self.reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "codes": list(self.codes),
            "reasons": list(self.reasons),
            "metrics": self.metrics,
        }


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def validate_plan(
    plan: Plan,
    calibration: Calibration | None = None,
    pen: Pen | None = None,
    envelope: Envelope | None = None,
) -> ValidationResult:
    """Every rule in :data:`REFUSAL_CODES`, all reasons collected, never raises.

    Order: shape of the plan, then each step against the car, then the totals against the pen,
    then the closed-loop check. A plan with any reason is refused; the metrics are filled in
    whenever the steps were numeric enough to add up.
    """
    cal = calibration or Calibration()
    pen = pen or Pen()
    env = envelope or Envelope(max_linear=cal.max_speed_mps, max_duration_s=cal.max_duration_s)
    codes: list[str] = []
    reasons: list[str] = []

    def refuse(code: str, reason: str) -> None:
        codes.append(code)
        reasons.append(reason)

    steps = tuple(plan.steps)
    if not steps:
        refuse("empty", REFUSAL_CODES["empty"])
        return ValidationResult(False, tuple(codes), tuple(reasons), {"steps": 0})
    if len(steps) > pen.max_steps:
        refuse("too_many_steps", f"{len(steps)} steps exceed the pen limit of {pen.max_steps}")
    if not plan.terminal_stop:
        refuse("no_terminal_stop", REFUSAL_CODES["no_terminal_stop"])

    numeric = True
    min_radius = cal.bicycle_min_turn_radius_m
    for i, step in enumerate(steps, start=1):
        if not (_finite(step.linear) and _finite(step.angular) and _finite(step.duration)):
            refuse("not_a_number", f"step {i}: linear, angular and duration must be finite numbers")
            numeric = False
            continue
        v, w, t = float(step.linear), float(step.angular), float(step.duration)
        if abs(v) > cal.max_speed_mps + 1e-9:
            refuse(
                "linear_cap", f"step {i}: |linear| {abs(v):g} m/s exceeds the cap {cal.max_speed_mps:g} m/s"
            )
        if t > cal.max_duration_s + 1e-9:
            refuse("duration_cap", f"step {i}: duration {t:g} s exceeds the hop cap {cal.max_duration_s:g} s")
        if t <= 0:
            refuse("duration_nonpositive", f"step {i}: duration {t:g} s must be positive")
        rest = rest_command_error(v, w)
        if abs(v) < REST_VELOCITY_EPS and abs(w) >= STRAIGHT_EPS:
            refuse("yaw_at_rest", f"step {i}: {rest or 'yaw at rest'}")
        elif abs(v) < REST_VELOCITY_EPS:
            refuse(
                "zero_step", f"step {i}: neither moves nor turns; the terminal stop is implicit, not a step"
            )
        radius = step.radius_m
        if radius is not None and radius < min_radius * (1 - 1e-6):
            refuse(
                "below_min_turn_radius",
                f"step {i}: arc radius {radius:.3f} m is tighter than the wheels can steer "
                f"({min_radius:.3f} m at full lock); the car would leave the planned path",
            )
        violations = env.violations(v, w, t)
        if violations:
            refuse("envelope", f"step {i}: outside the envelope: {'; '.join(violations)}")

    metrics: dict[str, Any] = {"steps": len(steps)}
    if numeric:
        total_time = plan.total_time_s
        total_distance = plan.total_distance_m
        along, across = footprint(steps)
        turn = plan.turn_rad
        net = plan.net_heading_rad
        metrics.update(
            {
                "total_time_s": round(total_time, 2),
                "total_distance_m": round(total_distance, 2),
                "footprint_m": [round(along, 2), round(across, 2)],
                "turn_deg": round(math.degrees(turn), 1),
                "net_heading_deg": round(math.degrees(net), 1),
                "usable_m": [round(x, 2) for x in pen.usable_m],
            }
        )
        if total_time > pen.max_total_time_s + 1e-9:
            refuse(
                "total_time",
                f"total time {total_time:.1f} s exceeds the pen limit {pen.max_total_time_s:g} s",
            )
        if total_distance > pen.max_total_distance_m + 1e-9:
            refuse(
                "total_distance",
                f"total distance {total_distance:.2f} m exceeds the pen limit {pen.max_total_distance_m:g} m",
            )
        usable = sorted(pen.usable_m)
        extent = sorted((along, across))
        if extent[0] > usable[0] + 1e-9 or extent[1] > usable[1] + 1e-9:
            refuse(
                "footprint",
                f"footprint {along:.2f} x {across:.2f} m does not fit the usable pen "
                f"{pen.usable_m[0]:.2f} x {pen.usable_m[1]:.2f} m ({pen.width_m:g} x {pen.depth_m:g} m "
                f"minus a {pen.margin_m:g} m margin)",
            )
        if plan.expected_turn_rad is not None and abs(turn - plan.expected_turn_rad) > ROTATION_TOLERANCE_RAD:
            refuse(
                "rotation_mismatch",
                f"headings add up to {math.degrees(turn):.0f} deg, the {plan.shape} needs "
                f"{math.degrees(plan.expected_turn_rad):.0f} deg "
                f"(tolerance {math.degrees(ROTATION_TOLERANCE_RAD):g})",
            )
        if (
            plan.expected_net_heading_rad is not None
            and abs(net - plan.expected_net_heading_rad) > ROTATION_TOLERANCE_RAD
        ):
            refuse(
                "net_heading_mismatch",
                f"net heading {math.degrees(net):.0f} deg, the {plan.shape} must close to "
                f"{math.degrees(plan.expected_net_heading_rad):.0f} deg",
            )
    return ValidationResult(not codes, tuple(codes), tuple(reasons), metrics)


# -- proposals ---------------------------------------------------------------------------------------


@dataclass
class Proposal:
    """A plan and its validation together: what the rover narrates, or why it declines."""

    shape: str
    size_m: float
    plan: Plan | None
    validation: ValidationResult
    source: str = "shapes"

    @property
    def ok(self) -> bool:
        return self.plan is not None and self.validation.ok

    def narration(self) -> str:
        """One or two spoken sentences a presenter can read aloud."""
        size = _fmt_size(self.size_m)
        if not self.ok:
            return f"I will not drive a {size} {self.shape}: {'; '.join(self.validation.reasons)}."
        assert self.plan is not None
        m = self.validation.metrics
        fp = m.get("footprint_m", [0, 0])
        desc = self.plan.description or f"a {size} {self.shape}"
        return (
            f"Plan: {desc}; {len(self.plan.steps)} gated hops, {m.get('total_distance_m')} m in "
            f"{m.get('total_time_s')} s, footprint {fp[0]} by {fp[1]} m. Each hop is one drive_deepracer "
            "call the gate checks first."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "shape": self.shape,
            "size_m": self.size_m,
            "plan": None if self.plan is None else self.plan.to_dict(),
            "validation": self.validation.to_dict(),
            "narration": self.narration(),
            "source": self.source,
        }


def _fmt_size(size_m: float) -> str:
    if size_m < 1.0:
        return f"{round(size_m * 100):d} cm"
    return f"{size_m:g} m"


# -- execution: one gated hop per step --------------------------------------------------------------


class GateLike(Protocol):
    async def decide(self, args: dict[str, Any], *, request_id: str = "") -> Any: ...


@dataclass
class Advice:
    """What a policy says after a verdict: keep going, re-plan the remaining steps, or stop."""

    action: Literal["continue", "replan", "stop"]
    reason: str = ""
    steps: list[Step] | None = None


def default_advice(decision: Any, index: int, steps: Sequence[Step]) -> Advice:
    """Without a policy the executor is strict: only Proceed continues."""
    action = getattr(decision, "action", None)
    reason = str(getattr(decision, "reason", "") or "")
    if action == "Proceed":
        return Advice("continue", reason)
    return Advice("stop", f"{action}: {reason}" if action else "no verdict")


@dataclass
class PlanRun:
    """The record of one executed plan: how far it got and why it stopped, if it did."""

    plan: Plan
    completed: int = 0
    aborted_at: int | None = None
    reason: str | None = None
    replans: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)
    validation: ValidationResult | None = None
    total: int | None = None  # hops in the effective plan after any re-plan

    @property
    def done(self) -> bool:
        total = len(self.plan.steps) if self.total is None else self.total
        return self.aborted_at is None and self.completed == total

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape": self.plan.shape,
            "size_m": self.plan.size_m,
            "steps": len(self.plan.steps),
            "completed": self.completed,
            "total": len(self.plan.steps) if self.total is None else self.total,
            "aborted_at": self.aborted_at,
            "reason": self.reason,
            "replans": self.replans,
            "done": self.done,
            "validation": None if self.validation is None else self.validation.to_dict(),
        }


def _result_text(result: Any) -> str:
    if isinstance(result, dict):
        parts = [str(c.get("text", "")) for c in result.get("content", []) if isinstance(c, dict)]
        return " ".join(p for p in parts if p) or str(result)
    return str(result)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _stop(driver: Any, cause: str) -> Any:
    stop = getattr(driver, "stop", None)
    if not callable(stop):
        return None
    try:
        return await _call(stop, None, cause=cause)
    except TypeError:
        return await _call(stop)


async def execute_plan(
    target: Any,
    plan: Plan,
    event_log: Any,
    *,
    gate: GateLike | None = None,
    policy: Any = None,
    calibration: Calibration | None = None,
    pen: Pen | None = None,
    envelope: Envelope | None = None,
    beat: str | None = None,
    request_prefix: str = "plan",
    on_step: Callable[[int, int, Step], Any] | None = None,
) -> PlanRun:
    """Drive ``plan`` as a sequence of gated hops; abandon it at the first verdict that is not Proceed.

    Args:
        target: An ``AgentRuntime`` (its ``driver`` is used), a ``DeepRacerRobot`` or any
            :class:`deepracer_agent.platforms.MobilePlatform` with ``drive``/``stop``.
        plan: The plan; it is validated here again, whatever produced it.
        event_log: CONTRACTS section 4 sink; ``thought``, ``command``, ``stop`` and ``error`` go here
            (the gate writes its own ``verdict`` rows, the driver its ``motion`` rows).
        gate: A ``DeciderGate`` or anything with ``async decide(args, request_id=)``. When ``None``
            the hop is still subject to the strands-robots command gate inside the transport, but no
            decider verdict is taken; beats and kiosks always pass the gate.
        policy: Something with ``advise(decision, index, steps) -> Advice`` (see ``policies.py``).
            Without one, only Proceed continues.
        on_step: Optional callback ``(index, total, step)`` before each hop, for a screen.

    Every path out of this function ends with a zero pair: the driver's own trailing zero after
    each hop and a final ``stop`` from ``finally``. The function never raises; a failure is an
    ``error`` event and an aborted run.
    """
    driver = getattr(target, "driver", target)
    run = PlanRun(plan)
    run.validation = validate_plan(plan, calibration, pen, envelope)

    def emit(type: str, payload: dict[str, Any]) -> None:
        try:
            event_log.emit(type, payload, source="plan", beat=beat)
        except TypeError:
            event_log.emit(type, payload)

    size = _fmt_size(plan.size_m)
    if not run.validation.ok:
        run.aborted_at = 0
        run.reason = run.validation.summary()
        emit("thought", {"text": f"plan {plan.shape} {size} {run.reason}"})
        return run

    steps = list(plan.steps)
    emit(
        "thought",
        {"text": f"plan {plan.shape} {size}: {len(steps)} gated hops; {run.validation.summary()}"},
    )
    advise = getattr(policy, "advise", None) if policy is not None else None
    stop_cause = "trailing_zero"
    i = 0
    try:
        while i < len(steps):
            step = steps[i]
            request_id = f"{request_prefix}-{uuid.uuid4().hex[:6]}-{i + 1}"
            if on_step is not None:
                try:
                    await _maybe_await(on_step(i, len(steps), step))
                except Exception as exc:  # a screen callback never stops the plan
                    logger.debug("on_step failed: %s", exc)
            emit("thought", {"text": f"plan step {i + 1}/{len(steps)} {step.label}: {step.describe()}"})
            emit(
                "command",
                {
                    "tool": "drive_deepracer",
                    "args": step.args(),
                    "request_id": request_id,
                    "plan_step": i + 1,
                },
            )
            if gate is not None:
                decision = await gate.decide(step.args(), request_id=request_id)
                to_dict = getattr(decision, "to_dict", None)
                run.decisions.append(to_dict() if callable(to_dict) else {"action": str(decision)})
                advice = (
                    advise(decision, i, steps) if callable(advise) else default_advice(decision, i, steps)
                )
                if advice.action == "replan" and advice.steps:
                    run.replans += 1
                    steps = list(advice.steps)
                    run.total = len(steps)
                    emit(
                        "thought",
                        {"text": f"plan re-planned at step {i + 1}: {advice.reason}; {len(steps)} hops now"},
                    )
                    continue
                if advice.action != "continue":
                    run.aborted_at = i + 1
                    run.reason = advice.reason
                    stop_cause = "deny" if getattr(decision, "action", None) == "Deny" else "operator"
                    emit("thought", {"text": f"plan abandoned at step {i + 1}/{len(steps)}: {advice.reason}"})
                    return run
            if hasattr(driver, "request_id"):
                driver.request_id = request_id
            result = await _call(
                driver.drive, linear=step.linear, angular=step.angular, duration=step.duration
            )
            if isinstance(result, dict) and result.get("status") not in (None, "success"):
                run.aborted_at = i + 1
                run.reason = _result_text(result)
                stop_cause = "error"
                emit("error", {"where": "plans.execute_plan", "message": run.reason})
                return run
            run.completed = i + 1
            i += 1
        emit("thought", {"text": f"plan {plan.shape} {size} complete: {run.completed}/{len(steps)} hops"})
        return run
    except Exception as exc:
        run.aborted_at = run.aborted_at or (i + 1)
        run.reason = f"{type(exc).__name__}: {exc}"
        stop_cause = "error"
        emit("error", {"where": "plans.execute_plan", "message": run.reason})
        return run
    finally:
        # The plan's terminal stop (phase-1 rule): a zero pair whatever happened above.
        try:
            await _stop(driver, stop_cause)
        except Exception as exc:
            emit("error", {"where": "plans.execute_plan.stop", "message": str(exc)})


# -- the plan_deepracer tool --------------------------------------------------------------------------


class _PlanState:
    calibration: Calibration | None = None
    pen: Pen | None = None
    envelope: Envelope | None = None
    event_log: Any = None
    beat: str | None = None
    last: Proposal | None = None


_state = _PlanState()


def configure_plans(
    *,
    calibration: Calibration | None = None,
    pen: Pen | None = None,
    envelope: Envelope | None = None,
    event_log: Any = None,
    beat: str | None = None,
) -> None:
    """Bind the ``plan_deepracer`` tool to a calibration, a pen, an envelope and an event sink."""
    _state.calibration = calibration
    _state.pen = pen
    _state.envelope = envelope
    _state.event_log = event_log
    _state.beat = beat


def reset_plans() -> None:
    configure_plans()
    _state.last = None


def last_proposal() -> Proposal | None:
    """The most recent plan the tool produced (the beat and the kiosk read progress from it)."""
    return _state.last


def propose(shape: str, size_m: float, **kwargs: Any) -> Proposal:
    """Build and validate a shape with the configured calibration and pen (no events, no motion)."""
    from deepracer_agent import shapes  # shapes imports Step/Plan from here

    return shapes.propose(
        shape,
        size_m,
        calibration=kwargs.pop("calibration", None) or _state.calibration,
        pen=kwargs.pop("pen", None) or _state.pen,
        envelope=kwargs.pop("envelope", None) or _state.envelope,
        **kwargs,
    )


def _emit(type: str, payload: dict[str, Any]) -> None:
    log = _state.event_log
    if log is None:
        from deepracer_agent.gate import resolve_event_log

        log = _state.event_log = resolve_event_log()
    try:
        log.emit(type, payload, source="plan", beat=_state.beat)
    except Exception as exc:  # the log never stops a plan
        logger.debug("plan event failed: %s", exc)


@tool
def plan_deepracer(shape: str, size_m: float = 0.6) -> dict[str, Any]:
    """Plan a named shape as a list of small gated hops and validate it against the car and the pen.
    Never moves the car. Call this first, say the narration aloud, then drive the steps in order
    with drive_deepracer, one call per step; stop at the first denial.

    Args:
        shape: circle, oval, u_turn, figure_8, square, triangle, pentagon, hexagon, slalom,
            straight or back.
        size_m: The size in metres: diameter for a circle, side for a polygon, length for a
            straight, oval or slalom (default 0.6).
    """
    from deepracer_agent.shapes import SHAPE_NAMES

    try:
        proposal = propose(str(shape), float(size_m))
    except (TypeError, ValueError) as exc:
        proposal = Proposal(
            str(shape),
            0.0,
            None,
            ValidationResult.refused("geometry", f"size_m must be a number in metres: {exc}"),
        )
    _state.last = proposal
    size = _fmt_size(proposal.size_m)
    if proposal.ok:
        _emit("thought", {"text": f"plan {proposal.shape} {size}: {proposal.validation.summary()}"})
    else:
        _emit("thought", {"text": f"plan {proposal.shape} {size}: {proposal.validation.summary()}"})
    out = proposal.to_dict()
    out["shapes"] = list(SHAPE_NAMES)
    if proposal.ok and proposal.plan is not None:
        out["drive_calls"] = [s.args() for s in proposal.plan.steps]
        out["note"] = (
            "Validated. Narrate it, then call drive_deepracer once per entry of drive_calls, in order. "
            "The gate rules on each hop; stop at the first denial and say why."
        )
    else:
        out["note"] = "Refused. Say the reasons in one sentence and do not drive."
    return out


__all__ = [
    "FOOTPRINT_SAMPLES_PER_STEP",
    "REFUSAL_CODES",
    "ROTATION_TOLERANCE_RAD",
    "Advice",
    "GateLike",
    "Pen",
    "Plan",
    "PlanRun",
    "Proposal",
    "Step",
    "ValidationResult",
    "configure_plans",
    "default_advice",
    "execute_plan",
    "footprint",
    "last_proposal",
    "plan_deepracer",
    "propose",
    "reset_plans",
    "simulate_path",
    "validate_plan",
]
