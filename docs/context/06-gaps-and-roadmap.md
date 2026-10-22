# Gaps and roadmap

Synthesized from reports 01 (§12, 13 gaps with plug-in points), 02 (§6, §7, §9), 03 and
04. Each gap names where it plugs in and which upstream rule binds it. The build order
at the end is the proposed plan, not a commitment; nothing below has been started.

## A. Upstream fixes to ship first (small PRs, high leverage)

1. **Manual-mode handshake sends the wrong state.** `AckermannRosRobot.from_deepracer()`
   (`strands_robots/drivers/ros/ackermann_robot.py:253-282`) sends
   `/ctrl_pkg/vehicle_state state=1`. On the car `1` is autonomous (`ctrl_node.cpp`
   `enum CtrlState { manual, autonomous, calibration }`; webserver uses
   `0 if drive_mode == "manual" else 1`). Fix: `state=0`, update the docstring, update
   the wiring pins in `tests/mesh/test_ackermann_robot.py:92, 118, 156` (all assert
   `{"state": 1}`) and the gate-order test,
   add `changelog.d/<pr>-deepracer-manual-mode-is-state-zero.md` written as a
   behavioural fix with the before/after table AGENTS.md asks for. Risk statement for
   the fragment: with a model loaded, the old handshake would start autonomous driving
   when `enable_state true` followed.
2. **QoS-adaptive `echo` for BEST_EFFORT topics.** `/rplidar_ros/scan` is BEST_EFFORT;
   `use_ros echo` and `get_scan_*` subscribe RELIABLE and receive nothing. The design
   and plan exist (`~/strands-robots-cont/docs/superpowers/specs/2026-07-02-use-ros-qos-params-design.md`,
   branch `fix/use-ros-echo-qos`). Rebase onto main (transports moved to
   `strands_robots/ros.py`), re-run the refusal tables, open the PR. The params PR
   (`param_list/get/set`) can follow separately.
3. **Docs polish.** `docs/learn/ros2.md:79` and `docs/learn/mesh/bridges.md:71` still
   place the mobile bases in `strands_robots.mesh`; AGENTS.md rule 18 cites a removed
   path. One-line fixes, bundle with PR 1.

## B. Project-side gaps (build in this repo, upstream later if accepted)

| # | Gap | Plug-in point | Binding rules |
|---|---|---|---|
| 4 | Transport-agnostic Ackermann bridge so a laptop drives over rosbridge | `MobileBaseRobot` subclass overriding `_cmd_fields` with the bicycle model (`_mobile_base.py:24-26, 387-397`), accepting any `Transport`; rosbridge needs two-segment type strings and gated `service_call` for `ActiveStateSrv`/`EnableStateSrv` | keep `_rest_command_error`, shared numeric domains, `failed_halt_error`, `partial_construction_repr`; new module gets its own `_GATE_SUITES` entry |
| 5 | Camera, inference, battery, LED, calibration, model-state reads | `_extra_tools()` on the Ackermann class, each `never_gated`; images returned as `{"image": base64}` blocks like `EarthRoverDriver.capture_frame` | every writing service (`set_led`, `set_car_cal`, model load) added bare to `COMMAND_BLOCKLIST` and documented in `docs/learn/ros2.md` |
| 6 | Registry entry + native `DeepRacerDriver` so `Robot("deepracer", mode="real")` exists, joins the mesh, shows in the dashboard, and is voice-stoppable | `registry/robots.json` entry (`category: mobile`, `hardware.driver: strands`), driver with `send_action`, `stop_task`, `get_observation`, `tool_spec`; template `drivers/yahboom_m3pro.py` (transports rosbridge/ros2/twin) | registry integrity test, driver contract tests, `reads_cameras`, `docs/robots/deepracer.md` + `docs/learn/hardware/deepracer.md` under 900 words |
| 7 | HTTP webserver driver (zero-touch on the car) | shape of `drivers/earthrover.py` (requests, re-send, best-effort zero on cleanup); CSRF login, `drive_mode`, `start_stop`, `manual_drive`; gate via `gate_motion(tool="deepracer", action="manual_drive", allow_env="STRANDS_DEEPRACER_COMMAND_ALLOW")`; your `strands-robots-ros2` `deepracer_v2` client is the starting point (fix stream topic to `/camera_pkg/display_mjpeg`) | respect quantisation and negation (02 §6); single-token eviction documented |
| 8 | DeepRacer messages in the RTPS IDL bundle (`ServoCtrlMsg`, `LaserScan`, `CompressedImage`) | `strands_robots/rtps/idl/__init__.py` `REGISTRY` | `tests/rtps/test_idl_bundle.py`; services over RTPS out of scope, so RTPS cannot arm the car yet |
| 9 | Sim twin (MuJoCo Ackermann car) for rehearsal | registry `asset` + twin transport answering `/webserver_pkg/manual_drive`, like `yahboom_m3pro_twin.py`; MJCF converted from the AWS URDF (wheelbase 0.164, track 0.162, wheel r 0.03) | asset declaration rules AGENTS.md:286-291 |
| 10 | Decider motion gate | `strands.interventions.InterventionHandler.before_tool_call` on `drive_*` returning `Proceed`/`Guide`/`Deny`/`Confirm`; local `strands-decider serve` (2B Qwen3.5 v1-2610, ~150 ms) | never auto-approve a physical move on decider output alone; the operator gate stays |
| 11 | Vision decider frame classifier | MJPEG route or `/compressed` topic -> `POST /v1/systemone` with `images`, `choice`/`noul` questions (track clear, obstacle, off-track) with calibrated deferral | 200-400 ms per request; run beside the agent, not on AgentCore |
| 12 | Voice teleop | `BidiAgent` + `BedrockNovaSonicModel` with the car's `drive`/`stop` tools, `@tool(context=True)` + `cancel()` for "stop"; dashboard voice console fails closed on physical peers by design, so this is a project agent, not the dashboard | Python 3.12+, strands-agents >= 1.57.2, `[bidi,bidi-io,bidi-pyaudio,bidi-aec]`; posture change must be documented |
| 13 | Odometry / `navigate_to` | only with the community Nav2 stack and a `cmd_vel -> ServoCtrlMsg` node on the car; optional `odom_topic`/`nav_action` on the Ackermann class | out of scope for v1 |
| 14 | Sandboxing the agent's shell/python tools | Strands Box (`box run --config box.toml`, Dogwood policy) around the agent process on macOS | developer preview v0.1.0; macOS Apple silicon only |

## B2. Carry-forward from the earlier GitHub work (report 07)

| # | Item | Action |
|---|---|---|
| 15 | Plan-level validator (terminal stop, 5 s step cap, closed-loop rotation sum) | Port from `strands-agentic-deepracer/agent.py` as a project module with refusal-table tests; candidate upstream PR since upstream validates commands, not plans |
| 16 | Pattern library + planner prompt (circle, figure-8, square, slalom, spiral, parallel-park) | Keep as a project policy/skill; re-express durations in `linear, angular, duration` for `drive_*` |
| 17 | Measured constants (0.30/0.20/0.50, 60 deg/s, 0.28 m radius, 1.5 m/s corner limit) | Store as `calibration/http-2026-03.json`; re-measure on the ROS path in week 1 and store alongside |
| 18 | MJPEG SOI/EOI frame buffer | Wrap as the camera read tool for gap 5 and the frame source for gap 11 |
| 19 | Vision continue/replan/abort rules | Become the decider question criteria in gap 11; flip the fallback from continue to stop |
| 20 | HTTP client | Do not depend on `aws_deepracer_control_v2`; rewrite per gap 7 with token refresh, zero-on-exit and the 2.x stream topic |

## C. Proposed build order

1. **Week 1, upstream.** PR for gap 1 (mode bug) with docs polish (gap 3). Rebase and
   open gap 2 (QoS echo). Both are small and unblock real-car runs.
2. **Week 1, car.** Bring the car up on the community `deepracer-custom-car` image
   (Ubuntu 24.04 + Jazzy), install `rosbridge_suite`, open 9090, confirm the three
   control recipes in 02 §7 by hand with wheels off the ground at `max_speed 0.3`.
   Record calibration values and the sign convention observed.
3. **Week 2, driver.** Gaps 15 and 17 (validator, calibration file) first since they gate everything; then gap 4 (rosbridge Ackermann bridge) in `src/`, tested with the
   `_transport_stand_in` recorder pattern and a local rosbridge mock; then gap 5 reads
   (camera via MJPEG route first, battery, LED). First end-to-end: agent drives a square.
4. **Week 3, robot.** Gap 6 registry entry and `DeepRacerDriver` so the car is a mesh
   peer and dashboard card; gap 7 HTTP driver as the no-ROS fallback.
5. **Week 4, intelligence.** Gap 10 decider gate and gap 11 vision decider on the frame
   stream; gap 12 voice teleop agent. Each gets a refusal-table test and a demo script
   that raises on `stop_reason == "interrupt"` per upstream's examples contract.
6. **Later.** Gap 9 sim twin, gap 8 RTPS IDL, gap 13 Nav2, gap 14 Box sandbox.

## D. Open questions to settle before week 2

- Which car image: stock Foxy (frozen, Python 3.8) or community Jazzy? Recommendation:
  community, because `/compressed` camera topics and `rosbridge_suite` packages exist
  for Jazzy and the stock image is unsupported since 2026-07.
- Where does the agent run: laptop (rosbridge), on-car (rclpy, Python 3.12 installed
  by your old `setup_deepracer.sh`), or AgentCore (bidi WebSocket, but no low-latency
  decider)? Recommendation: laptop for development, AgentCore only for the voice
  front-end.
- Licensing: `strands-robots-ros2` has PolyForm Noncommercial parts (`runtime/rosbridge.py`,
  `skills/nav2.py`, examples). Reuse only the Apache-2.0 parts (`deepracer_v2` client,
  `twist_to_servo_norm`) or rewrite.
