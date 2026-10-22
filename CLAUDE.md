# strands-robots-deepracer

Agentic AWS DeepRacer built on upstream `strands-labs/robots` (strands-robots).

## Read first
- `docs/context/00-README.md` is the project context index. Reports `01`..`12` and
  `council/` are the ground research and decisions completed 2026-10-12. Do not re-derive
  those facts; cite them. Reading order for a new session: 00, 11, 12, then 06.
- Upstream `strands-robots` is pinned in `pyproject.toml` as a git dependency on the fork branch
  `fix/deepracer-manual-state`; `pip install` / `uv sync` installs that pin and nothing else is
  needed. The maintainer instead uses an editable install from a local worktree at a path of
  their choosing. If `import strands_robots._command_gate` fails in the maintainer's venv, the
  recreate command (the maintainer's own paths) is:
  `git -C ~/Documents/strands-0.5x/robots worktree prune && git -C ~/Documents/strands-0.5x/robots worktree add ~/Documents/strands-0.5x/robots-wt-deepracer fix/deepracer-manual-state && uv pip install --python .venv/bin/python -e ~/Documents/strands-0.5x/robots-wt-deepracer`.
  Never put a worktree under the session scratchpad (that directory is wiped between sessions).

- `docs/context/07-prior-github-use-case-work.md` covers the earlier GitHub repos
  (`Vivek0712/strands-agentic-deepracer`, `Vivek0712/aws_deepracer_control_v2`). Reuse
  their measured constants, plan validator and MJPEG parser; do not reuse the custom
  AgentTool, the sleep-and-stop loop, or the fail-open vision fallback.
- The chosen showcase is `docs/context/11-final-use-cases.md` (council verdict, 2026-10-12):
  one spine, seven live beats (Pre-flight, Marshal, Apology, Blindfold, Sign, Red Light, Pull
  the Plug), two booth kiosks, Pit Stop and Two Bodies pre-recorded. 09 and 10 are history.
- Safety posture to repeat everywhere: physics stops the car (pen, hop cap, on-car deadman,
  marshal's thumb); the decider explains. Never present the decider as the safety layer.
- Harness SDK study is `docs/context/08-harness-sdk.md`. The harness is the race-engineer
  agent (SSH sandbox to the car, Cedar/decider interventions), never the driving loop.

## Non-negotiables
- The git root is the HOME directory. Scope every `git add` to `strands-robots-deepracer/`.
  Never `git add .` or `git add -A`.
- Python 3.12 (`uv sync --python 3.12`). strands-agents >= 1.57.2, code against
  `strands.bidi`, never `strands.experimental.bidi`.
- DeepRacer `vehicle_state`: 0 = manual, 1 = autonomous, 2 = calibration. Always follow a
  mode change with `enable_state is_active=true`. Always publish a zero servo pair before
  exit; the car has no watchdog.
- Any tool that publishes to `/manual_drive`, `/vehicle_state`, `/enable_state` or `/cmd_vel`
  goes through `strands_robots._command_gate`; headless runs set
  `STRANDS_ROS2_COMMAND_ALLOW` explicitly and say so in the docs.
- Contributions to upstream follow its `AGENTS.md`: one `changelog.d/<pr>-<slug>.md`
  fragment, never edit `CHANGELOG.md [Unreleased]`, refusal-table tests, 900-word doc pages.
- Car credentials live only in `~/.config/deepracer/env` (see `car/connect/env.example`); never
  commit them. Use env vars or keychain.
- AWS: profile `heisenberg` (us-east-1) for any Bedrock, AgentCore or CDK work.

## Layout (planned)
- `docs/context/` research bundle (done)
- `src/` project code: rosbridge Ackermann driver, decider gate, voice teleop, camera loop
- `upstream/` worktree of strands-labs/robots main (gitignored) for reference and PRs
