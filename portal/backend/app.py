"""Pit Wall FastAPI app: events in, events out, operator intent to the runtime, one screen for sim and car.

``POST /api/events`` accepts any CONTRACTS section 4 event, writes it to the run's ``events.jsonl``
unless the header ``X-Deepracer-Source: eventlog`` says the agent's EventLog already did, and
rebroadcasts it on ``WS /ws``. The socket sends a snapshot of the last two hundred events on
connect and then live events; it receives ``command``, ``approve``, ``stop_all``, ``preflight``,
``body``, ``ptt`` and ``audio`` ops and routes them to the runtime adapter. ``WS /ws/audio`` is the
browser push-to-talk: binary 16 kHz mono int16 PCM frames in while the key is held, the rover's PCM
back out, ``ptt`` as JSON text frames on the same socket so a press always lands before its first
audio frame. ``GET /api/stream/mjpeg``
proxies the car or fake console camera; ``GET /api/runs/{session}/frames/{name}`` serves audit
thumbnails from the run dir; ``/kiosk/*`` are the two booth kiosks (``portal.backend.kiosk``); ``/``
serves the built React frontend. Physics stops the car (pen, hop cap, on-car deadman, marshal's
thumb); the decider explains; this app is only the window.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import SAFETY_LINE
from .car import CarService, mount_car
from .console import ConsoleStream
from .hub import EventHub, utc_now_iso
from .kiosk import KioskService, mount_kiosk
from .narrator import Narrator
from .runtime_adapter import Emit, RuntimeLike, build_runtime
from .schema import validate_event

log = logging.getLogger("portal.app")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
VALID_BODIES = {"car", "sim"}
VALID_PTT = {"down", "up"}
MAX_AUDIO_FRAME = 64 * 1024

_PLACEHOLDER = f"""<!doctype html><html><head><meta charset="utf-8"><title>Pit Wall</title>
<style>body{{background:#0b0d10;color:#e8e8e8;font:20px system-ui;padding:3rem}}
code{{color:#9ad}}</style></head>
<body><h1>Pit Wall backend is up</h1><p>The frontend build is missing. Run <code>make portal-build</code>
(Node 22) and reload. Events: <code>POST /api/events</code>, live: <code>WS /ws</code>.</p>
<p><b>{SAFETY_LINE}</b></p></body></html>"""


def portal_port() -> int:
    url = os.environ.get("PORTAL_URL", "http://127.0.0.1:8765")
    return urlparse(url).port or 8765


def create_app(
    *,
    run_dir: Path | None = None,
    runtime: RuntimeLike | None = None,
    runtime_factory: Callable[[Emit], RuntimeLike] | None = None,
    console: ConsoleStream | None = None,
    frontend_dist: Path | None = None,
    kiosk_decider: Any | None = None,
    kiosk_frame_source: Callable[[], Any] | None = None,
) -> FastAPI:
    """Build the app. Tests inject a recorder runtime (or a factory given the hub emit) and a tmp run dir.

    ``kiosk_decider`` / ``kiosk_frame_source`` let tests give the kiosk routes a stub decider and a
    frame without a console; the default is ``DeciderClient()`` on ``DECIDER_URL`` and the console grab.
    """
    hub = EventHub(run_dir)
    rt_holder: list[Any] = []
    if (
        runtime is None
        and runtime_factory is None
        and os.environ.get("PORTAL_AUTOCONNECT", "") in ("1", "true", "on")
    ):
        # Find the car before the runtime opens its sockets (USB, direct IPv4, or an IPv6 SSH tunnel).
        try:
            from deepracer_agent import connect as _connect

            link = _connect.connect(on_step=lambda st, ok, d: log.info("connect %s %s: %s", st, ok, d))
            log.info("autoconnect: %s", {k: v for k, v in link.to_dict().items() if k != "steps"})
            app_autoconnect_link = link.to_dict()
        except Exception as exc:
            log.warning("autoconnect failed: %s", exc)
            app_autoconnect_link = None
    else:
        app_autoconnect_link = None
    console = console or ConsoleStream()
    dist = frontend_dist if frontend_dist is not None else FRONTEND_DIST

    def shared_camera() -> Any | None:
        cam = getattr(rt_holder[0], "camera", None) if rt_holder else None
        return cam if cam is not None and getattr(cam, "running", False) else None

    async def grab_frame() -> str | None:
        cam = shared_camera()
        if cam is not None:
            data = cam.latest() or await asyncio.to_thread(cam.wait_for_frame, 3.0)
        else:
            data = await console.grab_jpeg()
        if not data:
            return None
        frames = hub.run_dir / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        name = f"{len(list(frames.glob('*.jpg'))) + 1:06d}.jpg"
        (frames / name).write_bytes(data)
        ref = f"frames/{name}"
        await hub.emit("frame", {"frame_ref": ref, "width": 480, "height": 360}, source="camera")
        return ref

    if runtime is not None:
        rt: RuntimeLike = runtime
    elif runtime_factory is not None:
        rt = runtime_factory(hub.emit)
    else:
        rt = build_runtime(
            hub.emit,
            publish=lambda event: hub.publish(event, persist=False),
            run_dir=str(hub.run_dir),
            session=hub.session,
            frame_grabber=grab_frame,
        )

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("Pit Wall session %s, run dir %s, runtime %s", hub.session, hub.run_dir, rt.name)
        starter = getattr(rt, "start", None)
        if starter is not None:
            with contextlib.suppress(Exception):
                await starter()
        try:
            yield
        finally:
            with contextlib.suppress(Exception):
                await rt.aclose()
            with contextlib.suppress(Exception):
                await console.aclose()

    rt_holder.append(rt)
    app = FastAPI(title="DeepRacer Pit Wall", lifespan=lifespan)
    app.state.hub = hub
    app.state.runtime = rt
    app.state.console = console
    kiosk = KioskService(
        hub,
        frame_source=kiosk_frame_source or console.grab_jpeg,
        console_host=urlparse(console.base_url).netloc or console.base_url,
        decider=kiosk_decider,
    )
    app.state.kiosk = kiosk
    mount_kiosk(app, kiosk)  # POST /kiosk/judge, /kiosk/simon, GET/POST /kiosk/labels, GET /kiosk/leaderboard
    hub.attach(Narrator(hub))  # the rover's instant line on a gate verdict
    car = CarService(hub, rt, console=console)
    car.link = app_autoconnect_link
    app.state.car = car
    mount_car(app, car)  # /api/car/*, /api/show/*, /api/memory

    def state_payload() -> dict[str, Any]:
        state = hub.state()
        state["body"] = rt.body
        state["runtime"] = rt.name
        with contextlib.suppress(Exception):
            state["runtime_status"] = rt.status()
        state["console_url"] = console.base_url
        state["safety"] = SAFETY_LINE
        state["decider_url"] = os.environ.get("DECIDER_URL", "http://127.0.0.1:8111")
        state["ts"] = utc_now_iso()
        return state

    # ----- HTTP -----------------------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "session": hub.session, "runtime": rt.name, "clients": hub.client_count}

    @app.get("/api/state")
    async def get_state() -> dict[str, Any]:
        return state_payload()

    @app.post("/api/events")
    async def post_event(
        request: Request,
        x_deepracer_source: str | None = Header(default=None),
    ) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"accepted": False, "reason": "body is not JSON"}, status_code=422)
        event, reason = validate_event(body)
        if event is None:
            return JSONResponse({"accepted": False, "reason": reason}, status_code=422)
        # An EventLog (CONTRACTS section 4) numbers every event it writes, so an event that arrives
        # with a seq is already on disk; only unnumbered hand-posted events are appended here.
        from_eventlog = (x_deepracer_source or "").strip().lower() == "eventlog" or event.get(
            "seq"
        ) is not None
        persist = not from_eventlog
        stored = await hub.publish(event, persist=persist)
        return JSONResponse({"accepted": True, "seq": stored["seq"], "persisted": persist}, status_code=202)

    @app.get("/api/runs/{session}/frames/{name}")
    async def get_frame(session: str, name: str) -> Any:
        path = hub.frame_path(session, name)
        if path is None:
            return JSONResponse({"reason": "frame path escapes the run dir"}, status_code=400)
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg"}:
            return JSONResponse({"reason": "no such frame"}, status_code=404)
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})

    @app.get("/api/stream/mjpeg")
    async def mjpeg_proxy() -> Any:
        cam = shared_camera()
        if cam is not None:
            # Phase 3's design: one stream from the car, re-multiplexed here to every browser.
            first_jpeg = cam.latest() or await asyncio.to_thread(cam.wait_for_frame, 5.0)
            if first_jpeg is None:
                return JSONResponse({"reason": "camera stream has no frame"}, status_code=502)

            def part(jpeg: bytes) -> bytes:
                head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode()
                return head + b"\r\n\r\n" + jpeg + b"\r\n"

            async def fanout() -> AsyncIterator[bytes]:
                yield part(first_jpeg)
                it = cam.frames_iter(max_fps=15.0, timeout_s=5.0)
                sentinel = object()
                while True:
                    jpeg = await asyncio.to_thread(next, it, sentinel)
                    if jpeg is sentinel:
                        return
                    yield part(jpeg)

            return StreamingResponse(
                fanout(),
                media_type="multipart/x-mixed-replace; boundary=frame",
                headers={"Cache-Control": "no-store"},
            )
        gen = console.stream()
        try:
            first = await gen.__anext__()
        except StopAsyncIteration:
            return JSONResponse({"reason": "console stream ended immediately"}, status_code=502)
        except (httpx.HTTPError, OSError) as exc:
            return JSONResponse({"reason": f"console unreachable: {type(exc).__name__}"}, status_code=502)

        async def body() -> AsyncIterator[bytes]:
            yield first
            try:
                async for chunk in gen:
                    yield chunk
            except (httpx.HTTPError, OSError) as exc:
                log.info("mjpeg stream ended: %s", type(exc).__name__)

        return StreamingResponse(
            body(), media_type=console.content_type, headers={"Cache-Control": "no-store"}
        )

    # ----- WebSocket ------------------------------------------------------------------------
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        cid = hub.attach(ws.send_json)
        await ws.send_json({"op": "snapshot", "events": hub.snapshot(), "state": state_payload()})
        try:
            while True:
                msg = await ws.receive_json()
                reply = await handle_op(msg)
                if reply is not None:
                    await ws.send_json(reply)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.info("ws closed: %s", type(exc).__name__)
        finally:
            hub.detach(cid)

    @app.websocket("/ws/audio")
    async def ws_audio(ws: WebSocket) -> None:
        """Browser PTT audio: PCM frames in (binary), the rover's PCM out (binary), ``ptt`` ops as text."""
        await ws.accept()
        sink = getattr(rt, "audio_sink", None)
        token: int | None = None
        pressed_here = False
        if sink is not None and hasattr(sink, "attach"):
            token = sink.attach(ws.send_bytes, lambda: ws.send_json({"op": "barge_in"}))
        voice_status = getattr(rt, "voice_status", None)
        await ws.send_json(
            {
                "op": "audio_ready",
                "sample_rate": int(getattr(sink, "sample_rate", 16000) or 16000),
                "voice": voice_status() if callable(voice_status) else {"state": "off"},
                "max_frame": MAX_AUDIO_FRAME,
            }
        )
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                data = msg.get("bytes")
                if data is not None:
                    if len(data) > MAX_AUDIO_FRAME:
                        reason = f"audio frame over {MAX_AUDIO_FRAME} bytes"
                        await ws.send_json({"op": "error", "for": "audio", "reason": reason})
                        continue
                    if data:
                        await rt.voice_audio(bytes(data))
                    continue
                text = msg.get("text")
                if not text:
                    continue
                try:
                    op = json.loads(text)
                except ValueError:
                    await ws.send_json({"op": "error", "reason": "text frame is not JSON"})
                    continue
                reply = await handle_op(op)  # ptt (validated there), ping; anything else is refused
                if reply is not None:
                    if reply.get("op") == "ack" and reply.get("for") == "ptt":
                        pressed_here = reply.get("state") == "down"
                        if callable(voice_status):
                            reply["voice"] = voice_status()
                    await ws.send_json(reply)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.info("ws/audio closed: %s", type(exc).__name__)
        finally:
            if token is not None and sink is not None:
                sink.detach(token)
            if pressed_here:  # the browser went away mid-press: release, so the agent is not left listening
                with contextlib.suppress(Exception):
                    await rt.voice_ptt("up")

    async def handle_op(msg: Any) -> dict[str, Any] | None:
        if not isinstance(msg, dict) or not isinstance(msg.get("op"), str):
            return {"op": "error", "reason": "message must be an object with a string op"}
        op = msg["op"]
        try:
            if op == "command":
                text = msg.get("text")
                if not isinstance(text, str) or not text.strip():
                    return {"op": "error", "for": op, "reason": "command text is empty"}
                beat = msg.get("beat") if isinstance(msg.get("beat"), str) else None
                rid = await rt.submit(text.strip(), beat=beat)
                return {"op": "ack", "for": op, "request_id": rid}
            if op == "approve":
                rid = msg.get("request_id")
                approved = msg.get("approved")
                if not isinstance(rid, str) or not isinstance(approved, bool):
                    return {
                        "op": "error",
                        "for": op,
                        "reason": "approve needs request_id (str) and approved (bool)",
                    }
                found = rt.resolve_approval(rid, approved)
                hub.pending_approvals.pop(rid, None)
                return {"op": "ack", "for": op, "request_id": rid, "resolved": bool(found)}
            if op == "stop_all":
                await rt.stop_all()
                return {"op": "ack", "for": op}
            if op == "preflight":
                payload = await rt.preflight()
                return {"op": "ack", "for": op, "go": bool(payload.get("go"))}
            if op == "body":
                active = msg.get("active")
                if active not in VALID_BODIES:
                    return {"op": "error", "for": op, "reason": "body.active must be 'car' or 'sim'"}
                await rt.set_body(active)
                return {"op": "ack", "for": op, "active": active}
            if op == "ptt":
                state = msg.get("state")
                if state not in VALID_PTT:
                    return {"op": "error", "for": op, "reason": "ptt.state must be 'down' or 'up'"}
                await rt.voice_ptt(state)
                return {"op": "ack", "for": op, "state": state}
            if op == "audio":
                raw = msg.get("pcm_b64")
                if not isinstance(raw, str):
                    return {"op": "error", "for": op, "reason": "audio needs pcm_b64"}
                try:
                    pcm = base64.b64decode(raw, validate=True)
                except (binascii.Error, ValueError):
                    return {"op": "error", "for": op, "reason": "pcm_b64 is not base64"}
                if len(pcm) > MAX_AUDIO_FRAME:
                    return {"op": "error", "for": op, "reason": f"audio frame over {MAX_AUDIO_FRAME} bytes"}
                await rt.voice_audio(pcm)
                return None  # no ack per audio frame; they arrive at 10-20 Hz
            if op == "ping":
                return {"op": "pong", "ts": utc_now_iso()}
            return {"op": "error", "for": op, "reason": f"unknown op {op!r}"}
        except Exception as exc:
            log.exception("op %s failed", op)
            await hub.emit("error", {"where": f"portal.op.{op}", "message": str(exc)})
            return {"op": "error", "for": op, "reason": str(exc)}

    # ----- frontend -------------------------------------------------------------------------
    if dist.is_dir() and (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        async def placeholder() -> str:
            return _PLACEHOLDER

    return app


def main() -> None:
    """Run the Pit Wall on ``PORTAL_URL``'s port (default 8765) with uvicorn."""
    import uvicorn

    logging.basicConfig(
        level=os.environ.get("PORTAL_LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(message)s"
    )
    host = os.environ.get("PORTAL_HOST", "0.0.0.0")
    uvicorn.run(create_app(), host=host, port=portal_port(), log_level="info")


if __name__ == "__main__":
    main()
