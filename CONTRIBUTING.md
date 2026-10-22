# Contributing

Thanks for looking. This repository is the agentic AWS DeepRacer built on
[strands-labs/robots](https://github.com/strands-labs/robots). It is small enough that one
rule carries most of the review: **physics stops the car; the decider explains.** Nothing you
add may present the decider, the agent or the voice as the layer that keeps a foot safe.

## Before you start

- Read `CLAUDE.md`, `AGENTS.md` and `docs/dev/CONTRACTS.md` (binding).
- Python 3.12 on the laptop (`make venv`). Anything under `car/` must stay Python 3.8: it runs
  on the Foxy image on the car.
- Never commit a frame or a photo that shows a person. The three event photos in
  `docs/article/img/` are the only approved exceptions.
- Never commit a car password or a console password. They live outside the repo.

## Workflow

1. Branch from `main`.
2. Run the no-car stack and the tests before and after your change:

   ```bash
   make fake-car & make fake-console & make fake-decider &
   make unit && make sim
   make lint
   ```

3. Any tool that publishes to `/manual_drive`, `/vehicle_state`, `/enable_state` or `/cmd_vel`
   goes through `strands_robots._command_gate`. Headless runs set
   `STRANDS_ROS2_COMMAND_ALLOW` explicitly and say so in their docs.
4. A mode change is always followed by `enable_state is_active=true`, and every drive publishes
   a zero servo pair before it exits. The car has no watchdog of its own.
5. Measured numbers go in `docs/results/` with the command that produced them. Do not write a
   latency or a probability into prose without a results file to cite.
6. Open a pull request with a short description of what changed and which make targets you ran.

## Changes to the Decider pattern

`patterns/strands/` mirrors the upstream `strands-decider` example names (`_client.py`,
`tool_call_intervention.py`). Keep the question names, the `QUESTIONS` dict and the `YES`
threshold stable, and re-run `python -m deepracer_agent.calibrate_frames` before changing any
frame question text or class description (see `docs/results/decider-calibration-2026-10-14.md`
for why).

## Contributing upstream

Fixes that belong in strands-robots follow its `AGENTS.md`: one `changelog.d/<pr>-<slug>.md`
fragment, refusal-table tests, and doc pages under 900 words.
