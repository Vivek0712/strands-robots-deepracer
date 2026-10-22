# Two Bodies beat on the sim stack, 2026-10-14

One run of the recorded beat "Two Bodies" (`beats/two_bodies.py`): the same operator line to two
`AgentRuntime` instances at once, one on the fake car (rosbridge protocol, `harness.fake_car`) and
one on the kinematic twin (`deepracer_agent.twin.TwinTransport`), then "stop all" on both. Fake
console and fake decider on the override ports (CONTRACTS section 3: rosbridge 9291, console 8290,
control 8292, decider 8311; no portal), live model `us.amazon.nova-pro-v1:0` through Bedrock
(`AWS_PROFILE=heisenberg`, `us-east-1`). Headless pre-grant was set and is declared here:
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`, so both bodies' approval
rows say `by: pregrant`; the twin consults the same gate as the car. Physics stops the car; the
decider explains; the twin is a picture of the physics, never a safety layer.

Command:

```
DEEPRACER_ROSBRIDGE_PORT=9291 DEEPRACER_CONSOLE_URL=http://127.0.0.1:8290 \
DEEPRACER_SIM_CONTROL_URL=http://127.0.0.1:8292 DECIDER_URL=http://127.0.0.1:8311 \
DEEPRACER_SIM_SHARED=<scratch>/shared.json .venv/bin/python -m harness.stack --deadman   # background
AWS_PROFILE=heisenberg AWS_DEFAULT_REGION=us-east-1 \
STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state <same four port vars> \
DEEPRACER_RUN_DIR=<scratch>/run PORTAL_URL= .venv/bin/python -m beats two_bodies --body sim --text
```

## Outcome: PASS, 6 of 6

| Step | Result |
|---|---|
| both bodies started on one line | 3245 ms from the line to the second body moving; the twin's agent answered in 1.8 s, the fake car's in 2.8 s (two independent Nova round trips) |
| stop all halted sim within budget | 1 ms (`stop_all` wall time: zero pair on the persistent publisher, heartbeat off) |
| stop all halted twin within budget | 1 ms |
| twin pose moved then froze | 16.0 cm over 7 pose samples at 10 Hz, `v` back to 0.0, pose identical 300 ms later |
| a stop by the operator was logged for both bodies | `stop {cause: operator}` for `sim` (seq 47) and `twin` (seq 48), 1 ms apart |
| events for both bodies carry distinct body labels | `sim` (no stamp, the `--body` runtime) and `twin` (`body: twin` on every payload) |

Both agents heard "Hop forward twenty centimetres." and both called
`drive_deepracer(linear=0.3, duration=0.5)`: Nova took the default hop (15 cm at the cap) rather
than computing 0.67 s for 20 cm, on both bodies, from the same prompt. Both drives went through the
gate (envelope `Proceed` p=0.95, frame `clear` p=0.93, 1-3 ms each against the fake decider).

What the timeline says (`events.jsonl`, 54 events):

- 16:05:34.662 the twin's hop starts; 16:05:35.194 its ten messages are done and the trailing zero
  lands (`stop {cause: trailing_zero}`); the twin's pose trail reads 0.0, 3.2, 6.4, 9.6, 12.7, 15.9 cm
  then 15.95 cm with `v: 0.0`. 0.3 m/s for 0.532 s of wall time is 16 cm: the kinematic model agrees
  with the clock to the centimetre.
- 16:05:35.793 the fake car's hop starts (its model answer came 1.1 s later). 16:05:35.999 "stop all"
  lands on both: the fake car's stream is interrupted after 254 ms of a 500 ms hop (`motion end
  duration_s 0.254`, then its own trailing zero); the twin, already still, gets a second zero pair.
- 16:05:36.301 the twin's deadman trips 301 ms after `stop_all` stopped the heartbeat
  (`heartbeat {state: tripped}` then `stop {cause: deadman}`), exactly what the on-car node does
  after a Red Light stop; the fake car's did the same but the runtime closed before its 2 Hz echo.

So the stop landed mid-drive on the body that moved last, and the twin had already finished its hop
on its own trailing zero. With a 0.5 s hop and two independent model round trips, the two bodies
overlap only when the model latencies happen to match; the beat waits for both to be moving and
then stops 200 ms later, which is honest about that. A longer line ("roll for two seconds") would
show both interrupted; the line is kept at the hop because that is the showcase's envelope.

## What is kinematic and what is not

- The twin is a **pure kinematic bicycle model** (rear-axle reference: `x' = v cos yaw`,
  `y' = v sin yaw`, `yaw' = v tan(delta) / L`, Euler at 50 Hz) with the constants in
  `deepracer_agent.calibration` (wheelbase 0.164 m, 30 degree lock, throttle 0.3 = 0.3 m/s). It is
  the exact inverse of the driver's `twist_to_servo`, so what the driver sends for `linear=0.3` comes
  back as 0.3 m/s. Velocity is instantaneous: no slip, no ESC ramp, no tyre physics.
- **Not MuJoCo.** `import mujoco` fails in `.venv`; a kinematic twin was chosen on purpose for
  reliability (no renderer, no model file, deterministic in unit tests with an injected clock).
  Upstream's `yahboom_m3pro_twin.py` is the pattern (a transport that answers the graph from a
  model); the DeepRacer version answers the stock graph (`manual_drive`, `vehicle_state`,
  `enable_state`, `battery_level`, `get_calibration`, `set_led_state`, `deadman_state`).
- What **is** faithful to the car: relay only in mode 0 and enabled; `vehicle_state` disables and
  writes a zero pair; values outside [-1, 1] are dropped; **no watchdog** (a stream that stops holds
  the last value and the twin keeps rolling, `tests/unit/test_twin.py::test_no_watchdog_...`); the
  deadman is the on-car `deadman_logic.py` imported by path (300 ms trip, ten-zero burst as one
  value write, LED green/red/off, re-zero of a late non-zero command, 1 s steady resume).

## Files

- `beats.log`: the beat's console (presenter lines and the pass/fail card).
- `beats.stderr.log`: logger output at INFO (httpx, roslibpy, botocore), DEBUG lines dropped.
- `events.jsonl`: the run's event log (CONTRACTS section 4), both bodies in one file. The twin's
  events carry `body: twin` in the payload; its pose samples are `body` events with `x, y, yaw, v,
  t_ms`. Frames were the fake console's and are not kept.
- `stack.log`: the fake stack's log.

## Caveats

- Not run on the car today; `--body car` would put the real DeepRacer beside the twin with the same
  code path (the twin runtime is always `TwinTransport`, the other body is whatever `--body` says).
- `stop_all` latency here is the laptop's zero pair on a persistent publisher (1 ms); the car's
  stop-to-PWM number is the wheels-off record's (22-35 ms), not this run's.
- Report 11 keeps Two Bodies pre-recorded: a second body doubles the failure budget on stage.
