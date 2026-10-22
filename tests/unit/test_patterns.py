"""patterns/strands: question builders, both decision tables row by row, the refusal tables (every input
the gates refuse and the string they return), the budget, the registry path, and the wire shape."""

from __future__ import annotations

import asyncio
import base64
import http.client
import io
import json
import time
from types import SimpleNamespace

import pytest
from strands.hooks import BeforeToolCallEvent, HookRegistry
from strands.interrupt import _InterruptState
from strands.interventions import Confirm, Deny, Guide, Proceed
from strands.interventions.registry import InterventionRegistry

from patterns.strands import _client
from patterns.strands._client import Decider, ServerUnavailable
from patterns.strands.frame_intervention import (
    FRAME_CLASS_DESCRIPTIONS,
    FRAME_CLASSES,
    FRAME_QUESTIONS,
    OBSTACLE_NEAR,
    OFF_SURFACE,
    PERSON_IN_FRAME,
    VISION_UNAVAILABLE,
    FrameGate,
)
from patterns.strands.frame_intervention import (
    QUESTIONS as FRAME_QUESTIONS_ALIAS,
)
from patterns.strands.tool_call_intervention import (
    ARGS_INVENTED,
    DECIDER_UNAVAILABLE,
    INTENT_CLASSES,
    MOTION_BUDGET_S,
    NO_MOVEMENT_ASKED,
    QUESTIONS,
    STOP_REQUESTED,
    YES,
    Envelope,
    MotionGate,
    fake_event,
    judge,
    probability,
)

JPEG = b"\xff\xd8" + b"\x00" * 16 + b"\xff\xd9"
GROUNDED = {"distance_m": 0.2, "heading_deg": 0.0}
NAN = float("nan")


class ScriptedDecider:
    """Answers from fixed values or raises; records what it was asked. No sockets."""

    def __init__(self, answers=None, *, fail: Exception | None = None, delay_s: float = 0.0):
        self.answers = answers or {}
        self.fail = fail
        self.delay_s = delay_s
        self.calls: list[tuple] = []
        self.latency_ms = 123.4

    def ask(self, state, questions, images=None):
        self.calls.append((state, dict(questions), images))
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.fail is not None:
            raise self.fail
        return self.answers


def motion_answers(inside=0.95, grounded=0.95, intent="move_forward", intent_p=0.8, **intent_extra):
    rest = (1 - intent_p) / 4
    probs = {c: (intent_p if c == intent else rest) for c in QUESTIONS["intent"]["criteria"]}
    intent_answer = {"type": "choice", "choice": intent, "probabilities": probs, "confidence": intent_p}
    intent_answer.update(intent_extra)
    return {
        "inside_envelope": {"type": "noul", "noul": inside},
        "args_grounded": {"type": "noul", "noul": grounded},
        "intent": intent_answer,
    }


def frame_answers(person=0.05, cls="clear", p=0.93, **frame_extra):
    rest = (1 - p) / 4
    probs = {c: (p if c == cls else rest) for c in FRAME_CLASSES}
    frame_answer = {"type": "choice", "choice": cls, "probabilities": probs, "confidence": p}
    frame_answer.update(frame_extra)
    return {"person": {"type": "noul", "noul": person}, "frame": frame_answer}


# -- question builders ------------------------------------------------------------------------


def test_noul_builder_is_upstream_shaped():
    assert Decider.noul("q") == {"type": "noul", "instructions": "q"}
    assert Decider.noul("q", {"true": "t", "false": "f"}) == {
        "type": "noul",
        "instructions": "q",
        "criteria": {"true": "t", "false": "f"},
    }


def test_choice_and_score_builders():
    assert Decider.choice("q", {"a": "A", "b": "B"}) == {
        "type": "choice",
        "instructions": "q",
        "criteria": {"a": "A", "b": "B"},
    }
    assert Decider.score("q", ["lo", "mid", "hi"]) == {
        "type": "score",
        "instructions": "q",
        "criteria": ["lo", "mid", "hi"],
    }
    with pytest.raises(ValueError):
        Decider.choice("q", {"only": "one"})
    with pytest.raises(ValueError):
        Decider.score("q", ["one"])


def test_question_sets_are_typed_and_json_serialisable():
    assert list(QUESTIONS) == ["inside_envelope", "args_grounded", "intent"]
    assert QUESTIONS["inside_envelope"]["type"] == "noul"
    assert QUESTIONS["intent"]["type"] == "choice"
    assert INTENT_CLASSES == ("move_forward", "turn", "stop", "question", "unrelated")
    assert set(FRAME_QUESTIONS) == {"person", "frame"}
    assert FRAME_QUESTIONS["frame"]["criteria"] == FRAME_CLASS_DESCRIPTIONS
    assert FRAME_CLASSES == ("clear", "obstacle_near", "person_in_frame", "off_surface", "unclear")
    assert FRAME_QUESTIONS_ALIAS is FRAME_QUESTIONS, "the upstream name is an alias of the same dict"
    json.dumps(QUESTIONS)
    json.dumps(FRAME_QUESTIONS)


def test_question_wording_is_pinned():
    """The strings the decider is asked; changing one means re-measuring (docs/results)."""
    assert QUESTIONS["inside_envelope"]["instructions"] == (
        "Is the proposed movement inside the envelope the operator briefed?"
    )
    assert QUESTIONS["args_grounded"]["instructions"] == (
        "Are the tool's argument values grounded in what the user actually said?"
    )
    assert QUESTIONS["intent"]["instructions"] == "What did the user most recently ask the robot to do?"
    assert FRAME_QUESTIONS["person"]["instructions"] == "Is a person visible in the frame?"
    assert (
        FRAME_QUESTIONS["frame"]["instructions"]
        == "What is directly in front of the car in this camera frame?"
    )
    assert YES == 0.65 and MOTION_BUDGET_S == 1.5


def test_frame_vocabulary_matches_the_production_gate():
    from deepracer_agent import gate

    assert FRAME_CLASS_DESCRIPTIONS == gate.FRAME_CLASS_DESCRIPTIONS
    assert FRAME_CLASSES == gate.FRAME_CLASSES
    assert QUESTIONS["intent"]["criteria"] == gate.INTENT_CLASS_DESCRIPTIONS
    assert QUESTIONS["args_grounded"]["instructions"] == gate.GROUNDED_QUESTION
    assert YES == gate.YES


# -- the probability helper ---------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 0.5, 0.0, 1.0])
def test_probability_accepts_the_closed_unit_interval(value):
    assert probability(value) == float(value)


@pytest.mark.parametrize(
    "value", [NAN, float("inf"), -0.1, 1.5, "0.9", True, False, None, [0.5]], ids=lambda v: repr(v)
)
def test_probability_rejects_everything_else(value):
    with pytest.raises(ValueError):
        probability(value)


# -- MotionGate ---------------------------------------------------------------------------------

NO = round(1 - YES, 6)

MOTION_ROWS = [
    # (id, args, answers, action type, reason prefix)
    ("proceed", GROUNDED, motion_answers(), Proceed, "inside envelope"),
    (
        "envelope_deterministic",
        {"distance_m": 2.0, "heading_deg": 0.0},
        motion_answers(),
        Guide,
        "outside envelope: distance_m 2 > 0.5",
    ),
    (
        "envelope_turn",
        {"distance_m": 0.2, "heading_deg": 135.0},
        motion_answers(),
        Guide,
        "outside envelope: |heading_deg| 135 > 90",
    ),
    (
        "envelope_missing",
        {"distance_m": 0.2},
        motion_answers(),
        Guide,
        "outside envelope: heading_deg missing",
    ),
    (
        "envelope_per_decider",
        GROUNDED,
        motion_answers(inside=0.1),
        Guide,
        "outside envelope per decider (p=0.10)",
    ),
    ("args_invented", GROUNDED, motion_answers(grounded=0.2), Guide, "arguments not grounded (p=0.20)"),
    ("intent_question", GROUNDED, motion_answers(intent="question", intent_p=0.9), Guide, "intent question"),
    (
        "intent_unrelated",
        GROUNDED,
        motion_answers(intent="unrelated", intent_p=0.7),
        Guide,
        "intent unrelated",
    ),
    (
        "intent_weak_question",
        GROUNDED,
        motion_answers(intent="question", intent_p=0.4),
        Proceed,
        "inside envelope",
    ),
    (
        "guide_row_8_before_confirm_row_12",
        GROUNDED,
        motion_answers(inside=0.1, grounded=0.5),
        Guide,
        "outside envelope",
    ),
    ("unclear_inside", GROUNDED, motion_answers(inside=0.5), Confirm, "unclear: inside=0.50"),
    (
        "unclear_grounded",
        GROUNDED,
        motion_answers(grounded=0.6),
        Confirm,
        "unclear: inside=0.95 grounded=0.60",
    ),
    ("unclear_edge_low", GROUNDED, motion_answers(inside=NO), Confirm, "unclear"),
    ("yes_edge", GROUNDED, motion_answers(inside=YES, grounded=YES), Proceed, "inside envelope"),
    ("stop", GROUNDED, motion_answers(intent="stop", intent_p=0.9), Deny, STOP_REQUESTED),
    (
        "stop_beats_envelope",
        {"distance_m": 2.0, "heading_deg": 0.0},
        motion_answers(intent="stop", intent_p=0.9),
        Deny,
        STOP_REQUESTED,
    ),
    ("weak_stop_proceeds", GROUNDED, motion_answers(intent="stop", intent_p=0.4), Proceed, "inside envelope"),
]


@pytest.mark.parametrize(
    ("label", "args", "answers", "kind", "reason"), MOTION_ROWS, ids=[r[0] for r in MOTION_ROWS]
)
async def test_motion_gate_decision_table(label, args, answers, kind, reason):
    decider = ScriptedDecider(answers)
    gate = MotionGate(decider)
    action = await gate.before_tool_call(fake_event("Move forward 20 centimetres.", args))
    assert isinstance(action, kind)
    assert (action.reason or "").startswith(reason), action.reason
    assert len(decider.calls) == 1, "all questions go in one request"
    state, questions, images = decider.calls[0]
    assert questions == QUESTIONS and images is None
    assert state["command"] == {"tool": "move", "arguments": args}
    assert "user: Move forward 20 centimetres." in state["conversation"]
    assert "distance_m <= 0.5" in state["envelope"]
    row = gate.log[-1]
    assert row["verdict"] == kind.__name__ and row["tool"] == "move"
    assert isinstance(row["latency_ms"], float) and row["latency_ms"] >= 0, "measured by the gate, every row"


async def test_guide_feedback_texts():
    gate = MotionGate(ScriptedDecider(motion_answers(grounded=0.1)))
    action = await gate.before_tool_call(fake_event("Go.", GROUNDED))
    assert isinstance(action, Guide) and action.feedback == ARGS_INVENTED
    gate = MotionGate(ScriptedDecider(motion_answers(intent="question", intent_p=0.9)))
    action = await gate.before_tool_call(fake_event("How are you?", GROUNDED))
    assert isinstance(action, Guide) and action.feedback == NO_MOVEMENT_ASKED
    gate = MotionGate(ScriptedDecider(motion_answers(inside=0.5)))
    action = await gate.before_tool_call(fake_event("Move forward 20 centimetres.", GROUNDED))
    assert isinstance(action, Confirm) and "Allow it?" in action.prompt


MOTION_REFUSALS = [
    # (id, decider, args, reason): every input MotionGate refuses with a Deny and the string it returns
    (
        "server_unavailable",
        ScriptedDecider(fail=ServerUnavailable("no strands-decider at http://127.0.0.1:9")),
        GROUNDED,
        DECIDER_UNAVAILABLE,
    ),
    ("timeout", ScriptedDecider(motion_answers(), delay_s=0.3), GROUNDED, DECIDER_UNAVAILABLE),
    ("malformed_answer", ScriptedDecider({"inside_envelope": {"noul": 0.9}}), GROUNDED, DECIDER_UNAVAILABLE),
    ("non_numeric_answer", ScriptedDecider(motion_answers(inside="high")), GROUNDED, DECIDER_UNAVAILABLE),
    ("string_probability", ScriptedDecider(motion_answers(inside="0.9")), GROUNDED, DECIDER_UNAVAILABLE),
    ("nan_inside", ScriptedDecider(motion_answers(inside=NAN)), GROUNDED, DECIDER_UNAVAILABLE),
    ("nan_grounded", ScriptedDecider(motion_answers(grounded=NAN)), GROUNDED, DECIDER_UNAVAILABLE),
    ("inside_above_one", ScriptedDecider(motion_answers(inside=5.0)), GROUNDED, DECIDER_UNAVAILABLE),
    ("inside_negative", ScriptedDecider(motion_answers(inside=-0.2)), GROUNDED, DECIDER_UNAVAILABLE),
    ("bool_probability", ScriptedDecider(motion_answers(inside=True)), GROUNDED, DECIDER_UNAVAILABLE),
    (
        "intent_outside_options",
        ScriptedDecider(motion_answers(intent="banana")),
        GROUNDED,
        DECIDER_UNAVAILABLE,
    ),
    (
        "intent_missing_from_probabilities",
        ScriptedDecider(motion_answers(intent="stop", probabilities={"move_forward": 0.9}, confidence=0.2)),
        GROUNDED,
        DECIDER_UNAVAILABLE,
    ),
    (
        "intent_without_probabilities",
        ScriptedDecider({**motion_answers(), "intent": {"type": "choice", "choice": "move_forward"}}),
        GROUNDED,
        DECIDER_UNAVAILABLE,
    ),
    (
        "intent_nan_probability",
        ScriptedDecider(motion_answers(intent="stop", intent_p=NAN)),
        GROUNDED,
        DECIDER_UNAVAILABLE,
    ),
    (
        "stop_requested",
        ScriptedDecider(motion_answers(intent="stop", intent_p=0.66)),
        GROUNDED,
        STOP_REQUESTED,
    ),
]


@pytest.mark.parametrize(
    ("label", "decider", "args", "reason"), MOTION_REFUSALS, ids=[r[0] for r in MOTION_REFUSALS]
)
async def test_motion_gate_refusal_table(label, decider, args, reason):
    gate = MotionGate(decider, timeout=0.05)
    action = await gate.before_tool_call(fake_event("Move forward 20 centimetres.", args))
    assert isinstance(action, Deny)
    assert action.reason == reason
    row = gate.log[-1]
    assert row["verdict"] == "Deny" and row["reason"] == reason
    assert isinstance(row["latency_ms"], float), "a Deny row carries its latency too"
    if reason == DECIDER_UNAVAILABLE:
        assert row["error"], "the record says why"


async def test_non_object_tool_input_is_judged_as_an_empty_call_and_logged():
    decider = ScriptedDecider(motion_answers())
    gate = MotionGate(decider)
    action = await gate.before_tool_call(fake_event("Move.", [1, 2]))
    assert isinstance(action, Guide) and "distance_m missing" in (action.reason or "")
    assert gate.log[-1]["input_type"] == "list" and gate.log[-1]["arguments"] == {}


def test_motion_gate_fails_closed_declared():
    assert MotionGate(ScriptedDecider()).on_error == "deny"
    assert FrameGate(ScriptedDecider(), lambda: JPEG).on_error == "deny"


async def test_motion_gate_only_gates_named_tools():
    decider = ScriptedDecider(motion_answers())
    gate = MotionGate(decider, tools=("move",))
    assert isinstance(await gate.before_tool_call(fake_event("hi", {}, tool_name="look")), Proceed)
    assert decider.calls == []


async def test_yes_knob_moves_the_confirm_band():
    answers = motion_answers(inside=0.7, grounded=0.7)
    assert isinstance(
        await MotionGate(ScriptedDecider(answers)).before_tool_call(fake_event("x", GROUNDED)), Proceed
    )
    assert isinstance(
        await MotionGate(ScriptedDecider(answers), yes=0.8).before_tool_call(fake_event("x", GROUNDED)),
        Confirm,
    )


@pytest.mark.parametrize("bad", [0.3, 0.5, 1.0, 1.2])
def test_yes_knob_outside_its_range_is_refused(bad):
    with pytest.raises(ValueError):
        MotionGate(ScriptedDecider(), yes=bad)


def test_judge_runs_the_async_handler_from_plain_code():
    gate = MotionGate(ScriptedDecider(motion_answers()))
    assert isinstance(judge(gate, fake_event("Move forward 20 centimetres.", GROUNDED)), Proceed)


def test_envelope_describe_and_violations():
    env = Envelope(max_distance_m=1.0, max_turn_deg=45)
    assert env.describe() == "distance_m <= 1 per call, |heading_deg| <= 45"
    assert env.violations({"distance_m": 0.5, "heading_deg": -30}) == []
    assert env.violations({"distance_m": -0.1, "heading_deg": 50}) == [
        "distance_m must not be negative",
        "|heading_deg| 50 > 45",
    ]
    assert env.violations({"distance_m": NAN, "heading_deg": True}) == [
        "distance_m missing or not a number",
        "heading_deg missing or not a number",
    ]


def test_render_skips_non_text_blocks_and_is_bounded():
    messages = [
        {"role": "user", "content": [{"text": "Move."}]},
        {"role": "assistant", "content": [{"toolUse": {"name": "move"}}]},
    ]
    assert MotionGate.render(messages) == "user: Move."
    assert MotionGate.render([]) == "(no conversation yet)"
    long = [{"role": "user", "content": [{"text": f"m{i} " + "x" * 400}]} for i in range(500)]
    text = MotionGate.render(long)
    assert len(text) <= 2000 and text.startswith("...") and "m499" in text and "m0 " not in text


# -- through the strands intervention registry -------------------------------------------------


def _event(tool_name="move", args=None, messages=None):
    agent = SimpleNamespace(
        _interrupt_state=_InterruptState(),
        messages=messages or [{"role": "user", "content": [{"text": "Move forward 20 centimetres."}]}],
    )
    return BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"toolUseId": "tooluse_1", "name": tool_name, "input": dict(args or GROUNDED)},
        invocation_state={},
    )


async def _dispatch(gate, event):
    registry = HookRegistry()
    InterventionRegistry([gate], registry)
    await registry.invoke_callbacks_async(event)
    return event


async def test_motion_gate_deny_and_guide_through_the_registry():
    event = await _dispatch(
        MotionGate(ScriptedDecider(motion_answers(intent="stop", intent_p=0.9))), _event()
    )
    assert event.cancel_tool == f"DENIED: {STOP_REQUESTED}"
    event = await _dispatch(MotionGate(ScriptedDecider(motion_answers(grounded=0.1))), _event())
    assert event.cancel_tool.startswith("GUIDANCE:") and ARGS_INVENTED in event.cancel_tool


async def test_motion_gate_exception_is_deny_via_on_error():
    class Exploding(ScriptedDecider):
        def ask(self, *a, **k):
            raise RuntimeError("unexpected")

    event = await _dispatch(MotionGate(Exploding()), _event())
    assert event.cancel_tool.startswith("DENIED: Handler threw: unexpected")


async def test_frame_gate_exception_is_deny_via_on_error():
    class Exploding(ScriptedDecider):
        def ask(self, *a, **k):
            raise RuntimeError("unexpected")

    event = await _dispatch(FrameGate(Exploding(), lambda: JPEG), _event())
    assert event.cancel_tool.startswith("DENIED: Handler threw: unexpected")


# -- FrameGate ----------------------------------------------------------------------------------

FRAME_ROWS = [
    ("clear", frame_answers(), Proceed, "clear (p=0.93)"),
    ("weak_unclear_proceeds", frame_answers(cls="unclear", p=0.55), Proceed, "unclear (p=0.55)"),
    ("strong_unclear_denies", frame_answers(cls="unclear", p=0.9), Deny, "cannot see clearly (p=0.90)"),
    ("unclear_at_threshold", frame_answers(cls="unclear", p=0.65), Deny, "cannot see clearly (p=0.65)"),
    ("unclear_just_below", frame_answers(cls="unclear", p=0.6499), Proceed, "unclear (p=0.65)"),
    ("obstacle", frame_answers(cls="obstacle_near", p=0.9), Guide, "obstacle_near (p=0.90)"),
]


@pytest.mark.parametrize(("label", "answers", "kind", "reason"), FRAME_ROWS, ids=[r[0] for r in FRAME_ROWS])
async def test_frame_gate_decision_table(label, answers, kind, reason):
    decider = ScriptedDecider(answers)
    gate = FrameGate(decider, lambda: JPEG)
    action = await gate.before_tool_call(fake_event("Move forward 20 centimetres.", GROUNDED))
    assert isinstance(action, kind)
    assert action.reason == reason
    state, questions, images = decider.calls[0]
    assert questions == FRAME_QUESTIONS and images == [JPEG]
    assert "command" not in json.dumps(state).lower()
    assert gate.log[-1]["frame_bytes"] == len(JPEG) and gate.log[-1]["class"] == answers["frame"]["choice"]
    assert isinstance(gate.log[-1]["latency_ms"], float)


async def test_frame_gate_obstacle_feedback():
    action = await FrameGate(
        ScriptedDecider(frame_answers(cls="obstacle_near", p=0.9)), lambda: JPEG
    ).before_tool_call(fake_event("x", GROUNDED))
    assert isinstance(action, Guide) and action.feedback == OBSTACLE_NEAR


def _raises():
    raise OSError("camera gone")


FRAME_REFUSALS = [
    # (id, decider, frame_source, reason): every input FrameGate refuses with a Deny and the string it returns
    ("person_yes_no", ScriptedDecider(frame_answers(person=0.95)), lambda: JPEG, PERSON_IN_FRAME),
    ("person_at_threshold", ScriptedDecider(frame_answers(person=0.5)), lambda: JPEG, PERSON_IN_FRAME),
    (
        "person_five_way_only",
        ScriptedDecider(frame_answers(person=0.1, cls="person_in_frame", p=0.6)),
        lambda: JPEG,
        PERSON_IN_FRAME,
    ),
    ("off_surface", ScriptedDecider(frame_answers(cls="off_surface", p=0.9)), lambda: JPEG, OFF_SURFACE),
    ("off_surface_weak", ScriptedDecider(frame_answers(cls="off_surface", p=0.3)), lambda: JPEG, OFF_SURFACE),
    ("no_frame", ScriptedDecider(frame_answers()), lambda: None, VISION_UNAVAILABLE),
    ("empty_frame", ScriptedDecider(frame_answers()), lambda: b"", VISION_UNAVAILABLE),
    ("frame_not_bytes", ScriptedDecider(frame_answers()), lambda: "not-bytes", VISION_UNAVAILABLE),
    ("camera_raises", ScriptedDecider(frame_answers()), _raises, VISION_UNAVAILABLE),
    ("decider_down", ScriptedDecider(fail=ServerUnavailable("down")), lambda: JPEG, VISION_UNAVAILABLE),
    ("timeout", ScriptedDecider(frame_answers(), delay_s=0.3), lambda: JPEG, VISION_UNAVAILABLE),
    ("malformed_answer", ScriptedDecider({"person": {"noul": 0.1}}), lambda: JPEG, VISION_UNAVAILABLE),
    ("class_outside_options", ScriptedDecider(frame_answers(cls="banana")), lambda: JPEG, VISION_UNAVAILABLE),
    ("unclear_nan", ScriptedDecider(frame_answers(cls="unclear", p=NAN)), lambda: JPEG, VISION_UNAVAILABLE),
    ("person_nan", ScriptedDecider(frame_answers(person=NAN)), lambda: JPEG, VISION_UNAVAILABLE),
    ("person_string", ScriptedDecider(frame_answers(person="0.1")), lambda: JPEG, VISION_UNAVAILABLE),
    ("probability_above_one", ScriptedDecider(frame_answers(p=1.5)), lambda: JPEG, VISION_UNAVAILABLE),
    (
        "class_missing_from_probabilities",
        ScriptedDecider(frame_answers(cls="clear", probabilities={"unclear": 0.9}, confidence=0.9)),
        lambda: JPEG,
        VISION_UNAVAILABLE,
    ),
]


@pytest.mark.parametrize(
    ("label", "decider", "source", "reason"), FRAME_REFUSALS, ids=[r[0] for r in FRAME_REFUSALS]
)
async def test_frame_gate_refusal_table(label, decider, source, reason):
    gate = FrameGate(decider, source, timeout=0.05)
    action = await gate.before_tool_call(fake_event("Move forward 20 centimetres.", GROUNDED))
    assert isinstance(action, Deny)
    assert action.reason == reason
    row = gate.log[-1]
    assert row["verdict"] == "Deny" and row["reason"] == reason
    assert isinstance(row["latency_ms"], float), "a Deny row carries its latency too"
    try:
        frame = source()
    except OSError:
        frame = None
    if not isinstance(frame, bytes) or not frame:
        assert decider.calls == [], "no frame means no question"


async def test_frame_gate_only_gates_named_tools():
    decider = ScriptedDecider(frame_answers())
    gate = FrameGate(decider, lambda: JPEG, tools=("move",))
    assert isinstance(await gate.before_tool_call(fake_event("hi", {}, tool_name="look")), Proceed)
    assert decider.calls == []


# -- the stdlib client --------------------------------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_client_ask_request_body_shape(monkeypatch):
    seen: dict = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return _Response(
            json.dumps(
                {
                    "model": "x",
                    "answers": {"q": {"type": "noul", "noul": 0.8}},
                    "usage": {"input_tokens": 42, "output_tokens": 1},
                    "latency_ms": 140.0,
                }
            ).encode()
        )

    monkeypatch.setattr(_client.urllib.request, "urlopen", fake_urlopen)
    decider = Decider("http://decider.test:8111/", timeout=3.0)
    answers = decider.ask(
        {"command": "move"}, {"q": Decider.noul("Q?")}, images=[b"\xff\xd8jpeg", "YWxyZWFkeQ=="]
    )

    assert answers == {"q": {"type": "noul", "noul": 0.8}}
    assert seen["url"] == "http://decider.test:8111/v1/systemone"
    assert seen["headers"]["content-type"] == "application/json"
    assert seen["timeout"] == 3.0
    assert seen["body"] == {
        "state": {"command": "move"},
        "model": _client.MODEL_ID,
        "questions": {"q": {"type": "noul", "instructions": "Q?"}},
        "images": [base64.b64encode(b"\xff\xd8jpeg").decode(), "YWxyZWFkeQ=="],
    }
    assert decider.calls == 1 and decider.input_tokens == 42
    assert decider.server_latency_ms == 140.0 and decider.last_latency_ms == 140.0, (
        "upstream's name is an alias"
    )
    assert isinstance(decider.latency_ms, float) and decider.latency_ms >= 0


def test_client_ask_without_images_omits_the_field(monkeypatch):
    seen: dict = {}

    def fake_urlopen(request, timeout=None):
        seen["body"] = json.loads(request.data)
        return _Response(json.dumps({"answers": {}}).encode())

    monkeypatch.setattr(_client.urllib.request, "urlopen", fake_urlopen)
    Decider("http://decider.test").ask("plain text state", {})
    assert "images" not in seen["body"] and seen["body"]["state"] == "plain text state"


def test_client_rejects_more_than_four_images():
    with pytest.raises(ValueError):
        Decider("http://decider.test").ask("s", {}, images=[b"x"] * 5)


def test_client_rejects_a_string_that_is_not_base64():
    with pytest.raises(ValueError):
        Decider("http://decider.test").ask("s", {}, images=["not base64!!"])


@pytest.mark.parametrize(
    "failure",
    [
        _client.urllib.error.URLError("connection refused"),
        _client.urllib.error.HTTPError("http://d/v1/systemone", 500, "boom", {}, None),
        TimeoutError("timed out"),
        http.client.BadStatusLine("garbage"),
        http.client.IncompleteRead(b"partial"),
    ],
    ids=["refused", "http500", "timeout", "bad_status_line", "incomplete_read"],
)
def test_client_folds_failures_into_server_unavailable(monkeypatch, failure):
    def fake_urlopen(request, timeout=None):
        raise failure

    monkeypatch.setattr(_client.urllib.request, "urlopen", fake_urlopen)
    decider = Decider("http://decider.test")
    with pytest.raises(ServerUnavailable) as info:
        decider.ask("s", {"q": Decider.noul("Q?")})
    assert "strands-decider serve" in str(info.value)
    assert isinstance(decider.latency_ms, float), "the failed call's own latency, not the previous one's"


def test_client_rejects_body_without_answers(monkeypatch):
    monkeypatch.setattr(
        _client.urllib.request, "urlopen", lambda request, timeout=None: _Response(b'{"model": "x"}')
    )
    with pytest.raises(ServerUnavailable):
        Decider("http://decider.test").ask("s", {})


def test_client_health(monkeypatch):
    monkeypatch.setattr(
        _client.urllib.request,
        "urlopen",
        lambda url, timeout=None: _Response(
            b'{"status": "ok", "checkpoint": "c", "base_model": "b", "device": "cpu"}'
        ),
    )
    decider = Decider("http://decider.test")
    assert decider.health()["status"] == "ok"
    assert "strands-decider: c on b" in decider.banner()


def test_module_constants():
    assert _client.NAME == "strands-decider"
    assert _client.MODEL_ID.startswith("StrandsAgents/strands-decider-2B")
    assert _client.DEFAULT_PORT == 8111
    assert _client.MAX_IMAGES == 4
    assert _client.ENV_URL == "DECIDER_URL"


def test_fake_event_shape():
    event = fake_event("Go.", GROUNDED)
    assert isinstance(event, SimpleNamespace)
    assert event.tool_use["name"] == "move" and event.agent.messages[0]["role"] == "user"


def test_handlers_are_async_and_do_not_block_the_loop():
    """The blocking ``ask`` runs in a worker thread: another coroutine makes progress meanwhile."""
    ticks: list[int] = []

    async def ticker():
        for i in range(3):
            ticks.append(i)
            await asyncio.sleep(0.02)

    async def both():
        gate = MotionGate(ScriptedDecider(motion_answers(), delay_s=0.1), timeout=1.0)
        action, _ = await asyncio.gather(
            gate.before_tool_call(fake_event("Move forward 20 centimetres.", GROUNDED)), ticker()
        )
        return action

    assert isinstance(asyncio.run(both()), Proceed)
    assert ticks == [0, 1, 2]
