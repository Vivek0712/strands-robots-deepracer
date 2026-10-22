# Notebook review, round 1 (2026-10-22)

Reviewer: `notebook-reviewer` (`.claude/agents/notebook-reviewer.md`). Read-only; the notebook was
executed with its output written to the scratchpad, never in place. Nothing in the repo was edited
or committed by this review.

Scope: `notebooks/decider_gate_walkthrough.ipynb` (14 code cells, 15 markdown cells, nbformat 4.5),
`notebooks/decider_gate_walkthrough.html`, `notebooks/README.md`, checked against
`patterns/strands/_client.py`, `patterns/strands/tool_call_intervention.py`,
`patterns/strands/frame_intervention.py`, `harness/fake_decider.py`, `harness/frames.py`,
`docs/context/03-strands-box-deciders-bidi.md` section 2.1, `docs/results/decider-benchmark-2026-10-14/q2610.json`
and `.kiro/steering/decider-patterns.md`.

Rubric lines applied: "Effective use of Decider 2B ... B2.2 Wiring and fail behaviour: fail-closed on
timeout or error", "B2.3 ... a notebook that runs it against a fake server", "B2.4 Measured latency
... p50 and p95", "B3.4 Honesty of claims". Brief rules applied: "Fake services for offline work:
`make fake-decider` (port 8111, `/v1/systemone`)", "No secrets."

Working-tree note: while this review ran, other sessions modified 44 tracked files (including
`harness/fake_decider.py`, `src/deepracer_agent/decider_client.py`, `Makefile`, `CLAUDE.md`) and
started `make fake-decider` on port 8111 at 16:08:57. Findings cite the working tree as read at
about 16:10 to 16:15; the notebook and its HTML are unmodified since commit `5adec9d`.

## Findings

| Severity | File:line (cell N) | Finding | Why it matters for the rubric | Suggested fix |
|---|---|---|---|---|
| High | `notebooks/decider_gate_walkthrough.ipynb` cells 1, 8, 12, 14 (no cell uses `fail=` or `latency_ms=`; `ServerUnavailable` appears nowhere in the notebook) | The notebook never shows the fail-closed path. `/control?fail=1` and `/control?latency_ms=3000` are never called, no `Deny("vision unavailable")` or `Deny("decider unavailable ...")` appears in any saved output, and `ServerUnavailable` is never imported or demonstrated. The only Denys shown are person, off_surface, unclear and "user asked to stop". The `control()` helper in cell 1 advertises "injected latency" but is only used for `label=`. | Checklist: "outputs show ... one Deny for `vision unavailable` (injected with `/control?fail=1` or `latency_ms`)" and "`ServerUnavailable` is demonstrated leading to `Deny`". Rubric B2.2 anchor 5 is "fail-closed on timeout or error". Spec `requirements.md` 6.3 and `tasks.md` 3.1 both promise this cell. | Add one cell after cell 14: `control(fail=1)`, run `MotionGate`/`FrameGate` once each, print the `Deny` and the log row; then `control(latency_ms=3000)` with a `Decider(timeout=1.5)` and show the timeout Deny; `control(fail=0, latency_ms=0)` at the end. Import `ServerUnavailable` in cell 6 and show it raised by `Decider(url="http://127.0.0.1:9", timeout=2).ask(...)` as `run_offline()` in `tool_call_intervention.py:339-342` already does. |
| Medium | cell 16, `nearest_rank` (`round(q * len(ordered) + 0.5) - 1`) | The percentile is not nearest-rank. Python `round` is half-to-even, so for n=20 the p95 index is `round(19.5) - 1 = 19`, the maximum (true nearest rank `ceil(0.95 * 20) - 1 = 18`); for n=10 the p50 is the 6th value, not the 5th. Verified: `n=20 p95 nb: 20 correct: 19`, `n=10 p50 nb: 6 correct: 5`. The saved numbers (0.4/0.5 ms on the fake) hide it, but the cell is labelled "nearest-rank p50 and p95" and sits beside the recorded booth numbers that `src/deepracer_agent/bench_decider.py:117` computes with `math.ceil`. | B2.4 "A benchmark file with p50 and p95 ... and the method"; a judge who copies the helper gets a wrong p95. | `return ordered[max(0, math.ceil(q * len(ordered)) - 1)]`, or import `percentile` from `deepracer_agent.bench_decider`. |
| Medium | cell 4, bullet 1 ("With two outcomes that probability is also the confidence; there is nothing else to report.") | Misstates the Decider's confidence. Per `docs/context/03-strands-box-deciders-bidi.md` section 2.1 a `noul` returns P(true) only; `confidence` is defined for `choice` as `(N p_max - 1)/(N - 1)` and for `score` as `1 - sigma/sigma_max`. Applying the choice formula at N=2 gives `2 p_max - 1`, which is not P(true); a noul at 0.5 has confidence 0, not 0.5. The rest of the bullet list (choice formula, 0.4667 for 4 options at 0.6, score as expected level) is correct and matches the output. | B3.4 honesty and the caller's explicit check "explains probability vs confidence correctly per the Decider docs section 2.1". | "A `noul` carries only `P(true)`. The server reports no separate confidence for it; how far the number sits from 0.5 is the whole story, which is why the gate uses one threshold `YES` and its mirror `1 - YES`." |
| Medium | cell 25 markdown (recorded run) and cell 24 default `us.amazon.nova-pro-v1:0` vs `tool_call_intervention.py:352` default `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Honest about the fake: the recorded run states "the fake decider on port 8111 as the judge (no real decider server was running on this machine at the time)" and explains why the fake could not object to the invented 2 m. Good. Two gaps: the pasted log is a markdown cell that nothing can re-verify, and the notebook's default Bedrock model differs from the library's, so a reader running `make pattern-demo` without `--offline` gets a different model than the one the recorded run used. Also prints the private `bedrock_gate._decider` (cell 24 line 31). | B3.4 "Numbers cited to files"; B2.3 drop-in consistency. | State in cell 25 that the log is a paste and name the file it came from if one exists (or save it under `docs/results/`); align the default model id in the library with `tech.md` (Nova Pro) or say why they differ; use `str(bedrock_gate._decider)` via a public attribute or drop the line. |
| Low | cell 0 (first markdown cell) | Does not name the declared pattern. "Guardrails" first appears in cell 7. The safety line and the typed questions are present and correct. | Checklist: "the first cell states the declared pattern (Guardrails), the typed questions and the safety line". Rubric A7 and the AI first-pass scorer key on the pattern name. | Add one sentence to cell 0: "The declared hackathon pattern is Guardrails (`#guardrails`, `#strands-decider-2b`): before a tool call, verify the arguments are grounded in what the user actually said." |
| Low | cell 6 output line 2 ("at or below 0.35 a confident no"), cell 26 ("at or below `1 - YES` a confident no"), cell 7 ("anything between `1 - YES` and `YES` is a `Confirm`") | Boundary is off by the equality. The code is `inside < self.no` and `grounded < self.no` (`tool_call_intervention.py:264, 272`) and the Confirm band is `[NO, YES)` per the module docstring line 26; verified `inside=0.35 exactly -> Confirm`. The library's own comment at lines 95-97 has the same slip. | B2.1 "thresholds explained". | "below 0.35 a confident no; 0.35 to 0.64 is the Confirm band". |
| Low | cell 3 request body (no `model` field) | The hand-written request omits `model`, which the pattern client always sends (`_client.py:148`), the steering request shape lists (`decider-patterns.md:19-29`) and the project client docstring lists. The fake accepts it; whether the real server requires it is unconfirmed here. | B2.3: a judge who copies cell 3 against a real server may get a 422 that the library would not. | Add `"model": MODEL_ID` (import it from `patterns.strands._client`) so the hand request matches the library request. |
| Low | cell 1 (`DECIDER_URL` default 8111, reuse of any server found) and cell 12 (`control(label=...)`) | The notebook reuses whatever answers on 8111 and, if it is the fake, rewrites its shared label (`runs/sim/shared.json` via `harness/shared.py:29`) seven times, resetting to `clear` only in cell 28. In this review the notebook attached to another session's `make fake-decider` (started 16:08:57) and drove its label; a sim run on the same laptop would have seen its camera label change. The checklist asks for "a subprocess on a non-default port". | Reproducibility for a judge with a sim stack running; "If execution needs a port, use one outside 8090/8092/8111/8765/9091". | Start the fake on a notebook-only port (for example 8311 via `python -m harness.fake_decider --port 8311` and `DECIDER_URL`) unless `DECIDER_URL` is set explicitly; or at least print a warning when a fake was already running. Mention the side effect in `notebooks/README.md`. |
| Low | cell 25 (`AWS_PROFILE=heisenberg`) | Not a secret, but a local AWS profile name a judge cannot use is printed in a public notebook. `grep -nE 'AKIA|aws_secret|password|DEEPRACER_PASSWORD|/Users/'` on the ipynb and the HTML returns nothing; the brief rule "No secrets" is met. | B3.4 clarity for a stranger. | Write `AWS_PROFILE=<profile with Bedrock access>` as cell 24 already does. |
| Info | cells 12, 17, 19, 22 figures | Opened all four PNGs. Legible; axes labelled; each says which numbers are fake and which are recorded: frame grid title "answered live by fake decider ... recorded booth-model answer beneath" with per-frame "live (fake)" and "booth model 2026-10-14" lines; latency chart title "Left: measured now against the fake decider ... Right three: recorded 2026-10-14"; envelope dot plot and calibration bars both titled "Recorded 2026-10-14". The frame grid honestly shows the booth model calling the drawn obstacle "clear 0.42". The fake's 0.4/0.5 ms bars are invisible at the 1700 ms scale but annotated. No real person in any image (all seven frames are Pillow drawings from `harness/frames.py`). | B3.1 "figures ... sourced". | None required. Optional: log-scale or an inset for the fake bars. |
| Info | cells 9, 15, 18, 20 claims checked against `q2610.json` and `decider-calibration-2026-10-14.md` | "mean P(inside) 0.92 for a 0.2 m/s hop, 0.10 for 0.5 m/s": hop_forward (linear 0.2) 0.92, too_fast (linear 0.5) 0.10, correct. "280 timed noul calls and 70 timed choice calls": n=280 and n=70, correct. "490 / 498" gate estimate: correct. "Blind ... misses the long duration and the sharp angular rate on three commands": far_too_long 0.70, too_sharp 0.85, too_sharp_negative 0.80 are the three wrong blind cases, correct. "about 95 ms more than the choice alone": calibration says 450 vs 355 ms p50, correct. "300 to 700 ms end-to-end stop budget": `docs/context/11-final-use-cases.md:43`, an estimate, labelled as such there. Decision table in cell 13 matches `frame_intervention.py:180-190` and `gate.py:69` (`UNCLEAR_THRESHOLD = 0.65`). | B3.4. | None. |
| Info | `notebooks/decider_gate_walkthrough.html` | Regenerated the HTML from the committed ipynb into the scratchpad; visible text is identical (40,623 characters, 5 embedded PNGs, no `/Users/` path). Title is the file name `decider_gate_walkthrough`. | B3.3 "a notebook" that a judge can read without Jupyter. | Optional: set a `title` in the notebook metadata so the HTML tab reads "Decider gate walkthrough". |
| Info | `notebooks/README.md:12-19` | Accurate: the `notebook` extra exists (`pyproject.toml:54`), the first cell behaves as described, `RUN_BEDROCK` guard matches cell 24. Missing: a headless one-liner (`jupyter nbconvert --to notebook --execute`) and the warning that an already-running fake on 8111 will be reused and relabelled. | B3.3. | Add the nbconvert line and the side-effect sentence. |

## Execution report

Pre-check: `lsof -i :8111` returned nothing at the start of the review. Another session then started
`make fake-decider` (PID 87929, parent `make fake-decider`, 16:08:57) before the run below, so the
notebook took its "was already running" branch; the committed outputs show the "started by this
notebook" branch and a clean `terminate()` (exit code -15).

Command (run from `notebooks/`, output to the scratchpad, repo file untouched):

```
cd ~/strands-robots-deepracer/notebooks
~/strands-robots-deepracer/.venv/bin/jupyter nbconvert --to notebook --execute \
  --output-dir <scratch>/nbreview \
  --output executed.ipynb --ExecutePreprocessor.timeout=600 decider_gate_walkthrough.ipynb
```

Result: exit 0, wall time 5 s, 0 error cells, no credentials used (`RUN_BEDROCK` unset, cell 24
printed the skip line). Executed copy:
`<scratch>/nbreview/executed.ipynb`.

Diff against the committed outputs (timings and PNG bytes masked):

- cell 1: `started by this notebook` -> `was already running` (explained above).
- cell 16: live fake p50 0.5 ms -> 0.6 ms (timing only).
- cell 28: `fake decider stopped (exit code -15)` -> `left the running decider on http://127.0.0.1:8111 alone`.
- every other code cell (3, 6, 8, 10, 12, 14, 17, 19, 21, 22, 24): identical. Every verdict, probability,
  class, reason string and table matches the committed file.

After the run: the only listener on 8111 is the other session's `make fake-decider` (`/control`
reports `label: clear`, `calls: 61`); the notebook left no process of its own behind. `git status`
shows no change under `notebooks/`.

Committed-output checklist: every code cell has outputs and `execution_count` 1..14 in order; outputs
show Proceed (cells 8, 10, 14), Guide (cells 8, 10, 14), Confirm (cell 10) and Deny (cells 10, 14);
no Deny for `vision unavailable` (finding 1).

## Scores (0-5)

| Criterion | Score | Basis |
|---|---|---|
| Runs offline, top to bottom | 5 | 5 s, no errors, no network beyond localhost, Bedrock guarded by `RUN_BEDROCK` (default off). |
| Outputs saved and meaningful | 3 | All saved and reproducible; Proceed, Guide, Confirm and Deny all shown; but no injected-failure Deny and no `ServerUnavailable` path, the one row the rubric's fail-closed anchor asks for. |
| Narrative quality | 4 | First person, plain ASCII (no non-ASCII characters in any cell, no em dashes, no rhetorical questions), each code cell introduced, last cell gives the three-step swap-in. Deductions: pattern name missing from cell 0, noul confidence sentence, threshold boundary wording. |
| No secrets or people | 5 | Secrets grep clean on ipynb and HTML; frames are drawn; the only questionable string is a profile name. |
| API fidelity to `patterns/strands/` | 4 | Imports `Decider`, `QUESTIONS`, `YES`, `MotionGate`, `FrameGate`, `FRAME_QUESTIONS` from the library, no private fork; question types `noul`/`choice`/`score`; request shape matches the steering file except the omitted `model` field; `ServerUnavailable`/`MODEL_ID` not imported or shown. |
