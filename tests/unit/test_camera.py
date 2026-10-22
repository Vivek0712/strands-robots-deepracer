"""camera: one stream per process with a latest-frame buffer (phase 3's design on this console)."""

from __future__ import annotations

import threading
import time

from deepracer_agent.camera import CameraStream
from deepracer_agent.tools import ConsoleClient

JPEG_A = b"\xff\xd8" + b"A" * 20 + b"\xff\xd9"
JPEG_B = b"\xff\xd8" + b"B" * 20 + b"\xff\xd9"


def _source_of(frames: list[bytes], gap_s: float = 0.01, end: threading.Event | None = None):
    def source():
        for f in frames:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + f[:5]
            yield f[5:] + b"\r\n"
            time.sleep(gap_s)
        if end is not None:
            end.wait(2.0)

    return source


def test_latest_frame_arrives_and_goes_stale():
    end = threading.Event()
    cam = CameraStream(
        source=_source_of([JPEG_A, JPEG_B], end=end), stale_after_s=0.3, reconnect_delay_s=0.05
    )
    assert cam.start(wait_first_s=2.0)
    assert cam.wait_for_frame(1.0, after_seq=1) == JPEG_B
    assert cam.latest() == JPEG_B and cam.frames == 2
    info = cam.info()
    assert info["running"] and info["frames"] == 2 and info["stale"] is False
    time.sleep(0.4)
    assert cam.latest() is None  # too old to drive on
    assert cam.latest(max_age_s=0) == JPEG_B  # unless the caller says any age
    end.set()
    cam.stop()
    assert not cam.running


def test_stream_reconnects_after_an_error_and_counts_it():
    calls = {"n": 0}

    def source():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("link dropped")
        yield JPEG_A

    cam = CameraStream(source=source, reconnect_delay_s=0.05)
    cam.start()
    assert cam.wait_for_frame(2.0) == JPEG_A
    assert cam.reconnects >= 1 and calls["n"] >= 2
    cam.stop()


def test_frames_iter_yields_new_frames_only_and_stops_when_quiet():
    end = threading.Event()
    cam = CameraStream(
        source=_source_of([JPEG_A, JPEG_B, JPEG_A], gap_s=0.05, end=end), reconnect_delay_s=5.0
    )
    cam.start(wait_first_s=1.0)
    got = []
    for f in cam.frames_iter(max_fps=100.0, timeout_s=0.5):
        got.append(f)
    assert 1 <= len(got) <= 3 and got[-1] == JPEG_A
    end.set()
    cam.stop()


def test_console_client_serves_grabs_from_an_attached_stream():
    class Stream:
        running = True

        def __init__(self):
            self.waited = 0

        def latest(self):
            return JPEG_B

        def wait_for_frame(self, timeout):
            self.waited += 1
            return JPEG_A

        def fps(self):
            return 19.5

    c = ConsoleClient("http://127.0.0.1:9", password="x")
    s = Stream()
    c.attach_stream(s)
    assert c.capture_frame() == JPEG_B and s.waited == 0  # no login, no HTTP: the buffer answers
    assert c.frame_rate() == 19.5
    s.running = False
    assert c.capture_frame(timeout=0.2) is None  # back to the one-shot grab, which cannot reach port 9
