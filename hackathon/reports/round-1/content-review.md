# Content review, round 1 (2026-10-22)

Reviewer: content-editor-reviewer (read-only). Scope: `docs/article/article.md`, `README.md`,
`hackathon/SUBMISSION.md`, `patterns/README.md`, `patterns/strands/README.md`,
`notebooks/README.md`, the markdown cells of `notebooks/decider_gate_walkthrough.ipynb`.
Rules applied: the brief's style rules word for word, `hackathon/RUBRIC.md` gates A3, A5, A7 and
sub-criteria B2.1, B3.1, B3.3, B3.4, and the source-of-truth rule for the decision table
(`patterns/strands/tool_call_intervention.py` and `frame_intervention.py`: intent options
move_forward/turn/stop/question/unrelated; frame classes clear/obstacle_near/person_in_frame/
off_surface/unclear; `YES = 0.65`, `NO = 0.35`; `unclear` at or above 0.65 denies).

## Findings

| Severity | File:line | Finding | Why it matters for the rubric | Suggested fix |
|---|---|---|---|---|
| HIGH | `docs/article/article.md:97` vs `:165` | Line 97 says "an envelope violation is a Confirm for the operator"; the table at line 165 says a failed envelope check is a Guide. The library (`tool_call_intervention.py:256-263`) says Guide; the on-car `gate.py:27` says Confirm. The article states both without saying which gate it is describing. | B3.1 anchor 5 is "a reader could rebuild the decision from the article". Two outcomes for one input makes that impossible, and A3 asks for "the exact question handed to the Decider". | Line 97: "obstacle_near is a Guide at half speed, a failed envelope check sends the model back to re-plan, an unsure envelope or grounding answer is a Confirm for the operator, and no frame, a decider error or an answer later than 1.5 s is a Deny for vision unavailable." |
| HIGH | `docs/article/article.md:87`, `:91`, `:107` | The heading and line 91 say the gate asks two questions (envelope noul plus the frame pair, which is `gate.py`). Line 107 says the first request carries three questions and "the questions are the same" as the on-car tool. `gate.py` asks no `args_grounded` and no `intent` question (grep confirms; `FACTS.md:226` already flags this). | A3 and B2.1: the judge cannot tell which question set runs on the car. B3.4 (honesty): "the questions are the same" is not true today. | Line 107: "The first carries the conversation, the proposed tool call and the briefed envelope, with three questions. On the car the gate asks the envelope question alone and the arithmetic check does the rest; the drop-in library adds args_grounded and intent so it can catch a guessed distance without a camera. The on-car tool takes linear and angular speed and a duration; the library uses a distance and a heading." |
| HIGH | `docs/article/article.md:97`, `:172`, `:267` | "a palm over the lens reads around 0.90" and "the calibration study found ... a hand over the lens at about 0.90". The calibration file never contains 0.90. The booth model's covered-lens reading is 0.75 on the drawn frame (`decider-benchmark-2026-10-14.md:83`, `q2610.json` chosen_probability 0.7463). The 0.90 is the fake decider's fixed number from the sim run (`beats-sim-fastpub-2026-10-14/README.md:23`). The "plain floors and desks at 0.5 to 0.6" figure is a `gate.py:561-563` comment (a hotel corridor at 0.54 on 2026-10-17), and the calibration's real frames show a person at a desk at 0.58 to 0.67, not an empty desk. | B3.4: a number attributed to a measurement that did not produce it. The thresholds argument in "What I learned" rests on it. | Line 172: "The unclear threshold is 0.65 because the booth model read a desk scene as unclear at 0.58 to 0.67 on eleven real frames and the drawn covered lens at 0.75, so the bar sits between the two and a weak unclear proceeds and says so." Line 97: "a covered lens reads about 0.75 and stops". Line 267: "because I measured where a desk scene and a covered lens land". |
| HIGH | `hackathon/SUBMISSION.md:28-30`, `:41-56` | The declared-pattern sentence omits the "grounded in what the user actually said" check that defines Guardrails. The question table lists envelope/person/frame only (the on-car names), omits `args_grounded` and `intent`, and maps "envelope answers no" to Confirm. The article (`:158-170`), README (`:126-138`) and `patterns/strands/README.md:100-120` all show the library table with Guide for the envelope. | A7 and B2.3: the submission form is what the scanner and the judge read first; it must match the pattern folder. The library is the declared source of truth. | Line 28-30: "Declared pattern: Guardrails. Before every motion tool call, the agent verifies with Strands Decider 2B that the call is inside the envelope the operator briefed, that its argument values are grounded in what the user actually said, and that the live camera frame allows the move." Replace the two tables with the library names and rows from `patterns/strands/README.md:100-120`, and add one line: "On the car the envelope question runs alone and an unsure answer goes to the operator as a Confirm; the drop-in library adds args_grounded and intent." |
| HIGH | `README.md:126-138` | The column "What the rover says" quotes six lines ("I am at the edge. Not moving.", "You did not say how far. How far?", "I am not sure about this one. Marshal?", "Something is close ahead, going slower.", "That is outside the briefed envelope.", "You said stop. Holding."). Only the two narrator lines on rows 128-129 exist in code (`portal/backend/narrator.py:20-21`); none of the other six is anywhere in `src/`, `portal/` or `docs/results/`. | B3.4 and the brief's "no invented labels": quoted speech the rover never produces. | Drop the third column, or keep it for the two sourced rows only and write "the reason string from the gate log" for the rest. |
| MEDIUM | `README.md:121-123` | "every 2B checkpoint answering all 140 envelope questions correctly with the deterministic_check line present and only 79 percent without it". The benchmark (`decider-benchmark-2026-10-14.md:93-97`) gives 79 percent for 2610 only; v19 and v21 were 50 percent (70/140). | B3.4. | "the benchmark showed every 2B checkpoint answering all 140 envelope questions correctly with the deterministic_check line present; without it the booth model, 2610, managed 110 of 140 and the hobson checkpoints said yes to everything." |
| MEDIUM | `README.md:44-46` vs `:64-70` | "Two typed questions per hop" (the on-car gate) sits above a table of five questions in two requests (the library). Same two-gates confusion as the article. | B3.3 and B2.1. | Line 44: "**Judges every move with Decider 2B before the wheels turn.** Two requests per hop with typed questions, answered as calibrated probabilities and mapped to the Strands interventions Proceed, Guide, Confirm and Deny." |
| MEDIUM | `docs/article/article.md:87-101` and `:103-174` | The two decider sections repeat each other: the model id with --vision (89, 105), the frame question and five classes (91, 144-149), the mapping (97, 158-172), the 1.5 s Deny (97, 160), the 700 ms (95, 174), the safety line (99, 174). Decider prose is 1,488 of 4,896 words. The safety line appears six times in the article (3, 32, 99, 174, 213, 277). | B3.1: length without new information; the piece reads as two drafts stitched together. | Fold: keep paragraph 89 (what a Decider is, PR #10), paragraph 99 (modes) and paragraph 101 (narrator) in the first section; delete lines 91, 93-97 (the figure moves under the JSON at line 152); let the hackathon section carry the questions, the table and the numbers. Keep the safety line at 32, 213 and 277 and cut it from 99 and 174. |
| MEDIUM | `patterns/strands/README.md:91-94`; `patterns/README.md:55-56`; notebook cell 13 lines 6-8 and cell 26 lines 17-21 | "YES = 0.65 ... comes from the DeepRacer calibration" and "That rule came out of the calibration study". The calibration file sets no 0.65 and does not touch the text questions; it adds the person yes/no at 0.5 and says the Deny threshold is unchanged. The 0.65 unclear bar is `gate.py:69` with the comment at `:561-565` as its evidence. (`tool_call_intervention.py:98` carries the same sentence; out of this review's scope but it is the source the READMEs copy.) | B2.1 anchor 5 is "thresholds set from measurement"; claiming a measurement that does not exist invites the judge to open the file and find otherwise. | "`YES = 0.65` mirrors the on-car gate's unclear bar (`src/deepracer_agent/gate.py`, `UNCLEAR_THRESHOLD`). The calibration study in `docs/results/decider-calibration-2026-10-14.md` is the method: run it on your own traffic and set the knob from the two probability bands you see." |
| MEDIUM | notebook cell 2 line 5 | "three questions cost about the same as one". No file in `docs/results/` times a multi-question text request; the one measured case is the frame pair, which cost about 95 ms over the choice alone (`decider-calibration-2026-10-14.md:16`). | B3.4 and B2.4. | "It reads a `state` once and answers every question in the request from a shared prefix, so a second question costs far less than a second round trip: about 95 ms for the frame pair in `docs/results/decider-calibration-2026-10-14.md`." |
| MEDIUM | `README.md:31-55`, `:210` | The first screen says what it is (31) and the safety line (54), but "how to run it offline" is at line 210, after two JSON blocks (76-119) that duplicate `patterns/strands/README.md:18-53`. | B3.3 anchor 3 is "quick start" near the top; the checklist asks for the three things in under ten lines. | After line 37 add: "Run it offline in two commands: `make fake-decider` then `make pattern-demo`. Full quick start below." Replace lines 72-119 with: "The requests are the upstream System One shape (`POST /v1/systemone`); both question sets are written out as JSON in [patterns/strands/README.md](patterns/strands/README.md)." |
| MEDIUM | `docs/article/article.md:3`; `docs/article/FACTS.md:17`, `:20` | Description is 509 characters (limit 512, three to spare); FACTS says 477. FACTS line 20 still lists `physical-ai` as a tag; the article has `guardrails` (FACTS line 219 records the change but line 20 was not updated). | A3 (five tags, limits). Any further edit to the description tips it over. | Trim the description by one clause, e.g. drop "and gates and audits every motor command" (509 to 470), and update FACTS lines 17 and 20. |
| LOW | `docs/article/article.md:10` | `< COVER IMAGE >` is an inline placeholder while `cover: img/cover.png` is already in the front matter. If Builder Center takes the cover from the front matter, the literal text will publish. | A3 presentation. | Delete line 10, or replace with `![Cover](img/cover.png)` if the platform wants it inline. Author decides. |
| LOW | `hackathon/SUBMISSION.md:51` | "frame class person_in_frame at p >= 0.5". The library denies on class `person_in_frame` at any probability (`frame_intervention.py:182`). | Consistency with the pattern folder. | "person p >= 0.5, or frame class person_in_frame" |
| LOW | `docs/article/article.md:165-166`, `:169`; `README.md:133-134`, `:137` | "at 0.35 or below" / "<= 0.35" for the Guide rows. The library uses a strict `inside < self.no` (`tool_call_intervention.py:264`, `:272`); at exactly 0.35 it Confirms. | Rebuildability (B3.1). | "below 0.35" and "from 0.35 up to 0.65 is a Confirm". |
| LOW | `docs/article/article.md:267` | Nested triads: "Three things changed ..." contains "compare it to a number, log it and act on it". The passage has two rules of three. | Brief: at most one rule-of-three per passage. | "code can compare it to a number and act on it, and nobody has to parse prose." |
| NIT | `docs/article/article.md:73` | "one rule I consider load-bearing". Borderline stakes language. | Brief: no stakes inflation; body precise. | "The system prompt carries one rule I will not remove." |
| NIT | `docs/article/FACTS.md:19`, `:238`, `:241` | FACTS flags the series name as a placeholder and says `patterns/strands/`, `make pattern-demo` and the notebook "did not exist" on 2026-10-22; they exist now. | Housekeeping before publishing. | Update the three flag rows to "confirmed 2026-10-22". |

## Counts

- Title: 115 characters (limit 255).
- Description: 509 characters (limit 512). FACTS says 477; stale.
- Tags: 5 (`aws-deepracer, strands-agents, strands-decider-2b, amazon-bedrock, guardrails`); `strands-decider-2b` and `guardrails` present; one pattern tag only.
- Cover: `img/cover.png` 1200x675 (read from the PNG header); MANIFEST row says no text.
- Non-ASCII hits across all seven targets, including every notebook markdown cell: 0.
- Banned words (tapestry, landscape, paradigm, synergy, ecosystem, framework): 0.
- Filler transitions and "think of it as": 0.
- Questions ending in "?": 1 hit, `SUBMISSION.md:45`, a quoted question string, not rhetorical. Article: 0 outside quoted question text.
- Stakes words: 1 borderline ("load-bearing", `article.md:73`).
- One paragraph per line in the article: holds (no multi-line paragraph outside code and tables).
- First person: "I" at `article.md:20, 73, 89, 105, 205, 267`; "we" once at `:275` for the AWS User Group Madurai team (allowed per FACTS:204); "the author": 0. Byline present at `:14`.
- Placeholders: cover `:10`, testimonials `:249`, repo URL `:263` and `:271`, video `:273` all marked, none described as done. `SUBMISSION.md:71-73` likewise.
- Safety line present in every file reviewed; the decider is never called the safety layer. `SUBMISSION.md:58` and `README.md:55` say the opposite explicitly, as the brief asks.
- Links: every relative link in README.md and every image path in article.md resolves.

## Fifteen numbers spot-checked

| Number | Where used | Source | Result |
|---|---|---|---|
| 141 / 144 ms noul p50/p95 | article:174, README:143, SUBMISSION:65 | `decider-benchmark-2026-10-14.md:63` | matches |
| 349 / 354 ms choice | same | benchmark:63 | matches |
| 490 / 498 ms both | article:174, README:143, SUBMISSION:64, notebook cell 18 | benchmark:10, :63 | matches |
| 5.4 GB | article:174, README:143, SUBMISSION:65 | benchmark:63 | matches |
| 9.4 s load | SUBMISSION:65 | benchmark:63, `q2610.json` load_s | matches |
| 140/140 and 110/140 | article:154, SUBMISSION:66, FACTS:228 | benchmark:63, :93-96 | matches; README:121-123 generalises 79 percent to every checkpoint, wrong for v19/v21 |
| about 95 ms for the person yes/no | article:174, notebook cell 11 | calibration:16 (450 vs 355) | matches |
| 681-727 ms gate on the car | article:174, README:145, README alt:252 | `beats-car-2026-10-15-person-gate/README.md:20, :26` | matches |
| 456 ms person deny | README:145 | person-gate README:18 | matches |
| 47 ms first publish to PWM | article:213, README alt:252 | `wheels-off-2026-10-14.md:179` | matches |
| 35 ms STOP ALL, 22 ms barge-in | article:213, README:259 | `docs/results/README.md:23-24`, wheels-off:204-206 | matches |
| 278 ms deadman, 300 ms gap | article:213, :219, README:257 | wheels-off:209, :214-215 | matches |
| 0.90 covered lens | article:97, :172 | calibration: absent; benchmark:83 says 0.75; 0.90 is the fake decider (`beats-sim-fastpub` README:23) | does not trace |
| 0.58-0.67 unclear on 11 frames, 10 of 11 fixed | notebook cells 13, 20 | calibration:5, :15 | matches |
| mean P(inside) 0.92 (0.2 m/s) and 0.10 (0.5 m/s) | notebook cell 9 | `q2610.json` hop_forward 0.9161, too_fast 0.0965 | matches |

Also checked and matching FACTS: 20 Hz / 10 Hz heartbeat, 480x360, port 9090, 2 Hz deadman state, 2 s frame staleness, 0.3 m/s and 2 s hop cap, 0.5 s default hop, 24 GB, 14 October 2026, PR #10 on 3 October 2026, the four Strands release dates, 16 to 23 October 2026 and 5,000 dollars.

## Consistency of the decision table across files

| Item | Library (truth) | article | README | SUBMISSION | patterns/README | patterns/strands/README | notebook |
|---|---|---|---|---|---|---|---|
| intent options | move_forward, turn, stop, question, unrelated | match (:125-129) | match (:68, :92-96) | absent | named by type only | match | match (cell 5, 7) |
| frame classes | clear, obstacle_near, person_in_frame, off_surface, unclear | match | match | match | "five frame classes" | match | match (cell 11) |
| YES / NO | 0.65 / 0.35 | match | match | absent | absent | match | match |
| unclear >= 0.65 denies | yes | match | match | match | n/a | match | match |
| envelope fail | Guide | :165 Guide, :97 Confirm | Guide | Confirm | n/a | Guide | Guide |
| args_grounded, intent rows | present | present | present | absent | present | present | present |
| person_in_frame class | Deny at any p | match | match | "at p >= 0.5" | n/a | match | match |

## Scores (0-5)

- Clarity of the agent description: 4. Sections 1 to 4 and the Pit Wall and show sections read cleanly; the two-gates confusion costs the point.
- Clarity of the Decider decision: 3. The JSON blocks and the table are exactly what A3 asks for, but the Confirm/Guide contradiction and "the questions are the same" undo it until fixed.
- Traceability of claims: 3. All latency and car numbers trace; the 0.90 figure, the 79 percent generalisation and six invented rover quotes do not.
- Style compliance: 5 on the mechanical rules (ASCII, banned words, filler, questions, first person); 4 overall because of the repeated decider prose and the six safety-line repeats.
- Front matter and placeholders: 4. Limits met, placeholders marked; the description sits three characters under the limit and FACTS is stale on two rows.

## Flow note on the article after the inserted sections

The hackathon sections (103-174, 251-263, 265-267) are the strongest part of the piece and read in the author's voice. The seam is the old "Strands Decider" section directly before them, which pre-answers the same questions in a different gate's terms. With the fold suggested above the article drops to about 4,300 words, the decider story is told once, and the order "what a Decider is, the decision I handed it, how it maps, what it costs, the pattern you can copy" runs without a backtrack. "What I learned" and "Try it" close well; the final line earns its place once the safety line is cut from 99 and 174.
