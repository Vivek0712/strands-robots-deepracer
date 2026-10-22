"""DeciderGate: every row of the CONTRACTS section 7 decision table (five questions, two requests), the
verdict events, the fail-closed paths over a real client, and BargeInStop."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from strands.hooks import BeforeToolCallEvent, HookRegistry
from strands.interrupt import _InterruptState
from strands.interventions import Confirm, Deny, Guide, Proceed, Transform
from strands.interventions.registry import InterventionRegistry

from deepracer_agent.decider_client import DeciderClient, DeciderUnavailable
from deepracer_agent.gate import (
    ENVELOPE_QUESTION,
    FRAME_CLASS_DESCRIPTIONS,
    FRAME_CLASSES,
    FRAME_QUESTION,
    GROUNDED_CRITERIA,
    GROUNDED_QUESTION,
    INTENT_CLASS_DESCRIPTIONS,
    INTENT_CLASSES,
    INTENT_QUESTION,
    NO,
    PERSON_QUESTION,
    VISION_UNAVAILABLE,
    YES,
    BargeInStop,
    DeciderGate,
    Envelope,
    LocalEventLog,
    combine_frame_answers,
    normalise_frame,
    render_conversation,
    text_questions,
)

JPEG = b"\xff\xd8" + b"\x00" * 16 + b"\xff\xd9"
HOP = {"linear": 0.3, "angular": 0.0, "duration": 0.5}


class FakeDecider:
    """Answers from fixed values, or raises, so every table row is one parametrisation.

    ``envelope_p``, ``grounded_p``, ``intent`` and ``intent_p`` are the text request's answers;
    ``person_p`` is the yes/no "is a person visible" answer that rides with the frame; it defaults
    to a clear "no" so the five-way ``cls``/``p`` alone drives the frame rows. Like
    ``DeciderClient`` it has ``ask_many`` (the three text questions in one call) and ``ask_frame``
    (both frame questions in one call); ``LegacyDecider`` below lacks both and exercises the
    envelope-only and two-call fallbacks.
    """

    def __init__(
        self,
        *,
        envelope_p=0.9,
        grounded_p=0.9,
        intent="move_forward",
        intent_p=0.8,
        cls="clear",
        p=0.9,
        fail=None,
        person_p=0.05,
    ):
        self.envelope_p = envelope_p
        self.grounded_p = grounded_p
        self.intent = intent
        self.intent_p = intent_p
        self.cls = cls
        self.p = p
        self.person_p = person_p
        self.fail = fail  # None | "envelope" | "frame"
        self.calls: list[tuple] = []

    def ask_noul(self, question, context, image_bytes=None, **kw):
        self.calls.append(("noul", question, context, image_bytes))
        if image_bytes is not None:
            return {"yes": self.person_p >= 0.5, "probability": self.person_p, "latency_ms": 160}
        if self.fail == "envelope":
            raise DeciderUnavailable("decider timeout after 1.5s")
        return {"yes": self.envelope_p >= 0.5, "probability": self.envelope_p, "latency_ms": 140}

    def ask_many(self, questions, context, image_bytes=None):
        self.calls.append(("many", dict(questions), context, image_bytes))
        if self.fail == "envelope":
            raise DeciderUnavailable("decider timeout after 1.5s")
        classes = list(questions["intent"]["criteria"])
        rest = round((1 - self.intent_p) / (len(classes) - 1), 4)
        probs = {c: (self.intent_p if c == self.intent else rest) for c in classes}
        return {
            "answers": {
                "inside_envelope": {
                    "yes": self.envelope_p >= 0.5,
                    "probability": self.envelope_p,
                    "latency_ms": 140,
                },
                "args_grounded": {
                    "yes": self.grounded_p >= 0.5,
                    "probability": self.grounded_p,
                    "latency_ms": 140,
                },
                "intent": {
                    "class": self.intent,
                    "probability": self.intent_p,
                    "probabilities": probs,
                    "latency_ms": 140,
                },
            },
            "latency_ms": 140,
        }

    def ask_choice(self, question, classes, image_bytes=None, **kw):
        self.calls.append(("choice", question, tuple(classes), image_bytes))
        if self.fail == "frame":
            raise DeciderUnavailable("decider HTTP 500")
        probs = {c: 0.01 for c in classes}
        probs[self.cls] = self.p
        return {"class": self.cls, "probability": self.p, "latency_ms": 180, "probabilities": probs}

    def ask_frame(self, person_question, frame_question, classes, image_bytes, **kw):
        self.calls.append(("frame", person_question, frame_question, tuple(classes), image_bytes))
        if self.fail == "frame":
            raise DeciderUnavailable("decider HTTP 500")
        probs = {c: 0.01 for c in classes}
        probs[self.cls] = self.p
        return {
            "person": {"yes": self.person_p >= 0.5, "probability": self.person_p, "latency_ms": 450},
            "frame": {"class": self.cls, "probability": self.p, "latency_ms": 450, "probabilities": probs},
            "latency_ms": 450,
        }


class LegacyDecider(FakeDecider):
    """A decider with only ``ask_noul``/``ask_choice``: the envelope question alone, then two frame calls."""

    ask_frame = None
    ask_many = None


class Broker:
    def __init__(self, answer=True, raise_timeout=False):
        self.answer = answer
        self.raise_timeout = raise_timeout
        self.asked: list[tuple[str, str]] = []

    async def ask(self, request_id, prompt, timeout_s=30.0):
        self.asked.append((request_id, prompt))
        if self.raise_timeout:
            raise TimeoutError
        return self.answer


@pytest.fixture
def log(tmp_path):
    return LocalEventLog(tmp_path, session="s-test")


def make_gate(decider, log, *, frame=JPEG, **kw):
    return DeciderGate(decider, (lambda: frame), event_log=log, **kw)


CONVERSATION = "user: Hop forward twenty centimetres."
OVER = {"linear": 0.6, "angular": 0.0, "duration": 0.5}  # |linear| 0.6 > 0.3: the deterministic check fails


# -- the decision table (CONTRACTS section 7, rows checked in this order) ----------------------

ROWS = [
    # (label, decider kwargs, args, frame, expected action, expected reason fragment, expected class)
    ("row 13: clear frame, inside envelope, grounded", {}, HOP, JPEG, "Proceed", "inside envelope", "clear"),
    (
        "row 1: decider timeout on the text request",
        {"fail": "envelope"},
        HOP,
        JPEG,
        "Deny",
        VISION_UNAVAILABLE,
        None,
    ),
    (
        "row 1: decider error on the frame request",
        {"fail": "frame"},
        HOP,
        JPEG,
        "Deny",
        VISION_UNAVAILABLE,
        None,
    ),
    ("row 2: no frame", {}, HOP, None, "Deny", VISION_UNAVAILABLE, None),
    ("row 2: empty frame bytes", {}, HOP, b"", "Deny", VISION_UNAVAILABLE, None),
    (
        "row 3: person in frame p>=0.5",
        {"cls": "person_in_frame", "p": 0.97},
        HOP,
        JPEG,
        "Deny",
        "person_in_frame",
        "person_in_frame",
    ),
    (
        "row 3: person in frame at the threshold",
        {"cls": "person_in_frame", "p": 0.5},
        HOP,
        JPEG,
        "Deny",
        "person_in_frame",
        "person_in_frame",
    ),
    (
        "row 3: person in frame below threshold proceeds",
        {"cls": "person_in_frame", "p": 0.4},
        HOP,
        JPEG,
        "Proceed",
        "person_in_frame",
        "person_in_frame",
    ),
    (
        "row 4: off_surface denies at any p",
        {"cls": "off_surface", "p": 0.3},
        HOP,
        JPEG,
        "Deny",
        "off_surface",
        "off_surface",
    ),
    ("row 5: unclear p>=0.65", {"cls": "unclear", "p": 0.9}, HOP, JPEG, "Deny", "unclear", "unclear"),
    (
        "row 6: intent stop",
        {"intent": "stop", "intent_p": 0.9},
        HOP,
        JPEG,
        "Deny",
        "the user asked to stop",
        "clear",
    ),
    (
        "row 6: weak stop proceeds",
        {"intent": "stop", "intent_p": 0.4},
        HOP,
        JPEG,
        "Proceed",
        "inside envelope",
        "clear",
    ),
    (
        "row 6 before row 7: stop beats the envelope violation",
        {"intent": "stop", "intent_p": 0.9},
        OVER,
        JPEG,
        "Deny",
        "the user asked to stop",
        "clear",
    ),
    (
        "row 7: deterministic envelope violation confirms",
        {},
        OVER,
        JPEG,
        "Confirm",
        "|linear| 0.6 > 0.3",
        "clear",
    ),
    (
        "row 7 before row 11: violation and obstacle confirm",
        {"cls": "obstacle_near"},
        OVER,
        JPEG,
        "Confirm",
        "outside envelope",
        "obstacle_near",
    ),
    (
        "row 8: envelope no per decider guides",
        {"envelope_p": 0.1},
        HOP,
        JPEG,
        "Guide",
        "outside envelope per decider",
        "clear",
    ),
    (
        "row 9: arguments not grounded guides",
        {"grounded_p": 0.2},
        HOP,
        JPEG,
        "Guide",
        "arguments not grounded",
        "clear",
    ),
    (
        "row 10: intent question guides",
        {"intent": "question", "intent_p": 0.9},
        HOP,
        JPEG,
        "Guide",
        "intent question",
        "clear",
    ),
    (
        "row 10: intent unrelated guides",
        {"intent": "unrelated", "intent_p": 0.7},
        HOP,
        JPEG,
        "Guide",
        "intent unrelated",
        "clear",
    ),
    (
        "row 10: weak question proceeds",
        {"intent": "question", "intent_p": 0.4},
        HOP,
        JPEG,
        "Proceed",
        "inside envelope",
        "clear",
    ),
    (
        "row 11: obstacle near guides at half speed",
        {"cls": "obstacle_near", "p": 0.8},
        HOP,
        JPEG,
        "Guide",
        "half speed",
        "obstacle_near",
    ),
    (
        "row 11 before row 12: obstacle and an unsure envelope guide",
        {"cls": "obstacle_near", "envelope_p": 0.5},
        HOP,
        JPEG,
        "Guide",
        "half speed",
        "obstacle_near",
    ),
    (
        "row 12: envelope unsure confirms",
        {"envelope_p": 0.5},
        HOP,
        JPEG,
        "Confirm",
        "unclear: inside=0.50",
        "clear",
    ),
    (
        "row 12: grounding unsure confirms",
        {"grounded_p": 0.6},
        HOP,
        JPEG,
        "Confirm",
        "grounded=0.60",
        "clear",
    ),
    ("row 12: envelope at NO confirms", {"envelope_p": 0.35}, HOP, JPEG, "Confirm", "unclear", "clear"),
    (
        "row 13: both at YES proceed",
        {"envelope_p": 0.65, "grounded_p": 0.65},
        HOP,
        JPEG,
        "Proceed",
        "inside envelope",
        "clear",
    ),
    (
        "row 3 before row 8: envelope no but person denies",
        {"envelope_p": 0.1, "cls": "person_in_frame"},
        HOP,
        JPEG,
        "Deny",
        "person_in_frame",
        "person_in_frame",
    ),
]


@pytest.mark.parametrize(
    ("label", "dkw", "args", "frame", "action", "reason", "cls"), ROWS, ids=[r[0] for r in ROWS]
)
async def test_decision_table(label, dkw, args, frame, action, reason, cls, log):
    gate = make_gate(FakeDecider(**dkw), log, frame=frame)
    decision = await gate.decide(dict(args), request_id="req-1", conversation=CONVERSATION)
    assert decision.action == action, decision
    assert reason in decision.reason
    verdicts = log.read("verdict")
    assert verdicts, "every decision emits at least one verdict"
    for v in verdicts:
        p = v["payload"]
        assert set(p) == {
            "request_id",
            "stage",
            "action",
            "reason",
            "class",
            "probability",
            "latency_ms",
            "frame_ref",
        }
        assert p["request_id"] == "req-1"
        assert p["stage"] in ("envelope", "frame")
        assert p["action"] in ("Proceed", "Guide", "Confirm", "Deny")
        assert isinstance(p["latency_ms"], int)
        assert v["type"] == "verdict" and v["session"] == "s-test"
    frame_verdicts = [v["payload"] for v in verdicts if v["payload"]["stage"] == "frame"]
    if cls is not None:
        assert frame_verdicts[-1]["class"] == cls
    if action == "Deny" and reason == VISION_UNAVAILABLE:
        assert verdicts[-1]["payload"]["reason"] == VISION_UNAVAILABLE
    assert gate.last_verdict["action"] == action


async def test_malformed_decider_body_fails_closed(log):
    """A real DeciderClient over a server that answers nonsense -> Deny vision unavailable."""
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"answers": {"q": {"type": "noul", "noul": "???"}}})
    )
    gate = make_gate(DeciderClient("http://d.test", timeout_s=0.2, transport=transport), log)
    decision = await gate.decide(dict(HOP), request_id="r")
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


async def test_slow_decider_over_budget_fails_closed(log):
    def slow(request):
        raise httpx.ReadTimeout("1.5 s budget exceeded", request=request)

    gate = make_gate(DeciderClient("http://d.test", timeout_s=0.05, transport=httpx.MockTransport(slow)), log)
    decision = await gate.decide(dict(HOP), request_id="r")
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


async def test_frame_source_exception_is_no_frame(log):
    def broken():
        raise OSError("camera unplugged")

    gate = DeciderGate(FakeDecider(), broken, event_log=log)
    decision = await gate.decide(dict(HOP))
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE
    assert gate.decider.calls == [], "no decider call without a frame"


async def test_async_frame_source_and_capture_frame_dict(log):
    import base64

    async def capture():
        return {"frame_ref": "frames/000007.jpg", "bytes_b64": base64.b64encode(JPEG).decode()}

    gate = DeciderGate(FakeDecider(), capture, event_log=log)
    decision = await gate.decide(dict(HOP), request_id="r7")
    assert decision.action == "Proceed"
    assert all(v.frame_ref == "frames/000007.jpg" for v in decision.verdicts)


def test_normalise_frame_shapes():
    assert normalise_frame(None) is None
    assert normalise_frame(b"") is None
    assert normalise_frame(JPEG).jpeg == JPEG
    assert normalise_frame({"bytes": JPEG, "frame_ref": "x"}).frame_ref == "x"
    assert normalise_frame({"bytes_b64": "!!!not base64"}) is None
    assert normalise_frame(42) is None


async def test_envelope_deterministic_check_forces_confirm_even_if_decider_says_yes(log):
    decider = FakeDecider()
    gate = make_gate(decider, log, envelope=Envelope(max_linear=0.3, max_duration_s=2.0))
    decision = await gate.decide({"linear": 0.6, "angular": 0.0, "duration": 0.5}, request_id="r")
    assert decision.action == "Confirm"
    assert "|linear| 0.6 > 0.3" in decision.reason
    ctx = decider.calls[0][2]
    assert "0.6 > 0.3" in ctx["deterministic_check"]
    assert "directions: forward or backward" in ctx["envelope"]


def test_envelope_violations_and_directions():
    env = Envelope(max_linear=0.3, max_duration_s=2.0, allowed_directions=("forward",))
    assert env.violations(0.3, 0.0, 0.5) == []
    assert "direction backward not allowed" in env.violations(-0.3, 0.0, 0.5)
    assert any("duration" in v for v in env.violations(0.3, 0.0, 3.0))
    assert "duration must be positive" in env.violations(0.3, 0.0, 0.0)
    assert any("angular" in v for v in env.violations(0.1, 2.0, 0.5))
    assert Envelope.direction(0.0) == "none"
    assert env.to_dict()["allowed_directions"] == ["forward"]


async def test_frame_question_uses_the_five_contract_classes(log):
    decider = FakeDecider()
    await make_gate(decider, log).decide(dict(HOP))
    frame_call = next(c for c in decider.calls if c[0] == "frame")
    assert frame_call[1:4] == (PERSON_QUESTION, FRAME_QUESTION, FRAME_CLASSES)
    assert frame_call[4] == JPEG


async def test_legacy_decider_is_asked_the_person_question_and_the_choice_separately(log):
    decider = LegacyDecider()
    decision = await make_gate(decider, log).decide(dict(HOP))
    assert decision.action == "Proceed"
    kinds = [c[0] for c in decider.calls]
    assert kinds == ["noul", "noul", "choice"], (
        "envelope, then person yes/no with the frame, then the five-way"
    )
    assert decider.calls[1][1] == PERSON_QUESTION and decider.calls[1][3] == JPEG
    assert decider.calls[2][2] == FRAME_CLASSES
    assert decision.verdicts[-1].latency_ms == 160 + 180, "two calls: latencies are summed"


# -- the text request: five questions, two requests ----------------------------------------------


async def test_text_request_carries_the_three_questions_and_the_conversation(log):
    decider = FakeDecider()
    decision = await make_gate(decider, log).decide(dict(HOP), request_id="r", conversation=CONVERSATION)
    assert decision.action == "Proceed"
    many = [c for c in decider.calls if c[0] == "many"]
    assert len(many) == 1, "one text request, one forward pass"
    _, questions, state, image = many[0]
    assert image is None
    assert list(questions) == ["inside_envelope", "args_grounded", "intent"]
    assert questions["inside_envelope"] == {"type": "noul", "instructions": ENVELOPE_QUESTION}
    assert questions["args_grounded"]["instructions"] == GROUNDED_QUESTION
    assert questions["args_grounded"]["criteria"] == GROUNDED_CRITERIA
    assert questions["intent"] == {
        "type": "choice",
        "instructions": INTENT_QUESTION,
        "criteria": INTENT_CLASS_DESCRIPTIONS,
    }
    assert state["conversation"] == CONVERSATION
    assert state["command"]["tool"] == "drive_deepracer" and state["deterministic_check"] == "ok"
    assert "directions: forward or backward" in state["envelope"]
    assert "grounded (p=0.90)" in decision.reason and "intent move_forward (p=0.80)" in decision.reason
    envelope = next(v for v in decision.verdicts if v.stage == "envelope")
    assert envelope.probability == 0.9 and envelope.latency_ms == 140


async def test_text_questions_match_the_drop_in_recipe():
    """The on-car gate and patterns/strands/tool_call_intervention.py ask the same grounding questions."""
    from patterns.strands.tool_call_intervention import QUESTIONS
    from patterns.strands.tool_call_intervention import YES as PATTERN_YES

    assert text_questions()["args_grounded"]["instructions"] == QUESTIONS["args_grounded"]["instructions"]
    assert text_questions()["args_grounded"]["criteria"] == QUESTIONS["args_grounded"]["criteria"]
    assert text_questions()["intent"] == QUESTIONS["intent"]
    assert YES == PATTERN_YES == 0.65 and NO == 0.35


async def test_without_a_conversation_only_the_envelope_question_is_asked(log):
    """The kiosk and a plan step have no user words to ground against."""
    decider = FakeDecider(grounded_p=0.0, intent="stop", intent_p=0.99)
    decision = await make_gate(decider, log).decide(dict(HOP), request_id="r")
    assert decision.action == "Proceed", "the grounding rows need the grounding answers"
    assert [c[0] for c in decider.calls] == ["noul", "frame"]
    assert decider.calls[0][1] == ENVELOPE_QUESTION
    assert "grounded" not in decision.reason


async def test_before_tool_call_renders_the_agent_messages_into_the_text_request(log):
    decider = FakeDecider()
    gate = make_gate(decider, log)
    agent = SimpleNamespace(
        _interrupt_state=_InterruptState(),
        messages=[
            {"role": "user", "content": [{"text": "Hop forward twenty centimetres."}]},
            {"role": "assistant", "content": [{"toolUse": {"name": "drive_deepracer"}}]},
        ],
    )
    action = await gate.before_tool_call(_event(agent=agent))
    assert isinstance(action, Proceed)
    state = next(c for c in decider.calls if c[0] == "many")[2]
    assert state["conversation"] == "user: Hop forward twenty centimetres."


def test_render_conversation_is_bounded():
    messages = [{"role": "user", "content": [{"text": f"m{i} " + "x" * 400}]} for i in range(40)]
    text = render_conversation(messages)
    assert len(text) <= 2000 and text.startswith("...") and text.endswith("x")
    assert "m39" in text and "m0 " not in text, "the newest messages survive"
    assert render_conversation([]) == "(no conversation yet)"
    assert render_conversation(None) == "(no conversation yet)"
    assert render_conversation([{"role": "user", "content": [{"image": {}}]}]) == "(no conversation yet)"


@pytest.mark.parametrize(
    ("label", "patch"),
    [
        ("intent class outside the option set", {"intent": "banana"}),
        ("intent probability NaN", {"intent_p": float("nan")}),
        ("envelope probability NaN", {"envelope_p": float("nan")}),
        ("grounded probability above one", {"grounded_p": 1.7}),
        ("grounded probability a string", {"grounded_p": "0.9"}),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
async def test_malformed_text_answers_fail_closed_through_a_real_client(label, patch, log):
    """DeciderClient.ask_many over a server answering nonsense on one of the three -> Deny."""
    values = {"envelope_p": 0.9, "grounded_p": 0.9, "intent": "move_forward", "intent_p": 0.8}
    values.update(patch)

    def handler(request):
        body = json.loads(request.content)
        if "intent" in body["questions"]:
            probs = {c: 0.05 for c in INTENT_CLASSES}
            probs["move_forward"] = values["intent_p"]
            answers = {
                "inside_envelope": {"type": "noul", "noul": values["envelope_p"]},
                "args_grounded": {"type": "noul", "noul": values["grounded_p"]},
                "intent": {"type": "choice", "choice": values["intent"], "probabilities": probs},
            }
        else:
            answers = {
                "person": {"type": "noul", "noul": 0.05},
                "frame": {
                    "type": "choice",
                    "choice": "clear",
                    "probabilities": {c: 0.2 for c in FRAME_CLASSES},
                },
            }
        return httpx.Response(
            200,
            content=json.dumps({"answers": answers}).encode(),
            headers={"content-type": "application/json"},
        )

    gate = make_gate(DeciderClient("http://d.test", timeout_s=1, transport=httpx.MockTransport(handler)), log)
    decision = await gate.decide(dict(HOP), request_id="r", conversation=CONVERSATION)
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE
    assert [v.stage for v in decision.verdicts] == ["envelope"], "no frame request after a bad text answer"


async def test_nan_choice_probability_on_the_frame_fails_closed(log):
    """The round-1 hole: a NaN on the chosen class defeated ``p >= bar`` and proceeded."""

    def handler(request):
        body = json.loads(request.content)
        if "intent" in body["questions"]:
            answers = {
                "inside_envelope": {"type": "noul", "noul": 0.9},
                "args_grounded": {"type": "noul", "noul": 0.9},
                "intent": {
                    "type": "choice",
                    "choice": "move_forward",
                    "probabilities": {c: 0.2 for c in INTENT_CLASSES},
                },
            }
        else:
            probs = {c: 0.01 for c in FRAME_CLASSES}
            probs["person_in_frame"] = float("nan")
            answers = {
                "person": {"type": "noul", "noul": 0.05},
                "frame": {"type": "choice", "choice": "person_in_frame", "probabilities": probs},
            }
        return httpx.Response(
            200,
            content=json.dumps({"answers": answers}).encode(),
            headers={"content-type": "application/json"},
        )

    gate = make_gate(DeciderClient("http://d.test", timeout_s=1, transport=httpx.MockTransport(handler)), log)
    decision = await gate.decide(dict(HOP), request_id="r", conversation=CONVERSATION)
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


def test_warm_gate_sends_the_full_text_request():
    from deepracer_agent.gate import warm_gate

    decider = FakeDecider()
    out = warm_gate(decider)
    assert out == {"envelope_ms": 140, "frame_ms": 450}
    kinds = [c[0] for c in decider.calls]
    assert kinds == ["many", "frame"], "the warm-up primes the same two request shapes the gate sends"
    assert decider.calls[0][2]["conversation"]


# -- the person yes/no (calibration 2026-10-14) -------------------------------------------------


def test_frame_question_wording_is_pinned():
    """Changing any of these means re-running ``python -m deepracer_agent.calibrate_frames`` and
    recording the result in docs/results; the calibration of 2026-10-14 showed that sharper
    descriptions push ``unclear`` below the 0.5 threshold on real person frames."""
    assert FRAME_QUESTION == "What is directly in front of the car in this camera frame?"
    assert PERSON_QUESTION == "Is a person (any part of a human body) visible in this camera frame?"
    assert FRAME_CLASS_DESCRIPTIONS == {
        "clear": "the pen floor ahead is empty and the car can move",
        "obstacle_near": "an object is close in front of the bumper",
        "person_in_frame": "a person, or part of one (foot, leg, hand), is in the camera view",
        "off_surface": "the car is at or past the edge of the pen surface",
        "unclear": "the image is dark, blurred, blocked or otherwise unreadable",
    }
    assert tuple(FRAME_CLASS_DESCRIPTIONS) == FRAME_CLASSES, "option order is part of the calibrated ask"


@pytest.mark.parametrize(
    ("person_p", "cls", "p", "expected"),
    [
        (0.95, "unclear", 0.67, ("person_in_frame", 0.95, "five-way said unclear 0.67")),  # the car, tonight
        (0.95, "clear", 0.60, ("person_in_frame", 0.95, "five-way said clear 0.60")),
        (0.64, "person_in_frame", 0.56, ("person_in_frame", 0.64, "five-way said person_in_frame 0.56")),
        (0.50, "clear", 0.50, ("person_in_frame", 0.50, "five-way said clear 0.50")),  # at the threshold
        (0.60, "person_in_frame", 0.97, ("person_in_frame", 0.97, None)),  # five-way already surer
        (0.49, "clear", 0.60, ("clear", 0.60, None)),  # below threshold: five-way stands
        (0.07, "unclear", 0.62, ("unclear", 0.62, None)),  # frame 000004: deny holds as unclear
        (0.05, "person_in_frame", 0.56, ("person_in_frame", 0.56, None)),  # a "no" never lowers a deny
        (0.05, "obstacle_near", 0.80, ("obstacle_near", 0.80, None)),
    ],
)
def test_combine_frame_answers_is_monotone_toward_deny(person_p, cls, p, expected):
    assert combine_frame_answers(person_p, cls, p, 0.5) == expected


async def test_person_yes_overrides_unclear_and_names_the_right_reason(log):
    """The booth model's answer on the real frames: unclear 0.65 from the five-way, person 0.95
    from the yes/no. The gate denies as person_in_frame so the Apology speaks the right reason."""
    gate = make_gate(FakeDecider(cls="unclear", p=0.65, person_p=0.95), log)
    decision = await gate.decide(dict(HOP), request_id="r")
    assert decision.action == "Deny"
    frame = decision.verdicts[-1]
    assert (frame.cls, frame.probability) == ("person_in_frame", 0.95)
    assert (
        frame.reason
        == "person_in_frame (p=0.95): stopping; someone is in front of me (five-way said unclear 0.65)"
    )
    logged = log.last("verdict")["payload"]
    assert logged["class"] == "person_in_frame" and logged["probability"] == 0.95
    assert set(logged) == {
        "request_id",
        "stage",
        "action",
        "reason",
        "class",
        "probability",
        "latency_ms",
        "frame_ref",
    }


async def test_person_yes_on_a_clear_five_way_still_denies(log):
    gate = make_gate(FakeDecider(cls="clear", p=0.9, person_p=0.8), log)
    decision = await gate.decide(dict(HOP))
    assert decision.action == "Deny" and decision.verdicts[-1].cls == "person_in_frame"


async def test_person_no_never_weakens_the_five_way_deny(log):
    gate = make_gate(FakeDecider(cls="person_in_frame", p=0.56, person_p=0.05), log)
    decision = await gate.decide(dict(HOP))
    assert decision.action == "Deny" and decision.verdicts[-1].probability == 0.56


async def test_person_yes_cannot_rescue_a_failed_frame_request(log):
    """Both answers come from one request; if it fails there is no person answer to act on."""
    gate = make_gate(FakeDecider(cls="unclear", p=0.65, person_p=0.95, fail="frame"), log)
    decision = await gate.decide(dict(HOP))
    assert decision.action == "Deny" and decision.reason == VISION_UNAVAILABLE


async def test_person_pre_check_through_a_real_client_in_one_request(log):
    """DeciderClient sends both questions in one POST; the gate reads both answers from it."""
    seen: dict = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "answers": {
                    "person": {"type": "noul", "noul": 0.95},
                    "frame": {
                        "type": "choice",
                        "choice": "unclear",
                        "probabilities": {c: (0.65 if c == "unclear" else 0.0875) for c in FRAME_CLASSES},
                    },
                }
                if "person" in json.loads(request.content)["questions"]
                else {"q": {"type": "noul", "noul": 0.9}}
            },
        )

    gate = make_gate(DeciderClient("http://d.test", timeout_s=1, transport=httpx.MockTransport(handler)), log)
    decision = await gate.decide(dict(HOP), request_id="r")
    assert decision.action == "Deny" and decision.verdicts[-1].cls == "person_in_frame"
    questions = seen["body"]["questions"]
    assert set(questions) == {"person", "frame"}
    assert questions["person"] == {"type": "noul", "instructions": PERSON_QUESTION}
    assert questions["frame"]["instructions"] == FRAME_QUESTION
    assert questions["frame"]["criteria"] == FRAME_CLASS_DESCRIPTIONS
    assert len(seen["body"]["images"]) == 1


# -- through the strands intervention registry -------------------------------------------------


def _event(tool_name="drive_deepracer", args=None, agent=None):
    agent = agent or SimpleNamespace(_interrupt_state=_InterruptState())
    return BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"toolUseId": "tooluse_1", "name": tool_name, "input": dict(args or HOP)},
        invocation_state={},
    )


async def _dispatch(gate, event):
    registry = HookRegistry()
    InterventionRegistry([gate], registry)
    await registry.invoke_callbacks_async(event)
    return event


async def test_other_tools_proceed_without_touching_the_decider(log):
    decider = FakeDecider()
    gate = make_gate(decider, log)
    action = await gate.before_tool_call(_event("stop_deepracer", {}))
    assert isinstance(action, Proceed)
    assert decider.calls == [] and log.read("verdict") == []


async def test_deny_sets_cancel_tool_with_reason(log):
    gate = make_gate(FakeDecider(cls="person_in_frame", p=0.97), log)
    event = await _dispatch(gate, _event())
    assert isinstance(event.cancel_tool, str) and event.cancel_tool.startswith(
        "DENIED: person_in_frame (p=0.97)"
    )


async def test_guide_default_cancels_with_half_speed_feedback(log):
    gate = make_gate(FakeDecider(cls="obstacle_near", p=0.8), log)
    action = await gate.before_tool_call(_event())
    assert isinstance(action, Guide) and "linear <= 0.15" in action.feedback
    event = await _dispatch(gate, _event())
    assert event.cancel_tool.startswith("GUIDANCE:") and "0.15" in event.cancel_tool


async def test_guide_transform_mode_halves_linear_in_place(log):
    gate = make_gate(FakeDecider(cls="obstacle_near", p=0.8), log, obstacle_mode="transform")
    action = await gate.before_tool_call(_event())
    assert isinstance(action, Transform)
    event = await _dispatch(gate, _event())
    assert event.cancel_tool is False
    assert event.tool_use["input"]["linear"] == pytest.approx(0.15)


async def test_confirm_without_broker_returns_bare_confirm(log):
    gate = make_gate(FakeDecider(), log)
    action = await gate.before_tool_call(_event(args=OVER))
    assert isinstance(action, Confirm) and action.response is None and "Approve?" in action.prompt


@pytest.mark.parametrize(
    ("broker", "decision", "cancelled"),
    [
        (Broker(answer=True), "approved", False),
        (Broker(answer=False), "denied", True),
        (Broker(raise_timeout=True), "timeout", True),
    ],
    ids=["approved", "denied", "timeout"],
)
async def test_confirm_with_broker_is_inline_and_logs_approval(log, broker, decision, cancelled):
    gate = make_gate(FakeDecider(), log, approval=broker)
    event = await _dispatch(gate, _event(args=OVER))
    assert bool(event.cancel_tool) is cancelled
    if cancelled:
        assert event.cancel_tool.startswith("CONFIRMATION_FAILED:")
    approvals = log.read("approval")
    assert approvals and approvals[-1]["payload"] == {
        "request_id": "tooluse_1",
        "decision": decision,
        "by": "operator",
    }
    assert broker.asked and broker.asked[0][0] == "tooluse_1"


async def test_confirm_through_the_broker_with_the_five_question_request(log):
    """The agent path: messages rendered into the text request, row 7 Confirm resolved by the broker."""
    broker = Broker(answer=True)
    decider = FakeDecider()
    gate = make_gate(decider, log, approval=broker)
    agent = SimpleNamespace(
        _interrupt_state=_InterruptState(),
        messages=[{"role": "user", "content": [{"text": "Go forward fast for two seconds."}]}],
    )
    event = await _dispatch(gate, _event(args=OVER, agent=agent))
    assert event.cancel_tool is False, "approved: the hop runs"
    many = [c for c in decider.calls if c[0] == "many"]
    assert len(many) == 1 and list(many[0][1]) == ["inside_envelope", "args_grounded", "intent"]
    assert many[0][2]["conversation"] == "user: Go forward fast for two seconds."
    assert broker.asked and "|linear| 0.6 > 0.3" in broker.asked[0][1]
    assert log.read("approval")[-1]["payload"]["decision"] == "approved"
    envelope = [v for v in log.read("verdict") if v["payload"]["stage"] == "envelope"][-1]["payload"]
    assert envelope["action"] == "Confirm" and envelope["reason"].startswith(
        "outside envelope: |linear| 0.6 > 0.3"
    )


async def test_handler_exception_is_deny_via_on_error(log):
    class Exploding(FakeDecider):
        def ask_noul(self, *a, **k):
            raise RuntimeError("unexpected")

    gate = make_gate(Exploding(), log)
    assert gate.on_error == "deny"
    event = await _dispatch(gate, _event())
    assert event.cancel_tool.startswith("DENIED: vision unavailable")


async def test_verdicts_also_flow_through_the_car_teams_event_log(tmp_path):
    events = pytest.importorskip("deepracer_agent.events")
    log = events.EventLog(run_dir=tmp_path, session="s-car", portal_url="")
    gate = make_gate(FakeDecider(), log)
    await gate.decide(dict(HOP), request_id="r")
    lines = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["type"] for e in lines] == ["verdict", "verdict"]
    assert lines[0]["payload"]["stage"] == "envelope" and lines[1]["payload"]["stage"] == "frame"


# -- BargeInStop ---------------------------------------------------------------------------------


class Runtime:
    def __init__(self, fail=False):
        self.stops = 0
        self.fail = fail
        self.driving = True

    async def stop_all(self):
        await asyncio.sleep(0.005)
        self.stops += 1
        self.driving = False
        if self.fail:
            raise RuntimeError("rosbridge gone")

    def is_driving(self):
        return self.driving


async def test_barge_in_trigger_emits_voice_and_stop_with_ms_timestamps(log):
    rt = Runtime()
    hook = BargeInStop(rt, log, beat="red_light")
    stamp = await hook.trigger()
    assert rt.stops == 1
    voice = log.read("voice")[-1]
    stop = log.read("stop")[-1]
    assert voice["payload"]["event"] == "barge_in" and isinstance(voice["payload"]["t_ms"], int)
    assert voice["beat"] == "red_light"
    assert stop["payload"] == {"request_id": None, "cause": "barge_in", "latency_ms": stamp["latency_ms"]}
    assert 0 <= stamp["latency_ms"] < 1000 and stamp["stop_t_ms"] >= stamp["t_ms"]
    assert voice["seq"] < stop["seq"]


async def test_barge_in_hook_registers_on_bidi_barge_in_event(log):
    from strands.bidi.hooks import BidiBargeInEvent

    rt = Runtime()
    hook = BargeInStop(rt, log)
    registry = HookRegistry()
    registry.add_hook(hook)
    await registry.invoke_callbacks_async(BidiBargeInEvent(agent=SimpleNamespace()))
    assert rt.stops == 1 and hook.count == 1


async def test_barge_in_stop_failure_still_logs_stop_and_error(log):
    hook = BargeInStop(Runtime(fail=True), log)
    stamp = await hook.trigger()
    assert stamp["error"] == "rosbridge gone"
    assert [e["type"] for e in log.read()] == ["voice", "stop", "error"]


async def test_user_transcript_start_stops_only_while_driving(log):
    from strands.bidi.types.events import BidiTranscriptStartEvent

    rt = Runtime()
    hook = BargeInStop(rt, log)
    await hook(BidiTranscriptStartEvent(role="user", content_id="c1"))
    assert rt.stops == 1
    assert [e["payload"]["event"] for e in log.read("voice")] == ["speech_start", "barge_in"]
    await hook(BidiTranscriptStartEvent(role="user", content_id="c2"))
    assert rt.stops == 1, "not driving any more: speech start is only logged"
    await hook(BidiTranscriptStartEvent(role="assistant", content_id="c3"))
    assert len(log.read("voice")) == 3


def test_deny_action_reason_is_the_contract_string():
    assert Deny(reason=VISION_UNAVAILABLE).reason == "vision unavailable"


async def test_operator_can_switch_the_gate_off_and_every_hop_proceeds_with_a_named_verdict(tmp_path) -> None:
    """Gate off: no frame grab, no decider call, one Proceed verdict that says the operator did it."""
    from deepracer_agent.gate import GATE_OFF, DeciderGate, LocalEventLog

    class Boom:
        def ask_noul(self, *a, **k):
            raise AssertionError("decider must not be asked with the gate off")

        ask_choice = ask_noul
        ask_frame = ask_noul

    async def no_frame():
        raise AssertionError("no frame grab with the gate off")

    log = LocalEventLog(tmp_path, session="s-gate-off")
    gate = DeciderGate(Boom(), no_frame, event_log=log)
    gate.enabled = False
    d = await gate.decide({"linear": 0.3, "angular": 0.0, "duration": 0.5}, request_id="r1")
    assert d.action == "Proceed" and d.reason == GATE_OFF
    assert [v.action for v in d.verdicts] == ["Proceed"] and d.verdicts[0].reason == GATE_OFF
    rows = [r for r in log.read() if r["type"] == "verdict"]
    assert rows and rows[-1]["payload"]["reason"] == GATE_OFF
    gate.enabled = True  # back on: the decider is asked again (and Boom raises -> fail closed)
    d2 = await gate.decide({"linear": 0.3, "angular": 0.0, "duration": 0.5}, request_id="r2")
    assert d2.action == "Deny"


@pytest.mark.parametrize(
    ("p", "expect"), [(0.54, "Proceed"), (0.64, "Proceed"), (0.65, "Deny"), (0.90, "Deny")]
)
async def test_weak_unclear_proceeds_and_strong_unclear_denies(tmp_path, p, expect) -> None:
    from deepracer_agent.gate import DeciderGate, LocalEventLog

    class Decider:
        def ask_noul(self, question, context, image_bytes=None, **kw):
            return {"yes": True, "probability": 0.9, "latency_ms": 1}

        def ask_frame(self, person_q, frame_q, classes, image_bytes, **kw):
            return {
                "person": {"yes": False, "probability": 0.05, "latency_ms": 1},
                "frame": {
                    "class": "unclear",
                    "probability": p,
                    "probabilities": {"unclear": p},
                    "latency_ms": 1,
                },
                "latency_ms": 2,
            }

    async def frame():
        return b"\xff\xd8" + b"x" * 10 + b"\xff\xd9"

    gate = DeciderGate(Decider(), frame, event_log=LocalEventLog(tmp_path, session="s-unclear"))
    d = await gate.decide({"linear": 0.3, "angular": 0.0, "duration": 0.5}, request_id="r")
    assert d.action == expect, d.reason
    if expect == "Proceed":
        assert "weak call" in d.verdicts[-1].reason


async def test_advisory_mode_shows_the_verdict_but_never_blocks(tmp_path) -> None:
    from deepracer_agent.gate import DeciderGate, LocalEventLog

    class Decider:
        def ask_noul(self, question, context, image_bytes=None, **kw):
            return {"yes": True, "probability": 0.9, "latency_ms": 1}

        def ask_frame(self, person_q, frame_q, classes, image_bytes, **kw):
            return {
                "person": {"yes": True, "probability": 0.95, "latency_ms": 1},
                "frame": {"class": "unclear", "probability": 0.6, "probabilities": {}, "latency_ms": 1},
                "latency_ms": 2,
            }

    async def frame():
        return b"\xff\xd8" + b"x" * 10 + b"\xff\xd9"

    log = LocalEventLog(tmp_path, session="s-advisory")
    gate = DeciderGate(Decider(), frame, event_log=log)
    gate.mode = "advisory"
    assert gate.enabled is True
    decision = await gate.decide({"linear": 0.3, "angular": 0.0, "duration": 0.5}, request_id="r")
    assert decision.action == "Deny"  # the verdict itself is unchanged and shown
    action = await gate._to_action(decision, None)
    assert type(action).__name__ == "Proceed" and "would have said Deny" in (action.reason or "")
    rows = log.read()
    assert all(r["payload"].get("advisory") is True for r in rows if r["type"] == "verdict")
    assert not [r for r in rows if r["type"] == "stop"]
    gate.enabled = False
    assert gate.mode == "off"
    gate.mode = "enforce"
    action2 = await gate._to_action(decision, None)
    assert type(action2).__name__ == "Deny"
