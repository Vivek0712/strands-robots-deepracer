"""Beat 2, Marshal in the pen: gated 20 cm hops, and a volunteer's foot that stops them.

The only continuous motion in the show. Each hop is one ``drive_deepracer`` call that the
decider gate checks twice (envelope, frame) and the operator approves; the rover hops, hops
again, and when a foot steps into the frame the gate denies, the LED turns red and the rover
says who is in its way and how sure it is. In the sim the foot is the fake camera's
``person_in_frame`` label. Physics stops the car; the decider explains.
"""

from __future__ import annotations

from . import BeatContext, BeatResult

HOP_TEXT = "Hop forward twenty centimetres."
HOPS_BEFORE_FOOT = 2


async def hop(ctx: BeatContext, label: str) -> dict:
    seq = ctx.last_seq()
    await ctx.submit(HOP_TEXT)
    outcome = await ctx.outcome_after(seq)
    ctx.result.latencies[f"{label}_verdict_ms"] = outcome["verdict_latency_ms"]
    return outcome


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    if ctx.sim:
        ctx.sim.set_frame("clear")
    ctx.think("marshal: clear pen, hops on request only")
    for i in range(HOPS_BEFORE_FOOT):
        outcome = await hop(ctx, f"hop{i + 1}")
        verdict = outcome["final_verdict"] or {}
        ok = outcome["moved"] or verdict.get("action") == "Proceed"
        res.step(f"hop {i + 1} proceeded", ok, f"{verdict.get('action')} {verdict.get('reason', '')}".strip())
    if ctx.sim:
        ctx.sim.set_frame("person_in_frame")
    ctx.think("marshal: a foot in the frame")
    outcome = await hop(ctx, "foot")
    verdict = outcome["final_verdict"] or {}
    denied = verdict.get("action") == "Deny" and verdict.get("class") == "person_in_frame"
    res.step(
        "hop with a person in frame was denied",
        denied,
        f"{verdict.get('action')} class={verdict.get('class')} p={verdict.get('probability')}",
        verdict.get("latency_ms"),
    )
    res.step("no motion after the deny", not outcome["moved"])
    stops = outcome["stops"]
    res.step(
        "a stop event with cause deny was logged",
        any((s.get("payload") or {}).get("cause") == "deny" for s in stops),
    )
    if denied:
        p = verdict.get("probability")
        pct = f"{round(p * 100)} percent" if isinstance(p, int | float) else "high confidence"
        ctx.say(f"Stopping. There is a person in my frame at {pct}. I will not hop until they step back.")
    else:
        ctx.say("I did not get the deny I expected; check the decider and the frame label.")
    return res
