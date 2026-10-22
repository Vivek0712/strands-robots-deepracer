"""Unit tests for the booth kiosks: label card, consent gating, leaderboard, egress and the portal routes.

No sockets: the decider is a stub with ``ask_noul``/``ask_choice``, the frame is a few JPEG bytes
handed straight to the kiosk, the portal runs under FastAPI's TestClient with a tmp run dir. The
refusal table lists what the routes turn away and why. Physics stops the car; the decider explains;
the kiosks are the decider explaining all day, and these tests check that nothing is kept without
consent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from beats.kiosk import (
    JUDGE_BEAT,
    Judgement,
    LabelCard,
    Leaderboard,
    TimedFrameSource,
    judge_frame,
    normalise_label,
    parse_command,
    replan_for,
    simon_async,
    words_to_digits,
)
from deepracer_agent.decider_client import DeciderUnavailable
from deepracer_agent.gate import DeciderGate, Decision, Envelope, LocalEventLog, Verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # portal/ is a plain package at the repo root, not installed
    sys.path.insert(0, str(REPO_ROOT))

from portal.backend.app import create_app  # noqa: E402
from portal.backend.console import ConsoleStream  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


class StubDecider:
    """Answers every choice with one class and every noul yes; records the criteria it was asked over."""

    base_url = "http://decider.test:8411"

    def __init__(self, cls: str = "clear", p: float = 0.93, *, fail: bool = False) -> None:
        self.cls, self.p, self.fail = cls, p, fail
        self.asked: list[dict[str, Any]] = []

    def ask_noul(self, q: str, ctx: Any, image_bytes: bytes | None = None, **kw: Any) -> dict[str, Any]:
        if "person" in q.lower():  # the gate's person pre-check over the frame (gate.PERSON_QUESTION)
            p = self.p if self.cls == "person_in_frame" else 0.05
            return {"yes": p >= 0.5, "probability": p, "latency_ms": 40}
        return {"yes": True, "probability": 0.95, "latency_ms": 40}

    def ask_choice(self, q: str, classes: Any, image_bytes: bytes | None = None, **kw: Any) -> dict[str, Any]:
        crit = dict(classes) if isinstance(classes, dict) else dict.fromkeys(classes)
        self.asked.append(crit)
        if self.fail:
            raise DeciderUnavailable("decider down")
        cls = self.cls if self.cls in crit else next(iter(crit))
        rest = round((1 - self.p) / max(1, len(crit) - 1), 4)
        return {
            "class": cls,
            "probability": self.p,
            "latency_ms": 120,
            "probabilities": {k: (self.p if k == cls else rest) for k in crit},
        }


def events_of(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ----- label card -------------------------------------------------------------------------------


def test_label_card_starts_with_the_five_frame_classes_and_adds_live() -> None:
    card = LabelCard()
    assert card.labels() == ["clear", "obstacle_near", "person_in_frame", "off_surface", "unclear"]
    assert card.add(" Running Shoe ") == "running_shoe"
    assert "running shoe" in card and card.criteria()["running_shoe"] is None
    card.add("running_shoe", "a trainer held up to the lens")
    assert card.criteria()["running_shoe"] == "a trainer held up to the lens"
    assert len(card) == 6
    assert card.remove("running shoe") is True and card.remove("running shoe") is False


@pytest.mark.parametrize("bad", ["", "   ", "!!!", "x" * 40, 7])
def test_label_card_refuses_bad_labels(bad: Any) -> None:
    with pytest.raises(ValueError):
        normalise_label(bad)


def test_label_card_limits() -> None:
    card = LabelCard(["a", "b"], max_labels=3)
    card.add("c")
    with pytest.raises(ValueError, match="at most 3"):
        card.add("d")
    card.remove("c")
    with pytest.raises(ValueError, match="at least two"):
        card.remove("a")


def test_new_label_reaches_the_decider_with_no_retraining(tmp_path: Path) -> None:
    decider = StubDecider("shoe", 0.8)
    card = LabelCard()
    judge_frame(JPEG, card, nickname="Ada", decider=decider)
    card.add("shoe")
    out = judge_frame(JPEG, card, nickname="Ada", decider=decider)
    assert list(decider.asked[0]) == ["clear", "obstacle_near", "person_in_frame", "off_surface", "unclear"]
    assert list(decider.asked[1])[-1] == "shoe"
    assert out["class"] == "shoe" and out["probability"] == 0.8 and out["latency_ms"] == 120
    assert out["labels"][-1] == "shoe"


# ----- consent ----------------------------------------------------------------------------------


def test_without_consent_no_frame_is_written_and_the_verdict_says_so(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="k")
    out = judge_frame(
        JPEG,
        LabelCard(),
        nickname="Ada",
        consent=False,
        decider=StubDecider(),
        event_log=log,
        run_dir=tmp_path,
    )
    assert out["frame_saved"] is False and out["frame_ref"] is None and out["consent"] is False
    assert not (tmp_path / "frames").exists()
    events = events_of(tmp_path)
    assert [e["type"] for e in events] == ["verdict"]
    v = events[0]
    assert v["beat"] == JUDGE_BEAT and v["source"] == "kiosk"
    assert v["payload"]["frame_ref"] is None and v["payload"]["consent"] is False
    assert v["payload"]["nickname"] == "Ada" and v["payload"]["stage"] == "frame"
    assert v["payload"]["class"] == "clear" and v["payload"]["probability"] == 0.93
    assert v["payload"]["latency_ms"] == 120


def test_with_consent_the_frame_is_saved_once_and_a_frame_event_follows(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="k")
    out = judge_frame(
        JPEG,
        LabelCard(),
        nickname="Grace",
        consent=True,
        decider=StubDecider(),
        event_log=log,
        run_dir=tmp_path,
    )
    assert out["frame_saved"] is True and out["frame_ref"].startswith("frames/kiosk-judge-")
    saved = list((tmp_path / "frames").glob("*.jpg"))
    assert len(saved) == 1 and saved[0].read_bytes() == JPEG
    events = events_of(tmp_path)
    assert [e["type"] for e in events] == ["frame", "verdict"]
    assert events[0]["payload"]["frame_ref"] == out["frame_ref"] and events[0]["beat"] == JUDGE_BEAT
    assert events[1]["payload"]["frame_ref"] == out["frame_ref"] and events[1]["payload"]["consent"] is True


def test_consent_without_a_run_dir_keeps_nothing(tmp_path: Path) -> None:
    out = judge_frame(JPEG, LabelCard(), nickname="Ada", consent=True, decider=StubDecider())
    assert out["frame_saved"] is False and out["frame_ref"] is None
    assert not list(tmp_path.iterdir())


def test_judge_frame_maps_the_gate_table_and_fails_closed() -> None:
    assert (
        judge_frame(JPEG, LabelCard(), nickname="a", decider=StubDecider("person_in_frame", 0.97))["action"]
        == "Deny"
    )
    assert (
        judge_frame(JPEG, LabelCard(), nickname="a", decider=StubDecider("obstacle_near", 0.9))["action"]
        == "Guide"
    )
    assert (
        judge_frame(JPEG, LabelCard(), nickname="a", decider=StubDecider("unclear", 0.4))["action"]
        == "Proceed"
    )
    down = judge_frame(JPEG, LabelCard(), nickname="a", decider=StubDecider(fail=True))
    assert down["action"] == "Deny" and down["class"] is None and "vision unavailable" in down["reason"]
    assert down["egress"] == [
        {"what": "decider POST /v1/systemone (choice)", "host": "decider.test:8411", "ms": None}
    ]
    with pytest.raises(ValueError, match="nickname"):
        judge_frame(JPEG, LabelCard(), nickname="  ", decider=StubDecider())


# ----- leaderboard ------------------------------------------------------------------------------


def test_leaderboard_ranks_wrong_class_above_low_confidence_and_keeps_one_row_per_nickname() -> None:
    board = Leaderboard()
    board.record(Judgement("Ada", "clear", 0.93, 120, expected="shoe"))  # wrong: 1.07
    board.record(Judgement("Grace", "clear", 0.93, 120, expected="clear"))  # right, sure: 0.07
    board.record(Judgement("Linus", "clear", 0.55, 120))  # no claim, unsure: 0.45
    board.record(Judgement("Grace", "unclear", 0.6, 120, expected="clear"))  # wrong: 1.4, Grace's best
    board.record(Judgement("Down", None, None, None))  # decider down scores nothing
    top = board.top()
    assert [(r["rank"], r["nickname"]) for r in top] == [(1, "Grace"), (2, "Ada"), (3, "Linus"), (4, "Down")]
    assert top[0]["tries"] == 2 and top[0]["wrong"] is True and top[0]["fool_score"] == 1.4
    assert top[2]["wrong"] is False and top[2]["fool_score"] == 0.45
    assert top[3]["fool_score"] == 0.0
    assert len(board.top(2)) == 2 and len(board) == 5


def test_leaderboard_survives_a_restart_from_events_jsonl(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="k")
    board = Leaderboard()
    for nick, cls, exp in (("Ada", "clear", "shoe"), ("Grace", "clear", "clear"), ("Linus", "clear", None)):
        judge_frame(
            JPEG,
            LabelCard(),
            nickname=nick,
            expected=exp,
            decider=StubDecider(cls),
            event_log=log,
            run_dir=tmp_path,
            leaderboard=board,
        )
    log.emit("thought", {"text": "not a judgement"})
    reloaded = Leaderboard.load(tmp_path / "events.jsonl")
    assert (
        [r["nickname"] for r in reloaded.top()]
        == [r["nickname"] for r in board.top()]
        == ["Ada", "Grace", "Linus"]  # Grace and Linus tie on 1 - 0.93; the earlier judgement ranks first
    )
    assert reloaded.top()[0]["expected"] == "shoe" and reloaded.top()[0]["wrong"] is True
    assert Leaderboard.load(tmp_path / "missing.jsonl").top() == []


# ----- Simon Says: egress and re-plan -------------------------------------------------------------


async def test_simon_egress_lists_camera_and_decider_calls_with_ms(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="k")
    frames = TimedFrameSource(lambda: JPEG, host="console.test:8390")
    gate = DeciderGate(
        StubDecider("clear", 0.93), frames, event_log=log, envelope=Envelope(), beat="kiosk-simon"
    )
    out = await simon_async("hop forward", gate)
    assert out["action"] == "Proceed" and out["class"] == "clear" and out["probability"] == 0.93
    assert out["latency_ms"] == 200  # envelope 40 + frame (person 40 + choice 120) and out["replan"] is None
    assert [e["host"] for e in out["egress"]] == [
        "console.test:8390",
        "decider.test:8411",
        "decider.test:8411",
    ]
    assert out["egress"][1]["ms"] == 40 and out["egress"][2]["ms"] == 160
    assert out["egress"][1]["what"].endswith("(envelope, noul)") and out["egress"][2]["what"].endswith(
        "(frame, person noul + choice)"
    )
    assert isinstance(out["egress"][0]["ms"], int) and "No model call" in out["egress_note"]
    assert all(e["beat"] == "kiosk-simon" for e in events_of(tmp_path))


async def test_simon_over_envelope_shows_the_slower_plan_and_guide_halves(tmp_path: Path) -> None:
    log = LocalEventLog(tmp_path, session="k")
    gate = DeciderGate(StubDecider("clear"), lambda: JPEG, event_log=log, envelope=Envelope())
    confirm = await simon_async("go forward fast for two seconds", gate)
    assert confirm["action"] == "Confirm" and confirm["command"]["linear"] == 0.6
    assert confirm["replan"] == {"linear": 0.3, "angular": 0.0, "duration": 2.0}
    assert "The gate would take: forward at 0.3 m/s for 2 s" in confirm["card"]
    gate.decider = StubDecider("obstacle_near", 0.9)
    guide = await simon_async("hop forward", gate)
    assert guide["action"] == "Guide" and guide["replan"] == {"linear": 0.15, "angular": 0.0, "duration": 0.5}
    assert "0.15 m/s" in guide["card"]
    words = await simon_async("what is your battery", gate)
    assert words["action"] is None and words["egress"] == [] and words["replan"] is None
    yaw = await simon_async("turn left", gate)
    assert yaw["action"] == "Deny" and yaw["egress"] == []


def test_replan_for_clips_backwards_commands_into_the_envelope() -> None:
    decision = Decision("r", "Confirm", "outside", [Verdict("r", "envelope", "Confirm", "outside")])
    assert replan_for(decision, {"linear": -0.9, "angular": -3.0, "duration": 5.0}, Envelope()) == {
        "linear": -0.3,
        "angular": -1.0,
        "duration": 2.0,
    }
    assert replan_for(Decision("r", "Deny", "x"), {"linear": 0.3}, Envelope()) is None


# ----- routes -----------------------------------------------------------------------------------


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs" / "s-kiosk"


@pytest.fixture
def decider() -> StubDecider:
    return StubDecider()


def make_client(run_dir: Path, decider: StubDecider, tmp_path: Path, frame: Any = lambda: JPEG) -> TestClient:
    from tests.unit.test_portal_backend import RecorderRuntime

    console = ConsoleStream(base_url="http://127.0.0.1:1", password="")
    app = create_app(
        run_dir=run_dir,
        runtime=RecorderRuntime(),
        console=console,
        frontend_dist=tmp_path / "nodist",
        kiosk_decider=decider,
        kiosk_frame_source=frame,
    )
    return TestClient(app)


@pytest.fixture
def client(run_dir: Path, decider: StubDecider, tmp_path: Path) -> TestClient:
    with make_client(run_dir, decider, tmp_path) as tc:
        yield tc


def test_judge_route_without_consent_writes_no_frame(client: TestClient, run_dir: Path) -> None:
    r = client.post("/kiosk/judge", json={"nickname": "Ada", "expected": "shoe"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True and body["consent"] is False and body["frame_saved"] is False
    assert body["class"] == "clear" and body["probability"] == 0.93 and body["latency_ms"] == 120
    assert body["wrong"] is True and body["egress"][0]["what"].startswith("camera console")
    assert not (run_dir / "frames").exists()
    events = events_of(run_dir)
    assert [e["type"] for e in events] == ["verdict"] and events[0]["beat"] == JUDGE_BEAT
    assert client.get("/api/state").json()["latest"]["verdict"]["payload"]["nickname"] == "Ada"


def test_judge_route_with_consent_saves_and_serves_the_frame(client: TestClient, run_dir: Path) -> None:
    r = client.post("/kiosk/judge", json={"nickname": "Grace", "consent": True})
    body = r.json()
    assert r.status_code == 200 and body["frame_saved"] is True
    name = body["frame_ref"].split("/")[-1]
    assert (run_dir / "frames" / name).read_bytes() == JPEG
    assert client.get(f"/api/runs/s-kiosk/frames/{name}").status_code == 200
    assert [e["type"] for e in events_of(run_dir)] == ["frame", "verdict"]


def test_judge_route_accepts_a_tablet_frame_and_the_leaderboard_orders_three(
    client: TestClient, decider: StubDecider
) -> None:
    import base64

    b64 = base64.b64encode(JPEG).decode()
    assert (
        client.post(
            "/kiosk/judge", json={"nickname": "Ada", "expected": "shoe", "frame_b64": b64}
        ).status_code
        == 200
    )
    assert client.post("/kiosk/judge", json={"nickname": "Grace", "expected": "clear"}).status_code == 200
    decider.p = 0.55
    assert client.post("/kiosk/judge", json={"nickname": "Linus"}).status_code == 200
    board = client.get("/kiosk/leaderboard").json()
    assert board["total"] == 3 and [r["nickname"] for r in board["entries"]] == ["Ada", "Linus", "Grace"]
    assert board["entries"][0]["wrong"] is True and board["entries"][1]["probability"] == 0.55
    assert [j["nickname"] for j in board["recent"]] == ["Linus", "Grace", "Ada"]


def test_labels_routes_add_remove_and_ask_over_the_new_list(
    client: TestClient, decider: StubDecider, run_dir: Path
) -> None:
    assert [x["label"] for x in client.get("/kiosk/labels").json()["labels"]][-1] == "unclear"
    r = client.post("/kiosk/labels", json={"label": "Shoe", "description": "a trainer"})
    assert r.status_code == 200 and r.json()["labels"][-1] == {
        "label": "shoe",
        "description": "a trainer",
        "builtin": False,
    }
    decider.cls = "shoe"
    body = client.post("/kiosk/judge", json={"nickname": "Ada"}).json()
    assert body["class"] == "shoe" and list(decider.asked[-1])[-1] == "shoe"
    assert client.post("/kiosk/labels", json={"label": "shoe", "remove": True}).json()["count"] == 5
    assert client.post("/kiosk/labels", json={"label": "shoe", "remove": True}).status_code == 404
    thoughts = [e for e in events_of(run_dir) if e["type"] == "thought"]
    assert len(thoughts) == 2 and "no retraining" in thoughts[0]["payload"]["text"]


def test_simon_route_returns_the_card_replan_and_egress(
    client: TestClient, decider: StubDecider, run_dir: Path
) -> None:
    r = client.post("/kiosk/simon", json={"text": "go forward fast for two seconds"})
    body = r.json()
    assert r.status_code == 200 and body["action"] == "Confirm" and body["replan"]["linear"] == 0.3
    assert len(body["egress"]) == 3 and body["egress"][0]["host"] == "127.0.0.1:1"
    assert body["envelope"]["max_linear"] == 0.3
    decider.cls, decider.p = "person_in_frame", 0.97
    deny = client.post("/kiosk/simon", json={"text": "hop forward"}).json()
    assert deny["action"] == "Deny" and deny["class"] == "person_in_frame" and deny["card"].startswith("Deny")
    history = client.get("/kiosk/simon").json()["history"]
    assert [h["action"] for h in history] == ["Deny", "Confirm"]
    verdicts = [e for e in events_of(run_dir) if e["type"] == "verdict"]
    assert len(verdicts) == 4 and all(v["beat"] == "kiosk-simon" for v in verdicts)


def test_judge_route_fails_closed_without_a_frame(
    run_dir: Path, decider: StubDecider, tmp_path: Path
) -> None:
    with make_client(run_dir, decider, tmp_path, frame=lambda: None) as tc:
        r = tc.post("/kiosk/judge", json={"nickname": "Ada"})
        assert r.status_code == 503 and r.json()["error"] == "vision unavailable"
        assert not events_of(run_dir)
        simon = tc.post("/kiosk/simon", json={"text": "hop forward"}).json()
        assert simon["action"] == "Deny" and simon["reason"] == "vision unavailable"


@pytest.mark.parametrize(
    ("route", "body", "status", "reason_part"),
    [
        ("/kiosk/judge", {"consent": True}, 422, "nickname"),
        ("/kiosk/judge", {"nickname": "x" * 41}, 422, "longer than"),
        ("/kiosk/judge", {"nickname": "Ada", "consent": "yes"}, 422, "consent"),
        ("/kiosk/judge", {"nickname": "Ada", "frame_b64": "@@@"}, 422, "base64"),
        ("/kiosk/judge", {"nickname": "Ada", "frame_b64": "aGVsbG8="}, 422, "JPEG"),
        ("/kiosk/judge", {"nickname": "Ada", "expected": 3}, 422, "expected"),
        ("/kiosk/judge", [1], 422, "object"),
        ("/kiosk/simon", {"text": "  "}, 422, "text"),
        ("/kiosk/simon", {"text": "x" * 201}, 422, "longer"),
        ("/kiosk/labels", {"label": ""}, 422, "empty"),
        ("/kiosk/labels", {"label": "a", "description": 1}, 422, "description"),
        ("/kiosk/labels", {"remove": True}, 422, "label"),
    ],
)
def test_kiosk_refusal_table(
    client: TestClient, route: str, body: Any, status: int, reason_part: str
) -> None:
    r = client.post(route, json=body)
    assert r.status_code == status
    assert r.json()["accepted"] is False and reason_part in r.json()["reason"]


def test_kiosk_routes_refuse_non_json(client: TestClient) -> None:
    for route in ("/kiosk/judge", "/kiosk/simon", "/kiosk/labels"):
        r = client.post(route, content=b"not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and "JSON" in r.json()["reason"]


def test_leaderboard_resumes_from_the_run_dir_on_restart(
    run_dir: Path, decider: StubDecider, tmp_path: Path
) -> None:
    with make_client(run_dir, decider, tmp_path) as tc:
        tc.post("/kiosk/judge", json={"nickname": "Ada", "expected": "shoe"})
    with make_client(run_dir, decider, tmp_path) as tc:
        board = tc.get("/kiosk/leaderboard").json()
        assert board["total"] == 1 and board["entries"][0]["nickname"] == "Ada" and board["recent"] == []


@pytest.mark.parametrize(
    ("text", "linear", "duration"),
    [
        ("Drive forward at two metres per second for ten seconds.", 2.0, 10.0),
        ("go forward for two seconds", 0.3, 2.0),
        ("roll ahead at half a metre per second for three seconds", 0.5, 3.0),
        ("move forward at a metre per second for a second", 1.0, 1.0),
        ("hop forward 0.2 m/s for 1.5 s", 0.2, 1.5),
        ("drive back at twenty centimetres per second", -0.3, 0.5),  # cm/s is not a speed the grammar knows
    ],
)
def test_parse_command_reads_number_words(text: str, linear: float, duration: float) -> None:
    out = parse_command(text)
    assert out is not None
    assert out["linear"] == pytest.approx(linear)
    assert out["duration"] == pytest.approx(duration)


def test_words_to_digits_leaves_unknown_words_alone() -> None:
    assert words_to_digits("Hop forward twenty centimetres.") == "hop forward 20 centimetres."
    assert words_to_digits("go somewhere nice") == "go somewhere nice"
