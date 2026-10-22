"""narrator: the rover's instant line on a gate verdict, phrased for the gate mode."""

from __future__ import annotations

import asyncio

from portal.backend.narrator import LINES, Narrator, line_for


def test_lines_for_each_verdict_shape():
    assert (
        line_for(
            {
                "stage": "frame",
                "action": "Deny",
                "class": "unclear",
                "probability": 0.9,
                "reason": "unclear (p=0.90): stopping",
            }
        )
        == LINES["unclear"] + " unclear at 90 percent."
    )
    assert line_for(
        {
            "stage": "frame",
            "action": "Deny",
            "class": "person_in_frame",
            "probability": 0.95,
            "reason": "person_in_frame (p=0.95)",
        }
    ).startswith("Someone is in front of me. I stopped.")
    assert (
        line_for({"stage": "envelope", "action": "Deny", "reason": "vision unavailable"})
        == "My vision is unavailable, so I will not move."
    )
    assert (
        line_for(
            {"stage": "frame", "action": "Guide", "class": "obstacle_near", "reason": "obstacle_near (p=0.7)"}
        )
        == LINES["obstacle_near"]
    )
    assert (
        line_for({"stage": "frame", "action": "Proceed", "class": "clear", "reason": "clear (p=0.93)"})
        is None
    )
    adv = line_for(
        {
            "stage": "frame",
            "action": "Deny",
            "class": "unclear",
            "probability": 0.7,
            "reason": "unclear",
            "advisory": True,
        }
    )
    assert adv.startswith("Advisory: I've lost my eyes. I would not drive blind.")


def test_narrator_emits_one_rover_line_per_request():
    emitted = []

    class Hub:
        async def emit(self, etype, payload, *, source="portal", beat=None, persist=True):
            emitted.append((etype, payload["text"], source))

    async def run():
        n = Narrator(Hub())
        ev = {
            "type": "verdict",
            "source": "agent",
            "seq": 1,
            "payload": {
                "stage": "frame",
                "action": "Deny",
                "class": "unclear",
                "probability": 0.9,
                "reason": "unclear",
                "request_id": "r1",
            },
        }
        await n(ev)
        await n(ev)  # same request, same line: once
        await n(
            {
                "type": "verdict",
                "source": "agent",
                "seq": 2,
                "payload": {"stage": "frame", "action": "Proceed", "class": "clear", "request_id": "r2"},
            }
        )
        await n({"type": "thought", "source": "agent", "seq": 3, "payload": {"text": "x"}})
        await asyncio.sleep(0)

    asyncio.run(run())
    assert emitted == [("thought", "rover: " + LINES["unclear"] + " unclear at 90 percent.", "narrator")]
