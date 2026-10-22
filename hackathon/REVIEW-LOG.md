# Review log

One row per finding per round. Run `make scan` (or `python hackathon/scan_submission.py ...`),
paste the summary table under the round heading, then log each finding with its fix and status.
Status is one of: open, fixed, accepted (kept on purpose, reason in Fix), deferred.

## Round 0 (baseline), 2026-10-22

Scanner: `hackathon/reports/round-0.md`, `round-0.json`. Result: 8 PASS, 5 WARN, 2 FAIL;
heuristic rubric estimate 79.2/100; exit code 1. Other teams were still creating `patterns/`,
`notebooks/`, `LICENSE` and the README while this ran, so the FAILs on those paths were expected.

| Check | Status | Weight | Gate | First evidence |
|---|---|---|---|---|
| Decider 2B usage | PASS | 10 | yes | /v1/systemone: 17 hit(s), first beats/kiosk.py:474 |
| InterventionHandler wiring | PASS | 10 | yes | subclass src/deepracer_agent/gate.py:515: class DeciderGate(InterventionHandler): |
| Amazon Bedrock pairing | PASS | 8 | yes | anthropic.claude: 1 hit(s), first src/deepracer_agent/runtime.py:38 |
| Reusable decision pattern folder | FAIL | 10 | yes | present: patterns/strands/_client.py |
| Strands family coverage (informational) | PASS | 3 |  | README mentions 5/6: strands-agents, strands-robots, strands.bidi, Strands Box, strands-decider |
| README structure | PASS | 6 |  | title: True; hero image above first section: True; badges: True |
| LICENSE and contributor guide | FAIL | 3 | yes | LICENSE: missing |
| Walk-through notebook | WARN | 2 |  | notebooks/*.ipynb: none |
| Article front matter | PASS | 8 | yes | title: 115 chars (limit 255) |
| Article body | WARN | 6 |  | byline 'Vivek Raja, AWS AI Hero': True |
| Submission package (hackathon/SUBMISSION.md) | WARN | 6 | yes | tags present: #strands-decider-2b, #guardrails |
| Originality statement | PASS | 3 |  | SUBMISSION.md states originality and prior non-publication: True |
| Secrets scan of tracked files | WARN | 10 | yes | WARN car/connect/env.example:6: password assignment, review |
| People-photo policy (human review) | WARN | 2 | yes | approved event photos: 3 |
| Tests present and collectable | PASS | 4 |  | test files under tests/: 37 |

| Date | Scanner score | Reviewer | Finding | Fix | Status |
|---|---|---|---|---|---|
| 2026-10-22 | 79.2 | scanner | `patterns/strands/README.md` missing; no "How to use" note; QUESTIONS not printed as JSON | patterns team wrote the README mirroring upstream `examples/strands/README.md` | fixed |
| 2026-10-22 | 79.2 | scanner | No `LICENSE` at the root (README badge says Apache-2.0) | `LICENSE` (Apache-2.0) added | fixed |
| 2026-10-22 | 79.2 | scanner | Article placeholders: `< COVER IMAGE >`, `[TESTIMONIALS`, `[REPO URL` | author fills at publish time; the cover marker stays (the bundle places uploads by marker) | deferred (URLs) |
| 2026-10-22 | 79.2 | scanner | SUBMISSION.md repo and video URLs are placeholders | fill after the repo is public and the video is uploaded | deferred (URLs) |
| 2026-10-22 | 79.2 | scanner | No `notebooks/*.ipynb` | notebooks team added `decider_gate_walkthrough.ipynb` | fixed |
| 2026-10-22 | 79.2 | scanner | Secrets WARN: `car/connect/env.example:6-7` empty password keys; private LAN IPv4 literals in `src/deepracer_agent/{connect,discover,quick_hop}.py`, `portal/frontend/src/views/Settings.tsx` | human review: keys are empty placeholders; IPs are example defaults, no credential | accepted |
| 2026-10-22 | 79.2 | scanner | People-photo WARN: `docs/results/portal/04-main-person-deny.png` | human review: portal screenshot of the drawn stick figure, no real person | accepted |

## Round 1, 2026-10-22

Scanner: `hackathon/reports/round-1.md`, `round-1.json`. Result: 11 PASS, 4 WARN, 0 FAIL;
heuristic rubric estimate 94.6/100. Seven read-only reviewer reports in
`hackathon/reports/round-1/`:

| Reviewer | Report | Scores (0-5) | Mean |
|---|---|---|---|
| content-editor-reviewer | `content-review.md` | agent description 4, decision clarity 3, traceability 3, style 4, front matter 4 | 3.6 |
| hackathon-criteria-reviewer | `criteria-review.md` | Creativity 4.0, Decider with Bedrock 4.0, Communication 2.75, Originality 4.0; weighted 3.69/5 (73.75/100) | 3.69 |
| repo-aesthetics-reviewer | `aesthetics-review.md` | hero 3, media 4, section order 3, links 4, naming 3 | 3.4 |
| kiro-setup-reviewer | `kiro-review.md` | steering 4, spec 3, hooks 3, consistency 3 | 3.25 |
| hackathon-code-reviewer | `code-review.md` | gate correctness 3, thresholds 4, error paths 4, tests 4, reusability 3 | 3.6 |
| decider-pattern-conformance-reviewer | `conformance-review.md` | file names 5, API names 4, request shape 5, handler contract 5, docs 4 | 4.6 |
| notebook-reviewer | `notebook-review.md` | runs offline 5, outputs 3, narrative 4, no secrets 5, API fidelity 4 | 4.2 |

Fixes below were applied the same day by the docs agent (article, README, SUBMISSION, results
index, Kiro, `.github`), the code agent (`patterns/`, `gate.py`, `decider_client.py`,
`CONTRACTS.md`) and the measurement agent (`docs/results/decider-text-questions-2026-10-22.md`).
The canonical decision (five questions in two requests, 13 rows checked in order, row 7 Confirm on
the car and Guide in the drop-in) is the lead's decision of 2026-10-22 and every file now states it.

| Date | Scanner score | Reviewer | Finding | Fix | Status |
|---|---|---|---|---|---|
| 2026-10-22 | 94.6 | content, criteria F1, aesthetics | The decision described four ways (two vs five questions; envelope fail Confirm vs Guide) across article, README, SUBMISSION, gate.py | One canonical 13-row table in article, README (in `<details>`), SUBMISSION and the pattern README; one sentence states the single row-7 difference and why; gate.py asks the same five questions (code agent) | fixed |
| 2026-10-22 | 94.6 | criteria F2 | `args_grounded` and `intent` only in the drop-in, not in the car's gate | Added to `DeciderGate`'s text request (code agent; verified in `gate.py` 2026-10-22) | fixed |
| 2026-10-22 | 94.6 | criteria F3, aesthetics 3 | No demo video; TODO wording in README | Article/Demo video pending table in README and SUBMISSION; recording is the author's | deferred (video) |
| 2026-10-22 | 94.6 | criteria F4 | No recorded clear-pen Proceed hop on the real car | Stated in the Limits paragraph of the article and README; the run needs the car | deferred (car runs) |
| 2026-10-22 | 94.6 | criteria F5, notebook | Recorded Bedrock run shows the invented argument going through on the fake decider; no failure-injection cell | Real-decider text run recorded in `decider-text-questions-2026-10-22.md` (no invented argument proceeded); notebook re-record and fail cell remain open (tasks.md 3.1) | deferred (car runs / notebook) |
| 2026-10-22 | 94.6 | content, criteria F6 | `YES = 0.65` claimed to come from the frame calibration; no text-question distribution | Measured on the real 2B: grounded >= 0.78, invented <= 0.63, 0 confident errors at 0.65/0.35; cited in article, README, SUBMISSION, tech.md | fixed |
| 2026-10-22 | 94.6 | criteria F7 | Drop-in `Decider` defaults to a 120 s timeout; snippets pass no budget | Every wiring snippet in README and article uses `Decider(timeout=1.5)`; library default is the code agent's | fixed (docs) |
| 2026-10-22 | 94.6 | criteria F8 | No cost or latency comparison against the hosted alternative | Nova Pro on the same `args_grounded` question: 69/72, 797/4069 ms, 31 of 72 over budget, 0.13 USD per 1000 decisions; in article, README, SUBMISSION | fixed |
| 2026-10-22 | 94.6 | content, criteria F9 | Decision section starts at word 1400; two Decider sections overlap | Merged into one section "The decision I handed to Decider 2B" directly after "The architecture at a glance" (word 580); prose cut from about 3,950 to about 3,300 words | fixed |
| 2026-10-22 | 94.6 | criteria F10 | Originality statement names no earlier repo; pre-window commits | Originality paragraph in article "Try it", README and SUBMISSION naming `Vivek0712/aws_deepracer_control_v2` and `Vivek0712/strands-agentic-deepracer`, what carried over, and that the agent was private until this submission | fixed |
| 2026-10-22 | 94.6 | criteria F11 | `make pattern-demo` misdescribed (four verdicts); snippet incomplete; model id mismatch | Three rows described; four imports and `Decider(timeout=1.5)`; model id `us.amazon.nova-pro-v1:0` matching `tool_call_intervention.py` (`BEDROCK_MODEL_ID` default), the same model as the car | fixed |
| 2026-10-22 | 94.6 | criteria F12 | Four article placeholders | `[TESTIMONIALS]`, `[REPO URL]`, `[VIDEO URL]` kept and marked; cover marker kept on purpose | deferred (URLs) |
| 2026-10-22 | 94.6 | criteria F13 | Scanner WARN on `car/connect/env.example:6` | AWS-documented default, no credential; human review | accepted |
| 2026-10-22 | 94.6 | criteria F14 | Notebook install not in the quick start | One line under "Try it in 60 seconds": `uv pip install ... -e '.[notebook]'` then jupyter lab | fixed |
| 2026-10-22 | 94.6 | content | 0.90 covered-lens figure not in any measurement | 0.75 for the drawn covered lens (benchmark line 83) and 0.58-0.67 for the person-at-desk frames (calibration) in the article, FACTS rows added | fixed |
| 2026-10-22 | 94.6 | content | Six invented "What the rover says" quotes in the README | Column dropped; the two narrator lines from `portal/backend/narrator.py` kept in prose | fixed |
| 2026-10-22 | 94.6 | content, aesthetics | "every 2B checkpoint ... 79 percent" generalised | 2610-only statement, "110 of 140 (79 percent)", with the benchmark link | fixed |
| 2026-10-22 | 94.6 | content | "Two typed questions per hop" | "Five typed questions in two requests per hop" | fixed |
| 2026-10-22 | 94.6 | content | "<= 0.35" for the Guide rows; the library uses strict `<` | "below 0.35" and `[0.35, 0.65)` in every table | fixed |
| 2026-10-22 | 94.6 | content | Description 509 of 512 characters; FACTS says 477 and lists `physical-ai` | Trimmed to 471; FACTS tag and description rows updated | fixed |
| 2026-10-22 | 94.6 | content | Nested rule-of-three in "What I learned"; "load-bearing" | "compare it to a number and act on it"; "one rule I will not remove" | fixed |
| 2026-10-22 | 94.6 | content | Cover marker duplicate | Kept: the Builder Center bundle places uploads by marker | accepted |
| 2026-10-22 | 94.6 | content | Pattern README and notebook say YES comes from the calibration | Pattern README is the code agent's; notebook cell text remains open | deferred (code agent / notebook) |
| 2026-10-22 | 94.6 | aesthetics 1 | No call to action under the badges | Four-link CTA row (Try it, Copy the pattern, Read the article, Watch the demo) | fixed |
| 2026-10-22 | 94.6 | aesthetics 2 | Hero GIF opens on the phase-1 planner UI | `car-hop.gif` re-cut to the 4 s of the car on the floor (640 px, 12 fps, 1.35 MB), no person in any of the 48 frames; caption "phase-1 HTTP hop, ungated" | fixed (a gated recording is deferred: car runs) |
| 2026-10-22 | 94.6 | aesthetics 4 | Repo URL 404, no CI badge | Needs the public push | deferred (URLs) |
| 2026-10-22 | 94.6 | aesthetics 5 | Fixed-width `<table>` media pairs overflow at 390 px | `<p align="center">` with two `width="49%"` images for both pairs | fixed |
| 2026-10-22 | 94.6 | aesthetics 6 | Quick start at line 210 | "Quick start: try it in 60 seconds (no car)" right after "What it does", two-command offline line first | fixed |
| 2026-10-22 | 94.6 | aesthetics 7 | Duplicated JSON, 90-line decision section | Second JSON block and the 13-row table in `<details>`; link to `patterns/strands/README.md` for the full tables | fixed |
| 2026-10-22 | 94.6 | aesthetics 8 | SUBMISSION question names drift from the library | Regenerated from the canonical names and table | fixed |
| 2026-10-22 | 94.6 | aesthetics 9 | Layout table misses `.github/`, `.claude/`, `scripts/` | Rows added | fixed |
| 2026-10-22 | 94.6 | aesthetics 10 | `docs/results/README.md` is a one-day diary with no index | Retitled "Measured results", index of every note including the 2026-10-22 one, diary under a dated heading, "today" replaced, "Lead authorised" sentence removed | fixed |
| 2026-10-22 | 94.6 | aesthetics | No "Limits" paragraph in the README; "Start here" points at the research diary | Limits section added; Start here points at `docs/context/12-architecture.md` and `docs/dev/CONTRACTS.md` | fixed |
| 2026-10-22 | 94.6 | aesthetics | No `SECURITY.md`, issue template or `.gitattributes` | All three added | fixed |
| 2026-10-22 | 94.6 | aesthetics | Social preview, `fig-deepracer.png` alpha, `pitwall.gif` black first frame, results page renames | Not in this round | deferred |
| 2026-10-22 | 94.6 | kiro 6 | README and hook descriptions mention a `.kiro.hook` pair that never existed | `.json` only (Kiro IDE 1.0 v1); README split into "What loads" and "Hooks" | fixed |
| 2026-10-22 | 94.6 | kiro 7 | Hooks lack `timeout` and `enabled`; `^`-anchored matchers | `"enabled": true`, `"timeout": 300`; matchers accept relative, `./` and absolute paths (tested with `re`) | fixed |
| 2026-10-22 | 94.6 | kiro 8 | Trailing period after the commands in the prompts | Commands in backticks | fixed |
| 2026-10-22 | 94.6 | kiro 9 | `structure.md` puts `drive_deepracer`/`stop_deepracer` in `tools.py`; `tech.md` names a home-directory checkout | Moved to `driver.py`; `make decider` via the pip package, no local path | fixed |
| 2026-10-22 | 94.6 | kiro | `tasks.md` ticks stale | 3.2, 4.2, 4.4 ticked with today's numbers; 3.1 rewritten (14 code cells, outputs saved, fail-injection cell open) | fixed |
| 2026-10-22 | 94.6 | kiro High, Medium | Drop-in does not validate probability range or unknown class; CONTRACTS section 7 and the gate.py docstring say unclear 0.5 | Code agent's scope (`patterns/`, `gate.py`, `CONTRACTS.md`) | deferred (code agent) |

## Round 2 (2026-10-22, after the round-1 fix wave)

Scanner: 11 PASS, 4 WARN, 0 FAIL, heuristic 94.6/100 (`hackathon/reports/round-2.md`). Unit suite 997 passed, 1 skipped; sim layer 26 passed.

| Date | Scanner score | Reviewer | Finding | Fix | Status |
|---|---|---|---|---|---|
| 2026-10-22 | 94.6 | code FAIL 1-3 | Drop-in gates and `decider_client._parse_choice` proceeded on NaN, out-of-range or string probabilities and unknown classes | `probability()` helpers in both recipes and the production client; unknown class, missing key, bool, NaN, out of range all Deny; refusal rows added (997 unit tests) | fixed |
| 2026-10-22 | 94.6 | code HIGH 4-5 | `intent_p` fell back to confidence; Confirm interrupt crashed the Bedrock demo on the next request | Missing `probabilities[intent]` denies; `main()` loops on `stop_reason == "interrupt"` and resumes with `interruptResponse` (exercised live) | fixed |
| 2026-10-22 | 94.6 | code MEDIUM 6-12 | Sync blocking handler with 120 s timeout, unbounded render, no latency on Deny rows, HTTPException escaping, non-dict input | Async handlers with `asyncio.to_thread` and a 1.5 s budget, `render()` bounded, latency on every row, HTTPException folded, dict guard, `yes` validated | fixed |
| 2026-10-22 | 94.6 | code 10 / criteria F2 | Production gate asked two text-side questions fewer than the declared pattern; `off_surface` proceeded | On-car gate asks the five questions in two requests; `off_surface` denies; CONTRACTS section 7, steering, READMEs carry the canonical 13-row ordered table | fixed |
| 2026-10-22 | 94.6 | criteria F6 | YES 0.65 borrowed from the frame calibration | Measured on the real 2B: grounded >= 0.78, invented <= 0.63, 0 confident errors at 0.65/0.35 (`docs/results/decider-text-questions-2026-10-22.md`) | fixed |
| 2026-10-22 | 94.6 | criteria F8 | No cost or latency comparison against the generative model | Nova Pro on the same question: 69/72 right, 797/4069 ms, 31 of 72 over budget, about 0.13 USD per 1000; local 2B 462/498 ms, 0 over budget | fixed |
| 2026-10-22 | 94.6 | criteria F5 | Only recorded Bedrock run used the fake decider | Re-recorded against the real 2B: "Go." -> Guide (arithmetic), re-planned hop -> Confirm at grounded 0.40, operator declined, no motion (notebook, recorded-run cell) | fixed |
| 2026-10-22 | 94.6 | notebook 1-5, 9, 10 | No fail-closed cell; p50/p95 rounding; noul confidence wording; pattern unnamed; strict threshold wording; shared 8111 side effect | Fail-injection cell (fail, 3 s latency, dead port); `math.ceil` ranks; wording fixed; Guardrails named in cell 0; default port 8113 | fixed |
| 2026-10-22 | 94.6 | notebook (new) | Four concurrent gate calls crashed the 2B on Metal (command encoder assertion); gates failed closed | Recipe client serialises requests per server with a process-wide lock; notebook uses `SequentialToolExecutor` | fixed |
| 2026-10-22 | 94.6 | conformance 1-5 | Tags, `STRANDS_DECIDER_URL`, `last_latency_ms`, install line, `QUESTIONS` alias | All added to the recipes and their README | fixed |
| 2026-10-22 | 94.6 | audit BLOCKER | Car SSH password equals the Mac login short name present in `/Users/...` paths in history | Paths scrubbed in the tree; password rotation and a clean-snapshot publish are the author's | deferred (author) |
| 2026-10-22 | 94.6 | criteria F3, F4 | Demo video; clear-pen run with a recorded Proceed | Need the car and the author | deferred (author) |
| 2026-10-22 | 94.6 | gates G7 | Repo, article and video URLs; testimonials | Placeholders remain, clearly marked | deferred (author) |
