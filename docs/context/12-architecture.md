# Architecture for the final use cases

Companion to report 11. Answers three questions: where each component runs, how a spoken
"go forward" becomes motion, and what is proven versus still to be built.

## Where things run

| Component | Runs on | Why there |
|---|---|---|
| ROS 2 Jazzy, ctrl_pkg, servo_pkg, camera_pkg, webserver, i2c (battery, LED) | DeepRacer (Intel Atom, 4 GB) | stock car software (community image) |
| `rosbridge_server` on port 9090 | DeepRacer | lets the laptop publish and call services without ROS installed on the Mac |
| **Deadman node** (new): zero servo if no heartbeat for 300 ms | DeepRacer | the only stop that survives laptop or link death; must be on the car |
| Strands Agent with drive, stop, look, battery, why_stopped tools | Laptop (Python 3.12) | needs strands-robots and Bedrock access |
| Decider `InterventionHandler` + `strands-decider serve` | Laptop GPU or small GPU box on the LAN | about 150 ms per question there; about 7 s on the car's CPU |
| strands-robots command gate, audit log, DeepRacer driver, rosbridge transport | Laptop | upstream code, 254 tests pass on this machine |
| Bidi voice agent (Nova Sonic, push-to-talk) | Laptop, audio over the internet to Bedrock | voice model is cloud-only |
| VLM for "what do you see" and sign reading (Nova Pro or Claude) | Bedrock | too large for anything local |
| Harness race engineer (`create_harness`, SSH sandbox to the car, Cedar policy) | Laptop, SSH into the car | shell and file tools act on the car; model stays off it |
| MuJoCo twin | Laptop | rehearsal before metal; fallback body |
| Screen contract (frame, thought, verdict, LED badge) | Laptop to the booth display | one UI for every beat |
| Strands Box (optional) | Laptop (macOS only in 0.1.x) | sandboxes the agent process; egress only to car and Bedrock |
| Travel router | Booth | own SSID; the rover is never on venue Wi-Fi |

## Diagram

```
                         CLOUD (Amazon Bedrock, us-east-1)
            Nova Sonic (voice)   Nova Pro / Claude (describe frame, read sign)
                      ^                        ^
                      |  only egress allowed   |
 ---------------------+------------------------+-------------------- travel router
                      |                        |
 LAPTOP (macOS, Python 3.12)
 +------------------------------------------------------------------+
 |  Bidi voice agent (PTT mic) --+                                   |
 |  Text kiosk / Strands CLI ----+--> Strands Agent                  |
 |                               |     tools: drive, stop, look,     |
 |                               |            battery, why_stopped   |
 |                               v                                   |
 |   Decider InterventionHandler (before_tool_call)                  |
 |     envelope ok?  frame class?  -> Proceed/Guide/Confirm/Deny     |
 |                               v                                   |
 |   strands-robots command gate (operator approval + audit log)     |
 |                               v                                   |
 |   DeepRacer driver (MobileBaseRobot, bicycle model, 20 Hz,        |
 |   trailing zero) -- rosbridge transport (roslibpy ws://car:9090)  |
 |                                                                   |
 |   Screen contract: live frame | thought | big verdict | LED badge |
 |   Harness (race engineer): SSH sandbox to car, Cedar policy       |
 |   MuJoCo twin (rehearsal, fallback body)                          |
 +------------------------------------------------------------------+
          ^ MJPEG https://car/route (camera)      | JSON over ws:9090
          |                                       v
 GPU BOX (optional)                     DEEPRACER (Ubuntu 24.04, ROS 2 Jazzy, Atom)
  strands-decider serve  <-- frames    +---------------------------------------+
  (~150 ms/question)                   | rosbridge_server :9090                |
                                       | NEW deadman node: zero servo if no    |
                                       |   heartbeat for 300 ms                |
                                       | ctrl_pkg (mode 0 manual, enabled)     |
                                       |   /webserver_pkg/manual_drive -->     |
                                       |   servo_pkg --> PWM --> steering+ESC  |
                                       | camera_pkg --> MJPEG via webserver    |
                                       | i2c battery, LED, calibration         |
                                       +---------------------------------------+
 PHYSICAL SAFETY (independent of all software)
  2x2 m low-lipped pen | hop cap 0.5 s at 0.3 m/s | drive-battery switch | marshal's thumb
```

## "Go forward for two seconds", end to end

1. Operator presses push-to-talk and speaks. Nova Sonic transcribes; the bidi agent calls
   `drive_deepracer(linear=0.3, angular=0.0, duration=2.0)`. "Back" is `linear=-0.3`.
   "Turn on the spot" is refused by the driver (Ackermann cannot yaw at rest) and the rover
   says so.
2. Decider gate (`before_tool_call`): `noul` "inside the briefed envelope?" and `choice` on
   the latest MJPEG frame `{clear, obstacle_near, person_in_frame, off_surface, unclear}`.
   About 150 ms each. Returns Proceed, Guide (slower re-plan), Confirm (ask a human) or
   Deny (refuse with reason, call stop). Fail closed on timeout or error.
3. strands-robots command gate: logs the command to the audit store; unless the slow
   envelope is pre-granted via `STRANDS_ROS2_COMMAND_ALLOW`, interrupts for operator
   approval (`y`/`yes`).
4. Driver: once per session calls `/ctrl_pkg/vehicle_state {state: 0}` then
   `/ctrl_pkg/enable_state {is_active: true}`; converts (linear, angular) to servo
   (angle, throttle) with the bicycle model; publishes `ServoCtrlMsg` on
   `/webserver_pkg/manual_drive` at 20 Hz for 2 s with a heartbeat topic alongside;
   publishes the zero pair in `finally`; reports a failed trailing stop as the drive's error.
5. Car: ctrl node relays to `/ctrl_pkg/servo_msg` only while mode is manual and enabled;
   servo node writes PWM. The deadman node zeroes the servos if the heartbeat stops.
6. Audit row written with timestamp, command, verdicts, approval and the frame; the screen
   shows it; "why did you stop?" reads it back.

## Stop paths and who owns them

| Stop | Trigger | Owner | Latency |
|---|---|---|---|
| Trailing zero | end of every drive | driver | immediate |
| Decider Deny | person, unclear, off-envelope | laptop | 300-700 ms end to end (measure in week 2) |
| Operator "stop" | voice barge-in or kiosk | bidi hook or gate | about 200-400 ms |
| Deadman | no heartbeat 300 ms (laptop crash, Wi-Fi loss, router pulled) | car | under 1 s |
| Pen lip and hop cap | any single move | physics | bounded travel |
| Drive-battery switch | marshal | physics | immediate |

The decider is the explanation layer. The last three rows are the safety layer.

## Proven today versus to build

| Piece | Status | Evidence |
|---|---|---|
| Gated drive/stop tools, numeric domains, trailing stop, audit | Proven upstream | 254 tests pass locally (report 05) |
| rosbridge transport and `RosbridgeRobot` | Proven upstream, live on a Gazebo rover | your PR #1110 (report 04) |
| HTTP control and MJPEG on this exact car | Proven March 2026 | report 07 |
| Bidi, decider, harness packages | Released, APIs documented | report 03, 08 |
| Manual-mode arming | **Bug upstream** (state 1 is autonomous) | report 00; fix is a one-line PR plus tests |
| On-car deadman node | **Does not exist** | week 1; upstreamable |
| rosbridge Ackermann driver (laptop side) | **Does not exist** (upstream class is rclpy-only) | week 2; `MobileBaseRobot` subclass |
| Decider intervention gate with frame class | **Not built** | week 2; API exists |
| Camera read tool, battery, LED | **Not built** | week 2; MJPEG parser reusable from report 07 |
| Registry entry, twin | **Not built** | week 3 or recorded |
| Stop-latency budget | **Unmeasured** | week 2 |

Nothing in the chain is research. Every unbuilt piece has a template upstream or in your
earlier repos, and the three blockers (mode bug, deadman, rosbridge Ackermann driver) are the
first two weeks of report 11's build order.
