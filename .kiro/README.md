# Kiro setup

Open the repo root (`strands-robots-deepracer/`) as the workspace in Kiro.

## What loads

- `steering/product.md` (always): what the rover is, the seven beats, and the house line
  "physics stops the car; the decider explains".
- `steering/tech.md` (always): Python 3.12, strands-agents >= 1.57.2, the decider served on 8111
  with `make decider`, Bedrock profile `heisenberg`, the fake services, lint and test commands.
- `steering/structure.md` (always): the directory map and the naming rules.
- `steering/safety.md` (always): vehicle_state values, the zero servo pair before exit, the
  command gate, no secrets, scoped `git add`.
- `steering/decider-patterns.md` (fileMatch): loads only while editing `patterns/**` or
  `src/deepracer_agent/gate.py`; the request and response shapes, thresholds and the
  fail-closed rule.
- `specs/decider-guardrail-pattern/`: `requirements.md` (EARS), `design.md` and `tasks.md` for
  the reusable guardrail pattern.

## Hooks

`hooks/*.json` use the Kiro IDE 1.0 v1 schema (`trigger`, `matcher`, `action`, `timeout`,
`enabled`). Both fire on `PostFileSave`, run an agent action, and report without editing.

| Hook | Fires on | Runs |
|---|---|---|
| `pattern-tests.json` | any `patterns/**/*.py` save | `.venv/bin/python -m pytest tests/unit/test_patterns.py -q`, then ruff check and format check on `patterns` |
| `scan-on-save.json` | a pattern module, anything under `hackathon/`, `docs/article/article.md` or the root `README.md` | `.venv/bin/python hackathon/scan_submission.py --repo . --article docs/article/article.md` |

The matchers accept relative, `./`-prefixed and absolute paths. To check one by hand, save
`patterns/strands/_client.py` and watch for the pattern-tests report.
