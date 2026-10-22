"""calibrate_frames: frame-set parsing, the variants, the gate's two-question path and the pick rule.

No ports: the decider is an in-memory fake with the same two (or three) methods the gate uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deepracer_agent import calibrate_frames as cf
from deepracer_agent.decider_client import DeciderUnavailable
from deepracer_agent.gate import FRAME_CLASS_DESCRIPTIONS, FRAME_CLASSES, FRAME_QUESTION, PERSON_QUESTION
from harness.frames import LABELS, render

JPEG = b"\xff\xd8" + b"\x00" * 8 + b"\xff\xd9"


class ScriptedDecider:
    """Answers per frame from ``script[jpeg] = (person_p, cls, p)``; counts calls per method."""

    def __init__(self, script: dict[bytes, tuple[float, str, float]], *, with_ask_frame: bool = True):
        self.script = script
        self.calls: list[str] = []
        if not with_ask_frame:
            self.ask_frame = None  # type: ignore[assignment]

    def _lookup(self, jpeg: bytes) -> tuple[float, str, float]:
        if jpeg not in self.script:
            raise DeciderUnavailable("decider HTTP 500")
        return self.script[jpeg]

    def ask_noul(self, question, context, image_bytes=None, **kw):
        self.calls.append("noul")
        person_p, _, _ = self._lookup(image_bytes)
        return {"yes": person_p >= 0.5, "probability": person_p, "latency_ms": 300}

    def ask_choice(self, question, classes, image_bytes=None, **kw):
        self.calls.append("choice")
        _, cls, p = self._lookup(image_bytes)
        probs = {c: 0.01 for c in classes}
        probs[cls] = p
        return {"class": cls, "probability": p, "latency_ms": 350, "probabilities": probs}

    def ask_frame(self, person_question, frame_question, classes, image_bytes, **kw):
        self.calls.append("frame")
        assert (person_question, frame_question) == (PERSON_QUESTION, FRAME_QUESTION)
        person_p, cls, p = self._lookup(image_bytes)
        probs = {c: 0.01 for c in classes}
        probs[cls] = p
        return {
            "person": {"yes": person_p >= 0.5, "probability": person_p, "latency_ms": 450},
            "frame": {"class": cls, "probability": p, "latency_ms": 450, "probabilities": probs},
            "latency_ms": 450,
        }


def test_variants_use_exactly_the_contract_classes_and_current_is_the_gate():
    assert set(cf.VARIANTS) >= {"current", "sharp", "car_camera", "person_first", "two_step"}
    for v in cf.VARIANTS.values():
        assert sorted(v.descriptions) == sorted(FRAME_CLASSES)
    current = cf.VARIANTS["current"]
    assert current.question == FRAME_QUESTION and current.descriptions == FRAME_CLASS_DESCRIPTIONS
    assert cf.VARIANTS["two_step"].person_noul == PERSON_QUESTION
    assert next(iter(cf.VARIANTS["person_first"].descriptions)) == "person_in_frame"


def test_variant_rejects_a_renamed_class():
    with pytest.raises(cf.CalibrationError):
        cf.Variant("bad", "q", {**FRAME_CLASS_DESCRIPTIONS, "human": "x"})


def test_parse_frames_spec_and_load_from_stems(tmp_path: Path):
    assert cf.parse_frames_spec("runs/x/frames") == (Path("runs/x/frames"), None)
    assert cf.parse_frames_spec("runs/x/frames:person_in_frame") == (Path("runs/x/frames"), "person_in_frame")
    with pytest.raises(cf.CalibrationError):
        cf.parse_frames_spec("runs/x/frames:zebra")
    for label in ("clear", "unclear"):
        (tmp_path / f"{label}.jpg").write_bytes(render(label))
    (tmp_path / "000001.jpg").write_bytes(JPEG)
    (tmp_path / "notes.txt").write_text("ignored")
    items = cf.load_frame_set(str(tmp_path))
    assert [(i.path.name, i.label) for i in items] == [
        ("000001.jpg", cf.UNLABELLED),
        ("clear.jpg", "clear"),
        ("unclear.jpg", "unclear"),
    ]
    forced = cf.load_frame_set(f"{tmp_path}:person_in_frame")
    assert {i.label for i in forced} == {"person_in_frame"}
    with pytest.raises(cf.CalibrationError):
        cf.load_frame_set(str(tmp_path / "missing"))


def test_every_harness_label_has_an_expected_outcome_or_is_ambiguous():
    for label in LABELS:
        assert cf.expected_outcome(label) in {"Proceed", "Guide", "Deny", None}
    assert cf.expected_outcome("person_in_frame") == "Deny"
    assert cf.expected_outcome("hand_over_lens") == "Deny"
    assert cf.expected_outcome("clear") == "Proceed"
    assert cf.expected_outcome("sign") is None, "clear or unclear: Proceed or Deny"
    assert cf.gate_outcome("unclear", 0.49) == "Proceed", "below the threshold the table proceeds"


def test_two_step_variant_runs_the_gates_combined_ask_and_overrides_unclear():
    decider = ScriptedDecider({JPEG: (0.95, "unclear", 0.65)})
    out = cf.ask_variant(decider, cf.VARIANTS["two_step"], JPEG)
    assert decider.calls == ["frame"]
    assert (out["class"], out["probability"], out["person_p"]) == ("person_in_frame", 0.95, 0.95)
    assert out["overridden"] == "five-way said unclear 0.65" and out["latency_ms"] == 450


def test_two_step_falls_back_to_two_calls_without_ask_frame():
    decider = ScriptedDecider({JPEG: (0.07, "unclear", 0.62)}, with_ask_frame=False)
    out = cf.ask_variant(decider, cf.VARIANTS["two_step"], JPEG)
    assert decider.calls == ["noul", "choice"]
    assert (out["class"], out["probability"], out["overridden"]) == ("unclear", 0.62, None)
    assert out["latency_ms"] == 650


def test_plain_variant_asks_only_the_choice_with_its_own_wording():
    decider = ScriptedDecider({JPEG: (0.95, "unclear", 0.60)})
    out = cf.ask_variant(decider, cf.VARIANTS["sharp"], JPEG)
    assert decider.calls == ["choice"] and out["person_p"] is None and out["steps"] == 1


def test_score_label_strict_metric_separates_class_from_outcome():
    unclear_denies = [
        {"class": "unclear", "probability": 0.62, "probabilities": {"unclear": 0.62}, "latency_ms": 350}
    ] * 3
    row = cf.score_label(unclear_denies, "person_in_frame")
    assert row["gate_accuracy"] == 1.0, "Deny held"
    assert row["class_accuracy"] == 0.0 and row["strict_accuracy"] == 0.0, "but for the wrong reason"
    weak_person = [{"class": "person_in_frame", "probability": 0.45, "probabilities": {}, "latency_ms": 350}]
    row = cf.score_label(weak_person, "person_in_frame")
    assert row["class_accuracy"] == 1.0 and row["strict_accuracy"] == 0.0, "right class, gate would proceed"


def _result(name: str, person: float, clear: float, dark: float, p95: float = 400.0) -> dict:
    def row(strict: float) -> dict:
        return {"strict_accuracy": strict}

    labels = {
        "person_in_frame": row(person),
        "clear": row(clear),
        "unclear": row(dark),
        "hand_over_lens": row(dark),
    }
    return {
        "variant": name,
        "labels": labels,
        "strict_accuracy_mean": (person + clear + dark) / 3,
        "latency": {"p95_ms": p95},
    }


def test_pick_best_requires_all_three_and_never_rewards_a_fail_open_variant():
    current = _result("current", person=0.0, clear=1.0, dark=1.0)  # unclear denies: class wrong
    sharp = _result("sharp", person=0.0, clear=1.0, dark=1.0)  # unclear under 0.5: strict 0
    car = _result("car_camera", person=0.5, clear=1.0, dark=1.0)
    two_step = _result("two_step", person=0.91, clear=1.0, dark=1.0, p95=673)
    assert cf.pick_best([current, sharp, car]) is None
    assert cf.pick_best([current, sharp, car, two_step])["variant"] == "two_step"
    assert cf.pick_best([two_step], min_rate=1.0) is None, "one real miss in eleven is reported, not hidden"


def test_run_variant_and_markdown_without_a_server(tmp_path: Path):
    person_jpeg, clear_jpeg, dark_jpeg = JPEG, JPEG + b"c", JPEG + b"d"
    items = [
        cf.FrameItem(tmp_path / "000001.jpg", "person_in_frame", person_jpeg),
        cf.FrameItem(tmp_path / "clear.jpg", "clear", clear_jpeg),
        cf.FrameItem(tmp_path / "unclear.jpg", "unclear", dark_jpeg),
        cf.FrameItem(tmp_path / "broken.jpg", "clear", b"\x00"),
    ]
    decider = ScriptedDecider(
        {
            person_jpeg: (0.95, "unclear", 0.65),
            clear_jpeg: (0.09, "clear", 0.5),
            dark_jpeg: (0.09, "unclear", 0.66),
        }
    )
    res = cf.run_variant(decider, cf.VARIANTS["two_step"], items, repeats=2)
    assert res["labels"]["person_in_frame"]["strict_accuracy"] == 1.0
    assert res["labels"]["clear"]["strict_accuracy"] == 1.0
    assert res["labels"]["unclear"]["deny_held"] == 1.0
    assert len(res["errors"]) == 2 and all(e["frame"] == "broken.jpg" for e in res["errors"])
    no_dark = cf.run_variant(decider, cf.VARIANTS["two_step"], items[:2], repeats=1)
    assert cf.pick_best([no_dark]) is None, "no dark frames in the run: nothing to select from"
    report = {
        "meta": {
            "model": "m",
            "url": "u",
            "health": {},
            "started_utc": "t",
            "wall_s": 1,
            "repeats": 2,
            "frame_sets": ["x"],
            "label_counts": {"person_in_frame": 1, "clear": 2, "unclear": 1},
        },
        "variants": [res],
        "best": cf.pick_best([res])["variant"],
    }
    md = cf.to_markdown(report)
    assert "**Selected: `two_step`**" in md and "| person_in_frame | 2 |" in md
    assert "000001" not in md, "the report is tables per label; frame names stay in the JSON"
