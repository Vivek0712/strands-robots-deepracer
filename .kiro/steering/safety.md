---
inclusion: always
---

# Safety and repo non-negotiables

These come from `CLAUDE.md`, `AGENTS.md` and `docs/dev/CONTRACTS.md` section 9. They bind
every edit Kiro makes in this repo.

## The car

- Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb); the decider
  explains. Never present the decider gate as the safety layer, in code, docs or UI copy.
- DeepRacer `vehicle_state`: `0` = manual, `1` = autonomous, `2` = calibration. Upstream's
  `state=1` was the mode bug; manual is `0`. Always follow a mode change with
  `enable_state is_active=true`.
- The car has no watchdog. Always publish a zero servo pair (`angle=0, throttle=0` on
  `/webserver_pkg/manual_drive`) before exit, from a `finally` block. A trailing zero that does
  not land is the drive's error, not a warning.
- Caps: `|linear| <= 0.3 m/s`, `duration <= 2.0 s` (hop default 0.5 s), 20 Hz publish, a
  heartbeat on `/deepracer_agent/heartbeat` beside every command stream. The on-car deadman
  zeroes the servos after a 300 ms heartbeat gap.
- Fail closed: no frame, no decider, no heartbeat means no motion.
- `stop_deepracer()` is never gated.

## The command gate

- Any tool that publishes to `/manual_drive`, `/vehicle_state`, `/enable_state` or `/cmd_vel`
  goes through `strands_robots._command_gate` (`gate_command`). Headless runs set
  `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state` explicitly, and the
  document or script that sets it says so.

## Secrets and people

- Plaintext car passwords exist in `~/strands-deepracer/poc`, `edge/.env` and
  `~/.config/deepracer/env`. Never copy any value into this repo. Read env vars at runtime
  only; `car/connect/env.example` shows the names.
- Never commit frames or photos that show people. `runs/` and `eventpics/` are gitignored. The
  only approved photos of people are the three event photos already in `docs/article/img/`.
- Calibration on the car is read, never written, without the operator's explicit approval.

## Git and scope

- Never `git add .` or `git add -A`. Scope every `git add` to the files you own.
- Agents do not `git commit`; the lead commits.
- Do not edit `pyproject.toml` outside your team's comment block; do not edit files outside
  the paths your task names.
- Upstream contributions follow `strands-labs/robots` `AGENTS.md`: one
  `changelog.d/<pr>-<slug>.md` fragment, never edit `CHANGELOG.md [Unreleased]`, refusal-table
  tests, 900-word doc pages.

## Facts

- Cite `docs/context/`, `docs/results/` and `docs/article/FACTS.md`. Do not invent numbers,
  dates or quotes. The demo video placeholder stays a placeholder until the author records it.
