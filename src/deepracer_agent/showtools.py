"""Tools for the interactive show: a memory for names, a metrics card, an LED blink.

Three things the speaker asks the rover on stage that the driving tools do not cover: "remember
my name" (and use it afterwards), "tell me your metrics" (battery, link, stop latencies, hops,
verdicts, from the audit log and the pre-flight), and "blink green if you are listening". None
of these can move the car. Memory lives in one JSON file (``DEEPRACER_MEMORY`` or
``~/.config/deepracer/memory.json``) so it survives a restart and travels with the laptop; the
name goes into the system prompt when the agent is built and into every ``recall`` answer.
Physics stops the car; the decider explains; these tools only talk.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from strands import tool

logger = logging.getLogger(__name__)

MEMORY_ENV = "DEEPRACER_MEMORY"
DEFAULT_MEMORY = "~/.config/deepracer/memory.json"
_lock = threading.Lock()


def memory_path() -> Path:
    return Path(os.path.expanduser(os.environ.get(MEMORY_ENV) or DEFAULT_MEMORY))


def load_memory() -> dict[str, Any]:
    p = memory_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_memory(data: dict[str, Any]) -> None:
    p = memory_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def remembered_name() -> str | None:
    name = load_memory().get("operator_name")
    return str(name) if name else None


def memory_prompt_line() -> str:
    """One sentence for the system prompt; empty when nothing is remembered."""
    name = remembered_name()
    facts = load_memory().get("facts") or {}
    parts = []
    if name:
        parts.append(f"The person talking to you is {name}; use their name naturally, not in every sentence.")
    if isinstance(facts, dict) and facts:
        listed = "; ".join(f"{k}: {v}" for k, v in list(facts.items())[:8])
        parts.append(f"Things you were asked to remember: {listed}.")
    return " ".join(parts)


@tool(
    name="remember",
    description="Remember something for later conversations: the operator's name (key 'operator_name') "
    "or any short fact. Saved on the laptop, survives restarts. Never stores commands.",
)
def remember(key: str, value: str) -> dict[str, Any]:
    key = str(key).strip().lower().replace(" ", "_")[:40]
    value = str(value).strip()[:200]
    if not key or not value:
        return {"ok": False, "reason": "key and value are required"}
    with _lock:
        data = load_memory()
        if key in ("operator_name", "name", "my_name"):
            data["operator_name"] = value
            key = "operator_name"
        else:
            facts = data.setdefault("facts", {})
            if not isinstance(facts, dict):
                facts = data["facts"] = {}
            facts[key] = value
        data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_memory(data)
    return {"ok": True, "key": key, "value": value}


@tool(
    name="recall",
    description="What you remember: the operator's name and the facts you were asked to keep.",
)
def recall() -> dict[str, Any]:
    data = load_memory()
    return {
        "operator_name": data.get("operator_name"),
        "facts": data.get("facts") or {},
        "updated": data.get("updated"),
    }


def forget_all() -> None:
    with _lock:
        save_memory({})


# -- metrics ------------------------------------------------------------------------------------


def metrics_from_events(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Numbers an audience can hear: counts and latencies from CONTRACTS section 4 events."""
    motions = [r.get("payload") or {} for r in rows if r.get("type") == "motion"]
    hops = sum(1 for m in motions if m.get("state") == "start")
    verdicts = [r.get("payload") or {} for r in rows if r.get("type") == "verdict"]
    stops = [r.get("payload") or {} for r in rows if r.get("type") == "stop"]
    denies = [v for v in verdicts if v.get("action") == "Deny"]
    lat = [int(v.get("latency_ms") or 0) for v in verdicts if v.get("latency_ms")]
    stop_lat = [int(s.get("latency_ms") or 0) for s in stops if s.get("latency_ms")]
    hb = next((r.get("payload") or {} for r in reversed(rows) if r.get("type") == "heartbeat"), {})
    pre = next((r.get("payload") or {} for r in reversed(rows) if r.get("type") == "preflight"), {})
    last_stop = stops[-1] if stops else None
    return {
        "hops": hops,
        "verdicts": len(verdicts),
        "denies": len(denies),
        "last_deny_reason": denies[-1].get("reason") if denies else None,
        "gate_latency_ms_avg": round(sum(lat) / len(lat)) if lat else None,
        "gate_latency_ms_max": max(lat) if lat else None,
        "stops": len(stops),
        "stop_latency_ms_avg": round(sum(stop_lat) / len(stop_lat)) if stop_lat else None,
        "last_stop_cause": last_stop.get("cause") if last_stop else None,
        "deadman": hb.get("state"),
        "heartbeat_gap_ms": hb.get("gap_ms"),
        "battery": pre.get("battery"),
        "camera_fps": pre.get("camera_fps") or pre.get("fps"),
        "preflight_go": pre.get("go"),
    }


def make_metrics_tool(event_log: Any, runtime: Any | None = None) -> Any:
    """``metrics`` bound to one event log (and, when given, the runtime's live status)."""

    @tool(
        name="metrics",
        description="Your own numbers for this session: hops driven, gate verdicts and their latency, "
        "stops and stop latency, deadman state, battery, camera fps. Say them in one or two sentences.",
    )
    def metrics() -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        reader = getattr(event_log, "read", None)
        try:
            if callable(reader):
                rows = list(reader())
            else:
                path = getattr(event_log, "path", None)
                if path is not None and Path(path).is_file():
                    for line in Path(path).read_text(encoding="utf-8").splitlines():
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            continue
        except Exception as exc:
            logger.debug("metrics read failed: %s", exc)
        out = metrics_from_events(rows)
        if runtime is not None:
            try:
                status = runtime.status()
                out["armed"] = status.get("armed")
                out["deadman"] = out["deadman"] or status.get("deadman")
                out["battery"] = out["battery"] if out["battery"] is not None else status.get("battery")
            except Exception as exc:
                logger.debug("metrics status failed: %s", exc)
        out["safety"] = "Physics stops the car; the decider explains."
        return out

    return metrics


# -- LED blink ----------------------------------------------------------------------------------


def make_blink_tool(transport: Any, event_log: Any) -> Any:
    """``blink_led``: a colour pulsed a few times on the tail light, then left on. Never blocks a stop."""
    from deepracer_agent.tools import LED_LABELS, set_led

    @tool(
        name="blink_led",
        description="Blink the tail LED in a colour (green, red, amber, blue, off) a few times, then leave "
        "it on, for example green when asked whether you are listening. Does not move the car.",
    )
    def blink_led(colour: str = "green", times: int = 3) -> dict[str, Any]:
        label = str(colour).strip().lower()
        if label not in LED_LABELS:
            return {"ok": False, "reason": f"unknown colour {label!r}; choose one of {', '.join(LED_LABELS)}"}
        n = max(1, min(int(times), 6))
        for _ in range(n):
            set_led(transport, label, event_log)
            time.sleep(0.18)
            set_led(transport, "off", event_log)
            time.sleep(0.14)
        set_led(transport, label, event_log)
        return {"ok": True, "colour": label, "times": n}

    return blink_led


__all__ = [
    "forget_all",
    "load_memory",
    "make_blink_tool",
    "make_metrics_tool",
    "memory_path",
    "memory_prompt_line",
    "metrics_from_events",
    "recall",
    "remember",
    "remembered_name",
    "save_memory",
]
