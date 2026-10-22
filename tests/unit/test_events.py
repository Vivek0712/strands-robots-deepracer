"""EventLog: JSONL append, seq, session, beat, portal mirror that never raises, frames."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from deepracer_agent.events import EVENT_TYPES, EventLog, jpeg_dimensions, new_session_id
from tests.unit._car_fakes import tiny_jpeg


def test_emit_appends_jsonl_with_schema_fields(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s-1", portal_url="", beat="marshal", source="driver")
    event = log.emit("command", {"tool": "drive_deepracer", "args": {}, "request_id": "r-1"})
    log.emit("stop", {"request_id": "r-1", "cause": "trailing_zero", "latency_ms": 3}, beat="apology")
    lines = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["seq"] for e in lines] == [1, 2]
    assert event["seq"] == 1 and event["ts"].endswith("Z") and "T" in event["ts"]
    assert lines[0]["session"] == "s-1" and lines[0]["beat"] == "marshal" and lines[0]["source"] == "driver"
    assert lines[1]["beat"] == "apology"
    assert set(lines[0]) == {"ts", "seq", "session", "beat", "type", "source", "payload"}


def test_every_contract_type_is_accepted() -> None:
    expected = {
        "thought", "command", "verdict", "approval", "motion", "stop", "heartbeat",
        "preflight", "frame", "voice", "led", "body", "error",
    }  # fmt: skip
    assert EVENT_TYPES == expected


@pytest.mark.parametrize(
    "type_,payload,reason",
    [
        ("teleport", {"x": 1}, "unknown event type 'teleport'"),
        ("command", "not a dict", "payload must be a dict"),
        ("command", None, "payload must be a dict"),
        ("command", [1, 2], "payload must be a dict"),
    ],
)
def test_refusal_table_emit_records_bad_input_as_error(
    tmp_path: Path, type_: str, payload: Any, reason: str
) -> None:
    """A malformed emit never raises and never silently disappears: it becomes an ``error`` row."""
    log = EventLog(tmp_path, session="s", portal_url="")
    event = log.emit(type_, payload)
    assert event["type"] == "error"
    assert reason in event["payload"]["message"]


def test_portal_mirror_posts_same_object(tmp_path: Path) -> None:
    posted: list[tuple[str, dict[str, Any]]] = []
    done = threading.Event()

    def poster(url: str, body: dict[str, Any]) -> None:
        posted.append((url, body))
        done.set()

    log = EventLog(tmp_path, session="s", portal_url="http://portal:8765/", poster=poster)
    event = log.emit("body", {"active": "sim"})
    assert done.wait(2.0)
    assert posted == [("http://portal:8765/api/events", event)]


def test_portal_down_never_raises_and_file_still_written(tmp_path: Path) -> None:
    def poster(url: str, body: dict[str, Any]) -> None:
        raise ConnectionError("portal down")

    log = EventLog(tmp_path, session="s", portal_url="http://127.0.0.1:1", poster=poster)
    log.emit("thought", {"text": "hi"})
    log.flush()
    assert len(log.read()) == 1


def test_real_poster_against_closed_port_never_raises(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s", portal_url="http://127.0.0.1:9")
    log.emit("thought", {"text": "hi"})
    log.flush(2.0)
    assert log.read("thought")[0]["payload"] == {"text": "hi"}


def test_empty_portal_url_disables_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_URL", "")
    called = []
    log = EventLog(tmp_path, session="s", poster=lambda u, b: called.append(u))
    log.emit("thought", {"text": "x"})
    log.flush()
    assert called == [] and log.portal_url == ""


def test_save_frame_writes_under_run_dir_and_emits_frame(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s", portal_url="")
    ref = log.save_frame(tiny_jpeg(480, 360))
    assert ref == "frames/000001.jpg"
    assert (tmp_path / "frames" / "000001.jpg").exists()
    frame = log.last("frame")
    assert frame and frame["payload"] == {"frame_ref": ref, "width": 480, "height": 360}
    assert log.save_frame(tiny_jpeg()) == "frames/000002.jpg"


@pytest.mark.parametrize("bad", [b"", b"abc", b"\xff\xd8junk", "not bytes", None])
def test_refusal_table_save_frame_rejects_non_jpeg(tmp_path: Path, bad: Any) -> None:
    log = EventLog(tmp_path, session="s", portal_url="")
    assert log.save_frame(bad) is None  # type: ignore[arg-type]
    assert log.last("error")["payload"]["where"] == "events.save_frame"
    assert not (tmp_path / "frames").exists()


def test_jpeg_dimensions_reads_sof() -> None:
    assert jpeg_dimensions(tiny_jpeg(640, 480)) == (640, 480)
    assert jpeg_dimensions(b"\xff\xd8\xff\xd9") is None


def test_read_filters_by_type_and_last(tmp_path: Path) -> None:
    log = EventLog(tmp_path, session="s", portal_url="")
    log.emit("thought", {"text": "a"})
    log.emit("stop", {"request_id": None, "cause": "operator", "latency_ms": None})
    log.emit("thought", {"text": "b"})
    assert [e["payload"]["text"] for e in log.read("thought")] == ["a", "b"]
    assert log.last("stop")["payload"]["cause"] == "operator"
    assert log.last("verdict") is None


def test_session_id_shape() -> None:
    sid = new_session_id()
    assert sid.startswith("s-") and len(sid) == len("s-20261014-0652")


def test_default_run_dir_honours_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPRACER_RUN_DIR", str(tmp_path / "run"))
    log = EventLog(session="s", portal_url="")
    log.emit("thought", {"text": "x"})
    assert (tmp_path / "run" / "events.jsonl").exists()
