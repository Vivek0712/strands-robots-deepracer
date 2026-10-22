"""Headless visual QA of the two booth kiosks: Frame Judge and Simon Says, photographed end to end.

``python -m portal.evidence.kiosks`` attaches to a running portal on ``PORTAL_URL`` (start your own
fake stack with ``python -m harness.stack`` on override ports and ``python -m portal.backend.app``;
``--stack`` starts both in-process like ``portal.evidence.capture`` does) and drives the kiosk pages
in headless Chromium the way an attendee and a presenter would: add a label live, judge three
frames (one without consent, one with, one at low confidence), read the leaderboard, then type
commands at Simon Says until it has shown Proceed, Confirm with the slower plan, Guide and Deny with
the Box egress log beside each. Phone-width shots prove the one-column layout. PNGs and a
``manifest.json`` land in ``docs/results/kiosks-<date>/``. Physics stops the car; the decider
explains; this script only photographs the explanation.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from .capture import (
    REPO_ROOT,
    Shots,
    _http_get,
    _http_ok,
    env_with_overrides,
    portal_process,
    set_label,
    sim_stack,
    wait_until,
)

log = logging.getLogger("portal.evidence.kiosks")

DEFAULT_OUT = REPO_ROOT / "docs" / "results" / f"kiosks-{time.strftime('%Y-%m-%d')}"
TABLET = {"width": 1280, "height": 860}
PHONE = {"width": 390, "height": 844}


def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def wait_open(page: Any) -> None:
    page.wait_for_function("() => document.body.innerText.includes('open')", timeout=15000)


# ----- Frame Judge -------------------------------------------------------------------------------


def judge_once(page: Any, nickname: str, expected: str | None, consent: bool) -> None:
    page.fill("input[data-judge-nickname]", nickname)
    page.select_option("select[data-judge-expected]", expected or "")
    box = page.locator("input[data-judge-consent]")
    if box.is_checked() != consent:
        box.click()
    page.click("button[data-judge-go]")
    page.wait_for_selector("[data-judge-saved]", timeout=20000)
    page.wait_for_function(
        "() => !document.querySelector('button[data-judge-go]').disabled "
        "|| document.querySelector('input[data-judge-nickname]').value === ''",
        timeout=20000,
    )


def run_judge(browser: Any, portal_url: str, shots: Shots, console_url: str) -> None:
    ctx = browser.new_context(viewport=TABLET, device_scale_factor=1)
    try:
        page = ctx.new_page()
        page.goto(f"{portal_url}/?kiosk=judge")
        wait_open(page)
        set_label(console_url, "clear")
        shots.take(
            page,
            "judge-idle",
            "Frame Judge on open: live view, the judge form with the consent switch off, the five "
            "built-in labels on the card, an empty leaderboard.",
        )

        page.fill("input[data-label-input]", "shoe")
        page.click("button[data-label-add]")
        page.wait_for_selector("[data-label-chip='shoe']", timeout=10000)
        shots.take(
            page,
            "judge-label-added",
            "The presenter typed 'shoe' and pressed Add: the card now has six labels and the next "
            "question is asked over the new list, no retraining.",
            selector="section:has(h2:has-text('Label card'))",
        )

        judge_once(page, "Ada", "shoe", consent=False)
        shots.take(
            page,
            "judge-fooled-no-consent",
            "Ada says she holds a shoe; the decider says clear p=0.93 with its latency, so she fooled it. "
            "Consent off: the card says the frame was judged in memory and not saved.",
        )

        judge_once(page, "Grace", "clear", consent=True)
        shots.take(
            page,
            "judge-agreed-consent",
            "Grace says clear, the decider agrees. Consent on: the frame is written to the run dir "
            "and the card shows its frames/ path; the leaderboard shows the thumbnail.",
        )

        set_label(console_url, "sign")
        judge_once(page, "Linus", None, consent=False)
        shots.take(
            page,
            "judge-leaderboard-3",
            "After three judgements: Linus held the sign card (clear at p=0.80, the least sure answer). "
            "Best fools ranks Ada (wrong class) first, then the lowest probabilities.",
        )
        shots.take(
            page,
            "judge-leaderboard-table",
            "The best fools table alone: rank, nickname, decider class, what they said, p, ms, frame "
            "(thumbnail only for the consented one).",
            selector="section:has(h2:has-text('Best fools'))",
        )
        set_label(console_url, "clear")
    finally:
        ctx.close()

    phone = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    try:
        page = phone.new_page()
        page.goto(f"{portal_url}/?kiosk=judge")
        wait_open(page)
        shots.take(
            page,
            "judge-phone",
            "Frame Judge at phone width (390 px): one column, the judge form first, the page scrolls.",
            settle_ms=600,
        )
    finally:
        phone.close()


# ----- Simon Says --------------------------------------------------------------------------------


def ask_simon(page: Any, text: str, want_action: str) -> None:
    page.fill("input[data-simon-input]", text)
    page.click("button[data-simon-send]")
    page.wait_for_function(
        "(a) => (document.querySelector('[data-simon-action]')?.textContent || '').trim() === a",
        arg=want_action,
        timeout=20000,
    )


def run_simon(browser: Any, portal_url: str, shots: Shots, console_url: str) -> None:
    ctx = browser.new_context(viewport=TABLET, device_scale_factor=1)
    try:
        page = ctx.new_page()
        page.goto(f"{portal_url}/?kiosk=simon")
        wait_open(page)
        set_label(console_url, "clear")
        ask_simon(page, "hop forward", "Proceed")
        shots.take(
            page,
            "simon-proceed",
            "Simon Says: 'hop forward' on a clear frame is Proceed; the Box egress log lists the camera "
            "grab and the two decider questions with host and milliseconds.",
        )

        ask_simon(page, "go forward fast for two seconds", "Confirm")
        shots.take(
            page,
            "simon-confirm-replan",
            "'go forward fast for two seconds' asks for 0.6 m/s, outside the briefed envelope: Confirm, "
            "and the slower plan the gate would take (0.3 m/s for 2 s) is shown under the card.",
        )

        set_label(console_url, "obstacle_near")
        ask_simon(page, "hop forward", "Guide")
        shots.take(
            page,
            "simon-guide",
            "A box close to the bumper: Guide, re-plan at half speed (0.15 m/s), probability and "
            "latency on the card, the egress log beside it.",
        )

        set_label(console_url, "person_in_frame")
        ask_simon(page, "hop forward", "Deny")
        shots.take(
            page,
            "simon-deny",
            "A person in frame: Deny with class person_in_frame and its probability; the history "
            "shows the four answers in order.",
        )

        ask_simon(page, "turn left", "Deny")
        shots.take(
            page,
            "simon-deny-yaw",
            "'turn left' is refused before the gate: Ackermann cannot yaw at rest, no outbound call "
            "(empty egress log).",
            selector="section:has(h2:has-text('Simon Says'))",
        )
        set_label(console_url, "clear")
    finally:
        ctx.close()

    phone = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    try:
        page = phone.new_page()
        page.goto(f"{portal_url}/?kiosk=simon")
        wait_open(page)
        shots.take(
            page,
            "simon-phone",
            "Simon Says at phone width (390 px): the reason card first, then the live view, the egress "
            "log and the history, one column.",
            settle_ms=600,
        )
    finally:
        phone.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m portal.evidence.kiosks", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="screenshot directory")
    parser.add_argument(
        "--stack", action="store_true", help="start a fake stack and a portal in-process first"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"), format="%(name)s %(message)s")

    from playwright.sync_api import sync_playwright

    env = env_with_overrides()
    portal_url = env["PORTAL_URL"].rstrip("/")
    console_url = env["DEEPRACER_CONSOLE_URL"]
    out_dir = Path(args.out).resolve()
    shots = Shots(out_dir)
    with contextlib.ExitStack() as stack:
        if args.stack:
            run_dir = (REPO_ROOT / "runs" / f"kiosks-evidence-{time.strftime('%Y%m%d-%H%M%S')}").resolve()
            run_dir.mkdir(parents=True, exist_ok=True)
            stack.enter_context(sim_stack(env, run_dir / "shared.json"))
            stack.enter_context(
                portal_process(env, run_dir, fake_runtime=False, log_path=run_dir / "portal.log")
            )
        wait_until(lambda: _http_ok(f"{portal_url}/health"), 30, "portal")
        state = json.loads(_http_get(f"{portal_url}/api/state"))
        log.info("portal %s session %s runtime %s", portal_url, state.get("session"), state.get("runtime"))
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch()
        stack.callback(browser.close)
        run_judge(browser, portal_url, shots, console_url)
        run_simon(browser, portal_url, shots, console_url)
        shots.write_manifest()
        board = json.loads(_http_get(f"{portal_url}/kiosk/leaderboard"))
        (out_dir / "leaderboard.json").write_text(json.dumps(board, indent=2) + "\n")
        history = json.loads(_http_get(f"{portal_url}/kiosk/simon"))
        (out_dir / "simon-history.json").write_text(json.dumps(history, indent=2) + "\n")
    print(json.dumps({"out": str(out_dir), "shots": shots.manifest}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
