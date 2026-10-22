"""Rehearse the voice path with real audio and no microphone: synthesized speech into Nova Sonic.

Two utterances are synthesized with macOS ``say`` as 16 kHz mono 16-bit WAV ("Hop forward twenty
centimetres", "Roll forward slowly for two seconds and describe the pen") plus the one word "stop".
The rover's :class:`~deepracer_agent.voice.VoiceAgent` runs in audio mode on a
:class:`~deepracer_agent.voice_pcm.PcmInputStream` against the fake stack (fake car, console and
decider), so the hop is a real gated ``drive_deepracer`` over rosbridge. Sequence: press, play the
hop, release, wait for the motion events; then ask for the slow narrated roll and, while the rover
is speaking, press and play "stop": Nova Sonic reports the barge-in, ``BargeInStop`` calls
``stop_all`` and the event log carries ``voice barge_in`` and ``stop {cause: barge_in}`` with the
latency. Everything heard and said is written to the run dir (transcript, events.jsonl, the
rover's audio as WAV, ``summary.json``/``summary.md``) for ``docs/results``.

Headless run: ``STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`` pre-grants
the three command surfaces (said so here and in the evidence), and ``--auto-approve`` answers a
decider ``Confirm`` with yes, since no operator sits at this rehearsal. ``--fake`` runs the same
script on :class:`~deepracer_agent.voice.ScriptedBidiModel` with its fake ASR and no cloud, which
is how the script itself is tested. Physics stops the car; the decider explains.

    .venv/bin/python -m deepracer_agent.voice_rehearsal --stack --out /tmp/voice-rehearsal
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from strands.bidi.types.events import (
    BidiBargeInEvent,
    BidiConnectionStartEvent,
    BidiOutputEvent,
    BidiResponseStartEvent,
    BidiResponseStopEvent,
    BidiToolUseBlocksEvent,
)

from .gate import EventSink, resolve_event_log, voice_clock
from .voice_pcm import AudioSink, FilePcmInput, PcmInputStream

logger = logging.getLogger(__name__)

HOP = "Hop forward twenty centimetres"
ROLL = "Roll forward slowly for two seconds and describe the pen"
STOP = "stop"

#: The second fake stack's ports (CONTRACTS section 3 override column, Intelligence rehearsal).
REHEARSAL_ENV = {
    "DEEPRACER_BODY": "sim",
    "DEEPRACER_HOST": "127.0.0.1",
    "DEEPRACER_ROSBRIDGE_PORT": "9491",
    "DEEPRACER_CONSOLE_URL": "http://127.0.0.1:8490",
    "DEEPRACER_SIM_CONTROL_URL": "http://127.0.0.1:8492",
    "DECIDER_URL": "http://127.0.0.1:8511",
    "AWS_PROFILE": "heisenberg",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    #: Declared pre-grant for this headless run; the driver logs `approval {by: pregrant}` per motion.
    "STRANDS_ROS2_COMMAND_ALLOW": "/manual_drive,/vehicle_state,/enable_state",
}


# -- speech synthesis -------------------------------------------------------------------------------


def synthesize(text: str, path: Path, *, voice: str | None = None) -> Path:
    """``say -o path --file-format=WAVE --data-format=LEI16@16000 text`` (cached when the file exists)."""
    if path.exists():
        return path
    if shutil.which("say") is None:
        raise RuntimeError(
            "macOS `say` is not available; give --audio-dir with hop.wav, roll.wav and stop.wav"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["say", "-o", str(path), "--file-format=WAVE", "--data-format=LEI16@16000"]
    if voice:
        cmd += ["-v", voice]
    subprocess.run([*cmd, text], check=True, capture_output=True)
    return path


# -- the fake stack as a subprocess -----------------------------------------------------------------


class StackProcess:
    """``python -m harness.stack --deadman`` on the rehearsal ports, stopped on exit."""

    def __init__(self, out: Path, env: dict[str, str]) -> None:
        self.out = out
        self.env = env
        self.proc: subprocess.Popen[bytes] | None = None
        self.log = out / "stack.log"

    def start(self, timeout_s: float = 20.0) -> None:
        from harness.stack import _http_ok, _port_open

        self.out.mkdir(parents=True, exist_ok=True)
        fh = self.log.open("ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "harness.stack", "--deadman"],
            env={**os.environ, **self.env},
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        deadline = time.monotonic() + timeout_s
        port = int(self.env["DEEPRACER_ROSBRIDGE_PORT"])
        while time.monotonic() < deadline:
            if (
                _port_open("127.0.0.1", port)
                and _http_ok(self.env["DEEPRACER_SIM_CONTROL_URL"] + "/state")
                and _http_ok(self.env["DEEPRACER_CONSOLE_URL"] + "/login")
                and _http_ok(self.env["DECIDER_URL"] + "/health")
            ):
                return
            if self.proc.poll() is not None:
                raise RuntimeError(f"fake stack exited early (code {self.proc.returncode}); see {self.log}")
            time.sleep(0.1)
        raise TimeoutError(f"fake stack not ready in {timeout_s}s; see {self.log}")

    def stop(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


# -- an output stream that watches the conversation -------------------------------------------------


class Monitor:
    """Records every bidi event with a wall stamp and raises flags the script waits on."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.connected = asyncio.Event()
        self.barge_in = asyncio.Event()
        self.response_stops = 0
        self.tool_uses: list[dict[str, Any]] = []
        self.barge_in_at: float | None = None
        self.barge_in_t_ms: int | None = None

    async def start(self, agent: Any) -> None:
        return

    async def stop(self) -> None:
        return

    async def __call__(self, event: BidiOutputEvent) -> None:
        now = time.monotonic()
        name = type(event).__name__
        row: dict[str, Any] = {"t": round(now, 3), "event": name, "voice_t_ms": voice_clock.now_ms()}
        if isinstance(event, BidiConnectionStartEvent):
            self.connected.set()
        elif isinstance(event, BidiBargeInEvent):
            self.barge_in_at = now
            self.barge_in_t_ms = voice_clock.now_ms()
            self.barge_in.set()
        elif isinstance(event, BidiResponseStopEvent):
            self.response_stops += 1
        elif isinstance(event, BidiToolUseBlocksEvent):
            for use in event.tool_uses:
                self.tool_uses.append({"name": use["name"], "input": use.get("input", {})})
            row["tools"] = [u["name"] for u in event.tool_uses]
        elif isinstance(event, BidiResponseStartEvent):
            pass
        if name not in ("BidiAudioDeltaEvent",):  # one row per audio chunk would drown the record
            self.events.append(row)


# -- the rehearsal ------------------------------------------------------------------------------------


async def wait_until(predicate: Any, timeout_s: float, poll_s: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(poll_s)
    return bool(predicate())


async def wait_quiet(sink: AudioSink, quiet_s: float, timeout_s: float) -> bool:
    """True once the rover has been silent for ``quiet_s`` (speaking over its tail is a barge-in)."""

    def quiet() -> bool:
        if sink.speaking.is_set():
            return False
        return sink.last_audio_at is None or time.monotonic() - sink.last_audio_at >= quiet_s

    return await wait_until(quiet, timeout_s)


def _events_after(log: EventSink, seq: int, type: str | None = None) -> list[dict[str, Any]]:
    reader = getattr(log, "read", None)
    if not callable(reader):
        return []
    return [e for e in reader() if int(e.get("seq", 0)) > seq and (type is None or e.get("type") == type)]


def _last_seq(log: EventSink) -> int:
    rows = getattr(log, "read", lambda: [])()
    return int(rows[-1].get("seq", 0)) if rows else 0


def build_pieces(args: argparse.Namespace) -> tuple[Any, Any, EventSink, Any]:
    """``(voice_agent, runtime, event_log, approval)`` for ``--fake`` or the real Nova Sonic path."""
    from .voice import DEFAULT_SCRIPT, ScriptedBidiModel, _fake_pieces, _load_runtime_pieces, make_voice_agent

    if args.fake:
        log = resolve_event_log(beat=args.beat)
        runtime, tools, gate = _fake_pieces(log, args.beat)
        script = dict(DEFAULT_SCRIPT)
        script["roll"] = (
            "drive_deepracer",
            {"linear": 0.1, "angular": 0.0, "duration": 2.0},
            "Rolling forward slowly. The pen is a grey floor with white walls and no one in front of me.",
        )
        model = ScriptedBidiModel(script, barge_in_on=("stop",), audio_transcripts=[HOP, ROLL, STOP])
        va = make_voice_agent(tools, gate, runtime, model=model, event_log=log, beat=args.beat)
        return va, runtime, log, None
    runtime, tools, gate, log = _load_runtime_pieces(args.beat)
    approval = getattr(runtime, "approval", None)
    if args.auto_approve and approval is not None:
        approval.on_ask = lambda rid, prompt: approval.resolve(rid, True)
    va = make_voice_agent(tools, gate, runtime, model=args.model, event_log=log, beat=args.beat)
    return va, runtime, log, approval


async def rehearse(args: argparse.Namespace, audio: dict[str, Path]) -> dict[str, Any]:
    out = Path(args.out)
    summary: dict[str, Any] = {
        "mode": "fake" if args.fake else "nova-sonic",
        "model": "scripted" if args.fake else (args.model or "amazon.nova-2-5-sonic"),
        "env": {k: os.environ.get(k) for k in REHEARSAL_ENV},
        "pregrant": os.environ.get("STRANDS_ROS2_COMMAND_ALLOW"),
        "auto_approve": bool(args.auto_approve),
        "audio": {k: str(v) for k, v in audio.items()},
        "steps": [],
        "errors": [],
    }
    va, runtime, log, _approval = build_pieces(args)
    summary["run_dir"] = str(getattr(log, "run_dir", out))
    pcm = PcmInputStream(log, beat=args.beat)
    sink = AudioSink(wav_path=out / "rover.wav")
    monitor = Monitor()
    player = FilePcmInput(pcm, tail_ms=args.tail_ms)
    out_lines: list[str] = []

    def say(line: str) -> None:
        out_lines.append(line)
        print(line, flush=True)

    va.transcript.out = say

    def step(label: str, ok: bool, detail: str = "", **extra: Any) -> None:
        row = {"label": label, "ok": bool(ok), "detail": detail, **extra}
        summary["steps"].append(row)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{': ' + detail if detail else ''}", flush=True)

    voice_task = asyncio.create_task(va.run_pcm(pcm, outputs=[sink, monitor]), name="voice")

    async def fail_if_voice_died() -> None:
        if voice_task.done():
            exc = voice_task.exception() if not voice_task.cancelled() else None
            raise RuntimeError(
                f"voice agent ended early: {type(exc).__name__}: {exc}" if exc else "voice task ended"
            )

    try:
        # 0. connect
        t0 = time.monotonic()
        waiter = asyncio.create_task(monitor.connected.wait())
        done, _ = await asyncio.wait(
            {waiter, voice_task}, timeout=args.connect_timeout, return_when="FIRST_COMPLETED"
        )
        if waiter not in done:
            waiter.cancel()
            await fail_if_voice_died()
            raise TimeoutError(f"no BidiConnectionStartEvent within {args.connect_timeout}s")
        await fail_if_voice_died()
        step("Nova Sonic connection open", True, f"{round((time.monotonic() - t0) * 1000)} ms")
        if not args.fake:
            pre = await runtime.preflight()
            step(
                "preflight (arms the heartbeat)",
                bool(pre.get("go")),
                ", ".join(pre.get("reasons") or []) or "go",
            )
        await asyncio.sleep(args.settle_s)  # let the first silence frames open the audio content

        # 1. the hop
        seq = _last_seq(log)
        stops_before = monitor.response_stops
        rec = await player.play(audio["hop"], label="hop")
        step(
            "hop utterance streamed while pressed",
            rec["bytes"] > 0,
            f"{rec['frames']} frames, {rec['duration_s']} s",
        )
        moved = await wait_until(
            lambda: (
                any((m.get("payload") or {}).get("state") == "end" for m in _events_after(log, seq, "motion"))
                or any(
                    (v.get("payload") or {}).get("action") == "Deny"
                    for v in _events_after(log, seq, "verdict")
                )
            ),
            args.turn_timeout,
        )
        await wait_until(lambda: monitor.response_stops > stops_before, 20.0)
        quiet = await wait_quiet(sink, args.quiet_s, 30.0)
        step(
            "hop: rover finished speaking before the next press",
            quiet,
            f"{round(sink.seconds_heard(), 2)} s heard",
        )
        motions = _events_after(log, seq, "motion")
        verdicts = [v["payload"] for v in _events_after(log, seq, "verdict")]
        transcript_events = [
            e["payload"]["text"]
            for e in _events_after(log, seq, "voice")
            if e["payload"].get("event") == "transcript"
        ]
        step(
            "hop: user transcript heard",
            bool(transcript_events),
            " | ".join(t for t in transcript_events if t) or "no transcript",
        )
        step(
            "hop: gated drive produced motion events",
            moved and bool(motions),
            f"{len(motions)} motion events, verdicts {[v['action'] for v in verdicts]}, "
            f"tools {[t['name'] for t in monitor.tool_uses]}",
        )
        summary["hop"] = {
            "play": rec,
            "transcripts": transcript_events,
            "verdicts": verdicts,
            "motions": [m["payload"] for m in motions],
            "tool_uses": list(monitor.tool_uses),
            "rover_said": [t for r, t in va.transcript.lines if r == "rover"],
        }

        # 2. the narrated roll, then "stop" over the narration
        seq2 = _last_seq(log)
        tools_before = len(monitor.tool_uses)
        stops_before = monitor.response_stops
        starts_before = sink.audio_starts
        lines_before = len(va.transcript.lines)
        rec_roll = await player.play(audio["roll"], label="roll")
        # narration follows the roll's tool results: wait for the drive call, then a new response's audio
        asked = await wait_until(lambda: len(monitor.tool_uses) > tools_before, args.turn_timeout)
        step(
            "roll: the rover called a tool for the roll",
            asked,
            ", ".join(t["name"] for t in monitor.tool_uses[tools_before:]) or "no tool call",
        )
        speaking = await wait_until(lambda: sink.audio_starts > starts_before, args.turn_timeout)
        step(
            "roll: rover is narrating (new spoken response)",
            speaking,
            f"audio starts {starts_before} -> {sink.audio_starts}, {round(sink.seconds_heard(), 2)} s heard",
        )
        if args.barge_delay_s:
            await asyncio.sleep(args.barge_delay_s)
        monitor.barge_in.clear()
        bi_before = va.barge_in.count
        press_wall = time.monotonic()
        rec_stop = await player.play(audio["stop"], label="stop")
        heard = await wait_until(
            lambda: monitor.barge_in.is_set() or va.barge_in.count > bi_before, args.barge_timeout
        )
        barge = va.barge_in.last if va.barge_in.count > bi_before else None
        stop_events = [
            e["payload"] for e in _events_after(log, seq2, "stop") if e["payload"].get("cause") == "barge_in"
        ]
        voice_bi = [
            e["payload"] for e in _events_after(log, seq2, "voice") if e["payload"].get("event") == "barge_in"
        ]
        step(
            "stop: BidiBargeInEvent reached BargeInStop",
            heard and barge is not None,
            f"press -> barge-in {monitor.barge_in_t_ms} ms (voice clock), BargeInStop {barge}"
            if barge
            else "no barge-in",
        )
        step(
            "stop: stop event with cause barge_in logged",
            bool(stop_events),
            json.dumps(stop_events[-1]) if stop_events else "",
        )
        await wait_until(lambda: monitor.response_stops > stops_before + 1, 20.0)
        transcripts2 = [
            e["payload"]["text"]
            for e in _events_after(log, seq2, "voice")
            if e["payload"].get("event") == "transcript"
        ]
        summary["red_light"] = {
            "play_roll": rec_roll,
            "play_stop": rec_stop,
            "press_to_barge_in_ms": monitor.barge_in_t_ms,
            "press_to_barge_in_wall_ms": round((monitor.barge_in_at - press_wall) * 1000)
            if monitor.barge_in_at
            else None,
            "barge_in_to_stop_all_ms": barge["latency_ms"] if barge else None,
            "press_to_stop_ms": barge["stop_t_ms"] if barge else None,
            "voice_barge_in_events": voice_bi,
            "stop_events": stop_events,
            "transcripts": transcripts2,
            "tool_uses": monitor.tool_uses[tools_before:],
            "motions": [m["payload"] for m in _events_after(log, seq2, "motion")],
            "rover_said": [t for r, t in va.transcript.lines[lines_before:] if r == "rover"],
        }
    except Exception as exc:
        summary["errors"].append(
            {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        )
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    finally:
        voice_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await voice_task
        if voice_task.done() and not voice_task.cancelled() and voice_task.exception() is not None:
            exc = voice_task.exception()
            summary["errors"].append({"type": type(exc).__name__, "message": str(exc), "where": "voice task"})
        with contextlib.suppress(Exception):
            close = getattr(runtime, "close", None)
            if callable(close):
                close()
    summary["transcript"] = [f"{r}> {t}" for r, t in va.transcript.lines]
    summary["console"] = out_lines
    summary["bidi_events"] = monitor.events
    summary["pcm"] = pcm.stats()
    summary["rover_audio_s"] = round(sink.seconds_heard(), 2)
    summary["passed"] = (
        bool(summary["steps"]) and all(s["ok"] for s in summary["steps"]) and not summary["errors"]
    )
    return summary


def write_summary(out: Path, summary: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    lines = [
        f"# Voice rehearsal ({summary['mode']}, {summary['model']}): "
        f"{'PASS' if summary['passed'] else 'FAIL'}",
        "",
        f"pre-grant: `STRANDS_ROS2_COMMAND_ALLOW={summary['pregrant']}`; "
        f"auto-approve: {summary['auto_approve']}",
        "",
        "## Steps",
        *(
            f"- [{'PASS' if s['ok'] else 'FAIL'}] {s['label']}"
            + (f": {s['detail']}" if s.get("detail") else "")
            for s in summary["steps"]
        ),
        "",
        "## Transcript",
        *(f"    {line}" for line in summary.get("transcript", [])),
        "",
    ]
    rl = summary.get("red_light") or {}
    if rl:
        lines += [
            "## Red Light latencies",
            f"- press -> BidiBargeInEvent: {rl.get('press_to_barge_in_ms')} ms (voice clock), "
            f"{rl.get('press_to_barge_in_wall_ms')} ms (wall)",
            f"- barge-in -> stop_all returned: {rl.get('barge_in_to_stop_all_ms')} ms",
            f"- press -> stop: {rl.get('press_to_stop_ms')} ms",
            "",
        ]
    if summary["errors"]:
        lines += ["## Errors", *(f"- `{e['type']}: {e['message']}`" for e in summary["errors"]), ""]
    (out / "summary.md").write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m deepracer_agent.voice_rehearsal", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--out", default=os.environ.get("VOICE_REHEARSAL_OUT", "runs/voice-rehearsal"))
    parser.add_argument(
        "--audio-dir", default=None, help="where hop.wav/roll.wav/stop.wav live (default <out>/audio)"
    )
    parser.add_argument("--fake", action="store_true", help="scripted model with fake ASR, no cloud")
    parser.add_argument(
        "--stack", action="store_true", help="start `harness.stack --deadman` on the rehearsal ports"
    )
    parser.add_argument("--beat", default="red_light")
    parser.add_argument("--model", default=None, help="Bedrock bidi model id (default amazon.nova-2-5-sonic)")
    parser.add_argument("--say-voice", default=None, help="macOS voice for `say` (default system voice)")
    parser.add_argument("--no-auto-approve", dest="auto_approve", action="store_false")
    parser.add_argument("--connect-timeout", type=float, default=30.0)
    parser.add_argument("--turn-timeout", type=float, default=60.0)
    parser.add_argument("--barge-timeout", type=float, default=15.0)
    parser.add_argument(
        "--barge-delay-s", type=float, default=0.3, help="let the narration run this long before 'stop'"
    )
    parser.add_argument("--settle-s", type=float, default=1.0)
    parser.add_argument(
        "--quiet-s", type=float, default=1.2, help="rover silence required before the next press"
    )
    parser.add_argument("--tail-ms", type=int, default=400, help="silence appended before each release")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARNING"))

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(REHEARSAL_ENV)
    env["DEEPRACER_SIM_SHARED"] = str(out / "shared.json")
    for key, value in env.items():
        os.environ.setdefault(key, value)
    os.environ.setdefault("DEEPRACER_RUN_DIR", str(out / "run"))
    env = {k: os.environ[k] for k in env}
    print(
        f"rehearsal out {out}; pre-grant STRANDS_ROS2_COMMAND_ALLOW="
        f"{os.environ['STRANDS_ROS2_COMMAND_ALLOW']}"
    )

    audio_dir = Path(args.audio_dir) if args.audio_dir else out / "audio"
    audio = {
        "hop": synthesize(HOP, audio_dir / "hop.wav", voice=args.say_voice),
        "roll": synthesize(ROLL, audio_dir / "roll.wav", voice=args.say_voice),
        "stop": synthesize(STOP, audio_dir / "stop.wav", voice=args.say_voice),
    }
    stack = StackProcess(out, env) if args.stack else None
    try:
        if stack is not None:
            stack.start()
            print(
                f"fake stack up: rosbridge {env['DEEPRACER_ROSBRIDGE_PORT']}, "
                f"console {env['DEEPRACER_CONSOLE_URL']}, decider {env['DECIDER_URL']}"
            )
        summary = asyncio.run(rehearse(args, audio))
    finally:
        if stack is not None:
            stack.stop()
    write_summary(out, summary)
    print(f"summary -> {out / 'summary.md'} ({'PASS' if summary['passed'] else 'FAIL'})")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
