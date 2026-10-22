---
inclusion: always
---

# Tech stack and commands

## Runtime

- Python 3.12 only on the laptop (`requires-python = ">=3.12,<3.13"`). Anything under `car/`
  runs on the Foxy car and must stay Python 3.8 compatible (ruff ignores `UP` there).
- Interpreter: always `.venv/bin/python`. Create it with `make venv`
  (`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"`).
- `strands-agents >= 1.57.2` with the `bidi` and `bidi-io` extras. Code against `strands.bidi`,
  never `strands.experimental.bidi`. Interventions come from `strands.interventions`
  (`InterventionHandler`, `Proceed`, `Guide`, `Confirm`, `Deny`, `Transform`).
- `strands-robots` is pinned to the fork branch
  `git+https://github.com/Vivek0712/robots@fix/deepracer-manual-state` in `pyproject.toml`.
  On the laptop it is installed editable from the worktree
  `~/Documents/strands-0.5x/robots-wt-deepracer` (recreate with the command in `CLAUDE.md` if
  `import strands_robots._command_gate` fails).
- Other deps: `roslibpy` (rosbridge), `httpx`, `websockets`, `boto3`, `pillow`, `numpy`,
  `strands-harness`, `cedarpy`, `fastapi`, `uvicorn`.

## Strands Decider server

- Model: `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`. Serve with `make decider`, which
  runs `strands-decider serve $(DECIDER_MODEL) --vision --device mps --port 8111` from the pip
  package `strands-decider` (no local checkout needed). `--vision` is required for any request
  carrying `images`.
- HTTP contract: `POST http://127.0.0.1:8111/v1/systemone`, `GET /health`. Env `DECIDER_URL`
  overrides the base URL. Client budget 1.5 s per request (`DEFAULT_TIMEOUT_S` in
  `src/deepracer_agent/decider_client.py`); slower is `DeciderUnavailable` and the gate denies.
- Measured (booth laptop, M4 Pro, 2026-10-14): both gate questions 490 ms p50 (p95 498 ms),
  5.4 GB, loads in 10 s. Source: `docs/results/decider-benchmark-2026-10-14.md`. The three text
  questions in one request: 462 ms p50 (p95 498 ms), `YES = 0.65` kept on measurement
  (`docs/results/decider-text-questions-2026-10-22.md`).

## Amazon Bedrock

- AWS profile `heisenberg`, region `us-east-1`, for every Bedrock, AgentCore or CDK call.
- Agent LLM and look-tool VLM: Amazon Nova Pro (`us.amazon.nova-pro-v1:0`). Voice: Amazon Nova
  Sonic via `strands.bidi.BidiAgent`. A Bedrock smoke test is allowed; do not loop against it.

## Fake services (offline work; no real decider is assumed to be running)

| Target | Service | Address |
|---|---|---|
| `make fake-decider` | `POST /v1/systemone`, `GET /health`, `/control?latency_ms=&fail=&label=` | `http://127.0.0.1:8111` |
| `make fake-console` | MJPEG + console API | `http://127.0.0.1:8090` |
| `make fake-car` | rosbridge-protocol fake car (+ control on 8092) | `ws://127.0.0.1:9091` |
| `make portal` | Pit Wall backend | `http://127.0.0.1:8765` |

Headless runs set `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`
and `DEEPRACER_BODY=sim`, and every doc that sets it says so. Port overrides for a second
stack are in `docs/dev/CONTRACTS.md` section 3.

## Lint and test

```bash
.venv/bin/ruff check <paths> && .venv/bin/ruff format <paths>   # lint + format the paths you touched
make lint                                                        # ruff check + format --check on src portal/backend harness beats tests
make unit                                                        # layer 0: .venv/bin/pytest -q tests/unit
make sim                                                         # layer 1: fake car + console + decider + agent + portal
.venv/bin/python -m pytest tests/unit/test_patterns.py -q        # the reusable pattern library
.venv/bin/python hackathon/scan_submission.py --repo . --article docs/article/article.md
```

Ruff: line length 110, target py312, rules `E F I UP B RUF`. Tests use a recorder object
implementing `publish/echo/service_call`, never sockets; each module ships a refusal table
(one parametrised test listing every input the module refuses and the reason string).
Layers 2 and 3 (`make wheels-off`, `make pen`) need the real car and an operator.

## Git

The repo root is `~/strands-robots-deepracer` on branch `main`. Agents never
`git commit`; the lead commits. Never `git add .` or `git add -A`; scope every add to the
paths you own.
