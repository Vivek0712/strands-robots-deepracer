# Strands Decider 2B inside a Strands agent: the guardrails recipe

Tags: `#strands-decider-2b` `#guardrails`

Two drop-in intervention handlers that put a local Strands Decider 2B
(`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`) in front of a Bedrock agent's motion
tools. The files mirror `examples/strands/` in
[strands-labs/strands-decider](https://github.com/strands-labs/strands-decider).

| File | What it is |
|---|---|
| `_client.py` | stdlib `Decider`: `noul`, `choice`, `score`, `ask(state, questions, images=None)`, `health()`, `latency_ms`, `last_latency_ms`, `ServerUnavailable` |
| `tool_call_intervention.py` | `#guardrails`: `MotionGate` checks a proposed tool call against the user's words and the briefed envelope (`QUESTIONS`, `YES`) |
| `frame_intervention.py` | vision variant: `FrameGate` reads the camera frame before the hop (`FRAME_QUESTIONS`, also exported as `QUESTIONS`) |

## Install

```bash
pip install strands-agents strands-decider   # the agent framework and the decider server
pip install -e .                             # this project, for the demos and the fake services
```

The Bedrock demo needs AWS credentials with Amazon Bedrock model access in the environment
(`AWS_PROFILE` or the usual variables); the offline demo needs none.

## The typed questions

`MotionGate` asks all three in one request (one forward pass):

```json
{
  "inside_envelope": {"type": "noul",
    "instructions": "Is the proposed movement inside the envelope the operator briefed?",
    "criteria": {"true": "the distance and heading are within the briefed limits",
                 "false": "the movement exceeds a briefed limit or goes a way the briefing did not allow"}},
  "args_grounded": {"type": "noul",
    "instructions": "Are the tool's argument values grounded in what the user actually said?",
    "criteria": {"true": "every argument value traces back to something the user said",
                 "false": "an argument value was guessed or invented, not stated by the user"}},
  "intent": {"type": "choice",
    "instructions": "What did the user most recently ask the robot to do?",
    "criteria": {"move_forward": "drive straight ahead by some distance",
                 "turn": "change heading, with or without moving",
                 "stop": "stop, halt, wait, do not move",
                 "question": "ask something about the robot or the room; no movement requested",
                 "unrelated": "something that is not about the robot moving at all"}}
}
```

The state is `{"conversation": <the newest 12 messages, newest 2000 characters>, "command":
{"tool", "arguments"}, "envelope": <the briefed limits>, "deterministic_check": "ok" | <violations>}`.

`FrameGate` asks two over one JPEG (`images: [<base64>]`, server started with `--vision`):

```json
{
  "person": {"type": "noul", "instructions": "Is a person visible in the frame?",
    "criteria": {"true": "a person, or any part of a human body, is in the camera view",
                 "false": "no part of a person is in the camera view"}},
  "frame": {"type": "choice",
    "instructions": "What is directly in front of the car in this camera frame?",
    "criteria": {"clear": "the pen floor ahead is empty and the car can move",
                 "obstacle_near": "an object is close in front of the bumper",
                 "person_in_frame": "a person, or part of one (foot, leg, hand), is in the camera view",
                 "off_surface": "the car is at or past the edge of the pen surface",
                 "unclear": "the image is dark, blurred, blocked or otherwise unreadable"}}
}
```

## Wiring

```python
from strands import Agent
from strands.models import BedrockModel
from _client import Decider
from tool_call_intervention import MotionGate

agent = Agent(
    model=BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1"),
    tools=[move],
    interventions=[MotionGate(Decider(timeout=1.5))],
)
```

Add `FrameGate(Decider(timeout=1.5), frame_source=camera.latest_jpeg)` for vision. Both
handlers are `async def before_tool_call`: the blocking round trip runs in a worker thread
(`asyncio.to_thread`) under the gate's own `timeout` (1.5 s by default), so a hung decider
never blocks the agent's event loop or a voice stream on it. `before_tool_call` returns
`Proceed()`, `Guide(feedback=...)`, `Confirm(prompt=...)` or `Deny(reason=...)` and appends one
record (probabilities, verdict, reason, round trip in ms, on every row including a Deny) to
`gate.log`.

## Run it offline

```bash
make fake-decider          # http://127.0.0.1:8111, leave it running
make pattern-demo          # tool_call_intervention.py --offline
make pattern-demo-frame    # the drawn frames in harness/frames/ through FrameGate
```

`make pattern-demo` prints three rows: a grounded request (`Proceed`), a request whose
arguments exceed the envelope (`Guide`, from the deterministic check), and a decider that is
down (`Deny`, "decider unavailable"). `make pattern-demo-frame` runs the five drawn frames,
then no frame, then a dead decider through `FrameGate`. The fake decider speaks the wire
protocol but is not a model: it answers the grounding yes/no from the `deterministic_check`
line and the intent choice with `move_forward`. The real model answers from the words.

## Run it against a real decider and Bedrock

```bash
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8111
AWS_PROFILE=<profile> python patterns/strands/tool_call_intervention.py
```

The Bedrock demo sends "Move forward 20 centimetres." and "Go." to an eager agent, prints
each `Confirm` the gate raises and auto-answers it with `False` (a real operator answers
here), then prints the gate's log.

| Env | Meaning |
|---|---|
| `DECIDER_URL` | decider endpoint (default `http://127.0.0.1:8111`); upstream's `STRANDS_DECIDER_URL` is honoured as a fallback, and `--url` overrides both |
| `DECIDER_MODEL` | the `model` field sent with every request (default the 2610 checkpoint id) |
| `BEDROCK_MODEL_ID` | the Bedrock model the demo agent runs on (default `us.amazon.nova-pro-v1:0`) |

## Tuning the YES knob

`YES = 0.65` is the policy knob, owned by the code, not the model: at or above it a
confident yes, below `1 - YES` a confident no, between them a `Confirm`. Raise it to confirm
more: `MotionGate(decider, yes=0.8)`; the constructor refuses a value outside (0.5, 1). It
was measured on 2026-10-22 against the real 2B checkpoint
(`docs/results/decider-text-questions-2026-10-22.md`): grounded commands all scored 0.78 or
higher, invented ones 0.63 or lower, so 0.65 gives zero confident errors and sends the six
unsure answers to Confirm. Measure your own traffic the same way (`scripts/bench_text_questions.py`).

## Decision table

One table for both handlers and for the on-car gate (`src/deepracer_agent/gate.py`). Rows are
checked in this order; the first matching row is the action. Thresholds: `YES = 0.65`,
`NO = 0.35`, person 0.5, unclear 0.65, budget 1.5 s. The one deliberate on-car difference is
row 7.

| # | Condition | Action | Reason string |
|---|---|---|---|
| 1 | decider unreachable, timeout (> 1.5 s), malformed answer (missing key, probability outside [0, 1] or NaN, unknown class) | `Deny` | "decider unavailable" (text request) / "vision unavailable" (frame request) |
| 2 | no camera frame | `Deny` | "vision unavailable" |
| 3 | person >= 0.5, or frame class `person_in_frame` | `Deny` | "person in frame" |
| 4 | frame class `off_surface` | `Deny` | "off the surface" |
| 5 | frame class `unclear` with p >= 0.65 | `Deny` | "cannot see clearly" |
| 6 | intent `stop` with p >= 0.65 | `Deny` | "the user asked to stop" |
| 7 | deterministic envelope check fails (code, not the model) | drop-in: `Guide` "re-plan inside the envelope"; ON THE CAR: `Confirm` (the marshal's thumb: the operator may approve a bigger hop) | "outside envelope: <violations>" |
| 8 | `inside_envelope` < 0.35 | `Guide`: re-plan inside the envelope | "outside envelope per decider (p=...)" |
| 9 | `args_grounded` < 0.35 | `Guide`: ask the user for the values instead of inventing them | "arguments not grounded (p=...)" |
| 10 | intent `question` or `unrelated` with p >= 0.65 | `Guide`: answer the user instead of moving | "intent <x> (p=...)" |
| 11 | frame class `obstacle_near` | `Guide`: halve the speed and re-plan the hop | "obstacle_near (p=...)" |
| 12 | `inside_envelope` or `args_grounded` in [0.35, 0.65) | `Confirm`: ask the operator | "unclear: inside=... grounded=..." |
| 13 | otherwise | `Proceed` | "<class> (p=...)" / "inside envelope p=..., grounded p=..." |

Rows 1, 6 to 10, 12 and 13 are `MotionGate`'s; rows 1 to 5, 11 and 13 are `FrameGate`'s; the
on-car gate walks all thirteen over its two requests. `tests/unit/test_patterns.py` pins every
row, and a refusal table lists every input each gate refuses with the string it returns.

## What this is not

Physics stops the car: pen lip, hop cap, on-car deadman, the marshal's thumb on the
battery switch. None waits on a model. The decider explains: a stop becomes a class and a
probability, and a guessed argument is caught before the tool runs. A gate that cannot
reach its decider denies. The production version, with event log, cooldowns, warm-up and
calibration, is `src/deepracer_agent/gate.py`.
