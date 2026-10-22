# Demo video script, v3: "This car can refuse an order"

Hackathon demo for the AWS Builder Center "Strands Decider 2B" hackathon. Hard limit 3:00.
Durations are "auto": the renderer sizes every shot's picture to its Polly audio (the shot's
own VO start offset plus the audio length plus 0.5 s), never below the minimum stated per shot.
Estimated with Amazon Polly generative Matthew at 176 words per minute (it ignores rate tags)
plus 0.35 s per sentence end, the picture ends at 2:51.8 and the last spoken word lands at
2:49.0 (ceiling 3:00; planned picture 2:52, audio by 2:49). Format 1920x1080, 30 fps. Voice-over for Amazon Polly
(generative voice, calm, one speaker, the author in the first person). Layout, colour and
type are in `STORYBOARD.md`; clip paths and timecodes come from `ASSETS.md`.

## Changes in v3

The author's verdict on the v2 render: the text and the narration run through where the
arguments and the probabilities are discussed; a judge wants the how and the why explained
neatly. v3 changes shots 3, 4, 5, 6, 7, 8 and 11 and leaves 1, 1b, 2, 9, 10, 12, 13 and 14 as
they were (shot 12 only has its minimum trimmed to 10.7 s).

1. Shots 5, 6, 7, 8 and 11 now show one idea at a time, each reveal keyed with an `at` time to
   the VO clause that names it (clause times computed at 176 wpm plus 0.35 s per sentence end;
   the renderer should re-key to Polly's sentence marks if they drift). Fewer words per card:
   type chips, the `POST /v1/systemone` line, the `#guardrails` tag, the shot 11 bars, p95s and
   footnote, and the shot 8 pre-shown first turn are cut. Body text is 36 px, mono is 30 px.
2. Shot 5 VO explains what a noul question is and why the answer is a probability rather than
   a sentence, then why the three text questions exist (envelope, grounded in what the user
   said, intent), then the two frame questions.
3. Shot 6 VO explains how a probability becomes an action: the two thresholds (0.65 confident
   yes, 0.35 confident no, between them the operator is asked), then the four actions with one
   example each (person -> Deny, invented distance -> Guide, unsure -> Confirm, otherwise
   Proceed), and why the gate never fails open. The card is a big ruler and four example rows.
4. Shot 7 VO reads the one real request and answer slowly: twenty centimetres said, zero point
   two in the tool call, so grounded 0.91; inside the envelope 0.95; intent move forward; a
   Proceed in 583 ms. The request lines and the bars appear in that order as they are spoken.
5. Shot 8 VO walks the recorded run step by step: "Go." carries no distance, Nova Pro guesses
   two metres, the arithmetic check fails and grounded reads 0.18, so Guide: re-plan; Nova Pro
   proposes half a metre, grounded reads 0.40, inside the unsure band, so Confirm: the operator
   is asked, the scripted operator says no, and the car never moved on a guessed number. Each
   terminal line appears with its clause.
6. Shot 11 is down to the numbers that matter: 462 ms median and 0 of 72 over budget for the
   local decider; 31 of 72 over budget and 0.13 USD per 1000 decisions for Nova Pro.
7. Seconds found by trimming shots 3 (callouts every 1.25 s, VO 26 words) and 4 (three groups
   at 3 s, VO 23 words) to about 10 s each and shot 11 to about 12 s. VO total 402 words (v2
   345; limit about 420). Every number is verbatim from the sources; honesty labels unchanged.

## Changes in v2

Applied from `docs/video/reviews/round-1-judge.md` and `round-1-editor.md`:

1. Hook rebuilt as the editor's alternative open: DENY and the red LED inside the first second
   (`pitwall-sim.webm` 2.5 s to 3.2 s, cropped to the live view and verdict panel), then the
   real car with its `REAL CAR, PHASE-1 RECORDING, UNGATED` label, then back to the frozen
   Deny with pointers and `Here is why.` Title is now `This car can refuse an order.`
2. The old shot 9 (ungated footage with an animated gate blink) is cut. Its slot is a card
   with the measured on-car Deny: 456 ms, `person_in_frame` p 0.9485, frames withheld because
   they show a person (`docs/results/beats-car-2026-10-15-person-gate/README.md`), with the
   judge's VO.
3. Shot 8: `OPERATOR: no (auto-answered by the test cell)` restored on screen; VO says "the
   scripted operator says no"; lower-third renamed `Recorded run, 2026-10-22: the real decider
   judges Nova Pro`; the first turn is pre-shown and the replay starts at `USER : Go.`; "say"
   became "type".
4. Shot 2 VO no longer says the light went red; it says the hop was refused, and the safety
   line sits as a footer on the frame from frame 0. The fake decider's 0.97 is never spoken as
   a judgement (shot 10 VO rewritten per the judge) and the `Judge: Strands Decider 2B` badge
   is hidden on every fake-stack frame (shots 1, 2, 10) and on the car (1b, 13).
5. Shot 12 uses the exact printed reason strings from `docs/video/build/clips/pattern-demo.txt`
   and a two-row layout with the terminal full width at Menlo 24; the chips became highlights
   on the verdict and reason values in the printed rows.
6. Shot 11: `0 USD marginal per 1000 decisions (after the laptop)`; the Nova Pro bars use 1500
   ms = 280 px so the p95 bar fits; the VO says "the grounding question alone".
7. Shot 6: row 7 footnote, Confirm on the car and Guide in the library; bands carry chips
   instead of prose. Shot 5: rows every 2.5 s, option sets only on the two choice rows, a key
   line for `noul` and `choice`. Shot 3: the figure is cropped below its baked title, no extra
   leader lines, a label plate per callout, reveals every 1.8 s.
8. Every text over footage or a photo sits on a plate; honesty labels are 28 px; cyan pointers
   on portal frames and orange on cards; the GIF is cropped to its content column with a
   darkened blur fill and frame blending; shot 13 stills run 2 s each; shot 14 has the URL at
   48 px with the author line above the tags; shot 7's JSON key order matches the log and its
   pointer brackets the words and the value.
9. VO trimmed by 42 words (387 to 345) so every shot's picture is at least the VO length plus
   0.5 s; durations are "auto" with minimums; no VO gap exceeds 1.5 s; no music and no room
   tone (nothing licensed; the renderer adds nothing to the audio track).
10. A "Shot list for the renderer" section at the end gives, per shot, the clip path, in and
    out seconds, crop rectangle, every overlay verbatim with position and times, every pointer
    with coordinates, and the VO.

Not applied, with the reason: a music bed or room tone (no licensed bed; coordinator's
decision); the YouTube author clip for shot 3 (burnt captions and name badge in every frame;
the Mumbai still carries the author's face instead); the judge's LOW note to lengthen shot 10
by a fixed 2 s (superseded by auto durations); the editor's 1440x810 letterbox for the webm
(superseded by the 1.59x crop of the live view, which makes the chips larger); the `draw.py`
colour and `SAFE_Y` mismatch is documented in `STORYBOARD.md` but `draw.py` is not edited here
(not owned by this task; the storyboard adopts `SAFE_Y = 72` and keeps its palette as the
source of truth); the second footnote line on shot 11 (`0 confident errors`) is dropped from
the card for density and did not fit the VO.

## Recurring on-screen elements

- Lower-third left: the section name on a plate. Lower-third right: the honesty label on a
  plate, Menlo 28 all caps: `REAL CAR, PHASE-1 RECORDING, UNGATED`; `SIM, FAKE DECIDER, DRAWN
  FIGURE`; `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`; `MEASURED ON THE CAR 2026-10-15, REAL
  DECIDER` + `FRAMES WITHHELD: THEY SHOW A PERSON`; `MEASURED 2026-10-22`; `FAKE DECIDER, STDOUT
  VERBATIM`.
- Verdict chips: PROCEED green, GUIDE amber, CONFIRM cyan, DENY red.
- Badge, two lines on a plate: `Agent: Amazon Nova Pro on Bedrock` / `Judge: Strands Decider
  2B, local`. Shown on shots 3 to 9, 11, 12. Hidden on 1, 1b, 2, 10, 13, 14.
- Safety line, exact wording everywhere: `Physics stops the car. The decider explains.`

## Shot table

| # | Duration | VISUAL | ON-SCREEN TEXT (verbatim) | POINTERS | VOICE-OVER (verbatim) |
|---|---|---|---|---|---|
| 1 | auto, min 4.0 s | HOOK A. `pitwall-sim.webm` from 2.5 s, cropped to the live view and verdict panel (1447 px wide, anchored left; the right column is bg). A clear frame, PROCEED; at +0.2 the stick figure walks in; at +0.4 DENY lands and `LED RED` turns red; freeze at +0.7 (webm 3.2 s) and hold. | Right column: `This car` / `can refuse` / `an order.` (Bold 56, in at +1.0). Honesty label, two lines: `SIM, FAKE DECIDER,` / `DRAWN FIGURE`. | Red pulse around the `LED RED` label at +0.4, twice. Nothing else. | This car can refuse an order. |
| 1b | 4.0 s fixed | THE CAR. `car-hop.gif` content column (x 217..422) at 618x1080 centred, darkened blur fill, frame-blended; the car drives away up the tiles and back, all 4 s. | Caption on a plate, top-left: `A stock AWS DeepRacer`. Honesty label: `REAL CAR, PHASE-1 RECORDING, UNGATED`. | None. | This is a stock AWS DeepRacer. |
| 2 | auto, min 4.0 s | HOOK B. The frozen webm frame from shot 1 (webm 3.2 s), same crop, held. | Right column: `Here is why.` (Caption 40, at +4.0). Footer, 26 px ink-dim: `Physics stops the car.` / `The decider explains.` from frame 0. Honesty label as shot 1. | Cyan circle around the figure at +0.3; cyan highlight on the two live-view chips (`FRAME CLASS person_in_frame`, `PROBABILITY 0.97`) and a cyan arrow from the circle to the probability chip at +1.0; red highlight on the DENY word at +2.5. | A person in the frame. The hop was refused. Here is why. |
| 3 | auto, min 9.5 s | WHAT IT IS. Dip to black 0.3 s. `fig-deepracer-strands.png` cropped below its baked title (y 100..900), 1440x720 centred; the seven callouts (box, baked leader line, dot) appear one every 1.25 s from +0.5: Decider, strands-robots, deadman, Harness, Agents, Bidi, Box. At +9.5 all but the Decider settle at 70 percent. | Title: `Driven as a Strands robot`. One label plate per callout: `Decider on the camera` (orange), `strands-robots on the drive`, `The deadman on the servos`, `Harness on the compute`, `Agents as the loop`, `Bidi as the voice`, `Box around the process`. Lower-third left: `Vivek Raja, AWS AI Hero`. Badge at +3.0. The figure's baked footer `Physics stops the car; the decider explains.` stays. | The baked leader lines are the pointers; nothing extra is drawn. | I am Vivek Raja. A Strands agent on Bedrock turns my words into hops; a local Decider two B judges each one before the wheels turn. |
| 4 | auto, min 9.5 s | ARCHITECTURE. `fig-architecture.png` at 1280x720, left, 25 percent brightness. Regions light in three groups: Bedrock Nova Pro and Strands Agents at +0.3; DeciderGate with the local Decider 2B at +3.3; strands-robots and the DeepRacer with the deadman node at +6.3. The picture carries the detail; the VO says less. | Label stack, top-right: `1 Nova Pro proposes the move` / `2 Strands Agents runs the tools` / `3 Decider 2B judges, before the tool runs` / `4 strands-robots carries it over rosbridge` / `5 On-car deadman: stops without the laptop` (lines added with their group; current line orange). Lower-third left: `Architecture`. Badge under the stack. | Cyan outline on each lit region, orange on region 3, red on the deadman sub-box; orange number badges 1 to 5; an orange arrow along the figure's "commands 20 Hz" line from the laptop to the car with group 2. | Nova Pro proposes the move. A Strands intervention handler asks the decider before the tool runs. The on-car deadman needs none of it. |
| 5 | auto, min 20.0 s | THE DECISION, part 1: what is asked, and why. Rendered card, one idea at a time, each keyed to the voice: the noul explanation in three short lines (+2.4, +4.8, +6.1), then the `Request 1` header and its three rows as each is named (+10.9, +11.9, +14.0), then the `Request 2` header and its two rows (+17.4, +18.4). Body 36 px, mono 30 px; no type chips, no endpoint line, no tag. | Title: `Five typed questions, two requests`. Key lines: `noul = a yes/no question` / `answered as a probability, 0 to 1, not a sentence` / `so code can compare it to a number`. `Request 1: the words`: `inside_envelope  Is the proposed movement inside the envelope the operator briefed?` / `args_grounded  Are the tool's argument values grounded in what the user actually said?` / `intent (choice)  What did the user most recently ask the robot to do?  move_forward turn stop question unrelated`. `Request 2: the frame, 480x360 JPEG`: `person  Is a person visible in the frame?` / `frame (choice)  What is directly in front of the car in this camera frame?  clear obstacle_near person_in_frame off_surface unclear`. Lower-third left: `The five questions`. | 2 px cyan leading bar on each row as it appears; orange on the `args_grounded` row. | Five typed questions. A noul is a yes or no, answered as a probability, so code can compare it to a number. Three are about the words: inside the envelope, grounded in what the user said, and what was asked. Two are about the frame: a person visible, and what is ahead. |
| 6 | auto, min 22.0 s | THE DECISION, part 2: how a probability becomes an action. Rendered card. Left: one big vertical probability ruler; the YES tick and label at +2.4, the NO tick and label at +5.8, the shaded band between them at +9.2. Right: four example rows with verdict chips, one per clause (+11.6, +13.6, +15.7, +16.7), then the fail-closed line (+17.8) and its explanation (+20.5). Body 36 px. | Title: `From a probability to an action`. Ruler: `1.0`, `0.65 or above: confident yes`, `0.35 or below: confident no`, `between: ask the operator`, `0.0`. Rows: `a person in frame` chip `DENY` / `an invented distance` chip `GUIDE` + `re-plan` / `unsure, in the band` chip `CONFIRM` + `ask the operator` / `otherwise` chip `PROCEED`. Then `a late or missing decider` chip `DENY` and `The gate never fails open.` Small note: `Row 7 on the car: Confirm (the marshal may approve a bigger hop); in the library: Guide.` Lower-third left: `Thresholds and actions`. | Green tick and shade above 0.65, red tick and shade below 0.35, cyan shade between; nothing else. | Two thresholds make the action. Zero point six five or above: a confident yes. Zero point three five or below: a confident no. Between them, the operator is asked. A person in frame: Deny. An invented distance: Guide, re-plan. Unsure: Confirm. Otherwise: Proceed. A late or missing decider is a Deny: the gate never fails open. |
| 7 | auto, min 13.0 s | THE DECISION, part 3: one real request and answer, read slowly (gate log row 1 of the recorded run). Left: the request lines appear as they are spoken: the conversation line at +0.3, the tool call at +2.0, the envelope and the arithmetic check at +6.8. Right: the bars appear in the order spoken: grounded at +4.7, inside the envelope at +6.8, intent at +9.5; the chip at +10.9 and the latency at +11.6. Mono 30 px. | Title: `One real request, one real answer`. Left (mono): `"conversation": "user: Move forward 20 centimetres."` / `"command": {"tool": "move",` / `"arguments": {"heading_deg": 0, "distance_m": 0.2}},` / `"envelope": "distance_m <= 0.5 per call,` / `\|heading_deg\| <= 90",` / `"deterministic_check": "ok"`. Right: `args_grounded  0.907` / `inside_envelope  0.948` / `intent  move_forward  0.959` / chip `PROCEED` / `583 ms`. `YES 0.65`. Honesty label: `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`. | Cyan highlight on `20 centimetres.` at +0.3 and on `0.2` at +2.0, joined by a cyan bracket; one orange arrow from the bracket to the `args_grounded` bar at +4.7; each bar turns green as it crosses the YES rule. | The user said twenty centimetres; the tool call says zero point two. Grounded: zero point nine one. Inside the envelope: zero point nine five. Intent: move forward. A Proceed, in five hundred eighty three milliseconds. |
| 8 | auto, min 22.0 s | THE RECORDED RUN, step by step. Terminal replay, Menlo 30, left column; no pre-shown lines. Each line appears with the clause that explains it: `USER : Go.` +1.0; the 2 m call +3.0; the failed arithmetic check +5.4; grounded 0.18 +6.8; the Guide verdict and reason +8.8; the 0.5 m call +9.9; grounded 0.404 +12.3; the Confirm verdict, reason and the operator question +15.7; `OPERATOR: no (this cell auto-answers False)` (verbatim) +17.7; the agent's reply, with `(thinking omitted)` for the dropped think block, +19.8. | Lower-third left: `Recorded run, 2026-10-22: the real decider judges Nova Pro`. Honesty label: `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`. Step labels, right column, one per clause: `"Go." carries no distance` / `Nova Pro guesses 2 m` / `check fails: 2 > 0.5; grounded 0.18` / `GUIDE: re-plan` / `Nova Pro proposes 0.5 m` / `grounded 0.40: the unsure band` / `CONFIRM: the operator is asked` / `scripted operator: no`. Caption at +20.5: `A guessed distance moved nothing.` | Highlights with their clause: `"distance_m": 2` orange, `"distance_m 2 > 0.5"` orange, `0.18` amber, `"Guide"` amber, `"distance_m": 0.5` orange, `0.404` cyan, `"Confirm"` cyan, the OPERATOR line cyan. No arrows. | I type: Go. Go carries no distance, so Nova Pro guesses two metres. The arithmetic check fails, grounded reads zero point one eight: Guide, re-plan. Nova Pro proposes half a metre. Grounded reads zero point four zero, inside the unsure band: Confirm, the operator is asked. The scripted operator says no. The car never moved on a guessed number. |
| 9 | auto, min 6.0 s | MEASURED ON THE CAR. Rendered card on bg, no footage (the frames show the operator at the desk and stay out of the repo). Lines appear at +0.3, +4.0, +6.5, +8.5. | Title: `Measured on the real car`. Centre: `On the car: a person in frame was denied in 456 ms` / `person_in_frame   p = 0.9485` / `whole gate 681 to 727 ms per hop; no motion event after the deny` / `Source: docs/results/beats-car-2026-10-15-person-gate`. Lower-third left: `On the car, 2026-10-15`. Honesty label, two lines: `MEASURED ON THE CAR 2026-10-15, REAL DECIDER` / `FRAMES WITHHELD: THEY SHOW A PERSON`. Badge shown (the judge here is the real decider). | None. | On the car, the same gate denied a hop with a person in frame in four hundred fifty six milliseconds. The frames stay private; they show a person. |
| 10 | auto, min 10.0 s | THE DENY IN THE SIMULATOR. `fig-portal-stage.png` native, no push-in. At +7.5 the screenshot dims to 40 percent behind a plate band and the safety line. | Caption on a plate, top-centre: `Row 3: person in frame -> Deny`. Quote card at +5.0: `"Someone is in front of me. I stopped."` Safety line at +7.5: `Physics stops the car. The decider explains.` Lower-third left: `Pit Wall, the simulated car`. Honesty label: `SIM, FAKE DECIDER, DRAWN FIGURE`. Badge hidden. | Cyan arrow from the figure to the CLASS chip and a cyan highlight around the CLASS and PROBABILITY chips at +1.0; red highlight on the DENY word at +2.5. The `92 ms` stop card is not marked. | In the simulator, a figure in the frame is row three, a Deny, and the rover says why. Physics stops the car. The decider explains. |
| 11 | auto, min 10.0 s | THE NUMBERS, the four that matter. Rendered card, two columns; each number counts up over 1 s when the voice reaches it: 462 ms at +1.3, 0 of 72 at +3.4, 31 of 72 at +7.1, 0.13 USD at +9.5. No bars, no p95, no footnote. | Title: `Measured on the booth laptop: 72 timed calls`. Left header `Strands Decider 2B, local`: `462 ms` + `median, three questions in one request` / `0 of 72` + `over the 1.5 s budget`. Right header `Amazon Nova Pro on Bedrock`: `31 of 72` + `over the 1.5 s budget` / `0.13 USD` + `per 1000 decisions`. Lower-third left: `The numbers`. Honesty label: `MEASURED 2026-10-22`. | None. | The local decider: four hundred sixty two milliseconds median, zero of seventy two over budget. Nova Pro on Bedrock: thirty one of seventy two over budget, thirteen cents per thousand decisions. |
| 12 | auto, min 10.7 s | THE REUSABLE PATTERN. Two rows: the file tree and the wiring snippet at +0.3; the terminal full width at +4.5, typed over 2 s, showing the three JSON rows of `make pattern-demo` verbatim from `pattern-demo.txt`; highlights at +7.0. | Title: `Drop it into your own agent`. `three files, upstream names`: `patterns/strands/` `_client.py` `tool_call_intervention.py` `frame_intervention.py` `README.md`. `three lines of wiring`: `decider = Decider(timeout=1.5)` / `agent = Agent(` / `model=BedrockModel(model_id="us.amazon.nova-pro-v1:0",` / `region_name="us-east-1"),` / `tools=[move],` / `interventions=[MotionGate(decider)],` / `)`. Terminal header: `make pattern-demo, against the fake decider (a script, not the model)`; rows with `"verdict": "Proceed"`, `"reason": "inside envelope p=0.95, grounded p=0.95"`, `"verdict": "Guide"`, `"reason": "outside envelope: distance_m 2 > 0.5"`, `"verdict": "Deny"`, `"reason": "decider unavailable: failing closed, no motion"`. Lower-third left: `github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands`. Honesty label: `FAKE DECIDER, STDOUT VERBATIM`. | Cyan highlight on `timeout=1.5` at +1.5; orange on `interventions=[MotionGate(decider)]` at +2.5; green, amber and red highlights on the three `"verdict"` values and orange on the three `"reason"` values at +7.0. | The pattern is a drop-in. Three files with the upstream names, three lines of wiring, and make pattern demo runs it offline against a fake decider. |
| 13 | 4.0 s fixed | MUMBAI. `event-speaker-with-car.jpg` fitted to height for 2.0 s, then `event-hall.jpg` fitted to height for 2.0 s, each over a darkened blur fill. | Lower-third left: `AWS Community Day Mumbai, 17 October 2026`. | None. | Shown at AWS Community Day Mumbai. |
| 14 | auto, min 8.0 s | CLOSE. Dip to black 0.3 s; `cover.png` at 40 percent; the centre stack fades in over 1.0 s from +0.4; fade to black over the last 0.5 s. | Centre: `Physics stops the car. The decider explains.` / `github.com/Vivek0712/strands-robots-deepracer` / `Vivek Raja, AWS AI Hero  \|  Article on AWS Builder Center` / `#strands-decider-2b   #guardrails`. Strands mark bottom-right. | None. | Repo and article below. Physics stops the car. The decider explains. |

## Timing table (estimated; the renderer conforms to the Polly audio)

Estimate per shot: VO words at 176 wpm (Polly generative Matthew) plus 0.35 s per sentence
end; picture = max(minimum, VO start + VO length + 0.5 s). Fixed shots keep their length.

| # | VO words | VO est. | VO starts | Minimum | Est. duration | Est. window | Est. VO window |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 2.4 s | +1.0 s | 4.0 s | 4.0 s | 0:00.0-0:04.0 | 0:01.0-0:03.4 |
| 1b | 6 | 2.4 s | +0.5 s | 4.0 s fixed | 4.0 s | 0:04.0-0:08.0 | 0:04.5-0:06.9 |
| 2 | 12 | 5.1 s | +0.3 s | 4.0 s | 5.9 s | 0:08.0-0:13.9 | 0:08.3-0:13.4 |
| 3 | 26 | 9.6 s | +0.4 s | 9.5 s | 10.5 s | 0:13.9-0:24.4 | 0:14.3-0:23.9 |
| 4 | 23 | 8.9 s | +0.3 s | 9.5 s | 9.7 s | 0:24.4-0:34.1 | 0:24.7-0:33.6 |
| 5 | 52 | 19.1 s | +1.0 s | 20.0 s | 20.6 s | 0:34.1-0:54.7 | 0:35.1-0:54.2 |
| 6 | 56 | 22.2 s | +0.3 s | 22.0 s | 23.0 s | 0:54.7-1:17.8 | 0:55.0-1:17.3 |
| 7 | 35 | 13.7 s | +0.3 s | 13.0 s | 14.5 s | 1:17.8-1:32.2 | 1:18.1-1:31.7 |
| 8 | 59 | 22.6 s | +0.3 s | 22.0 s | 23.4 s | 1:32.2-1:55.6 | 1:32.5-1:55.1 |
| 9 | 28 | 10.2 s | +0.3 s | 6.0 s | 11.0 s | 1:55.6-2:06.7 | 1:55.9-2:06.2 |
| 10 | 25 | 9.6 s | +0.3 s | 10.0 s | 10.4 s | 2:06.7-2:17.0 | 2:07.0-2:16.5 |
| 11 | 31 | 11.3 s | +0.3 s | 10.0 s | 12.1 s | 2:17.0-2:29.1 | 2:17.3-2:28.6 |
| 12 | 26 | 9.6 s | +0.3 s | 10.7 s | 10.7 s | 2:29.1-2:39.8 | 2:29.4-2:39.0 |
| 13 | 6 | 2.4 s | +0.3 s | 4.0 s fixed | 4.0 s | 2:39.8-2:43.8 | 2:40.1-2:42.5 |
| 14 | 11 | 4.8 s | +0.4 s | 8.0 s | 8.0 s | 2:43.8-2:51.8 | 2:44.2-2:49.0 |

Totals: 402 VO words; picture ends at 2:51.8 (planned maximum 2:52, ceiling 3:00); the last
word at 2:49.0; the longest gap between spoken lines is 1.7 s (into shot 5, whose first row
waits for the voice); the hold after the last word is the closing card. The v2 render came in
at 2:37.5 with 345 words at the same voice, so the 57 extra words cost about 20 s and the trims
on shots 3, 4 and 11 give about 6 s back.

Render Polly first, one request per shot, keep the per-shot audio files, and conform the
picture to the measured audio; re-key every `at` time in the renderer list to Polly's sentence
marks (`--speech-mark-types sentence`) when they drift from the estimates. If the measured
audio runs long, cut in this order: (1) the hall still on shot 13 (1 s); (2) shot 9's second
sentence from the VO only, the label keeps it (1.9 s); (3) shot 6's row 7 note from the card
and `the gate never fails open` from the VO, the card line keeps it (1.7 s); (4) shot 14's
hold to 7 s. Never cut shot 7's answer, shot 8's steps or shot 11's numbers.

## Voice-over, read-through copy

For pasting into Amazon Polly, one request per shot. A generative English voice at the default
rate; no SSML needed because every number is written as it is spoken.

1. This car can refuse an order.
1b. This is a stock AWS DeepRacer.
2. A person in the frame. The hop was refused. Here is why.
3. I am Vivek Raja. A Strands agent on Bedrock turns my words into hops; a local Decider two B judges each one before the wheels turn.
4. Nova Pro proposes the move. A Strands intervention handler asks the decider before the tool runs. The on-car deadman needs none of it.
5. Five typed questions. A noul is a yes or no, answered as a probability, so code can compare it to a number. Three are about the words: inside the envelope, grounded in what the user said, and what was asked. Two are about the frame: a person visible, and what is ahead.
6. Two thresholds make the action. Zero point six five or above: a confident yes. Zero point three five or below: a confident no. Between them, the operator is asked. A person in frame: Deny. An invented distance: Guide, re-plan. Unsure: Confirm. Otherwise: Proceed. A late or missing decider is a Deny: the gate never fails open.
7. The user said twenty centimetres; the tool call says zero point two. Grounded: zero point nine one. Inside the envelope: zero point nine five. Intent: move forward. A Proceed, in five hundred eighty three milliseconds.
8. I type: Go. Go carries no distance, so Nova Pro guesses two metres. The arithmetic check fails, grounded reads zero point one eight: Guide, re-plan. Nova Pro proposes half a metre. Grounded reads zero point four zero, inside the unsure band: Confirm, the operator is asked. The scripted operator says no. The car never moved on a guessed number.
9. On the car, the same gate denied a hop with a person in frame in four hundred fifty six milliseconds. The frames stay private; they show a person.
10. In the simulator, a figure in the frame is row three, a Deny, and the rover says why. Physics stops the car. The decider explains.
11. The local decider: four hundred sixty two milliseconds median, zero of seventy two over budget. Nova Pro on Bedrock: thirty one of seventy two over budget, thirteen cents per thousand decisions.
12. The pattern is a drop-in. Three files with the upstream names, three lines of wiring, and make pattern demo runs it offline against a fake decider.
13. Shown at AWS Community Day Mumbai.
14. Repo and article below. Physics stops the car. The decider explains.

## Sound off test

Does each shot make sense muted?

- Shot 1: yes. DENY, the red LED and the three-line title `This car can refuse an order.` are on screen within the first second; the SIM label is on frame 0.
- Shot 1b: yes. The caption names the car and the label says what the footage is.
- Shot 2: yes. The circle, the chip highlights, the red DENY highlight, `Here is why.` and the safety footer read without sound.
- Shot 3: yes. The title and the seven label plates name the project and the Strands pieces; the badge names the agent model and the judge.
- Shot 4: yes. The numbered label stack is the five-step path; the figure is a backdrop.
- Shot 5: yes. The three key lines say what a noul answer is, then the five questions appear verbatim one at a time with their option sets.
- Shot 6: yes. The ruler shows the two thresholds and the band, the four rows show one example per action, and the last line says the gate never fails open.
- Shot 7: yes. The words and the value are highlighted and bracketed, the three bars arrive in the spoken order with their numbers, then the PROCEED chip and 583 ms.
- Shot 8: yes. Each terminal line arrives with a short step label beside it; the highlighted numbers, the OPERATOR line and the closing caption carry the argument.
- Shot 9: yes. Four lines of measured numbers with the source path and the withheld-frames label.
- Shot 10: yes. The caption names the row, the quote card gives the rover's line, the safety line is large; the SIM label is on screen throughout.
- Shot 11: yes. Four numbers with their units and one line each saying what they are.
- Shot 12: yes. The file tree, the wiring lines and the highlighted verdicts and reasons are the whole message; the path is in the lower third.
- Shot 13: yes, with the lower third; four seconds of context.
- Shot 14: yes. Safety line, URL, author line and tags are all on the card.

Verdict: the video makes sense with the sound off on all 15 shots.

## Voice-over word count

402 words across the 15 shots (counted on the read-through copy above, numerals written out);
v2 had 345, v1 387. At 176 words per minute plus 0.35 s per sentence end that is 2 minutes 25
seconds of speech; with the per-shot start offsets and the fixed shots the last word lands at
about 2:49.0 and the picture ends at about 2:51.8.

## Assets referenced

Footage and stills (paths relative to the repo root; details in `ASSETS.md`):
- `docs/results/portal/pitwall-sim.webm` (shots 1, 2): 1280x720, 25 fps; the DENY window is
  2.9 to 3.5 s, the figure is in frame 2.7 to 3.5 s; used from 2.5 s, frozen at 3.2 s.
- `docs/media/car-hop.gif` (shot 1b): 640x360, 12 fps, 4.0 s, content column x 217..422;
  phase-1, ungated. (`docs/video/build/clips/car-hop-1080p.mp4` is the same content padded on
  black without the blur fill; the GIF crop is preferred.)
- `docs/article/img/fig-deepracer-strands.png` (shot 3), with its HTML source
  `docs/article/img/svg/fig-deepracer-strands.html` for the per-callout layers.
- `docs/article/img/fig-architecture.png` (shot 4).
- `docs/article/img/fig-portal-stage.png` (shot 10): the Pit Wall Stage view, sim.
- `docs/article/img/event-speaker-with-car.jpg`, `docs/article/img/event-hall.jpg` (shot 13).
- `docs/article/img/cover.png` (shot 14 backdrop).
- `docs/talk/deck/assets/logos/strands-mark.svg` (shot 14).

Recorded data quoted on screen:
- `docs/video/build/clips/real-decider-transcript.txt` and `notebooks/decider_gate_walkthrough.ipynb`,
  "Recorded run on 2026-10-22, against the real decider": the transcript and gate log rows 1 to
  3 (shots 7, 8).
- `docs/video/build/clips/pattern-demo.txt` lines 7 to 9: the three gate log rows of `make
  pattern-demo` (shot 12).
- `docs/results/beats-car-2026-10-15-person-gate/README.md`: 456 ms, `person_in_frame` p 0.9485,
  681 to 727 ms per hop, no motion event, frames withheld (shot 9).
- `docs/results/decider-text-questions-2026-10-22.md`: 462 ms p50 (three questions in one
  request), 0 of 72 over the 1.5 s budget, Nova Pro 31 of 72 over budget, 0.1318 USD per 1000
  decisions (shot 11).
- `hackathon/SUBMISSION.md` and `docs/article/article.md`: the five questions, the 13-row
  table, YES 0.65 / NO 0.35, budget 1.5 s, row 7 on the car vs the library (shots 5, 6).
- `portal/backend/narrator.py`: "Someone is in front of me. I stopped." (shot 10).
- `patterns/strands/README.md` and `tool_call_intervention.py`: the wiring lines (shot 12).

Rendered by the renderer (no source file; layout in `STORYBOARD.md`, coordinates below): the
title and captions, lower thirds and honesty labels, the badge, the callout label plates (3),
the label stacks (4, 8), the five-question card (5), the band card and ruler (6), the request
and answer split card (7), the terminal replay (8), the on-car card (9), the quote card and
safety band (10), the numbers card (11), the file tree, code panel and terminal (12), the
closing card (14).

## Shot list for the renderer

All coordinates are in the 1920x1080 frame, x to the right, y down, as `x0..x1, y0..y1` for
boxes and `(x, y)` for the top-left of a text box. Times are seconds from the shot's start.
Fonts: `HelveticaNeue.ttc` (index 0 Regular, 1 Bold; Medium and Medium Italic by index per
`ASSETS.md` section 6) and `Menlo.ttc` (index 0). Character widths used: Menlo 28 = 16.85 px,
Menlo 26 = 15.65 px, Menlo 24 = 14.45 px. Colours by token from `STORYBOARD.md`. "Plate" is
`#0b0b10` at 60 percent with 16 px padding around the text box unless a box is given.
Standard positions: lower-third left plate `80..(text width + 128), 952..1008` with a 2 px
orange bar at x 96 and the text at (112, 964) Medium 32; honesty label plate right-aligned,
text Menlo 28 ink-dim ending at x 1824, plate to x 1840, y 952..1008 (two-line variant y
924..1008, lines at y 932 and 966); badge plate `1480..1840, 72..130`, lines Menlo 22 ink-dim
at (1496, 80) and (1496, 106) unless noted.

### Shot 1 (auto, min 4.0)
- Clip: `docs/results/portal/pitwall-sim.webm`, in 2.5 s, out 3.2 s, then hold the 3.2 s frame.
  Crop source `0..910, 40..720`; scale 1.59; place at `0..1447, 0..1080`. Right of x 1447: bg.
- Overlays: title lines Bold 56 ink at (1500, 120) `This car`, (1500, 190) `can refuse`,
  (1500, 260) `an order.`, in +1.0 (0.3 s fade), out at shot end. Honesty label Menlo 28
  ink-dim at (1500, 940) `SIM, FAKE DECIDER,` and (1500, 972) `DRAWN FIGURE`, in 0.0, no plate
  (bg column).
- Pointers: red pulse rectangle `1310..1432, 8..48` around the `LED RED` label, at +0.4, two
  pulses of 0.3 s, then off.
- VO at +1.0: This car can refuse an order.

### Shot 1b (fixed 4.0)
- Clip: `docs/media/car-hop.gif`, in 0.0, out 4.0. Crop source `217..422, 0..360`; scale 3.0;
  place at `651..1269, 0..1080`. Behind it: the same crop scaled to cover 1920x1080, gaussian
  blur 24 px, 35 percent brightness. Convert 12 to 30 fps with `minterpolate=mi_mode=blend`.
- Overlays: caption Medium 40 ink at (96, 72) `A stock AWS DeepRacer` on a plate `80..560,
  60..132`, in +0.2. Honesty label Menlo 28 ink-dim at (1216, 964) `REAL CAR, PHASE-1
  RECORDING, UNGATED` on a plate `1200..1840, 952..1008`, in 0.0.
- Pointers: none.
- VO at +0.5: This is a stock AWS DeepRacer.

### Shot 2 (auto, min 4.0)
- Clip: the shot 1 freeze frame (webm 3.2 s), same crop and placement, held for the shot.
- Overlays: footer Regular 26 ink-dim at (1500, 840) `Physics stops the car.` and (1500, 872)
  `The decider explains.`, in 0.0. Honesty label as shot 1. Caption Medium 40 ink at (1500,
  120) `Here is why.`, in +4.0.
- Pointers (cyan): circle centre (405, 370) radius 190, 4 px, at +0.3. Highlight boxes
  `40..310, 545..625` (FRAME CLASS chip) and `615..770, 545..625` (PROBABILITY chip) at +1.0.
  Arrow from (557, 484) to (685, 548) at +1.0. Red highlight `825..1107, 135..262` on the DENY
  word at +2.5.
- VO at +0.3: A person in the frame. The hop was refused. Here is why.

### Shot 3 (auto, min 9.5)
- 0.0 to 0.3: black. Asset: `docs/article/img/fig-deepracer-strands.png` (1600x900), crop source
  `0..1600, 100..900`, scale 0.9, place at `240..1680, 190..910`. Render from
  `docs/article/img/svg/fig-deepracer-strands.html` as 8 layers: base (car, background, baked
  footer) and one per callout (box, leader line, dot). Composite the callout layers in at the
  times below (0.3 s fade); at +9.5 drop layers 2 to 7 to 70 percent opacity.
- Callout boxes (frame coordinates) and their label plates (Medium 30, plate 44 px tall at
  the box's top edge minus 24, text at plate x + 12):
  1. `267..561, 208..314`, plate at (267, 184) `Decider on the camera` orange, +0.5
  2. `267..561, 370..494`, plate at (267, 346) `strands-robots on the drive`, +1.75
  3. `267..561, 586..674`, plate at (267, 562) `The deadman on the servos`, +3.0
  4. `1401..1680, 199..305`, plate at (1401, 175) `Harness on the compute`, +4.25
  5. `1401..1680, 374..463`, plate at (1401, 350) `Agents as the loop`, +5.5
  6. `1401..1680, 550..638`, plate at (1401, 526) `Bidi as the voice`, +6.75
  7. `1401..1680, 712..800`, plate at (1401, 688) `Box around the process`, +8.0
- Overlays: title Bold 64 ink at (96, 72) `Driven as a Strands robot`, in +0.4. Lower-third
  left `Vivek Raja, AWS AI Hero`, in +0.4. Badge plate `1284..1840, 926..1008`, lines Menlo 22
  ink-dim at (1300, 936) `Agent: Amazon Nova Pro on Bedrock` and (1300, 966) `Judge: Strands
  Decider 2B, local`, in +3.0.
- Pointers: none drawn.
- VO at +0.4: I am Vivek Raja. A Strands agent on Bedrock turns my words into hops; a local Decider two B judges each one before the wheels turn.

### Shot 4 (auto, min 9.5)
- Asset: `docs/article/img/fig-architecture.png` (1600x900), scale 0.8, place at `96..1376,
  200..920`, 25 percent brightness. Regions (frame coordinates), lit to 100 percent over 0.4 s,
  earlier ones settling at 70 percent:
  R1 Bedrock `128..752, 224..324` and R2 Strands Agents `160..384, 416..512` at +0.3;
  R3 DeciderGate and Decider 2B `400..728, 416..512` at +3.3;
  R4 strands-robots `160..728, 520..684` and R5 DeepRacer `960..1344, 360..892` at +6.3;
  deadman sub-box `976..1328, 552..676` (inside R5).
- Pointers: cyan 3 px outline on R1, R2, R4, R5 as each lights; orange outline on R3; red
  outline on the deadman sub-box with R5; orange number badges (circle r 18, white digit 22 px)
  centred at (128, 224) `1`, (160, 416) `2`, (400, 416) `3`, (160, 520) `4`, (960, 360) `5`,
  each with its region; orange arrow from (752, 464) to (960, 464) at +3.3.
- Overlays: label stack Regular 30, 40 px leading, at x 1392, wrapped as shown, current line
  orange, earlier lines ink-dim: (1392, 200) `1 Nova Pro proposes the move` and (1392, 240)
  `2 Strands Agents runs the tools` at +0.3; (1392, 280) `3 Decider 2B judges,` and (1392, 320)
  `  before the tool runs` at +3.3; (1392, 360) `4 strands-robots carries it`, (1392, 400) `  over
  rosbridge`, (1392, 440) `5 On-car deadman: stops`, (1392, 480) `  without the laptop` at +6.3.
  Badge plate `1392..1840, 540..598`, lines at (1408, 548) and (1408, 574). Lower-third left
  `Architecture`.
- VO at +0.3: Nova Pro proposes the move. A Strands intervention handler asks the decider before the tool runs. The on-car deadman needs none of it.

### Shot 5 (auto, min 20.0)
- Card on bg. Title Bold 56 ink at (96, 72) `Five typed questions, two requests` from 0.0.
  Lower-third left `The five questions`. Badge plate `1284..1840, 926..1008`, lines at (1300,
  936) and (1300, 966). Body text is Regular 36 ink (about 18 px per character), names Menlo 30.
- Key lines, Regular 36 ink, each keyed to its clause: (96, 160) `noul = a yes/no question` at
  +2.4; (96, 210) `answered as a probability, 0 to 1, not a sentence` at +4.8; (96, 260) `so
  code can compare it to a number` at +6.1.
- Header Medium 32 ink-dim at (96, 340) `Request 1: the words` at +9.2.
- Row 1 at +10.9: leading bar cyan `86..88, 386..426`; Menlo 30 ink at (96, 390)
  `inside_envelope`; Regular 36 ink at (520, 390) `Is the proposed movement inside the envelope
  the operator briefed?` (one line, about 1190 px).
- Row 2 at +11.9: leading bar orange `86..88, 446..486`; (96, 450) `args_grounded`; (520, 450)
  `Are the tool's argument values grounded in what the user actually said?` (wrap to a second
  line at y 494 if it exceeds 1304 px).
- Row 3 at +14.0: bar cyan `86..88, 506..546`; (96, 510) `intent` with Menlo 24 ink-dim at (96,
  548) `choice`; (520, 510) `What did the user most recently ask the robot to do?`; options
  Menlo 26 ink-dim at (520, 556) `move_forward   turn   stop   question   unrelated`.
- Header at (96, 640) `Request 2: the frame, 480x360 JPEG` at +15.7.
- Row 4 at +17.4: bar cyan `86..88, 686..726`; (96, 690) `person`; (520, 690) `Is a person
  visible in the frame?`
- Row 5 at +18.4: bar cyan `86..88, 746..786`; (96, 750) `frame` with Menlo 24 ink-dim at (96,
  788) `choice`; (520, 750) `What is directly in front of the car in this camera frame?`;
  options at (520, 796) `clear   obstacle_near   person_in_frame   off_surface   unclear`.
- Pointers: the leading bars only.
- VO at +1.0: Five typed questions. A noul is a yes or no, answered as a probability, so code can compare it to a number. Three are about the words: inside the envelope, grounded in what the user said, and what was asked. Two are about the frame: a person visible, and what is ahead.

### Shot 6 (auto, min 22.0)
- Card on bg. Title Bold 56 ink at (96, 72) `From a probability to an action` from 0.0.
  Lower-third left `Thresholds and actions`. Badge plate standard (`1480..1840, 72..130`).
- Ruler (left): ink-dim 3 px line `300, 180..880` (1.0 at the top, 0.0 at the bottom, 700 px
  for 1.0) from +0.3; Menlo 26 ink-dim at (250, 168) `1.0` and (250, 868) `0.0`.
  At +2.4: green tick `280..320, 423..427`; green shade `280..320, 180..425` at 15 percent;
  Regular 36 ink at (340, 405) `0.65 or above: confident yes`.
  At +5.8: red tick `280..320, 633..637`; red shade `280..320, 635..880` at 15 percent; Regular
  36 ink at (340, 615) `0.35 or below: confident no`.
  At +9.2: cyan shade `280..320, 425..635` at 20 percent; Regular 36 ink at (340, 510)
  `between: ask the operator`.
- Example rows (right), Regular 36 ink at x 1000, verdict chip Menlo Bold 30 at x 1560 on the
  same row, each keyed:
  +11.6: (1000, 300) `a person in frame`, chip DENY (red) at (1560, 298).
  +13.6: (1000, 400) `an invented distance`, chip GUIDE (amber) at (1560, 398); Regular 28
  ink-dim at (1000, 444) `re-plan`.
  +15.7: (1000, 500) `unsure, in the band`, chip CONFIRM (cyan) at (1560, 498); Regular 28
  ink-dim at (1000, 544) `ask the operator`.
  +16.7: (1000, 600) `otherwise`, chip PROCEED (green) at (1560, 598).
  +17.8: Regular 32 ink at (1000, 720) `a late or missing decider`, chip DENY (red) at (1560,
  718).
  +20.5: Regular 32 ink-dim at (1000, 790) `The gate never fails open.`; Regular 26 ink-dim at
  (1000, 850) `Row 7 on the car: Confirm (the marshal may approve` and (1000, 884) `a bigger
  hop); in the library: Guide.`
- Pointers: none beyond the ticks and shades.
- VO at +0.3: Two thresholds make the action. Zero point six five or above: a confident yes. Zero point three five or below: a confident no. Between them, the operator is asked. A person in frame: Deny. An invented distance: Guide, re-plan. Unsure: Confirm. Otherwise: Proceed. A late or missing decider is a Deny: the gate never fails open.

### Shot 7 (auto, min 13.0)
- Card on bg. Title Bold 56 ink at (96, 72) `One real request, one real answer`. Badge plate
  standard. Honesty label plate `1070..1840, 952..1008`, text at (1086, 964) `RECORDED
  2026-10-22, REAL DECIDER + NOVA PRO`. No lower-third left.
- Left: Menlo 24 ink-dim at (96, 196) `REQUEST (state)` from +0.3. Request lines Menlo 30 ink
  at x 96, 44 px leading (line n at y 230 + 44 n), each line appearing with its clause:
  +0.3: line 0 `"conversation": "user: Move forward 20 centimetres."` with a cyan highlight
  `742..1021, 226..264` on `20 centimetres.`
  +2.0: line 1 `"command": {"tool": "move",` and line 2 `  "arguments": {"heading_deg": 0,
  "distance_m": 0.2}},` with a cyan highlight `958..1021, 314..352` on `0.2`, and a cyan
  bracket: vertical line `1035, 245..333` with 10 px ticks to the left at both ends.
  +6.8: line 3 `"envelope": "distance_m <= 0.5 per call,`, line 4 `  |heading_deg| <= 90",`,
  line 5 `"deterministic_check": "ok"`.
- Right: Menlo 24 ink-dim at (1000, 196) `ANSWER` from +4.7; Menlo 24 ink-dim at (1530, 255)
  `YES 0.65` and a dotted cyan line `1560, 280..560` from +4.7. Bars 400 px for 1.0 from x 1300,
  36 px tall, filling over 1.2 s, ink-dim until the fill crosses x 1560 then green; labels Menlo
  30 ink at x 1000; values Menlo 30 ink at x 1716:
  +4.7: label (1000, 294) `args_grounded`; bar `1300..1663, 290..326` filling from +5.1; value
  (1716, 294) `0.907`.
  +6.8: label (1000, 394) `inside_envelope`; bar `1300..1679, 390..426` filling from +7.8; value
  (1716, 394) `0.948`.
  +9.5: label (1000, 494) `intent` with Menlo 24 ink-dim at (1000, 540) `move_forward`; bar
  `1300..1684, 490..526` filling from +9.9; value (1716, 494) `0.959`.
  +10.9: chip PROCEED (green) Menlo Bold 30 at (1300, 600). +11.6: Bold 48 ink at (1480, 592)
  `583 ms`.
- Pointer: orange arrow from (1045, 290) to (1296, 308) at +4.7 (bracket to the grounded bar).
- VO at +0.3: The user said twenty centimetres; the tool call says zero point two. Grounded: zero point nine one. Inside the envelope: zero point nine five. Intent: move forward. A Proceed, in five hundred eighty three milliseconds.

### Shot 8 (auto, min 22.0)
- Card on bg. Terminal text Menlo 30 (18.05 px per character) at x 96, first line y 150, 38 px
  leading (line n at y 150 + 38 n), left column x 96..1071. No pre-shown lines. Lines
  (hard-wrapped, verbatim values from the recorded run; gate rows with keys omitted), each
  typed at 40 characters per second starting at its `at` time:
  ```
  00 USER : Go.                                                    at +1.0
  01 {"arguments": {"heading_deg": 0, "distance_m": 2},            at +3.0
  02  "deterministic_check": "distance_m 2 > 0.5",                 at +5.4
  03  "args_grounded": 0.18, "verdict": "Guide",                   at +6.8
  04  "reason": "outside envelope: distance_m 2 > 0.5"}            at +8.8
  05 {"arguments": {"heading_deg": 0, "distance_m": 0.5},          at +9.9
  06  "deterministic_check": "ok", "args_grounded": 0.404,         at +12.3
  07  "verdict": "Confirm",                                        at +15.7
  08  "reason": "unclear: inside=0.88 grounded=0.40"}              at +15.7
  09 CONFIRM (operator asked): The decider is unsure about         at +15.7
  10   this move (inside envelope p=0.88, grounded p=0.40).        at +15.7
  11   Allow it?                                                   at +15.7
  12 OPERATOR: no (this cell auto-answers False)                   at +17.7
  13 AGENT: (thinking omitted) The move could not be              at +19.8
  14   completed because the decider is unsure about it,         at +19.8
  15   despite it being within the allowed envelope.             at +19.8
  16   Please provide further instructions or                    at +19.8
  17   clarification.                                            at +19.8
  ```
- Highlights (3 px, 12 percent fill), each 0.4 s after its line starts: orange `688..966,
  184..222` (`"distance_m": 2`) at +3.4; orange `525..894, 222..260` (`"distance_m 2 > 0.5"`)
  at +5.8; amber `417..497, 260..298` (`0.18`) at +7.2; amber `724..858, 260..298` (`"Guide"`)
  at +8.8; orange `688..1002, 336..374` (`"distance_m": 0.5`) at +10.3; cyan `940..1039,
  374..412` (`0.404`) at +12.7; cyan `309..479, 412..450` (`"Confirm"`) at +16.0; cyan
  `92..912, 602..640` (the OPERATOR line) at +18.0.
- Step labels Regular 32 ink at x 1120, 40 px leading, current line orange, earlier lines
  ink-dim: (1120, 150) `"Go." carries no distance` at +1.7; (1120, 190) `Nova Pro guesses 2 m`
  at +3.0; (1120, 230) `check fails: 2 > 0.5; grounded 0.18` at +5.4; (1120, 270) `GUIDE:
  re-plan` at +8.8; (1120, 310) `Nova Pro proposes 0.5 m` at +9.9; (1120, 350) `grounded 0.40:
  the unsure band` at +12.3; (1120, 390) `CONFIRM: the operator is asked` at +15.7; (1120, 430)
  `scripted operator: no` at +17.7.
- Caption Medium 36 ink at (1120, 520) `A guessed distance moved nothing.` at +20.5. Badge
  plate `1120..1480, 580..638`, lines at (1136, 588) and (1136, 614).
- Lower-third left plate `80..1030, 952..1008`, text at (112, 964) `Recorded run, 2026-10-22:
  the real decider judges Nova Pro`. Honesty label plate `1070..1840, 952..1008`, text at
  (1086, 964) `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`.
- VO at +0.3: I type: Go. Go carries no distance, so Nova Pro guesses two metres. The arithmetic check fails, grounded reads zero point one eight: Guide, re-plan. Nova Pro proposes half a metre. Grounded reads zero point four zero, inside the unsure band: Confirm, the operator is asked. The scripted operator says no. The car never moved on a guessed number.

### Shot 9 (auto, min 6.0)
- Card on bg. Title Medium 40 ink at (96, 72) `Measured on the real car`. Badge plate standard.
  Lower-third left `On the car, 2026-10-15`. Honesty label plate `1070..1840, 924..1008`, text
  at (1086, 932) `MEASURED ON THE CAR 2026-10-15, REAL DECIDER` and (1086, 966) `FRAMES
  WITHHELD: THEY SHOW A PERSON`.
- Centre lines (centred on x 960): Bold 48 ink at y 330 `On the car: a person in frame was
  denied in 456 ms` at +0.3; Menlo 40 ink at y 430 `person_in_frame   p = 0.9485` at +4.0;
  Regular 36 ink-dim at y 520 `whole gate 681 to 727 ms per hop; no motion event after the
  deny` at +6.5; Regular 26 ink-dim at y 600 `Source: docs/results/beats-car-2026-10-15-person-gate`
  at +8.5.
- Pointers: none.
- VO at +0.3: On the car, the same gate denied a hop with a person in frame in four hundred fifty six milliseconds. The frames stay private; they show a person.

### Shot 10 (auto, min 10.0)
- Asset: `docs/article/img/fig-portal-stage.png`, 1920x1080, placed 1:1, no push-in. At +7.5
  dim the image to 40 percent.
- Overlays: caption Medium 36 ink at (770, 18) `Row 3: person in frame -> Deny` on a plate
  `754..1250, 8..62` at +0.3. Quote card: plate `150..1110, 560..636` with a 4 px orange bar at
  x 150, text Medium Italic 44 ink at (176, 574) `"Someone is in front of me. I stopped."` at
  +5.0. Safety band: plate `0..1920, 450..610` and Bold 72 ink centred on x 960 at y 492
  `Physics stops the car. The decider explains.` at +7.5. Lower-third left `Pit Wall, the
  simulated car`. Honesty label plate `1300..1840, 952..1008`, text at (1316, 964) `SIM, FAKE
  DECIDER, DRAWN FIGURE`. No badge.
- Pointers: cyan arrow from (790, 440) to (1232, 352) at +1.0; cyan highlight `1234..1772,
  314..388` (CLASS and PROBABILITY chips) at +1.0; red highlight `1232..1540, 158..262` (the
  DENY word) at +2.5. The stop card `92 ms` is not marked.
- VO at +0.3: In the simulator, a figure in the frame is row three, a Deny, and the rover says why. Physics stops the car. The decider explains.

### Shot 11 (auto, min 10.0)
- Card on bg. Title Bold 56 ink at (96, 72) `Measured on the booth laptop: 72 timed calls`.
  Badge plate standard. Lower-third left `The numbers`. Honesty label plate `1480..1840,
  952..1008`, text at (1496, 964) `MEASURED 2026-10-22`.
- Headers Medium 32 ink from +0.3: orange square `96..116, 176..196` and text at (128, 170)
  `Strands Decider 2B, local`; from +5.8: ink-dim square `984..1004, 176..196` and text at
  (1016, 170) `Amazon Nova Pro on Bedrock`.
- Numbers, each counting up over 1.0 s from its `at` time, Bold 96 ink with the unit Regular
  36 ink-dim on the same baseline, and one line Regular 32 ink-dim beneath:
  +1.3: (96, 240) `462 ms`; (96, 350) `median, three questions in one request`.
  +3.4: (96, 440) `0 of 72`; (96, 550) `over the 1.5 s budget`.
  +7.1: (984, 440) `31 of 72`; (984, 550) `over the 1.5 s budget`.
  +9.5: (984, 640) `0.13 USD`; (984, 750) `per 1000 decisions`.
- Pointers: none.
- VO at +0.3: The local decider: four hundred sixty two milliseconds median, zero of seventy two over budget. Nova Pro on Bedrock: thirty one of seventy two over budget, thirteen cents per thousand decisions.

### Shot 12 (auto, min 10.7)
- Card on bg. Title Bold 64 ink at (96, 72) `Drop it into your own agent`. Badge plate
  standard. Lower-third left plate `80..1230, 952..1008`, text Menlo 26 ink at (112, 966)
  `github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands`. Honesty label
  plate `1330..1840, 952..1008`, text at (1346, 964) `FAKE DECIDER, STDOUT VERBATIM`.
- Row 1 at +0.3. Panel 1 header Medium 28 ink-dim at (96, 170) `three files, upstream names`;
  file tree Menlo 28 ink at x 96, y 220, 260, 300, 340, 380: `patterns/strands/`,
  `  _client.py`, `  tool_call_intervention.py`, `  frame_intervention.py`, `  README.md`.
  Panel 2 header at (616, 170) `three lines of wiring`; code Menlo 28 ink at x 616, y 220 + 40
  n:
  ```
  0 decider = Decider(timeout=1.5)
  1 agent = Agent(
  2     model=BedrockModel(model_id="us.amazon.nova-pro-v1:0",
  3                        region_name="us-east-1"),
  4     tools=[move],
  5     interventions=[MotionGate(decider)],
  6 )
  ```
  Highlights: cyan `915..1109, 216..252` (`timeout=1.5`) at +1.5; orange `679..1277, 416..452`
  (`interventions=[MotionGate(decider)]`) at +2.5.
- Row 2: header Regular 28 ink-dim at (96, 566) `make pattern-demo, against the fake decider
  (a script, not the model)` at +4.5. Terminal Menlo 24 ink at x 96, first line y 600, 32 px
  leading, typed from +4.5 over 2.0 s: lines 7 to 9 of `docs/video/build/clips/pattern-demo.txt`
  verbatim, wrapped at 118 characters with a two-space continuation indent (10 lines; line n at
  y 600 + 32 n). The wrap, for the coordinates below, is:
  ```
  00 {"tool": "move", "arguments": {"distance_m": 0.2, "heading_deg": 0.0}, "deterministic_check": "ok", "inside_envelope":
  01   0.95, "args_grounded": 0.95, "intent": "move_forward", "intent_p": 0.6, "verdict": "Proceed", "reason": "inside
  02   envelope p=0.95, grounded p=0.95", "latency_ms": 1.5}
  03 {"tool": "move", "arguments": {"distance_m": 2.0, "heading_deg": 0.0}, "deterministic_check": "distance_m 2 > 0.5",
  04   "inside_envelope": 0.05, "args_grounded": 0.05, "intent": "move_forward", "intent_p": 0.6, "verdict": "Guide",
  05   "reason": "outside envelope: distance_m 2 > 0.5", "latency_ms": 0.6}
  06 {"tool": "move", "arguments": {"distance_m": 0.2, "heading_deg": 0.0}, "deterministic_check": "ok", "verdict": "Deny",
  07   "reason": "decider unavailable: failing closed, no motion", "error": "no strands-decider at http://127.0.0.1:9
  08   (<urlopen error [Errno 61] Connection refused>). Start one with:\n    strands-decider serve
  09   StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8111", "latency_ms": 0.3}
  ```
  Highlights at +7.0: green `1161..1458, 628..660` (`"verdict": "Proceed"`); amber `1436..1704,
  724..756` (`"verdict": "Guide"`); red `1537..1791, 788..820` (`"verdict": "Deny"`); orange
  `1483..1733, 628..660` and `121..602, 660..692` (the row 1 reason, split over two lines);
  orange `121..822, 756..788` (row 2 reason); orange `121..967, 820..852` (row 3 reason).
- VO at +0.3: The pattern is a drop-in. Three files with the upstream names, three lines of wiring, and make pattern demo runs it offline against a fake decider.

### Shot 13 (fixed 4.0)
- 0.0 to 2.0: `docs/article/img/event-speaker-with-car.jpg` (1200x1600) fitted to height, place
  at `555..1365, 0..1080`, over a blur fill of itself (24 px, 35 percent). 2.0 to 4.0:
  `docs/article/img/event-hall.jpg` (1600x1200) fitted to height, place at `240..1680, 0..1080`,
  same fill. Hard cut between.
- Overlays: lower-third left `AWS Community Day Mumbai, 17 October 2026` from 0.0. No badge.
- VO at +0.3: Shown at AWS Community Day Mumbai.

### Shot 14 (auto, min 8.0)
- 0.0 to 0.3: black. Asset: `docs/article/img/cover.png` scaled to `0..1920, 0..1080` at 40
  percent brightness.
- Overlays, all centred on x 960, fading in together over 1.0 s from +0.4: Bold 56 ink at y 380
  `Physics stops the car. The decider explains.`; Menlo 48 cyan at y 470
  `github.com/Vivek0712/strands-robots-deepracer`; Regular 30 ink-dim at y 560 `Vivek Raja, AWS
  AI Hero  |  Article on AWS Builder Center`; Menlo 32 orange at y 620 `#strands-decider-2b
  #guardrails`. `docs/talk/deck/assets/logos/strands-mark.svg` rendered at 96x96, placed at
  `1728..1824, 912..1008`, with a violet glow (radius 24 px, 30 percent).
- Fade the whole frame to black over the last 0.5 s of the shot.
- VO at +0.4: Repo and article below. Physics stops the car. The decider explains.
