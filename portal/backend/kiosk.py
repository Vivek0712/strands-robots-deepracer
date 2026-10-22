"""Kiosk routes for the Pit Wall: Frame Judge and Simon Says, driven by ``beats.kiosk`` all day.

``POST /kiosk/judge`` grabs one frame from the console (or takes ``frame_b64`` from a tablet
camera), asks the decider over the live label card and answers with class, probability,
latency and whether the frame was kept: only ``consent: true`` writes it to the run dir, otherwise
it is judged in memory and dropped. ``GET``/``POST /kiosk/labels`` is the presenter's card (add a
label live, no retraining). ``GET /kiosk/leaderboard`` is the best fools table. ``POST
/kiosk/simon`` runs the typed command through the real ``DeciderGate`` and returns the reason card,
the slower re-plan and the Box egress log. Every judgement and gate verdict goes through the hub as
an ordinary ``verdict`` (and ``frame``) event, so the audit and ``events.jsonl`` see the kiosks like
any beat. Physics stops the car; the decider explains; these routes are the decider explaining.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
from collections import deque
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from beats.kiosk import (
    JUDGE_BEAT,
    JUDGE_DECIDER_TIMEOUT_S,
    MAX_NICKNAME_CHARS,
    LabelCard,
    Leaderboard,
    TimedFrameSource,
    egress_entry,
    judge_frame,
    simon_async,
)
from deepracer_agent.decider_client import DeciderClient
from deepracer_agent.gate import DeciderGate, Envelope, grab_frame

from .hub import EventHub, utc_now_iso

log = logging.getLogger("portal.kiosk")

MAX_FRAME_B64 = 4 * 1024 * 1024
MAX_COMMAND_CHARS = 200
HISTORY_SIZE = 50


class HubSink:
    """``EventSink`` for the gate and the judge: a sync ``emit`` that lands on the hub's loop.

    The judge runs in a worker thread (the decider client is synchronous) and the gate emits from
    the loop thread; both call ``emit`` without awaiting, so the event is handed to the loop with
    ``run_coroutine_threadsafe`` and ``flush`` waits for the batch before the route answers.
    """

    def __init__(self, hub: EventHub, *, source: str = "kiosk") -> None:
        self.hub = hub
        self.source = source
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: list[Any] = []

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        beat: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "ts": utc_now_iso(),
            "seq": None,
            "session": self.hub.session,
            "beat": beat,
            "type": type,
            "source": source or self.source,
            "payload": payload or {},
        }
        loop = self._loop
        if loop is None or loop.is_closed():
            log.warning("kiosk event %s dropped: no loop bound", type)
            return event
        self._pending.append(asyncio.run_coroutine_threadsafe(self.hub.publish(event, persist=True), loop))
        return event

    async def flush(self) -> None:
        pending, self._pending = self._pending, []
        for fut in pending:
            try:
                await asyncio.wrap_future(fut)
            except Exception as exc:  # the screen must not fail the kiosk answer
                log.warning("kiosk event publish failed: %s", exc)


class KioskService:
    """State the two kiosks share for one portal process: card, leaderboard, gate, history."""

    def __init__(
        self,
        hub: EventHub,
        *,
        frame_source: Callable[[], Any],
        console_host: str,
        decider: Any | None = None,
        decider_url: str | None = None,
        labels: list[str] | None = None,
    ) -> None:
        self.hub = hub
        self.sink = HubSink(hub)
        self.card = LabelCard(labels)
        self.leaderboard = Leaderboard.load(hub.run_dir / "events.jsonl")
        url = decider_url or os.environ.get("DECIDER_URL")
        self.judge_decider = decider or DeciderClient(url, timeout_s=JUDGE_DECIDER_TIMEOUT_S)
        self.gate_decider = decider or DeciderClient(url)
        self.frames = TimedFrameSource(frame_source, host=console_host)
        self.gate = DeciderGate(
            self.gate_decider, self.frames, event_log=self.sink, envelope=Envelope(), beat="kiosk-simon"
        )
        self.history: deque[dict[str, Any]] = deque(maxlen=HISTORY_SIZE)
        self.judgements: deque[dict[str, Any]] = deque(maxlen=HISTORY_SIZE)
        if len(self.leaderboard):
            log.info("kiosk leaderboard resumed with %d judgements", len(self.leaderboard))

    def _bind(self) -> None:
        self.sink.bind(asyncio.get_running_loop())

    # ----- Frame Judge ---------------------------------------------------------------------
    async def judge(self, body: Any) -> tuple[int, dict[str, Any]]:
        self._bind()
        if not isinstance(body, dict):
            return 422, {"accepted": False, "reason": "body must be a JSON object"}
        nickname = body.get("nickname")
        if not isinstance(nickname, str) or not nickname.strip():
            return 422, {"accepted": False, "reason": "nickname is required"}
        if len(nickname.strip()) > MAX_NICKNAME_CHARS:
            return 422, {"accepted": False, "reason": f"nickname longer than {MAX_NICKNAME_CHARS} characters"}
        consent = body.get("consent", False)
        if not isinstance(consent, bool):
            return 422, {"accepted": False, "reason": "consent must be true or false"}
        expected = body.get("expected")
        if expected is not None and not isinstance(expected, str):
            return 422, {"accepted": False, "reason": "expected must be a string or null"}
        raw = body.get("frame_b64")
        frame_bytes: bytes | None
        grab_ms: int | None = None
        if raw is not None:
            if not isinstance(raw, str) or len(raw) > MAX_FRAME_B64:
                return 422, {"accepted": False, "reason": "frame_b64 must be a base64 string under 4 MiB"}
            try:
                frame_bytes = base64.b64decode(raw, validate=True)
            except (binascii.Error, ValueError):
                return 422, {"accepted": False, "reason": "frame_b64 is not base64"}
            if not frame_bytes.startswith(b"\xff\xd8"):
                return 422, {"accepted": False, "reason": "frame_b64 is not a JPEG"}
        else:
            frame = await grab_frame(self.frames)
            grab_ms = self.frames.last_ms
            frame_bytes = frame.jpeg if frame is not None else None
        if not frame_bytes:
            return 503, {
                "accepted": False,
                "reason": "no frame from the camera console",
                "action": "Deny",
                "class": None,
                "probability": None,
                "latency_ms": None,
                "error": "vision unavailable",
                "egress": [egress_entry("camera console GET /route: no frame", self.frames.host, grab_ms)],
            }
        try:
            result = await asyncio.to_thread(
                judge_frame,
                frame_bytes,
                self.card,
                nickname=nickname,
                consent=consent,
                expected=expected,
                decider=self.judge_decider,
                event_log=self.sink,
                run_dir=self.hub.run_dir,
                leaderboard=self.leaderboard,
            )
        except ValueError as exc:
            return 422, {"accepted": False, "reason": str(exc)}
        finally:
            await self.sink.flush()
        del frame_bytes  # without consent nothing else holds the picture
        if grab_ms is not None:
            result["egress"] = [
                egress_entry("camera console GET /route (one frame)", self.frames.host, grab_ms),
                *result["egress"],
            ]
        result["accepted"] = True
        result["session"] = self.hub.session
        self.judgements.appendleft(result)
        return 200, result

    def labels_payload(self) -> dict[str, Any]:
        return {"labels": self.card.to_list(), "count": len(self.card), "max": self.card.max_labels}

    async def set_label(self, body: Any) -> tuple[int, dict[str, Any]]:
        self._bind()
        if not isinstance(body, dict) or not isinstance(body.get("label"), str):
            return 422, {"accepted": False, "reason": "body needs a string label"}
        label = body["label"]
        try:
            if body.get("remove"):
                removed = self.card.remove(label)
                if not removed:
                    return 404, {"accepted": False, "reason": f"label {label!r} is not on the card"}
                note = f"label card: removed {label!r}"
            else:
                description = body.get("description")
                if description is not None and not isinstance(description, str):
                    return 422, {"accepted": False, "reason": "description must be a string or null"}
                key = self.card.add(label, description)
                note = f"label card: added {key!r} (no retraining; the next question asks over the new list)"
        except ValueError as exc:
            return 422, {"accepted": False, "reason": str(exc)}
        self.sink.emit("thought", {"text": note}, beat=JUDGE_BEAT)
        await self.sink.flush()
        return 200, {"accepted": True, **self.labels_payload()}

    def leaderboard_payload(self) -> dict[str, Any]:
        return {
            "session": self.hub.session,
            "entries": self.leaderboard.top(),
            "total": len(self.leaderboard),
            "recent": list(self.judgements)[:10],
        }

    # ----- Simon Says ----------------------------------------------------------------------
    async def simon(self, body: Any) -> tuple[int, dict[str, Any]]:
        self._bind()
        if not isinstance(body, dict):
            return 422, {"accepted": False, "reason": "body must be a JSON object"}
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return 422, {"accepted": False, "reason": "text is required"}
        if len(text) > MAX_COMMAND_CHARS:
            return 422, {"accepted": False, "reason": f"text longer than {MAX_COMMAND_CHARS} characters"}
        try:
            result = await simon_async(text.strip(), self.gate)
        finally:
            await self.sink.flush()
        result["accepted"] = True
        result["session"] = self.hub.session
        result["envelope"] = self.gate.envelope.to_dict()
        self.history.appendleft(result)
        return 200, result

    def simon_payload(self) -> dict[str, Any]:
        return {
            "session": self.hub.session,
            "history": list(self.history),
            "envelope": self.gate.envelope.to_dict(),
        }


async def _json_body(request: Request) -> tuple[Any, str | None]:
    try:
        return await request.json(), None
    except ValueError:
        return None, "body is not JSON"


def mount_kiosk(app: FastAPI, service: KioskService) -> None:
    """Register the five kiosk routes on ``app``."""

    @app.post("/kiosk/judge")
    async def kiosk_judge(request: Request) -> JSONResponse:
        body, err = await _json_body(request)
        if err:
            return JSONResponse({"accepted": False, "reason": err}, status_code=422)
        status, payload = await service.judge(body)
        return JSONResponse(payload, status_code=status)

    @app.post("/kiosk/simon")
    async def kiosk_simon(request: Request) -> JSONResponse:
        body, err = await _json_body(request)
        if err:
            return JSONResponse({"accepted": False, "reason": err}, status_code=422)
        status, payload = await service.simon(body)
        return JSONResponse(payload, status_code=status)

    @app.get("/kiosk/simon")
    async def kiosk_simon_history() -> dict[str, Any]:
        return service.simon_payload()

    @app.get("/kiosk/labels")
    async def kiosk_labels() -> dict[str, Any]:
        return service.labels_payload()

    @app.post("/kiosk/labels")
    async def kiosk_set_label(request: Request) -> JSONResponse:
        body, err = await _json_body(request)
        if err:
            return JSONResponse({"accepted": False, "reason": err}, status_code=422)
        status, payload = await service.set_label(body)
        return JSONResponse(payload, status_code=status)

    @app.get("/kiosk/leaderboard")
    async def kiosk_leaderboard() -> dict[str, Any]:
        return service.leaderboard_payload()


__all__ = ["HubSink", "KioskService", "mount_kiosk"]
