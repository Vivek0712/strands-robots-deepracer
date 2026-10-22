"""The one screen contract: every observable thing becomes one line in events.jsonl.

Each component that does something observable (a command, a motion, a verdict, a
stop, a frame, a heartbeat) appends one JSON object per line to the run directory
and, when the Pit Wall portal is reachable, posts the same object to it so the
booth screen updates live. The log never raises and never blocks the car: a dead
portal costs half a second at most, in a background thread. Frames of people stay
in the run directory and never leave the laptop.

Schema: ``docs/dev/CONTRACTS.md`` section 4. Physics stops the car; the decider
explains; this file is how the explanation reaches the screen.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Every ``type`` CONTRACTS section 4 defines. An unknown type is recorded as an
#: ``error`` event naming the offender, so a typo never silently splits the log.
EVENT_TYPES = frozenset(
    {
        "thought",
        "command",
        "verdict",
        "approval",
        "motion",
        "stop",
        "heartbeat",
        "preflight",
        "frame",
        "voice",
        "led",
        "body",
        "error",
    }
)

PORTAL_TIMEOUT_S = 0.5
_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"


def one_line(text: str, limit: int = 600) -> str:
    """Collapse whitespace so a ``thought`` is one line on the screen; long ones end in an ellipsis."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


def utc_now_iso() -> str:
    """UTC timestamp with millisecond precision and a ``Z`` suffix."""
    now = _dt.datetime.now(_dt.UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def new_session_id(now: _dt.datetime | None = None) -> str:
    """``s-YYYYMMDD-HHMM`` as CONTRACTS section 4 spells it."""
    now = now or _dt.datetime.now(_dt.UTC)
    return now.strftime("s-%Y%m%d-%H%M")


def default_run_dir(session: str) -> Path:
    """``$DEEPRACER_RUN_DIR`` when set, else ``runs/<session>/`` under the repo."""
    env = os.environ.get("DEEPRACER_RUN_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "runs" / session


def _post_with_httpx(url: str, body: dict[str, Any]) -> None:
    import httpx

    httpx.post(url, json=body, timeout=PORTAL_TIMEOUT_S, headers={"X-Deepracer-Source": "eventlog"})


class EventLog:
    """Append-only JSONL event log with a fire-and-forget mirror to the portal.

    Args:
        run_dir: Directory holding ``events.jsonl`` and ``frames/``. Created on
            first write. Defaults to :func:`default_run_dir`.
        session: Session id stamped on every event. Defaults to a fresh
            :func:`new_session_id`.
        portal_url: Base URL of the Pit Wall portal; ``None`` reads
            ``$PORTAL_URL`` and an empty value disables the mirror.
        beat: Current beat name (``marshal``, ``blindfold`` ...), mutable.
        source: Default ``source`` field (``agent``, ``driver``, ``deadman`` ...).
        poster: Replacement for the HTTP POST, used by tests. Receives the URL
            and the event dict; any exception it raises is swallowed.
    """

    def __init__(
        self,
        run_dir: str | Path | None = None,
        *,
        session: str | None = None,
        portal_url: str | None = None,
        beat: str | None = None,
        source: str = "agent",
        poster: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.session = session or new_session_id()
        self.run_dir = Path(run_dir) if run_dir is not None else default_run_dir(self.session)
        self.portal_url = (os.environ.get("PORTAL_URL", "") if portal_url is None else portal_url).rstrip("/")
        self.beat = beat
        self.source = source
        self._poster = poster or _post_with_httpx
        self._seq = 0
        self._frame_seq = 0
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._resume_counters()

    def _resume_counters(self) -> None:
        """Continue ``seq`` and the frame counter from an existing run dir.

        Several processes (the beats runner, the portal, the voice CLI) may append to one
        ``events.jsonl``; restarting ``seq`` at 1 would make "events after seq N" ambiguous.
        """
        try:
            if self.path.exists():
                last = 0
                with self.path.open("rb") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if raw:
                            try:
                                last = max(last, int(json.loads(raw).get("seq", 0)))
                            except (ValueError, AttributeError):
                                continue
                self._seq = last
            if self.frames_dir.exists():
                names = sorted(p.stem for p in self.frames_dir.glob("*.jpg") if p.stem.isdigit())
                self._frame_seq = int(names[-1]) if names else 0
        except OSError:
            pass

    # -- paths ---------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self.run_dir / "events.jsonl"

    @property
    def frames_dir(self) -> Path:
        return self.run_dir / "frames"

    # -- writing -------------------------------------------------------------

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        beat: str | None = None,
    ) -> dict[str, Any]:
        """Append one event and mirror it to the portal. Never raises.

        Returns the event as written, so a caller can hand its ``seq`` on.
        """
        if type not in EVENT_TYPES:
            payload = {"where": "events", "message": f"unknown event type {type!r}", "payload": payload}
            type = "error"
        if not isinstance(payload, dict):
            payload = {"where": "events", "message": f"payload must be a dict, got {type_name(payload)}"}
            type = "error"
        with self._lock:
            self._seq += 1
            event = {
                "ts": utc_now_iso(),
                "seq": self._seq,
                "session": self.session,
                "beat": beat if beat is not None else self.beat,
                "type": type,
                "source": source or self.source,
                "payload": payload,
            }
            line = json.dumps(event, default=str, separators=(",", ":"))
            try:
                self.run_dir.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:  # a full disk must not stop the car's stop
                logger.warning("event log write failed: %s", exc)
        self._mirror(event)
        return event

    def _mirror(self, event: dict[str, Any]) -> None:
        if not self.portal_url:
            return
        url = f"{self.portal_url}/api/events"

        def _send() -> None:
            try:
                self._poster(url, event)
            except Exception as exc:
                logger.debug("portal mirror failed: %s", exc)

        thread = threading.Thread(target=_send, name="event-mirror", daemon=True)
        thread.start()
        self._threads = [t for t in self._threads if t.is_alive()] + [thread]

    def flush(self, timeout: float = PORTAL_TIMEOUT_S) -> None:
        """Wait briefly for in-flight portal posts (tests and clean shutdown)."""
        for thread in list(self._threads):
            thread.join(timeout)

    # -- frames --------------------------------------------------------------

    def save_frame(
        self,
        jpeg: bytes,
        *,
        width: int | None = None,
        height: int | None = None,
        emit: bool = True,
    ) -> str | None:
        """Write one JPEG under ``frames/`` and emit a ``frame`` event.

        Returns the ``frame_ref`` relative to the run dir, or ``None`` when the
        bytes are not a JPEG (no SOI/EOI), which is recorded as an ``error``.
        """
        if not isinstance(jpeg, bytes | bytearray) or len(jpeg) < 4:
            self.emit("error", {"where": "events.save_frame", "message": "frame is empty or not bytes"})
            return None
        if not jpeg.startswith(_JPEG_SOI) or not jpeg.rstrip(b"\x00").endswith(_JPEG_EOI):
            self.emit(
                "error", {"where": "events.save_frame", "message": "frame is not a JPEG (SOI/EOI missing)"}
            )
            return None
        with self._lock:
            self._frame_seq += 1
            name = f"{self._frame_seq:06d}.jpg"
        ref = f"frames/{name}"
        try:
            self.frames_dir.mkdir(parents=True, exist_ok=True)
            (self.frames_dir / name).write_bytes(bytes(jpeg))
        except OSError as exc:
            self.emit("error", {"where": "events.save_frame", "message": f"could not write frame: {exc}"})
            return None
        if width is None or height is None:
            dims = jpeg_dimensions(bytes(jpeg))
            if dims:
                width, height = dims
        if emit:
            self.emit("frame", {"frame_ref": ref, "width": width, "height": height})
        return ref

    # -- reading -------------------------------------------------------------

    def read(self, type: str | None = None) -> list[dict[str, Any]]:
        """Every event written so far (optionally one type), oldest first."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if type is None or event.get("type") == type:
                    out.append(event)
        return out

    def last(self, type: str) -> dict[str, Any] | None:
        events = self.read(type)
        return events[-1] if events else None


def type_name(value: Any) -> str:
    return type(value).__name__


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read ``(width, height)`` from a JPEG's SOF marker without decoding it."""
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            return None
        length = (data[i + 2] << 8) | data[i + 3]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 9 > n:
                return None
            height = (data[i + 5] << 8) | data[i + 6]
            width = (data[i + 7] << 8) | data[i + 8]
            return (width, height)
        i += 2 + length
    return None


__all__ = [
    "EVENT_TYPES",
    "PORTAL_TIMEOUT_S",
    "EventLog",
    "default_run_dir",
    "jpeg_dimensions",
    "new_session_id",
    "utc_now_iso",
]
