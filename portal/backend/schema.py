"""Event validation for the Pit Wall: accept what CONTRACTS section 4 describes, refuse the rest with a reason

Every event is one JSON object with ``ts`` (ISO 8601), ``type`` (one of the fourteen contract types)
and a ``payload`` object. The portal never guesses what a malformed event meant; it answers 422 with
a one-line reason so the sender can fix it. Physics stops the car; the decider explains.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

EVENT_TYPES: frozenset[str] = frozenset(
    {
        "thought",
        "connect",
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

MAX_PAYLOAD_BYTES = 256 * 1024


def parse_ts(value: Any) -> datetime | None:
    """Return the datetime for an ISO 8601 string with a zone, or None if it is not one."""
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def validate_event(obj: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(event, None)`` for a well-formed event or ``(None, reason)`` for a refused one.

    The returned event is a shallow copy with ``payload`` defaulted to ``{}`` and ``beat`` and
    ``source`` defaulted to ``None`` / ``"unknown"``. ``seq`` and ``session`` are left for the hub.
    """
    if not isinstance(obj, dict):
        return None, "event must be a JSON object"
    if "type" not in obj:
        return None, "missing type"
    etype = obj["type"]
    if not isinstance(etype, str) or etype not in EVENT_TYPES:
        return None, f"unknown type {etype!r}; expected one of {sorted(EVENT_TYPES)}"
    if "ts" not in obj:
        return None, "missing ts"
    if parse_ts(obj["ts"]) is None:
        return None, f"bad ts {obj['ts']!r}; expected ISO 8601 with a zone, e.g. 2026-10-14T06:52:01.123Z"
    payload = obj.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return None, "payload must be an object"
    seq = obj.get("seq")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int) or seq < 0):
        return None, "seq must be a non-negative integer"
    session = obj.get("session")
    if session is not None and (
        not isinstance(session, str) or not session or "/" in session or ".." in session
    ):
        return None, "session must be a non-empty string without path separators"
    beat = obj.get("beat")
    if beat is not None and not isinstance(beat, str):
        return None, "beat must be a string or null"
    source = obj.get("source", "unknown")
    if not isinstance(source, str):
        return None, "source must be a string"
    event = dict(obj)
    event["payload"] = payload
    event["beat"] = beat
    event["source"] = source
    return event, None
