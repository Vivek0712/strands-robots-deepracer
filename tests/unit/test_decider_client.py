"""DeciderClient: the exact /v1/systemone wire format, and every way the server can fail us."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from deepracer_agent.decider_client import WARM_JPEG, DeciderClient, DeciderUnavailable


def _server(handler):
    """A DeciderClient over an httpx.MockTransport driven by ``handler(request) -> Response``."""
    return DeciderClient("http://decider.test", timeout_s=0.2, transport=httpx.MockTransport(handler))


def _ok(answers: dict, **extra) -> httpx.Response:
    body = {"model": "strands-decider-E4B-gemma4-v1-2610", "answers": answers, "usage": {"input_tokens": 1}}
    body.update(extra)
    return httpx.Response(200, json=body)


def test_noul_request_matches_server_schema():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return _ok({"q": {"type": "noul", "noul": 0.91}}, latency_ms=12.5)

    client = _server(handler)
    out = client.ask_noul("Inside the envelope?", {"command": {"linear": 0.3}, "envelope": "x"})
    assert seen["path"] == "/v1/systemone"
    body = seen["body"]
    assert body["model"] == "strands-decider-latest"
    assert body["state"] == {"command": {"linear": 0.3}, "envelope": "x"}
    assert body["questions"] == {"q": {"type": "noul", "instructions": "Inside the envelope?"}}
    assert "images" not in body
    assert out["yes"] is True
    assert out["probability"] == pytest.approx(0.91)
    assert isinstance(out["latency_ms"], int)


def test_noul_criteria_are_forwarded_and_no_is_below_half():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok({"q": {"type": "noul", "noul": 0.2}})

    out = _server(handler).ask_noul("ok?", "state", criteria={"true": "it holds", "false": "it does not"})
    assert seen["body"]["questions"]["q"]["criteria"] == {"true": "it holds", "false": "it does not"}
    assert out["yes"] is False and out["probability"] == pytest.approx(0.2)


def test_choice_request_sends_base64_image_and_criteria():
    seen: dict = {}
    jpeg = b"\xff\xd8fakejpeg\xff\xd9"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok(
            {
                "q": {
                    "type": "choice",
                    "choice": "person_in_frame",
                    "probabilities": {"clear": 0.02, "person_in_frame": 0.97, "unclear": 0.01},
                    "confidence": 0.95,
                }
            }
        )

    out = _server(handler).ask_choice(
        "What is ahead?", ["clear", "person_in_frame", "unclear"], image_bytes=jpeg
    )
    body = seen["body"]
    assert body["images"] == [base64.b64encode(jpeg).decode("ascii")]
    assert body["state"] == ""
    q = body["questions"]["q"]
    assert q["type"] == "choice"
    assert q["criteria"] == {"clear": None, "person_in_frame": None, "unclear": None}
    assert out["class"] == "person_in_frame"
    assert out["probability"] == pytest.approx(0.97)
    assert out["probabilities"]["clear"] == pytest.approx(0.02)


def test_choice_accepts_descriptions_mapping():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok(
            {"q": {"type": "choice", "choice": "a", "probabilities": {"a": 0.6, "b": 0.4}, "confidence": 0.2}}
        )

    _server(handler).ask_choice("pick", {"a": "first thing", "b": None})
    assert seen["body"]["questions"]["q"]["criteria"] == {"a": "first thing", "b": None}


def test_choice_requires_two_classes():
    with pytest.raises(ValueError):
        _server(lambda r: _ok({})).ask_choice("pick", ["only"])


def test_health_returns_server_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok", "model": "m", "vision": True})

    assert _server(handler).health()["vision"] is True


@pytest.mark.parametrize(
    ("label", "handler", "match"),
    [
        ("timeout", lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=r)), "timeout"),
        (
            "connect error",
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("down", request=r)),
            "transport",
        ),
        ("http 500", lambda r: httpx.Response(500, text="boom"), "HTTP 500"),
        ("http 422", lambda r: httpx.Response(422, json={"detail": "too many options"}), "HTTP 422"),
        ("non-json", lambda r: httpx.Response(200, text="<html>"), "non-JSON"),
        ("missing answers", lambda r: httpx.Response(200, json={"model": "m"}), "missing answers"),
        ("wrong question name", lambda r: _ok({"other": {"type": "noul", "noul": 0.5}}), "missing answers"),
        ("noul not a number", lambda r: _ok({"q": {"type": "noul", "noul": "yes"}}), "malformed noul"),
        ("noul a string number", lambda r: _ok({"q": {"type": "noul", "noul": "0.9"}}), "malformed noul"),
        ("noul a bool", lambda r: _ok({"q": {"type": "noul", "noul": True}}), "malformed noul"),
        ("noul missing", lambda r: _ok({"q": {"type": "noul"}}), "malformed noul"),
        ("noul out of range", lambda r: _ok({"q": {"type": "noul", "noul": 1.7}}), "out of range"),
        ("noul negative", lambda r: _ok({"q": {"type": "noul", "noul": -0.1}}), "out of range"),
        (
            "noul NaN",
            lambda r: httpx.Response(
                200,
                content=b'{"answers": {"q": {"type": "noul", "noul": NaN}}}',
                headers={"content-type": "application/json"},
            ),
            "out of range",
        ),
        (
            "noul wrong type",
            lambda r: _ok({"q": {"type": "choice", "choice": "a", "probabilities": {"a": 1}}}),
            "malformed noul",
        ),
    ],
)
def test_noul_failures_raise_decider_unavailable(label, handler, match):
    with pytest.raises(DeciderUnavailable, match=match):
        _server(handler).ask_noul("q?", "s")


@pytest.mark.parametrize(
    ("label", "answer"),
    [
        (
            "choice not in classes",
            {"type": "choice", "choice": "zebra", "probabilities": {"a": 0.5, "b": 0.5}},
        ),
        ("probabilities missing", {"type": "choice", "choice": "a"}),
        ("choice missing from probabilities", {"type": "choice", "choice": "a", "probabilities": {"b": 1.0}}),
        (
            "probability not numeric",
            {"type": "choice", "choice": "a", "probabilities": {"a": "high", "b": 0.0}},
        ),
        (
            "probability a string number",
            {"type": "choice", "choice": "a", "probabilities": {"a": "0.9", "b": 0.1}},
        ),
        ("probability a bool", {"type": "choice", "choice": "a", "probabilities": {"a": True, "b": 0.0}}),
        ("probability above one", {"type": "choice", "choice": "a", "probabilities": {"a": 1.5, "b": 0.0}}),
        ("probability negative", {"type": "choice", "choice": "a", "probabilities": {"a": 0.9, "b": -0.1}}),
        (
            "probability NaN",
            {"type": "choice", "choice": "a", "probabilities": {"a": float("nan"), "b": 0.1}},
        ),
        ("noul answer to a choice", {"type": "noul", "noul": 0.9}),
    ],
)
def test_choice_malformed_raises_decider_unavailable(label, answer):
    body = json.dumps({"answers": {"q": answer}}).encode()  # json.dumps writes NaN as the NaN literal
    with pytest.raises(DeciderUnavailable):
        _server(
            lambda r: httpx.Response(200, content=body, headers={"content-type": "application/json"})
        ).ask_choice("pick", ["a", "b"])


def test_ask_many_sends_three_questions_in_one_request_and_parses_each_by_type():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok(
            {
                "inside_envelope": {"type": "noul", "noul": 0.91},
                "args_grounded": {"type": "noul", "noul": 0.2},
                "intent": {
                    "type": "choice",
                    "choice": "stop",
                    "probabilities": {"move_forward": 0.1, "stop": 0.9},
                    "confidence": 0.8,
                },
            }
        )

    questions = {
        "inside_envelope": {"type": "noul", "instructions": "inside?"},
        "args_grounded": {
            "type": "noul",
            "instructions": "grounded?",
            "criteria": {"true": "t", "false": "f"},
        },
        "intent": {
            "type": "choice",
            "instructions": "intent?",
            "criteria": {"move_forward": "m", "stop": "s"},
        },
    }
    out = _server(handler).ask_many(questions, {"conversation": "user: stop", "command": {"linear": 0.3}})
    assert seen["body"]["questions"] == questions and "images" not in seen["body"]
    assert seen["body"]["state"] == {"conversation": "user: stop", "command": {"linear": 0.3}}
    answers = out["answers"]
    assert answers["inside_envelope"]["yes"] is True and answers["inside_envelope"]["probability"] == 0.91
    assert answers["args_grounded"]["yes"] is False and answers["args_grounded"]["probability"] == 0.2
    assert answers["intent"]["class"] == "stop" and answers["intent"]["probability"] == 0.9
    assert out["latency_ms"] == answers["intent"]["latency_ms"] >= 0


@pytest.mark.parametrize(
    ("label", "answers"),
    [
        (
            "one of three missing",
            {
                "a": {"type": "noul", "noul": 0.9},
                "c": {"type": "choice", "choice": "x", "probabilities": {"x": 1, "y": 0}},
            },
        ),
        (
            "choice outside criteria",
            {
                "a": {"type": "noul", "noul": 0.9},
                "b": {"type": "noul", "noul": 0.9},
                "c": {"type": "choice", "choice": "zebra", "probabilities": {"x": 1, "y": 0}},
            },
        ),
        (
            "noul NaN",
            {
                "a": {"type": "noul", "noul": float("nan")},
                "b": {"type": "noul", "noul": 0.9},
                "c": {"type": "choice", "choice": "x", "probabilities": {"x": 1, "y": 0}},
            },
        ),
    ],
)
def test_ask_many_part_of_an_answer_is_unavailable(label, answers):
    body = json.dumps({"answers": answers}).encode()
    questions = {
        "a": {"type": "noul", "instructions": "a?"},
        "b": {"type": "noul", "instructions": "b?"},
        "c": {"type": "choice", "instructions": "c?", "criteria": {"x": None, "y": None}},
    }
    with pytest.raises(DeciderUnavailable):
        _server(
            lambda r: httpx.Response(200, content=body, headers={"content-type": "application/json"})
        ).ask_many(questions, "s")


def test_health_failure_raises_decider_unavailable():
    with pytest.raises(DeciderUnavailable):
        _server(lambda r: httpx.Response(503, text="loading")).health()


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("DECIDER_URL", "http://10.0.0.5:8111/")
    assert DeciderClient().base_url == "http://10.0.0.5:8111"
    monkeypatch.delenv("DECIDER_URL")
    assert DeciderClient().base_url == "http://127.0.0.1:8111"


def test_ask_frame_sends_both_questions_in_one_request():
    seen: dict = {}
    jpeg = b"\xff\xd8fakejpeg\xff\xd9"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok(
            {
                "person": {"type": "noul", "noul": 0.95},
                "frame": {
                    "type": "choice",
                    "choice": "unclear",
                    "probabilities": {"clear": 0.1, "person_in_frame": 0.2, "unclear": 0.7},
                    "confidence": 0.5,
                },
            }
        )

    out = _server(handler).ask_frame(
        "Is a person visible?",
        "What is ahead?",
        {"clear": "x", "person_in_frame": "y", "unclear": None},
        jpeg,
    )
    body = seen["body"]
    assert body["images"] == [base64.b64encode(jpeg).decode("ascii")] and body["state"] == ""
    assert body["questions"]["person"] == {"type": "noul", "instructions": "Is a person visible?"}
    assert body["questions"]["frame"]["criteria"] == {"clear": "x", "person_in_frame": "y", "unclear": None}
    assert out["person"]["yes"] is True and out["person"]["probability"] == pytest.approx(0.95)
    assert out["frame"]["class"] == "unclear" and out["frame"]["probability"] == pytest.approx(0.7)
    assert out["latency_ms"] == out["person"]["latency_ms"] == out["frame"]["latency_ms"]


@pytest.mark.parametrize(
    ("label", "answers"),
    [
        (
            "person half missing",
            {"frame": {"type": "choice", "choice": "a", "probabilities": {"a": 1, "b": 0}}},
        ),
        ("frame half missing", {"person": {"type": "noul", "noul": 0.9}}),
        (
            "person malformed",
            {
                "person": {"type": "noul", "noul": "yes"},
                "frame": {"type": "choice", "choice": "a", "probabilities": {"a": 1, "b": 0}},
            },
        ),
        (
            "frame malformed",
            {
                "person": {"type": "noul", "noul": 0.9},
                "frame": {"type": "choice", "choice": "zebra", "probabilities": {"a": 1, "b": 0}},
            },
        ),
    ],
)
def test_ask_frame_half_an_answer_is_unavailable(label, answers):
    """The gate asked for two answers; one is worth nothing (fail closed)."""
    with pytest.raises(DeciderUnavailable):
        _server(lambda r: _ok(answers)).ask_frame("p?", "f?", ["a", "b"], b"\xff\xd8\xff\xd9")


def test_warm_sends_one_noul_with_the_tiny_jpeg_under_a_long_budget():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.extensions["timeout"]["read"] == 42.0
        return httpx.Response(200, json={"answers": {"warm": {"type": "noul", "noul": 0.5}}})

    client = _server(handler)
    latency = client.warm(timeout_s=42.0)
    assert latency >= 0
    assert len(seen) == 1
    assert list(seen[0]["questions"]) == ["warm"]
    assert seen[0]["questions"]["warm"]["type"] == "noul"
    assert base64.b64decode(seen[0]["images"][0]) == WARM_JPEG
    # the gate's own budget is restored afterwards
    assert client._client.timeout.read == 0.2


def test_warm_failure_is_decider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="loading")

    with pytest.raises(DeciderUnavailable, match="HTTP 503"):
        _server(handler).warm(timeout_s=1.0)


def test_orphaned_request_marker_makes_the_next_ask_wait(monkeypatch, tmp_path):
    """A dead holder leaves its busy marker; the next holder waits out the settle window."""
    import time as _time

    from deepracer_agent import decider_client as dc

    monkeypatch.setattr(dc.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(dc, "ORPHAN_SETTLE_S", 0.3)
    (tmp_path / "deepracer-decider-9999.busy").write_text(f"{_time.time()} 424242")
    slept: list[float] = []
    monkeypatch.setattr(dc.time, "sleep", lambda s: slept.append(s))
    with dc._process_lock("http://127.0.0.1:9999"):
        pass
    assert slept and 0 < slept[0] <= 0.3
    assert (tmp_path / "deepracer-decider-9999.busy").read_text() == "0 0"
    slept.clear()
    with dc._process_lock("http://127.0.0.1:9999"):
        pass
    assert slept == []  # a cleared marker costs nothing
