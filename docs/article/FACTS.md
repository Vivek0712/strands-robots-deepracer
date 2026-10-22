# FACTS for docs/article/article.md

Every number, date, name and claim in the article, with the file (and line or section) it comes
from. Paths are relative to the repo root. "notes NN" means `docs/talk/deck/sections/NN-*.notes.md`
(the deck's verified-sources files). Items marked **per author** are the author's own statements
from the writing brief and have no file in the repo; items marked **flag** are the ones the author
should check before publishing. Rewritten 2026-10-22 (round 1) for the merged article: one decision
section directly after the architecture, the canonical 13-row decision table from
`/private/tmp/.../canonical-decision.md` (lead's decision 2026-10-22, names from
`patterns/strands/tool_call_intervention.py` and `frame_intervention.py`), the text-question
benchmark, the limits and originality paragraphs.

## Front matter, title, byline

| Claim | Source |
|---|---|
| Title "Physical AI with Strands Decider 2B: a calibrated decision guardrail for every move an AWS DeepRacer agent makes" (114 characters); the earlier title "Physical AI on AWS DeepRacer: a rover that drives on natural language, judges every move, and answers to your voice" is the opening line of the body | author's instruction 2026-10-23: the hackathon theme is the Decider model |
| Description (471 characters, limit 512): the Strands pieces on one DeepRacer, the rule | brief; `docs/context/11-final-use-cases.md` lines 91-100 (the pillars). Trimmed 2026-10-22 from 509 characters by dropping "and gates and audits every motor command" |
| Byline "Vivek Raja, AWS AI Hero" | brief; notes 01 line 50 (Builder Center profile: AI Hero) |
| Series name "Strands on wheels", part 1 | **flag**: placeholder chosen by the writing team; the brief requires a series name and part number but does not give one |
| Tags: aws-deepracer, strands-agents, strands-decider-2b, amazon-bedrock, guardrails (five; `physical-ai` dropped to stay at five) | hackathon brief (`#strands-decider-2b` and `#guardrails` required, one pattern tag); notes 05 line 99 |
| Cover `img/cover.png`, 1200x675, no text; the inline `< COVER IMAGE >` marker stays because the Builder Center bundle (`publish/make_bundle.py`) places uploads by marker | brief; `docs/article/img/MANIFEST.md` (cover row) |

## Section 1: A rover that explains itself

| Claim | Source |
|---|---|
| Presented at AWS Community Day Mumbai, 17 October 2026 | **per author** (brief). The article does not say which beats ran live on stage. **flag** |
| Pen two metres on a side with a low lip | `docs/context/12-architecture.md` line 66; `docs/context/11-final-use-cases.md` line 64 |
| Screen shows the live frame and the verdict in large type | `docs/context/11-final-use-cases.md` line 17; `docs/context/12-architecture.md` line 48 |
| Figure callouts (Decider on the camera, strands-robots on the drive, deadman on the servos, Harness on the compute, Agents, Bidi, Box) | `docs/article/img/MANIFEST.md` (fig-deepracer-strands row); `docs/context/12-architecture.md` lines 10-21 |
| 20 cm hops; bounded hop at up to 0.3 m/s | `docs/context/11-final-use-cases.md` line 64; `docs/dev/CONTRACTS.md` lines 211-213 |
| Speaks each verdict (narrator), explains any stop from its audit record (why_stopped), reads a sign without obeying it (Sign), stops on its own when the router loses power (Pull the Plug) | `portal/backend/narrator.py` lines 1-9; `src/deepracer_agent/look.py` lines 7-10; `docs/context/11-final-use-cases.md` lines 67, 69 |
| "Physics stops the car; the decider explains." | `CLAUDE.md` (Read first); `docs/dev/CONTRACTS.md` line 353; `docs/context/12-architecture.md` line 103 |
| Pen lip, hop cap, on-car deadman, marshal's thumb on the drive-battery switch; none waits on a model | `docs/context/12-architecture.md` lines 65-66, 94-103; `docs/context/11-final-use-cases.md` lines 40-42 |

## Section 2: The architecture at a glance

| Claim | Source |
|---|---|
| Amazon Bedrock, us-east-1; Nova Pro `us.amazon.nova-pro-v1:0` is the agent's language model and the vision model behind `look` | `src/deepracer_agent/runtime.py` lines 40-42; `src/deepracer_agent/look.py` lines 3-4; `docs/dev/CONTRACTS.md` lines 84, 245 |
| Nova Sonic `amazon.nova-2-5-sonic` is the voice | `src/deepracer_agent/voice.py` lines 13, 64; notes 03 line 31 |
| Laptop runs the Agents runtime and tools, the decider gate with the local Decider 2B, the strands-robots layer, one shared camera stream, the Pit Wall | `docs/context/12-architecture.md` lines 13-20, 33-51; `src/deepracer_agent/camera.py` lines 1-12 |
| Travel router, car and laptop as its only clients; venue Wi-Fi with client isolation blocks laptop-to-car traffic | `docs/dev/networking.md` lines 58-64; `docs/context/12-architecture.md` line 22 |
| Architecture figure contents | `docs/article/img/MANIFEST.md` (fig-architecture row); `docs/context/12-architecture.md` lines 26-67 |
| Servo pairs on `/webserver_pkg/manual_drive` at 20 Hz for the hop; JSON over one rosbridge WebSocket on 9090; no ROS on the laptop | `docs/dev/CONTRACTS.md` lines 13, 18-20; `docs/context/12-architecture.md` line 11 |
| Heartbeat beside the servo pairs; MJPEG frames at 480x360 from the console; deadman state coming back | `docs/dev/CONTRACTS.md` lines 30-33, 95-96 |
| With the internet dead the decider, the gate and the text console still run | `docs/context/11-final-use-cases.md` lines 45-47, 95-96; `src/deepracer_agent/voice.py` lines 7-9 |

## Section 3: The decision I handed to Decider 2B

| Claim | Source |
|---|---|
| strands-labs/strands-decider announced 1 October 2026 | notes 01 line 45; notes 04 line 38 (blog datePublished 2026-10-01) |
| Decision model: pointer head, one forward pass; noul = P(true), choice = probability per option | notes 04 lines 32, 36, 72; `docs/context/03-strands-box-deciders-bidi.md` line 436 |
| Model `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` with `--vision` on the laptop | `docs/results/decider-benchmark-2026-10-14.md` lines 9-10; `docs/results/beats-car-2026-10-15-person-gate/README.md` lines 4-5 |
| PR #10 merged 3 October 2026, author Vivek0712, vision tower kept, no retraining; Qwen3.5-2B base ships with a vision tower | notes 04 lines 37, 41, 78; notes 01 line 67; `docs/context/11-final-use-cases.md` line 130 |
| The decision: before every `drive_deepracer` call, inside the briefed envelope, arguments grounded in what the user said, what is in front of the camera | `src/deepracer_agent/gate.py` module docstring; `patterns/strands/tool_call_intervention.py` lines 1-25, 68-100; canonical decision (lead, 2026-10-22) |
| Declared pattern Guardrails: "before a tool call, verify the arguments are grounded in what the user actually said" (the article adds "and what the camera sees") | hackathon brief, requirement 5 |
| Five questions in two requests to `POST /v1/systemone`, one forward pass each; request body `state`, `questions` (`noul` / `choice` with `instructions` and `criteria`), `images` | `patterns/strands/_client.py` (`Decider.ask`, lines 6-7 "one forward pass answers every question"); `src/deepracer_agent/decider_client.py` lines 15-36; `docs/context/03-strands-box-deciders-bidi.md` line 436 |
| Question names `inside_envelope`, `args_grounded`, `intent` (move_forward, turn, stop, question, unrelated) and their instruction and criteria text, verbatim in the first JSON block | `patterns/strands/tool_call_intervention.py` `QUESTIONS` (lines 68-93) |
| `person` and `frame` (clear, obstacle_near, person_in_frame, off_surface, unclear) and their text, verbatim in the second JSON block | `patterns/strands/frame_intervention.py` `FRAME_QUESTIONS`, `FRAME_CLASSES`; `src/deepracer_agent/gate.py` lines 58-66, 80-84 |
| The on-car tool takes linear, angular and duration; the drop-in uses distance and heading; the questions are the same | `src/deepracer_agent/gate.py` (`Envelope`, `GATED_TOOLS`); `patterns/strands/tool_call_intervention.py` (`move(distance_m, heading_deg)`); `src/deepracer_agent/gate.py` docstring rows 6, 9, 10, 12 and the `args_grounded` question at line 237 (verified 2026-10-22 after the code agent's round-1 change) |
| Gate-flow figure contents; caption 681 to 727 ms on the car | `docs/article/img/MANIFEST.md` (fig-gate-flow row); `docs/results/beats-car-2026-10-15-person-gate/README.md` lines 20, 26 |
| `Envelope.violations` writes `deterministic_check` into the state | `src/deepracer_agent/gate.py` lines 91-162 (`violations`, `envelope_context`); `patterns/strands/tool_call_intervention.py` (`MotionGate.state_for`) |
| With the check in the state the 2610 model answered all 140 envelope commands correctly; without it 110 of 140 | `docs/results/decider-benchmark-2026-10-14.md`, Results table (envelope as_gate 140/140, blind 110/140) and lines 93-97 |
| The 13-row decision table, its order, actions and reason strings; "rows are checked in this order" | canonical decision (lead, 2026-10-22), rows 1-13, from `patterns/strands/tool_call_intervention.py` (`MotionGate.decide`) and `frame_intervention.py` (`FrameGate`) |
| Row 7: on the car a failed envelope check is a Confirm; in the drop-in it is a Guide | `src/deepracer_agent/gate.py` docstring table ("envelope ... -> Confirm (operator)") and `Confirm(` at lines 640, 647; `patterns/strands/tool_call_intervention.py` lines 256-263 (Guide); canonical decision row 7 |
| Why the car confirms: the marshal at the screen may approve one bigger hop | canonical decision row 7 ("the marshal's thumb: the operator may approve a bigger hop"); `docs/dev/CONTRACTS.md` lines 152-159 (ApprovalBroker) |
| Thresholds YES 0.65, NO 0.35 (text), person 0.5, unclear 0.65, budget 1.5 s; between NO and YES is Confirm, below NO is Guide | `patterns/strands/tool_call_intervention.py` line 100 (`YES = 0.65`), lines 264-272 (strict `<` NO); `src/deepracer_agent/gate.py` line 69 (`UNCLEAR_THRESHOLD = 0.65`), line 549 (`deny_threshold=0.5`); `src/deepracer_agent/decider_client.py` (`DEFAULT_TIMEOUT_S = 1.5`) |
| Calibration: a person at desk distance read unclear at 0.58 to 0.67 on eleven real frames; the person yes/no now reads 0.95 on ten of them | `docs/results/decider-calibration-2026-10-14.md` lines 5, 14-15; `src/deepracer_agent/gate.py` module docstring |
| The drawn covered lens read unclear at 0.75 (not 0.90; 0.90 is the fake decider's fixed number) | `docs/results/decider-benchmark-2026-10-14.md` line 83 (hand_over_lens, 2610 column: unclear 0.75; `q2610.json` chosen_probability 0.7463); `docs/results/beats-sim-fastpub-2026-10-14/README.md` line 23 (fake 0.90) |
| A weak unclear below the bar proceeds and says so | `src/deepracer_agent/gate.py` lines 561-565; `patterns/strands/README.md` FrameGate table ("otherwise (clear, or a weak unclear)") |
| Never fails open: no frame or no decider -> Deny; malformed or late answer -> Deny; `on_error` is deny | `src/deepracer_agent/gate.py` lines 14, 23, 68, 578-581; `src/deepracer_agent/decider_client.py` lines 316-328 |
| Modes enforce / advisory / off; advisory shows the verdict with a would-have-stopped note; portal starts in advisory; command gate and deadman stand in every mode | `src/deepracer_agent/gate.py` lines 70-71, 568-573; `portal/backend/narrator.py` line 6 |
| Narrator speaks a fixed line the moment the verdict lands, before the language model answers; lines "Someone is in front of me. I stopped." and "I've lost my eyes. I will not drive blind." | `portal/backend/narrator.py` lines 1-9, 20-21 (verified verbatim 2026-10-22) |
| Benchmark machine Apple M4 Pro, 24 GB; date 14 October 2026 | `docs/results/decider-benchmark-2026-10-14.md`, Method ("Machine") and title |
| Envelope noul 141 ms p50 / 144 ms p95; frame choice 349 / 354; the two together 490 / 498; 5.4 GB | `docs/results/decider-benchmark-2026-10-14.md`, Results table, row 2B-qwen3.5-v1-2610 (141 + 349 = 490) |
| Adding the person yes/no to the frame request cost about 95 ms (450 ms p50 against 355 ms for the choice alone) | `docs/results/decider-calibration-2026-10-14.md` line 16 |
| On the car the full gate ran 681 to 727 ms per hop; a person was denied in 456 ms | `docs/results/beats-car-2026-10-15-person-gate/README.md` lines 18, 20, 26 |
| Every timed call under the 1.5 s fail-closed budget | `docs/results/decider-benchmark-2026-10-14.md`, paragraph under the Results table; `docs/results/decider-text-questions-2026-10-22.md` line 97 (0 of 72 over budget) |
| Text questions measured 22 October 2026 on the real 2B: 24 labelled utterance and tool-call pairs, 72 timed calls; 462 ms p50 / 498 ms p95 per three-question request; 0 of 72 over 1.5 s | `docs/results/decider-text-questions-2026-10-22.md` lines 12-19, 55-73, 95-98 |
| `args_grounded`: grounded cases at 0.78 or above, invented at 0.63 or below; 0 confident errors at 0.65/0.35; 6 unsure answers (two cases) to Confirm | `docs/results/decider-text-questions-2026-10-22.md` lines 12-18, 108, 192-195 |
| `inside_envelope` 69 of 72 right, 0 confident errors | `docs/results/decider-text-questions-2026-10-22.md` line 109 |
| `intent` 66 of 72; the `question` class never chosen; both misses ended in Guide through `args_grounded` | `docs/results/decider-text-questions-2026-10-22.md` lines 121-135 |
| Nova Pro (`us.amazon.nova-pro-v1:0`) on `args_grounded`: 69 of 72; 797 ms p50 / 4069 ms p95 at the client; 31 of 72 over 1.5 s; 391 ms p50 inside Bedrock; about 0.13 USD (0.1318) per 1000 decisions at list price (AWS Price List API, us-east-1, fetched 2026-10-22); local 2B 0 USD marginal after the laptop | `docs/results/decider-text-questions-2026-10-22.md` lines 19-22, 82-89, 164-186 |

## Section 4: strands-robots

| Claim | Source |
|---|---|
| Upstream provides the rosbridge transport, MobileBaseRobot, the command gate | `docs/context/12-architecture.md` lines 109-110, 115; `src/deepracer_agent/driver.py` lines 1-10 |
| DeepRacerRobot subclasses MobileBaseRobot | `src/deepracer_agent/driver.py` lines 1-10, 101-140 |
| Arming: `vehicle_state` state 0, then `enable_state` is_active true; 0 manual, 1 autonomous, 2 calibration | `docs/dev/CONTRACTS.md` lines 14-16; `CLAUDE.md` Non-negotiables; `src/deepracer_agent/driver.py` lines 34-49 |
| Bicycle model in `twist_to_servo`; Ackermann car cannot turn in place; yaw at rest refused with the reason | `src/deepracer_agent/driver.py` lines 52-80; `docs/dev/CONTRACTS.md` line 165 |
| Calibration: 0.3 m/s -> servo throttle 0.3; hop 0.5 s; max 2 s | `src/deepracer_agent/calibration.py` lines 57-63; `docs/dev/CONTRACTS.md` lines 211-213 |
| No watchdog on the car; 20 Hz for a bounded duration; zero pair from `finally`; heartbeat beside the stream | `docs/dev/CONTRACTS.md` lines 25-26, 95, 354; `docs/context/12-architecture.md` lines 82-86 |
| `strands_robots._command_gate` on every motion publish and service call; blocklist `/manual_drive`, `/vehicle_state`, `/enable_state`, `/cmd_vel`; interrupt for the operator's yes; audit row | `src/deepracer_agent/transport.py` lines 3-8, 213-220; notes 02 line 76; `CLAUDE.md` Non-negotiables |

## Section 5: Strands Agents

| Claim | Source |
|---|---|
| Codes against strands-agents >= 1.57.2 | `CLAUDE.md` Non-negotiables |
| Tools `drive_deepracer(linear, angular, duration)`, `stop_deepracer()` (never gated), `plan_deepracer`, `look(question)`, `why_stopped()`; `remember`, `metrics`, `blink_led` only talk | `docs/dev/CONTRACTS.md` lines 161-172; `src/deepracer_agent/plans.py` lines 741-752; `src/deepracer_agent/look.py` lines 3-10; `src/deepracer_agent/showtools.py` lines 1-10 |
| Interventions: `before_tool_call` returns Proceed, Guide, Confirm or Deny; the gate is a handler on `drive_deepracer` | notes 03 line 24; `src/deepracer_agent/gate.py` line 57 (`GATED_TOOLS`), 595-603 |
| ApprovalBroker: portal Approve and terminal `y` are one path | `docs/dev/CONTRACTS.md` lines 152-159; `src/deepracer_agent/runtime.py` lines 1-12 |
| Code excerpt `SIGN_RULE` | `src/deepracer_agent/prompts/__init__.py` lines 15-20 (verified verbatim 2026-10-22) |
| Sign card quoted aloud and declined; decider classifies it as a clear frame | `docs/context/11-final-use-cases.md` line 67; `docs/results/decider-benchmark-2026-10-14.md` lines 82, 87-89 |

## Section 6: Strands Bidi

| Claim | Source |
|---|---|
| Bidi general availability announced 5 October 2026 | notes 01 line 33; `docs/context/03-strands-box-deciders-bidi.md` lines 5, 677-678 |
| BidiAgent on Nova Sonic; gate attached through InterventionRegistry; same gated tools as the text console | `src/deepracer_agent/voice.py` lines 1-21 |
| Push-to-talk; PcmInputStream 16 kHz, 100 ms frames while held, paced silence; "stop" over the narration is a barge-in | `docs/context/11-final-use-cases.md` lines 35-37, 97; `docs/dev/CONTRACTS.md` lines 335-342 |
| BargeInStop hook on `BidiBargeInEvent` calls `stop_all` ahead of the model's own tool call | `src/deepracer_agent/gate.py` lines 807-856; `docs/results/voice-audio-2026-10-14.md` lines 70, 76-78 |
| `stop_all` to throttle PWM at neutral 22 ms (22.4) on the car | `docs/results/wheels-off-2026-10-14.md` line 206 |

## Section 7: Strands Harness

| Claim | Source |
|---|---|
| Strands harness shipped 21 September 2026; `create_harness` returns a plain `strands.Agent` with prompt, tools, memory, sandbox | notes 01 line 38; notes 03 lines 18-20 |
| Never the driving loop; the race engineer for Pit Stop; shell, read, write, edit in an `SshSandbox` on the car | `CLAUDE.md` Read first; `ops/race_engineer.py` lines 1-9, 84-104 |
| Reads the calibration file, compares with memory, reports the offset in nanoseconds, proposes the edit; the edit is refused until the operator confirms | `docs/results/pit-stop-2026-10-14/README.md` lines 13-19 |
| Code excerpt: Cedar shell forbid and write/edit forbid (the read permit, the write/edit permit and the restart/apt/reboot forbid omitted for length) | `ops/pit_stop.cedar` lines 15, 18-23, 39-43 (verified verbatim 2026-10-22) |
| `DEEPRACER_OPERATOR_CONFIRMED=1` read by the context enricher, set for one session | `ops/race_engineer.py` lines 55-61 |
| Pit Stop pre-recorded; a live SSH write over hall Wi-Fi is a risk not taken | `docs/context/11-final-use-cases.md` line 83 |

## Section 8: Strands Box

| Claim | Source |
|---|---|
| strands-agents/box v0.1.0 on 7 October 2026; Dogwood policies in Cedar syntax; default deny; enforced outside the process; decision records | notes 01 line 46; notes 04 lines 47-49, 82 |
| Box around the agent process; egress only to the car and Bedrock | `docs/context/12-architecture.md` line 21. **flag**: the repo records Box as optional on the laptop; the article presents it as part of the design per the author's brief |
| Egress panel beside the Simon Says kiosk, one line per outbound call with host and ms | `docs/results/kiosks-2026-10-14/README.md` line 35; `docs/dev/CONTRACTS.md` lines 301-303 |

## Section 9: Safety by physics

| Claim | Source |
|---|---|
| Pen with a low lip; hop cap 0.3 m/s for at most 2 s | `docs/context/12-architecture.md` lines 65-66, 100; `docs/dev/CONTRACTS.md` lines 211-213 |
| First publish to PWM 47 ms | `docs/results/wheels-off-2026-10-14.md` line 179 |
| Operator STOP ALL 35 ms (34.8); barge-in 22 ms (22.4) | `docs/results/wheels-off-2026-10-14.md` lines 204, 206 |
| Deadman: trip at > 300 ms gap; ten zero pairs on both motion topics; LED red; latched until 1 s of steady heartbeats; 278 ms (278.3) cut to PWM neutral on the car's clock | `docs/dev/CONTRACTS.md` lines 97, 99-104; `car/deadman/deepracer_deadman/deadman_logic.py` lines 22-26; `docs/results/wheels-off-2026-10-14.md` line 209 |
| Marshal's thumb on the drive-battery switch | `docs/context/12-architecture.md` lines 66, 101 |
| Safety ladder figure contents | `docs/article/img/MANIFEST.md` (fig-safety-ladder row); `docs/context/12-architecture.md` lines 92-103 |

## Section 10: The Pit Wall

| Claim | Source |
|---|---|
| FastAPI + WebSocket backend, React frontend; views Stage, Operator, Settings | `docs/dev/CONTRACTS.md` line 52; `portal/backend/app.py` lines 1-14; `portal/frontend/src/views/{Stage,Operator,Settings}.tsx` |
| Stage and Operator contents | `docs/context/11-final-use-cases.md` line 17; `docs/results/portal.md` lines 16-23; `docs/article/img/MANIFEST.md` (fig-portal-stage and fig-portal-operator rows: sim run on the fake stack, drawn stick figure, person_in_frame 0.97, DENY, stop card deny 92 ms, pending Confirm "outside the briefed envelope") |
| One event schema: one JSON object per line in events.jsonl, rebroadcast on the portal WebSocket; screen, `why_stopped` and `metrics` read the same rows | `docs/dev/CONTRACTS.md` lines 106-137; `src/deepracer_agent/look.py` lines 7-10; `src/deepracer_agent/showtools.py` lines 3-6 |

## Section 11: The show

| Claim | Source |
|---|---|
| Seven beats and what each shows (Pre-flight, Marshal, Apology, Blindfold, Sign, Red Light, Pull the Plug) | `docs/context/11-final-use-cases.md` lines 61-69 |
| Pre-flight checks battery, camera, link, calibration, PWM outputs, deadman heartbeat | `docs/dev/CONTRACTS.md` lines 129, 275-281 |
| Frame Judge and Simon Says kiosks; Pit Stop and Two Bodies pre-recorded; one stop all halts both bodies | `docs/context/11-final-use-cases.md` lines 75-84 |
| Event photos (three approved) and the testimonial placeholder | brief; `docs/article/img/MANIFEST.md` |

## Section 12: A pattern you can drop into your own agent

| Claim | Source |
|---|---|
| `patterns/strands/` with `_client.py`, `tool_call_intervention.py`, `frame_intervention.py`, `README.md`; names mirror upstream `examples/strands/`; `Decider.noul`, `Decider.choice`, `Decider.score`, `ask`, `health`, `ServerUnavailable`; `QUESTIONS`, `YES`, `MotionGate`, `FrameGate` | the files themselves (confirmed present 2026-10-22); hackathon brief ("Official upstream names to mirror") |
| Wiring snippet: `Decider(timeout=1.5)`, `MotionGate(decider)`, `Agent(..., interventions=[...])`; default model id `us.amazon.nova-pro-v1:0` (the same model the car's agent runs on), env `BEDROCK_MODEL_ID` | `patterns/strands/_client.py` (`Decider.__init__` `timeout` kwarg); `patterns/strands/tool_call_intervention.py` line 391 (`BEDROCK_MODEL_ID` default, verified 2026-10-22 after the code agent's round-1 change); `src/deepracer_agent/runtime.py` line 40 |
| `make fake-decider` serves `/v1/systemone` on 8111 from a label | `Makefile` lines 41-42 |
| `make pattern-demo` prints three rows (Proceed, Guide from the deterministic envelope check, Deny on a dead port); `make pattern-demo-frame` runs the drawn frames through FrameGate | `Makefile` lines 72-77; `patterns/strands/README.md` "Run it offline"; `patterns/strands/tool_call_intervention.py` `run_offline` |
| The fake decider is not a model | `patterns/strands/README.md` lines 77-78; `harness/fake_decider.py` |
| Notebook `notebooks/decider_gate_walkthrough.ipynb` (14 code cells, outputs saved) | the file (confirmed 2026-10-22); commit `5adec9d` |

## Section 13: Limits

| Claim | Source |
|---|---|
| The text questions were measured on the laptop, not on the car; on-car runs asked the envelope question and the frame pair | `docs/results/decider-text-questions-2026-10-22.md` (Setup); `docs/results/beats-car-2026-10-15-person-gate/README.md` lines 20-26 |
| No recorded gated hop on the real car returned Proceed and moved; every on-car gated hop was denied with the operator in frame | `docs/results/beats-car-2026-10-15-person-gate/README.md` lines 16-20 (hops 1 and 2 denied, person_in_frame 0.95); `docs/results/five-use-cases-2026-10-15.md` lines 13-14 ("still waiting on a clear pen") |
| Latencies measured on the booth laptop and over the travel router, not a phone hotspot or venue Wi-Fi | `docs/results/decider-benchmark-2026-10-14.md` (Method); `docs/results/beats-car-2026-10-15-person-gate/README.md` line 4 (car at a travel-router address); `docs/dev/networking.md` |
| Right on 6 of the 7 drawn frames | `docs/results/decider-benchmark-2026-10-14.md` line 11 |

## Section 14: What I learned

| Claim | Source |
|---|---|
| Decisions vs generations; calibration lets code act on confidence; the gate explains rather than stops | author's statements per the brief; the 0.65 bar from `docs/results/decider-calibration-2026-10-14.md` and benchmark line 83 |

## Section 15: Try it

| Claim | Source |
|---|---|
| strands-labs/robots; strands-labs/strands-decider with the `--vision` path from PR #10; strands-agents/harness-sdk hosts the Agents SDK, `strands.bidi` and `create_harness`; strands-agents/box | notes 02 lines 23-47; notes 04 lines 32, 41, 48; notes 03 lines 12, 17-20 |
| Project repo name strands-robots-deepracer; URL placeholder | `CLAUDE.md` title. Public URL not in the sources. **flag** |
| Beats run against a fake car and a fake decider | `docs/dev/CONTRACTS.md` lines 53, 190-205 |
| Built from 14 October 2026 in a private repository | `git log --date=short` (first commits 2026-10-14; no remote at the time of writing) |
| Earlier public repos `Vivek0712/aws_deepracer_control_v2` (HTTP console client, 2021) and `Vivek0712/strands-agentic-deepracer` (Strands + Nova planner, March 2026); measured motion constants, plan validator and MJPEG parser carried over; neither has strands-robots, the Decider gate, Bidi or Harness | `docs/context/07-prior-github-use-case-work.md` (table: dates 2021-02-21 to 2021-11-01 and 2026-03-10 to 2026-03-17; sections 2.1 constants, plan validator, `camera_stream.py`); `CLAUDE.md` Read first |
| Hackathon window opened 16 October 2026; runs to 23 October; three winners, $5,000 AWS credits each | notes 05 lines 91-103 |
| Demo video https://youtu.be/oMHml_LT_tY, 2:57 (177.3 s by ffprobe on docs/video/build/deepracer-decider-demo-v2.mp4), published 2026-10-23 | hackathon brief, requirement 4; YouTube |
| The rule sits in the module docstrings of the repo | `src/deepracer_agent/driver.py` lines 9-10, `gate.py` lines 18-19, `camera.py` lines 11-12, `connect.py` line 17, `look.py` line 9, `voice.py` line 9, `showtools.py` line 9, `portal/backend/narrator.py` lines 7-8 |

## Needed but not in the sources, therefore left out

- Which beats ran live on stage at AWS Community Day Mumbai, and attendance numbers.
- The public URL of this project repository, the Builder Center URL and the video URL.
- Whether Strands Box ran around the agent process on the stage laptop (`docs/context/12-architecture.md` line 21 records it as optional).
- A recorded Proceed hop on the real car under the gate (see Limits).
| Project repository URL `https://github.com/Vivek0712/strands-robots-deepracer` (public snapshot pushed 2026-10-22) | `git remote -v`; GitHub |
| Testimonials: Tanvi Patil (Associate Software Engineer, Accenture) and Ajay Kumar Yadav (AWS Community Builder, Associate Architect), LinkedIn posts of 2026-10-18 about the Mumbai session | Post text supplied by the author on 2026-10-22; activity ids 7518550541090885632 and 7518315061879328769 |
