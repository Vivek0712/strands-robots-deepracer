# Decision recipes for Strands agents

Tags: `#strands-decider-2b` `#guardrails`

Reusable Strands Decider 2B decision patterns: the typed question and option set, the
wiring that puts it in the agent's path (a Strands `InterventionHandler`), and a note on
how to use it. Each recipe is a single file you copy into your own project. The layout
mirrors `examples/strands/` in
[strands-labs/strands-decider](https://github.com/strands-labs/strands-decider), so the
client and the handlers are interchangeable with the upstream example.

## Recipes

| Pattern tag | File | Question types | When to use |
|---|---|---|---|
| `#guardrails` | `strands/tool_call_intervention.py` (`MotionGate`) | `noul` inside_envelope, `noul` args_grounded, `choice` intent | before a tool call with physical or financial effect: verify the arguments are grounded in what the user said and inside the limits the operator briefed |
| `#guardrails` (vision) | `strands/frame_intervention.py` (`FrameGate`) | `noul` person, `choice` over five frame classes, one image | before a motion tool when a camera is available: stop on a person, the edge of the surface or a blind camera; slow down for an obstacle |
| client | `strands/_client.py` (`Decider`) | builds all three (`noul`, `choice`, `score`) | any Strands agent that talks to a `strands-decider serve` endpoint with the standard library only |

`strands/README.md` has the questions written out as JSON, the decision table, the
offline and live run instructions and the tuning knob.

## Drop-in procedure

1. Copy `patterns/strands/_client.py` and the recipe file next to your agent. Both need
   only `strands-agents` (`pip install strands-agents`); the client is `urllib` and `json`.
2. Edit the questions and the envelope to your tool: the question names are the keys you
   read answers from, the `criteria` descriptions are where the signal is, and `YES` is
   the policy knob your code owns.
3. Register the handler and run a decider (AWS credentials with Bedrock access in the
   environment):

   ```python
   from strands import Agent
   from strands.models import BedrockModel
   from _client import Decider
   from tool_call_intervention import MotionGate

   agent = Agent(
       model=BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1"),
       tools=[your_tool],
       interventions=[MotionGate(Decider(timeout=1.5))],
   )
   ```

   ```bash
   pip install strands-decider
   strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8111
   ```

Without a decider, `make fake-decider` then `make pattern-demo` and `make pattern-demo-frame`
run both recipes end to end on this laptop.

## Decision table

Rows are checked in this order; the first matching row is the action. The same table runs
on the car (`src/deepracer_agent/gate.py`), with one deliberate difference on row 7.
Thresholds: `YES = 0.65`, `NO = 0.35`, person 0.5, unclear 0.65, budget 1.5 s.

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

## The production version

`src/deepracer_agent/gate.py` is the same five questions as they run on the AWS DeepRacer:
one handler, two requests per hop (the three text questions in one forward pass, the two
frame questions in another), an event log every verdict is written to with its latency, a
per-request timeout with a cooldown after a slow answer, a warm-up so the first hop is not
cold, operator modes (enforce, advisory, off) and the thresholds from the calibration study
in `docs/results/`. Start from the recipe; graduate to the gate when you need the record.

Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb). The decider
explains.
