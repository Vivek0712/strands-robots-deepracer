"""Benchmark the gate's two questions against any strands-decider server, with numbers we can quote.

Before every hop the gate asks the decider two things: is this command inside the briefed
envelope (a yes/no), and what is in front of the camera (one of five classes). This tool
asks exactly those two questions, built from the same code the gate uses, against whatever
server ``DECIDER_URL`` points at: the fake decider in CI, or a real model on this laptop.
It replays the seven drawn harness frames N times each and a fixed table of commands inside
and outside the envelope, throws away the warm-up call, and reports p50/p95 latency per
question type, the class and probability per frame, agreement with the frame's intended
label, and envelope yes/no accuracy. The result is what the stop-latency budget and the
booth model choice are argued from. Physics stops the car; the decider explains; this
measures how fast and how well it explains.

The envelope table runs twice: ``as_gate`` sends the state the gate sends, including the
``deterministic_check`` line that already states the answer, and ``blind`` drops that line so
the model has to read the numbers itself. The harness frames are Pillow drawings (a stick
figure, a box, a dark frame), not camera frames: agreement here shows the pipeline and the
class vocabulary work, not how the model does on real booth frames.

Run::

    .venv/bin/python -m deepracer_agent.bench_decider --url http://127.0.0.1:8111 --repeats 10 \\
        --extra load_s=41.2 --extra rss_mb=5120

Output: a Markdown summary on stdout plus ``bench.json`` and ``bench.md`` in ``--out`` (default
``runs/bench/<UTC stamp>-<model>/``). Exit status 0 on a completed run, 2 when the server's
``/health`` does not answer.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import platform
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .decider_client import DEFAULT_DECIDER_URL, DeciderClient, DeciderUnavailable
from .gate import (
    ENVELOPE_QUESTION,
    FRAME_CLASS_DESCRIPTIONS,
    FRAME_CLASSES,
    FRAME_QUESTION,
    Envelope,
    envelope_context,
)

#: The gate's per-question budget (CONTRACTS section 7): anything slower is a Deny("vision unavailable").
GATE_BUDGET_MS = 1500
#: Which decider class(es) count as agreeing with each harness frame label.
EXPECTED_CLASSES: dict[str, tuple[str, ...]] = {
    "clear": ("clear",),
    "obstacle_near": ("obstacle_near",),
    "person_in_frame": ("person_in_frame",),
    "off_surface": ("off_surface",),
    "unclear": ("unclear",),
    "sign": ("clear", "unclear"),
    "hand_over_lens": ("unclear",),
}
FAKE_MODEL_NAME = "fake-decider"


@dataclass(frozen=True)
class EnvelopeCase:
    """One command and whether it is inside the default :class:`Envelope`."""

    name: str
    linear: float
    angular: float
    duration: float
    inside: bool


#: Fixed table against the default envelope (|linear| <= 0.3, |angular| <= 1.0, duration <= 2 s, both ways).
ENVELOPE_CASES: tuple[EnvelopeCase, ...] = (
    EnvelopeCase("hop_forward", 0.2, 0.0, 0.5, True),
    EnvelopeCase("hop_backward", -0.2, 0.0, 0.5, True),
    EnvelopeCase("cap_speed_cap_duration", 0.3, 0.0, 2.0, True),
    EnvelopeCase("gentle_arc", 0.1, 0.5, 1.0, True),
    EnvelopeCase("cap_angular", 0.3, 1.0, 0.5, True),
    EnvelopeCase("reverse_arc_at_caps", -0.3, -1.0, 2.0, True),
    EnvelopeCase("creep", 0.05, 0.0, 0.2, True),
    EnvelopeCase("too_fast", 0.5, 0.0, 0.5, False),
    EnvelopeCase("way_too_fast", 1.0, 0.0, 0.5, False),
    EnvelopeCase("too_fast_backward", -0.6, 0.0, 0.5, False),
    EnvelopeCase("too_long", 0.2, 0.0, 3.0, False),
    EnvelopeCase("far_too_long", 0.3, 0.0, 10.0, False),
    EnvelopeCase("too_sharp", 0.2, 1.5, 0.5, False),
    EnvelopeCase("too_sharp_negative", 0.2, -2.0, 1.0, False),
)


class BenchError(ValueError):
    """Bad benchmark arguments; the message is the reason string."""


def percentile(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile (``q`` in 0..100); ``None`` for an empty sample."""
    if not values:
        return None
    if not 0 <= q <= 100:
        raise BenchError(f"percentile must be within 0..100, got {q}")
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return float(ordered[rank - 1])


def summarise_latency(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "mean_ms": round(statistics.fmean(values), 1) if values else None,
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None,
        "over_budget": sum(1 for v in values if v > GATE_BUDGET_MS),
    }


def parse_extra(items: Iterable[str] | None) -> dict[str, Any]:
    """``key=value`` pairs for the report; numbers become numbers."""
    out: dict[str, Any] = {}
    for item in items or ():
        if "=" not in item:
            raise BenchError(f"--extra expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise BenchError(f"--extra expects key=value, got {item!r}")
        try:
            out[key] = float(value) if re.fullmatch(r"[-+]?\d+(\.\d+)?", value.strip()) else value
        except ValueError:
            out[key] = value
    return out


def select_labels(requested: str | None, known: Sequence[str]) -> list[str]:
    if not requested:
        return list(known)
    labels = [x.strip() for x in requested.split(",") if x.strip()]
    unknown = [x for x in labels if x not in known]
    if unknown:
        raise BenchError(f"unknown frame label(s) {', '.join(unknown)}; known: {', '.join(known)}")
    if not labels:
        raise BenchError("--labels must name at least one frame label")
    return labels


def load_frames(directory: Path | None, labels: Sequence[str]) -> dict[str, bytes]:
    """Generate the harness frames (no people, only drawings) into ``directory`` and load them."""
    from harness.frames import ensure_frames

    target = directory or Path(tempfile.mkdtemp(prefix="bench-frames-"))
    paths = ensure_frames(target)
    return {label: paths[label].read_bytes() for label in labels}


class Bench:
    """One benchmark run against ``url``. Call :meth:`run`; the result dict is also in ``self.result``."""

    def __init__(
        self,
        url: str | None = None,
        *,
        repeats: int = 10,
        timeout_s: float = 10.0,
        envelope: Envelope | None = None,
        labels: Sequence[str] | None = None,
        frames_dir: Path | None = None,
        blind: bool = True,
        extra: dict[str, Any] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        if repeats < 1:
            raise BenchError("repeats must be >= 1")
        if timeout_s <= 0:
            raise BenchError("timeout must be > 0 seconds")
        from harness.frames import LABELS

        self.url = (url or os.environ.get("DECIDER_URL") or DEFAULT_DECIDER_URL).rstrip("/")
        self.repeats = repeats
        self.timeout_s = timeout_s
        self.envelope = envelope or Envelope()
        self.labels = select_labels(",".join(labels) if labels else None, LABELS)
        self.frames_dir = frames_dir
        self.blind = blind
        self.extra = dict(extra or {})
        self.log = log or (lambda _msg: None)
        self.client = DeciderClient(self.url, timeout_s=timeout_s)
        self.result: dict[str, Any] = {}
        self._is_fake = False

    # -- helpers -------------------------------------------------------------------------

    def _set_fake_label(self, label: str) -> None:
        """The fake decider answers from the shared label, not the pixels; tell it what it sees."""
        if not self._is_fake:
            return
        with httpx.Client(base_url=self.url, timeout=5) as c:
            c.get("/control", params={"label": label}).raise_for_status()

    def _ask_choice(self, jpeg: bytes) -> dict[str, Any] | str:
        try:
            return self.client.ask_choice(FRAME_QUESTION, FRAME_CLASS_DESCRIPTIONS, jpeg)
        except DeciderUnavailable as exc:
            return str(exc)

    def _ask_noul(self, context: dict[str, Any]) -> dict[str, Any] | str:
        try:
            return self.client.ask_noul(ENVELOPE_QUESTION, context)
        except DeciderUnavailable as exc:
            return str(exc)

    # -- stages --------------------------------------------------------------------------

    def frames_stage(self, frames: dict[str, bytes]) -> tuple[list[dict[str, Any]], list[float]]:
        rows: list[dict[str, Any]] = []
        latencies: list[float] = []
        for label, jpeg in frames.items():
            self._set_fake_label(label)
            warm = self._ask_choice(jpeg)  # warm-up, excluded
            warm_note = warm if isinstance(warm, str) else None
            classes: list[str] = []
            chosen_p: list[float] = []
            lat: list[float] = []
            prob_sum: Counter[str] = Counter()
            errors: list[str] = []
            for _ in range(self.repeats):
                out = self._ask_choice(jpeg)
                if isinstance(out, str):
                    errors.append(out)
                    continue
                classes.append(out["class"])
                chosen_p.append(float(out["probability"]))
                lat.append(float(out["latency_ms"]))
                for k, v in out["probabilities"].items():
                    prob_sum[k] += float(v)
            n_ok = len(classes)
            counts = Counter(classes)
            majority = counts.most_common(1)[0][0] if counts else None
            expected = EXPECTED_CLASSES.get(label, ())
            agree = sum(1 for c in classes if c in expected)
            rows.append(
                {
                    "label": label,
                    "expected": list(expected),
                    "chosen": majority,
                    "chosen_probability": round(statistics.fmean(chosen_p), 4) if chosen_p else None,
                    "agreement": round(agree / n_ok, 4) if n_ok else None,
                    "class_counts": dict(counts),
                    "mean_probabilities": {k: round(v / n_ok, 4) for k, v in prob_sum.items()}
                    if n_ok
                    else {},
                    "latency": summarise_latency(lat),
                    "latencies_ms": lat,
                    "errors": errors,
                    "warm_up_error": warm_note,
                    "jpeg_bytes": len(jpeg),
                }
            )
            latencies.extend(lat)
            self.log(
                f"frame {label:16s} -> {majority} p={rows[-1]['chosen_probability']} "
                f"agree={rows[-1]['agreement']} p50={rows[-1]['latency']['p50_ms']} ms"
                + (f" errors={len(errors)}" if errors else "")
            )
        return rows, latencies

    def envelope_stage(self, *, blind: bool) -> tuple[dict[str, Any], list[float]]:
        variant = "blind" if blind else "as_gate"
        cases: list[dict[str, Any]] = []
        latencies: list[float] = []
        first = ENVELOPE_CASES[0]
        self._ask_noul(self._context(first, blind))  # warm-up, excluded
        correct = total = 0
        for case in ENVELOPE_CASES:
            context = self._context(case, blind)
            yes_votes = 0
            probs: list[float] = []
            lat: list[float] = []
            errors: list[str] = []
            for _ in range(self.repeats):
                out = self._ask_noul(context)
                if isinstance(out, str):
                    errors.append(out)
                    continue
                yes_votes += int(bool(out["yes"]))
                probs.append(float(out["probability"]))
                lat.append(float(out["latency_ms"]))
            n_ok = len(probs)
            right = yes_votes if case.inside else n_ok - yes_votes
            correct += right
            total += n_ok
            cases.append(
                {
                    "name": case.name,
                    "linear": case.linear,
                    "angular": case.angular,
                    "duration": case.duration,
                    "inside": case.inside,
                    "mean_p_inside": round(statistics.fmean(probs), 4) if probs else None,
                    "yes_votes": yes_votes,
                    "n": n_ok,
                    "accuracy": round(right / n_ok, 4) if n_ok else None,
                    "latency": summarise_latency(lat),
                    "errors": errors,
                }
            )
            latencies.extend(lat)
        accuracy = round(correct / total, 4) if total else None
        self.log(f"envelope[{variant}] accuracy={accuracy} over {total} answers")
        return {
            "variant": variant,
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "cases": cases,
        }, latencies

    def _context(self, case: EnvelopeCase, blind: bool) -> dict[str, Any]:
        context = envelope_context(self.envelope, case.linear, case.angular, case.duration)
        if blind:
            context.pop("deterministic_check", None)
        return context

    # -- run -----------------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        health = self.client.health()  # raises DeciderUnavailable: nothing to measure
        self._is_fake = health.get("model") == FAKE_MODEL_NAME
        self.log(f"decider {health.get('model')} on {health.get('device')} vision={health.get('vision')}")
        frames = load_frames(self.frames_dir, self.labels)
        frame_rows, choice_lat = self.frames_stage(frames)
        envelope: dict[str, Any] = {}
        noul_lat: list[float] = []
        as_gate, lat = self.envelope_stage(blind=False)
        envelope["as_gate"] = as_gate
        noul_lat.extend(lat)
        if self.blind:
            blind_res, lat = self.envelope_stage(blind=True)
            envelope["blind"] = blind_res
            noul_lat.extend(lat)
        noul = summarise_latency(noul_lat)
        choice = summarise_latency(choice_lat)
        gate = {
            "p50_sum_ms": _sum_or_none(noul["p50_ms"], choice["p50_ms"]),
            "p95_sum_ms": _sum_or_none(noul["p95_ms"], choice["p95_ms"]),
            "budget_ms_per_question": GATE_BUDGET_MS,
            "note": "gate = frame grab + envelope (noul) + frame (choice), sequential; grab not included",
        }
        agreements = [r["agreement"] for r in frame_rows if r["agreement"] is not None]
        self.result = {
            "meta": {
                "url": self.url,
                "model": health.get("model"),
                "health": health,
                "started_utc": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "wall_s": round(time.perf_counter() - started, 1),
                "repeats": self.repeats,
                "timeout_s": self.timeout_s,
                "envelope": self.envelope.to_dict(),
                "labels": self.labels,
                "frame_classes": list(FRAME_CLASSES),
                "machine": {"platform": platform.platform(), "machine": platform.machine()},
                "extra": self.extra,
                "fake": self._is_fake,
            },
            "latency": {"noul": noul, "choice": choice, "gate_estimate": gate},
            "frames": frame_rows,
            "frame_agreement_mean": round(statistics.fmean(agreements), 4) if agreements else None,
            "envelope": envelope,
        }
        return self.result

    def close(self) -> None:
        self.client.close()


def _sum_or_none(*values: float | None) -> float | None:
    if any(v is None for v in values):
        return None
    return round(sum(float(v) for v in values if v is not None), 1)


# -- report --------------------------------------------------------------------------------


def _fmt(value: Any, digits: int = 0) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def to_markdown(result: dict[str, Any]) -> str:
    meta = result["meta"]
    lat = result["latency"]
    lines = [
        f"# Decider benchmark: {meta['model']}",
        "",
        f"- URL `{meta['url']}`, device `{meta['health'].get('device')}`,"
        f" vision `{meta['health'].get('vision')}`, checkpoint `{meta['health'].get('checkpoint')}`",
        f"- {meta['started_utc']}, repeats {meta['repeats']} per frame/case (warm-up excluded),"
        f" client timeout {meta['timeout_s']} s, wall {meta['wall_s']} s",
        f"- machine {meta['machine']['platform']} ({meta['machine']['machine']})",
    ]
    if meta["extra"]:
        lines.append("- extra: " + ", ".join(f"{k}={v}" for k, v in meta["extra"].items()))
    if meta["fake"]:
        lines.append("- **fake decider**: answers come from the harness label, not a model")
    lines += [
        "",
        "## Latency (client round trip, ms)",
        "",
        "| question | n | p50 | p95 | mean | max | over 1500 ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in ("noul", "choice"):
        s = lat[name]
        lines.append(
            f"| {name} | {s['n']} | {_fmt(s['p50_ms'])} | {_fmt(s['p95_ms'])} | {_fmt(s['mean_ms'], 1)} |"
            f" {_fmt(s['max_ms'])} | {s['over_budget']} |"
        )
    g = lat["gate_estimate"]
    lines += [
        "",
        f"Gate estimate (noul + choice, sequential, no frame grab): p50 {_fmt(g['p50_sum_ms'])} ms,"
        f" p95 {_fmt(g['p95_sum_ms'])} ms.",
        "",
        "## Frames (drawn harness frames, 480x360 JPEG)",
        "",
        "| label | expected | chosen | p(chosen) | agreement | p50 ms | p95 ms | errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in result["frames"]:
        lines.append(
            f"| {r['label']} | {' or '.join(r['expected'])} | {r['chosen']} |"
            f" {_fmt(r['chosen_probability'], 2)} |"
            f" {_fmt(r['agreement'], 2)} | {_fmt(r['latency']['p50_ms'])} | {_fmt(r['latency']['p95_ms'])} |"
            f" {len(r['errors'])} |"
        )
    lines += ["", f"Mean agreement over frames: {_fmt(result['frame_agreement_mean'], 3)}", ""]
    lines += ["### Mean class probabilities per frame", "", "| label | " + " | ".join(FRAME_CLASSES) + " |"]
    lines.append("|---|" + "---|" * len(FRAME_CLASSES))
    for r in result["frames"]:
        mp = r["mean_probabilities"]
        lines.append(f"| {r['label']} | " + " | ".join(_fmt(mp.get(c), 2) for c in FRAME_CLASSES) + " |")
    lines += ["", "## Envelope (noul yes/no)", ""]
    for variant, block in result["envelope"].items():
        lines += [
            f"### {variant}: accuracy {_fmt(block['accuracy'], 3)} ({block['correct']}/{block['total']})",
            "",
            "| case | linear | angular | duration | inside | mean P(inside) | yes | accuracy | errors |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for c in block["cases"]:
            lines.append(
                f"| {c['name']} | {c['linear']} | {c['angular']} | {c['duration']} | {c['inside']} |"
                f" {_fmt(c['mean_p_inside'], 2)} | {c['yes_votes']}/{c['n']} | {_fmt(c['accuracy'], 2)} |"
                f" {len(c['errors'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_report(result: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "bench.json"
    md_path = out_dir / "bench.md"
    json_path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(result) + "\n", encoding="utf-8")
    return json_path, md_path


def default_out_dir(model: str | None) -> Path:
    stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model or "decider")
    return Path(__file__).resolve().parents[2] / "runs" / "bench" / f"{stamp}-{safe}"


# -- CLI -----------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="bench_decider", description=__doc__.splitlines()[0])
    ap.add_argument(
        "--url", default=None, help="decider root (default $DECIDER_URL or http://127.0.0.1:8111)"
    )
    ap.add_argument("--repeats", type=int, default=10, help="timed calls per frame and per envelope case")
    ap.add_argument("--timeout", type=float, default=10.0, help="client timeout per call, seconds")
    ap.add_argument("--labels", default=None, help="comma-separated subset of harness frame labels")
    ap.add_argument("--frames-dir", type=Path, default=None, help="where to write the generated frames")
    ap.add_argument("--no-blind", action="store_true", help="skip the envelope table without the hint")
    ap.add_argument("--out", type=Path, default=None, help="output directory for bench.json and bench.md")
    ap.add_argument(
        "--extra", action="append", default=[], metavar="KEY=VALUE", help="recorded in the report"
    )
    ap.add_argument("-q", "--quiet", action="store_true")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = (lambda _m: None) if args.quiet else (lambda m: print(m, file=sys.stderr, flush=True))
    try:
        bench = Bench(
            args.url,
            repeats=args.repeats,
            timeout_s=args.timeout,
            labels=select_labels(args.labels, _known_labels()),
            frames_dir=args.frames_dir,
            blind=not args.no_blind,
            extra=parse_extra(args.extra),
            log=log,
        )
    except BenchError as exc:
        print(f"bench_decider: {exc}", file=sys.stderr)
        return 2
    try:
        result = bench.run()
    except DeciderUnavailable as exc:
        print(f"bench_decider: decider at {bench.url} not usable: {exc}", file=sys.stderr)
        return 2
    finally:
        bench.close()
    out_dir = args.out or default_out_dir(result["meta"]["model"])
    json_path, md_path = write_report(result, out_dir)
    print(to_markdown(result))
    print(f"\nwrote {json_path}\nwrote {md_path}")
    return 0


def _known_labels() -> tuple[str, ...]:
    from harness.frames import LABELS

    return LABELS


__all__ = [
    "ENVELOPE_CASES",
    "EXPECTED_CLASSES",
    "GATE_BUDGET_MS",
    "Bench",
    "BenchError",
    "EnvelopeCase",
    "main",
    "parse_extra",
    "percentile",
    "select_labels",
    "summarise_latency",
    "to_markdown",
    "write_report",
]

if __name__ == "__main__":
    raise SystemExit(main())
