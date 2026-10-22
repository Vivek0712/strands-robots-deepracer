"""why_stopped(): the Apology, read back from events.jsonl for every stop cause."""

from __future__ import annotations

import json

import pytest

from deepracer_agent.gate import LocalEventLog
from deepracer_agent.look import configure_look, explain_stop, read_events, reset_look, why_stopped


def _ev(seq, type, payload, ts="2026-10-14T06:52:01.123Z"):
    return {
        "ts": ts,
        "seq": seq,
        "session": "s",
        "beat": "marshal",
        "type": type,
        "source": "agent",
        "payload": payload,
    }


DENY_RUN = [
    _ev(
        1,
        "command",
        {
            "tool": "drive_deepracer",
            "args": {"linear": 0.3, "angular": 0, "duration": 0.5},
            "request_id": "r1",
        },
    ),
    _ev(2, "frame", {"frame_ref": "frames/000010.jpg", "width": 480, "height": 360}),
    _ev(
        3,
        "verdict",
        {
            "request_id": "r1",
            "stage": "envelope",
            "action": "Proceed",
            "reason": "inside envelope (p=0.93)",
            "class": None,
            "probability": 0.93,
            "latency_ms": 140,
            "frame_ref": "frames/000010.jpg",
        },
    ),
    _ev(
        4,
        "verdict",
        {
            "request_id": "r1",
            "stage": "frame",
            "action": "Deny",
            "reason": "person_in_frame (p=0.97): stopping",
            "class": "person_in_frame",
            "probability": 0.97,
            "latency_ms": 180,
            "frame_ref": "frames/000010.jpg",
        },
    ),
    _ev(5, "stop", {"request_id": "r1", "cause": "deny", "latency_ms": 320}, ts="2026-10-14T06:52:01.500Z"),
]


@pytest.fixture(autouse=True)
def _reset():
    reset_look()
    yield
    reset_look()


def test_deny_explanation_names_class_probability_and_frame():
    out = explain_stop(DENY_RUN)
    assert out["cause"] == "deny" and out["request_id"] == "r1"
    assert out["frame_ref"] == "frames/000010.jpg"
    assert "person in frame" in out["text"] and "97 percent" in out["text"]
    assert "2026-10-14T06:52:01.500Z" in out["text"]
    assert "decider" in out["text"].lower()


def test_vision_unavailable_explanation():
    events = [
        _ev(
            1,
            "verdict",
            {
                "request_id": "r2",
                "stage": "frame",
                "action": "Deny",
                "reason": "vision unavailable",
                "class": None,
                "probability": None,
                "latency_ms": 0,
                "frame_ref": None,
            },
        ),
        _ev(2, "stop", {"request_id": "r2", "cause": "deny", "latency_ms": None}),
    ]
    out = explain_stop(events)
    assert "lost my eyes" in out["text"] and out["frame_ref"] is None


def test_barge_in_explanation_quotes_latency():
    events = [
        *DENY_RUN,
        _ev(6, "voice", {"event": "barge_in", "text": None, "t_ms": 1760000000000}),
        _ev(
            7,
            "stop",
            {"request_id": None, "cause": "barge_in", "latency_ms": 212},
            ts="2026-10-14T06:53:00.000Z",
        ),
    ]
    out = explain_stop(events)
    assert out["cause"] == "barge_in"
    assert "212 milliseconds" in out["text"] and "spoke over me" in out["text"]
    assert "person in frame" in out["text"], "the last judged frame is still mentioned"


def test_deadman_explanation_uses_gap_and_credits_the_car():
    events = [
        _ev(
            1,
            "motion",
            {
                "request_id": "r3",
                "state": "start",
                "angle": 0,
                "throttle": 0.3,
                "duration_s": 0.5,
                "messages": 10,
            },
        ),
        _ev(2, "heartbeat", {"state": "tripped", "gap_ms": 412}),
        _ev(3, "stop", {"request_id": "r3", "cause": "deadman", "latency_ms": None}),
    ]
    out = explain_stop(events)
    assert (
        "412 millisecond" in out["text"] and "deadman" in out["text"] and "did not stop myself" in out["text"]
    )


@pytest.mark.parametrize(
    ("cause", "fragment"),
    [
        ("operator", "operator stopped me"),
        ("trailing_zero", "not a fault"),
        ("error", "driver error"),
        ("odd", "cause was odd"),
    ],
)
def test_other_causes(cause, fragment):
    out = explain_stop([_ev(1, "stop", {"request_id": None, "cause": cause, "latency_ms": None})])
    assert fragment in out["text"]


def test_no_stop_yet():
    out = explain_stop([_ev(1, "thought", {"text": "hello"})])
    assert out["cause"] is None and "not stopped" in out["text"]


def test_tool_reads_events_jsonl_from_run_dir(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in DENY_RUN) + "\nnot json\n\n")
    assert len(read_events(path)) == 5, "blank and non-JSON lines are skipped"
    log = LocalEventLog(tmp_path, session="s")
    configure_look(event_log=log, run_dir=tmp_path)
    result = why_stopped()
    assert result["frame_ref"] == "frames/000010.jpg" and "person in frame" in result["text"]
    assert log.read("thought")[-1]["payload"]["text"] == "why_stopped: deny"


def test_tool_uses_deepracer_run_dir_env(tmp_path, monkeypatch):
    (tmp_path / "events.jsonl").write_text(
        json.dumps(_ev(1, "stop", {"request_id": None, "cause": "operator", "latency_ms": 0}))
    )
    monkeypatch.setenv("DEEPRACER_RUN_DIR", str(tmp_path))
    configure_look(event_log=_NoRunDir())  # a sink without run_dir forces the env fallback
    assert "operator" in why_stopped()["text"]


class _NoRunDir:
    """An event sink without run_dir, forcing the DEEPRACER_RUN_DIR fallback."""

    def emit(self, type, payload=None, *, source=None, beat=None):
        return {"type": type, "payload": payload}


def test_tool_spec_name_and_description():
    assert why_stopped.tool_spec["name"] == "why_stopped"
    assert "event log" in why_stopped.tool_spec["description"]
