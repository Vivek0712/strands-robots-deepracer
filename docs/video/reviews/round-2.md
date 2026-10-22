# Round 2 review: SCRIPT.md v2 and STORYBOARD.md v2, judge and editor

Reviewer stance: both hats. The Gate 2 judge reads the shot table and the VO as the video it
will become (sound on, then sound off); the editor checks the renderer shot list against the
real assets and fonts. Date: 2026-10-22. Inputs: `docs/video/SCRIPT.md` v2 (shot table,
timing table, read-through copy, "Shot list for the renderer"), `docs/video/STORYBOARD.md` v2,
`docs/video/ASSETS.md`, `docs/video/reviews/round-1-judge.md`, `round-1-editor.md`, the
hackathon brief, and the fact sources: `docs/results/decider-text-questions-2026-10-22.md`,
`docs/results/beats-car-2026-10-15-person-gate/README.md`, `docs/dev/CONTRACTS.md` section 7,
`docs/video/build/clips/real-decider-transcript.txt`, `docs/video/build/clips/pattern-demo.txt`,
plus `patterns/strands/tool_call_intervention.py`, `frame_intervention.py`, `README.md`,
`portal/backend/narrator.py`, `Makefile`, `hackathon/SUBMISSION.md`, `docs/article/article.md`,
`docs/article/FACTS.md`, `docs/media/MANIFEST.md`, `docs/article/img/MANIFEST.md`, and
`docs/video/render/README.md`, `compose.py`, `draw.py`.

Method, so the numbers below can be reproduced: text widths were measured with Pillow against
`/System/Library/Fonts/HelveticaNeue.ttc` (index 0 Regular, 1 Bold, 10 Medium, 11 Medium
Italic) and `/System/Library/Fonts/Menlo.ttc` (index 0). The webm frames at 2.5, 2.7, 2.88,
2.92, 3.0, 3.2 and 3.5 s were extracted with ffmpeg; the 3.2 s frame was cropped and scaled
exactly as the shot list says (source 0..910, 40..720, scale 1.59, anchored left) and the
stated pointer boxes were drawn on it and looked at. The same was done for
`fig-portal-stage.png` (shot 10), `fig-deepracer-strands.png` cropped and scaled as shot 3
says, and `fig-architecture.png` scaled as shot 4 says. Pacing was recomputed at 150 wpm plus
0.35 s per sentence from the read-through copy. Nothing outside this file was changed.

## 1. Round-1 findings: are they resolved in v2

Status: resolved / partly / not. "Evidence" is the v2 line in `SCRIPT.md` unless noted.

| # | Round 1 | Severity | Status | Evidence in v2 |
|---|---|---|---|---|
| J1 | Shot 1 title "just refused" over footage labelled UNGATED | HIGH | resolved | Lines 15-18 and 78: the hook is the labelled SIM Deny (`SIM, FAKE DECIDER, DRAWN FIGURE` from frame 0), the title is `This car can refuse an order.`, the real car is shot 1b with `REAL CAR, PHASE-1 RECORDING, UNGATED` (line 79). Shot 9's measured on-car Deny earns "can". |
| J2 | Shot 9 ungated footage with an animated gate blink | HIGH | resolved | Lines 19-22 and 87: the blink shot is cut; the slot is the on-car card (456 ms, p 0.9485, 681 to 727 ms, frames withheld), with the judge's VO verbatim (line 141). |
| J3 | Shot 8 `OPERATOR: no` truncated the auto-answer parenthetical | HIGH (honesty) | partly | Line 403 restores a parenthetical, but as a paraphrase: `OPERATOR: no (auto-answered by the test cell)`. The transcript (`real-decider-transcript.txt` line 10) reads `OPERATOR: no (this cell auto-answers False)`, and the storyboard (lines 398-399) promises "the OPERATOR line is verbatim with the auto-answer parenthetical". The judge's own round-1 wording caused this; the verbatim line is 43 characters and fits. See F4. |
| J4 | Shot 8 lower-third "Live proof" on a rendered replay | MED (honesty) | resolved | Line 86: `Recorded run, 2026-10-22: the real decider judges Nova Pro`. |
| J5 | Shot 10 VO voices the fake 0.97 as a judgement; Judge badge on fake-stack frames | MED (honesty) | resolved | Line 88 VO: "a figure in the frame is row three, a Deny, and the rover says why"; line 71: badge hidden on 1, 1b, 2, 10, 13, 14; storyboard lines 604-612. |
| J6 | Shot 12 reason strings did not match `make pattern-demo` | MED | resolved | Line 90 and lines 505-515 quote `pattern-demo.txt` lines 7 to 9 verbatim (checked character by character, including the `\n    strands-decider serve` tail). |
| J7 | Shot 2 "The light went red" with no safety line until 2:00 | MED (honesty) | resolved | Line 80 VO: "The hop was refused."; footer `Physics stops the car.` / `The decider explains.` from frame 0 (lines 252-253). |
| J8 | Shot 11 `0 USD per 1000 decisions` dropped "marginal, after the laptop" | MED | resolved | Line 469: `0 USD marginal per 1000 decisions (after the laptop)`; the VO no longer makes the cost claim for the 2B at all. |
| J9 | Shot 4 at 18 s, 44 words | MED | resolved | Min 12.0 s, 27 words, three groups (line 82). |
| J10 | Shot 8 at 28 s, first turn duplicated | MED | resolved | First turn pre-shown dim, replay from `USER : Go.`, est. 23.8 s (lines 86, 409-411). |
| J11 | Row 7 footnote; "Shown live"; JSON key order; "same question" VO; density on 5 and 11 | LOW | resolved | Line 84 footnote 2; line 145 "Shown at"; line 360 `heading_deg` first; line 143 "on the grounding question alone"; option sets on the two choice rows only; shot 11 second footnote sentence dropped. |
| E1 | Shot 2 timed to a 0.6 s DENY window; circle on an empty frame; freeze on CONFIRM | Critical | resolved | Lines 230-231 and 251: in at webm 2.5 s, freeze at 3.2 s. Verified on the extracted frames: 2.5 s is PROCEED "path clear (p=0.931)", 2.7 s the figure is in, DENY lands between 2.88 and 2.92 s, 3.2 s shows DENY, `LED RED` and the thought "I stopped because the decider said: person in frame (p=0.97)", 3.5 s has moved on to "go fast for 3 seconds". The +0.4 pulse and the 3.2 s freeze are right. |
| E2 | VO longer than picture on seven shots | Critical | resolved | Durations are auto with minimums; 345 words; recomputed below, every shot's picture is at least VO start + VO length + 0.5 s and the estimates in the timing table match mine to 0.05 s. |
| E3 | GIF pillarbox: crop, blur fill, 12 to 30 fps | High | resolved | Lines 241-243: crop 217..422, 3x to 618x1080 at x 651, blur 24 px at 35 percent, `minterpolate=mi_mode=blend`. |
| E4 | White title on a bright blur with no plate | High | resolved | The title now sits in the bg column of shot 1 (no footage under it); 1b's caption is on a plate; the blur is at 35 percent. Rule written into the storyboard (line 41). |
| E5 | `fig-deepracer-strands.png` baked title collision, doubled leader lines, 15 px callout text | High | resolved | Lines 262-275: crop y 100..900, layers from the HTML, no extra lines, seven 30 px label plates. All seven stated callout boxes land on the baked boxes to within 2 px (checked on the composed frame). One residual: see F13 (plate opacity over the baked header). |
| E6 | Shot 5 reveal faster than reading | High | partly | Rows every 2.5 s, option sets only on the choice rows, a `noul` key line (lines 304-325). This is the editor's own round-1 compromise, but the storyboard (lines 86-88) now states a rule, "nothing new appears faster than 3 words per second plus 1 s", that shot 5 (12-word rows at 2.5 s) and shot 6 (10-word bands at 2.5 s) do not meet. See F9. |
| E7 | Shot 6 prose bands | High | resolved, two residuals | Chips instead of prose (lines 333-341). Residuals: the GUIDE chip row overflows the band and row 5 `unclear` is missing from the DENY chips (F5). |
| E8 | Shot 11 bars overflow the frame | High | resolved | 1500 ms = 280 px; the 4069 ms bar is 984..1744 (line 471), inside the column; dotted budget line at 376 and 1264. |
| E9 | Shot 12 code does not fit a 576 px panel; 6 px terminal type | High | resolved | Two-row layout (lines 484-516); the model line measures 986 px at Menlo 28 in a 1208 px panel; the terminal is Menlo 24 at full width, 10 wrapped lines. |
| E10 | Fade to black runs past the picture end | High | resolved | Line 540: fade over the last 0.5 s of shot 14; picture end 2:48.6 (line 117). |
| E11 | No sound plan beyond the VO | High | not applied, by decision | Lines 52-53 and storyboard 16-18: no licensed bed, no room tone; mitigated by keeping every VO gap at or under 1.5 s (recomputed: longest 1.5 s into shots 5; 1.35 s into 8 and 14). Acceptable for a 2:49 explainer; the renderer has `--music` if a bed is cleared later. |
| E12 | Badge overlaps content on 4, 8, 11 | Medium | changed, now broken differently | Badges have plates and per-shot positions (line 226 and per shot), but the plates are narrower than their text (F1). |
| E13 | Honesty labels 24 px | Medium | resolved | 28 px everywhere (line 65), but the hard-coded x starts put five of them past the plate or the safe margin (F7). |
| E14 | Orange pointers on portal frames | Medium | resolved | Cyan on 1, 2, 10; red only for LED and DENY (storyboard lines 43-47). |
| E15 | Shot 10 caption on the wordmark; `92 ms` highlighted | Medium | resolved | Caption plate at top-centre 754..1250 (lands in the empty header stretch; checked); `92 ms` not marked (line 454). |
| E16 | Shot 7 arrow to the wrong evidence | Medium | resolved in intent, collides in geometry | Bracket joins `20 centimetres.` and `0.2` (line 374-376); see F6 for the collision. |
| E17 | Shot 8 label line 5 wraps | Medium | resolved | `5 Scripted operator: no. The agent asks,` measures 536 px at Regular 30 in a 674 px column. |
| E18 | Shot 13 at 1.5 s per still | Medium | resolved | 2.0 s each (line 524-527). |
| E19 | `draw.py` disagrees with the storyboard | Medium | documented, not fixed | Storyboard lines 20-26: `SAFE_Y = 72` adopted, palette stays the storyboard's; `draw.py` untouched (out of scope). Still true: `draw.py` carries `#4cc9f0`, `#ff7a1a`, `#f3f4f6`, `#8b8f98`. |
| E20 | Dips start on the VO | Low | resolved | VO at +0.4 on shots 3 and 14 (lines 281, 541). |
| E21 | Shot 14 hierarchy | Low | resolved | 56 / 48 / 30 / 32, author line above the tags (lines 534-538). |
| E22 | Checklist "no face other than the author's" | Low | resolved | Storyboard lines 615-616. |
| E23 | `noul` key | Low | resolved | Line 306. |
| E24 | SRT sidecar | Low | resolved | Storyboard lines 617-619; the renderer writes `<out>.srt` from the VO text. |

Net: both Criticals and nine of ten editor Highs are applied; all three judge Highs are
applied, one of them (J3) with a paraphrase where a verbatim line was promised. The remaining
honesty item is small and the fix is one string.

## 2. Fact check, every number and quote in the v2 VO and on-screen text

| # | Shot | Claim | Verdict | Source |
|---|---|---|---|---|
| 1 | 1 | `This car can refuse an order.` over the SIM Deny; label `SIM, FAKE DECIDER, DRAWN FIGURE` | PASS | "can" is earned by shot 9 (`beats-car-2026-10-15-person-gate/README.md` line 18, denied in 456 ms). The label is on frame 0. |
| 2 | 1 | webm in 2.5 s, figure at +0.2, DENY and `LED RED` at +0.4, freeze at 3.2 s | PASS | Extracted frames: 2.5 PROCEED clear; 2.7 figure in; DENY between 2.88 and 2.92; 3.2 DENY + LED RED + the stop thought. `ASSETS.md` says 3.0 for DENY; the frames say 2.9. The script is right. |
| 3 | 1b | `A stock AWS DeepRacer` / `REAL CAR, PHASE-1 RECORDING, UNGATED`, 4 s, content x 217..422 | PASS | `docs/media/MANIFEST.md` line 7; `ASSETS.md` 2.1. |
| 4 | 2 | `FRAME CLASS person_in_frame`, `PROBABILITY 0.97`, DENY word, red LED | PASS (sim, labelled) | The 3.2 s frame; `harness/fake_decider.py` line 12 (constant 0.97). Never spoken as a judgement. |
| 5 | 2 | Footer `Physics stops the car.` / `The decider explains.` | PASS | Exact wording per `CLAUDE.md` and the brief. |
| 6 | 2 VO | "A person in the frame." | PASS, note | The figure is drawn and labelled; shot 10 says "a figure". Consistent wording is better (F15). |
| 7 | 3 | `Driven as a Strands robot`; seven callouts Decider, strands-robots, deadman, Harness, Agents, Bidi, Box | PASS | `docs/article/img/MANIFEST.md` line 50; the baked callout headers match. |
| 8 | 3 | `Vivek Raja, AWS AI Hero` | PASS | `docs/article/article.md` line 14. |
| 9 | 3, badge | `Agent: Amazon Nova Pro on Bedrock` / `Judge: Strands Decider 2B, local` on 3 to 9, 11, 12 | PASS | `real-decider-transcript.txt` line 1 (`us.amazon.nova-pro-v1:0`, `strands-decider-2B-qwen3.5-v1-2610`); shot 9's judge was the booth 2B on the car (`beats-car...` line 4). |
| 10 | 3 VO | "A Strands agent on Amazon Bedrock turns my words into bounded hops. Before each hop, a local Strands Decider two B judges the command and the frame." | PASS | Brief; `CONTRACTS.md` section 7 (two requests per drive). |
| 11 | 4 | Five label lines; `5 On-car deadman: stops without the laptop` | PASS | `docs/article/img/MANIFEST.md` line 17 (300 ms rule, measured 278 ms). |
| 12 | 4 VO | "A Strands intervention handler asks the decider before the tool runs." | PASS | `tool_call_intervention.py` `before_tool_call`. |
| 13 | 5 | All five question strings and both option sets | PASS, verbatim | `QUESTIONS` in `tool_call_intervention.py` and `FRAME_QUESTIONS` in `frame_intervention.py` (printed and compared). |
| 14 | 5 | `POST /v1/systemone`, `Request 2: the frame (480x360 JPEG)`, `noul = yes/no as a probability, choice = one of a set` | PASS | `CONTRACTS.md` section 7; `_client.py`. |
| 15 | 6 | DENY rows 1-6, GUIDE rows 7-11, CONFIRM row 12 `0.35 <= p < 0.65`, PROCEED row 13; `YES 0.65` `NO 0.35` `budget 1.5 s`; "thirteen rows" | PASS | `CONTRACTS.md` section 7 table; `gate.py` lines 94-95. |
| 16 | 6 | DENY chips `decider down` `late` `no frame` `person` `off surface` `"stop"` | PASS but incomplete | Rows 1 (unreachable, timeout), 2, 3, 4, 6 are covered; row 5 (`unclear` with p >= 0.65, "cannot see clearly") has no chip. F5. |
| 17 | 6 | Footnotes: never fails open; row 7 Confirm on the car, Guide in the library | PASS | `CONTRACTS.md` row 7 and "Never fail open". |
| 18 | 7 | State keys `conversation`, `command{tool, arguments}`, `envelope`, `deterministic_check: "ok"`; `"user: Move forward 20 centimetres."`; `{"heading_deg": 0, "distance_m": 0.2}`; `distance_m <= 0.5 per call, \|heading_deg\| <= 90` | PASS | `MotionGate.state_for` (lines 251-261), `Envelope.describe` (line 158), transcript gate log row 1. |
| 19 | 7 | `0.948`, `0.907`, `move_forward 0.959`, PROCEED, `583 ms`; VO "zero point nine five", "zero point nine one", "five hundred eighty three" | PASS | Gate log row 1 (`latency_ms: 583.3`, reason "inside envelope p=0.95, grounded p=0.91"). |
| 20 | 8 | Lines 00-05 (model names, first turn), `USER : Go.` | PASS | Transcript lines 3-6, 8. `centimeters` is the transcript's spelling. |
| 21 | 8 | Gate rows: `"distance_m": 2`, `"distance_m 2 > 0.5"`, `0.18`, `Guide`; `0.5`, `0.404`, `Confirm`, `"unclear: inside=0.88 grounded=0.40"` | PASS | Transcript gate log rows 2 and 3 (keys omitted, values verbatim). |
| 22 | 8 | `CONFIRM (operator asked): ... Allow it?` | PASS | Transcript line 9, wrapped. |
| 23 | 8 | `OPERATOR: no (auto-answered by the test cell)` | FAIL as "verbatim" | Transcript line 10: `OPERATOR: no (this cell auto-answers False)`. Meaning preserved, text altered while the storyboard says verbatim. F4. |
| 24 | 8 | `AGENT: The move could not be completed ... clarification.` | PASS, note | Transcript line 11 with the `<thinking>...</thinking>` block dropped and no marker (v1 had an ellipsis). F14. |
| 25 | 8 VO | "Nova Pro guesses two metres", "re-plans half a metre", "grounded reads zero point four zero", "the scripted operator says no, and the agent asks me instead of driving" | PASS | Rows 2 and 3; the agent line. |
| 26 | 8 | Lower-third `Recorded run, 2026-10-22: the real decider judges Nova Pro`; label `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO` | PASS | Transcript header. |
| 27 | 9 | `456 ms`, `person_in_frame p = 0.9485`, `whole gate 681 to 727 ms per hop; no motion event after the deny`, `On the car, 2026-10-15`, frames withheld | PASS | `beats-car-2026-10-15-person-gate/README.md` lines 18-20 and 24. |
| 28 | 9 VO | "the same gate" | PASS, note | On the car the gate is `src/deepracer_agent/gate.py`; `CONTRACTS.md` section 7 says the drop-in asks the same five questions with the same row table. Row 3 is identical. |
| 29 | 10 | `Row 3: person in frame -> Deny`; `"Someone is in front of me. I stopped."`; `Pit Wall, the simulated car`; `92 ms` unmarked | PASS | `CONTRACTS.md` row 3; `portal/backend/narrator.py` line 21; `img/MANIFEST.md` line 20. |
| 30 | 11 | Title `24 cases, 72 timed calls, Apple M4 Pro`; `462 ms p50`, `498 ms p95`, `0 of 72`, `0 USD marginal per 1000 decisions (after the laptop)` | PASS | Results doc Setup, Method and the comparison table. |
| 31 | 11 | `797 ms p50`, `4069 ms p95`, `31 of 72`, `0.13 USD per 1000 decisions`; footnote `391 ms p50. The tail is the network.` | PASS | Same table (0.1318; provider-side 391; "the path to us-east-1"). |
| 32 | 11 VO | "none over the one and a half second budget", "on the grounding question alone", "a four second tail over Wi-Fi", "thirteen cents per thousand decisions" | PASS | 0 of 72; `args_grounded` only; p95 4069 over Wi-Fi; 0.1318. |
| 33 | 12 | File tree; `Decider(timeout=1.5)`, `BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1")`, `interventions=[MotionGate(decider)]` | PASS | `patterns/strands/README.md` Wiring block (there as one expression); `ls patterns/strands/`. |
| 34 | 12 | Terminal rows and header `make pattern-demo, against the fake decider (a script, not the model)`; label `FAKE DECIDER, STDOUT VERBATIM`; VO "runs it offline against a fake decider" | PASS | `pattern-demo.txt` lines 1-2, 7-9; `Makefile` lines 73-74. |
| 35 | 12 | Footer `github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands` | PASS | `SUBMISSION.md` Links. |
| 36 | 13 | `AWS Community Day Mumbai, 17 October 2026`; VO "Shown at" | PASS | `article.md` line 28; `FACTS.md` line 28 ("live" dropped as flagged). |
| 37 | 14 | Safety line, URL, `Vivek Raja, AWS AI Hero  \|  Article on AWS Builder Center`, `#strands-decider-2b   #guardrails` | PASS | `SUBMISSION.md` Tags and Links. |
| 38 | header | "345 words", "picture ends at 2:48.6", "last word 2:46.5" | PASS | Recomputed: 345 words, 168.6 s, 166.5 s. |

Decider-as-safety-layer scan: no sentence calls the decider the safety layer. The safety line
appears in the exact wording on shots 2 (footer), 10 and 14, and the baked version on shot 3's
figure and in the webm crop's own footer. Shot 2 no longer says the light protected anyone.

## 3. Fresh eyes on v2

### The hook

Frame 0 is the fake console at PROCEED with the honesty label already on; DENY and the red LED
land at 0.4 s; the freeze at 0.7 s is the frame with the stop thought in it; the title fades in
at 1.0 s. The first second lands: the thumbnail frame is a red DENY, and the first word a judge
can read is the SIM label, which is the honesty posture doing the work. The right column text
(`This car` / `can refuse` / `an order.`, Bold 56) measures 213, 281 and 241 px in a 324 px
column, so it fits with margin and is visible from 1.3 s to 4.2 s. Six words at 3 words per
second plus 1 s needs 3.0 s and gets 2.9 s, with the VO saying the same words; readable.

The cut from the DENY freeze (shot 1) to the car (1b) to the same DENY freeze (shot 2) is the
right order. One honesty note: the car in shot 1 is a simulated one; the real car is labelled
UNGATED; shot 9 is where the two meet. Nothing to change.

### Pacing, recomputed (150 wpm plus 0.35 s per sentence)

| Shot | Words | Sentences | VO est. | Script est. | Picture (auto, min) | Script | wpm on picture | Gap into shot |
|---|---|---|---|---|---|---|---|---|
| 1 | 6 | 1 | 2.75 | 2.8 | 4.25 (4.0) | 4.2 | 85 | 1.00 |
| 1b | 6 | 1 | 2.75 | 2.8 | 4.00 fixed | 4.0 | 90 | 1.00 |
| 2 | 12 | 3 | 5.85 | 5.8 | 6.65 (4.0) | 6.6 | 108 | 1.05 |
| 3 | 31 | 3 | 13.45 | 13.4 | 14.35 (14.0) | 14.3 | 130 | 0.90 |
| 4 | 27 | 3 | 11.85 | 11.8 | 12.65 (12.0) | 12.6 | 128 | 0.80 |
| 5 | 31 | 5 | 14.15 | 14.2 | 15.65 (15.0) | 15.7 | 119 | 1.50 |
| 6 | 21 | 3 | 9.45 | 9.4 | 10.50 (10.5) | 10.5 | 120 | 0.80 |
| 7 | 19 | 3 | 8.65 | 8.7 | 10.00 (10.0) | 10.0 | 114 | 1.05 |
| 8 | 54 | 4 | 23.00 | 23.0 | 23.80 (18.0) | 23.8 | 136 | 1.35 |
| 9 | 28 | 2 | 11.90 | 11.9 | 12.70 (6.0) | 12.7 | 132 | 0.80 |
| 10 | 25 | 3 | 11.05 | 11.1 | 11.85 (10.0) | 11.9 | 127 | 0.80 |
| 11 | 42 | 2 | 17.50 | 17.5 | 18.30 (16.0) | 18.3 | 138 | 0.80 |
| 12 | 26 | 2 | 11.10 | 11.1 | 11.90 (11.0) | 11.9 | 131 | 0.80 |
| 13 | 6 | 1 | 2.75 | 2.8 | 4.00 fixed | 4.0 | 90 | 0.80 |
| 14 | 11 | 3 | 5.45 | 5.5 | 8.00 (8.0) | 8.0 | 82 | 1.35 |

Totals: 345 words, picture ends 168.6 s (2:48.6), last word 166.5 s. Every shot's picture is at
least VO start + VO length + 0.5 s; the fastest read is 138 wpm (shot 11); no VO gap exceeds
1.5 s. The script's timing table matches to 0.05 s. Two renderer facts change this slightly:
`docs/video/render` pads auto shots by 0.4 s, not 0.5 s (its README, Pipeline step 2), and its
dip transitions overlap the two shots, so the real timeline would be about 2:46.5 with the same
list. Under 3:00 either way; pick one number (F8).

### Reveal pace (3 words per second plus 1 s)

- Shot 3: labels of 3 to 5 words every 1.8 s (`strands-robots on the drive` needs 2.7 s). Over
  the rule by up to 0.9 s, but the previous label stays. Acceptable.
- Shot 4: lines 1-2 (10 words) get 4.2 s; line 3 (6 words) gets 4.0 s; lines 4-5 (11 words) get
  4.1 s. Meets the rule.
- Shot 5: row 2 is 12 words plus the tag and needs 5.0 s; row 3 is 10 words plus five options
  and needs 5.3 s; rows arrive every 2.5 s. Does not meet the rule the storyboard states.
- Shot 6: the DENY band is about 10 words of chips and needs 4.3 s; bands arrive every 2.5 s.
  Does not meet the rule.
- Shots 7, 9, 11: bars, lines and counters at 1.2 to 4 s intervals for 1 to 12 words. Meets it.

The round-1 editor accepted 2.5 s on shot 5 as a trade ("a viewer reads two rows fully; the VO
names all five"). That trade is still sound; what is wrong is the storyboard's sentence that
claims the rule is met. See F9 for the two options.

### Text wider than its plate or column, measured

Widths from Pillow with the real faces. Menlo advances come out hinted to whole pixels:
Menlo 22 = 13.0, 24 = 14.0, 26 = 16.0, 28 = 17.0, 30 = 18.0 px per character, not the 14.45,
15.65 and 16.85 the shot list used. That matters for every coordinate derived from a character
index (F2).

| Shot | Text | Face, size | Width | Starts | Ends | Limit | Result |
|---|---|---|---|---|---|---|---|
| 5, 7, 9, 11, 12 | `Agent: Amazon Nova Pro on Bedrock` (standard badge) | Menlo 22 | 429 | 1496 | 1925 | plate 1840, frame 1920 | OVER by 85 (plate), 5 px off the frame |
| 5, 7, 9, 11, 12 | `Judge: Strands Decider 2B, local` | Menlo 22 | 416 | 1496 | 1912 | 1840 | OVER by 72 |
| 4 | same badge, plate 1392..1840 | Menlo 22 | 429 | 1408 | 1837 | safe 1824 | OVER by 13 |
| 8 | same badge, plate 1150..1510 | Menlo 22 | 429 | 1166 | 1595 | 1510 | OVER by 85 |
| 1b | `A stock AWS DeepRacer` | Medium 40 | 457 | 96 | 553 | plate 560 minus 16 | OVER by 9 |
| 1b | `REAL CAR, PHASE-1 RECORDING, UNGATED` | Menlo 28 | 612 | 1216 | 1828 | safe 1824 | OVER by 4 |
| 7, 8 | `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO` | Menlo 28 | 748 | 1086 | 1834 | safe 1824 | OVER by 10 |
| 9 | `MEASURED ON THE CAR 2026-10-15, REAL DECIDER` | Menlo 28 | 748 | 1086 | 1834 | 1824 | OVER by 10 |
| 10 | `SIM, FAKE DECIDER, DRAWN FIGURE` | Menlo 28 | 527 | 1316 | 1843 | plate 1840 | OVER by 3 (19 past safe) |
| 12 | `FAKE DECIDER, STDOUT VERBATIM` | Menlo 28 | 493 | 1346 | 1839 | safe 1824 | OVER by 15 |
| 10 | `Row 3: person in frame -> Deny` | Medium 36 | 527 | 770 | 1297 | plate 1250 minus 16 | OVER by 63 |
| 12 | `github.com/Vivek0712/.../patterns/strands` | Menlo 26 | 1152 | 112 | 1264 | plate 1230 minus 16 | OVER by 50 |
| 7 | `  "arguments": {"heading_deg": 0, "distance_m": 0.2}},` | Menlo 28 | 918 | 96 | 1014 | bracket at x 965 | the bracket crosses `}},` |
| 6 | GUIDE chips (Menlo 26, 8 px padding, 12 px gaps) | | | 520 | 1596 | band edge 1560 | OVER by 36 |
| 6 | DENY chips as written | | | 520 | 1428 | 1560 | fits; with `unclear` added, 1568, OVER by 8 |

Everything else fits: shot 1 title lines (213 to 281 px in 324); shot 3 title 780 px; the
longest callout label `strands-robots on the drive` 380 px, well short of the car; shot 4 stack
lines up to 420 px in 432; shot 5 title 1066 px, questions up to 957 px (row 2 ends at 1517,
the `#guardrails` tag starts at 1681); shot 6 title 1674 px, footnote 1011 px; shot 7 values
end at 1821; shot 8 terminal lines up to 864 px in a 1008 px column, stack lines up to 595 px,
lower-third text 895 px in a 918 px plate; shot 9 lines 672 to 1167 px centred; shot 10 quote
789 px in 944, safety line 1507 px; shot 11 title 1322 px (ends 1418, badge plate at 1480),
headers 695 and 760 px, cost line 748 px in an 840 px column, footnote 713 px; shot 12 title 835
px, model line 986 px, terminal line 00 at 118 characters 1652 px (ends 1748); shot 14 URL 1305
px, safety 1170 px, author 771 px, tags 627 px.

### Pointer coordinates against the real frames

Five targets checked by drawing the stated boxes on the composed frames and looking at them.

| Shot | Pointer | Stated | On the frame | Verdict |
|---|---|---|---|---|
| 1 | red pulse `1310..1432, 8..48` | around `LED RED` | the label sits inside the box with 6 to 10 px of air | correct |
| 2 | circle centre (405, 370) r 190 | around the figure | encloses head, arms and torso; the legs run below (figure is 740 px tall) | correct for "around the figure"; a 230 px radius would take the hips too |
| 2 | boxes `40..310, 545..625` and `615..770, 545..625`; arrow (557, 484) to (685, 548); red `825..1107, 135..262` | the two live-view chips, the DENY word | the boxes sit exactly on `FRAME CLASS person_in_frame` and `PROBABILITY 0.97`; the arrow leaves the circle's lower right and meets the probability chip's top edge; the DENY box frames the word with 8 px of air | correct |
| 3 | seven callout boxes | the baked boxes after the crop and 0.9 scale | all seven match the baked boxes to within 2 px | correct |
| 4 | R1 to R5 and the deadman sub-box; arrow (752, 464) to (960, 464) | the figure's blocks at 0.8 scale | R1 = Bedrock, R2 = Strands Agents, R3 = DeciderGate + Decider 2B, R4 = strands-robots, R5 = the DeepRacer, the red box = the deadman node; the arrow runs on the figure's own `commands 20 Hz ws:9090` line | correct |
| 10 | caption plate `754..1250, 8..62`; arrow (790, 440) to (1232, 352); cyan `1234..1772, 314..388`; red `1232..1540, 158..262`; quote plate `150..1110, 560..636` | the empty header stretch; figure's right arm to the CLASS chip; CLASS + PROBABILITY chips; DENY word; the live view | the plate is in the empty header (tabs end at 740, `run OPEN` starts at 1770); the arrow starts at the arm's end and meets the CLASS chip's left edge; the cyan box frames both chips and stops before LATENCY; the DENY box frames the word; the quote plate covers the figure's hips, nothing else | correct; see F6 for the lower-third plate |

### Honesty labels

Every fake-stack frame (1, 2, 10) carries `SIM, FAKE DECIDER, DRAWN FIGURE` and no judge badge;
the webm crop also keeps the UI's own `FAKE CONSOLE` tag in frame. The car (1b) carries
`REAL CAR, PHASE-1 RECORDING, UNGATED`. Shots 7 and 8 carry the recorded-run label with the
date, 9 the two-line on-car label with the withheld-frames reason, 11 `MEASURED 2026-10-22`,
12 `FAKE DECIDER, STDOUT VERBATIM`. The 0.97 is never spoken as a result. The one wording gap is
shot 8's OPERATOR line (F4). The label positions overflow the safe margin on five shots (F7),
which is geometry, not honesty.

### The ending card

Safety line Bold 56, URL Menlo 48 cyan (1305 px, centred), author line above the tags, both
tags, the Strands mark inside the safe margin at bottom-right, a 1.0 s fade-in from +0.4, a
6.6 s hold with the URL on screen, fade over the last 0.5 s. The VO's "Repo and article below"
points at the description, which is where a judge will look. Nothing sits in the YouTube
caption band. Done; do not touch.

### Sound off

All fifteen shots carry their own text. Density is highest on 5, 6, 8 and 12, as in round 1,
but every element there is at 24 px or larger and the argument of each shot is in a title or a
numbered label, so a muted judge still gets: the five questions, the four verdicts, the one
real answer, the recorded run's five steps, the on-car numbers, the comparison, the file tree
and the path. The only sound-off casualties are the badge overflows (F1), which put the agent
and judge names half off the frame on five shots.

### Is the renderer shot list complete and unambiguous

Complete in coverage: every shot has a source or card, in and out times, every overlay has text,
font, size, position and an in time (out defaults to the shot end), every pointer has
coordinates and an in time, and every source asset exists:
`docs/results/portal/pitwall-sim.webm`, `docs/media/car-hop.gif`,
`docs/article/img/fig-deepracer-strands.png` and its `svg/fig-deepracer-strands.html`,
`fig-architecture.png`, `fig-portal-stage.png`, `event-speaker-with-car.jpg`, `event-hall.jpg`,
`cover.png`, `docs/talk/deck/assets/logos/strands-mark.svg`,
`docs/video/build/clips/real-decider-transcript.txt` and `pattern-demo.txt`.

Where it is ambiguous or not yet renderable:

- The shot list describes primitives that `docs/video/render` does not have (its schema is in
  `render/README.md` and `compose.py` `KIND_KEYS`): a source crop rectangle on a clip, a blur
  fill, `minterpolate`, per-region brightness and opacity, a two-pulse rectangle, probability
  bars that fill, counters that count to a value with units, chips, a ruler with a shaded band,
  a dotted line, a bracket with ticks, plates with explicit boxes, two-line lower-thirds, and
  the eight shot-3 layers rendered from HTML. There is no `docs/video/shots.yaml` yet. The
  renderer does have `terminal` and `json` kinds with match-based highlights, `card`, `still`,
  `clip` (start, end, fit, zoom), `arrow`, `box`, `circle`, `underline`, per-overlay `font`,
  `size`, `color`, `pos` as `[x, y]`, and `dip_to_black`. So shots 8 and 12's terminals, shot
  7's JSON, the lower-thirds, captions and the pointers can be fed straight in; the rest needs
  either a renderer extension or pre-rendered inputs (F3).
- Derived assets that do not exist in `docs/video/build/clips/`: the hook clip (webm 2.5 to
  3.2 s cropped to 1447x1080 and held), the blur-filled car clip (the existing
  `car-hop-1080p.mp4` is padded on black, which the script itself says not to use), the seven
  callout layers plus base for shot 3, and a 96 px raster of the Strands mark (the existing
  `svg-strands-mark.png` is a 1920x1080 canvas with a 290 px mark). `rsvg-convert` is not
  installed; the renderer falls back to `qlmanage`, which the script does not mention.
- Shot 3: the label plate width is not stated (the height is 44 px, the text x is plate + 12);
  the renderer needs a rule such as "text width + 24".
- Shot 5: the type chip's padding is not stated (the storyboard gives 8 px for row chips on
  shot 6 and 10 px for verdict chips; nothing for the `noul` / `choice` chips).
- Shot 8: "the cursor stops while each highlighted number is spoken" is a rule with no numbers;
  every block start time in the list assumes no pauses (F4).
- Shot 10: at +7.5 the image dims to 40 percent; whether the caption plate, quote card and the
  three pointers stay over the dimmed image or go is not stated. Say "all overlays stay".
- Shot 7: the storyboard says the bars are 440 px for 1.0; the shot list says 380 px (and its
  bar coordinates are built on 380). The shot list is right; fix the storyboard line.
- The `auto` padding is 0.5 s in the script and 0.4 s in the renderer (F8).

## 4. Scores (1 to 5), round 1 to round 2

| Criterion | R1 | R2 | Delta | One line |
|---|---|---|---|---|
| Hook, first 10 s | 3 | 4 | +1 | Red DENY at 0.4 s, honest label at 0.0, a true title; held back from 5 only because the first car on screen is simulated and the real one is UNGATED, which the labels say and shot 9 repairs 100 s later. |
| What the agent is, by 0:30 | 5 | 5 | 0 | Shot 3 ends at 0:29.2 with the car, the agent model, the judge and the seven pieces named. |
| Can a judge state the 2B decision | 5 | 5 | 0 | Questions verbatim with types and option sets, the row table as chips, one real answer with latency. |
| Proof it works, labelled | 3 | 4 | +1 | Real decider and real Nova Pro on 7 and 8; the on-car Deny with its numbers on 9; still no footage of the gated car, and the card says why. |
| Use of the measured numbers | 4 | 5 | +1 | Every number on shot 11 is sourced and qualified; the VO compares the grounding question alone. |
| Reusable pattern visibility | 4 | 5 | +1 | Upstream file names, the wiring, stdout verbatim with its reason strings, the path in the lower third. |
| Originality cues | 4 | 4 | 0 | Unchanged: a local 2B judging a hosted frontier model, measured both ways, on a stock DeepRacer. |
| Pacing | 3 | 4 | +1 | VO-first with minimums; 345 words; fastest shot 138 wpm; shot 5 and 6 reveals still faster than the reading rule. |
| Sound-off legibility | 4 | 4 | 0 | Every shot carries its argument in text; the badge overflow on five shots and the overflowing honesty labels cost the point. |
| Ending | 5 | 5 | 0 | URL, tags, safety line, author line, 6.6 s hold, fade. |
| Total | 40 | 45 | +5 | |

## 5. Findings

Severity: HIGH breaks a frame or the build; MED a judge may notice or a label is not what it
claims; LOW polish. Coordinates are 1920x1080 frame units.

| Severity | Shot | Finding | Exact fix |
|---|---|---|---|
| HIGH | 4, 5, 7, 8, 9, 11, 12 | F1. The badge plate is narrower than its own text. `Agent: Amazon Nova Pro on Bedrock` is 429 px at Menlo 22; the standard plate `1480..1840` gives 328 px inside, so the line runs to x 1925, off the frame, on shots 5, 7, 9, 11, 12; on shot 4 it ends at 1837 (past the plate's padding and the safe margin); on shot 8 it ends at 1595 in a plate that stops at 1510. | Badge lines Menlo 20 (396 and 384 px). Standard plate `1400..1840, 72..130`, lines at (1416, 80) and (1416, 106), text ends at 1812. Shot 4: plate `1400..1840, 540..598`, lines at (1416, 548) and (1416, 574). Shot 8: plate `1150..1580, 400..458`, lines at (1166, 408) and (1166, 434). Shots 3 and 6 (plate `1284..1840`) are fine at 22 px; use 20 px there too so the badge is one size. |
| HIGH | 7, 8, 12 | F2. Every highlight box derived from a character index is off, because Pillow draws Menlo with hinted integer advances: 17.0 px at 28, 16.0 at 26, 14.0 at 24, not 16.85, 15.65, 14.45. Shot 12's boxes drift by up to 50 px (for example `"verdict": "Deny"` is drawn at 1537..1791 but the text sits at about 1496..1735, so the box covers the wrong half); shot 8's drift 10 to 20 px (`0.404` is at 848..928, box 828..914; the OPERATOR line ends at 816, box 804); shot 7's bracket targets drift 5 to 8 px. | Specify all terminal and code highlights by match string, which the renderer supports (`terminal.highlight: [{match, color}]`, `json.reveal: [{match, color, at}]`), and let it compute the box from the font; keep the listed coordinates as a reference only. In the storyboard's "Type" section replace the three constants with Menlo 22 = 13, 24 = 14, 26 = 16, 28 = 17, 30 = 18 px per character (hinted). |
| HIGH | build | F3. The shot list is not an input the current renderer can take: no `docs/video/shots.yaml` exists, and the list uses primitives the renderer lacks (clip crop rectangle, blur fill, `minterpolate`, region brightness and opacity, a two-pulse rectangle, filling bars, counting counters, chips, the ruler, dotted lines, a bracket, boxed plates, two-line labels, HTML layers). Its `auto` padding is 0.4 s, its default title is 76 px and its palette is the old one. | Two routes, pick one and write it into `SCRIPT.md` under "Shot list for the renderer". (a) Pre-render: cut `build/clips/hook-deny-1447.mp4` (webm 2.5 to 3.2 s, `crop=910:680:0:40,scale=1447:1080`, last frame held to 7 s) and `build/clips/car-hop-blur-1080p.mp4` (the GIF crop over its own 24 px blur at 35 percent, `minterpolate=mi_mode=blend`, 30 fps) with ffmpeg; export `build/clips/fig-strands-layer-0.png` to `-7.png` from the HTML with Chrome headless (hide `.c`, `.dot`, `.lbl` by index); render the card shots 5, 6, 7 (right half), 9, 11, 12 row 1 and 14 as PNG frame sequences with a small Pillow script in `docs/video/render/cards.py`; feed the renderer `clip`, `still`, `terminal` and `json` kinds plus its own lower-thirds, captions and pointers. (b) Extend the renderer with those primitives. Either way set `auto_pad: 0.5` in the list and give every text overlay an explicit `font`, `size` and `[x, y]`, since the renderer's defaults differ from the storyboard. |
| MED | 8 | F4. Three things on the replay. (1) The OPERATOR highlight at +15.5 lands before the line exists: at 40 cps line 19 types from +15.95 to +17.07. (2) The AGENT block starts at +17.0, 0.07 s before line 19 finishes. (3) `OPERATOR: no (auto-answered by the test cell)` is a paraphrase of the transcript's `OPERATOR: no (this cell auto-answers False)` while the storyboard says the line is verbatim. Also "the cursor stops while each highlighted number is spoken" has no numbers and would push every later block. | Line 19: `OPERATOR: no (this cell auto-answers False)` (43 characters, fits). OPERATOR highlight and label line 5 at +17.1; AGENT block from +17.2; the VO reaches "The scripted operator says no" at about +17.4. Delete the pause rule; the highlight is the motion. Storyboard lines 398-399 then become true. |
| MED | 6 | F5. The DENY band says `rows 1-6` but its six chips cover rows 1, 1, 2, 3, 4 and 6; row 5 (`unclear` at p >= 0.65, "cannot see clearly") has no chip. And at Menlo 26 the GUIDE chip row ends at x 1596, past the band's edge at 1560 (36 px over); adding `unclear` puts the DENY row at 1568. | Row chips Menlo 24 (14 px per character), 8 px padding, 12 px gaps: DENY `decider down` `late` `no frame` `person` `off surface` `unclear` `"stop"` ends at 1460; GUIDE ends at 1474; CONFIRM at 1040. Update storyboard line 72 to 24 px. |
| MED | 7, 10 | F6. Two pointer collisions. Shot 7: the bracket's vertical at x 965 sits on top of `}},` (line 3 runs to x 1014), and the orange arrow from (975, 304) to (1336, 408) crosses the `inside_envelope` label (y 294..322) and clips the `args_grounded` label. Shot 10: the section lower-third plate (x 80..517, y 952..1008) covers the rover log's last line at y 990, `11:34:45.507 I stopped because the decider said: person in frame (p=0.97)`, which is the line the VO means by "the rover says why". | Shot 7: replace the bracket with two cyan 3 px underlines, `708..963` at y 282 (under `20 centimetres.`) and `912..963` at y 362 (under `0.2`), at +1.5; orange arrow from (963, 362) to (1336, 404) at +3.7 (it runs between the two labels). Shot 10: drop the section lower-third; the top-centre caption names the shot. Keep the honesty label where it is. |
| MED | 1b, 7, 8, 9, 10, 12 | F7. Honesty labels are placed by a hard x start, and five of them end past the safe margin or the plate: 1b ends at 1828, 7 and 8 at 1834, 9 at 1834, 10 at 1843 (past the plate), 12 at 1839. The storyboard rule (line 66) is "right-aligned, ending at x 1824". Shot 10's caption plate `754..1250` is 63 px short of its 527 px text, shot 12's lower-third plate `80..1230` is 50 px short of its 1152 px text, shot 1b's caption plate `80..560` is 9 px short. | Make the label rule the geometry: text right-aligned to end at x 1824, plate from (text start minus 16) to 1840. Shot 10 caption plate `754..1313, 8..62` (the header is empty to 1770). Shot 12 lower-third plate `80..1280, 952..1008` (the label plate starts at 1330). Shot 1b caption plate `80..585, 60..132`. |
| MED | all | F8. Two numbers for the same thing: the script pads auto shots by 0.5 s, the renderer by 0.4 s; the script treats a 0.3 s dip as the first 0.3 s of the receiving shot, the renderer's `dip_to_black` overlaps the two shots by 0.3 s. Net 0.1 s per auto shot and 0.6 s on the dips, about 2:46.5 instead of 2:48.6. Harmless to the limit, but the timing table will not match the render. | Set `auto_pad: 0.5` in the shot list (the renderer reads it from the top-level mapping) and note in the timing table that each dip shortens the timeline by 0.3 s. Then re-run `render check` and paste its start column into the table. |
| MED | 5, 6, storyboard | F9. Storyboard lines 86-88 state a reveal rule (3 words per second plus 1 s) that shots 5 and 6 do not meet: shot 5 rows of 10 to 12 words plus options at 2.5 s, shot 6 bands of about 10 chip words at 2.5 s. The round-1 trade (the VO names all five, a viewer reads two rows fully) is fine; the claim is not. | Either reword lines 86-88 to "shots 5 and 6 build faster than the reading rule on purpose: the VO carries the five questions and the four verdicts, the card is there to be paused on"; or slow both to 3.0 s (shot 5 rows at +1.0, +4.0, +7.0, +10.0, +13.0 with min 16.0; shot 6 bands at +0.5, +3.5, +6.5, +9.5 with min 11.5), which adds 2.0 s and puts the picture at about 2:50.6, still under the limit. I would reword, not slow. |
| LOW | 3 | F10. The seven callout label plates (60 percent) sit at the box's top edge minus 24, which is exactly over the baked small-caps header (`CAMERA: STRANDS DECIDER` at about y 215..230). At 60 percent the baked header bleeds through under the new label. | Draw the seven callout plates opaque (`#0b0b10` at 100 percent) so they replace the baked header cleanly, and state the plate width as text width + 24. |
| LOW | 8 | F11. The AGENT reply drops the transcript's `<thinking>...</thinking>` block with no marker (v1 had an ellipsis). The storyboard says every value is verbatim; a reader of the transcript will notice. | Line 20: `AGENT: (thinking omitted) The move could not be` / `  completed because the decider is unsure about it,` / `  despite it being within the allowed envelope.` / `  Please provide further instructions or` / `  clarification.` (five lines; the terminal ends at y 918, above the lower-third). |
| LOW | 2, 10 | F12. Shot 2 VO says "A person in the frame", shot 10 "a figure in the frame"; the frame is a drawn figure under a label that says so. | Shot 2 VO: `A figure in the frame. The hop was refused. Here is why.` (the reason string on screen still reads "person in frame"; the VO describes the picture). |
| LOW | 7, storyboard | F13. Storyboard line 361 says the bars are 440 px for 1.0; the shot list builds them on 380 px (`1340..1700` for 0.948). | Storyboard: "three bars (380 px for 1.0)". |
| LOW | 14 | F14. The Strands mark is to be "rendered at 96x96" from the SVG; `rsvg-convert` is absent and the renderer falls back to `qlmanage`, which is not mentioned anywhere. | Pre-render `build/clips/strands-mark-96.png` with Chrome headless (the ASSETS recipe, `<img width=96>`) and reference the PNG. |
| LOW | 12 | F15. "three lines of wiring" while seven lines are on screen (the README's one expression split by hand). | Panel header `three arguments of wiring` or `the wiring`, and the VO `three files with the upstream names, the wiring, and make pattern demo ...` (one word fewer). Optional. |
| LOW | 10 | F16. Whether the caption, quote card and pointers stay after the +7.5 dim is not stated. | Add "all overlays and pointers stay over the dimmed image" to the shot 10 entry. |
| LOW | 1, 2 | F17. The crop scaled by 1.59 is 1447x1081; one row over. | Scale to 1447x1080 (`scale=1447:1080`), or crop one source row. |

## 6. What is right and should not be touched

- The hook order (sim Deny, labelled car, back to the Deny with pointers) and the three-line
  title in the bg column: honest, red in the first second, readable.
- Shot 9's on-car card: four lines, the source path, the withheld-frames label, the judge's VO.
  It is the first number from the car itself and it is placed right after the recorded run.
- Shots 5, 6, 7 as the statement of the decision, and shot 11's two-column comparison with the
  qualifier on the cost line and the network footnote.
- Shot 12's verbatim stdout, including the `--port 8111` tail in the Deny row's error string:
  a judge who runs `make pattern-demo` will see the same text.
- The honesty-label system and the badge rule (hidden on fake-stack frames). All the findings
  above are geometry and one string; none is a reshoot.

## Verdict

Render: go with these fixes. The two Criticals and the honesty Highs from round 1 are applied.
Before the first draft render: F1 (badge plates), F2 (match-based highlights and the corrected
Menlo advances), F4 (shot 8's OPERATOR string and highlight time), F5 (shot 6 chips), F6 (the
two pointer collisions), F7 (label and plate widths). F3 is the build plan rather than a script
defect, but the draft cannot be produced until one of its two routes is chosen. Everything
else can be checked on the draft render's contact sheet.
