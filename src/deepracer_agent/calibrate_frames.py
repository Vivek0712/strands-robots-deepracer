"""Calibrate the gate's frame question: which wording lands a real person on ``person_in_frame``?

On the car, the booth decider answered ``unclear`` (p 0.58-0.67) on eleven sharp, well-lit frames
of a person sitting in front of the camera. Deny was the right action, but the class was wrong,
so the Apology beat spoke the wrong reason. This tool asks the decider the frame question for
every frame in one or more labelled directories, once per wording *variant*, and reports per
variant: the class distribution per label, the mean probability of the chosen class, the
client-measured latency, and accuracy against the labels. It never lowers the Deny threshold
and never adds a fail-open path: a variant is only a different question text, a different set of
class descriptions, a different class order, or a two-step ask (a yes/no "is a person visible"
first, then the five-way choice). The class names are fixed by CONTRACTS section 7.

Physics stops the car; the decider explains. This measures how well it explains.

Frame sets are ``--frames DIR[:LABEL]``. With ``:LABEL`` every JPEG in ``DIR`` carries that label
(the real set: ``runs/beats-car5/frames:person_in_frame``). Without it, each file's stem is its
label when it is one of the harness labels (``harness/frames/clear.jpg`` is ``clear``), else the
frame is unlabelled and counts only toward the class distribution and latency. Expected classes
per label follow ``bench_decider.EXPECTED_CLASSES`` (``hand_over_lens`` is ``unclear``, ``sign`` is
``clear`` or ``unclear``).

Run (decider calls are sequential; one at a time keeps the numbers honest)::

    .venv/bin/python -m deepracer_agent.calibrate_frames \\
        --frames harness/frames --frames runs/beats-car5/frames:person_in_frame \\
        --decider http://127.0.0.1:8111 --repeats 1 --out runs/calib/<stamp>

Output: a Markdown summary on stdout plus ``calibration.json`` and ``calibration.md`` in ``--out``.
Exit status 0 on a completed run, 2 when the server's ``/health`` does not answer. Real frames are
never copied, embedded or described: the report carries file names and numbers only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import statistics
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .bench_decider import EXPECTED_CLASSES, summarise_latency
from .decider_client import DEFAULT_DECIDER_URL, DeciderClient, DeciderUnavailable
from .gate import (
    DENY_CLASSES,
    FRAME_CLASS_DESCRIPTIONS,
    FRAME_CLASSES,
    FRAME_QUESTION,
    PERSON_QUESTION,
    ask_frame_questions,
    combine_frame_answers,
)

#: The gate's Deny threshold on a deny class (CONTRACTS section 7). Read-only here: a variant may
#: move probabilities, never this number.
DENY_THRESHOLD = 0.5
JPEG_SUFFIXES = (".jpg", ".jpeg")
UNLABELLED = "unlabelled"


class CalibrationError(ValueError):
    """Bad arguments; the message is the reason string."""


class ChoiceDecider(Protocol):
    """The two methods of ``DeciderClient`` this tool uses (tests pass a fake)."""

    def ask_noul(
        self,
        question: str,
        context: Any,
        image_bytes: bytes | None = None,
        *,
        criteria: Mapping[str, str] | None = None,
    ) -> dict[str, Any]: ...

    def ask_choice(
        self,
        question: str,
        classes: Sequence[str] | Mapping[str, Any],
        image_bytes: bytes | None = None,
        *,
        context: Any = "",
    ) -> dict[str, Any]: ...


# -- variants ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Variant:
    """One way of asking the frame question. Class names are always the five contract classes.

    ``descriptions`` is ordered: the decider numbers options in the order given, so the order is
    part of the variant. ``state`` is the text sent as the request state next to the image (the
    gate sends an empty string today). ``person_noul`` turns the variant into the gate's two-question
    ask: the yes/no and the five-way choice go in one request over the same image (two calls on a
    decider without ``ask_frame``) and ``gate.combine_frame_answers`` merges them: P(yes) >= 0.5 is
    ``person_in_frame`` at that probability unless the five-way was already surer, otherwise the
    five-way answer stands. Only the gate's own constants are measured on this path; the
    ``question``/``descriptions`` fields of a two-step variant are informational.
    """

    name: str
    question: str
    descriptions: dict[str, str]
    state: str = ""
    person_noul: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if tuple(sorted(self.descriptions)) != tuple(sorted(FRAME_CLASSES)):
            raise CalibrationError(
                f"variant {self.name!r} must describe exactly the contract classes {FRAME_CLASSES}"
            )


SHARP_DESCRIPTIONS: dict[str, str] = {
    "clear": "an empty floor ahead, nobody and nothing in the way; the car can move",
    "obstacle_near": "an object (box, cone, bag, furniture) is close in front of the bumper",
    "person_in_frame": (
        "a person is visible: a face, torso, arm, hand, leg or foot, at any distance, "
        "even filling the picture or very close to the lens"
    ),
    "off_surface": "the car is at or past the edge of the pen surface",
    "unclear": (
        "the picture itself is unreadable: black, very dark, blurred or blocked by something flat "
        "against the lens"
    ),
}
CAR_CAMERA_QUESTION = (
    "This is the front camera of a small robot car on the floor. What is in front of it right now?"
)
PERSON_NOUL_QUESTION = PERSON_QUESTION


def _ordered(descriptions: Mapping[str, str], order: Sequence[str]) -> dict[str, str]:
    return {name: descriptions[name] for name in order}


VARIANTS: dict[str, Variant] = {
    v.name: v
    for v in (
        Variant(
            "current",
            FRAME_QUESTION,
            dict(FRAME_CLASS_DESCRIPTIONS),
            note="gate.py as it stands: FRAME_QUESTION + FRAME_CLASS_DESCRIPTIONS",
        ),
        Variant(
            "sharp",
            FRAME_QUESTION,
            dict(SHARP_DESCRIPTIONS),
            note="same question; descriptions name body parts at any distance; unclear means unreadable",
        ),
        Variant(
            "car_camera",
            CAR_CAMERA_QUESTION,
            dict(SHARP_DESCRIPTIONS),
            note="sharp descriptions; the question names the camera on a small car on the floor",
        ),
        Variant(
            "person_first",
            FRAME_QUESTION,
            _ordered(
                SHARP_DESCRIPTIONS, ("person_in_frame", "obstacle_near", "off_surface", "unclear", "clear")
            ),
            note="sharp descriptions; person_in_frame listed first, clear last",
        ),
        Variant(
            "two_step",
            FRAME_QUESTION,
            dict(FRAME_CLASS_DESCRIPTIONS),
            person_noul=PERSON_NOUL_QUESTION,
            note="yes/no 'is a person visible' first; P(yes) >= 0.5 is person_in_frame, else the choice",
        ),
    )
}


# -- frame sets --------------------------------------------------------------------------------


@dataclass(frozen=True)
class FrameItem:
    path: Path
    label: str
    jpeg: bytes = field(repr=False)

    @property
    def expected(self) -> tuple[str, ...]:
        return EXPECTED_CLASSES.get(self.label, ())


def parse_frames_spec(spec: str) -> tuple[Path, str | None]:
    """``DIR`` or ``DIR:LABEL``. A drive letter is not a concern on this project (macOS/Linux)."""
    directory, sep, label = spec.rpartition(":")
    if not sep or "/" in label or not label:
        return Path(spec), None
    if label not in EXPECTED_CLASSES:
        raise CalibrationError(
            f"unknown label {label!r} in {spec!r}; known: {', '.join(sorted(EXPECTED_CLASSES))}"
        )
    return Path(directory), label


def load_frame_set(spec: str) -> list[FrameItem]:
    directory, label = parse_frames_spec(spec)
    if not directory.is_dir():
        raise CalibrationError(f"not a directory: {directory}")
    items: list[FrameItem] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in JPEG_SUFFIXES or not path.is_file():
            continue
        own = label if label is not None else (path.stem if path.stem in EXPECTED_CLASSES else UNLABELLED)
        items.append(FrameItem(path, own, path.read_bytes()))
    if not items:
        raise CalibrationError(f"no JPEG frames under {directory}")
    return items


# -- asking ------------------------------------------------------------------------------------


def ask_variant(decider: ChoiceDecider, variant: Variant, jpeg: bytes) -> dict[str, Any]:
    """One answer for one frame under ``variant``: ``{"class", "probability", "latency_ms",
    "probabilities", "person_p", "overridden", "steps"}``. Raises ``DeciderUnavailable`` like the
    client. ``steps`` is the number of questions asked (1 for a plain choice, 2 for the gate's ask).
    """
    if variant.person_noul is not None:
        person, choice, latency = ask_frame_questions(decider, jpeg)
        cls, p, note = combine_frame_answers(
            float(person["probability"]), str(choice["class"]), float(choice["probability"]), DENY_THRESHOLD
        )
        return {
            "class": cls,
            "probability": p,
            "latency_ms": latency,
            "probabilities": {str(k): float(v) for k, v in choice["probabilities"].items()},
            "person_p": float(person["probability"]),
            "overridden": note,
            "steps": 2,
        }
    choice = decider.ask_choice(variant.question, variant.descriptions, jpeg, context=variant.state)
    return {
        "class": str(choice["class"]),
        "probability": float(choice["probability"]),
        "latency_ms": int(choice["latency_ms"]),
        "probabilities": {str(k): float(v) for k, v in choice["probabilities"].items()},
        "person_p": None,
        "overridden": None,
        "steps": 1,
    }


def gate_outcome(cls: str, p: float) -> str:
    """What the unchanged decision table does with this answer (frame stage only)."""
    if cls in DENY_CLASSES and p >= DENY_THRESHOLD:
        return "Deny"
    if cls == "obstacle_near":
        return "Guide"
    return "Proceed"


def expected_outcome(label: str) -> str | None:
    """The outcome a labelled frame should produce; ``None`` when the label admits several."""
    expected = EXPECTED_CLASSES.get(label)
    if not expected:
        return None
    outcomes = {gate_outcome(c, 1.0) for c in expected}
    return outcomes.pop() if len(outcomes) == 1 else None


# -- scoring -----------------------------------------------------------------------------------


def score_label(answers: Sequence[dict[str, Any]], label: str) -> dict[str, Any]:
    """Aggregate the answers of one label under one variant."""
    expected = EXPECTED_CLASSES.get(label, ())
    want = expected_outcome(label)
    classes = [a["class"] for a in answers]
    counts = Counter(classes)
    chosen_p = [float(a["probability"]) for a in answers]
    lat = [float(a["latency_ms"]) for a in answers]
    class_ok = sum(1 for a in answers if a["class"] in expected)
    gate_ok = sum(
        1 for a in answers if want is not None and gate_outcome(a["class"], a["probability"]) == want
    )
    strict_ok = sum(
        1
        for a in answers
        if a["class"] in expected and (want is None or gate_outcome(a["class"], a["probability"]) == want)
    )
    deny_held = sum(1 for a in answers if gate_outcome(a["class"], a["probability"]) == "Deny")
    # Mean probability the model put on the expected class (first expected when several).
    p_expected: list[float] = []
    if expected:
        for a in answers:
            probs = a.get("probabilities") or {}
            p_expected.append(max(float(probs.get(c, 0.0)) for c in expected))
    n = len(answers)
    return {
        "label": label,
        "expected": list(expected),
        "expected_outcome": want,
        "n": n,
        "class_counts": dict(counts.most_common()),
        "majority": counts.most_common(1)[0][0] if counts else None,
        "mean_p_chosen": round(statistics.fmean(chosen_p), 4) if chosen_p else None,
        "mean_p_expected": round(statistics.fmean(p_expected), 4) if p_expected else None,
        "class_accuracy": round(class_ok / n, 4) if n and expected else None,
        "gate_accuracy": round(gate_ok / n, 4) if n and want is not None else None,
        "strict_accuracy": round(strict_ok / n, 4) if n and expected else None,
        "deny_held": round(deny_held / n, 4) if n else None,
        "latency": summarise_latency(lat),
        "steps_mean": round(statistics.fmean(a.get("steps", 1) for a in answers), 2) if answers else None,
    }


def run_variant(
    decider: ChoiceDecider,
    variant: Variant,
    frames: Sequence[FrameItem],
    *,
    repeats: int = 1,
    log: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    """Ask every frame ``repeats`` times under ``variant``; one warm-up call on the first frame."""
    if repeats < 1:
        raise CalibrationError("repeats must be >= 1")
    by_label: dict[str, list[dict[str, Any]]] = {}
    per_frame: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        ask_variant(decider, variant, frames[0].jpeg)  # warm-up, excluded
    except DeciderUnavailable as exc:
        errors.append({"frame": "warm-up", "error": str(exc)})
    for item in frames:
        for _ in range(repeats):
            try:
                answer = ask_variant(decider, variant, item.jpeg)
            except DeciderUnavailable as exc:
                errors.append({"frame": item.path.name, "error": str(exc)})
                log(f"[{variant.name}] {item.label:16s} {item.path.name:24s} -> error: {exc}")
                continue
            by_label.setdefault(item.label, []).append(answer)
            per_frame.append(
                {
                    "frame": item.path.name,
                    "label": item.label,
                    "class": answer["class"],
                    "probability": round(answer["probability"], 4),
                    "latency_ms": answer["latency_ms"],
                    "steps": answer["steps"],
                    "person_p": None if answer["person_p"] is None else round(answer["person_p"], 4),
                    "overridden": answer["overridden"],
                    "outcome": gate_outcome(answer["class"], answer["probability"]),
                    "probabilities": {k: round(v, 4) for k, v in answer["probabilities"].items()},
                }
            )
            log(
                f"[{variant.name}] {item.label:16s} {item.path.name:24s} -> "
                f"{answer['class']} p={answer['probability']:.2f} {answer['latency_ms']} ms"
            )
    labels = {lbl: score_label(answers, lbl) for lbl, answers in by_label.items()}
    all_lat = [float(a["latency_ms"]) for answers in by_label.values() for a in answers]
    scored = [s for s in labels.values() if s["strict_accuracy"] is not None]
    return {
        "variant": variant.name,
        "question": variant.question,
        "descriptions": variant.descriptions,
        "state": variant.state,
        "person_noul": variant.person_noul,
        "note": variant.note,
        "labels": labels,
        "frames": per_frame,
        "errors": errors,
        "latency": summarise_latency(all_lat),
        "strict_accuracy_mean": round(statistics.fmean(s["strict_accuracy"] for s in scored), 4)
        if scored
        else None,
    }


def pick_best(results: Sequence[dict[str, Any]], *, min_rate: float = 0.9) -> dict[str, Any] | None:
    """The selection rule, in code so the report cannot drift from it.

    Required: person frames -> class ``person_in_frame`` with the Deny holding (``strict_accuracy``,
    so an ``unclear`` Deny does not count); clear frames -> ``clear``; dark or covered frames ->
    ``unclear`` with the Deny holding. A variant must reach ``min_rate`` on each (default 0.9: one
    miss in ten real frames is reported, not hidden). Ties go to the higher mean strict accuracy
    over every labelled set, then to the lower p95 latency. ``None`` when no variant qualifies.
    """

    def requirements(res: dict[str, Any]) -> tuple[float, float, float]:
        labels = res["labels"]
        person = float((labels.get("person_in_frame") or {}).get("strict_accuracy") or 0.0)
        clear = float((labels.get("clear") or {}).get("strict_accuracy") or 0.0)
        dark_rows = [labels[lbl] for lbl in ("unclear", "hand_over_lens") if lbl in labels]
        dark = min((float(r["strict_accuracy"] or 0.0) for r in dark_rows), default=0.0)
        return person, clear, dark

    eligible = [r for r in results if all(v >= min_rate for v in requirements(r))]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda r: (r["strict_accuracy_mean"] or 0.0, -(r["latency"]["p95_ms"] or float("inf"))),
    )


# -- report --------------------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.0f}%"


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def to_markdown(report: dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        f"# Frame-question calibration: {meta['model']}",
        "",
        f"- decider `{meta['url']}` ({meta['health'].get('device')}, vision {meta['health'].get('vision')}),"
        f" {meta['started_utc']}, repeats {meta['repeats']}, wall {meta['wall_s']} s",
        f"- frame sets: {', '.join(meta['frame_sets'])}; labels: "
        + ", ".join(f"{lbl} x{n}" for lbl, n in meta["label_counts"].items()),
        f"- deny threshold {DENY_THRESHOLD} on {', '.join(DENY_CLASSES)} (unchanged)",
        "",
        "## Variants",
        "",
        "| variant | person -> person_in_frame, deny held | clear -> clear | dark -> unclear, deny held"
        " | strict accuracy, all labelled | p50 / p95 ms | note |",
        "|---|---|---|---|---|---|---|",
    ]
    for res in report["variants"]:
        labels = res["labels"]
        person = labels.get("person_in_frame", {})
        clear = labels.get("clear", {})
        dark = [labels[lbl] for lbl in ("unclear", "hand_over_lens") if lbl in labels]
        dark_rate = min((float(r["strict_accuracy"] or 0.0) for r in dark), default=None)
        lines.append(
            f"| {res['variant']} | {_pct(person.get('strict_accuracy'))}"
            f" (mean p {person.get('mean_p_chosen', '-')})"
            f" | {_pct(clear.get('strict_accuracy'))} (mean p {clear.get('mean_p_chosen', '-')})"
            f" | {_pct(dark_rate)} | {_pct(res['strict_accuracy_mean'])}"
            f" | {_ms(res['latency']['p50_ms'])} / {_ms(res['latency']['p95_ms'])} | {res['note']} |"
        )
    best = report.get("best")
    lines += ["", f"**Selected: `{best}`**" if best else "**No variant met all three requirements.**", ""]
    for res in report["variants"]:
        lines += [
            f"## {res['variant']}",
            "",
            f"Question: `{res['question']}`"
            + (f"; two-step noul: `{res['person_noul']}`" if res["person_noul"] else ""),
            "",
            "| label | n | classes (count) | mean p chosen | mean p expected | class acc | gate acc"
            " | strict | deny held | p50 / p95 ms |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for lbl, row in sorted(res["labels"].items()):
            counts = ", ".join(f"{c} {n}" for c, n in row["class_counts"].items())
            lines.append(
                f"| {lbl} | {row['n']} | {counts} | {row['mean_p_chosen']} | {row['mean_p_expected'] or '-'}"
                f" | {_pct(row['class_accuracy'])} | {_pct(row['gate_accuracy'])}"
                f" | {_pct(row['strict_accuracy'])} | {_pct(row['deny_held'])}"
                f" | {_ms(row['latency']['p50_ms'])} / {_ms(row['latency']['p95_ms'])} |"
            )
        if res["errors"]:
            lines.append("")
            lines.append(
                f"Errors: {len(res['errors'])} (" + "; ".join(e["error"] for e in res["errors"][:3]) + ")"
            )
        lines.append("")
    return "\n".join(lines)


# -- CLI -----------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m deepracer_agent.calibrate_frames",
        description="Ask the decider the frame question under several wordings and score them.",
    )
    parser.add_argument(
        "--frames",
        action="append",
        required=True,
        metavar="DIR[:LABEL]",
        help="a directory of JPEGs; with :LABEL every file carries that label (repeatable)",
    )
    parser.add_argument(
        "--decider", default=None, help=f"decider URL (default $DECIDER_URL or {DEFAULT_DECIDER_URL})"
    )
    parser.add_argument(
        "--variant",
        action="append",
        choices=sorted(VARIANTS),
        help="variant to run (repeatable; default: all)",
    )
    parser.add_argument("--repeats", type=int, default=1, help="timed asks per frame per variant (default 1)")
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="client timeout per call in seconds (default 30)"
    )
    parser.add_argument("--out", type=Path, default=None, help="output dir (default runs/calib/<UTC stamp>)")
    parser.add_argument("--quiet", action="store_true", help="no per-frame progress on stderr")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    url = (args.decider or os.environ.get("DECIDER_URL") or DEFAULT_DECIDER_URL).rstrip("/")
    try:
        frames = [item for spec in args.frames for item in load_frame_set(spec)]
        names = args.variant or list(VARIANTS)
        variants = [VARIANTS[n] for n in names]
    except CalibrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    client = DeciderClient(url, timeout_s=args.timeout)
    try:
        health = client.health()
    except DeciderUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    log = (lambda _m: None) if args.quiet else (lambda m: print(m, file=sys.stderr))
    started = time.perf_counter()
    results = [run_variant(client, v, frames, repeats=args.repeats, log=log) for v in variants]
    client.close()
    best = pick_best(results)
    report = {
        "meta": {
            "url": url,
            "model": health.get("model"),
            "health": health,
            "started_utc": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "wall_s": round(time.perf_counter() - started, 1),
            "repeats": args.repeats,
            "timeout_s": args.timeout,
            "frame_sets": list(args.frames),
            "label_counts": dict(Counter(item.label for item in frames)),
            "deny_threshold": DENY_THRESHOLD,
        },
        "variants": results,
        "best": best["variant"] if best else None,
    }
    out = args.out or Path("runs") / "calib" / _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = to_markdown(report)
    (out / "calibration.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nwritten: {out / 'calibration.json'}, {out / 'calibration.md'}", file=sys.stderr)
    return 0


__all__ = [
    "DENY_THRESHOLD",
    "VARIANTS",
    "CalibrationError",
    "Variant",
    "ask_variant",
    "expected_outcome",
    "gate_outcome",
    "load_frame_set",
    "parse_frames_spec",
    "pick_best",
    "run_variant",
    "score_label",
    "to_markdown",
]

if __name__ == "__main__":
    sys.exit(main())
