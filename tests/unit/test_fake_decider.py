"""The fake decider keeps the real server's wire shapes and answers from the fake camera's label."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from harness.fake_decider import FakeDecider, envelope_verdict, validate
from harness.frames import FRAME_CLASSES, LABEL_TO_CLASS, LABELS

FRAME_Q = {
    "type": "choice",
    "instructions": "Which class best describes the latest camera frame?",
    "criteria": dict.fromkeys(FRAME_CLASSES),
}
ENVELOPE_Q = {"type": "noul", "instructions": "Is this command inside the briefed envelope?"}


@pytest.fixture
def client(fake_decider: FakeDecider) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=fake_decider.url, timeout=5) as c:
        yield c


def ask(client: httpx.Client, state: Any, **questions: dict[str, Any]) -> dict[str, Any]:
    r = client.post("/v1/systemone", json={"state": state, "questions": questions, "images": ["AAAA"]})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_fields(client: httpx.Client) -> None:
    h = client.get("/health").json()
    for key in ("status", "model", "checkpoint", "base_model", "num_slots", "max_length", "device", "vision"):
        assert key in h
    assert h["status"] == "ok" and h["vision"] is True


def test_response_shape(client: httpx.Client) -> None:
    body = ask(client, "latest frame", frame=FRAME_Q, env=ENVELOPE_Q)
    assert set(body) == {"model", "answers", "usage", "latency_ms"}
    assert set(body["usage"]) == {"input_tokens", "output_tokens"}
    frame = body["answers"]["frame"]
    assert set(frame) == {"type", "choice", "probabilities", "confidence"} and frame["type"] == "choice"
    assert set(frame["probabilities"]) == set(FRAME_CLASSES)
    assert sum(frame["probabilities"].values()) == pytest.approx(1.0, abs=0.01)
    env = body["answers"]["env"]
    assert set(env) == {"type", "noul"} and env["type"] == "noul"


@pytest.mark.parametrize("label", LABELS)
def test_choice_follows_label(client: httpx.Client, fake_decider: FakeDecider, label: str) -> None:
    fake_decider.shared.set(label=label)
    cls, p = LABEL_TO_CLASS[label]
    answer = ask(client, "frame", frame=FRAME_Q)["answers"]["frame"]
    assert answer["choice"] == cls
    assert answer["probabilities"][cls] == pytest.approx(p)
    assert fake_decider.calls[-1]["label"] == label and fake_decider.calls[-1]["images"] == 1


def test_choice_outside_frame_classes_is_deterministic(client: httpx.Client) -> None:
    q = {"type": "choice", "instructions": "pick", "criteria": {"left": None, "right": None}}
    a = ask(client, "x", pick=q)["answers"]["pick"]
    assert a["choice"] == "left" and a["probabilities"]["left"] == pytest.approx(0.6)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("drive_deepracer linear=0.2 angular=0.0 duration=0.5", 0.95),
        ("drive_deepracer linear=0.5 angular=0.0 duration=0.5", 0.05),
        ("drive_deepracer linear=0.3 angular=0.4 duration=2.5", 0.05),
        ("drive_deepracer linear=-0.3 angular=0.0 duration=2.0", 0.95),
        ("turn left please", 0.5),
    ],
)
def test_noul_envelope_from_dict_state(client: httpx.Client, command: str, expected: float) -> None:
    state = {"command": command, "envelope": "|linear| <= 0.3 m/s, |angular| <= 1.0 rad/s, duration <= 2.0 s"}
    assert ask(client, state, env=ENVELOPE_Q)["answers"]["env"]["noul"] == pytest.approx(expected)


def test_noul_envelope_from_text_state(client: httpx.Client) -> None:
    envelope = "envelope: linear at most 0.3 m/s, duration at most 2.0 s"
    state = "command: drive_deepracer(linear=0.3, angular=0.1, duration=3.0)\n" + envelope
    assert ask(client, state, env=ENVELOPE_Q)["answers"]["env"]["noul"] == pytest.approx(0.05)
    state = "command: drive_deepracer(linear=0.3, angular=0.1, duration=1.0)\n" + envelope
    assert ask(client, state, env=ENVELOPE_Q)["answers"]["env"]["noul"] == pytest.approx(0.95)


def test_envelope_verdict_details() -> None:
    p, detail = envelope_verdict("linear 0.4 duration 1", "linear <= 0.3, duration <= 2")
    assert p == 0.05 and set(detail["violated"]) == {"linear"}


def test_noul_about_frame_class(client: httpx.Client, fake_decider: FakeDecider) -> None:
    q = {"type": "noul", "instructions": "Is there a person in the frame?"}
    assert ask(client, "frame", person=q)["answers"]["person"]["noul"] == pytest.approx(1 - 0.93)
    fake_decider.shared.set(label="person_in_frame")
    assert ask(client, "frame", person=q)["answers"]["person"]["noul"] == pytest.approx(0.97)


def test_noul_override(client: httpx.Client) -> None:
    assert client.get("/control", params={"noul": 0.11}).json()["noul"] == 0.11
    assert ask(client, "x", env=ENVELOPE_Q)["answers"]["env"]["noul"] == pytest.approx(0.11)
    client.get("/control", params={"noul": "none"})
    assert ask(client, "x", env=ENVELOPE_Q)["answers"]["env"]["noul"] == 0.5


def test_score_shape(client: httpx.Client) -> None:
    q = {"type": "score", "instructions": "how risky", "criteria": ["low", "medium", "high"]}
    a = ask(client, "x", risk=q)["answers"]["risk"]
    assert set(a) == {"type", "score", "legend", "probabilities", "confidence"}
    assert a["legend"] == {"0": "low", "1": "medium", "2": "high"}


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"questions": {"q": ENVELOPE_Q}}, "state must be a string, object or array"),
        ({"state": "x", "questions": {}}, "questions must be a non-empty object"),
        ({"state": "x", "questions": {"q": {"type": "guess", "instructions": "?"}}}, "unknown type 'guess'"),
        ({"state": "x", "questions": {"q": {"type": "noul"}}}, "instructions is required"),
        (
            {
                "state": "x",
                "questions": {"q": {"type": "choice", "instructions": "?", "criteria": {"a": None}}},
            },
            "choice requires at least 2 options",
        ),
        (
            {"state": "x", "questions": {"q": {"type": "score", "instructions": "?", "criteria": ["a"]}}},
            "score requires between 2 and 10 levels",
        ),
        (
            {
                "state": "x",
                "questions": {"q": {"type": "noul", "instructions": "?", "criteria": {"maybe": "x"}}},
            },
            "noul criteria keys must be a subset of {'true', 'false'}",
        ),
        (
            {"state": "x", "questions": {"q": ENVELOPE_Q}, "images": "AAAA"},
            "images must be a list of strings",
        ),
    ],
)
def test_validation_refusals(client: httpx.Client, body: dict[str, Any], reason: str) -> None:
    with pytest.raises(
        ValueError,
        match=reason.replace("{", "\\{").replace("}", "\\}").replace("(", "\\(").replace(")", "\\)"),
    ):
        validate(body)
    r = client.post("/v1/systemone", json=body)
    assert r.status_code == 422 and reason in r.json()["detail"][0]["msg"]


def test_latency_injection(client: httpx.Client) -> None:
    assert client.get("/control", params={"latency_ms": 400}).json()["latency_ms"] == 400
    t0 = time.monotonic()
    body = ask(client, "x", env=ENVELOPE_Q)
    assert time.monotonic() - t0 >= 0.4
    assert body["latency_ms"] >= 400


def test_failure_injection(client: httpx.Client, fake_decider: FakeDecider) -> None:
    client.get("/control", params={"fail": 1})
    r = client.post("/v1/systemone", json={"state": "x", "questions": {"env": ENVELOPE_Q}})
    assert r.status_code == 500 and r.json()["detail"] == "injected failure"
    assert fake_decider.calls[-1]["fail"] == "1"
    fake_decider.reset()
    assert ask(client, "x", env=ENVELOPE_Q)["answers"]["env"]["noul"] == 0.5
