"""``python -m beats <name> --body sim|car [--text]``: run one beat and print its pass/fail card.

The opener for every rehearsal: pick a beat, pick a body, watch the summary. With ``--body sim``
the fake car, fake console and fake decider must be up (``make fake-car fake-console
fake-decider``). With ``--body car`` the credentials come from ``~/.config/deepracer/env`` and the
marshal must be present. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from . import BEAT_NAMES, BOOTH_BEAT_NAMES, RECORDED_BEAT_NAMES, BeatError, load_beat, make_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m beats", description=__doc__.split("\n\n")[0])
    parser.add_argument("name", choices=[*BEAT_NAMES, *BOOTH_BEAT_NAMES, *RECORDED_BEAT_NAMES, "all"])
    parser.add_argument("--body", choices=["sim", "car"], default=os.environ.get("DEEPRACER_BODY", "sim"))
    parser.add_argument("--text", action="store_true", help="text console instead of push-to-talk voice")
    parser.add_argument(
        "--sim-control", default=None, help="fake car control URL (default http://127.0.0.1:8092)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARNING"))

    names = list(BEAT_NAMES) if args.name == "all" else [args.name]
    failures = 0
    for name in names:
        try:
            sim = None
            if args.sim_control and args.body == "sim":
                from . import SimControl

                sim = SimControl(args.sim_control)
            ctx = make_context(name, body=args.body, text=args.text, sim=sim)
            try:
                result = asyncio.run(load_beat(name)(ctx))
            finally:
                close = getattr(ctx.runtime, "close", None)
                if callable(close):
                    close()  # otherwise this beat's idle heartbeat keeps the deadman armed for the next
        except BeatError as exc:
            print(f"beat {name}: cannot run: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(result.summary())
        if not result.passed:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
