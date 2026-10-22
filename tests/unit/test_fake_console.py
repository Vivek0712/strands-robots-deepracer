"""The fake console behaves like the real one: CSRF login, cookie-gated API, MJPEG at 15 fps."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from harness.fake_car import CALIBRATION_PROFILES
from harness.fake_console import BOUNDARY, PWM_OFFSET, PWM_THROTTLE_CONVERSION, FakeConsole
from harness.frames import LABELS, load

CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')


def login(client: httpx.Client, password: str = "anything") -> httpx.Response:
    csrf = CSRF_RE.search(client.get("/login").text).group(1)
    return client.post("/login", data={"password": password}, headers={"X-CSRFToken": csrf})


def jpeg_frames(resp: httpx.Response, want: int) -> list[bytes]:
    """The reference parser from report 07: scan for SOI FFD8 / EOI FFD9."""
    frames: list[bytes] = []
    buf = b""
    for chunk in resp.iter_bytes():
        buf += chunk
        while True:
            i = buf.find(b"\xff\xd8")
            j = buf.find(b"\xff\xd9", i + 2) if i >= 0 else -1
            if i < 0 or j < 0:
                break
            frames.append(buf[i : j + 2])
            buf = buf[j + 2 :]
        if len(frames) >= want:
            break
    return frames


@pytest.fixture
def client(fake_console: FakeConsole) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=fake_console.url, timeout=5) as c:
        yield c


def test_login_page_carries_csrf_meta(client: httpx.Client, fake_console: FakeConsole) -> None:
    html = client.get("/login").text
    assert CSRF_RE.search(html).group(1) == fake_console.csrf_token
    assert client.get("/").status_code == 200


def test_api_requires_cookie(client: httpx.Client) -> None:
    assert client.get("/api/get_battery_level").status_code == 401
    assert client.get("/route", params={"topic": "/camera_pkg/display_mjpeg"}).status_code == 401


def test_login_without_csrf_is_refused(client: httpx.Client) -> None:
    assert client.post("/login", data={"password": "x"}).status_code == 400


def test_login_sets_cookie_and_redirect(client: httpx.Client) -> None:
    r = login(client)
    assert r.status_code == 200 and r.json() == {"redirect": "/home"}
    assert "deepracer_token" in client.cookies
    assert client.get("/api/get_battery_level").status_code == 200


def test_wrong_password_is_http_200_failure(
    client: httpx.Client, fake_console: FakeConsole, monkeypatch: Any
) -> None:
    monkeypatch.setattr(fake_console, "password", "sticker")
    r = login(client, "wrong")
    assert r.status_code == 200 and r.text == "failure"
    assert "deepracer_token" not in client.cookies
    assert login(client, "sticker").json() == {"redirect": "/home"}


def test_api_shapes_match_report_02(client: httpx.Client) -> None:
    login(client)
    assert client.get("/api/get_battery_level").json() == {"battery_level": 10, "success": True}
    sensors = client.get("/api/get_sensor_status").json()
    assert set(sensors) == {"camera_status", "stereo_status", "lidar_status", "success"}
    assert sensors["lidar_status"] == "not_connected"
    info = client.get("/api/get_device_info").json()
    assert set(info) == {"hardware_version", "software_version", "success"}


def test_calibration_in_ui_units(client: httpx.Client, fake_console: FakeConsole) -> None:
    login(client)
    fake_console.shared.set(calibration="uninitialised")
    cal = client.get("/api/get_calibration/throttle").json()
    assert set(cal) == {"mid", "min", "max", "polarity", "success"}
    motor = CALIBRATION_PROFILES["uninitialised"][1]
    assert cal["mid"] == int((motor["mid"] - PWM_OFFSET) / PWM_THROTTLE_CONVERSION)
    assert cal["polarity"] == -1
    # polarity -1: min/max swapped relative to the PWM order
    assert cal["min"] == int((motor["max"] - PWM_OFFSET) / PWM_THROTTLE_CONVERSION)
    assert client.get("/api/get_calibration/angle").json()["polarity"] == 1
    assert client.get("/api/get_calibration/yaw").status_code == 404


def test_battery_follows_shared_state(client: httpx.Client, fake_console: FakeConsole) -> None:
    login(client)
    fake_console.shared.set(battery=-1)
    assert client.get("/api/get_battery_level").json()["battery_level"] == -1


def test_mjpeg_stream_15fps_with_soi_eoi(client: httpx.Client) -> None:
    login(client)
    t0 = time.monotonic()
    with client.stream(
        "GET", "/route", params={"topic": "/camera_pkg/display_mjpeg", "width": 480, "height": 360}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"] == f"multipart/x-mixed-replace;boundary={BOUNDARY}"
        frames = jpeg_frames(resp, 6)
    elapsed = time.monotonic() - t0
    assert len(frames) == 6
    assert all(f.startswith(b"\xff\xd8") and f.endswith(b"\xff\xd9") for f in frames)
    assert frames[0] == load("clear")
    assert 0.25 < elapsed < 1.5  # six frames at ~15 fps


def test_stream_follows_label_and_size(client: httpx.Client, fake_console: FakeConsole) -> None:
    login(client)
    fake_console.shared.set(label="person_in_frame")
    with client.stream(
        "GET", "/route", params={"topic": "/camera_pkg/display_mjpeg", "width": 240, "height": 180}
    ) as r:
        frame = jpeg_frames(r, 1)[0]
    from io import BytesIO

    from PIL import Image

    assert Image.open(BytesIO(frame)).size == (240, 180)
    assert client.get("/control/frame").content == load("person_in_frame")


def test_unknown_topic_is_404(client: httpx.Client) -> None:
    login(client)
    assert client.get("/route", params={"topic": "/video_mjpeg"}).status_code == 404


@pytest.mark.parametrize("label", LABELS)
def test_control_accepts_every_label(client: httpx.Client, label: str) -> None:
    assert client.get("/control", params={"label": label}).json()["label"] == label


def test_control_rejects_unknown_label(client: httpx.Client) -> None:
    assert client.get("/control", params={"label": "cat"}).status_code == 400
