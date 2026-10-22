"""What the agent can read and signal without moving the car: camera, battery, LED, preflight.

``capture_frame`` logs into the car's web console (CSRF token, then password), pulls
one JPEG out of the MJPEG stream by scanning for the JPEG start and end markers, and
saves it under the run directory so the decider and the "what do you see" tool work
from the same picture the screen shows. ``battery_level`` and ``set_led`` are plain
ROS services over rosbridge. ``preflight`` is the pre-show checklist: battery, link,
mode, deadman, camera rate, a read-only look at the calibration and, on the real car,
whether the two PWM outputs are actually enabled (the stock servo node forgets), ending
in one go/no-go with reasons. None of these can move the car, so none is gated; physics
stops the car, the decider explains, and these tools only observe or signal.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from strands import tool
from strands.types.tools import AgentTool

from deepracer_agent.events import EventLog, jpeg_dimensions
from deepracer_agent.transport import DeadmanMonitor, RosbridgeTransport, parse_service_response, result_text

logger = logging.getLogger(__name__)

BATTERY_SERVICE = "/i2c_pkg/battery_level"
BATTERY_TYPE = "deepracer_interfaces_pkg/BatteryLevelSrv"
LED_SERVICE = "/servo_pkg/set_led_state"
LED_TYPE = "deepracer_interfaces_pkg/SetLedCtrlSrv"
CALIBRATION_SERVICE = "/servo_pkg/get_calibration"
CALIBRATION_TYPE = "deepracer_interfaces_pkg/GetCalibrationSrv"
CAL_TYPE_STEERING = 0
CAL_TYPE_THROTTLE = 1

#: ``set_led_state`` takes per-channel PWM 0..10000000 (verified on the car:
#: ``int32 red, green, blue -> int32 error``; the stock .srv comments on green and
#: blue are swapped, the field order is what counts).
LED_MAX = 10_000_000
LED_LABELS: dict[str, tuple[int, int, int]] = {
    "green": (0, LED_MAX, 0),
    "red": (LED_MAX, 0, 0),
    "amber": (LED_MAX, 4_000_000, 0),
    "blue": (0, 0, LED_MAX),
    "off": (0, 0, 0),
}

MJPEG_PATH = "/route?topic=/camera_pkg/display_mjpeg&width=480&height=360"
_SOI = b"\xff\xd8"
_EOI = b"\xff\xd9"
_CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')

#: The battery service answers -1 for "pack not seen or too low" and 0..10 bars.
BATTERY_OK_MIN = 1


def env_console_url() -> str:
    """``DEEPRACER_CONSOLE_URL``, else ``https://<car>`` with the car found by :mod:`.discover`."""
    explicit = os.environ.get("DEEPRACER_CONSOLE_URL")
    if explicit:
        return explicit.rstrip("/")
    if os.environ.get("DEEPRACER_BODY", "sim") != "car":
        return "http://127.0.0.1:8090"
    from deepracer_agent.discover import resolve_host

    return f"https://{resolve_host()}"


# -- MJPEG ---------------------------------------------------------------------


def iter_jpeg_frames(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """Yield complete JPEGs from a byte stream, boundary-agnostic (report 07's parser).

    Scans for ``FF D8`` and the next ``FF D9``; whatever multipart headers sit
    between frames are discarded. A frame whose SOI arrives before the previous
    EOI (a truncated frame) is dropped in favour of the newer one.
    """
    buf = bytearray()
    for chunk in chunks:
        if not chunk:
            continue
        buf.extend(chunk)
        while True:
            start = buf.find(_SOI)
            if start < 0:
                # keep a trailing 0xFF: the 0xD8 may be the first byte of the next chunk
                del buf[: len(buf) - 1 if buf[-1:] == b"\xff" else len(buf)]
                break
            end = buf.find(_EOI, start + 2)
            if end < 0:
                if start:
                    del buf[:start]
                break
            frame = bytes(buf[start : end + 2])
            del buf[: end + 2]
            if len(frame) > 4:
                yield frame


def first_jpeg(chunks: Iterable[bytes]) -> bytes | None:
    for frame in iter_jpeg_frames(chunks):
        return frame
    return None


# -- console -------------------------------------------------------------------


class ConsoleClient:
    """CSRF login + MJPEG + the console JSON API, over httpx.

    Args:
        base_url: ``https://<car>`` or the fake console ``http://127.0.0.1:8090``.
        password: Console password; defaults to ``$DEEPRACER_CONSOLE_PASSWORD``.
        verify: TLS verification; the car's certificate is self-signed.
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        password: str | None = None,
        verify: bool = False,
        timeout: float = 5.0,
    ) -> None:
        self._grab_lock = threading.Lock()
        self.stream: Any | None = None
        self.base_url = (base_url or env_console_url()).rstrip("/")
        self._password = (
            password if password is not None else os.environ.get("DEEPRACER_CONSOLE_PASSWORD", "")
        )
        self.verify = verify
        self.timeout = float(timeout)
        self._client: Any = None
        self._csrf: str | None = None
        self.logged_in = False

    def _http(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.Client(base_url=self.base_url, verify=self.verify, timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self.logged_in = False

    def login(self) -> bool:
        """``GET /login`` for the CSRF meta tag, ``POST /login`` with the password.

        Returns False (never raises) when the console is unreachable or the
        password is wrong (the stock console answers 200 with body ``failure``).
        """
        try:
            page = self._http().get("/login")
            match = _CSRF_RE.search(page.text)
            self._csrf = match.group(1) if match else ""
            headers = {"X-CSRFToken": self._csrf, "Referer": f"{self.base_url}/login"}
            resp = self._http().post("/login", data={"password": self._password}, headers=headers)
            body = resp.text.strip().lower()
            self.logged_in = resp.status_code < 400 and body != "failure"
        except Exception as exc:
            logger.debug("console login failed: %s", exc)
            self.logged_in = False
        return self.logged_in

    def _headers(self) -> dict[str, str]:
        return {"X-CSRFToken": self._csrf or "", "X-Requested-With": "XMLHttpRequest"}

    def api_get(self, path: str) -> dict[str, Any] | None:
        """``GET /api/<path>`` as JSON, logging in first when needed."""
        if not self.logged_in and not self.login():
            return None
        try:
            resp = self._http().get(f"/api/{path.lstrip('/')}", headers=self._headers())
            if resp.status_code == 401:
                self.logged_in = False
                return None
            data = resp.json()
        except Exception as exc:
            logger.debug("console api %s failed: %s", path, exc)
            return None
        return data if isinstance(data, dict) else None

    def stream_chunks(self, timeout: float) -> Iterator[bytes]:
        """Raw MJPEG chunks for at most ``timeout`` seconds."""
        deadline = time.monotonic() + timeout
        with self._http().stream("GET", MJPEG_PATH, headers=self._headers(), timeout=timeout) as resp:
            if resp.status_code >= 400:
                return
            for chunk in resp.iter_bytes(4096):
                yield chunk
                if time.monotonic() > deadline:
                    return

    def attach_stream(self, stream: Any) -> None:
        """Serve grabs from a shared :class:`deepracer_agent.camera.CameraStream` instead of opening one."""
        self.stream = stream

    def capture_frame(self, timeout: float = 5.0) -> bytes | None:
        """One JPEG, or ``None`` when there is no camera (fail closed).

        With a shared stream attached (phase 3's design) this is the newest frame of that stream,
        waited for up to ``timeout`` if none is fresh; without one it opens the MJPEG route itself.
        Grabs are serialised: the agent may call ``capture_frame`` and ``look`` in the same turn,
        and two concurrent MJPEG opens against one console lost frames in rehearsal. One retry
        covers a stream that closed between frames.
        """
        stream = getattr(self, "stream", None)
        if stream is not None and getattr(stream, "running", False):
            jpeg = stream.latest()
            if jpeg is None:
                jpeg = stream.wait_for_frame(timeout)
            return jpeg
        if not self.logged_in and not self.login():
            return None
        with self._grab_lock:
            for attempt in range(2):
                try:
                    jpeg = first_jpeg(self.stream_chunks(timeout))
                except Exception as exc:
                    logger.debug("capture_frame attempt %d failed: %s", attempt + 1, exc)
                    jpeg = None
                if jpeg:
                    return jpeg
            return None

    def frame_rate(self, seconds: float = 1.0) -> float | None:
        """Frames per second over ``seconds``, or ``None`` when none arrived."""
        stream = getattr(self, "stream", None)
        if stream is not None and getattr(stream, "running", False):
            if stream.latest() is None:
                stream.wait_for_frame(seconds)
            return stream.fps()
        if not self.logged_in and not self.login():
            return None
        count = 0
        t0 = time.monotonic()
        try:
            for _ in iter_jpeg_frames(self.stream_chunks(seconds)):
                count += 1
                if time.monotonic() - t0 >= seconds:
                    break
        except Exception as exc:
            logger.debug("frame_rate failed: %s", exc)
            return None
        elapsed = max(time.monotonic() - t0, 1e-3)
        return round(count / elapsed, 1) if count else None


# -- services ------------------------------------------------------------------


def battery_level(transport: RosbridgeTransport) -> dict[str, Any]:
    """``{"level": int, "ok": bool}``; ``level`` is -1 when the pack is not seen."""
    result = transport.service_call(service=BATTERY_SERVICE, type=BATTERY_TYPE, fields={})
    body = parse_service_response(result)
    if body is None or "level" not in body:
        return {"level": -1, "ok": False, "error": result_text(result) or "no response"}
    try:
        level = int(body["level"])
    except (TypeError, ValueError):
        return {"level": -1, "ok": False, "error": f"malformed level {body.get('level')!r}"}
    return {"level": level, "ok": level >= BATTERY_OK_MIN}


def led_refusal(label: Any) -> str | None:
    if not isinstance(label, str) or label.strip().lower() not in LED_LABELS:
        return f"set_led: unknown label {label!r}; use one of {sorted(LED_LABELS)}"
    return None


def set_led(transport: RosbridgeTransport, label: str, event_log: EventLog | None = None) -> dict[str, Any]:
    """Tail LED to a named colour; emits an ``led`` event on success."""
    reason = led_refusal(label)
    if reason:
        return {"status": "error", "content": [{"text": reason}]}
    key = label.strip().lower()
    red, green, blue = LED_LABELS[key]
    result = transport.service_call(
        service=LED_SERVICE, type=LED_TYPE, fields={"red": red, "green": green, "blue": blue}
    )
    body = parse_service_response(result)
    if body is None or int(body.get("error", 0) or 0) != 0:
        return {
            "status": "error",
            "content": [{"text": f"set_led: {result_text(result) or 'service error'}"}],
        }
    if event_log is not None:
        event_log.emit("led", {"red": red, "green": green, "blue": blue, "label": key}, source="driver")
    return {"status": "success", "content": [{"text": f"led {key}"}]}


def read_calibration(transport: RosbridgeTransport) -> dict[str, Any]:
    """Read-only look at both calibration channels: ``{"status": ok|uninitialised|unknown, ...}``.

    Never calls ``set_calibration``; CONTRACTS section 9 forbids writing it.
    """
    channels: dict[str, dict[str, int]] = {}
    for name, cal_type in (("steering", CAL_TYPE_STEERING), ("throttle", CAL_TYPE_THROTTLE)):
        result = transport.service_call(
            service=CALIBRATION_SERVICE, type=CALIBRATION_TYPE, fields={"cal_type": cal_type}
        )
        body = parse_service_response(result)
        if body is None:
            return {"status": "unknown", "reason": f"{name}: {result_text(result) or 'no response'}"}
        try:
            channels[name] = {k: int(body.get(k, 0)) for k in ("min", "mid", "max", "polarity", "error")}
        except (TypeError, ValueError):
            return {"status": "unknown", "reason": f"{name}: malformed response {body!r}"}
    status = "ok"
    for name, ch in channels.items():
        if ch["error"] != 0:
            return {
                "status": "unknown",
                "reason": f"{name}: service error {ch['error']}",
                "channels": channels,
            }
        if ch["min"] == ch["mid"] == ch["max"] == 0:
            status = "uninitialised"
        elif not (ch["min"] <= ch["mid"] <= ch["max"]):
            return {"status": "unknown", "reason": f"{name}: min<=mid<=max violated", "channels": channels}
    return {"status": status, "channels": channels}


# -- PWM outputs (car only) ------------------------------------------------------

PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_ENABLE_FILES = (f"{PWM_CHIP}/pwm0/enable", f"{PWM_CHIP}/pwm1/enable")  # throttle, steering
PWM_READ_COMMAND = "cat " + " ".join(PWM_ENABLE_FILES) + " 2>/dev/null"
PWM_SSH_TIMEOUT_S = 15.0
CAR_SH = Path(__file__).resolve().parents[2] / "car" / "connect" / "car.sh"

PwmRunner = Callable[[str], str]


def ssh_runner(command: str) -> str:
    """Run ``command`` on the car through ``car/connect/car.sh ssh`` and return its stdout.

    Credentials come from ``~/.config/deepracer/env`` inside ``car.sh``; nothing here reads them.
    Raises on a timeout or a non-zero exit so the caller reports ``unknown``, never ``ok``.
    """
    out = subprocess.run(
        ["bash", str(CAR_SH), "ssh", command],
        capture_output=True,
        text=True,
        timeout=PWM_SSH_TIMEOUT_S,
        check=True,
    )
    return out.stdout


def parse_pwm_outputs(stdout: str) -> str:
    """``ok`` when both enable flags read 1, ``disabled`` when either reads 0, else ``unknown``."""
    tokens = [t.strip() for t in stdout.replace("\r", "\n").split() if t.strip()]
    if len(tokens) != 2 or any(t not in ("0", "1") for t in tokens):
        return "unknown"
    return "ok" if tokens == ["1", "1"] else "disabled"


def read_pwm_outputs(runner: PwmRunner | None = None) -> str:
    """Read ``pwm0``/``pwm1`` ``enable`` over SSH (CONTRACTS section 4 ``pwm_outputs``).

    The stock servo node writes period and duty but never ``enable``; with the flags at 0 the
    ESC and steering servo receive no pulses and a perfect ServoCtrlMsg moves nothing.
    ``car/pwm/deepracer-pwm-enable.service`` fixes it at boot; this is the check that it did.
    """
    try:
        return parse_pwm_outputs((runner or ssh_runner)(PWM_READ_COMMAND))
    except Exception as exc:
        logger.debug("pwm_outputs read failed: %s", exc)
        return "unknown"


# -- preflight -----------------------------------------------------------------


DEADMAN_SETTLE_S = 2.0  # seconds to wait for the first deadman_state message


class Preflight:
    """The pre-show checklist, one ``preflight`` event, go/no-go with reasons.

    Args:
        transport: rosbridge transport for battery, calibration and link RTT.
        console: console client for the camera rate (``None`` skips the camera).
        deadman: deadman monitor whose state is reported.
        event_log: where the single ``preflight`` event goes.
        body: ``car`` or ``sim``. In sim a missing camera is a note, not a no-go
            (CONTRACTS section 0: do not block on sensors in sim).
        driver_state: ``(mode, enabled)`` from the driver when it has armed the car.
        decider_latency_ms: supplied by the Intelligence team's gate when known.
        pwm_runner: runs one shell command on the car and returns stdout (tests inject a
            fake); ``None`` uses ``car/connect/car.sh ssh``. Only consulted on ``car``.
    """

    def __init__(
        self,
        transport: RosbridgeTransport,
        *,
        console: ConsoleClient | None = None,
        deadman: DeadmanMonitor | None = None,
        event_log: EventLog | None = None,
        body: str = "sim",
        driver_state: Callable[[], tuple[int | None, bool | None]] | None = None,
        decider_latency_ms: Callable[[], int | None] | None = None,
        pwm_runner: PwmRunner | None = None,
    ) -> None:
        self.transport = transport
        self.console = console
        self.deadman = deadman
        self.event_log = event_log
        self.body = body
        self.driver_state = driver_state
        self.decider_latency_ms = decider_latency_ms
        self.pwm_runner = pwm_runner

    def run(self) -> dict[str, Any]:
        reasons: list[str] = []
        link = self.transport.status()
        if not link["connected"]:
            reasons.append(f"rosbridge not connected: {link['text'][:120]}")
        battery = battery_level(self.transport) if link["connected"] else {"level": -1, "ok": False}
        if not battery["ok"]:
            reasons.append(f"battery level {battery['level']} (pack not seen or too low)")
        mode, enabled = self.driver_state() if self.driver_state else (None, None)
        deadman_state = self.deadman.state if self.deadman is not None else "unknown"
        if deadman_state in ("unknown", "tripped") and self.deadman is not None:
            # The state topic arrives at 2 Hz and a trip clears one second after heartbeats resume;
            # give a fresh session that moment before saying no-go.
            deadline = time.monotonic() + DEADMAN_SETTLE_S
            while deadman_state in ("unknown", "tripped") and time.monotonic() < deadline:
                time.sleep(0.1)
                deadman_state = self.deadman.state
        if deadman_state == "unknown":
            reasons.append("deadman state unknown (no deadman_state message yet)")
        elif deadman_state == "tripped":
            reasons.append("deadman tripped; heartbeats must resume before driving")
        camera_fps = self.console.frame_rate(1.0) if self.console is not None else None
        if camera_fps is None:
            reasons.append(
                "camera: no frames in 1 s" + ("" if self.body == "car" else " (sim: not blocking)")
            )
        calibration = read_calibration(self.transport) if link["connected"] else {"status": "unknown"}
        if calibration["status"] != "ok":
            reasons.append(
                f"calibration {calibration['status']}"
                + (f": {calibration.get('reason')}" if calibration.get("reason") else "")
            )
        decider = self.decider_latency_ms() if self.decider_latency_ms else None
        if self.body == "car":
            pwm_outputs = read_pwm_outputs(self.pwm_runner)
            if pwm_outputs == "disabled":
                reasons.append(
                    "pwm outputs disabled (pwm0/pwm1 enable is 0: the servo node writes no pulses; "
                    "check deepracer-pwm-enable.service)"
                )
            elif pwm_outputs == "unknown":
                reasons.append("pwm outputs unknown (could not read pwm0/pwm1 enable over SSH)")
        else:
            pwm_outputs = "unknown"  # no PWM hardware in the sim; not a reason

        blocking = [r for r in reasons if not r.endswith("(sim: not blocking)")]
        if self.body == "sim":
            blocking = [r for r in blocking if not r.startswith("calibration")]
        payload = {
            "battery": battery["level"],
            "camera_fps": camera_fps,
            "link_rtt_ms": link["rtt_ms"],
            "mode": mode,
            "enabled": enabled,
            "deadman": deadman_state,
            "decider_latency_ms": decider,
            "calibration": calibration["status"],
            "pwm_outputs": pwm_outputs,
            "go": not blocking,
            "reasons": reasons,
        }
        if self.event_log is not None:
            self.event_log.emit("preflight", payload, source="driver")
        return payload


# -- agent tools ----------------------------------------------------------------


def make_tools(
    transport: RosbridgeTransport,
    event_log: EventLog,
    *,
    console: ConsoleClient | None = None,
    preflight: Preflight | None = None,
) -> list[AgentTool]:
    """``capture_frame``, ``battery_level``, ``set_led`` and ``preflight`` bound to one car."""
    console_client = console or ConsoleClient()
    pre = preflight or Preflight(transport, console=console_client, event_log=event_log)

    @tool(
        name="capture_frame",
        description="Save one camera frame from the DeepRacer and return its reference. You cannot see the "
        "image from this result; call look(question) to learn what the camera shows. Fails closed: no "
        "camera means no frame.",
    )
    def capture_frame() -> dict[str, Any]:
        jpeg = console_client.capture_frame()
        if jpeg is None:
            event_log.emit("error", {"where": "capture_frame", "message": "no frame from the camera stream"})
            return {
                "status": "error",
                "content": [{"text": "capture_frame: no frame (camera stream unavailable)"}],
            }
        dims = jpeg_dimensions(jpeg) or (None, None)
        ref = event_log.save_frame(jpeg, width=dims[0], height=dims[1])
        return {
            "frame_ref": ref,
            "frame_path": str(event_log.run_dir / ref),
            "width": dims[0],
            "height": dims[1],
            "note": "frame saved; call look(question) to read it, never guess its contents",
        }

    @tool(
        name="battery_level",
        description="Read the DeepRacer drive battery level (0..10 bars; -1 = pack not seen).",
    )
    def battery_level_tool() -> dict[str, Any]:
        return battery_level(transport)

    @tool(name="set_led", description="Set the DeepRacer tail LED: green, red, amber or off.")
    def set_led_tool(label: str) -> dict[str, Any]:
        return set_led(transport, label, event_log)

    @tool(
        name="preflight",
        description="Run the pre-show checklist (battery, link, deadman, camera, calibration read-only, "
        "PWM outputs enabled) and report go/no-go with reasons.",
    )
    def preflight_tool() -> dict[str, Any]:
        return pre.run()

    return [capture_frame, battery_level_tool, set_led_tool, preflight_tool]


__all__ = [
    "BATTERY_SERVICE",
    "CALIBRATION_SERVICE",
    "LED_LABELS",
    "LED_SERVICE",
    "ConsoleClient",
    "Preflight",
    "battery_level",
    "env_console_url",
    "first_jpeg",
    "iter_jpeg_frames",
    "led_refusal",
    "make_tools",
    "parse_pwm_outputs",
    "read_calibration",
    "read_pwm_outputs",
    "set_led",
]
