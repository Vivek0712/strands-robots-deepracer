# Prior GitHub use-case work (pre-strands-robots)

Studied 2026-10-12 from fresh clones. These two repos were built before and during the
evolution of strands-robots, against the DeepRacer web console rather than ROS. They
hold the only empirically measured motion calibration we have, a working MJPEG frame
buffer, a vision-in-the-loop executor, and a reusable use-case contract. They also
carry patterns that strands-robots has since made obsolete or that run against its
safety posture. Both are catalogued here so the use-case discussion can start from
what was proven on the car.

| Repo | Commits | Dates | Licence | Role |
|---|---|---|---|---|
| github.com/Vivek0712/aws_deepracer_control_v2 | 9 | 2021-02-21 to 2021-11-01 | MIT (c) 2021 lshw54 | HTTP console client, fork of lshw54/awsdeepracer_control; targets console 1.0.606.0 |
| github.com/Vivek0712/strands-agentic-deepracer | 10 | 2026-03-10 to 2026-03-17 | MIT (README badge; no LICENSE file in clone) | Three-phase Strands + Nova agent on top of that client, plus a 13-platform use-case library and Kiro specs/steering |

## 1. aws_deepracer_control_v2 (HTTP client)

Single module, `src/aws_deepracer_control_v2/aws_deepracer_control_v2.py`, class
`Client(password, ip="127.0.0.1", name="deepracer")`. Dependencies: requests,
requests_toolbelt, beautifulsoup4 + lxml, urllib3.

**Login flow** (matches report 02 §3 exactly): `GET https://<ip>/` with `verify=False`,
scrape `meta[name="csrf-token"]`, `POST /login` form `password=` with `X-CSRFToken`,
then every call carries `X-CSRFToken`, `content-type: application/json`, `referer`,
`origin`, `x-requested-with: XMLHttpRequest` and the session cookie. The token is
fetched once and cached for the life of the object; there is no re-login on the 1-hour
cookie expiry or when a browser login evicts the agent's token.

**API surface** (method -> HTTP):

| Method | Call |
|---|---|
| `set_manual_mode()` | `stop_car()` then `PUT api/drive_mode {"drive_mode":"manual"}` |
| `set_autonomous_mode()` | `stop_car()` then `PUT api/drive_mode {"drive_mode":"auto"}` |
| `start_car()` / `stop_car()` | `PUT api/start_stop {"start_stop":"start"|"stop"}` |
| `move(steering_angle, throttle, max_speed)` | `PUT api/manual_drive {"angle","throttle","max_speed"}` (single shot, no duration) |
| `set_throttle_percent(p)` | `PUT api/max_nav_throttle {"throttle": p}` |
| `get_battery_level()` / `get_is_usb_connected()` | `GET api/get_battery_level`, `GET api/is_usb_connected` |
| `get_raw_video_stream()` | `GET /route?topic=/display_mjpeg&width=480&height=360` streaming |
| `get_models()` / `get_uploaded_models()` / `upload_model()` / `load_model()` | `GET api/models`, `GET api/uploaded_model_list`, `PUT api/uploadModels` multipart, `PUT api/models/<name>/model` |
| `set_calibration_mode()` | `GET api/set_calibration_mode` |
| `get_calibration_angle()` / `get_calibration_throttle()` | `GET api/get_calibration/angle|throttle` |
| `set_calibration_angle()` / `set_calibration_throttle()` | `PUT api/set_calibration/angle|throttle` |

**Defects to not carry forward:**
- `load_model` references an undefined name `null` (NameError on call).
- Stream topic `/display_mjpeg` is the 1.x console path; console 2.x needs
  `/camera_pkg/display_mjpeg`. The agent repo monkey-patches this at import time.
- `_put` treats success as the substring `success": true` in the body; the webserver
  returns `{"success": true}` even when the car is not in manual mode (02 §9), so a
  "successful" move can be a silently dropped one.
- No zero-on-exit, no watchdog, no token refresh, module-level logging to stdout at
  INFO, and `set_calibration_mode` puts the car in calibration mode as a side effect of
  `show_vehicle_info()`.

PyPI: `awsdeepracer-control` 0.2.0 (lshw54, 2023-09-25) is the upstream; this fork is
installed from source as `aws_deepracer_control_v2`.

## 2. strands-agentic-deepracer (three phases + use cases)

245 files, about 12,300 lines of Python, of which roughly half is the duplicated
`use_cases/common/` copy of phase 3. Models: Nova Lite (`us.amazon.nova-lite-v1:0`)
for planning, Nova Pro (`us.amazon.nova-pro-v1:0`) for vision. Python 3.10+.

### 2.1 Measured car constants (the most valuable content)

All measured on the physical car through the HTTP path with `MAX_SPEED=1.0`:

| Constant | Value | Meaning |
|---|---|---|
| `FWD_THROTTLE` | 0.30 | about 0.40 m/s forward |
| `TURN_THROTTLE` | 0.20 | about 0.25 m/s while turning |
| `STEER_ANGLE` | 0.50 | half lock, about 0.35 m arc radius |
| Rotation calibration | 1.5 s of turn = 90 deg | 60 deg/s at the two values above |
| Min turning radius | 0.28 m | full lock |
| Max safe corner speed | 1.5 m/s | above this the car skids |
| `MAX_STEP_SECONDS` | 5.0 | hard cap per step, validator rejects longer |
| `MAX_PLAN_STEPS` | 20 | soft cap |
| Stabilisation step | forward 0.3 s | inserted after every left/right reversal |

Sign convention used: HTTP `throttle` negative drives forward (`-FWD_THROTTLE`),
`steering` negative turns left. This agrees with report 02 §6 (the webserver negates
both fields and the motor polarity is -1), so on the ROS topic path the signs flip.
Because the HTTP server quantises `|angle|,|throttle|` to {0.3, 0.5, 0.8}, these
constants land on the 0.3 and 0.5 steps. The rotation calibration is therefore only
valid for the HTTP path at these exact values; any ROS-path driver must re-measure.

### 2.2 Phase 1: planner + confirmation

Strands `Agent(model=Nova Lite, tools=[], system_prompt=PLANNER_PROMPT)` returns a JSON
plan `{"_reasoning", "pattern", "steps":[{"action","seconds"}]}`; actions are
`connect, forward, backward, left, right, stop`. A terminal REPL asks for `y|yes`
before execution. Bare `@tool` functions wrap the client. Known bug fixed in phase 2:
a `return` inside the `finally` that calls `stop_car()` swallowed the stop.

### 2.3 Phase 2: AgentTool architecture

- `agent.py`: `NavigationPolicy` base with `NovaPolicy`, `MockPolicy`, `ReplayPolicy`
  and `create_policy(provider)`; `validate_plan()` (last step must be `stop`, no step
  over 5 s, known actions only) and `_check_rotation()` (sum of turn seconds times
  60 deg/s must equal 360 for closed loops, 720 for figure-8, warning at 5 deg).
- Planner prompt holds a verified pattern library: circle (4 x left 1.5 s), large
  circle, U-turn, figure-8, square, triangle, pentagon, hexagon, oval, slalom,
  spiral-out, parallel-park and more; each with its rotation check written out, and an
  8-point `_reasoning` chain-of-thought the model must fill.
- `deepracer_tools.py`: `_move_for_duration(steering, throttle, seconds)` = one
  `move()` then `time.sleep(seconds)` then `stop_car()` in `finally`; the car holds the
  last command for the whole sleep because there is no watchdog (02 §9).
- `deepracer_agent_tool.py`: `DeepRacerTool(AgentTool)` with `tool_spec` action enum
  `execute | start | status | stop`, a `TaskStatus` state machine (IDLE, CONNECTING,
  PLANNING, RUNNING, COMPLETED, STOPPED, ERROR), a one-worker `ThreadPoolExecutor`, a
  `threading.Event` checked every step, `stream()` yielding one `ToolResultEvent`, and
  `cleanup()` that stops hardware then shuts the executor. This mirrors the four-action
  robot tool shape that strands-robots used at the time.
- Flask dashboard with SSE step streaming.

### 2.4 Phase 3: closed-loop vision

- `camera_stream.py`: daemon thread reading the MJPEG HTTP stream in 1 KiB chunks and
  extracting frames by JPEG SOI/EOI markers (`FF D8` / `FF D9`) regardless of multipart
  boundary; lock-protected latest frame; 15 s first-frame timeout; 2 s reconnect.
  Camera is woken with `PUT /api/vehicle/media_state {"activateVideo": 1}`.
- `vision_assessor.py`: one Bedrock Converse call per step with the raw JPEG bytes
  (no base64) and a context block (instruction, step index, remaining steps, replan
  count); returns `VisionDecision(action in continue|replan|abort, reasoning,
  new_instruction, confidence)`; instruction-aware rules ("stop when" -> abort, "avoid"
  -> replan, otherwise continue). `max_tokens 256`, `temperature 0.1`, read timeout 30 s.
- `camera_policy.py`: `CameraPolicy(NavigationPolicy)` composes NovaPolicy +
  VisionAssessor + CameraStream; `has_vision=True` is duck-typed by the tool.
- Executor loop: skip assessment for steps under 0.5 s and for `stop`/`connect`;
  `asyncio.wait_for(assess, 4.0 s)`; up to 3 replans per run; abort calls
  `deepracer_stop()` immediately.
- Dashboard routes: `/plan`, `/execute`, `/stop`, `/stream` (SSE), `/frame` (latest
  JPEG), `/vision_status`, `/reinit`, `/camera/reconnect`.

**Design flaw to reverse:** every failure path in the vision assessor (timeout, API
error, JSON parse error, unknown action) returns `safe_continue()`. That is fail-open:
a blind car keeps driving. strands-robots' posture is fail-closed (refuse, stop, name
the reason), and a decider gate in this project must stop on uncertainty, not continue.

### 2.5 Use-case library (unverified by its own README)

`use_cases/common/base_tools.py` defines a `RobotTools` Protocol: nine functions
(`connect, move_forward, move_backward, turn_left, turn_right, stop, is_error,
reset_client, activate_camera`) plus four physics constants
(`PHYSICS_MIN_TURN_RADIUS_M, PHYSICS_MAX_CORNER_SPEED, PHYSICS_FWD_SPEED_MS,
PHYSICS_TURN_SPEED_MS`) and optional `PLATFORM_NAME`, `PLATFORM_DESC`. `load_tools()`
imports `{USE_CASE}.py` by file path and `validate_tools()` reports missing names.
`USE_CASE=<name> python common/main.py --vision` swaps the platform.

Files present: `deepracer, drone, boat, robot_arm, pipeline_crawler, roomba, lawnmower,
hospital_cart, solar_inspection, rover, camera_dolly, underwater_rov`. The README and
the Kiro spec list `warehouse_robot.py`, which does not exist in the clone, and a stray
`lawnmower copy.py` is checked in. ROS2 platforms use rosbridge `/cmd_vel` Twist,
MAVLink platforms use DroneKit, TCP platforms send JSON. None were run on hardware.

The `use_cases/deepracer.py` adapter calls
`client.move(steering=..., throttle=..., duration=..., max_speed=...)`, but the
client's `move()` has no `duration` or `steering` keyword, so it raises `TypeError` on
first use. Only the phase-3 `deepracer_tools.py` path (positional `move` + sleep +
`stop_car`) was exercised.

### 2.6 Kiro steering and specs

39 spec folders (`requirements.md`, `tasks.md`, some `design.md`) and 18 steering
files. `phase2-safety.md` is the project's safety contract: `stop_car()` in `finally`,
5 s cap enforced in both validator and executor, `stop_on_failure=True`, plans must end
in `stop`, calibration values may not change without re-measuring, `y|yes` confirmation
only, `DEEPRACER_PASSWORD` never logged, `is_error()` as the single error predicate.
These rules map one-to-one onto strands-robots' refusal-table style and should be
restated as tests in this project rather than as prose.

## 3. Mapping onto strands-robots today

| This repo (Mar 2026) | strands-robots v0.5.3 equivalent | Carry forward? |
|---|---|---|
| `DeepRacerTool(AgentTool)` execute/start/status/stop | `MobileBaseRobot` tools `drive_<node>`, `stop_<node>`; operator gate via `tool_context.interrupt` | Retire the custom AgentTool; keep the state-machine ideas as tests |
| `NavigationPolicy` / `NovaPolicy` / `MockPolicy` / `ReplayPolicy` | `strands_robots.policies` providers and `create_policy` | Keep the planner prompt and pattern library as a project policy or skill; rebuild on upstream `Policy` |
| `validate_plan()` + `_check_rotation()` | no equivalent (upstream validates per-command numeric domains, not plans) | Keep, as a project-side plan validator and a refusal-table test |
| `_move_for_duration` sleep + `stop_car` | `drive(linear, angular, duration)` publishes at 20 Hz then trailing zero; `failed_halt_error` | Retire; upstream's loop is safer |
| `CameraStream` MJPEG SOI/EOI | `EarthRoverDriver.capture_frame` returns `{"image": base64}`; no MJPEG client upstream | Keep the parser; wrap as a `capture_frame` read tool |
| `VisionAssessor` Nova Pro continue/replan/abort | Decider (`noul`/`choice` with calibrated probability) or VLM tool; `InterventionHandler.before_tool_call` | Replace with a decider gate that fails closed; keep the instruction-aware rule set as the question text |
| Confirmation `y|yes` REPL and Execute button | command gate interrupt accepting `y|yes|approve|approved`, `STRANDS_ROS2_COMMAND_ALLOW` | Retire; upstream gate is audited |
| Flask SSE dashboard | strands-robots dashboard (FastAPI, mesh cards, voice console) | Retire once the car is a mesh peer |
| `base_tools.RobotTools` 9-function contract | registry entry + `HardwareDriver` verbs | Retire; the registry is the contract |
| Measured constants (0.30 / 0.20 / 0.50, 60 deg/s) | `AckermannRosRobot` bicycle model takes `linear, angular` and computes servo values | Keep as the first calibration dataset; re-measure on the ROS path and store in a calibration file the project reads |

## 4. What this adds to the roadmap

- A **plan-level validator** (closed-loop rotation check, step cap, terminal stop) is a
  real gap in upstream and a good candidate for a project module and later PR.
- The **HTTP driver** in gap 7 of report 06 should be a clean rewrite informed by
  `Client`, not a dependency on `aws_deepracer_control_v2` (undefined-name bug, wrong
  stream topic, no token refresh).
- The **vision loop** becomes a decider step: frame -> `choice` question with the
  instruction-aware criteria -> `Deny`/`Confirm` on low confidence. Fail closed.
- The **use-case library idea** (one engine, swap the platform) is already how
  strands-robots works through the registry; the new use-case discussion should pick
  scenarios by what the DeepRacer can sense (camera, LiDAR on Evo, battery) and what
  bidi, deciders and Box each add, not by porting the 13 platform stubs.
