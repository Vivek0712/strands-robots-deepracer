# Round 1 review: Gate 2 judge reads the script as the video it will become

Reviewer stance: a Gate 2 panel judge, fortieth demo of the day, sound on for the first pass,
sound off for the second. Sources read: `docs/video/SCRIPT.md` and `STORYBOARD.md` (the thing
under review), `docs/results/decider-text-questions-2026-10-22.md`, `hackathon/SUBMISSION.md`,
`docs/dev/CONTRACTS.md` section 7, the notebook cell "Recorded run on 2026-10-22" in
`notebooks/decider_gate_walkthrough.ipynb`, plus the code and manifests the script quotes
(`patterns/strands/tool_call_intervention.py`, `frame_intervention.py`, `README.md`, `Makefile`,
`portal/backend/narrator.py`, `harness/fake_decider.py`, `docs/media/MANIFEST.md`,
`docs/article/img/MANIFEST.md`, `docs/results/beats-car-2026-10-15-person-gate/README.md`).
Date of review: 2026-10-22. Nothing outside this file was changed.

## Scores (1-5, one line each)

| Criterion | Score | One line |
|---|---|---|
| Hook, first 10 s | 3 | "This car just refused an order." is a good line, but the footage under it is labelled UNGATED, so the first two things a judge reads contradict each other. |
| What the agent is, by 0:30 | 5 | Shot 3's title and the seven callouts land at 0:12-0:28; I could name the car, the agent model and the judge before the half-minute. |
| Can a judge state the 2B decision (question, options, action) | 5 | Shot 5 shows all five questions verbatim with types and option sets, shot 6 the four actions and the thresholds, shot 7 one real answer; this is the best-specified decision I have seen today. |
| Proof it works (real decider, real Bedrock, real car vs sim, labelled) | 3 | Real decider and real Nova Pro are proven on shots 7-8 with dates; the only real-car footage is ungated phase-1, the only Deny shown is a fake decider's constant, and the real on-car gated Deny (2026-10-15, 456 ms) that exists in the repo is never mentioned. |
| Use of the measured numbers | 4 | Shot 11 is the strongest card: 24 cases, 72 calls, p50/p95, budget line, cost; "0 USD per 1000" drops the source's "marginal, after the laptop" qualifier. |
| Reusable pattern visibility | 4 | File tree with upstream names, three wiring lines, a real `make pattern-demo` recording, URL to the path; the three reason strings on the card do not match what the command prints. |
| Originality cues | 4 | A local 2B judging a hosted frontier model, a stock DeepRacer as a Strands robot, Mumbai stage photos, the AI Hero byline; the measured 2B-vs-Bedrock comparison is the thing nobody else will have. |
| Pacing | 3 | 387 words at 150 wpm is right; shot 8 at 28 s (129 wpm) and shot 4 at 18 s (3.5 s per region) both sag, shot 10 at 174 wpm is the fastest read over the densest frame. |
| Sound-off legibility | 4 | Every shot carries its own text; the risk is density, not absence (shots 5, 8 and 11 are 10+ lines of 26-30 px text each). |
| Ending (URL, tags, memorable line) | 5 | URL in mono, both tags, the safety line twice, author line, 9 s hold; nothing to add. |

Weighted read against the rubric: the Decider section (30 percent) and communication (25) are
strong; creativity (30) is carried by the idea and undercut by the lack of a gated car on screen;
originality (15) is well cued.

## Fact check: every number and quote in the VO and on-screen text

| # | Shot | Claim | Verdict | Source |
|---|---|---|---|---|
| 1 | 1 | Title "This car just refused an order." over `car-hop.gif` | FAIL (footage) | `docs/media/MANIFEST.md` line 7: "forward-and-back hop from the phase-1 HTTP agent (ungated)". The car in the shot refused nothing. The label is true; the title is not true of the footage. |
| 2 | 1, 9 | `REAL CAR, PHASE-1 RECORDING, UNGATED`, 4 s, 640x360 | PASS | `docs/media/MANIFEST.md` line 7; measured 640x360, 48 frames, 4000 ms. |
| 3 | 2, 10 | `person_in_frame 0.97`, `Deny` | PASS as sim, FAIL as a judgement | `harness/fake_decider.py` line 12: the fake returns the constant `person_in_frame 0.97`. It is not a measurement; the SIM label is on screen, the VO in shot 10 voices it as a result ("a Deny at zero point nine seven"). |
| 4 | 2 | `pitwall-sim.webm` | PASS, note | File is 1280x720, 7.8 s; the storyboard scales it to 1920x1080 (1.5x upscale, will look soft next to the rendered cards). |
| 5 | 3 | "Vivek Raja, AWS AI Hero" | PASS | `docs/article/article.md` line 14; `hackathon/scan_submission.py` DEFAULT_BYLINE. |
| 6 | 3 | Seven callouts: Decider, robots, deadman, Harness, Agents, Bidi, Box | PASS | `docs/article/img/MANIFEST.md` line 50. |
| 7 | 3, badges | `Agent: Amazon Nova Pro on Bedrock` / `Judge: Strands Decider 2B, local` | PASS for shots 3-8, 11, 12; FAIL on shot 10 | Notebook cell 29 (`us.amazon.nova-pro-v1:0`, `strands-decider-2B-qwen3.5-v1-2610`). On shot 10 the footage's judge is the fake decider while the badge says "Strands Decider 2B, local". |
| 8 | 4 | Deadman "300 ms rule in red" / "stops without the laptop" | PASS | `docs/context/12-architecture.md` line 12; `docs/article/img/MANIFEST.md` line 17 (measured 278 ms). |
| 9 | 5 | "Is the proposed movement inside the envelope the operator briefed?" | PASS | `patterns/strands/tool_call_intervention.py` QUESTIONS. (Note: `CONTRACTS.md` section 7 words the on-car version differently, "Is this drive command inside the briefed envelope?"; the video quotes the pattern, which is the right one to quote.) |
| 10 | 5 | "Are the tool's argument values grounded in what the user actually said?" | PASS | Same file; `SUBMISSION.md` table; `CONTRACTS.md` section 7. |
| 11 | 5 | "What did the user most recently ask the robot to do?" + `move_forward turn stop question unrelated` | PASS | Same file; `CONTRACTS.md` section 7. |
| 12 | 5 | "Is a person visible in the frame?" | PASS for the pattern | `patterns/strands/frame_intervention.py` FRAME_QUESTIONS. (`CONTRACTS.md` on-car wording adds "(any part of a human body)".) |
| 13 | 5 | "What is directly in front of the car in this camera frame?" + `clear obstacle_near person_in_frame off_surface unclear` | PASS | `frame_intervention.py`; `CONTRACTS.md` section 7 classes list. |
| 14 | 5 | "480x360 JPEG", `POST /v1/systemone`, "two requests" | PASS | `CONTRACTS.md` section 7; `SUBMISSION.md`. |
| 15 | 6 | DENY rows 1-6 summary; GUIDE rows 7-11; CONFIRM row 12 `0.35 <= p < 0.65`; PROCEED row 13 | PASS, one omission | `CONTRACTS.md` section 7 table and `SUBMISSION.md`. Row 7 is Guide in the drop-in and Confirm on the car; the card says Guide only. Acceptable for a video about the pattern, worth a footnote word. |
| 16 | 6 | `NO 0.35`, `YES 0.65`, `budget 1.5 s`, "thirteen rows", "never fails open" | PASS | `src/deepracer_agent/gate.py` lines 94-95; `CONTRACTS.md` section 7 ("Never fail open"). |
| 17 | 7 | `"conversation": "user: Move forward 20 centimetres."` | PASS | `MotionGate.render` emits `f"{role}: {text}"`; transcript line `USER : Move forward 20 centimetres.` in cell 29. |
| 18 | 7 | `"command": {"tool": "move", "arguments": {"distance_m": 0.2, "heading_deg": 0}}` | PASS (key order differs from the log) | Log row 1: `{"heading_deg": 0, "distance_m": 0.2}`. Cosmetic. |
| 19 | 7 | `"envelope": "distance_m <= 0.5 per call, \|heading_deg\| <= 90"` | PASS | `Envelope.describe()` line 158; results doc "Default envelope". |
| 20 | 7 | `inside_envelope 0.948`, `args_grounded 0.907`, `intent move_forward 0.959`, PROCEED, `583 ms` | PASS | Cell 29 gate log row 1 (`latency_ms: 583.3`). |
| 21 | 7 VO | "zero point nine five", "zero point nine one", "five hundred eighty three milliseconds" | PASS | Row 1 reason string "inside envelope p=0.95, grounded p=0.91". |
| 22 | 8 | `distance_m 2`, `distance_m 2 > 0.5`, `args_grounded 0.18`, GUIDE | PASS | Cell 29 gate log row 2. |
| 23 | 8 | `distance_m 0.5`, `args_grounded 0.404`, CONFIRM, "inside envelope p=0.88, grounded p=0.40" | PASS | Cell 29 gate log row 3 and the CONFIRM line. |
| 24 | 8 | `OPERATOR: no` | FAIL (truncated quote) | Cell 29 transcript reads `OPERATOR: no (this cell auto-answers False)`. The storyboard says "nothing is altered, only keys omitted"; this line is altered, and the omission hides that no human pressed no. |
| 25 | 8 | `AGENT: The move could not be completed because the decider is unsure about it ... Please provide further instructions or clarification.` | PASS | Cell 29, the AGENT line after the `<thinking>` block; ellipsis is marked. |
| 26 | 8 | Lower-third "Live proof" | FAIL (wording) | The shot is a rendered terminal replay of a recorded transcript (storyboard: "Rendered terminal replay ... typing pace about 40 characters per second"). Not live, not a screen recording. |
| 27 | 8 VO | "Then I say only: Go." | PASS, note | The run was the notebook cell run as a script with typed input, not voice; "say" is loose but the transcript line is `USER : Go.` |
| 28 | 9 | `drive_deepracer(linear, angular, duration)` | PASS | `CONTRACTS.md` section 6 and `docs/article/img/MANIFEST.md` line 19. |
| 29 | 9 | Gate node "blinks green once as the car moves" | FAIL (implied event) | The footage is ungated (`docs/media/MANIFEST.md` line 7). No gate verdict happened in it; the animation invents one. |
| 30 | 10 | `Row 3: person in frame -> Deny` | PASS | `CONTRACTS.md` section 7 row 3. |
| 31 | 10 | "Someone is in front of me. I stopped." | PASS | `portal/backend/narrator.py` line 21. |
| 32 | 10 | stop card `deny, 92 ms` | PASS (sim) | `docs/article/img/MANIFEST.md` line 20 (fake runtime). |
| 33 | 11 | "Measured, 24 cases, 72 timed calls, Apple M4 Pro" | PASS | Results doc: Setup and Method. |
| 34 | 11 | `462 ms p50`, `498 ms p95`, `0 of 72 over the 1.5 s budget` | PASS | Results doc, latency table (client round trip). |
| 35 | 11 | `0 USD per 1000 decisions` / VO "costs nothing per decision" | PASS with a dropped qualifier | Results doc: "0 USD marginal after the laptop (Apple M4 Pro, 24 GB; 5.4 GB footprint)". The card and VO drop "marginal" and "after the laptop". |
| 36 | 11 | `797 ms p50`, `4069 ms p95`, `31 of 72 over the 1.5 s budget`, `0.13 USD per 1000 decisions` | PASS | Results doc, Nova Pro table (0.1318). |
| 37 | 11 | Footnote "Nova Pro inside Bedrock: 391 ms p50. The tail is the network." | PASS | Results doc: provider-side 391 / 558 ms; "The 3.3 s to 5.6 s tail is the path to us-east-1". |
| 38 | 11 | "Local 2B: 0 confident errors on args_grounded" | PASS | Results doc P(yes) table: confident wrong 0. |
| 39 | 11 VO | "Nova Pro on the same question" | PASS, note | True of the question (`args_grounded`); the latency columns compare three questions in one 2B call against one question in one Bedrock call, which the on-screen headers state and the source discusses (a like-for-like three-call gate would be about 0.395 USD). The comparison is conservative in 2B's disfavour, so it stands. |
| 40 | 11 VO | "a four second tail over Wi-Fi" | PASS | p95 4069 ms, max 5620 ms, "from the same laptop over Wi-Fi". |
| 41 | 12 | File tree `_client.py`, `tool_call_intervention.py`, `frame_intervention.py`, `README.md` | PASS | `ls patterns/strands/`. |
| 42 | 12 | `Decider(timeout=1.5)`, `BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1")`, `interventions=[MotionGate(decider)]` | PASS | `patterns/strands/README.md` Wiring block (as `interventions=[MotionGate(Decider(timeout=1.5))]`); code lines 434-436. |
| 43 | 12 | Panel 3 reasons `inside envelope` / `outside envelope: re-plan` / `decider unavailable: failing closed` | FAIL (two of three) | `run_offline` prints the log rows; the reasons are `inside envelope p=..., grounded p=...`, `outside envelope: distance_m 2 > 0.5` and `decider unavailable: failing closed, no motion` (lines 330, 352, 120). There is no "re-plan" in the printed reason. |
| 44 | 12 VO | "make pattern demo runs it offline against a fake decider" | PASS | `Makefile` lines 73-74 (`--offline`, "make fake-decider first"). |
| 45 | 12 | Footer `github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands` | PASS | `SUBMISSION.md` Links. |
| 46 | 13 | "AWS Community Day Mumbai, 17 October 2026" | PASS | `docs/article/article.md` line 28; `FACTS.md` line 28. |
| 47 | 13 VO | "Shown live at AWS Community Day Mumbai." | PASS with a flag | `FACTS.md` line 28 marks "which beats ran live on stage" as unverified in the docs. "Shown at" is fully sourced; "live" rests on the author. |
| 48 | 14 | URL, `#strands-decider-2b #guardrails`, "Article on AWS Builder Center" | PASS | `SUBMISSION.md` Tags and Links. |
| 49 | script | "387 words", "2 minutes 35 seconds at 150 wpm" | PASS | Counted 387; 154.8 s. |

## Decider-as-safety-layer scan

No sentence calls the decider the safety layer, and the safety line appears twice in the exact
wording. Three places still let a tired judge infer it:

- Shot 2 VO "A person in the frame. The light went red." The red LED in the portal is the
  stop indicator (`fake_runtime.py` emits `LED["red"]` on a deny). Spoken over a person and a
  DENY, it says the decider's verdict is what protected the person. Fix: "A person in the frame.
  The hop was refused. Here is why." (the LED can still go red on screen).
- Shots 1-2 together: "refused an order" then a person in frame, before anyone has heard that
  physics stops the car. The safety line arrives at 2:00, 108 s later. Fix: put a one-line
  on-screen footer on shot 2: `Physics stops the car. The decider explains.` (small, ink-dim),
  so the frame is read correctly from the start.
- Shot 9 "On the car, the gate sits before every hop" over footage of an ungated car with an
  animated green gate blink. It tells the judge the gate was in the loop in the footage; it was
  not, and the honesty label says so in the same frame. See finding F2.

## Hype and filler

- Shot 1 "just" in "This car just refused an order." claims a specific past refusal the footage
  does not show. "This car can refuse an order." is true and almost as sharp.
- Shot 8 lower-third "Live proof" on a rendered replay. "Recorded run, 2026-10-22" is the honest
  and still strong wording.
- Shot 11 "costs nothing per decision" and `0 USD per 1000 decisions`. The source says "0 USD
  marginal after the laptop". Say "0 USD marginal (after the laptop)" on the card and "costs
  nothing more per decision once the laptop is paid for" in the VO.
- Shot 7 "One real answer." and shot 8 "A guessed distance moved nothing." are fine: specific,
  earned by the log.
- Shot 13 "live" (see fact check 47); drop it unless the author confirms what ran on stage.
- No tapestry/landscape/paradigm/synergy/ecosystem/framework words, no rhetorical questions
  (the five questions on shot 5 are the decider's, not rhetoric). The VO is clean.

## Could a judge misread anything as faked footage, and do the labels cure it?

| Shot | Risk | Label present | Cured? |
|---|---|---|---|
| 1 | Real car shown under a title about refusing; a judge assumes the footage is the refusal | `REAL CAR, PHASE-1 RECORDING, UNGATED` at 0:03 | Half. The label is honest but it contradicts the title in the same frame, which costs trust rather than earning it. Change the title (F1). |
| 2, 10 | Fake decider's constant 0.97 and a drawn figure read as a real detection | `SIM, FAKE DECIDER, DRAWN FIGURE` | Yes for the picture; no for shot 10's VO, which voices 0.97 as a judgement, and no for the Judge badge on shot 10, which names the real 2B while the fake is on screen. |
| 8 | A rendered, typed-in terminal reads as a screen recording of a live session | `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO` plus the "Live proof" lower-third | Partly. The date label is right; "Live proof" undoes it. Also the truncated OPERATOR line hides the auto-answer. Rename the lower-third and restore the parenthetical. |
| 9 | Ungated footage with an animated gate verdict | `REAL CAR, PHASE-1 RECORDING, UNGATED` | No. The blink is an invented event; a label cannot cure an animation that depicts something that did not happen. Cut the blink or the shot. |
| 12 | Panel 3 is a real recording against a fake decider | header `make pattern-demo`, VO "against a fake decider" | Yes. |

## Three cuts I would make

1. Shot 9 (4 s). Same GIF as shot 1, ungated, with an invented gate blink and the only VO line
   that puts the gate "on the car" over footage where it was not. Give the 4 s to shot 8's
   freeze or to the new card in "one thing to add".
2. Shot 4 from 18 s to 12 s. Five regions at 3.5 s each is a slide reveal; the judge already
   saw the stack on shot 3. Light regions 1-2 together, 3 alone (it is the point), 4-5
   together; same VO at 44 words in 12 s is 220 wpm, so trim the VO to: "Nova Pro on Bedrock
   proposes each move. A Strands intervention handler asks the decider before the tool runs.
   strands robots carries it over rosbridge. The on-car deadman stops it without any of this."
3. Shot 8 from 28 s to 22 s. The typing pace (40 characters per second) is the cost. Pre-type
   the two header lines and the first USER/AGENT turn (they are already shown in shot 7), start
   the replay at `USER : Go.` with the gate rows appearing at 1:24 and 1:29, the CONFIRM pair at
   1:33, the AGENT line at 1:37, freeze 1:40-1:43.

## One thing I would add

The real on-car gated Deny. `docs/results/beats-car-2026-10-15-person-gate/README.md` line 18:
"hop with a person in frame: PASS, denied in 456 ms; `person_in_frame` p 0.9485". Frames were
withheld because they show a person, which is the right call, and a card does the job: replace
shot 9 with a 6 s card on `#0b0b10`, lower-third right `MEASURED ON THE CAR 2026-10-15, REAL
DECIDER, FRAMES WITHHELD (THEY SHOW A PERSON)`, centre: `On the car: a person in frame was
denied in 456 ms` / `person_in_frame p = 0.9485` / `whole gate 681 to 727 ms per hop`, VO: "On
the car, the same gate denied a hop with a person in frame in four hundred fifty six
milliseconds. The frames stay private; they show a person." That single card turns the video's
weakest rubric line (proof on real hardware) from sim-only into measured, and it is the first
time the judge hears a number from the car itself. Source for 681-727: `SUBMISSION.md` Measured
latency; `docs/article/img/MANIFEST.md` line 18.

## Findings table

Severity: HIGH blocks a fair reading of the submission; MED a judge may dock or misread; LOW polish.

| Severity | Shot | Finding | Suggested change (exact replacement text) |
|---|---|---|---|
| HIGH | 1 | Title asserts a refusal over footage labelled UNGATED; the first frame contradicts itself and "just" is unearned. | Title and VO: `This car can refuse an order.` Keep the source label. |
| HIGH | 9 | Ungated footage with an animated gate verdict ("gate node blinks green once as the car moves") and the VO "On the car, the gate sits before every hop." Depicts an event that did not happen in the clip. | Cut shot 9. Replace with the 6 s measured-on-car card described above, VO: `On the car, the same gate denied a hop with a person in frame in four hundred fifty six milliseconds. The frames stay private; they show a person.` |
| HIGH | 8 | `OPERATOR: no` truncates the verbatim `OPERATOR: no (this cell auto-answers False)`, while the storyboard promises "nothing is altered". Hides that no human answered. | On screen: `OPERATOR: no (auto-answered by the test cell)`. VO: `The scripted operator says no, and the agent asks me instead of driving.` Step label 5: `5 Operator (scripted): no. The agent asks instead of driving.` |
| MED | 8 | Lower-third "Live proof: the real decider judges Nova Pro" over a rendered terminal replay. | `Recorded run, 2026-10-22: the real decider judges Nova Pro` |
| MED | 10 | VO voices the fake decider's constant 0.97 as a judgement, and the Judge badge `Judge: Strands Decider 2B, local` stays on screen while the fake decider's output is shown. | VO: `In the simulator, a figure in the frame is row three, a Deny, and the rover says why. Physics stops the car. The decider explains.` Swap the badge on shots 2 and 10 to `Judge: fake decider (sim)` or hide it for those shots. |
| MED | 12 | Panel 3 reason strings do not match what `make pattern-demo` prints. | Chips with reasons: `inside envelope p=0.95, grounded p=0.95` (take the values from the recording) / `outside envelope: distance_m 2 > 0.5` / `decider unavailable: failing closed, no motion`. |
| MED | 2 | VO "The light went red." makes the decider's verdict sound like the thing that protected the person, 108 s before the safety line is heard. | VO: `A person in the frame. The hop was refused. Here is why.` Add an ink-dim footer on shot 2: `Physics stops the car. The decider explains.` |
| MED | 11 | `0 USD per 1000 decisions` and "costs nothing per decision" drop the source's qualifier. | Card: `0 USD marginal per 1000 decisions (after the laptop)`. VO: `The local two B costs nothing more per decision once the laptop is paid for.` |
| MED | 4 | 18 s for five regions at 3.5 s each; the stack was already named in shot 3. 44 words. | Cut to 12 s; VO: `Nova Pro on Bedrock proposes each move. A Strands intervention handler asks the decider before the tool runs. strands robots carries it over rosbridge. The on-car deadman stops it without any of this.` |
| MED | 8 | 28 s at 129 wpm; the shot over 20 s that does not fully earn it. The first turn duplicates shot 7. | Pre-type the headers and the first turn; start at `USER : Go.`; total 22 s (beats at 1:21, 1:24, 1:29, 1:33, 1:37, freeze 1:40-1:43). |
| LOW | 6 | GUIDE band says "rows 7-11: outside envelope" with no note that row 7 is Confirm on the car. | Footnote line 2 (ink-dim): `Row 7 on the car: Confirm, the marshal may approve a bigger hop.` |
| LOW | 13 | "Shown live" is flagged unverified in `FACTS.md` line 28. | VO: `Shown at AWS Community Day Mumbai.` unless the author confirms which beats ran live. |
| LOW | 2 | `pitwall-sim.webm` is 1280x720 upscaled to 1920x1080 next to crisp rendered cards. | Letterbox at 1440x810 with the blurred fill used on shot 1, or accept the softness. |
| LOW | 7 | JSON key order differs from the log (`heading_deg` first in the log). | Print `"arguments": {"heading_deg": 0, "distance_m": 0.2}` to match the record exactly. |
| LOW | 10 | 174 wpm over the densest frame (arrow, highlight, quote card, safety line in 10 s). | Move the quote card to 1:56 and the safety line to 2:01; or lengthen the shot by the 2 s saved from shot 13 if shot 13 is kept at one still. |
| LOW | 3, 5, 8, 11 | Sound-off density: 10+ lines of 26-30 px text on a 1080p frame read from a laptop in a judging room. | Shot 5: show the two choice option sets only while their row is current, then collapse them to a count (`5 options`). Shot 11: drop the footnote's second sentence to the VO only, as the script's own fallback already suggests. |
| LOW | 11 VO | "Nova Pro on the same question" while the latency columns compare three questions against one. | VO: `Nova Pro on the grounding question alone: seven hundred ninety seven median, a four second tail over Wi-Fi, thirteen cents per thousand decisions.` |

## What is right and should not be touched

- Shots 5, 6, 7: the decision is stated better than any other entry I would expect to see; the
  typed question names, the option sets, the threshold ruler and one real answer with its
  latency are exactly what the rubric's "effective use of Decider 2B" asks for.
- Shot 11: the measured 2B-vs-Bedrock table is the bonus the rubric names, with the fair
  footnote that the tail is the network and not the model.
- Shot 14: URL, both tags, the safety line, 9 s hold. Done.
- The honesty-label system itself. It is the reason most of the findings above are wording
  changes rather than reshoots.
