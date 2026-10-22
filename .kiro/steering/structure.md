---
inclusion: always
---

# Repository structure

Ownership per path is in `docs/dev/CONTRACTS.md` section 1. Stay inside the paths your task
names. Module docstrings open with one paragraph a presenter could read aloud.

| Path | What lives there |
|---|---|
| `src/deepracer_agent/` | Laptop side. `driver.py` (rosbridge Ackermann driver, bicycle model, trailing zero; the `drive_deepracer` and `stop_deepracer` tools), `transport.py`, `calibration.py`, `tools.py` (`capture_frame`, `battery_level`, `set_led`, `preflight`), `runtime.py` (AgentRuntime, ApprovalBroker), `events.py` (EventLog, one JSON object per line), `gate.py` (DeciderGate: Verdict, Decision, Envelope, BargeInStop), `decider_client.py` (DeciderClient, DeciderUnavailable), `look.py`, `voice.py`, `voice_pcm.py`, `prompts/` (SIGN_RULE), `plans.py`, `shapes.py`, `bench_decider.py`, `calibrate_frames.py`, `discover.py`, `connect.py`, `twin.py` |
| `patterns/` | The reusable Strands Decider 2B decision-pattern library (hackathon deliverable). `patterns/README.md` is the index. `patterns/strands/` mirrors the upstream quickstart file names exactly: `_client.py` (`Decider`, `Decider.noul/choice/score`, `.ask`, `.health`, `NAME`, `MODEL_ID`, `ServerUnavailable`), `tool_call_intervention.py` (`QUESTIONS`, `YES`, `MotionGate(InterventionHandler)`), `frame_intervention.py` (`FrameGate`, vision variant), `README.md` |
| `hackathon/` | Submission material: `README.md`, `RUBRIC.md` (criteria and gates), `scan_submission.py` (scanner: file names, imports, API names, tags, front matter, secrets), `SUBMISSION.md`, `REVIEW-LOG.md` (review rounds), `reports/` (scanner output per round) |
| `notebooks/` | `decider_gate_walkthrough.ipynb`: runs top to bottom offline against the fake decider, outputs saved, no secrets |
| `car/` | On-car code (Python 3.8, ROS 2 Foxy): `deadman/` node, `guard/` camera guard, `pwm/`, systemd units, `install.sh`, `rollback.sh`, `connect/` (find-car, env.example) |
| `harness/` | Fakes: `fake_car.py` (rosbridge protocol, ws 9091), `fake_console.py` (MJPEG, 8090), `fake_decider.py` (`/v1/systemone`, 8111), `frames.py` (seven drawn 480x360 frames, no real people), `shared.py`, `stack.py` |
| `beats/` | The seven beats plus `kiosk.py`, `shapes.py`, `two_bodies.py`; run with `make beat NAME=<beat> BODY=sim|car` |
| `portal/` | Pit Wall: `backend/` (FastAPI + WebSocket), `frontend/` (React/Vite, built `dist/` committed), `evidence/` (Playwright captures) |
| `ops/` | `pit_stop.cedar` policy and `race_engineer.py` (Strands Harness, SSH sandbox to the car) |
| `tests/` | `unit/` (layer 0, `test_<module>.py`, refusal tables), `sim/` (layer 1), `car/` (wheels off), `pen/` (operator present), `conftest.py`, `fixtures/` |
| `docs/context/` | Research bundle and decisions (`00-README.md` index; read 00, 11, 12, then 06); `council/` |
| `docs/dev/` | `CONTRACTS.md` (binding integration contract), `networking.md`, `phases.md`, `platforms.md`, `upstream-pr-manual-state.md` |
| `docs/results/` | Measured evidence: decider benchmark and calibration (2026-10-14), beats runs, wheels-off, voice audio, portal captures |
| `docs/article/` | `article.md` (the Builder Center article), `FACTS.md` (every claim with its source file), `img/` (figures and the three approved event photos), `publish/` |
| `docs/talk/` | The conference deck and its verified-sources notes |
| `.kiro/` | Kiro steering (this directory), the `decider-guardrail-pattern` spec, hooks (`hooks/*.json`) |
| `.claude/agents/` | Claude Code reviewer subagents for the hackathon review round |
| `.krewhq/`, `scripts/` | Team context protocol and session scripts |
| `Makefile`, `pyproject.toml` | Lead-owned. Add deps only inside your team's comment block |

Gitignored and never committed: `runs/` (events.jsonl and frames, which may show people),
`eventpics/`, `.agent/`, `upstream/`, `.venv/`, `.env`. The only approved photos of people
are the three event photos already in `docs/article/img/`.

Naming: tests are `tests/unit/test_<module>.py`; results notes are
`docs/results/<topic>-YYYY-MM-DD.md` with raw output in a sibling directory of the same name;
spec folders under `.kiro/specs/` are lowercase-hyphenated.
