"""Two Bodies (recorded): one agent, one line, two cars; "stop all" halts both.

The same operator line goes to two ``AgentRuntime`` instances at once: one on the body
``--body`` selects (the fake car in the sim, the real DeepRacer on ``car``) and one on the
kinematic twin (``deepracer_agent.twin.TwinTransport``), which answers the DeepRacer's own
ROS graph from a bicycle model with the car's calibration constants. Both agents plan the
same hop, both go through the same gate, both move; then "stop all" lands on both
(``runtime.stop_all()`` each) and the beat measures how long each body took to go still.
The twin's pose arrives as ``body`` events so the Pit Wall can draw its trail freezing.
Every event of the twin's runtime is stamped ``body: twin`` (``BodyEventLog``) so the one
``events.jsonl`` tells the two bodies apart. Report 11 keeps this beat pre-recorded: a second
body doubles the failure budget on stage. Physics stops the car; the decider explains; the
twin is a picture of the physics, never a safety layer.
"""

from __future__ import annotations

import asyncio
import inspect
import math
import time
from typing import Any

from deepracer_agent.gate import voice_clock

from . import BeatContext, BeatResult, load_runtime, wait_for

LINE = "Hop forward twenty centimetres."
STOP = "Stop all."
STOP_BUDGET_MS = 1000
#: Let both hops roll this long before "stop all", so the stop lands mid-drive (a hop is 0.5-0.7 s).
MID_DRIVE_S = 0.2
#: The twin must have rolled at least this far before the stop to count as "moved".
MIN_TWIN_TRAVEL_M = 0.02
FREEZE_SAMPLE_S = 0.3
TWIN_LABEL = "twin"


def make_twin_runtime(ctx: BeatContext) -> Any:
    """A second ``AgentRuntime`` on a fresh ``TwinTransport``; its events are stamped ``twin``."""
    from deepracer_agent.twin import BodyEventLog, TwinTransport

    events = BodyEventLog(ctx.events, TWIN_LABEL)
    transport = TwinTransport(event_log=events)
    return load_runtime("sim", beat=ctx.name, events=events, transport=transport)


def twin_pose(runtime: Any) -> dict[str, float] | None:
    pose = getattr(getattr(runtime, "transport", None), "pose", None)
    if not callable(pose):
        return None
    try:
        return dict(pose())
    except Exception:
        return None


def body_of(event: dict[str, Any], car_label: str) -> str:
    """Which body an event belongs to: the stamped label, else the ``--body`` runtime's."""
    payload = event.get("payload") or {}
    label = payload.get("body")
    return str(label) if isinstance(label, str) and label else car_label


async def _submit(runtime: Any, text: str, beat: str) -> str:
    result = runtime.submit(text, beat=beat)
    if inspect.isawaitable(result):
        result = await result
    return str(result)


async def _turn(runtime: Any, text: str, beat: str, timeout_s: float, notes: list[str], label: str) -> str:
    """Submit the line and wait for the turn to end; a cancelled turn is the expected end of a stopped hop."""
    request_id = await _submit(runtime, text, beat)
    wait = getattr(runtime, "wait", None)
    if callable(wait):
        try:
            await wait(request_id, timeout=timeout_s)
        except Exception as exc:
            notes.append(f"{label} turn {request_id} ended with {type(exc).__name__}")
    return request_id


async def _stop(runtime: Any, label: str) -> tuple[str, int, str | None]:
    t0 = time.perf_counter()
    error: str | None = None
    try:
        result = runtime.stop_all()
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return label, int((time.perf_counter() - t0) * 1000), error


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    car_label = ctx.body
    if ctx.sim:
        ctx.sim.set_frame("clear")
        ctx.sim.deadman(True)
    twin = getattr(ctx, "twin", None)
    owns_twin = twin is None
    if owns_twin:
        twin = make_twin_runtime(ctx)
        ctx.twin = twin  # type: ignore[attr-defined]
    try:
        ctx.think("two bodies: the same agent, the same line, the DeepRacer and its twin")
        pose_before = twin_pose(twin)
        seq = ctx.last_seq()
        ctx.out(f"you> {LINE}  (to both bodies)")
        voice_clock.mark()
        t_line = time.perf_counter()
        # Both turns run in the background (the real runtime returns a request id at once; the dry-run
        # fake drives inside submit), so the stop below can land while a hop is still in flight.
        turns = [
            asyncio.create_task(_turn(ctx.runtime, LINE, ctx.name, ctx.step_timeout_s, res.notes, car_label)),
            asyncio.create_task(_turn(twin, LINE, ctx.name, ctx.step_timeout_s, res.notes, TWIN_LABEL)),
        ]

        def started(label: str) -> bool:
            return any(
                (e.get("payload") or {}).get("state") == "start" and body_of(e, car_label) == label
                for e in ctx.events_after(seq, "motion")
            )

        both_started = await wait_for(
            lambda: started(car_label) and started(TWIN_LABEL), timeout_s=ctx.step_timeout_s
        )
        start_ms = int((time.perf_counter() - t_line) * 1000)
        res.latencies["line_to_both_moving_ms"] = start_ms if both_started else None
        res.step(
            "both bodies started on one line",
            both_started,
            f"{car_label}={started(car_label)}, twin={started(TWIN_LABEL)}",
            start_ms if both_started else None,
        )

        if both_started:
            await asyncio.sleep(MID_DRIVE_S)
        ctx.out(f"you> {STOP}")
        voice_clock.mark()
        seq_stop = ctx.last_seq()
        outcomes = await asyncio.gather(_stop(ctx.runtime, car_label), _stop(twin, TWIN_LABEL))
        for label, ms, error in outcomes:
            res.latencies[f"stop_all_{label}_ms"] = ms
            res.step(
                f"stop all halted {label} within budget",
                error is None and ms <= STOP_BUDGET_MS,
                error or f"budget {STOP_BUDGET_MS} ms",
                ms,
            )

        _done, pending = await asyncio.wait(turns, timeout=15.0)
        for task in pending:
            task.cancel()

        trail = [
            e["payload"]
            for e in ctx.events_after(seq, "body")
            if (e.get("payload") or {}).get("body") == TWIN_LABEL and "x" in (e.get("payload") or {})
        ]
        pose_after = twin_pose(twin)
        if trail:
            travel_m = math.hypot(trail[-1]["x"] - trail[0]["x"], trail[-1]["y"] - trail[0]["y"])
        elif pose_before is not None and pose_after is not None:
            travel_m = math.hypot(pose_after["x"] - pose_before["x"], pose_after["y"] - pose_before["y"])
        else:
            travel_m = 0.0
        await asyncio.sleep(FREEZE_SAMPLE_S)
        pose_later = twin_pose(twin)
        if pose_after is not None and pose_later is not None:
            frozen = pose_after == pose_later and pose_later.get("v", 1.0) == 0.0
        else:
            frozen = bool(trail) and trail[-1].get("v") == 0.0
        res.latencies["twin_travel_cm"] = round(travel_m * 100, 1)
        res.step(
            "twin pose moved then froze",
            travel_m >= MIN_TWIN_TRAVEL_M and frozen,
            f"{travel_m * 100:.1f} cm, {len(trail)} pose samples, frozen={frozen}",
        )

        stopped = {
            body_of(e, car_label)
            for e in ctx.events_after(seq_stop, "stop")
            if (e.get("payload") or {}).get("cause") == "operator"
        }
        res.step(
            "a stop by the operator was logged for both bodies",
            {car_label, TWIN_LABEL} <= stopped,
            ", ".join(sorted(stopped)) or "none",
        )
        labels = {body_of(e, car_label) for e in ctx.events_after(seq)}
        res.step(
            "events for both bodies carry distinct body labels",
            {car_label, TWIN_LABEL} <= labels,
            ", ".join(sorted(labels)),
        )

        car_ms = res.latencies.get(f"stop_all_{car_label}_ms")
        twin_ms = res.latencies.get("stop_all_twin_ms")
        car_name = "the DeepRacer" if car_label == "car" else "the fake car"
        ctx.say(
            f"One word stopped two bodies: {car_name} in {car_ms} milliseconds and the twin in {twin_ms}. "
            f"The twin rolled {travel_m * 100:.0f} centimetres and froze. "
            "Physics stopped them; I only said why."
        )
    finally:
        if owns_twin:
            close = getattr(twin, "close", None)
            if callable(close):
                close()
    return res
