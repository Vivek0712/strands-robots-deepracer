"""The rover's own line the moment the gate rules, without waiting for the model.

Blindfold, Marshal and the Sign are the gate's beats: a hand over the lens, a foot in the frame, a
paper that says drive. When the verdict lands the rover should say its line at once, on stage, in
every mode. The model says its own version a second or two later when voice is live; this is the
instant caption (and, with the Stage view's speech toggle, the instant sound). One line per request,
phrased for the mode: enforce stopped, advisory would have stopped. Physics stops the car; the
decider explains; this is the explanation spoken aloud.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("portal.narrator")

LINES: dict[str, str] = {
    "unclear": "I've lost my eyes. I will not drive blind.",
    "person_in_frame": "Someone is in front of me. I stopped.",
    "off_surface": "That is not my floor. I stopped.",
    "obstacle_near": "Something is close ahead. I am slowing down.",
}
UNAVAILABLE_LINE = "My vision is unavailable, so I will not move."
GATE_OFF_WORD = "gate off"


def line_for(payload: dict[str, Any]) -> str | None:
    """The spoken line for one frame-stage verdict payload, or None when there is nothing to say."""
    action = payload.get("action")
    cls = payload.get("class")
    reason = str(payload.get("reason") or "")
    advisory = bool(payload.get("advisory"))
    if action == "Guide" and cls == "obstacle_near":
        text = LINES["obstacle_near"]
    elif action == "Deny":
        if "vision unavailable" in reason:
            text = UNAVAILABLE_LINE
        else:
            text = LINES.get(str(cls), f"I stopped: {reason.split(':')[0]}.")
    else:
        return None
    if advisory:
        text = text.replace("I stopped.", "I would have stopped.").replace(
            "I will not drive blind.", "I would not drive blind."
        )
        text = text.replace("I will not move.", "I would not move.").replace(
            "I am slowing down.", "I would slow down."
        )
        text = "Advisory: " + text
    p = payload.get("probability")
    if isinstance(p, int | float) and cls and action == "Deny" and "unavailable" not in reason:
        text += f" {cls.replace('_', ' ')} at {round(float(p) * 100)} percent."
    return text


class Narrator:
    """A hub subscriber: on a gate verdict it emits ``thought {text: "rover: ..."}`` once per request."""

    def __init__(self, hub: Any) -> None:
        self.hub = hub
        self._said: dict[str, str] = {}

    async def __call__(self, event: dict[str, Any]) -> None:
        if event.get("type") != "verdict" or event.get("source") == "portal":
            return
        payload = event.get("payload") or {}
        if payload.get("stage") not in ("frame", "envelope"):
            return
        text = line_for(payload)
        if text is None:
            return
        rid = str(payload.get("request_id") or event.get("seq"))
        if self._said.get(rid) == text:
            return
        self._said[rid] = text
        if len(self._said) > 200:
            for key in list(self._said)[:-100]:
                self._said.pop(key, None)
        # Never emit from inside the hub's publish loop; schedule it.
        asyncio.get_running_loop().create_task(
            self.hub.emit("thought", {"text": f"rover: {text}"}, source="narrator", beat=event.get("beat"))
        )


__all__ = ["LINES", "Narrator", "line_for"]
