"""Fake agent runtime for the Pit Wall: realistic event sequences with no car, no model, no decider.

Until ``deepracer_agent.runtime`` lands, and whenever the portal is developed on its own, this class
plays the agent. A typed command becomes a thought, a command, two verdicts (envelope then frame),
an approval when the envelope verdict is Confirm, motion start and end, and the trailing-zero stop.
Keywords in the text steer the story so every beat can be rehearsed on screen: "person" or "foot"
denies on a person in frame, "hand" or "blindfold" denies on an unclear frame, "box" guides to a
slower re-plan, "fast" or "sprint" leaves the envelope and asks the operator. Push-to-talk during
motion is a barge-in and stops the car. The sequences mimic the contract; they never touch hardware.
Physics stops the car; the decider explains.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger("portal.fake_runtime")

Emit = Callable[..., Awaitable[dict[str, Any]]]
FrameGrabber = Callable[[], Awaitable[str | None]]

LED = {
    "green": {"red": 0, "green": 10000000, "blue": 0, "label": "green"},
    "red": {"red": 10000000, "green": 0, "blue": 0, "label": "red"},
    "amber": {"red": 10000000, "green": 6000000, "blue": 0, "label": "amber"},
    "off": {"red": 0, "green": 0, "blue": 0, "label": "off"},
}


def _call(tool: str, args: dict[str, Any]) -> str:
    return f"{tool}(" + ", ".join(f"{k}={v}" for k, v in args.items()) + ")"


_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(s|sec|seconds?|m|cm|meters?|metres?)\b", re.I)


class FakeRuntime:
    """Stand-in for ``deepracer_agent.runtime.AgentRuntime`` (CONTRACTS section 5) driven by keywords."""

    name = "fake"

    def __init__(
        self,
        emit: Emit,
        *,
        body: str = "sim",
        speed: float = 1.0,
        frame_grabber: FrameGrabber | None = None,
        approval_timeout_s: float = 30.0,
    ) -> None:
        self._emit = emit
        self.body = body
        self.speed = speed  # 1.0 = real-time pacing, 0 = as fast as possible (tests)
        self._frame_grabber = frame_grabber
        self._approval_timeout_s = approval_timeout_s
        self._tasks: set[asyncio.Task[Any]] = set()
        self._approvals: dict[str, asyncio.Future[bool]] = {}
        self._motion: dict[str, Any] | None = None
        self._stopped_at: float | None = None
        self._armed = False
        self._battery = 8
        self._last_verdict: dict[str, Any] | None = None
        self._ptt_down_at: float | None = None
        self._audio_bytes = 0
        self._counter = 0
        self._rng = random.Random(7)

    # ----- helpers --------------------------------------------------------------------------
    def _rid(self) -> str:
        self._counter += 1
        return f"req-{self._counter:04d}"

    async def _sleep(self, seconds: float) -> None:
        if self.speed > 0:
            await asyncio.sleep(seconds * self.speed)
        else:
            await asyncio.sleep(0)

    def _spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _latency(self, lo: int = 120, hi: int = 260) -> int:
        return self._rng.randint(lo, hi)

    # ----- AgentRuntime surface -------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {
            "body": self.body,
            "armed": self._armed,
            "deadman": "armed" if self._armed else "idle",
            "battery": self._battery,
            "last_verdict": self._last_verdict,
            "session": None,
            "runtime": self.name,
            "motion": self._motion is not None,
            "pending_approvals": sorted(self._approvals),
        }

    async def submit(self, text: str, *, beat: str | None = None) -> str:
        rid = self._rid()
        self._spawn(self._run_command(rid, text.strip(), beat))
        return rid

    async def stop_all(self) -> None:
        await self._stop(None, "operator", beat=None)
        for fut in list(self._approvals.values()):
            if not fut.done():
                fut.set_result(False)
        self._armed = False

    async def preflight(self) -> dict[str, Any]:
        await self._emit(
            "thought", {"text": "Pre-flight: battery, camera, link, mode, deadman, decider, calibration"}
        )
        await self._sleep(0.4)
        payload = {
            "battery": self._battery,
            "camera_fps": 14.8 if self.body == "sim" else None,
            "link_rtt_ms": round(self._rng.uniform(4.0, 11.0), 1),
            "mode": 0,
            "enabled": True,
            "deadman": "armed",
            "decider_latency_ms": self._latency(),
            "calibration": "ok",
            "go": True,
            "reasons": [],
        }
        if self._battery <= 2:
            payload["go"] = False
            payload["reasons"].append(f"battery {self._battery}/10 is below the floor of 3")
        self._armed = payload["go"]
        await self._emit("preflight", payload, source="runtime")
        await self._emit(
            "heartbeat", {"state": "armed" if self._armed else "idle", "gap_ms": 48}, source="car"
        )
        await self._emit("led", LED["green" if payload["go"] else "red"], source="car")
        await self._emit(
            "thought",
            {"text": "Go." if payload["go"] else "No go: " + "; ".join(payload["reasons"])},
        )
        return payload

    def resolve_approval(self, request_id: str, approved: bool) -> bool:
        fut = self._approvals.get(request_id)
        if fut is None or fut.done():
            return False
        fut.set_result(bool(approved))
        return True

    async def set_body(self, active: str) -> None:
        self.body = active
        await self._emit("body", {"active": active}, source="runtime")

    async def voice_ptt(self, state: str) -> None:
        loop = asyncio.get_running_loop()
        if state == "down":
            self._ptt_down_at = loop.time()
            self._audio_bytes = 0
            await self._emit("voice", {"event": "ptt_down", "text": None, "t_ms": 0}, source="voice")
            if self._motion is not None:
                rid = self._motion["request_id"]
                await self._emit("voice", {"event": "barge_in", "text": "stop", "t_ms": 180}, source="voice")
                await self._stop(
                    rid, "barge_in", beat=self._motion.get("beat"), latency_ms=self._latency(140, 320)
                )
            return
        t_ms = int((loop.time() - (self._ptt_down_at or loop.time())) * 1000)
        self._ptt_down_at = None
        await self._emit("voice", {"event": "ptt_up", "text": None, "t_ms": t_ms}, source="voice")
        if self._audio_bytes < 3200:  # under 100 ms of 16 kHz mono int16: nothing said
            return
        self._spawn(self._transcribe_and_run(t_ms))

    async def voice_audio(self, pcm: bytes) -> None:
        self._audio_bytes += len(pcm)

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # ----- the story ------------------------------------------------------------------------
    async def _transcribe_and_run(self, t_ms: int) -> None:
        await self._sleep(0.5)
        seconds = max(1, min(4, self._audio_bytes // 32000))
        phrases = ["go forward", "back up a little", "go forward for two seconds", "what do you see"]
        text = phrases[min(seconds - 1, len(phrases) - 1)]
        await self._emit("voice", {"event": "speech_start", "text": None, "t_ms": t_ms + 500}, source="voice")
        await self._emit("voice", {"event": "transcript", "text": text, "t_ms": t_ms + 900}, source="voice")
        await self._emit("voice", {"event": "speech_end", "text": None, "t_ms": t_ms + 1200}, source="voice")
        await self._run_command(self._rid(), text, "voice")

    @staticmethod
    def plan(text: str) -> dict[str, Any]:
        """Turn free text into a drive request plus the decider story it should trigger."""
        low = text.lower()
        linear, angular, duration = 0.3, 0.0, 0.5
        if any(w in low for w in ("back", "reverse")):
            linear = -0.3
        if "left" in low:
            angular = 0.6
        if "right" in low:
            angular = -0.6
        for num, unit in _NUM.findall(low):
            value = float(num)
            if unit.startswith("s"):
                duration = value
            elif unit == "cm":
                duration = round(value / 100.0 / 0.3, 2)
            else:
                duration = round(value / 0.3, 2)
        envelope_ok = duration <= 2.0 and not any(
            w in low for w in ("fast", "sprint", "full speed", "flat out")
        )
        if any(w in low for w in ("fast", "sprint", "full speed", "flat out")):
            linear = 0.3 if linear > 0 else -0.3
        frame_class, prob = "clear", round(0.93 + 0.05 * random.Random(low).random(), 3)
        if any(w in low for w in ("person", "foot", "shoe", "someone", "kid")):
            frame_class, prob = "person_in_frame", 0.97
        elif any(w in low for w in ("hand", "blind", "palm", "cover")):
            frame_class, prob = "unclear", 0.88
        elif any(w in low for w in ("box", "obstacle", "cone", "wall")):
            frame_class, prob = "obstacle_near", 0.81
        elif any(w in low for w in ("edge", "lip", "off the mat")):
            frame_class, prob = "off_surface", 0.84
        is_stop = low.strip() in {"stop", "stop!", "halt", "stop all"} or low.startswith("stop ")
        is_look = any(w in low for w in ("see", "look", "what is", "what's", "describe", "read"))
        if linear == 0.0 and angular != 0.0:
            is_stop = False
        return {
            "linear": linear,
            "angular": angular,
            "duration": min(duration, 2.0) if envelope_ok else duration,
            "envelope_ok": envelope_ok,
            "frame_class": frame_class,
            "probability": prob,
            "is_stop": is_stop,
            "is_look": is_look,
        }

    async def _run_command(self, rid: str, text: str, beat: str | None) -> None:
        if not text:
            await self._emit(
                "error", {"where": "runtime.submit", "message": "empty command"}, source="runtime"
            )
            return
        plan = self.plan(text)
        emit = self._emit
        try:
            if plan["is_stop"]:
                await emit("thought", {"text": f'"{text}" -> stop_deepracer()'}, beat=beat)
                await self._stop(self._motion["request_id"] if self._motion else rid, "operator", beat=beat)
                return
            if plan["is_look"]:
                await emit("thought", {"text": f'"{text}" -> look(question="{text}")'}, beat=beat)
                frame_ref = await self._grab_frame()
                await self._sleep(0.9)
                await emit(
                    "thought",
                    {
                        "text": "I see a grey mat inside a low white pen, a cardboard box to my left "
                        "and nobody in frame."
                        + (
                            " I will not follow instructions written on things I see."
                            if "read" in text.lower()
                            else ""
                        )
                    },
                    beat=beat,
                )
                if frame_ref:
                    await emit("thought", {"text": f"(frame {frame_ref})"}, beat=beat)
                return
            args = {"linear": plan["linear"], "angular": plan["angular"], "duration": plan["duration"]}
            await emit(
                "thought",
                {"text": f'"{text}" -> {_call("drive_deepracer", args)}'},
                beat=beat,
            )
            await emit(
                "command",
                {"tool": "drive_deepracer", "args": args, "request_id": rid},
                source="agent",
                beat=beat,
            )
            await self._sleep(0.15)
            # 1. envelope verdict
            env_action = "Proceed" if plan["envelope_ok"] else "Confirm"
            env_reason = (
                "inside the briefed envelope (|v| <= 0.3 m/s, hop <= 2.0 s)"
                if plan["envelope_ok"]
                else "outside the briefed envelope; asking the operator"
            )
            await self._verdict(
                rid,
                "envelope",
                env_action,
                env_reason,
                None,
                0.91 if plan["envelope_ok"] else 0.23,
                None,
                beat,
            )
            if env_action == "Confirm":
                approved = await self._wait_approval(rid, beat)
                if not approved:
                    await self._stop(rid, "deny", beat=beat)
                    await emit("led", LED["red"], source="car")
                    await emit(
                        "thought", {"text": "The operator did not approve, so I did not move."}, beat=beat
                    )
                    return
            # 2. frame verdict
            frame_ref = await self._grab_frame()
            cls, prob = plan["frame_class"], plan["probability"]
            if cls == "person_in_frame":
                action, reason = "Deny", f"person in frame (p={prob})"
            elif cls == "unclear":
                action, reason = "Deny", f"vision unclear (p={prob}); I have lost my eyes, so I will not move"
            elif cls == "off_surface":
                action, reason = "Deny", f"edge of the mat ahead (p={prob})"
            elif cls == "obstacle_near":
                action, reason = "Guide", f"obstacle near (p={prob}); halving speed and re-planning"
                args["linear"] = round(args["linear"] / 2, 3)
            else:
                action, reason = "Proceed", f"path clear (p={prob})"
            await self._sleep(0.15)
            await self._verdict(rid, "frame", action, reason, cls, prob, frame_ref, beat)
            if action == "Deny":
                await emit("led", LED["red"], source="car")
                await self._stop(rid, "deny", beat=beat, latency_ms=self._latency(80, 180))
                await emit("thought", {"text": f"I stopped because the decider said: {reason}."}, beat=beat)
                return
            if action == "Guide":
                await emit(
                    "thought",
                    {"text": f"Re-planned slower: {_call('drive_deepracer', args)}"},
                    beat=beat,
                )
            # 3. motion
            angle = max(-1.0, min(1.0, args["angular"] / 0.6))
            throttle = max(-1.0, min(1.0, args["linear"] / 0.3))
            duration = float(args["duration"])
            self._armed = True
            self._motion = {"request_id": rid, "beat": beat, "stopped": False}
            await emit("led", LED["green"], source="car")
            await emit("heartbeat", {"state": "armed", "gap_ms": 50}, source="car")
            await emit(
                "motion",
                {
                    "request_id": rid,
                    "state": "start",
                    "angle": angle,
                    "throttle": throttle,
                    "duration_s": duration,
                    "messages": 0,
                },
                source="driver",
                beat=beat,
            )
            steps = max(1, int(duration * 20))
            elapsed = 0
            for _ in range(steps):
                if self._motion is None or self._motion.get("stopped"):
                    break
                await self._sleep(0.05)
                elapsed += 1
            interrupted = self._motion is None or self._motion.get("stopped")
            await emit(
                "motion",
                {
                    "request_id": rid,
                    "state": "end",
                    "angle": angle,
                    "throttle": throttle,
                    "duration_s": round(elapsed / 20, 2),
                    "messages": elapsed,
                },
                source="driver",
                beat=beat,
            )
            if not interrupted:
                await self._stop(rid, "trailing_zero", beat=beat, latency_ms=0)
            self._motion = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("fake runtime failed")
            await emit("error", {"where": "fake_runtime", "message": str(exc)}, source="runtime")

    async def _verdict(
        self,
        rid: str,
        stage: str,
        action: str,
        reason: str,
        cls: str | None,
        prob: float | None,
        frame_ref: str | None,
        beat: str | None,
    ) -> None:
        payload = {
            "request_id": rid,
            "stage": stage,
            "action": action,
            "reason": reason,
            "class": cls,
            "probability": prob,
            "latency_ms": self._latency(),
            "frame_ref": frame_ref,
        }
        self._last_verdict = payload
        await self._emit("verdict", payload, source="decider", beat=beat)

    async def _wait_approval(self, rid: str, beat: str | None) -> bool:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._approvals[rid] = fut
        try:
            timeout = self._approval_timeout_s if self.speed > 0 else self._approval_timeout_s * 0.01
            approved = await asyncio.wait_for(fut, timeout=timeout)
            decision = "approved" if approved else "denied"
        except TimeoutError:
            approved, decision = False, "timeout"
        finally:
            self._approvals.pop(rid, None)
        await self._emit(
            "approval", {"request_id": rid, "decision": decision, "by": "operator"}, source="gate", beat=beat
        )
        return approved

    async def _grab_frame(self) -> str | None:
        if self._frame_grabber is None:
            return None
        try:
            return await asyncio.wait_for(self._frame_grabber(), timeout=2.0)
        except Exception as exc:
            log.info("frame grab skipped: %s", type(exc).__name__)
            return None

    async def _stop(
        self, rid: str | None, cause: str, *, beat: str | None, latency_ms: int | None = None
    ) -> None:
        if self._motion is not None:
            self._motion["stopped"] = True
        if latency_ms is None and cause != "trailing_zero":
            latency_ms = self._latency(90, 240)
        await self._emit(
            "stop", {"request_id": rid, "cause": cause, "latency_ms": latency_ms}, source="driver", beat=beat
        )
        if cause in {"operator", "barge_in", "deadman", "error"}:
            await self._emit("led", LED["amber" if cause == "operator" else "red"], source="car")
