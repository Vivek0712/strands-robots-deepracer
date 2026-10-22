"""Headless visual QA of the Pit Wall: screenshots of every state and one recorded run.

``python -m portal.evidence.capture`` starts the fake car, fake console and fake decider on the
override ports (9191 / 8192 / 8190 / 8211, never the contract ports another session may hold),
starts the portal with ``PORTAL_FAKE_RUNTIME=1`` on ``PORTAL_URL`` (default ``:8865``), opens the
main view and both kiosks in headless Chromium at 1920x1080 and drives the fake agent through the
WebSocket ops the buttons use: ``preflight``, a clear hop (``command``), a person-in-frame deny, a
Confirm followed by ``approve``, ``stop_all``. Each state is saved as a small PNG under
``docs/results/portal/`` and the main sequence is also recorded as ``pitwall-sim.webm``.
``python -m portal.evidence.capture watch`` instead attaches to a running portal fed by a real
beats run and screenshots the marshal deny, the apology and the final audit. Physics stops the
car; the decider explains; this script only photographs the explanation.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("portal.evidence")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs" / "results" / "portal"
VIEWPORT = {"width": 1920, "height": 1080}
VIDEO_SIZE = {"width": 1280, "height": 720}
MAX_PNG_BYTES = 400 * 1024
MAX_VIDEO_BYTES = 5 * 1024 * 1024

# Override ports (CONTRACTS section 3, "override" column): the evidence run never touches the
# contract ports so it can run next to a rehearsal that holds 9091 / 8090 / 8092 / 8111 / 8765.
OVERRIDE_ENV = {
    "PORTAL_URL": "http://127.0.0.1:8865",
    "DEEPRACER_ROSBRIDGE_PORT": "9191",
    "DEEPRACER_SIM_CONTROL_URL": "http://127.0.0.1:8192",
    "DEEPRACER_CONSOLE_URL": "http://127.0.0.1:8190",
    "DECIDER_URL": "http://127.0.0.1:8211",
}


def env_with_overrides() -> dict[str, str]:
    """The process env plus the override ports for anything the caller left unset."""
    env = dict(os.environ)
    for key, value in OVERRIDE_ENV.items():
        env.setdefault(key, value)
    return env


def _http_ok(url: str, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def _http_get(url: str, timeout: float = 2.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def wait_until(check: Callable[[], bool], timeout: float, what: str, poll: float = 0.1) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(poll)
    raise TimeoutError(f"{what} not ready within {timeout:.0f}s")


# ----- services ------------------------------------------------------------------------------


@contextlib.contextmanager
def sim_stack(env: dict[str, str], shared_path: Path) -> Iterator[Any]:
    """Fake car + console + decider in this process on the ports named by ``env``."""
    from harness.stack import SimStack

    stack = SimStack(
        rosbridge_port=int(env["DEEPRACER_ROSBRIDGE_PORT"]),
        control_port=urlparse(env["DEEPRACER_SIM_CONTROL_URL"]).port or 8192,
        console_port=urlparse(env["DEEPRACER_CONSOLE_URL"]).port or 8190,
        decider_port=urlparse(env["DECIDER_URL"]).port or 8211,
        shared_path=shared_path,
    )
    stack.start()
    try:
        yield stack
    finally:
        stack.stop()


@contextlib.contextmanager
def portal_process(
    env: dict[str, str], run_dir: Path, *, fake_runtime: bool, log_path: Path
) -> Iterator[Any]:
    """``python -m portal.backend.app`` as a child on ``PORTAL_URL``'s port; stopped on exit."""
    child_env = dict(env)
    child_env["DEEPRACER_RUN_DIR"] = str(run_dir)
    child_env["DEEPRACER_BODY"] = "sim"
    child_env["PORTAL_HOST"] = "127.0.0.1"
    child_env["PORTAL_FAKE_RUNTIME"] = "1" if fake_runtime else "0"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "portal.backend.app"], cwd=REPO_ROOT, env=child_env, stdout=fh, stderr=fh
        )
        try:
            wait_until(lambda: _http_ok(f"{env['PORTAL_URL']}/health"), 30, "portal")
            yield proc
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(5)


# ----- the operator's socket -----------------------------------------------------------------


class Operator:
    """A second WebSocket client on ``/ws``: sends the ops the buttons send, waits for events."""

    def __init__(self, portal_url: str) -> None:
        from websockets.sync.client import connect

        ws_url = portal_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/ws"
        self._ws = connect(ws_url, open_timeout=10)
        self.events: list[dict[str, Any]] = []
        self.acks: list[dict[str, Any]] = []
        first = json.loads(self._ws.recv(timeout=10))
        if first.get("op") == "snapshot":
            self.events.extend(first.get("events") or [])
        self.snapshot = first

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._ws.close()

    def send(self, **op: Any) -> None:
        self._ws.send(json.dumps(op))

    def pump(self, timeout: float = 0.05) -> bool:
        """Read one message if one is waiting; returns False when nothing arrived."""
        try:
            raw = self._ws.recv(timeout=timeout)
        except TimeoutError:
            return False
        msg = json.loads(raw)
        if msg.get("op") == "event":
            self.events.append(msg["event"])
        elif msg.get("op") in {"ack", "error"}:
            self.acks.append(msg)
        return True

    def wait_event(
        self, predicate: Callable[[dict[str, Any]], bool], timeout: float, what: str
    ) -> dict[str, Any]:
        """Block until an event matching ``predicate`` has been seen (including ones already read)."""
        start = len(self.events)
        deadline = time.monotonic() + timeout
        while True:
            for ev in self.events[start:]:
                if predicate(ev):
                    return ev
            start = len(self.events)
            if time.monotonic() >= deadline:
                raise TimeoutError(f"{what} not seen within {timeout:.0f}s")
            self.pump(timeout=min(0.2, max(0.0, deadline - time.monotonic())))

    def wait_ack(self, for_op: str, timeout: float = 10.0) -> dict[str, Any]:
        start = 0
        deadline = time.monotonic() + timeout
        while True:
            for ack in self.acks[start:]:
                if ack.get("for") == for_op:
                    return ack
            start = len(self.acks)
            if time.monotonic() >= deadline:
                raise TimeoutError(f"ack for {for_op} not seen within {timeout:.0f}s")
            self.pump(timeout=0.2)

    def drain(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.pump(timeout=max(0.0, deadline - time.monotonic()))


def is_type(etype: str, **fields: Any) -> Callable[[dict[str, Any]], bool]:
    def pred(ev: dict[str, Any]) -> bool:
        if ev.get("type") != etype:
            return False
        payload = ev.get("payload") or {}
        return all(payload.get(k) == v for k, v in fields.items())

    return pred


# ----- pictures ------------------------------------------------------------------------------


def optimise_png(path: Path, max_bytes: int = MAX_PNG_BYTES) -> int:
    """Shrink a screenshot: palette-quantise when the full-colour PNG is over the budget."""
    from PIL import Image

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        rgb.save(path, optimize=True)
        if path.stat().st_size > max_bytes:
            rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
        if path.stat().st_size > max_bytes:
            rgb.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
    return path.stat().st_size


class Shots:
    """Numbered screenshots into one directory, with a manifest of what each one shows."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.manifest: list[dict[str, Any]] = []

    def take(
        self, page: Any, name: str, caption: str, *, settle_ms: int = 400, selector: str | None = None
    ) -> Path:
        page.wait_for_timeout(settle_ms)
        path = self.out_dir / f"{len(self.manifest) + 1:02d}-{name}.png"
        if selector:
            page.locator(selector).first.screenshot(path=str(path))
        else:
            page.screenshot(path=str(path), full_page=False)
        size = optimise_png(path)
        self.manifest.append({"file": path.name, "caption": caption, "bytes": size})
        log.info("shot %s (%d KB): %s", path.name, size // 1024, caption)
        return path

    def write_manifest(self) -> Path:
        path = self.out_dir / "manifest.json"
        path.write_text(json.dumps(self.manifest, indent=2) + "\n")
        return path


# ----- the fake-runtime sequence --------------------------------------------------------------


def set_label(console_url: str, label: str) -> None:
    """Put a drawn frame on the fake camera so the live view matches the story."""
    with contextlib.suppress(Exception):
        _http_get(f"{console_url.rstrip('/')}/control?label={label}")


def run_main_sequence(page: Any, op: Operator, shots: Shots, console_url: str) -> None:
    """Idle, pre-flight, clear hop, person deny, Confirm + approve, STOP ALL on the main view."""
    page.wait_for_selector("text=Pit Wall")
    page.wait_for_function("() => document.body.innerText.includes('open')")
    shots.take(
        page,
        "main-idle",
        "Main view on connect: no verdict yet, live view from the fake console, STOP ALL ready.",
    )

    op.send(op="preflight")
    op.wait_event(is_type("preflight"), 15, "preflight event")
    op.wait_ack("preflight")
    shots.take(
        page,
        "main-preflight-go",
        "Pre-flight table after the `preflight` op: eight checks green, GO, LED green.",
    )

    set_label(console_url, "clear")
    op.send(op="command", text="go forward 20 cm")
    op.wait_event(is_type("motion", state="start"), 15, "motion start")
    shots.take(
        page,
        "main-clear-hop-moving",
        "A clear hop in motion: Proceed, path clear, heartbeat armed, motion card in the audit.",
        settle_ms=150,
    )
    op.wait_event(is_type("stop", cause="trailing_zero"), 15, "trailing zero")

    set_label(console_url, "person_in_frame")
    op.send(op="command", text="go forward, there is a person ahead")
    op.wait_event(is_type("stop", cause="deny"), 15, "deny stop")
    op.wait_event(
        lambda e: e.get("type") == "thought" and "decider said" in (e.get("payload") or {}).get("text", ""),
        10,
        "deny thought",
    )
    shots.take(
        page,
        "main-person-deny",
        "Person in frame: Deny with class and probability, LED red, stop cause deny, "
        "a drawn stick figure on the live view.",
    )
    set_label(console_url, "clear")

    op.send(op="command", text="go fast for 3 seconds")
    op.wait_event(is_type("verdict", action="Confirm"), 15, "Confirm verdict")
    shots.take(
        page,
        "main-confirm-pending",
        "Outside the envelope: Confirm pending, Approve / Deny buttons shown in the Command panel.",
        settle_ms=600,
    )
    rid = op.events[-1]["payload"]["request_id"]
    op.send(op="approve", request_id=rid, approved=True)
    op.wait_event(is_type("approval", decision="approved"), 10, "approval")
    op.wait_event(is_type("motion", state="start"), 15, "motion after approval")
    shots.take(
        page,
        "main-approved-moving",
        "After Approve: approval card by operator, frame verdict Proceed, motion start for 3 s.",
        settle_ms=300,
    )

    op.send(op="stop_all")
    op.wait_event(is_type("stop", cause="operator"), 10, "operator stop")
    op.wait_ack("stop_all")
    shots.take(
        page,
        "main-stop-all",
        "STOP ALL during motion: stop cause operator with its latency, LED amber, motion end card.",
        settle_ms=700,
    )


def run_kiosks(browser: Any, portal_url: str, op: Operator, shots: Shots, console_url: str) -> None:
    """Simon Says and Frame Judge, driven through the kiosk's own command box."""
    ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
    try:
        page = ctx.new_page()
        page.goto(f"{portal_url}/?kiosk=simon")
        page.wait_for_function("() => document.body.innerText.includes('open')")
        set_label(console_url, "obstacle_near")
        page.fill("input[data-cmd-input]", "go forward past the box")
        page.keyboard.press("Enter")
        op.wait_event(is_type("verdict", action="Guide"), 15, "Guide verdict")
        op.wait_event(is_type("stop", cause="trailing_zero"), 15, "hop end")
        shots.take(
            page,
            "kiosk-simon-guide",
            "Simon Says kiosk: an attendee typed a command, the gate answered Guide "
            "(obstacle near, halved speed).",
        )

        page.goto(f"{portal_url}/?kiosk=judge")
        page.wait_for_function("() => document.body.innerText.includes('open')")
        shots.take(
            page,
            "kiosk-judge",
            "Frame Judge kiosk: live view large, latest class and probability, "
            "verdict and frame cards with thumbnails.",
        )
        set_label(console_url, "clear")
    finally:
        ctx.close()


def capture(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    env = env_with_overrides()
    portal_url = env["PORTAL_URL"].rstrip("/")
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = (REPO_ROOT / "runs" / f"portal-evidence-{time.strftime('%Y%m%d-%H%M%S')}").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    shots = Shots(out_dir)
    video_tmp = run_dir / "video"

    with contextlib.ExitStack() as stack:
        if not args.attach:
            stack.enter_context(sim_stack(env, run_dir / "shared.json"))
            stack.enter_context(
                portal_process(env, run_dir, fake_runtime=True, log_path=run_dir / "portal.log")
            )
        state = json.loads(_http_get(f"{portal_url}/api/state"))
        if state.get("runtime") != "fake":
            log.error(
                "portal on %s runs %r, not the fake runtime; refusing", portal_url, state.get("runtime")
            )
            return 2
        op = Operator(portal_url)
        stack.callback(op.close)
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch()
        stack.callback(browser.close)

        ctx = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1,
            record_video_dir=str(video_tmp),
            record_video_size=VIDEO_SIZE,
        )
        page = ctx.new_page()
        page.goto(f"{portal_url}/")
        run_main_sequence(page, op, shots, env["DEEPRACER_CONSOLE_URL"])
        page.wait_for_timeout(800)
        video = page.video
        ctx.close()  # finalises the webm
        if video is not None:
            target = out_dir / "pitwall-sim.webm"
            video.save_as(str(target))
            size = target.stat().st_size
            log.info("video %s: %d KB", target.name, size // 1024)
            if size > MAX_VIDEO_BYTES:
                log.warning("video is over %d MB", MAX_VIDEO_BYTES // (1024 * 1024))
        shutil.rmtree(video_tmp, ignore_errors=True)

        run_kiosks(browser, portal_url, op, shots, env["DEEPRACER_CONSOLE_URL"])
        shots.write_manifest()
    print(json.dumps({"out": str(out_dir), "shots": shots.manifest}, indent=2))
    return 0


# ----- watching a real beats run --------------------------------------------------------------


def watch(args: argparse.Namespace) -> int:
    """Attach to a live portal and screenshot the marshal deny, the apology and the final audit."""
    from playwright.sync_api import sync_playwright

    env = env_with_overrides()
    portal_url = env["PORTAL_URL"].rstrip("/")
    out_dir = Path(args.out).resolve()
    shots = Shots(out_dir)
    wait_until(lambda: _http_ok(f"{portal_url}/health"), 60, "portal")
    op = Operator(portal_url)
    seen = {"marshal": False, "apology": False}
    deadline = time.monotonic() + args.timeout
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(f"{portal_url}/")
        page.wait_for_function("() => document.body.innerText.includes('open')")
        try:
            while time.monotonic() < deadline:
                if not op.pump(timeout=0.5):
                    continue
                ev = op.events[-1] if op.events else None
                if not ev:
                    continue
                payload = ev.get("payload") or {}
                beat = ev.get("beat")
                if (
                    not seen["marshal"]
                    and beat == "marshal"
                    and ev["type"] == "stop"
                    and payload.get("cause") == "deny"
                ):
                    seen["marshal"] = True
                    shots.take(
                        page,
                        "beats-marshal-deny",
                        "Live beats run: the Marshal beat's deny (person in frame) "
                        "as the real gate emitted it.",
                        settle_ms=400,
                    )
                if (
                    not seen["apology"]
                    and beat == "apology"
                    and ev["type"] == "thought"
                    and str(payload.get("text", "")).startswith("rover:")
                ):
                    seen["apology"] = True
                    shots.take(
                        page,
                        "beats-apology",
                        "Live beats run: the Apology beat, the rover's why_stopped answer "
                        "in the Thought panel.",
                        settle_ms=150,  # the next beat starts within a second of the apology
                    )
                if beat == "pull_the_plug" and ev["type"] == "stop" and payload.get("cause") == "deadman":
                    op.drain(4.0)
                    break
                if args.exit_when_seen and all(seen.values()):
                    op.drain(3.0)
                    break
            shots.take(
                page,
                "beats-final-audit",
                "Live beats run: the audit panel after all seven beats.",
                settle_ms=500,
                selector="section:has(h2:has-text('Audit'))",
            )
            shots.take(
                page,
                "beats-final-main",
                "Live beats run: the whole Pit Wall after all seven beats.",
                settle_ms=200,
            )
        finally:
            ctx.close()
            browser.close()
            op.close()
    shots.write_manifest()
    print(json.dumps({"out": str(out_dir), "seen": seen, "shots": shots.manifest}, indent=2))
    return 0 if all(seen.values()) else 1


# ----- replaying a recorded run ---------------------------------------------------------------


def replay(args: argparse.Namespace) -> int:
    """Feed a recorded ``events.jsonl`` to a fresh portal and screenshot the screen it rebuilds.

    Every line is POSTed to ``/api/events`` with ``X-Deepracer-Source: eventlog`` so nothing is
    written back to disk; the portal's run dir is the recorded run's directory so the audit
    thumbnails resolve. ``--until-seq`` stops the replay at a given event, which is how a state
    the live watcher missed (the last line of a beat) is photographed after the fact.
    """
    from playwright.sync_api import sync_playwright

    env = env_with_overrides()
    portal_url = env["PORTAL_URL"].rstrip("/")
    events_path = Path(args.events).resolve()
    run_dir = events_path.parent
    out_dir = Path(args.out).resolve()
    shots = Shots(out_dir)
    shots.manifest = [{"file": f"{i:02d}"} for i in range(1, args.number)]  # keep the numbering
    lines = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    if args.until_seq is not None:
        lines = [e for e in lines if int(e.get("seq", 0)) <= args.until_seq]
    with contextlib.ExitStack() as stack:
        stack.enter_context(sim_stack(env, run_dir / "replay-shared.json"))
        stack.enter_context(portal_process(env, run_dir, fake_runtime=True, log_path=run_dir / "replay.log"))
        for event in lines:
            req = urllib.request.Request(
                f"{portal_url}/api/events",
                data=json.dumps(event).encode(),
                headers={"Content-Type": "application/json", "X-Deepracer-Source": "eventlog"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 202:
                    log.warning("event seq %s refused: %s", event.get("seq"), resp.status)
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch()
        stack.callback(browser.close)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(f"{portal_url}/")
        page.wait_for_function("() => document.body.innerText.includes('open')")
        shots.take(page, args.name, args.caption, settle_ms=1500)
        ctx.close()
    shots.manifest = shots.manifest[args.number - 1 :]
    print(json.dumps({"out": str(out_dir), "replayed": len(lines), "shots": shots.manifest}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m portal.evidence.capture", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("mode", nargs="?", choices=["capture", "watch", "replay"], default="capture")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="screenshot directory")
    parser.add_argument(
        "--attach",
        action="store_true",
        help="capture: use a portal + sim stack already running on PORTAL_URL",
    )
    parser.add_argument("--timeout", type=float, default=900.0, help="watch: give up after this many seconds")
    parser.add_argument(
        "--exit-when-seen",
        action="store_true",
        help="watch: finish once the marshal deny and the apology were shot (single-beat reruns)",
    )
    parser.add_argument("--events", help="replay: the recorded events.jsonl (its directory is the run dir)")
    parser.add_argument("--until-seq", type=int, default=None, help="replay: stop after this seq")
    parser.add_argument("--name", default="replay", help="replay: screenshot name")
    parser.add_argument("--caption", default="Replayed from events.jsonl.", help="replay: manifest caption")
    parser.add_argument("--number", type=int, default=1, help="replay: the screenshot's number prefix")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"), format="%(name)s %(message)s")
    if args.mode == "watch":
        return watch(args)
    if args.mode == "replay":
        if not args.events:
            parser.error("replay needs --events <events.jsonl>")
        return replay(args)
    return capture(args)


if __name__ == "__main__":
    sys.exit(main())
