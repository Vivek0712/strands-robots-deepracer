"""The race engineer: a Strands Harness agent with SSH hands on the car and a Cedar leash.

Spoken version: the harness is not the driving loop. It is the mechanic. It can SSH into the
DeepRacer, read the calibration file, tail the logs and compare what it finds with what it
remembers, but every command it wants to run on the car passes a Cedar policy first. Reads are
permitted. A write to calibration or a service restart needs the operator to say yes. This is
the "Pit Stop" beat, shown pre-recorded on stage (report 11), and the one call that creates the
whole agent is ``create_harness`` below.

Run (laptop, car reachable, ``~/.config/deepracer/env`` present)::

    .venv/bin/python -m ops.race_engineer "check steering calibration against what you remember"

Nothing here publishes to a motion topic. Driving stays on the gated ``drive_deepracer`` tool in
``deepracer_agent.driver``; this agent may be handed that robot agent with ``Agent.as_tool`` later,
behind the same Cedar policy.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "deepracer" / "env"
POLICY_FILE = Path(__file__).with_name("pit_stop.cedar")
WORKING_DIR = "/opt/aws/deepracer"

INSTRUCTIONS = """You are the race engineer for an AWS DeepRacer running the stock ROS 2 Foxy stack.
You have a shell on the car over SSH. Reads are free: ros2 topic/service listing, journalctl,
cat of calibration under /opt/aws/deepracer/calibration.json, PWM sysfs values, battery level.
Anything that writes to the car (editing calibration, restarting services, apt, reboot) is a
separate tool call that the Cedar policy will send to the operator for confirmation; propose it,
explain the expected effect in one sentence, and wait. Never publish to /webserver_pkg/manual_drive
or any motion topic; driving belongs to the gated robot agent. Remember what you learn about this
car (calibration values, sign convention, which Wi-Fi it is on) in memory. Report in short
sentences a presenter can read aloud."""


def _load_env() -> dict[str, str]:
    """Read ``~/.config/deepracer/env`` without exporting secrets into the repo or logs."""
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("DEEPRACER_")})
    return values


def operator_confirmation(_call: dict[str, object]) -> dict[str, object]:
    """Cedar context enricher: the operator's standing yes for this session, from the environment.

    ``DEEPRACER_OPERATOR_CONFIRMED=1`` is set by the presenter at the keyboard for one session and
    is what the policy's ``operator_confirmed`` clauses read. It is never persisted.
    """
    return {"operator_confirmed": os.environ.get("DEEPRACER_OPERATOR_CONFIRMED") == "1"}


def build_race_engineer(*, model: str | None = None, interventions_override: object | None = None):
    """One call: ``create_harness`` with an SSH sandbox to the car and the Pit Stop Cedar policy."""
    from strands.sandbox.ssh import SshSandbox
    from strands.vended_interventions.cedar import CedarAuthorization
    from strands_harness import create_harness

    env = _load_env()
    user = env.get("DEEPRACER_SSH_USER", "deepracer")
    key = env.get("DEEPRACER_SSH_KEY")
    # DEEPRACER_HOST=auto (or a stale address) is resolved the way the driver does it.
    for name in ("DEEPRACER_HOST", "DEEPRACER_MAC", "DEEPRACER_MDNS"):
        if env.get(name):
            os.environ.setdefault(name, env[name])
    os.environ.setdefault("DEEPRACER_BODY", "car")
    from deepracer_agent.discover import resolve_host

    host = resolve_host("")
    if not host or host == "auto":
        raise SystemExit("DEEPRACER_HOST is not set and the car was not found; see docs/dev/networking.md")

    sandbox = SshSandbox(
        host=f"{user}@{host}",
        working_dir=WORKING_DIR,
        identity_file=os.path.expanduser(key) if key else None,
        ssh_options=["ConnectTimeout=8"],  # passed as -o flags; StrictHostKeyChecking is the flag below
        allow_unknown_hosts=True,
    )
    cedar = interventions_override or CedarAuthorization(
        policies=POLICY_FILE.read_text(),
        on_error="deny",
        context_enricher=operator_confirmation,
    )
    return create_harness(
        model=model or os.environ.get("DEEPRACER_HARNESS_MODEL"),
        instructions=INSTRUCTIONS,
        builtin_tools=["shell", "read", "write", "edit", "web_fetch"],
        interventions=cedar,
        memory=True,
        session=True,
        sandbox=sandbox,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeepRacer race engineer (Strands Harness over SSH)")
    parser.add_argument("prompt", nargs="*", help="what to check; defaults to a calibration review")
    parser.add_argument("--model", default=None, help="model id or provider/name; default from harness")
    args = parser.parse_args(argv)
    prompt = " ".join(args.prompt) or (
        "Read the steering and throttle calibration on the car, compare with what you remember, "
        "and report any offset. Do not change anything without asking."
    )
    agent = build_race_engineer(model=args.model)
    result = agent(prompt)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
