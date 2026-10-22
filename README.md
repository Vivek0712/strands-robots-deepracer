<p align="center">
  <img src="docs/article/img/cover.png" alt="A stock AWS DeepRacer on a lit grid with three Strands ribbons flowing from the Strands mark into the car" width="820">
</p>

<h1 align="center">Agentic AWS DeepRacer on strands-robots</h1>

<p align="center"><strong>A rover that drives on natural language, judges every move, and answers to your voice.</strong></p>

<p align="center">
  <a href="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml"><img src="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/strands--agents-%3E%3D%201.57.2-7c5cff" alt="strands-agents >= 1.57.2">
  <a href="https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"><img src="https://img.shields.io/badge/Strands%20Decider-2B%20qwen3.5--v1--2610-ff6b3d" alt="Strands Decider 2B"></a>
  <img src="https://img.shields.io/badge/Amazon%20Bedrock-Nova%20Pro%20%2B%20Nova%20Sonic-FF9900?logo=amazonwebservices&logoColor=white" alt="Amazon Bedrock">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-3fb950" alt="License Apache-2.0"></a>
  <a href="#hackathon-submission"><img src="https://img.shields.io/badge/Hackathon-Strands%20Decider%202B%20%2F%20%23guardrails-ffb347" alt="Hackathon: Strands Decider 2B / #guardrails"></a>
</p>

<p align="center"><a href="#quick-start"><b>Try it in 60 seconds</b></a> &nbsp;&middot;&nbsp; <a href="patterns/strands/README.md"><b>Copy the Decider pattern</b></a> &nbsp;&middot;&nbsp; <a href="docs/article/article.md"><b>Read the article</b></a> &nbsp;&middot;&nbsp; <a href="https://youtu.be/oMHml_LT_tY"><b>Watch the 3-minute demo</b></a></p>

<p align="center">
  <img src="docs/media/phase3-deviation.gif" width="49%" alt="The DeepRacer camera sees a toy car ahead, the vision planner replans with turn left to avoid the car ahead, then the real car steers left past it">
  <img src="docs/media/pitwall.gif" width="49%" alt="The Pit Wall on the fake stack: a clear hop proceeds, a drawn stick figure is denied as person_in_frame 0.97, an out-of-envelope command waits for Confirm, STOP ALL ends a run">
</p>
<p align="center"><sub>Left: the car's own camera sees a toy car, the planner replans, the real car steers left past it (phase-3 Nova vision planner, March 2026, before the Decider gate). Right: the Pit Wall: Proceed, Deny on a drawn person, Confirm, STOP ALL (sim, fake decider).</sub></p>

A stock AWS DeepRacer becomes a Strands robot. Upstream
[strands-labs/robots](https://github.com/strands-labs/robots) drives it over ROS 2 through
rosbridge and gates and audits every motor command. A Strands Agents loop on Amazon Bedrock turns
spoken or typed instructions into bounded movements, and before the wheels turn a local
**Strands Decider 2B** judges the command and the live camera frame. This repository is the
source, the measurements and the reusable Decider pattern behind the Builder Center article and
the hackathon entry. It was presented at AWS Community Day Mumbai on 17 October 2026.

## What it does

- **Drives on natural language.** "Go forward 20 centimetres" becomes one bounded hop at up to
  0.3 m/s through `drive_deepracer(linear, angular, duration)`; a named shape becomes a plan of
  small hops.
- **Judges every move with Decider 2B before the wheels turn.** Five typed questions in two
  requests per hop, answered as calibrated probabilities and mapped to the Strands interventions
  Proceed, Guide, Confirm and Deny. No frame or a slow decider means Deny: the gate fails closed.
- **Sees with the live frame.** One shared MJPEG stream feeds the gate, the `look` tool
  (Amazon Nova Pro) and the screen; a frame older than 2 s counts as no frame.
- **Speaks and listens.** Strands Bidi on Amazon Nova Sonic gives push-to-talk voice; a
  spoken "stop" over the rover's own narration is a barge-in that calls `stop_all`.
- **Is serviced by a race engineer.** A Strands Harness agent reaches the car through an SSH
  sandbox under a Cedar policy that forbids every motion topic.

**Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb). The decider
explains.** Nothing here presents the decider as the safety layer.

## Quick start: try it in 60 seconds (no car)

<a id="quick-start"></a>

Two commands run the guardrail offline: the fake decider speaks the `/v1/systemone` wire
protocol, and the pattern demo sends three tool calls through the gate.

```bash
make venv
make fake-decider          # terminal 1: http://127.0.0.1:8111
make pattern-demo          # terminal 2: Proceed, Guide (envelope), Deny (decider down)
```

The whole spine runs without the car. The fake car speaks the rosbridge protocol, the fake
console serves MJPEG, and the fake decider answers from the console's label:

```bash
make fake-car & make fake-console & make fake-decider & make portal &
make beat NAME=preflight BODY=sim
make unit && make sim && make lint
```

`make decider` starts the real Decider 2B on port 8111 (stop the fake first);
`make pattern-demo-frame` runs the drawn frames through the vision gate. Notebook:
`uv pip install --python .venv/bin/python -e '.[notebook]'` then
`.venv/bin/jupyter lab notebooks/`. With the car: `car/` has the deadman node, the camera guard,
the PWM-enable service and the install and rollback scripts;
[docs/dev/networking.md](docs/dev/networking.md) explains the travel router and
`DEEPRACER_HOST=auto`. Credentials live in `~/.config/deepracer/env` (see
`car/connect/env.example`), never in the repo. Then `make wheels-off` on a stand and `make pen` on
the floor with an operator present.

## The decision handed to Decider 2B

The pattern is **Guardrails**: before every `drive_deepracer` call, verify that the move is
inside the envelope the marshal briefed, that its argument values are grounded in what the user
actually said, and that the camera shows a floor the car may enter. The questions are typed, so
the answers are probabilities, not prose:

| Question | Type | Asked over |
|---|---|---|
| `inside_envelope` | noul (yes/no) | the tool call, the briefed envelope, the deterministic check |
| `args_grounded` | noul (yes/no) | the user's utterance beside the tool call |
| `intent` | choice | what the user asked for: move_forward, turn, stop, question, unrelated |
| `person` | noul (yes/no) | the latest 480x360 camera frame |
| `frame` | choice | the same frame: clear, obstacle_near, person_in_frame, off_surface, unclear |

The first request is the upstream System One shape (`POST /v1/systemone`) with the three text
questions; the second carries the JPEG and the two frame questions.

```json
{
  "state": {
    "conversation": "user: go forward twenty centimetres",
    "command": {"tool": "move", "arguments": {"distance_m": 0.2, "heading_deg": 0.0}},
    "envelope": "distance_m <= 0.5 per call, |heading_deg| <= 90",
    "deterministic_check": "ok"
  },
  "questions": {
    "inside_envelope": {"type": "noul", "instructions": "Is the proposed movement inside the envelope the operator briefed?",
                        "criteria": {"true": "the distance and heading are within the briefed limits",
                                     "false": "the movement exceeds a briefed limit or goes a way the briefing did not allow"}},
    "args_grounded": {"type": "noul", "instructions": "Are the tool's argument values grounded in what the user actually said?",
                      "criteria": {"true": "every argument value traces back to something the user said",
                                   "false": "an argument value was guessed or invented, not stated by the user"}},
    "intent": {"type": "choice", "instructions": "What did the user most recently ask the robot to do?",
               "criteria": {"move_forward": "drive straight ahead by some distance",
                            "turn": "change heading, with or without moving",
                            "stop": "stop, halt, wait, do not move",
                            "question": "ask something about the robot or the room; no movement requested",
                            "unrelated": "something that is not about the robot moving at all"}}
  }
}
```

<details>
<summary>The frame questions (second request, carries the image)</summary>

```json
{
  "state": {"command": {"tool": "move", "arguments": {"distance_m": 0.2, "heading_deg": 0.0}}},
  "images": ["<base64 JPEG, 480 by 360>"],
  "questions": {
    "person": {"type": "noul", "instructions": "Is a person visible in the frame?",
               "criteria": {"true": "a person, or any part of a human body, is in the camera view",
                            "false": "no part of a person is in the camera view"}},
    "frame": {"type": "choice", "instructions": "What is directly in front of the car in this camera frame?",
              "criteria": {"clear": "the pen floor ahead is empty and the car can move",
                           "obstacle_near": "an object is close in front of the bumper",
                           "person_in_frame": "a person, or part of one (foot, leg, hand), is in the camera view",
                           "off_surface": "the car is at or past the edge of the pen surface",
                           "unclear": "the image is dark, blurred, blocked or otherwise unreadable"}}
  }
}
```

</details>

The numeric bound stays in code (`Envelope.violations`) and goes into the state as
`deterministic_check`: in the benchmark the booth model, 2610, answered all 140 envelope
questions correctly with that line present and 110 of 140 (79 percent) without it
([docs/results/decider-benchmark-2026-10-14.md](docs/results/decider-benchmark-2026-10-14.md)).
Code compares the probabilities to thresholds (`YES = 0.65`, `NO = 0.35`, person 0.5,
unclear 0.65, budget 1.5 s) and maps them to the four interventions. The rows are checked in this
order; the first matching row is the action.

<details>
<summary>The decision table (13 rows, checked in order)</summary>

| # | Condition | Action | Reason string |
|---|---|---|---|
| 1 | decider unreachable, timeout (> 1.5 s), malformed answer (missing key, probability outside [0, 1] or NaN, unknown class) | Deny | "decider unavailable" (text request) / "vision unavailable" (frame request) |
| 2 | no camera frame | Deny | "vision unavailable" |
| 3 | person >= 0.5, or frame class person_in_frame | Deny | "person in frame" |
| 4 | frame class off_surface | Deny | "off the surface" |
| 5 | frame class unclear with p >= 0.65 | Deny | "cannot see clearly" |
| 6 | intent stop with p >= 0.65 | Deny | "the user asked to stop" |
| 7 | deterministic envelope check fails (code, not the model) | drop-in: Guide "re-plan inside the envelope"; on the car: Confirm (the marshal's thumb: the operator may approve a bigger hop) | "outside envelope: <violations>" |
| 8 | inside_envelope < 0.35 | Guide: re-plan inside the envelope | "outside envelope per decider (p=...)" |
| 9 | args_grounded < 0.35 | Guide: ask the user for the values instead of inventing them | "arguments not grounded (p=...)" |
| 10 | intent question or unrelated with p >= 0.65 | Guide: answer the user instead of moving | "intent <x> (p=...)" |
| 11 | frame class obstacle_near | Guide: halve the speed and re-plan the hop | "obstacle_near (p=...)" |
| 12 | inside_envelope or args_grounded in [0.35, 0.65) | Confirm: ask the operator | "unclear: inside=... grounded=..." |
| 13 | otherwise | Proceed | "<class> (p=...)" / "inside envelope p=..., grounded p=..." |

</details>

The on-car gate (`src/deepracer_agent/gate.py`) and the drop-in library (`patterns/strands/`)
ask the same five questions and map them the same way; they differ only on row 7, where the car
hands a failed envelope check to the marshal as a Confirm and the library sends the model back
with a Guide. The moment a Deny lands the narrator speaks a fixed line from
`portal/backend/narrator.py`: "Someone is in front of me. I stopped." for a person, "I've lost my
eyes. I will not drive blind." for unclear. Full tables, thresholds and the YES knob:
[patterns/strands/README.md](patterns/strands/README.md).

Measured on the booth laptop (Apple M4 Pro, 24 GB, MPS) with
`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision`
([benchmark](docs/results/decider-benchmark-2026-10-14.md)): envelope noul 141 ms p50 / 144 ms
p95, frame choice 349 / 354 ms, the two together 490 / 498 ms, 5.4 GB, healthy about 10 s after
start, right on 6 of the 7 drawn frames. Adding the person yes/no to the frame request cost about
95 ms ([calibration](docs/results/decider-calibration-2026-10-14.md)). On the car with the frame
pair in the gate, a person was denied in 456 ms and the whole gate took 681 to 727 ms per hop
([beats-car-2026-10-15-person-gate](docs/results/beats-car-2026-10-15-person-gate/README.md)).
The three text questions on the real 2B decider, 24 labelled utterance and tool-call pairs, 72 timed calls
([decider-text-questions-2026-10-22.md](docs/results/decider-text-questions-2026-10-22.md)):
462 ms p50 / 498 ms p95 per three-question request, 0 of 72 over the 1.5 s budget; `args_grounded`
read grounded cases at 0.78 or above and invented ones at 0.63 or below, so `YES = 0.65` gave 0
confident errors and 6 unsure answers went to Confirm; `inside_envelope` 69/72, `intent` 66/72
(the `question` class is never chosen; both misses still ended in Guide via `args_grounded`).
Amazon Nova Pro (`us.amazon.nova-pro-v1:0`) on the same `args_grounded` question: 69/72 right,
797 ms p50 / 4069 ms p95 at the client with 31 of 72 calls over the 1.5 s budget (391 ms p50
provider-side, so the tail is the network), about 0.13 USD per 1000 decisions at list price; the
local 2B is 0 USD marginal after the laptop.

## Reusable pattern

The gate is a drop-in for any Strands agent with a tool that moves something. The library in
`patterns/strands/` mirrors the upstream `strands-decider` example names (`_client.py`,
`tool_call_intervention.py`, `frame_intervention.py`, `README.md`) so the wiring is easy to
recognise. The library's `main()` defaults to Amazon Nova Pro, the model the car's agent runs on,
and reads `BEDROCK_MODEL_ID` to change it.

```python
from strands import Agent
from strands.models import BedrockModel
from patterns.strands._client import Decider
from patterns.strands.tool_call_intervention import MotionGate

decider = Decider(timeout=1.5)  # strands-decider serve <model> --vision --port 8111, or make fake-decider
agent = Agent(
    model=BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1"),
    tools=[move],                      # stop tools are never gated
    interventions=[MotionGate(decider)],
)
```

Add `FrameGate(decider, frame_source=camera.latest_jpeg)` for the vision questions. Every
verdict lands in the log with its probabilities, reason and round trip in ms. Index:
[patterns/README.md](patterns/README.md); questions, thresholds and refusal tables:
[patterns/strands/README.md](patterns/strands/README.md); step by step:
[notebooks/decider_gate_walkthrough.ipynb](notebooks/decider_gate_walkthrough.ipynb); the
production gate: [src/deepracer_agent/gate.py](src/deepracer_agent/gate.py).

## Architecture

<p align="center">
  <img src="docs/article/img/fig-architecture.png" alt="Architecture: Amazon Bedrock with Nova Pro and Nova Sonic; the laptop with the Strands agent, the decider gate, strands-robots and the Pit Wall; a travel router; the DeepRacer with rosbridge, ctrl and servo nodes, the deadman node and the camera" width="900">
</p>

Three places do the work. Amazon Bedrock (us-east-1) hosts Nova Pro, the agent's language and
vision model, and Nova Sonic, the voice. The laptop runs everything that reasons: the Strands
Agents runtime and tools, the decider gate with the local Decider 2B, the strands-robots driver,
one shared camera stream and the Pit Wall. The car runs its stock ROS 2 image plus a deadman
node that zeroes the servos 300 ms after the last heartbeat, the one stop that survives the
laptop, the link and the router.

### The Strands stack

<p align="center">
  <img src="docs/media/strands-stack.svg" alt="Six cards: Strands Agents, strands-robots, Strands Decider 2B, Strands Bidi, Strands Harness, Strands Box, each with its role" width="1000">
</p>

| Piece | Role here | Where |
|---|---|---|
| Strands Agents | the loop on Bedrock: `drive_deepracer`, `stop_deepracer`, `look`, `plan_deepracer`, `why_stopped`; interventions on every tool call | [strands-agents/sdk-python](https://github.com/strands-agents/sdk-python), `src/deepracer_agent/runtime.py` |
| strands-robots | `MobileBaseRobot` subclass over rosbridge: arming, bicycle model, 20 Hz publish with heartbeat, command gate and audit | [strands-labs/robots](https://github.com/strands-labs/robots), `src/deepracer_agent/driver.py` |
| Strands Decider 2B | the typed questions before every hop, served locally with `--vision` | [strands-labs/strands-decider](https://github.com/strands-labs/strands-decider), `src/deepracer_agent/gate.py`, `patterns/strands/` |
| Strands Bidi | `strands.bidi` on Nova Sonic: push-to-talk, barge-in calls `stop_all` | `src/deepracer_agent/voice.py` |
| Strands Harness | `create_harness` race engineer with an SSH sandbox on the car and a Cedar policy | [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk), `ops/race_engineer.py`, `ops/pit_stop.cedar` |
| Strands Box | the fence around the agent process; the kiosk shows its egress log | [strands-agents/box](https://github.com/strands-agents/box) |

The same strands-robots library drives the upstream Curiosity rover in MuJoCo
(`docs/media/curiosity.gif`), the twin body the Two Bodies beat moves the agent to.

## Pit Wall

One screen for every beat, the same for the fake car and the real one: live frame with the
frame class, the thought in flight, the verdict in large type, an audit column, Approve and Deny
when a Confirm is pending, and STOP ALL. Details in [portal/README.md](portal/README.md).

<p align="center">
  <img src="docs/article/img/fig-portal-stage.png" width="49%" alt="Pit Wall Stage view: the frozen frame judged person_in_frame 0.97, the DENY verdict card, the stop card and the controls">
  <img src="docs/article/img/fig-portal-operator.png" width="49%" alt="Pit Wall Operator view: pre-flight, maneuver shapes, gate mode, a pending Confirm with Approve and Deny, STOP ALL and the audit column">
</p>
<p align="center"><sub>Left, Stage: a Deny on a drawn person, with the reason and its latency. Right, Operator: a Confirm waiting for a human, gate mode, pre-flight.</sub></p>

## Safety by physics

<p align="center">
  <img src="docs/article/img/fig-safety-ladder.png" alt="Six safety layers with measured numbers: pen and hop cap, command gate 47 ms, on-car deadman 278 ms, STOP ALL 22 ms and operator stop 35 ms, decider gate 681 to 727 ms, the marshal's thumb" width="900">
</p>

- The pen has a low lip; a hop is at most 0.3 m/s for at most 2 s.
- Every drive publishes a zero servo pair from `finally`; the car has no watchdog of its own.
- The on-car deadman zeroes the servos when the heartbeat stops: 278 ms from the cut to PWM
  neutral, measured on the car's clock.
- Operator STOP ALL reaches PWM neutral in 35 ms, a voice barge-in in 22 ms.
- The marshal's thumb is on the drive-battery switch.

The decider sits above all of that. It explains a stop; it is never what makes one happen.
The numbers are in [docs/results/wheels-off-2026-10-14.md](docs/results/wheels-off-2026-10-14.md).

## Limits

Not measured yet: the three text questions on the car (they were measured on the laptop; the
on-car runs asked the envelope question and the frame pair), a gated hop on the real car that returned
Proceed and moved (every on-car gated hop in `docs/results` was denied with the operator in
frame; a clear-pen run is next), and latency over a phone hotspot or venue Wi-Fi. The 2B model
misread 1 of the 7 drawn benchmark frames. The fake decider is a script, so a Proceed from it
proves the wiring and not the model.

## Repository layout

| Path | What |
|---|---|
| `src/deepracer_agent/` | laptop side: rosbridge Ackermann driver, heartbeat, tools, decider gate, voice, runtime, event log |
| `patterns/` | the reusable Decider 2B pattern library; `patterns/strands/` mirrors the upstream example names |
| `notebooks/` | `decider_gate_walkthrough.ipynb`: the gate against the fake decider, step by step |
| `hackathon/` | the submission text, the rubric mapping, the scanner and the review log |
| `car/` | on-car: deadman node, camera guard, PWM enable, systemd units, install and rollback over SSH |
| `portal/` | Pit Wall: FastAPI + WebSocket backend, React frontend (built output committed), kiosks |
| `harness/` | fake car (rosbridge protocol), fake console (MJPEG + API), fake decider |
| `beats/` | the seven beats, `--body sim` or `--body car` |
| `ops/` | the Harness race engineer and its Cedar policy |
| `tests/` | `unit`, `sim`, `car` (wheels off), `pen` |
| `scripts/` | maintainer helpers |
| `docs/context/` | research bundle and decisions; `docs/dev/CONTRACTS.md` is the integration contract |
| `docs/results/` | every measured number with the command that produced it |
| `docs/article/` | the Builder Center article and its figures |
| `docs/media/` | the GIFs and the stack figure used by this page |
| `.github/` | CI (ruff, unit, sim on every push and PR), issue template |
| `.claude/` | the read-only review agents used for the hackathon review rounds |
| `.kiro/` | steering, the guardrail-pattern spec and hooks for Kiro sessions |
| `.krewhq/` | optional maintainer context tooling (not needed to run anything) |

## Hackathon submission

Agent Experience Hackathon: Strands Decider, AWS Builder Center. Decision pattern:
**Guardrails**. Tags: `#strands-decider-2b` `#guardrails`. Submission text:
[hackathon/SUBMISSION.md](hackathon/SUBMISSION.md); rubric mapping:
[hackathon/RUBRIC.md](hackathon/RUBRIC.md); review log:
[hackathon/REVIEW-LOG.md](hackathon/REVIEW-LOG.md).

| Deliverable | Status |
|---|---|
| Article | [docs/article/article.md](docs/article/article.md); Builder Center link pending publication |
| Demo video | [youtu.be/oMHml_LT_tY](https://youtu.be/oMHml_LT_tY) (2:57) |

This agent is new: built from 14 October 2026 in a private repository and first published for
this submission. Two earlier public repositories, `Vivek0712/aws_deepracer_control_v2` and
`Vivek0712/strands-agentic-deepracer`, are its seeds (measured motion constants, plan validator,
MJPEG parser; see
[docs/context/07-prior-github-use-case-work.md](docs/context/07-prior-github-use-case-work.md));
neither has the strands-robots body, the Decider gate, the Bidi voice or the Harness engineer.

## Seen live

<p align="center">
  <img src="docs/article/img/event-car-on-stage.jpg" alt="The DeepRacer on the AWS plinth on stage at AWS Community Day Mumbai" width="640">
</p>

Presented at AWS Community Day Mumbai, 17 October 2026: the rover in its pen, the Pit Wall on
the big screen, and the seven beats (Pre-flight, Marshal, Apology, Blindfold, Sign, Red Light,
Pull the Plug). More in [docs/article/article.md](docs/article/article.md).

## Docs

- Start here: [docs/context/12-architecture.md](docs/context/12-architecture.md) and the
  integration contract [docs/dev/CONTRACTS.md](docs/dev/CONTRACTS.md); the research bundle index
  is [docs/context/00-README.md](docs/context/00-README.md)
- Decider: [benchmark](docs/results/decider-benchmark-2026-10-14.md),
  [calibration](docs/results/decider-calibration-2026-10-14.md),
  [gate flow](docs/article/img/fig-gate-flow.png)
- Measured results index: [docs/results/README.md](docs/results/README.md)
- Portal: [portal/README.md](portal/README.md), [docs/results/portal.md](docs/results/portal.md)
- Harness: [docs/context/08-harness-sdk.md](docs/context/08-harness-sdk.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md); security: [SECURITY.md](SECURITY.md);
  cite with [CITATION.cff](CITATION.cff)

## License

Apache License 2.0, copyright 2026 Vivek Raja. See [LICENSE](LICENSE).
