"""Pit Wall portal backend: the one screen for every DeepRacer beat, in sim and on the car.

A small FastAPI app receives every event the agent, driver and decider emit (CONTRACTS section 4),
keeps the last two hundred in memory, appends them to the run's ``events.jsonl`` when nobody else
has, and rebroadcasts them to every browser on a WebSocket. The same socket carries the operator's
commands, Approve/Deny, STOP ALL, push-to-talk audio and the body switch to the agent runtime. The
portal explains and lets a human intervene; it is never the safety layer. Physics stops the car
(pen, hop cap, on-car deadman, marshal's thumb); the decider explains.
"""

SAFETY_LINE = "physics stops the car; the decider explains"

__all__ = ["SAFETY_LINE"]
