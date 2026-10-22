"""Beat 1, Pre-flight: the rover checks itself and says go or no-go before anyone touches it.

Battery, camera, calibration, link and the deadman heartbeat are read by the runtime's
``preflight()`` and written as one ``preflight`` event; the rover reads the verdict aloud and
the LED turns green. If something is wrong, that is the content of the beat: it says what, and
it does not drive. Physics stops the car; the decider explains; pre-flight is where the rover
proves it knows which is which.
"""

from __future__ import annotations

import inspect
import time

from . import BeatContext, BeatResult

REQUIRED_KEYS = ("battery", "deadman", "go", "reasons")


def spoken_verdict(payload: dict) -> str:
    battery = payload.get("battery")
    battery_text = "battery not seen" if battery in (None, -1) else f"battery {battery} of 10"
    fps = payload.get("camera_fps")
    camera = "camera off" if not fps else f"camera {fps:.0f} frames a second"
    link = payload.get("link_rtt_ms")
    link_text = "link unknown" if link is None else f"link {link:.0f} milliseconds"
    deadman = payload.get("deadman", "unknown")
    calibration = payload.get("calibration", "unknown")
    if payload.get("go"):
        return (
            f"Go. {battery_text}, {camera}, {link_text}, calibration {calibration}, deadman {deadman}. "
            "Physics stops me; the decider explains."
        )
    reasons = "; ".join(payload.get("reasons") or ["no reason recorded"])
    return (
        f"No go. {reasons}. {battery_text}, {camera}, deadman {deadman}. "
        "I will not drive until that is fixed."
    )


async def run(ctx: BeatContext) -> BeatResult:
    res = ctx.result
    ctx.think("pre-flight: battery, camera, calibration, link, deadman")
    t0 = time.perf_counter()
    try:
        payload = ctx.runtime.preflight()
        if inspect.isawaitable(payload):
            payload = await payload
    except Exception as exc:
        res.step("preflight() ran", False, str(exc))
        ctx.say(f"No go. Pre-flight itself failed: {exc}")
        return res
    latency = int((time.perf_counter() - t0) * 1000)
    res.latencies["preflight_ms"] = latency
    payload = dict(payload or {})
    missing = [k for k in REQUIRED_KEYS if k not in payload]
    res.step(
        "preflight() returned the section 4 payload",
        not missing,
        f"missing {missing}" if missing else "",
        latency,
    )
    res.step("a preflight event was logged", bool(ctx.events_after(0, "preflight")) or payload is not None)
    go = bool(payload.get("go"))
    reasons = list(payload.get("reasons") or [])
    res.step(
        "go/no-go is explicit", go or bool(reasons), "no-go without reasons" if not go and not reasons else ""
    )
    res.latencies["decider_ms"] = payload.get("decider_latency_ms")
    res.latencies["link_rtt_ms"] = payload.get("link_rtt_ms")
    sentence = spoken_verdict(payload)
    ctx.say(sentence)
    res.notes.append("go" if go else f"no-go: {'; '.join(reasons)}")
    return res
