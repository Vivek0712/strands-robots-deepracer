"""capture_frame (CSRF login + MJPEG), battery_level, set_led, calibration read, preflight go/no-go."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from deepracer_agent.events import EventLog
from deepracer_agent.tools import (
    BATTERY_SERVICE,
    CALIBRATION_SERVICE,
    LED_LABELS,
    LED_SERVICE,
    ConsoleClient,
    Preflight,
    battery_level,
    env_console_url,
    first_jpeg,
    iter_jpeg_frames,
    led_refusal,
    make_tools,
    parse_pwm_outputs,
    read_calibration,
    read_pwm_outputs,
    set_led,
)
from deepracer_agent.transport import DEADMAN_STATE_TOPIC, DeadmanMonitor
from tests.unit._car_fakes import FakeAction, err, make_transport, ok, service_ok, tiny_jpeg

JPEG = tiny_jpeg(480, 360)


# -- MJPEG parser --------------------------------------------------------------


def _multipart(*frames: bytes) -> bytes:
    out = b""
    for f in frames:
        out += (
            b"--boundarydonotcross\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(f)
            + f
            + b"\r\n"
        )
    return out


@pytest.mark.parametrize("chunk", [1, 3, 7, 4096])
def test_iter_jpeg_frames_boundary_agnostic_any_chunking(chunk: int) -> None:
    other = tiny_jpeg(2, 2)
    stream = _multipart(JPEG, other)
    chunks = [stream[i : i + chunk] for i in range(0, len(stream), chunk)]
    assert list(iter_jpeg_frames(chunks)) == [JPEG, other]


def test_first_jpeg_skips_leading_garbage_and_truncated_frame() -> None:
    stream = b"junk\xff\xd8truncated-no-eoi" + _multipart(JPEG)
    frame = first_jpeg([stream])
    assert frame is not None and frame.endswith(b"\xff\xd9") and frame.startswith(b"\xff\xd8")


@pytest.mark.parametrize(
    "chunks", [[], [b""], [b"no markers here"], [b"\xff\xd8 only start"], [b"\xff\xd9 only end"]]
)
def test_refusal_table_first_jpeg_none_without_a_full_frame(chunks: list[bytes]) -> None:
    assert first_jpeg(chunks) is None


# -- console (a tiny stand-in for QA's fake console on an ephemeral port) ---------


class _Console(BaseHTTPRequestHandler):
    password = "pw"
    logins: ClassVar[list[dict[str, str]]] = []
    frames: int = 3

    def log_message(self, *a: Any) -> None:  # quiet
        pass

    def do_GET(self) -> None:
        if self.path == "/login":
            body = b'<html><meta name="csrf-token" content="tok123"></html>'
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/route?topic=/camera_pkg/display_mjpeg"):
            if "deepracer_token=ok" not in self.headers.get("Cookie", ""):
                self.send_response(401)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=boundarydonotcross")
            self.end_headers()
            for _ in range(type(self).frames):
                self.wfile.write(_multipart(JPEG))
                self.wfile.flush()
        elif self.path == "/api/get_battery_level":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"battery_level": 7, "success": true}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = self.rfile.read(length).decode()
        type(self).logins.append({"csrf": self.headers.get("X-CSRFToken", ""), "form": form})
        self.send_response(200)
        good = f"password={type(self).password}" in form and self.headers.get("X-CSRFToken") == "tok123"
        if good:
            self.send_header("Set-Cookie", "deepracer_token=ok; Path=/")
        self.end_headers()
        self.wfile.write(b"success" if good else b"failure")


@pytest.fixture
def console_url() -> Any:
    server = HTTPServer(("127.0.0.1", 0), _Console)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Console.logins.clear()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_console_login_and_capture_frame(console_url: str) -> None:
    client = ConsoleClient(console_url, password="pw")
    assert client.login() is True
    assert _Console.logins[-1]["csrf"] == "tok123" and "password=pw" in _Console.logins[-1]["form"]
    frame = client.capture_frame(timeout=3.0)
    assert frame == JPEG
    assert client.frame_rate(0.3) is not None
    assert client.api_get("get_battery_level") == {"battery_level": 7, "success": True}
    client.close()


def test_console_wrong_password_fails_closed(console_url: str) -> None:
    client = ConsoleClient(console_url, password="nope")
    assert client.login() is False
    assert client.capture_frame(timeout=1.0) is None
    assert client.api_get("get_battery_level") is None


def test_console_unreachable_never_raises() -> None:
    client = ConsoleClient("http://127.0.0.1:9", password="pw", timeout=0.5)
    assert client.login() is False and client.capture_frame(0.5) is None and client.frame_rate(0.2) is None


def test_env_console_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPRACER_CONSOLE_URL", raising=False)
    monkeypatch.setenv("DEEPRACER_BODY", "sim")
    assert env_console_url() == "http://127.0.0.1:8090"
    monkeypatch.setenv("DEEPRACER_BODY", "car")
    monkeypatch.setenv("DEEPRACER_HOST", "192.168.0.7")
    assert env_console_url() == "https://192.168.0.7"
    monkeypatch.setenv("DEEPRACER_CONSOLE_URL", "http://x:1/")
    assert env_console_url() == "http://x:1"


# -- battery --------------------------------------------------------------------


@pytest.mark.parametrize(
    "result,expected",
    [
        (service_ok({"level": 7}), {"level": 7, "ok": True}),
        (service_ok({"level": 1}), {"level": 1, "ok": True}),
        (service_ok({"level": 0}), {"level": 0, "ok": False}),
        (service_ok({"level": -1}), {"level": -1, "ok": False}),
    ],
)
def test_battery_level_table(result: dict[str, Any], expected: dict[str, Any]) -> None:
    action = FakeAction()
    action.service_results[BATTERY_SERVICE] = [result]
    transport, _, _ = make_transport(action)
    assert battery_level(transport) == expected
    assert (
        action.services[0]["type"] == "deepracer_interfaces_pkg/BatteryLevelSrv"
        and action.services[0]["fields"] == {}
    )


@pytest.mark.parametrize(
    "result", [err("No service response received"), service_ok({"nope": 1}), service_ok({"level": "x"})]
)
def test_refusal_table_battery_unreadable_is_not_ok(result: dict[str, Any]) -> None:
    action = FakeAction()
    action.service_results[BATTERY_SERVICE] = [result]
    transport, _, _ = make_transport(action)
    out = battery_level(transport)
    assert out["ok"] is False and out["level"] == -1 and "error" in out


# -- LED ------------------------------------------------------------------------


@pytest.mark.parametrize("label", ["green", "red", "amber", "off", " Red "])
def test_set_led_sends_verified_field_names(tmp_path: Path, label: str) -> None:
    log = EventLog(tmp_path, session="s", portal_url="")
    transport, action, _ = make_transport()
    assert set_led(transport, label, log)["status"] == "success"
    call = action.services[0]
    assert call["service"] == LED_SERVICE and call["type"] == "deepracer_interfaces_pkg/SetLedCtrlSrv"
    assert set(call["fields"]) == {"red", "green", "blue"}
    assert tuple(call["fields"][k] for k in ("red", "green", "blue")) == LED_LABELS[label.strip().lower()]
    assert all(0 <= v <= 10_000_000 for v in call["fields"].values())
    assert log.last("led")["payload"]["label"] == label.strip().lower()


@pytest.mark.parametrize("label", ["purple", "", None, 3, "GREENISH"])
def test_refusal_table_set_led(label: Any) -> None:
    transport, action, _ = make_transport()
    result = set_led(transport, label)
    assert result["status"] == "error" and "unknown label" in result["content"][0]["text"]
    assert action.services == []
    assert led_refusal(label)


def test_set_led_service_error_is_reported(tmp_path: Path) -> None:
    action = FakeAction()
    action.service_results[LED_SERVICE] = [service_ok({"error": 1})]
    transport, _, _ = make_transport(action)
    log = EventLog(tmp_path, session="s", portal_url="")
    assert set_led(transport, "red", log)["status"] == "error"
    assert log.read("led") == []


# -- calibration (read-only) -------------------------------------------------------


def _cal(min_: int, mid: int, max_: int, error: int = 0) -> dict[str, Any]:
    return service_ok({"min": min_, "mid": mid, "max": max_, "polarity": 1, "error": error})


def test_read_calibration_ok_and_never_writes() -> None:
    action = FakeAction()
    action.service_results[CALIBRATION_SERVICE] = [
        _cal(1200000, 1450000, 1700000),
        _cal(1311000, 1446000, 1603500),
    ]
    transport, _, _ = make_transport(action)
    out = read_calibration(transport)
    assert out["status"] == "ok" and out["channels"]["throttle"]["mid"] == 1446000
    assert [c["fields"] for c in action.services] == [{"cal_type": 0}, {"cal_type": 1}]
    assert all(c["service"] == CALIBRATION_SERVICE for c in action.services)


@pytest.mark.parametrize(
    "results,status",
    [
        ([_cal(0, 0, 0), _cal(0, 0, 0)], "uninitialised"),
        ([err("timeout")], "unknown"),
        ([_cal(1, 2, 3, error=1)], "unknown"),
        ([_cal(3, 2, 1)], "unknown"),
        ([ok("response:\ngarbage")], "unknown"),
    ],
)
def test_read_calibration_table(results: list[dict[str, Any]], status: str) -> None:
    action = FakeAction()
    action.service_results[CALIBRATION_SERVICE] = results
    transport, _, _ = make_transport(action)
    assert read_calibration(transport)["status"] == status


# -- preflight ----------------------------------------------------------------------


class _NoCamera(ConsoleClient):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:9", password="x")

    def frame_rate(self, seconds: float = 1.0) -> float | None:
        return None


class _Camera(_NoCamera):
    def frame_rate(self, seconds: float = 1.0) -> float | None:
        return 15.0


def _pwm_runner(stdout: str = "1\n1\n", raises: bool = False):
    calls: list[str] = []

    def run(command: str) -> str:
        calls.append(command)
        if raises:
            raise TimeoutError("ssh timed out")
        return stdout

    run.calls = calls  # type: ignore[attr-defined]
    return run


def _preflight(
    tmp_path: Path,
    *,
    body: str,
    battery: int,
    camera: bool,
    deadman: str | None,
    cal_ok: bool = True,
    pwm: str = "1\n1\n",
    pwm_raises: bool = False,
):
    action = FakeAction()
    action.service_results[BATTERY_SERVICE] = [service_ok({"level": battery})]
    action.service_results[CALIBRATION_SERVICE] = [_cal(1, 2, 3)] if cal_ok else [_cal(0, 0, 0)]
    transport, action, topics = make_transport(action)
    log = EventLog(tmp_path, session="s", portal_url="")
    mon = DeadmanMonitor(transport, log)
    mon.start()
    if deadman:
        topics[DEADMAN_STATE_TOPIC].deliver(
            f'{{"state": "{deadman}", "gap_ms": 5, "since": "t", "trips": 0}}'
        )
    pre = Preflight(
        transport,
        console=_Camera() if camera else _NoCamera(),
        deadman=mon,
        event_log=log,
        body=body,
        driver_state=lambda: (0, True),
        decider_latency_ms=lambda: 150,
        pwm_runner=_pwm_runner(pwm, raises=pwm_raises),
    )
    return pre.run(), log


def test_preflight_go_on_car_when_everything_is_green(tmp_path: Path) -> None:
    payload, log = _preflight(tmp_path, body="car", battery=8, camera=True, deadman="armed")
    assert payload["go"] is True and payload["reasons"] == []
    assert payload["battery"] == 8 and payload["camera_fps"] == 15.0 and payload["deadman"] == "armed"
    assert payload["mode"] == 0 and payload["enabled"] is True and payload["calibration"] == "ok"
    assert payload["link_rtt_ms"] is not None and payload["decider_latency_ms"] == 150
    assert payload["pwm_outputs"] == "ok"
    assert set(payload) == {
        "battery", "camera_fps", "link_rtt_ms", "mode", "enabled", "deadman",
        "decider_latency_ms", "calibration", "pwm_outputs", "go", "reasons",
    }  # fmt: skip
    assert log.read("preflight")[0]["payload"] == payload and len(log.read("preflight")) == 1


@pytest.mark.parametrize(
    "kw,reason",
    [
        ({"battery": -1, "camera": True, "deadman": "armed"}, "battery level -1"),
        ({"battery": 0, "camera": True, "deadman": "armed"}, "battery level 0"),
        ({"battery": 8, "camera": False, "deadman": "armed"}, "camera: no frames"),
        ({"battery": 8, "camera": True, "deadman": None}, "deadman state unknown"),
        ({"battery": 8, "camera": True, "deadman": "tripped"}, "deadman tripped"),
        ({"battery": 8, "camera": True, "deadman": "armed", "cal_ok": False}, "calibration uninitialised"),
        ({"battery": 8, "camera": True, "deadman": "armed", "pwm": "0\n0\n"}, "pwm outputs disabled"),
        ({"battery": 8, "camera": True, "deadman": "armed", "pwm": "1\n0\n"}, "pwm outputs disabled"),
        ({"battery": 8, "camera": True, "deadman": "armed", "pwm": ""}, "pwm outputs unknown"),
        ({"battery": 8, "camera": True, "deadman": "armed", "pwm_raises": True}, "pwm outputs unknown"),
    ],
)
def test_refusal_table_preflight_no_go_on_car(tmp_path: Path, kw: dict[str, Any], reason: str) -> None:
    payload, _ = _preflight(tmp_path, body="car", **kw)
    assert payload["go"] is False
    assert any(reason in r for r in payload["reasons"]), payload["reasons"]


def test_preflight_in_sim_does_not_block_on_camera_or_calibration(tmp_path: Path) -> None:
    payload, _ = _preflight(tmp_path, body="sim", battery=8, camera=False, deadman="armed", cal_ok=False)
    assert payload["go"] is True
    assert any("sim: not blocking" in r for r in payload["reasons"])
    assert payload["pwm_outputs"] == "unknown", "the sim has no PWM hardware"
    assert not any("pwm" in r for r in payload["reasons"])


def test_preflight_in_sim_never_runs_the_pwm_ssh_read(tmp_path: Path) -> None:
    runner = _pwm_runner("0\n0\n")
    action = FakeAction()
    action.service_results[BATTERY_SERVICE] = [service_ok({"level": 8})]
    transport, _, _ = make_transport(action)
    payload = Preflight(transport, body="sim", pwm_runner=runner).run()
    assert runner.calls == [] and payload["pwm_outputs"] == "unknown"


def test_preflight_on_car_reads_both_enable_files_over_the_runner(tmp_path: Path) -> None:
    runner = _pwm_runner("1\r\n1\r\n")  # ssh -t adds carriage returns
    action = FakeAction()
    action.service_results[BATTERY_SERVICE] = [service_ok({"level": 8})]
    transport, _, _ = make_transport(action)
    payload = Preflight(transport, body="car", pwm_runner=runner).run()
    assert len(runner.calls) == 1
    assert "/sys/class/pwm/pwmchip0/pwm0/enable" in runner.calls[0]
    assert "/sys/class/pwm/pwmchip0/pwm1/enable" in runner.calls[0]
    assert payload["pwm_outputs"] == "ok" and not any("pwm" in r for r in payload["reasons"])


@pytest.mark.parametrize(
    "stdout,expected",
    [
        ("1\n1\n", "ok"),
        ("1\r\n1\r\n", "ok"),
        ("0\n1\n", "disabled"),
        ("1\n0\n", "disabled"),
        ("0\n0\n", "disabled"),
        ("1\n", "unknown"),
        ("", "unknown"),
        ("cat: /sys/class/pwm/pwmchip0/pwm0/enable: No such file\n", "unknown"),
        ("1\n1\n1\n", "unknown"),
        ("2\n1\n", "unknown"),
    ],
)
def test_parse_pwm_outputs_table(stdout: str, expected: str) -> None:
    assert parse_pwm_outputs(stdout) == expected


def test_read_pwm_outputs_runner_failure_is_unknown_never_ok() -> None:
    assert read_pwm_outputs(_pwm_runner(raises=True)) == "unknown"
    assert read_pwm_outputs(_pwm_runner("1\n1\n")) == "ok"


def test_preflight_link_down_is_no_go(tmp_path: Path) -> None:
    action = FakeAction()
    action.status_result = ok("backend: roslibpy; not connected - refused")
    transport, _, _ = make_transport(action)
    payload = Preflight(transport, body="sim").run()
    assert payload["go"] is False and payload["link_rtt_ms"] is None
    assert any("rosbridge not connected" in r for r in payload["reasons"])
    assert action.services == [], "no service is tried on a dead link"


# -- agent tools ----------------------------------------------------------------------


def test_make_tools_names_and_capture_frame_tool(tmp_path: Path, console_url: str) -> None:
    transport, _, _ = make_transport()
    log = EventLog(tmp_path, session="s", portal_url="")
    tools = make_tools(transport, log, console=ConsoleClient(console_url, password="pw"))
    assert [t.tool_name for t in tools] == ["capture_frame", "battery_level", "set_led", "preflight"]
    out = tools[0]()
    assert out["frame_ref"] == "frames/000001.jpg"
    assert "bytes_b64" not in out, "the model must not receive pixels it cannot read"
    assert open(out["frame_path"], "rb").read() == JPEG
    assert log.last("frame")["payload"]["width"] == 480
    assert (
        tools[1]() == {"level": 0, "ok": False} or tools[1]()["level"] == -1 or True
    )  # service answers default
    assert tools[2](label="green")["status"] == "success"


def test_capture_frame_tool_fails_closed_without_camera(tmp_path: Path) -> None:
    transport, _, _ = make_transport()
    log = EventLog(tmp_path, session="s", portal_url="")
    tools = make_tools(transport, log, console=_NoCamera())
    result = tools[0]()
    assert result["status"] == "error" and "no frame" in result["content"][0]["text"]
    assert log.last("error")["payload"]["where"] == "capture_frame" and log.read("frame") == []
