"""One camera stream per process: a background reader that always holds the newest frame.

The earlier repo's phase 3 (report 07, ``camera_stream.py``) kept a single MJPEG connection open in a
daemon thread, reconnected two seconds after any error, and let every consumer read the latest JPEG
in under a millisecond. This project first absorbed only its SOI/EOI parser and opened a fresh
stream per grab (gate, ``capture_frame``, ``look``, the portal proxy, the kiosk). Over a 300 ms
link with the console behind an SSH tunnel those competing opens starved each other
(2026-10-17: every grab timed out while the car was fine). This is the phase 3 design on today's
``ConsoleClient``: one stream, one buffer, every reader served from it; the portal re-multiplexes
it to any number of browsers. A frame older than ``stale_after_s`` is not a frame: ``latest`` then
returns ``None`` and the gate fails closed as before. Physics stops the car; the decider explains;
this is only how it looks.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from deepracer_agent.tools import ConsoleClient, iter_jpeg_frames

logger = logging.getLogger(__name__)

ChunkSource = Callable[[], Iterable[bytes]]


class CameraStream:
    """Background MJPEG reader with a latest-frame buffer and a reconnect loop.

    Args:
        console: The logged-in (or log-in-able) :class:`ConsoleClient`; its ``stream_chunks`` is the
            default chunk source.
        source: Test hook: a callable returning an iterable of raw bytes instead of the console.
        reconnect_delay_s: Pause before reopening the stream after an error or a clean end.
        stale_after_s: ``latest()`` returns ``None`` when the newest frame is older than this.
    """

    def __init__(
        self,
        console: ConsoleClient | None = None,
        *,
        source: ChunkSource | None = None,
        reconnect_delay_s: float = 2.0,
        stale_after_s: float = 2.0,
        stream_timeout_s: float = 3600.0,
    ) -> None:
        self.console = console
        self._source = source
        self.reconnect_delay_s = float(reconnect_delay_s)
        self.max_reconnect_delay_s = max(float(reconnect_delay_s), 15.0)
        self.stale_after_s = float(stale_after_s)
        self.stream_timeout_s = float(stream_timeout_s)
        self._cond = threading.Condition()
        self._latest: bytes | None = None
        self._latest_at: float = 0.0
        self._seq = 0
        self.frames = 0
        self.reconnects = 0
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._window: list[float] = []  # frame times for fps over the last ~2 s

    # -- lifecycle -------------------------------------------------------------------------------

    def start(self, wait_first_s: float = 0.0) -> bool:
        """Start the reader thread (idempotent). With ``wait_first_s`` block until a frame or timeout."""
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="camera-stream", daemon=True)
            self._thread.start()
        if wait_first_s > 0:
            return self.wait_for_frame(wait_first_s) is not None
        return True

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3.0)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    # -- reading ---------------------------------------------------------------------------------

    def latest(self, max_age_s: float | None = None) -> bytes | None:
        """The newest JPEG, or ``None`` when there is none or it is older than ``max_age_s``."""
        limit = self.stale_after_s if max_age_s is None else float(max_age_s)
        with self._cond:
            if self._latest is None:
                return None
            if limit > 0 and time.monotonic() - self._latest_at > limit:
                return None
            return self._latest

    def wait_for_frame(self, timeout_s: float, *, after_seq: int | None = None) -> bytes | None:
        """Block until a frame newer than ``after_seq`` (default: any frame) arrives, or time out."""
        deadline = time.monotonic() + timeout_s
        with self._cond:
            while True:
                if self._latest is not None and (after_seq is None or self._seq > after_seq):
                    return self._latest
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._stop.is_set():
                    return None
                self._cond.wait(remaining)

    def frames_iter(self, *, max_fps: float = 15.0, timeout_s: float = 5.0) -> Iterator[bytes]:
        """Yield each new frame as it lands (at most ``max_fps``); stops after ``timeout_s`` without one."""
        min_gap = 1.0 / max_fps if max_fps > 0 else 0.0
        seq = -1
        last = 0.0
        while not self._stop.is_set():
            with self._cond:
                current = self._seq
            frame = self.wait_for_frame(timeout_s, after_seq=seq if seq >= 0 else current - 1)
            if frame is None:
                return
            with self._cond:
                seq = self._seq
            gap = time.monotonic() - last
            if gap < min_gap:
                time.sleep(min_gap - gap)
            last = time.monotonic()
            yield frame

    def info(self) -> dict[str, Any]:
        with self._cond:
            age = (time.monotonic() - self._latest_at) if self._latest is not None else None
            now = time.monotonic()
            recent = [t for t in self._window if now - t <= 2.0]
            fps = round(len(recent) / 2.0, 1) if recent else 0.0
        return {
            "running": self.running,
            "frames": self.frames,
            "fps": fps,
            "age_s": None if age is None else round(age, 3),
            "stale": age is None or age > self.stale_after_s,
            "reconnects": self.reconnects,
            "error": self.error,
        }

    def fps(self) -> float | None:
        value = self.info()["fps"]
        return value or None

    # -- the reader thread -----------------------------------------------------------------------

    def _chunks(self) -> Iterable[bytes]:
        if self._source is not None:
            return self._source()
        if self.console is None:
            raise RuntimeError("CameraStream needs a console or a source")
        if not self.console.logged_in and not self.console.login():
            raise RuntimeError("console login failed")
        return self.console.stream_chunks(self.stream_timeout_s)

    def _loop(self) -> None:
        first = True
        delay = self.reconnect_delay_s
        while not self._stop.is_set():
            if not first:
                self.reconnects += 1
                # Back off while the console is away: every reopen adds and removes a stream on the
                # car's web_video_server, which segfaults under that churn (2026-10-17).
                self._stop.wait(delay)
                delay = min(delay * 2.0, self.max_reconnect_delay_s)
                if self._stop.is_set():
                    break
            first = False
            try:
                for jpeg in iter_jpeg_frames(self._chunks()):
                    self._publish(jpeg)
                    delay = self.reconnect_delay_s  # a frame arrived: the next retry is quick again
                    if self._stop.is_set():
                        break
                self.error = None if self._stop.is_set() else "stream ended"
            except Exception as exc:  # any failure: note it, wait, reopen
                self.error = f"{type(exc).__name__}: {exc}"[:200]
                logger.info("camera stream error: %s", self.error)

    def _publish(self, jpeg: bytes) -> None:
        now = time.monotonic()
        with self._cond:
            self._latest = jpeg
            self._latest_at = now
            self._seq += 1
            self.frames += 1
            self._window.append(now)
            if len(self._window) > 200:
                del self._window[:-200]
            self.error = None
            self._cond.notify_all()


__all__ = ["CameraStream"]
