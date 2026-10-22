"""The car's web console without the car: CSRF login, an MJPEG camera stream and the JSON API.

The real DeepRacer console is Flask behind nginx on https://<car>: `GET /login` renders a page
with `<meta name="csrf-token">`, `POST /login` takes a form `password=` plus `X-CSRFToken` and
sets the `deepracer_token` cookie (a wrong password still answers HTTP 200 with the body
`failure`), and nginx's `auth_request` turns away every `/api/*` and `/route` call without that
cookie. This fake does the same on `http://127.0.0.1:8090`, streams
`/route?topic=/camera_pkg/display_mjpeg&width=480&height=360` as `multipart/x-mixed-replace`
at 15 fps from `harness/frames/<label>.jpg`, and answers `/api/get_battery_level`,
`/api/get_sensor_status`, `/api/get_device_info` and `/api/get_calibration/{angle,throttle}`
with the real JSON shapes (docs/context/02 §3.2). The current label, battery and calibration
profile come from the shared file the fake car writes (`harness.shared`), so
`GET http://127.0.0.1:8092/frame?label=person_in_frame` changes what this camera sees.

Any password is accepted unless `FAKE_CONSOLE_PASSWORD` is set. Run it:
`python -m harness.fake_console`. Unauthenticated controls for tests:
`/control?label=&battery=&camera=connected|not_connected` and `/control/frame` (one JPEG).
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import uuid
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from harness import CONSOLE_PORT
from harness.fake_car import CALIBRATION_PROFILES
from harness.frames import HEIGHT, LABELS, WIDTH, load
from harness.shared import SharedState

logger = logging.getLogger("harness.fake_console")

MJPEG_TOPIC = "/camera_pkg/display_mjpeg"
BOUNDARY = "boundarydonotcross"
PWM_OFFSET = 1_500_000
PWM_ANGLE_CONVERSION = 10_000
PWM_THROTTLE_CONVERSION = 4_500
COOKIE_MAX_AGE = 3600

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="csrf-token" content="{csrf}">
<title>AWS DeepRacer (fake console)</title></head>
<body><form method="post" action="/login"><input type="password" name="password">
<button type="submit">Access vehicle</button></form></body></html>
"""


class FakeConsole:
    """The emulated device console. One instance, one CSRF token, one session token at a time."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = CONSOLE_PORT,
        *,
        shared: SharedState | None = None,
        fps: float = 15.0,
        password: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.shared = shared or SharedState()
        self.fps = fps
        self.password = password if password is not None else os.environ.get("FAKE_CONSOLE_PASSWORD") or None
        self.csrf_token = uuid.uuid4().hex
        self.session_token: str | None = None
        self.login_count = 0
        self.failed_logins = 0
        self.stream_clients = 0
        self.frames_served = 0
        self.sensors: dict[str, str] = {
            "camera_status": "connected",
            "stereo_status": "not_connected",
            "lidar_status": "not_connected",
        }
        self._lock = threading.RLock()
        self._resized: dict[tuple[str, int, int], bytes] = {}
        self._stopping = threading.Event()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> FakeConsole:
        if self._server is not None:
            return self
        self._stopping.clear()
        self._server = ThreadingHTTPServer((self.host, self.port), _handler(self))
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="fake-console", daemon=True)
        self._thread.start()
        logger.info("fake console on %s", self.url)
        return self

    def stop(self) -> None:
        self._stopping.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> FakeConsole:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # frames -------------------------------------------------------------
    def label(self) -> str:
        label = str(self.shared.get("label", "clear"))
        return label if label in LABELS else "clear"

    def frame(self, width: int = WIDTH, height: int = HEIGHT) -> bytes:
        """JPEG bytes of the current label at the requested size (cached per label/size)."""
        label = self.label()
        if (width, height) == (WIDTH, HEIGHT):
            return load(label)
        key = (label, width, height)
        with self._lock:
            cached = self._resized.get(key)
            if cached is None:
                img = Image.open(io.BytesIO(load(label))).resize((width, height))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                cached = self._resized[key] = buf.getvalue()
            return cached

    # auth ---------------------------------------------------------------
    def login(self, password: str) -> str | None:
        """Return a fresh session token, or None for a rejected password."""
        with self._lock:
            if self.password is not None and password != self.password:
                self.failed_logins += 1
                return None
            self.session_token = uuid.uuid4().hex
            self.login_count += 1
            return self.session_token

    def authenticated(self, cookie_header: str | None) -> bool:
        if not cookie_header:
            return False
        jar: cookies.SimpleCookie = cookies.SimpleCookie()
        try:
            jar.load(cookie_header)
        except cookies.CookieError:
            return False
        morsel = jar.get("deepracer_token")
        with self._lock:
            return (
                morsel is not None and self.session_token is not None and morsel.value == self.session_token
            )

    # api ----------------------------------------------------------------
    def battery_level(self) -> dict[str, Any]:
        return {"battery_level": int(self.shared.get("battery", 10)), "success": True}

    def sensor_status(self) -> dict[str, Any]:
        return {**self.sensors, "success": True}

    def device_info(self) -> dict[str, Any]:
        return {"hardware_version": "R2.1", "software_version": "2.0.383.0", "success": True}

    def calibration(self, which: str) -> dict[str, Any] | None:
        """UI units like the real webserver: `(pwm - 1500000) / conversion`, min/max swapped
        when polarity is not positive."""
        if which not in ("angle", "throttle"):
            return None
        profile = str(self.shared.get("calibration", "calibrated"))
        cal = CALIBRATION_PROFILES.get(profile, CALIBRATION_PROFILES["calibrated"])[
            0 if which == "angle" else 1
        ]
        conv = PWM_ANGLE_CONVERSION if which == "angle" else PWM_THROTTLE_CONVERSION
        lo = int((cal["min"] - PWM_OFFSET) / conv)
        hi = int((cal["max"] - PWM_OFFSET) / conv)
        mid = int((cal["mid"] - PWM_OFFSET) / conv)
        if cal["polarity"] <= 0:
            lo, hi = hi, lo
        return {"mid": mid, "min": lo, "max": hi, "polarity": cal["polarity"], "success": True}


def _handler(console: FakeConsole) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "nginx/1.18.0 (fake)"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("console " + fmt, *args)

        def _send(self, code: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Any, extra: dict[str, str] | None = None) -> None:
            self._send(code, json.dumps(payload).encode(), "application/json", extra)

        def _login_page(self) -> None:
            self._send(200, LOGIN_PAGE.format(csrf=console.csrf_token).encode(), "text/html; charset=utf-8")

        def _authed(self) -> bool:
            if console.authenticated(self.headers.get("Cookie")):
                return True
            self._send(401, b"401 Authorization Required", "text/plain")
            return False

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            path = url.path
            if path in ("/", "/home", "/login"):
                self._login_page()
            elif path == "/logout":
                console.session_token = None
                self._json(200, {"success": True}, {"Set-Cookie": "deepracer_token=; Path=/; Max-Age=0"})
            elif path == "/control":
                self._control(q)
            elif path == "/control/frame":
                self._send(200, console.frame(), "image/jpeg")
            elif path == "/route":
                if self._authed():
                    self._stream(q)
            elif path.startswith("/api/"):
                if self._authed():
                    self._api(path)
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:
            url = urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if url.path == "/login":
                form = {k: v[-1] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}
                csrf = self.headers.get("X-CSRFToken") or form.get("csrf_token")
                if csrf != console.csrf_token:
                    self._send(400, b"The CSRF token is missing.", "text/plain")
                    return
                token = console.login(form.get("password", ""))
                if token is None:
                    self._send(200, b"failure", "text/html; charset=utf-8")
                    return
                self._json(
                    200,
                    {"redirect": "/home"},
                    {"Set-Cookie": f"deepracer_token={token}; Path=/; Max-Age={COOKIE_MAX_AGE}"},
                )
            elif url.path == "/control":
                self._control({k: v[-1] for k, v in parse_qs(url.query).items()})
            elif url.path.startswith("/api/"):
                if self._authed():
                    self._api(url.path)
            else:
                self._send(404, b"not found", "text/plain")

        do_PUT = do_POST

        def _control(self, q: dict[str, str]) -> None:
            try:
                if "label" in q:
                    if q["label"] not in LABELS:
                        raise ValueError(f"unknown label {q['label']!r}")
                    console.shared.set(label=q["label"])
                if "battery" in q:
                    console.shared.set(battery=int(q["battery"]))
                if "camera" in q:
                    console.sensors["camera_status"] = q["camera"]
            except ValueError as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "label": console.label(),
                    "battery": int(console.shared.get("battery", 10)),
                    "sensors": dict(console.sensors),
                    "logins": console.login_count,
                    "stream_clients": console.stream_clients,
                    "frames_served": console.frames_served,
                },
            )

        def _api(self, path: str) -> None:
            if path == "/api/get_battery_level":
                self._json(200, console.battery_level())
            elif path == "/api/get_sensor_status":
                self._json(200, console.sensor_status())
            elif path == "/api/get_device_info":
                self._json(200, console.device_info())
            elif path.startswith("/api/get_calibration/"):
                cal = console.calibration(path.rsplit("/", 1)[-1])
                if cal is None:
                    self._send(404, b"not found", "text/plain")
                else:
                    self._json(200, cal)
            elif path == "/api/isSshEnabled":
                self._json(200, {"success": True, "isSshEnabled": True, "reason": ""})
            elif path == "/api/control_modes_available":
                self._json(
                    200, {"control_modes_available": ["manual", "autonomous", "calibration"], "success": True}
                )
            else:
                self._json(404, {"success": False, "reason": f"no such api {path}"})

        def _stream(self, q: dict[str, str]) -> None:
            if q.get("topic", MJPEG_TOPIC) != MJPEG_TOPIC:
                self._send(404, b"topic not found", "text/plain")
                return
            try:
                width = int(q.get("width", WIDTH))
                height = int(q.get("height", HEIGHT))
            except ValueError:
                self._send(400, b"bad size", "text/plain")
                return
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace;boundary={BOUNDARY}")
            self.send_header(
                "Cache-Control", "no-cache, no-store, must-revalidate, pre-check=0, post-check=0, max-age=0"
            )
            self.send_header("Pragma", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            console.stream_clients += 1
            period = 1.0 / console.fps
            try:
                while not console._stopping.is_set():
                    jpeg = console.frame(width, height)
                    head = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n"
                    part = head.encode() + jpeg + b"\r\n"
                    self.wfile.write(part)
                    self.wfile.flush()
                    console.frames_served += 1
                    time.sleep(period)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                console.stream_clients -= 1
                self.close_connection = True

    return Handler


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=CONSOLE_PORT)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(name)s %(message)s")
    with FakeConsole(port=a.port, fps=a.fps) as console:
        print(f"fake console: {console.url}/login  stream: {console.url}/route?topic={MJPEG_TOPIC}  (Ctrl-C)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
