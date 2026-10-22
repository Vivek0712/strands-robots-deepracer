# Tasks: reusable Strands Decider 2B guardrail pattern

Checked items exist in the repo today (`src/deepracer_agent/gate.py`,
`src/deepracer_agent/decider_client.py`, `harness/fake_decider.py`, their tests). The pattern
library, `hackathon/` and `tests/unit/test_patterns.py` landed on 2026-10-22 (56 tests pass);
unchecked items are what is still open. Requirement numbers refer to
`requirements.md`.

- [x] 1. Project gate and client (exists)
  - [x] 1.1 `DeciderClient` for `POST /v1/systemone` with `ask_noul`, `ask_choice`, `ask_frame`,
        `health`, `warm`; 1.5 s budget; every malformed response raises `DeciderUnavailable`
        (`src/deepracer_agent/decider_client.py`) (Req 2.1, 2.2, 5.1)
  - [x] 1.2 `DeciderGate(InterventionHandler)` with `before_tool_call` returning
        `Proceed` / `Guide` / `Confirm` / `Deny` / `Transform`; `on_error == "deny"`
        (`src/deepracer_agent/gate.py`) (Req 4.1, 4.2, 5.3)
  - [x] 1.3 `Envelope.violations` deterministic check beside the `noul` question;
        `envelope_context` shared with `bench_decider` (Req 4.4)
  - [x] 1.4 Decision table, rows checked in order (Deny, Guide, Confirm, Proceed); `combine_frame_answers` monotone toward Deny;
        `deny_threshold`, `UNCLEAR_THRESHOLD`, env `DEEPRACER_UNCLEAR_THRESHOLD` (Req 3.1, 3.3, 4.3)
  - [x] 1.5 One `verdict` event per stage with `latency_ms` and `frame_ref`; `stop` on Deny;
        `approval` on Confirm (Req 2.3)
  - [x] 1.6 Gate modes `enforce` / `advisory` / `off`, logged (Req 5.4)
  - [x] 1.7 `warm_gate` so the first real hop is not the cold one
  - [x] 1.8 Fake decider with the same wire shape and `/control` knobs (`harness/fake_decider.py`) (Req 6.1, 6.3)
  - [x] 1.9 Tests: `tests/unit/test_gate.py`, `test_decider_client.py`, `test_fake_decider.py`,
        `test_bench_decider.py`, `test_calibrate_frames.py` (Req 7.2, 7.3)
  - [x] 1.10 Calibration and benchmark recorded (`docs/results/decider-benchmark-2026-10-14.md`,
        `docs/results/decider-calibration-2026-10-14.md`) (Req 3.4)

- [x] 2. Pattern library `patterns/strands/` (hackathon deliverable; file names mirror the upstream quickstart)
  - [x] 2.1 `patterns/strands/_client.py`: `Decider` with `noul`, `choice`, `score` builders,
        `ask`, `health`, `NAME`, `MODEL_ID` = `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`,
        `ServerUnavailable`; stdlib only (Req 1.1, 1.2, 1.3, 8.1)
  - [x] 2.2 `patterns/strands/tool_call_intervention.py`: `QUESTIONS` dict, `YES` constant with
        the policy-knob comment, `InterventionHandler` subclass, `Agent(..., interventions=[gate])`
        `main()` runnable against the fake decider; `ServerUnavailable` -> `Deny`, never `Proceed`
        (Req 1.1, 3.1, 4.1, 5.1, 6.2)
  - [x] 2.3 `patterns/strands/frame_intervention.py`: vision variant with the person `noul` and
        the five-way `choice` over one base64 frame in one request (Req 1.4, 2.1)
  - [x] 2.4 `patterns/strands/README.md`: run command, how to swap questions and tools, the
        fail-closed rule, the safety line (Req 6.2)
  - [x] 2.5 `patterns/README.md`: library index naming the declared pattern (Guardrails) and tags
  - [x] 2.6 `tests/unit/test_patterns.py`: names present, refusal table, offline run (Req 7.1, 7.3)
  - [x] 2.7 Lint: `.venv/bin/ruff check patterns tests/unit/test_patterns.py` passes (2026-10-22);
        `ruff format --check` only flags the code blocks inside the two README.md files

- [x] 3. Offline demo and notebook
  - [x] 3.1 `notebooks/decider_gate_walkthrough.ipynb`: 16 code cells with outputs saved
        (2026-10-22), fake decider as a subprocess on port 8113, the typed questions and the four
        interventions shown, the `fail=1` / `latency_ms=3000` / no-frame / dead-port cell with
        `Deny("vision unavailable")`, `Deny("decider unavailable ...")` and `ServerUnavailable` in
        its saved output, the Bedrock run recorded against the real decider, no secrets (Req 6.4)
  - [x] 3.2 `make pattern-demo` (tool_call_intervention.py --offline) and `make pattern-demo-frame`
        exist in the `Makefile` (2026-10-22) (Req 6.2)

- [x] 4. Submission checks
  - [x] 4.1 `hackathon/RUBRIC.md` with the qualification gates and the four rubric criteria
  - [x] 4.2 `hackathon/scan_submission.py` reports zero FAIL on
        `--repo . --article docs/article/article.md` (Req 8.3). 2026-10-22 round 1: 11 PASS,
        4 WARN, 0 FAIL, 94.6/100 (`hackathon/reports/round-1.md`); the WARNs are the URL
        placeholders and the human-review rows
  - [x] 4.3 Article front matter carries `#strands-decider-2b` and `#guardrails`; demo video
        placeholder clearly marked (Req 8.2)
  - [x] 4.4 Review round recorded: round 1 (2026-10-22) in `hackathon/REVIEW-LOG.md`, seven
        reviewer reports in `hackathon/reports/round-1/` (`.claude/agents/README.md`)
