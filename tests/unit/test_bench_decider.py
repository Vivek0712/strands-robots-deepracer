"""bench_decider against the fake decider on an ephemeral port: it must run, score and write files."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from deepracer_agent import bench_decider as bd
from deepracer_agent.gate import FRAME_CLASSES, Envelope, envelope_context
from harness.fake_decider import FakeDecider
from harness.frames import LABELS
from harness.shared import SharedState


@pytest.fixture
def ephemeral_decider(tmp_path: Path) -> Iterator[FakeDecider]:
    """A FakeDecider on port 0 (the OS picks a free port) with its own shared file, never 8111."""
    decider = FakeDecider(port=0, shared=SharedState(tmp_path / "shared.json"))
    decider.start()
    assert decider._server is not None
    decider.port = decider._server.server_address[1]
    try:
        yield decider
    finally:
        decider.stop()


def test_percentile_nearest_rank() -> None:
    assert bd.percentile([], 50) is None
    assert bd.percentile([5.0], 95) == 5.0
    assert bd.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert bd.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert bd.percentile([3, 1, 2], 100) == 3


def test_envelope_table_is_at_least_twelve_and_matches_the_gate_check() -> None:
    assert len(bd.ENVELOPE_CASES) >= 12
    env = Envelope()
    for case in bd.ENVELOPE_CASES:
        ok = not env.violations(case.linear, case.angular, case.duration)
        assert ok == case.inside, case.name
    assert {c.inside for c in bd.ENVELOPE_CASES} == {True, False}


def test_expected_classes_cover_every_harness_label_with_real_classes() -> None:
    assert set(bd.EXPECTED_CLASSES) == set(LABELS)
    for classes in bd.EXPECTED_CLASSES.values():
        assert classes and set(classes) <= set(FRAME_CLASSES)


def test_blind_context_is_the_gate_context_minus_the_hint() -> None:
    bench = bd.Bench("http://127.0.0.1:1", repeats=1)
    case = bd.ENVELOPE_CASES[0]
    gate_ctx = envelope_context(Envelope(), case.linear, case.angular, case.duration)
    assert bench._context(case, blind=False) == gate_ctx
    blind = bench._context(case, blind=True)
    assert "deterministic_check" not in blind
    assert blind["command"] == gate_ctx["command"] and blind["envelope"] == gate_ctx["envelope"]
    bench.close()


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"repeats": 0}, "repeats must be >= 1"),
        ({"timeout_s": 0}, "timeout must be > 0 seconds"),
        ({"labels": ["clear", "nothing"]}, "unknown frame label(s) nothing"),
    ],
)
def test_refusals(kwargs: dict, reason: str) -> None:
    base = {"repeats": 1, "timeout_s": 1.0}
    base.update(kwargs)
    with pytest.raises(bd.BenchError, match=reason.replace("(", r"\(").replace(")", r"\)")):
        bd.Bench("http://127.0.0.1:1", **base)


@pytest.mark.parametrize(
    ("item", "reason"),
    [("novalue", "--extra expects key=value"), ("=3", "--extra expects key=value")],
)
def test_extra_refusals(item: str, reason: str) -> None:
    with pytest.raises(bd.BenchError, match=reason):
        bd.parse_extra([item])


def test_extra_parses_numbers() -> None:
    assert bd.parse_extra(["load_s=12.5", "rss_mb=4096", "note=hello"]) == {
        "load_s": 12.5,
        "rss_mb": 4096.0,
        "note": "hello",
    }


def test_run_against_fake_scores_everything(ephemeral_decider: FakeDecider, tmp_path: Path) -> None:
    bench = bd.Bench(
        ephemeral_decider.url,
        repeats=2,
        timeout_s=5.0,
        frames_dir=tmp_path / "frames",
        extra={"load_s": 0.1},
    )
    try:
        result = bench.run()
    finally:
        bench.close()
    assert result["meta"]["fake"] is True
    assert result["meta"]["model"] == "fake-decider"
    assert [r["label"] for r in result["frames"]] == list(LABELS)
    for row in result["frames"]:
        assert row["agreement"] == 1.0, row
        assert row["chosen"] in bd.EXPECTED_CLASSES[row["label"]]
        assert row["latency"]["n"] == 2 and not row["errors"]
        assert set(row["mean_probabilities"]) == set(FRAME_CLASSES)
    assert result["frame_agreement_mean"] == 1.0
    # noul: 14 cases x 2 repeats x 2 variants; choice: 7 frames x 2 repeats. Warm-ups excluded.
    assert result["latency"]["noul"]["n"] == len(bd.ENVELOPE_CASES) * 2 * 2
    assert result["latency"]["choice"]["n"] == len(LABELS) * 2
    assert result["latency"]["gate_estimate"]["p50_sum_ms"] is not None
    assert result["envelope"]["as_gate"]["accuracy"] == 1.0
    assert result["envelope"]["blind"]["accuracy"] == 1.0
    # every call carried exactly one image for choice and none for noul
    choice_calls = [c for c in ephemeral_decider.calls if "choice" in c["questions"].values()]
    noul_calls = [c for c in ephemeral_decider.calls if "noul" in c["questions"].values()]
    assert choice_calls and all(c["images"] == 1 for c in choice_calls)
    assert noul_calls and all(c["images"] == 0 for c in noul_calls)
    # frames were generated where asked, and contain all seven labels
    assert sorted(p.stem for p in (tmp_path / "frames").glob("*.jpg")) == sorted(LABELS)

    json_path, md_path = bd.write_report(result, tmp_path / "out")
    loaded = json.loads(json_path.read_text())
    assert loaded["meta"]["extra"] == {"load_s": 0.1}
    md = md_path.read_text()
    assert "| noul |" in md and "| choice |" in md and "### as_gate" in md and "### blind" in md
    assert "fake decider" in md


def test_main_writes_files_and_returns_zero(ephemeral_decider: FakeDecider, tmp_path: Path, capsys) -> None:
    code = bd.main(
        [
            "--url",
            ephemeral_decider.url,
            "--repeats",
            "1",
            "--labels",
            "clear,person_in_frame",
            "--no-blind",
            "--out",
            str(tmp_path / "report"),
            "--frames-dir",
            str(tmp_path / "frames"),
            "--extra",
            "rss_mb=1",
            "-q",
        ]
    )
    assert code == 0
    assert (tmp_path / "report" / "bench.json").exists() and (tmp_path / "report" / "bench.md").exists()
    out = capsys.readouterr().out
    assert "Decider benchmark: fake-decider" in out
    body = json.loads((tmp_path / "report" / "bench.json").read_text())
    assert body["meta"]["labels"] == ["clear", "person_in_frame"]
    assert "blind" not in body["envelope"]


def test_main_without_a_server_returns_two(tmp_path: Path, capsys) -> None:
    code = bd.main(["--url", "http://127.0.0.1:1", "--repeats", "1", "--timeout", "0.5", "-q"])
    assert code == 2
    assert "not usable" in capsys.readouterr().err


def test_main_refuses_bad_arguments(capsys) -> None:
    assert bd.main(["--url", "http://127.0.0.1:1", "--repeats", "0", "-q"]) == 2
    assert "repeats must be >= 1" in capsys.readouterr().err
