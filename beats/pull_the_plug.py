"""Beat 7, Pull the Plug: the router loses power mid-hop and the car stops on its own deadman.

Nothing on the laptop can help: the link is gone. The on-car deadman node sees the heartbeat
stop, zeroes the servos within a second and turns the LED red. The beat asks for a two second
slow roll under the pre-granted envelope so the pull lands mid-motion. When the link returns the rover
says how long it was gone and that it stopped itself. In the sim the plug is pulled by pausing
the runtime's heartbeat (``runtime.pause_heartbeat()`` or ``runtime.heartbeat.stop()``), or by
the fake car's control endpoint,
and the beat asserts the deadman state goes ``tripped``.
Physics stops the car; the decider explains; this beat is the physics.
"""

from __future__ import annotations

import asyncio
import inspect
import time

from . import BeatContext, BeatError, BeatResult, wait_for

ROLL = "Roll forward slowly for two seconds."
TRIP_BUDGET_MS = 1500
RECOVER_BUDGET_S = 3.0


async def _call(obj, name: str, *args) -> bool:
    """Call ``obj.<name>`` or, with a dotted name, ``obj.<attr>.<method>``; False when absent."""
    target = obj
    *path, attr = name.split(".")
    for part in path:
        target = getattr(target, part, None)
    fn = getattr(target, attr, None) if target is not None else None
    if not callable(fn):
        return False
    result = fn(*args)
    if inspect.isawaitable(result):
        await result
    return True


def _deadman(ctx: BeatContext) -> str:
    status = ctx.status()
    state = status.get("deadman")
    if state is None:
        hb = ctx.events_after(0, "heartbeat")
        state = (hb[-1].get("payload") or {}).get("state") if hb else None
    return str(state)


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    if ctx.sim:
        ctx.sim.set_frame("clear")
        ctx.sim.deadman(True)  # the real car always has its deadman; the fake needs asking
    ctx.think("pull the plug: hop, then the router dies")
    seq = ctx.last_seq()
    hop_task = asyncio.create_task(ctx.submit(ROLL))
    rolling = await wait_for(lambda: bool(ctx.events_after(seq, "motion")), timeout_s=10.0)
    if not rolling:
        res.notes.append("no motion event seen before the plug was pulled; cutting the heartbeat anyway")

    t_cut = time.perf_counter()
    cut = await _call(ctx.runtime, "pause_heartbeat") or await _call(ctx.runtime, "heartbeat.stop")
    if not cut:
        if ctx.sim is None:
            raise BeatError(
                "no way to cut the heartbeat: runtime has no pause_heartbeat() and there is no sim control"
            )
        ctx.sim.heartbeat(False)
    ctx.think("link lost: no heartbeat leaving the laptop")

    tripped = await wait_for(lambda: _deadman(ctx) == "tripped", timeout_s=TRIP_BUDGET_MS / 1000)
    trip_ms = int((time.perf_counter() - t_cut) * 1000)
    res.latencies["cut_to_tripped_ms"] = trip_ms if tripped else None
    res.step(
        "deadman tripped after the heartbeat stopped",
        tripped,
        f"state={_deadman(ctx)}",
        trip_ms if tripped else None,
    )
    res.step("trip within budget", tripped and trip_ms <= TRIP_BUDGET_MS, f"budget {TRIP_BUDGET_MS} ms")

    gap_start = time.perf_counter()
    await asyncio.sleep(0.2)
    resumed = await _call(ctx.runtime, "resume_heartbeat") or await _call(ctx.runtime, "heartbeat.start")
    if not resumed and ctx.sim is not None:
        ctx.sim.heartbeat(True)
    rearmed = await wait_for(lambda: _deadman(ctx) == "armed", timeout_s=RECOVER_BUDGET_S)
    gone_ms = int((time.perf_counter() - t_cut) * 1000)
    res.latencies["gone_ms"] = gone_ms
    res.step(
        "deadman re-armed once heartbeats resumed",
        rearmed,
        f"state={_deadman(ctx)}",
        int((time.perf_counter() - gap_start) * 1000),
    )

    try:
        await asyncio.wait_for(hop_task, timeout=15.0)
    except (TimeoutError, Exception) as exc:
        res.notes.append(f"hop turn ended with {type(exc).__name__}")

    stops = [e for e in ctx.events_after(seq, "stop") if (e.get("payload") or {}).get("cause") == "deadman"]
    res.step(
        "a stop with cause deadman was logged", bool(stops) or ctx.body == "car", "" if stops else "none seen"
    )
    seconds = max(1, round(gone_ms / 1000))
    ctx.say(
        f"Lost you for {seconds} second{'s' if seconds != 1 else ''}. I stopped. The car did that, not me."
    )
    return res
