"""Event hub for the Pit Wall: one in-memory ring of recent events, one fan-out to every browser.

The hub is the portal's memory of the run. It stamps a sequence number on events that arrive
without one, appends them to the run's ``events.jsonl`` unless the agent's EventLog already wrote
them, remembers the last two hundred for late joiners, tracks which Confirm verdicts still wait for
a human, and pushes every event to every connected WebSocket. Physics stops the car; the decider
explains; the hub only makes sure the explanation reaches the screen.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("portal.hub")

SNAPSHOT_SIZE = 200
Sender = Callable[[dict[str, Any]], Awaitable[None]]


def utc_now_iso() -> str:
    """Current UTC time in the contract's ``ts`` format (milliseconds, trailing Z)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def default_run_dir() -> Path:
    """``DEEPRACER_RUN_DIR`` or ``runs/s-<UTC stamp>`` under the current directory."""
    env = os.environ.get("DEEPRACER_RUN_DIR")
    if env:
        return Path(env).expanduser()
    return Path("runs") / datetime.now(UTC).strftime("s-%Y%m%d-%H%M")


class EventHub:
    """Ring buffer + broadcaster + events.jsonl writer for one portal process."""

    def __init__(self, run_dir: Path | None = None, *, snapshot_size: int = SNAPSHOT_SIZE) -> None:
        self.run_dir = (run_dir or default_run_dir()).resolve()
        self.runs_root = self.run_dir.parent
        self.session = self.run_dir.name
        self.recent: deque[dict[str, Any]] = deque(maxlen=snapshot_size)
        self.latest: dict[str, dict[str, Any]] = {}
        self.pending_approvals: dict[str, dict[str, Any]] = {}
        self.total = 0
        self._seq = 0
        self._clients: dict[int, Sender] = {}
        self._next_client = 0
        self._write_lock = asyncio.Lock()

    # ----- clients ------------------------------------------------------------------------
    def attach(self, sender: Sender) -> int:
        self._next_client += 1
        self._clients[self._next_client] = sender
        return self._next_client

    def detach(self, client_id: int) -> None:
        self._clients.pop(client_id, None)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ----- events -------------------------------------------------------------------------
    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.recent)

    def state(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "run_dir": str(self.run_dir),
            "events": self.total,
            "clients": self.client_count,
            "latest": dict(self.latest),
            "pending_approvals": list(self.pending_approvals.values()),
        }

    async def publish(self, event: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
        """Stamp, remember, optionally persist, and broadcast one validated event."""
        if event.get("seq") is None:
            self._seq += 1
            event["seq"] = self._seq
        else:
            self._seq = max(self._seq, int(event["seq"]))
        event.setdefault("session", self.session)
        self.total += 1
        self.recent.append(event)
        self.latest[event["type"]] = event
        self._track_approvals(event)
        if persist:
            await self._append(event)
        await self._broadcast({"op": "event", "event": event})
        return event

    async def emit(
        self,
        etype: str,
        payload: dict[str, Any],
        *,
        source: str = "portal",
        beat: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Build and publish an event from inside the portal (fake runtime, operator ops)."""
        event = {
            "ts": utc_now_iso(),
            "seq": None,
            "session": self.session,
            "beat": beat,
            "type": etype,
            "source": source,
            "payload": payload,
        }
        return await self.publish(event, persist=persist)

    def _track_approvals(self, event: dict[str, Any]) -> None:
        payload = event.get("payload") or {}
        rid = payload.get("request_id")
        if not rid:
            return
        if event["type"] == "verdict" and payload.get("action") == "Confirm":
            self.pending_approvals[rid] = {
                "request_id": rid,
                "reason": payload.get("reason"),
                "stage": payload.get("stage"),
                "ts": event["ts"],
            }
        elif event["type"] in {"approval", "stop"}:
            self.pending_approvals.pop(rid, None)

    async def _append(self, event: dict[str, Any]) -> None:
        session = str(event.get("session") or self.session)
        path = self.runs_root / session / "events.jsonl"
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        async with self._write_lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:  # the screen must keep working even if the disk does not
                log.warning("could not append to %s: %s", path, exc)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            return
        dead: list[int] = []
        for cid, send in list(self._clients.items()):
            try:
                await send(message)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.detach(cid)

    def frame_path(self, session: str, name: str) -> Path | None:
        """Resolve ``runs/<session>/frames/<name>`` safely, or None if the request escapes the run dir."""
        if not session or not name or "/" in session or "/" in name or ".." in session or ".." in name:
            return None
        candidate = (self.runs_root / session / "frames" / name).resolve()
        with contextlib.suppress(ValueError):
            candidate.relative_to(self.runs_root.resolve())
            return candidate
        return None
