# Shapes beat on the sim stack, 2026-10-14

One run of the booth beat "Shapes on request" (`beats/shapes.py`) against the fake car, fake
console and fake decider on the override ports (CONTRACTS section 3: rosbridge 9191, console 8190,
control 8192, decider 8211; no portal), with the live model (`us.amazon.nova-pro-v1:0` through
Bedrock, `AWS_PROFILE=heisenberg`, `us-east-1`). Headless pre-grant was set and is declared here:
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`, so every hop's approval row
says `by: pregrant`. Physics stops the car; the decider explains.

Command:

```
DEEPRACER_ROSBRIDGE_PORT=9191 DEEPRACER_CONSOLE_URL=http://127.0.0.1:8190 \
DEEPRACER_SIM_CONTROL_URL=http://127.0.0.1:8192 DECIDER_URL=http://127.0.0.1:8211 \
DEEPRACER_SIM_SHARED=<scratch>/shared.json .venv/bin/python -m harness.stack --deadman   # background
AWS_PROFILE=heisenberg AWS_DEFAULT_REGION=us-east-1 \
STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state <same four port vars> \
.venv/bin/python -m beats shapes --body sim --text
```

## Outcome: PASS, 6 of 6

| Step | Result |
|---|---|
| a 60 cm square plan was validated | `plan square 60 cm: ok: 8 steps, 4.27 m, 15.5 s, footprint 1.2 x 1.2 m, turn 360.0 deg` |
| the plan was narrated before the first hop | the model's narration (`plan_deepracer` result read back) precedes the first `drive_deepracer` command |
| every hop went through the gate | 8 hops, 8 frame verdicts (16 verdict rows: envelope + frame per hop) |
| hops were driven from the plan | 8 of 8 planned, exactly the `drive_calls` values: four `(0.3, 0.0, 2.0)` sides and four `(0.25, 0.8382, 1.874)` corners |
| the 1.5 m circle was refused by the validator | `plan circle 1.5 m: refused: footprint 1.50 x 1.50 m does not fit the usable pen 1.40 x 1.40 m (2 x 2 m minus a 0.3 m margin)` |
| no motion after the refusal | no `motion` event in the second turn |

Numbers from `events.jsonl` (171 events): operator text to `plan_deepracer` thought 1.7 s; operator
text to the eighth hop's command 28.1 s (the plan's own driving time is 15.5 s; the rest is nine
model round trips); the refusal turn 3.2 s end to end; fake-decider verdict latency 1-3 ms per
question. Nova Pro followed the plan tool's note to the letter: it narrated the plan in one
sentence, drove the eight entries of `drive_calls` in order with the exact values, said
"the square is complete", and on the refused circle repeated the validator's reason and did not
drive or propose a smaller circle.

The rover's lines, from the log:

- "The plan is: a square with 0.6 m sides and rounded corners (radius 0.30 m); 8 gated hops,
  4.27 m in 15.5 s, footprint 1.2 by 1.2 m. Each hop is one drive_deepracer call the gate checks
  first."
- "I will not drive a 1.5 m circle: footprint 1.50 x 1.50 m does not fit the usable pen
  1.40 x 1.40 m (2 x 2 m minus a 0.3 m margin)."

## Files

- `beats.log`: the beat's console (presenter lines and the pass/fail card).
- `beats.stderr.log`: logger output at INFO (model, transport, harness).
- `events.jsonl`: the run's event log (CONTRACTS section 4). Frames were the fake console's and
  are not kept.
- `stack.log`: the fake stack's log.

## Caveats

- The sim does not move, so "the square closes" is the bicycle model's claim, not a measurement;
  `tests/unit/test_plans.py` checks it on `SimPlatform` (heading 360 deg, back within 0.1 m of the
  start). On the car the direction sign and the real speed at throttle 0.3 are still unverified
  (CONTRACTS section 0), so the first floor run of a shape should be a 60 cm straight, then a
  square, with the marshal's thumb ready.
- The fake decider says `clear` for every frame here; the deny path of a plan (abandon at the
  first non-Proceed) is covered by the unit tests and by the Marshal beat's foot, not by this run.
