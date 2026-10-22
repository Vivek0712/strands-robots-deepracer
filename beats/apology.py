"""Beat 3, The Apology: "why did you stop?" answered from the record, not from memory.

After a stop the room assumes a fault. The presenter asks, and the rover reads its own event
log: the last stop, the verdict behind it, the frozen frame, the class and the probability.
Once the room has heard this, every later unplanned stop reads as competence. In the sim the
beat first provokes a deny with a person in frame, then asks. Physics stops the car; the
decider explains; this beat is the explaining.
"""

from __future__ import annotations

from deepracer_agent.look import explain_stop

from . import BeatContext, BeatResult
from .marshal import hop

QUESTION = "Why did you stop?"


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    if ctx.sim:
        ctx.sim.set_frame("person_in_frame")
    ctx.think("apology: provoke a deny, then ask why")
    outcome = await hop(ctx, "provoke")
    verdict = outcome["final_verdict"] or {}
    res.step("a deny stop exists to explain", verdict.get("action") == "Deny", str(verdict.get("reason", "")))

    seq = ctx.last_seq()
    await ctx.submit(QUESTION)
    outcome = await ctx.outcome_after(seq)
    spoken = [
        t["payload"].get("text", "")
        for t in outcome["thoughts"]
        if "why_stopped" in t["payload"].get("text", "")
    ]
    events = ctx.events_after(0)
    answer = explain_stop(events)
    res.step(
        "why_stopped read the last stop from events.jsonl", answer["cause"] is not None, str(answer["cause"])
    )
    cls = (answer.get("verdict") or {}).get("class")
    res.step(
        "the explanation names the class and probability",
        bool(cls) and cls.replace("_", " ") in answer["text"] and "percent" in answer["text"],
        answer["text"][:120],
    )
    res.step(
        "the frozen frame is referenced or none was captured",
        answer["frame_ref"] is not None or ctx.body == "sim",
    )
    res.notes.append(f"agent used why_stopped: {'yes' if spoken else 'not observed in thoughts'}")
    ctx.say(answer["text"])
    return res
