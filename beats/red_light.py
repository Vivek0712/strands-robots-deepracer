"""Beat 6, Red Light: the rover narrates while rolling; the presenter says "stop"; it stops mid-word.

One rehearsed barge-in with a headset mic. Under a pre-granted slow envelope the rover rolls
and talks; the presenter speaks over it, Nova Sonic reports the barge-in, the ``BargeInStop``
hook calls ``stop_all`` and the screen shows the barge-in and stop timestamps in milliseconds.
In the sim and in text mode the barge-in is fired by the script. The pre-grant is
``STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`` set by the runtime
for this beat only, and said out loud on the slide. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import asyncio

from deepracer_agent.gate import voice_clock

from . import BeatContext, BeatResult, wait_for

ROLL = "Roll forward slowly for two seconds and tell me what you see as you go."
STOP_BUDGET_MS = 1000


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    if ctx.sim:
        ctx.sim.set_frame("clear")
    ctx.think("red light: rolling under the slow envelope, narrating")
    seq = ctx.last_seq()
    roll_task = asyncio.create_task(ctx.submit(ROLL))

    def moving() -> bool:
        return any(
            (m.get("payload") or {}).get("state") == "start" for m in ctx.events_after(seq, "motion")
        ) or (callable(getattr(ctx.runtime, "is_driving", None)) and ctx.runtime.is_driving())

    started = await wait_for(moving, timeout_s=30.0)
    res.step("the rover started rolling", started)

    ctx.out("you> STOP")
    voice_clock.mark()  # the word is the press; the barge-in stamp counts from it
    stamp = await ctx.barge_in.trigger()
    res.latencies["barge_in_t_ms"] = stamp["t_ms"]
    res.latencies["stop_t_ms"] = stamp["stop_t_ms"]
    res.latencies["barge_in_to_stop_ms"] = stamp["latency_ms"]
    res.step(
        "stop_all ran on barge-in", stamp.get("error") is None, stamp.get("error") or "", stamp["latency_ms"]
    )
    res.step(
        "barge-in to stop under budget", stamp["latency_ms"] <= STOP_BUDGET_MS, f"budget {STOP_BUDGET_MS} ms"
    )

    try:
        await asyncio.wait_for(roll_task, timeout=15.0)
    except (TimeoutError, asyncio.CancelledError, Exception) as exc:
        res.notes.append(f"roll turn ended with {type(exc).__name__}")

    new = ctx.events_after(seq)
    voice = [
        e for e in new if e.get("type") == "voice" and (e.get("payload") or {}).get("event") == "barge_in"
    ]
    stops = [
        e for e in new if e.get("type") == "stop" and (e.get("payload") or {}).get("cause") == "barge_in"
    ]
    res.step(
        "voice barge_in event logged with t_ms", bool(voice) and "t_ms" in (voice[-1].get("payload") or {})
    )
    res.step("stop event with cause barge_in logged", bool(stops))
    driving_after = callable(getattr(ctx.runtime, "is_driving", None)) and ctx.runtime.is_driving()
    res.step("wheels are stopped", not driving_after)
    ctx.say(f"You said stop and my wheels stopped {stamp['latency_ms']} milliseconds later.")
    return res
