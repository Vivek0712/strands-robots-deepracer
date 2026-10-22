"""Car connection, settings and show routes for the Pit Wall.

``/api/car/*`` wraps :mod:`deepracer_agent.connect` (find the car over USB, IPv4 or an IPv6 SSH
tunnel) and the USB stick with the Wi-Fi credentials; ``/api/show/*`` are the speaker's one-click
acts (LED, maneuver, say, metrics) and ``/api/memory`` the remembered name. Every connect step is
also published on the websocket as a ``connect`` event so the Settings page can show the log live.
Physics stops the car; the decider explains; these routes only find the wire and press the buttons.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("portal.car")

SETTINGS_KEYS = ("DEEPRACER_HOST", "DEEPRACER_MAC", "DEEPRACER_MDNS")
SHAPES = ("square", "circle", "figure_8", "straight", "u_turn", "triangle", "oval", "slalom")


def _connect_mod() -> Any:
    return importlib.import_module("deepracer_agent.connect")


def _state_dict() -> dict[str, Any]:
    env = {k: os.environ.get(k, "") for k in SETTINGS_KEYS}
    env["DEEPRACER_SSH_HOST"] = os.environ.get("DEEPRACER_SSH_HOST", "")
    env["DEEPRACER_CONSOLE_URL"] = os.environ.get("DEEPRACER_CONSOLE_URL", "")
    env["DEEPRACER_ROSBRIDGE_PORT"] = os.environ.get("DEEPRACER_ROSBRIDGE_PORT", "")
    return env


class CarService:
    """Holds the last :class:`CarLink` and runs the workflow off the event loop."""

    def __init__(self, hub: Any, runtime: Any, console: Any | None = None) -> None:
        self.hub = hub
        self.runtime = runtime
        self.console = console
        self.link: dict[str, Any] | None = None
        self._busy = False

    async def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "connected": False,
            "host": os.environ.get("DEEPRACER_HOST", ""),
            "how": "none",
            "busy": self._busy,
            "env": _state_dict(),
            "body": getattr(self.runtime, "body", os.environ.get("DEEPRACER_BODY", "sim")),
        }
        if self.link:
            out.update({k: v for k, v in self.link.items() if k != "steps"})
            try:
                tunnel = _connect_mod().tunnel()
                if self.link.get("how") == "tunnel" and not tunnel.alive:
                    out["connected"] = False
                    out["error"] = "tunnel dropped"
            except Exception:
                pass
        with contextlib.suppress(Exception):
            out["runtime_status"] = self.runtime.status()
        return out

    async def connect(self, host: str | None) -> dict[str, Any]:
        if self._busy:
            return {"accepted": False, "reason": "a connect is already running"}
        self._busy = True
        loop = asyncio.get_running_loop()

        def on_step(step: str, status: str, detail: str) -> None:
            asyncio.run_coroutine_threadsafe(
                self.hub.emit("connect", {"step": step, "status": status, "detail": detail}, source="portal"),
                loop,
            )

        try:
            mod = _connect_mod()
            link = await asyncio.to_thread(mod.connect, host=host or None, on_step=on_step)
            self.link = link.to_dict()
            if link.connected:
                console_rebind = getattr(self.console, "rebind", None)
                if callable(console_rebind):
                    with contextlib.suppress(Exception):
                        await console_rebind(link.console_url)
                rebind = getattr(self.runtime, "reconnect", None)
                if callable(rebind):
                    await self.hub.emit(
                        "connect",
                        {
                            "step": "runtime",
                            "status": "running",
                            "detail": "rebinding the runtime to the car",
                        },
                        source="portal",
                    )
                    try:
                        await rebind()
                        await self.hub.emit(
                            "connect",
                            {"step": "runtime", "status": "ok", "detail": "runtime on the new link"},
                            source="portal",
                        )
                    except Exception as exc:
                        await self.hub.emit(
                            "connect",
                            {"step": "runtime", "status": "fail", "detail": f"{type(exc).__name__}: {exc}"},
                            source="portal",
                        )
            return {"accepted": True, **self.link}
        finally:
            self._busy = False

    async def disconnect(self) -> dict[str, Any]:
        with contextlib.suppress(Exception):
            await asyncio.to_thread(_connect_mod().disconnect)
        self.link = None
        return {"accepted": True, "connected": False}


def mount_car(app: FastAPI, service: CarService) -> None:
    hub = service.hub

    async def body_of(request: Request) -> tuple[Any, str | None]:
        try:
            return await request.json(), None
        except Exception:
            return None, "body is not JSON"

    @app.get("/api/car/status")
    async def car_status() -> dict[str, Any]:
        return await service.status()

    @app.post("/api/car/connect")
    async def car_connect(request: Request) -> JSONResponse:
        body, _ = await body_of(request)
        host = body.get("host") if isinstance(body, dict) else None
        out = await service.connect(str(host).strip() if isinstance(host, str) and host.strip() else None)
        return JSONResponse(out, status_code=200 if out.get("accepted") else 409)

    @app.post("/api/car/disconnect")
    async def car_disconnect() -> dict[str, Any]:
        return await service.disconnect()

    @app.get("/api/car/settings")
    async def car_settings() -> dict[str, Any]:
        return {
            "host": os.environ.get("DEEPRACER_HOST", ""),
            "mac": os.environ.get("DEEPRACER_MAC", ""),
            "mdns": os.environ.get("DEEPRACER_MDNS", ""),
        }

    @app.post("/api/car/settings")
    async def car_settings_set(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        if err or not isinstance(body, dict):
            return JSONResponse(
                {"accepted": False, "reason": err or "body must be an object"}, status_code=422
            )
        for key, env in (("host", "DEEPRACER_HOST"), ("mac", "DEEPRACER_MAC"), ("mdns", "DEEPRACER_MDNS")):
            if key in body and isinstance(body[key], str):
                os.environ[env] = body[key].strip()
        return JSONResponse(
            {
                "accepted": True,
                "host": os.environ.get("DEEPRACER_HOST", ""),
                "mac": os.environ.get("DEEPRACER_MAC", ""),
                "mdns": os.environ.get("DEEPRACER_MDNS", ""),
            }
        )

    @app.get("/api/car/wifi-usb")
    async def wifi_usb_report() -> dict[str, Any]:
        mod = _connect_mod()
        vols = await asyncio.to_thread(mod.external_volumes)
        reports = await asyncio.to_thread(mod.read_device_status, vols)
        return {"volumes": [str(v) for v in vols], "reports": reports}

    @app.post("/api/car/wifi-usb")
    async def wifi_usb_write(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        if err or not isinstance(body, dict) or not isinstance(body.get("ssid"), str):
            return JSONResponse({"accepted": False, "reason": err or "ssid is required"}, status_code=422)
        mod = _connect_mod()
        try:
            written = await asyncio.to_thread(
                mod.write_wifi_creds, body["ssid"], str(body.get("password") or "")
            )
        except ValueError as exc:
            return JSONResponse({"accepted": False, "reason": str(exc)}, status_code=422)
        if not written:
            return JSONResponse(
                {"accepted": False, "reason": "no writable USB volume mounted"}, status_code=409
            )
        return JSONResponse({"accepted": True, "written": [str(p) for p in written]})

    # -- the show --------------------------------------------------------------------------------

    @app.post("/api/show/led")
    async def show_led(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        label = body.get("label") if isinstance(body, dict) else None
        if err or not isinstance(label, str):
            return JSONResponse({"accepted": False, "reason": err or "label is required"}, status_code=422)
        rt = getattr(service.runtime, "_rt", None)
        transport = getattr(rt, "transport", None)
        if transport is None:
            return JSONResponse({"accepted": False, "reason": "no car runtime"}, status_code=409)
        from deepracer_agent.tools import set_led

        try:
            out = await asyncio.to_thread(set_led, transport, label, getattr(rt, "event_log", None))
        except Exception as exc:
            return JSONResponse(
                {"accepted": False, "reason": f"{type(exc).__name__}: {exc}"}, status_code=502
            )
        return JSONResponse({"accepted": True, **(out if isinstance(out, dict) else {"result": out})})

    @app.post("/api/show/maneuver")
    async def show_maneuver(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        if err or not isinstance(body, dict):
            return JSONResponse(
                {"accepted": False, "reason": err or "body must be an object"}, status_code=422
            )
        shape = str(body.get("shape", "square")).strip().lower()
        if shape not in SHAPES:
            return JSONResponse(
                {"accepted": False, "reason": f"shape must be one of {', '.join(SHAPES)}"}, status_code=422
            )
        try:
            size = float(body.get("size_m", 0.6))
        except (TypeError, ValueError):
            return JSONResponse({"accepted": False, "reason": "size_m must be a number"}, status_code=422)
        text = (
            f"Drive a {shape.replace('_', ' ')} of {size:g} m. First call plan_deepracer(shape='{shape}', "
            f"size_m={size:g}) and say the plan in one sentence. Then drive every entry of drive_calls in "
            "order with drive_deepracer, one call per hop, and stop at the first denial."
        )
        rid = await service.runtime.submit(text, beat="maneuver")
        return JSONResponse({"accepted": True, "request_id": rid, "shape": shape, "size_m": size})

    @app.post("/api/show/say")
    async def show_say(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        text = body.get("text") if isinstance(body, dict) else None
        if err or not isinstance(text, str) or not text.strip():
            return JSONResponse({"accepted": False, "reason": err or "text is required"}, status_code=422)
        rid = await service.runtime.submit(text.strip(), beat="show")
        return JSONResponse({"accepted": True, "request_id": rid})

    gate_words = {
        "enforce": "gate ENFORCE: a Deny stops the hop",
        "advisory": "gate ADVISORY: the decider is asked and shown, the hop proceeds; caps and deadman stand",
        "off": "gate OFF by operator: no decider questions; caps and deadman stand",
    }

    @app.get("/api/show/gate")
    async def show_gate() -> dict[str, Any]:
        gate = getattr(getattr(service.runtime, "_rt", None), "gate", None)
        mode = str(getattr(gate, "mode", "enforce"))
        return {"mode": mode, "enabled": mode != "off", "present": gate is not None}

    @app.post("/api/show/gate")
    async def show_gate_set(request: Request) -> JSONResponse:
        body, err = await body_of(request)
        if err or not isinstance(body, dict):
            return JSONResponse(
                {"accepted": False, "reason": err or "body must be an object"}, status_code=422
            )
        mode = body.get("mode")
        if mode is None and isinstance(body.get("enabled"), bool):
            mode = "enforce" if body["enabled"] else "off"
        if mode not in gate_words:
            return JSONResponse(
                {"accepted": False, "reason": "mode must be enforce, advisory or off"}, status_code=422
            )
        gate = getattr(getattr(service.runtime, "_rt", None), "gate", None)
        if gate is None:
            return JSONResponse(
                {"accepted": False, "reason": "no decider gate in this runtime"}, status_code=409
            )
        gate.mode = mode
        await hub.emit("thought", {"text": gate_words[mode]}, source="portal")
        return JSONResponse({"accepted": True, "mode": mode, "enabled": mode != "off"})

    @app.get("/api/show/throttle")
    async def show_throttle() -> dict[str, Any]:
        rt = getattr(service.runtime, "_rt", None)
        cal = getattr(getattr(rt, "driver", None), "calibration", None)
        if cal is None:
            return {"present": False}
        return {
            "present": True,
            "throttle_at_max_speed": cal.throttle_at_max_speed,
            "max_speed_mps": cal.max_speed_mps,
            "note": "servo throttle for a hop at the 0.3 m/s cap; the stock console sends 0.55 for its '0.3'",
        }

    @app.post("/api/show/throttle")
    async def show_throttle_set(request: Request) -> JSONResponse:
        from dataclasses import replace

        from deepracer_agent.calibration import DEFAULT_CALIBRATION_FILE

        body, err = await body_of(request)
        if err or not isinstance(body, dict):
            return JSONResponse(
                {"accepted": False, "reason": err or "body must be an object"}, status_code=422
            )
        try:
            value = float(body.get("throttle_at_max_speed"))
        except (TypeError, ValueError):
            return JSONResponse(
                {"accepted": False, "reason": "throttle_at_max_speed must be a number"}, status_code=422
            )
        if not 0.1 <= value <= 0.9:
            return JSONResponse(
                {"accepted": False, "reason": "throttle_at_max_speed must be within 0.1 and 0.9"},
                status_code=422,
            )
        rt = getattr(service.runtime, "_rt", None)
        driver = getattr(rt, "driver", None)
        if driver is None:
            return JSONResponse({"accepted": False, "reason": "no car runtime"}, status_code=409)
        driver.calibration = replace(driver.calibration, throttle_at_max_speed=round(value, 3))
        if rt is not None:
            rt._calibration = driver.calibration  # survives a rebind
        try:
            DEFAULT_CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_CALIBRATION_FILE.write_text(
                json.dumps(driver.calibration.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
            saved = str(DEFAULT_CALIBRATION_FILE)
        except OSError as exc:
            saved = f"not saved: {exc}"
        await hub.emit(
            "thought",
            {"text": f"hop throttle set to {driver.calibration.throttle_at_max_speed:g} (servo units)"},
            source="portal",
        )
        return JSONResponse(
            {
                "accepted": True,
                "throttle_at_max_speed": driver.calibration.throttle_at_max_speed,
                "saved": saved,
            }
        )

    @app.get("/api/show/metrics")
    async def show_metrics() -> dict[str, Any]:
        from deepracer_agent.showtools import metrics_from_events

        rows = hub.snapshot() if hasattr(hub, "snapshot") else []
        out = metrics_from_events(list(rows))
        with contextlib.suppress(Exception):
            status = service.runtime.status()
            out["armed"] = status.get("armed")
            out["battery"] = out["battery"] if out["battery"] is not None else status.get("battery")
        return out

    @app.get("/api/memory")
    async def memory_get() -> dict[str, Any]:
        from deepracer_agent.showtools import load_memory

        data = load_memory()
        return {
            "operator_name": data.get("operator_name"),
            "facts": data.get("facts") or {},
            "updated": data.get("updated"),
        }

    @app.post("/api/memory")
    async def memory_set(request: Request) -> JSONResponse:
        from deepracer_agent.showtools import forget_all, remember

        body, err = await body_of(request)
        if err or not isinstance(body, dict):
            return JSONResponse(
                {"accepted": False, "reason": err or "body must be an object"}, status_code=422
            )
        if body.get("forget"):
            forget_all()
            return JSONResponse({"accepted": True, "operator_name": None, "facts": {}})
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            return JSONResponse({"accepted": False, "reason": "name is required"}, status_code=422)
        out = remember("operator_name", name.strip())
        return JSONResponse({"accepted": True, **out})


__all__ = ["CarService", "mount_car"]
