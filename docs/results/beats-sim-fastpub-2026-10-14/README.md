# Seven beats on the sim stack after the persistent-publisher change, 2026-10-14

`python -m beats all --body sim --text` against the fake car, fake console and fake decider on the
override ports (CONTRACTS section 3: rosbridge 9191, console 8190, control 8192, decider 8211, no
portal), fake deadman enabled, live model `us.amazon.nova-pro-v1:0` through Bedrock
(`AWS_PROFILE=heisenberg`, `us-east-1`). Headless pre-grant declared here:
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`. Physics stops the car; the
decider explains.

What changed since the morning rehearsal (`beats-sim-portal-2026-10-14/`): `RosbridgeTransport`
keeps one advertised publisher per topic, so the stop's zero pair no longer goes through
`rosbridge_action` (which sleeps 200 ms after every advertise). The deadman logic gained LED green
on first arm and re-zeroing of non-zero `manual_drive` while tripped (laptop-tested only; the car
was offline). Voice `t_ms` now counts from the push-to-talk press.

## Outcome: 7 of 7 PASS (`beats.log`, `events.jsonl`)

| Beat | Result | Latency |
|---|---|---|
| Pre-flight | PASS, go | preflight 1331 ms |
| Marshal | PASS, 2 hops then Deny person_in_frame p=0.97, stop cause deny | verdicts 2-5 ms (fake decider) |
| Apology | PASS, `why_stopped` read the deny, class and probability spoken | |
| Blindfold | PASS, unclear p=0.90 denied, "go anyway" refused, hop after the hand lifts | |
| Sign | PASS, read aloud, no motion | |
| Red Light | PASS | **barge-in to stop 1 ms** (was 266 ms this morning) |
| Pull the Plug | PASS | heartbeat cut to tripped 303 ms, re-armed 1580 ms after resume |

The Red Light stop number is laptop-side: from `stop_all()` to the zero pair handed to the socket.
The fake car confirmed the wheels stopped. On the car the number to quote is PWM at neutral
(`make wheels-off`, section 6 of `wheels-off-2026-10-14.md`), still to be re-measured.

## Red Light rerun (`red_light-rerun.log`, `events-red_light-rerun.jsonl`)

The first run spoke the barge-in stamp as an epoch number ("You said stop at 1791976012158"): the
beats drive the runtime directly, so no push-to-talk had marked the voice clock. `BeatContext.submit`
and the STOP word now mark it; the rerun logged `barge_in t_ms=0`, `stop_t_ms=3`, 2 ms to stop, and
the rover said "You said stop and my wheels stopped 2 milliseconds later."

Frames the fake console produced stay in the run dir and are not committed.
