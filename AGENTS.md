# AGENTS.md: rules for every agent working in this repo

Read `CLAUDE.md`, then `docs/dev/CONTRACTS.md` (binding), then `docs/context/00-README.md`,
`11`, `12`. Stay inside your team's paths (CONTRACTS §1). Use `.venv/bin/python`.

- Python 3.12 on the laptop; **Python 3.8** for anything under `car/` (it runs on the Foxy car).
- Tests: `tests/unit/test_<module>.py` for your modules; use upstream's transport stand-in
  pattern (a recorder object implementing `publish/echo/service_call`) rather than sockets.
  Refusal tables: one parametrised test that lists every input the module refuses and the
  reason string it returns.
- Every module docstring starts with one paragraph that a presenter could read aloud.
- Lint clean: `.venv/bin/ruff check <paths> && .venv/bin/ruff format <paths>`.
- No secrets in the repo. Read `~/.config/deepracer/env` at runtime only.
- Events: everything observable goes through `deepracer_agent.events.EventLog` (CONTRACTS §4).
- Safety lines to keep in docstrings and UI copy: "physics stops the car; the decider explains".
- Optional maintainer tooling; skip if you do not have KrewHQ: before finishing,
  `scripts/krewhq-session.sh capture <team> gotcha "<title>" "<text>"` for each thing that cost
  you time, then `scripts/krewhq-session.sh handoff <team> <next-team>`.
- Do not run `git commit`; the lead commits. Do not touch `pyproject.toml` outside your team's
  comment block.
