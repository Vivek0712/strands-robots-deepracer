# Criteria review, round 1 (Gate 2 posture)

Reviewer: hackathon-criteria-reviewer (read-only). Date: 2026-10-22. Commit reviewed: `8c320c4`
(README.md and docs/results/decider-benchmark-2026-10-14.md received one-line edits from another
agent during the review; the cited line numbers were re-checked afterwards and did not move).

Scope: `hackathon/RUBRIC.md` Parts A and B over README.md, docs/article/article.md,
docs/article/FACTS.md, hackathon/SUBMISSION.md, patterns/, notebooks/, src/deepracer_agent/gate.py,
src/deepracer_agent/decider_client.py, docs/results/. Out of scope by the brief (another agent is on
them): personal identifiers and local paths in docs/context and docs/results, KrewHQ references, the
demo video recording and the repo/article/video URL placeholders. They are mentioned only where
they move a score.

What I ran:

- `.venv/bin/python hackathon/scan_submission.py --repo . --article docs/article/article.md`:
  11 PASS, 4 WARN, 0 FAIL, heuristic 94.6/100 (same as `hackathon/reports/round-1.md`).
- `.venv/bin/python -m pytest tests/unit/test_patterns.py tests/unit/test_gate.py -q`: 115 passed.
- Fake decider on 8111, then `patterns/strands/tool_call_intervention.py --offline` and
  `patterns/strands/frame_intervention.py`, with and without `PYTHONPATH`: both run, both print
  the logged rows, both fail closed on a dead port. The `harness` package imports from the venv.
- Opened `docs/results/portal/04-main-person-deny.png`: a drawn stick figure, no real person.
- Not run: the README quick start (`make venv`, the four fake services, `make sim`), the notebook
  end to end, anything against Bedrock or a real decider.

Rule I apply throughout: physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb);
the decider explains. Nothing below treats the decider as the safety layer.

## Score table

Formula from RUBRIC.md: `bucket = weight * sum(sub-scores) / (5 * n)`.

| Sub-criterion | Score | One-line justification |
|---|---|---|
| B1.1 Problem the decision solves | 5 | A motor command on a real car is gated and the verdict is on a wall screen (README.md:232-247, fig-portal-stage). |
| B1.2 Surprise and delight | 4 | Seven beats with an arc and a payoff (Apology, Sign, Pull the Plug; article.md:237); none of them is recorded on the real car, so a judge reads about them rather than seeing them. |
| B1.3 Breadth of the Strands stack | 5 | Six Strands projects, each with a stated job and a file (README.md:198-205). |
| B1.4 Demo quality | 2 | No video; `car-hop.gif` is a phase-1 HTTP hop with no gate (MANIFEST.md:21), `pitwall.gif` is sim plus fake decider; no real-car run under the gate ever produced a Proceed on record (see F4). |
| B2.1 Decision design | 4 | Typed questions, deterministic check in code and measured (140/140 vs 110/140, benchmark Results table), unclear bar from a calibration study; but the text-question threshold is borrowed, not measured (F6), and the on-car gate asks fewer questions than the article declares (F1, F2). |
| B2.2 Wiring and fail behaviour | 4 | `before_tool_call` with all four verdicts, `on_error = "deny"`, 1.5 s budget, cooldown, warm-up, every verdict logged with latency (gate.py:578-581, 594-603; decider_client.py:316-328); the drop-in's default budget is 120 s (F7). |
| B2.3 Reusability of the pattern | 4 | Upstream file names, `QUESTIONS` as JSON, refusal-table tests, demos verified, executed notebook; but the only recorded end-to-end run of the declared guardrail shows the invented argument going through (F5). |
| B2.4 Measured latency or cost (bonus) | 4 | p50/p95, memory, four-model comparison and method (benchmark Results table); no improvement number against the alternative (Nova Pro judging the same call) and no numbers for the three text questions. |
| B3.1 Article clarity | 3 | The decision is rebuildable from the JSON and the table (article.md:109-170); but it starts at word 1400 of 4100 and the article contradicts itself on the envelope verdict and the question count (F1, F9). |
| B3.2 Video | 0 | Not recorded. The placeholder is honest (README.md:296-297, SUBMISSION.md:73, article.md:273); a judge today scores the absence. |
| B3.3 README and repo navigation | 5 | Hero, badges, every rubric heading, notebook, LICENSE, CONTRIBUTING, CITATION.cff; scanner "sections present (9/9)". |
| B3.4 Honesty of claims | 3 | Every number traces to docs/results; limits are stated in the results files; but the README and article present the five-question drop-in table as the car's gate, the article misdescribes `make pattern-demo`, and no real-car Proceed exists to back the first screen (F1, F4, F11). |
| B4.1 Novelty of the agent | 5 | A stock DeepRacer on strands-robots with a vision-plus-text Decider gate; no other entry is likely to have this body or this decision shape. |
| B4.2 Own contribution | 4 | strands-decider PR #10 merged and cited (article.md:89); the strands-robots fork branch is unmerged and uncited; earlier repos not named (F10). |
| B4.3 Provenance | 3 | LICENSE, CITATION.cff, clear authorship; but 26 of 61 commits predate the 16 October window, no remote yet, and the originality statement names no prior repo (F10). |

| Bucket | Sub-scores | Computation | Points |
|---|---|---|---|
| B1 Creativity (30) | 5, 4, 5, 2 | 30 * 16 / 20 | 24.00 |
| B2 Decider 2B with Bedrock (30) | 4, 4, 4, 4 | 30 * 16 / 20 | 24.00 |
| B3 Communication (25) | 3, 0, 5, 3 | 25 * 11 / 20 | 13.75 |
| B4 Originality (15) | 5, 4, 3 | 15 * 12 / 15 | 12.00 |
| **Total** | | | **73.75 / 100** |

Weighted total out of 5: 3.69. Projection: a 4/5 video alone lifts B3 to 18.75 and the total to
78.75; F1 to F5 fixed on top of that is the 85+ band RUBRIC.md Part C describes for a top-3 entry.

The scanner's 94.6 measures presence of evidence; this review measures quality. The gap between the
two is the list below.

## Findings, ordered by rubric impact

| Severity | File:line | Finding | Why it matters for the rubric | Suggested fix |
|---|---|---|---|---|
| HIGH (F1) | hackathon/SUBMISSION.md:41-56; README.md:44 vs :64-70 and :127-138; docs/article/article.md:87-97 vs :103-170; src/deepracer_agent/gate.py:21-28, 735-790; docs/article/FACTS.md:226 | The decision is described four different ways. SUBMISSION.md: three questions (envelope, person, frame), "envelope answers no -> Confirm". README.md:44: "Two typed questions per hop", then a five-question table at :64-70 and "envelope check fails -> Guide" at :133. Article :91: "two questions", "an envelope violation is a Confirm" at :97; then five questions and "envelope check fails -> Guide" at :165. gate.py asks two (ENVELOPE_QUESTION at :79 via `ask_noul` at :758; person + frame at :780) and returns Confirm at :789-791. FACTS.md:226 already flags that gate.py "asks no args_grounded or intent question". | B2.1 ("thresholds explained"), B3.1 ("a reader could rebuild the decision"), B3.4. A Gate 2 judge who opens gate.py after reading the article finds a different decision table; the article contradicts itself within two sections. | One canonical table, used verbatim in all four places, with two labelled columns: "on the car (gate.py)" and "drop-in (patterns/strands)". Say in one sentence which questions run on the car today and which are in the library. Change README.md:44 to the true count. Reconcile the envelope verdict (Confirm on the car, Guide in the drop-in) or make them the same. |
| HIGH (F2) | src/deepracer_agent/runtime.py (wires `DeciderGate`), src/deepracer_agent/gate.py:79, 758; patterns/strands/tool_call_intervention.py:68-93; docs/article/article.md:105 | The declared pattern is Guardrails, quoted in the brief as "before a tool call, verify the arguments are grounded in what the user actually said". The `args_grounded` and `intent` questions that implement that exist only in the drop-in library; the agent that drove the car (`DeciderGate`) asks the envelope yes/no and the frame pair. Article :105 says "that decision is my hackathon entry: whether this move is inside the envelope ... and grounded in what the user said", which is not what the car ran. | B2.1 and B2.2 (30 points): "Effective use of Decider 2B" is judged on the agent, and the declared pattern's defining question is not in its path. | Add `args_grounded` and `intent` to the envelope request in `DeciderGate._decide_with_frame` (one request; `_client.py:6-7` says one forward pass answers every question, so the cost is one noul call, 141 ms p50 per benchmark). Re-run `make unit` and one car or sim beat; record the new per-hop latency. If this cannot land before the deadline, say plainly in README "The decision handed to Decider 2B" and article :105 that the car runs the envelope and frame questions and the drop-in adds the grounding questions. |
| HIGH (F3) | README.md:296-297; hackathon/SUBMISSION.md:73; docs/article/article.md:273 | No demo video. The placeholder is correct and honest; the score is still 0/5 on B3.2 and 2/5 on B1.4 until it exists. Out of scope for this round, listed because it is the single largest lever (6.25 points on B3.2 alone, about 4 more on B1.4). | B3.2 anchor 5: "under 3 minutes, shows a Proceed and a Deny, says why in one sentence each". B1.4 anchor 5: "a failure case shown on purpose". | Shot list for 2:30: (1) Pit Wall and the car in the pen, one spoken "go forward 20 centimetres", the Proceed with its probability and ms on screen and the hop; (2) a consenting shoe into frame, Deny, the rover's line "Someone is in front of me. I stopped."; (3) "Go." typed, the Guide or Confirm card; (4) kill the decider process, next hop denied "vision unavailable" (fail closed shown on purpose); (5) STOP ALL. One sentence of narration per verdict. State the runtime in SUBMISSION.md. |
| HIGH (F4) | docs/results/beats-car-2026-10-15-person-gate/README.md:16-20, 34; docs/results/beats-car-2026-10-14-evening/README.md:13-20; docs/results/five-use-cases-2026-10-15.md:13-14; README.md:22-27 | There is no recorded run on the real car where the gate returned Proceed and the car hopped. Every on-car gated hop in docs/results was denied (operator in frame), and the 15 October note ends "Still waiting on a clear pen". FACTS.md:208 records that which beats ran live on stage is unknown. The README's first screen (hero, "judges every move", car GIF) implies the car drives under the gate. | B1.4 (anchor 3 needs "a live or recorded run with the decision on screen"), B3.4 (claims without a backing record). A tough judge asks: did the gated car ever move? | One clear-pen run with `events.jsonl` committed under docs/results: Pre-flight, two Proceed hops with the verdict rows, one Deny (consenting foot, frame withheld), one Confirm. Cite it in README "The decision handed to Decider 2B" next to the 681-727 ms figure. If the Community Day run exists on anyone's phone, the event log from that laptop session is the evidence; commit it. |
| HIGH (F5) | notebooks/decider_gate_walkthrough.ipynb cell 25 ("Recorded run on 2026-10-22"); patterns/strands/tool_call_intervention.py:309-316; harness/fake_decider.py | The one recorded Bedrock run of the declared guardrail: "Go." produced `move(distance_m=2)`, the deterministic check returned Guide, and the agent then re-planned four 0.5 m hops, each Proceed with `args_grounded 0.95` (the fake decider's scripted value), and reported "completing the total requested distance of 2 metres". The invented distance went through in pieces. The notebook says the fake is not a model, which is honest, but the recording is what a judge sees. | B2.3 anchor 5 needs a notebook that demonstrates the pattern; this one demonstrates the pattern not firing. B2.1 "questions designed around the model's strengths" cannot be shown without the real model answering `args_grounded`. | Re-record cell 25 with `make decider` (the real 2610 checkpoint) and `RUN_BEDROCK=1`. If `args_grounded` reads low on "Go." the Guide "ask the user" row fires and that transcript is the headline of the article's pattern section. If it reads high, that is the finding: tighten the `criteria` text or the state (add "arguments the user stated: none"), re-run, and write the before/after into the notebook. Either outcome is better than the current one. |
| MEDIUM (F6) | patterns/strands/tool_call_intervention.py:95-100; patterns/strands/README.md:89-94; docs/results/decider-calibration-2026-10-14.md:11-17 | `YES = 0.65` is said to come "from the DeepRacer calibration". That study measured the frame `unclear` class on 22 frames. No distribution of `inside_envelope`, `args_grounded` or `intent` on the real model exists in docs/results; the benchmark measured the envelope yes/no only (0.89 inside vs 0.09 outside, which actually supports a wider band than 0.35-0.65). | B2.1 anchor 5: "thresholds set from measurement". B2.4 bonus: the declared pattern's questions have no latency or accuracy row. | A 20-row text benchmark: 10 grounded utterances and 10 that omit a value, each through `MotionGate.state_for`, against the real decider, p per question recorded; put it in docs/results/decider-text-questions-<date>.md and set `YES` from the two distributions. `bench_decider.py` already has the harness shape. |
| MEDIUM (F7) | patterns/strands/_client.py:85; patterns/strands/tool_call_intervention.py:168-182; patterns/strands/README.md:57-63; README.md:128 | The drop-in `Decider` defaults to `timeout=120.0`, and `MotionGate` and `FrameGate` pass no budget. README.md:128 promises "decider slower than 1.5 s -> Deny", true for gate.py (decider_client.py:316-328) and not for the recipe a stranger copies. Tests pin the dead-port row but not a slow server. | B2.2 anchor 5: "fail-closed on timeout". A reviewer who copies the recipe gets a two-minute hang before the Deny. | `Decider(timeout=1.5)` in every wiring snippet (patterns/README.md:39, patterns/strands/README.md:61, README.md:159, article.md:259), or a `timeout_s` kwarg on both gates that overrides the client's budget per call; one refusal-table test with the fake decider's injected latency (`/control` supports it per the notebook's `control()` helper). |
| MEDIUM (F8) | notebooks/decider_gate_walkthrough.ipynb cells 15-17; docs/results/decider-benchmark-2026-10-14.md | The bonus asks for a "measured latency/cost improvement". The benchmark compares four Decider checkpoints to each other; nothing compares the local 2B against the obvious alternative, asking Nova Pro on Bedrock the same five questions. | B2.4 anchor 5 is met on method; the brief's word "improvement" is not. | One table in notebook section 5 and in the article's cost paragraph: the five questions as a Converse call to `us.amazon.nova-pro-v1:0` (ms p50/p95, input tokens, price per 1000 decisions from the public price sheet) beside the local 2B (490 ms, 0 dollars after the laptop). Ten repeats is enough. |
| MEDIUM (F9) | docs/article/article.md:16-102 (1406 words before the decision section); section word counts: Decider 413 + 727 of 4101 | The decision handed to Decider 2B starts at line 103, after strands-robots and Strands Agents. Builder Center readers and the Gate 1 scorer meet the hackathon's subject a third of the way in. The two Decider sections also overlap (both describe the frame questions and the thresholds). | B3.1 anchor 5 and the brief's requirement 2 ("describing the agent, what it does, and the decision handed to Decider 2B"): the article should be organised around that decision. | Move "The decision I handed to Decider 2B" to directly after "A rover that explains itself", merge "Strands Decider: two questions before every hop" into it, and cut strands-robots and Strands Agents to one paragraph each with a pointer to the repo. Target 2500 words. Keep the JSON blocks and the table. |
| MEDIUM (F10) | hackathon/SUBMISSION.md:75-79; README.md, docs/article/article.md (no mention of the earlier repos); git log dates: 25 commits 2026-10-14, 1 on 10-15, 20 on 10-17, 15 on 10-22; `git remote -v` empty | The originality statement does not name the earlier public repos (`Vivek0712/strands-agentic-deepracer`, `Vivek0712/aws_deepracer_control_v2`, docs/context/07) whose names a judge will find in one search, and 26 of 61 commits predate the 16 October window. The repo has no remote yet (URL placeholder, out of scope). | B4.3 anchor 5: "commit history inside the window, originality statement". RUBRIC A8 evidence: "first public commit date; no earlier article with the same agent". | Expand SUBMISSION.md "Originality": "Built from 14 October 2026 for AWS Community Day Mumbai (17 October) in a private repository, first made public for this submission. Two earlier public repos, <names>, are seeds: measured servo constants, the plan validator and the MJPEG parser were reused; they contain no Strands, no Decider and no gate." Add one line to README "Hackathon submission" and the article's "Try it". |
| MEDIUM (F11) | docs/article/article.md:259-262; patterns/strands/tool_call_intervention.py:352; patterns/README.md:37; notebooks cell 24 | Article :262 says `make pattern-demo` "sends a grounded command, an ungrounded one and a frame with a person through the gate and prints the four verdicts"; the target prints three rows (Proceed, Guide, Deny on a dead port) and the person frame is `make pattern-demo-frame`. The three-line snippet at :259 imports `Agent` and `BedrockModel` but not `MotionGate` or `Decider`, and uses `us.amazon.nova-pro-v1:0` while the file defaults to `us.anthropic.claude-haiku-4-5-20251001-v1:0` and patterns/README.md:37 shows the Claude id. | B3.4 (a claim a judge can falsify in one command), B2.3 (the first snippet a stranger pastes does not run). | Rewrite :262 to match the two targets' real output. Make the snippet complete (four imports, `Decider(timeout=1.5)`) and pick one Bedrock model id across article, patterns/README.md, tool_call_intervention.py and the notebook; Nova Pro is what the car used (runtime.py:40). |
| LOW (F12) | docs/article/article.md:10 (`< COVER IMAGE >`), :249 (`[TESTIMONIALS`), :263, :271 (`[REPO URL`); hackathon/SUBMISSION.md:71-73 | Four article placeholders and three SUBMISSION placeholders. Out of scope for this round; listed so the count is on record. A `[TESTIMONIALS` line left in a published article is the one that would embarrass. | B3.1, A4. | Fill or delete before publishing; delete the testimonials line if no quotes are cleared by their authors. |
| LOW (F13) | car/connect/env.example:6; docs/context/02-deepracer-ros-http-stack.md:87, 91 | Scanner WARN rows: the value `deepracer` is the image default documented by AWS (the file says so), not a secret. Gate G8 passes. | A Gate 1 scanner that greps `PASSWORD=` with a value may flag it anyway. | Leave the value blank in env.example and keep the comment ("image default, see AWS docs"); docs/context quotes the public docs and can stay. |
| LOW (F14) | README.md:285; notebooks/README.md:11-12 | `.krewhq/` row in the layout table (out of scope, already reworded on disk). The notebook needs `pip install -e ".[notebook]"`, which the README quick start does not mention; `jupyter`, `pandas`, `matplotlib` are not in `make venv`. | B3.3 anchor 5 ("a notebook") assumes it opens. | One line under README "Quick start": "Notebook: `uv pip install --python .venv/bin/python -e '.[notebook]'` then `make notebook`" (or document the `.html` export as the no-install path, which already exists). |

## Qualification gates

| Gate | Result | Evidence |
|---|---|---|
| G1 Decider 2B used for a meaningful decision | PASS | `/v1/systemone` at src/deepracer_agent/decider_client.py:67 (`SYSTEMONE_PATH`); `DeciderGate(InterventionHandler)` at gate.py:515, `before_tool_call` at gate.py:594-603 consuming `decide()` at :660-702. The decision, in one sentence: before every `drive_deepracer` call, is the command inside the envelope the marshal briefed and what is in front of the camera right now; a Deny blocks the hop (docs/results/beats-car-2026-10-15-person-gate/README.md:16-20, three `stop {cause: deny}` events, no motion event). |
| G2 Paired with Amazon Bedrock | PASS | `DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"` at src/deepracer_agent/runtime.py:40; article.md:36; `BedrockModel(...)` at patterns/strands/tool_call_intervention.py:351-354 and notebook cell 24; car run on Bedrock at docs/results/beats-car-2026-10-15-person-gate/README.md:5. |
| G3 Article describes the agent, what it does, the decision | PASS | docs/article/article.md: what it does :26, the decision :103-170 with both request bodies and the verdict table. Caveat F1: the article describes the decision two ways. |
| G4 Reusable pattern | PASS | patterns/strands/_client.py (`Decider.noul/choice/score`, `ask`, `health`, `ServerUnavailable`), tool_call_intervention.py:68 `QUESTIONS`, :100 `YES`, :155 `MotionGate(InterventionHandler)`, :212 `before_tool_call`; patterns/strands/README.md:55-75 wiring and offline run; patterns/README.md:21-48 drop-in procedure. Demos verified, 115 tests pass. |
| G5 Video placeholder | PASS | README.md:296-297 ("the recording is not made yet; do not treat this line as a link"), SUBMISSION.md:73 ("under 3 minutes"), article.md:273. Nothing fabricated. |
| G6 One declared pattern and both tags | PASS | article.md:4 tags `strands-decider-2b, ... guardrails` (five tags, one pattern tag); SUBMISSION.md:24 `#strands-decider-2b #guardrails`, :28 "Declared pattern: Guardrails". |
| G7 Originality statement | PASS, with F10 | SUBMISSION.md:77-79 states first publication for this hackathon. The earlier repos from docs/context/07 are not cited in README, article or SUBMISSION (grep returns nothing). 26 commits predate the window. |
| G8 Secrets and people | PASS, with F13 | No real credential in tracked files: env.example:6 and docs/context/02:87,91 carry the AWS-documented default. Photos: the three approved event photos in docs/article/img; docs/results/portal/04-main-person-deny.png is a drawn stick figure (opened). Real frames of a person are withheld (person-gate README:10, calibration study:38-40). |

## Score lines

- Creativity and cool factor: 4.0/5 (24.0/30), because the problem, the stack breadth and the
  seven-beat story are top-band, and the demo evidence a judge can watch is a sim recording with a
  fake decider plus an ungated phase-1 hop.
- Effective use of Decider 2B with Bedrock: 4.0/5 (24.0/30), because the typed questions, the
  deterministic check kept in code, the fail-closed wiring and the benchmark are all there and
  tested, and the declared pattern's defining question is not in the car's path, its threshold is
  borrowed, and its one recorded run does not show it firing.
- Communication quality: 2.75/5 (13.75/25), because the README is complete and the numbers are
  sourced, the article contradicts itself on the decision and buries it, and there is no video.
- Originality: 4.0/5 (12.0/15), because the body and the decision shape are new and PR #10 is
  merged and cited, and the provenance story (earlier repos, pre-window commits) is not told.
- Weighted total: 3.69/5 (73.75/100).

## What a top-3 entry has that this does not

1. A video in which the real car hops on a Proceed, stops on a Deny for a real foot, is sent back
   with a Guide for "Go.", and is denied on purpose when the decider is killed, each with one
   spoken sentence. This repo has every piece of that on the laptop and none of it on film.
2. The declared question in the agent's path. The brief's pattern is "arguments grounded in what the
   user actually said"; the car's gate does not ask it. One request change in gate.py closes the gap.
3. A recorded transcript where the real Decider 2B catches the invented argument. Today's
   recording shows the opposite on a scripted fake.
4. One decision table, told once, with measured thresholds for every question in it.
5. A cost line against the alternative: "Nova Pro would take X ms and Y dollars per thousand
   decisions; the local 2B takes 490 ms and nothing."
6. An originality paragraph a judge cannot improve on with a search.

## The three fixes that raise the score most, in order

1. Record the video to the F3 shot list and, in the same session, capture the clear-pen event log
   (F4). Raises B3.2 from 0 to 4 or 5 and B1.4 from 2 to 4: about 10 points.
2. Put `args_grounded` and `intent` into `DeciderGate`'s envelope request (F2), re-record notebook
   cell 25 against the real decider (F5), then write one canonical decision table into README,
   article, SUBMISSION and the pattern README (F1). Raises B2.1, B2.3, B3.1 and B3.4 by one each:
   about 7 points.
3. Measure the three text questions on the real model and set `YES` from the result (F6), add the
   Nova Pro comparison row (F8), and set `Decider(timeout=1.5)` in every snippet (F7). Raises
   B2.1, B2.2 and B2.4 by one each: about 4.5 points.

Projected after all three: about 95/100 by this rubric, which is the band RUBRIC.md Part C calls
top-3.
