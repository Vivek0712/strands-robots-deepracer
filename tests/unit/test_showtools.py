"""showtools: the name memory, the metrics card and the LED blink, all without a car."""

from __future__ import annotations

from pathlib import Path

from deepracer_agent import showtools


def test_remember_and_recall_persist_to_the_memory_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEEPRACER_MEMORY", str(tmp_path / "memory.json"))
    assert showtools.recall()["operator_name"] is None
    assert showtools.remember("my name", "Vivek") == {"ok": True, "key": "operator_name", "value": "Vivek"}
    assert showtools.remember("favourite colour", "green")["key"] == "favourite_colour"
    data = showtools.recall()
    assert data["operator_name"] == "Vivek" and data["facts"] == {"favourite_colour": "green"}
    assert (
        "Vivek" in showtools.memory_prompt_line()
        and "favourite_colour: green" in showtools.memory_prompt_line()
    )
    assert showtools.remember("", "x")["ok"] is False
    showtools.forget_all()
    assert showtools.recall()["operator_name"] is None and showtools.memory_prompt_line() == ""


def test_metrics_from_events_counts_hops_verdicts_and_stops():
    rows = [
        {"type": "motion", "payload": {"state": "start"}},
        {"type": "motion", "payload": {"state": "end"}},
        {"type": "verdict", "payload": {"action": "Proceed", "latency_ms": 400}},
        {
            "type": "verdict",
            "payload": {"action": "Deny", "reason": "person_in_frame (p=0.95)", "latency_ms": 600},
        },
        {"type": "stop", "payload": {"cause": "deny", "latency_ms": 700}},
        {"type": "heartbeat", "payload": {"state": "armed", "gap_ms": 48}},
        {"type": "preflight", "payload": {"battery": 8, "go": True, "camera_fps": 28}},
    ]
    m = showtools.metrics_from_events(rows)
    assert m["hops"] == 1 and m["verdicts"] == 2 and m["denies"] == 1
    assert m["gate_latency_ms_avg"] == 500 and m["gate_latency_ms_max"] == 600
    assert m["stops"] == 1 and m["stop_latency_ms_avg"] == 700 and m["last_stop_cause"] == "deny"
    assert (
        m["deadman"] == "armed" and m["battery"] == 8 and m["camera_fps"] == 28 and m["preflight_go"] is True
    )
    assert m["last_deny_reason"].startswith("person_in_frame")
    assert showtools.metrics_from_events([])["hops"] == 0


def test_blink_led_pulses_then_leaves_the_colour_on(monkeypatch):
    calls: list[str] = []
    import deepracer_agent.tools as tools

    monkeypatch.setattr(
        tools, "set_led", lambda transport, label, log=None: calls.append(label) or {"ok": True}
    )
    monkeypatch.setattr(showtools.time, "sleep", lambda s: None)
    blink = showtools.make_blink_tool(transport=object(), event_log=None)
    out = blink(colour="Green", times=2)
    assert out == {"ok": True, "colour": "green", "times": 2}
    assert calls == ["green", "off", "green", "off", "green"]
    assert blink(colour="purple")["ok"] is False
