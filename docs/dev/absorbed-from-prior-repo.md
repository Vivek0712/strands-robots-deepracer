# Absorbed from the prior repo

Where every feature and use case of `Vivek0712/strands-agentic-deepracer` (and the
`aws_deepracer_control_v2` client it sat on) now lives in this project, or why it was dropped.
Source of the study: `docs/context/07-prior-github-use-case-work.md` (report 07). The earlier
repo is read-only reference; nothing was copied from it verbatim and its plaintext credentials
never enter this repo.

Headline: **36 items absorbed or already present, 11 dropped** (reasons cite report 07).

## Phase 1: agentic navigation planner

| Earlier feature | Status | Where |
|---|---|---|
| JSON plan `{pattern, steps:[{action, seconds}]}` from Nova Lite | absorbed, re-expressed | `plans.Plan`/`Step(linear, angular, duration)`; the model asks `plan_deepracer(shape, size_m)` instead of inventing step lists |
| Plan validator: last step must be stop | absorbed | `Plan.terminal_stop` (refusal `no_terminal_stop`); `execute_plan` sends the zero pair from `finally` |
| Plan validator: 5 s step cap | absorbed, tightened | the 2 s hop cap from `Calibration.max_duration_s` (refusal `duration_cap`) |
| Plan validator: known actions only | absorbed | numeric domain per step: `not_a_number`, `linear_cap`, `yaw_at_rest`, `zero_step`, `below_min_turn_radius`, `envelope` |
| `MAX_PLAN_STEPS` 20 (soft) | absorbed, hard | `Pen.max_steps` 24 (refusal `too_many_steps`) |
| Closed-loop rotation check (`_check_rotation`, 360 / 720 deg, 5 deg warning) | absorbed, now a refusal | `rotation_mismatch` and `net_heading_mismatch` in `validate_plan`; figure-8 720 total, 0 net |
| `y|yes` confirmation REPL before execution | dropped | report 07 section 3: the upstream command gate (`STRANDS_ROS2_COMMAND_ALLOW`, `ApprovalBroker`) is audited; a second prompt would be theatre |
| Bare `@tool` wrappers over the HTTP client | dropped | superseded by `DeepRacerRobot` tools (CONTRACTS section 6) |
| Flask `app_ui.py` (`/plan`, `/execute`) | dropped | the Pit Wall portal (Portal team) and the Simon Says kiosk `plan(text)` |
| Stabilisation step after a left/right reversal | dropped | an HTTP-path artefact (quantised steering); the bicycle model commands a continuous arc |

## Phase 2: strands-robots integration

| Earlier feature | Status | Where |
|---|---|---|
| `NavigationPolicy` base, `create_policy(provider)` | absorbed | `policies.NavigationPolicy` Protocol (`plan`, `advise`) |
| `NovaPolicy` | absorbed | `policies.ModelPolicy`: the agent itself calls `plan_deepracer` and drives |
| `MockPolicy` | absorbed | `policies.MockPolicy` (scripted plans, or the shape library without a model) |
| `ReplayPolicy` (library of canned plans) | absorbed, re-expressed | `policies.ReplayPolicy` replays a recorded run's `drive_deepracer` commands through today's gate |
| Pattern library in the planner prompt (circle, large circle, U-turn, figure-8, square, triangle, pentagon, hexagon, oval, slalom) | absorbed as code | `shapes.py` generators from the bicycle model; `prompts.SHAPES_RULE` is one paragraph, not a worked-example library |
| spiral-out, parallel-park, "figure-forward" patterns | dropped | no closed form inside a 1.4 m usable pen; not asked for by any beat |
| 8-point `_reasoning` chain-of-thought | dropped | the validator does the arithmetic; the model narrates `Proposal.narration()` |
| Rotation calibration 90 deg in 1.5 s (60 deg/s) at throttle 0.2 / steering 0.5 | dropped, documented | report 07 section 2.1: HTTP-path only, quantised; the ROS path uses the bicycle model and must be re-measured (`shapes.py` module docstring) |
| Measured constants `FWD_THROTTLE 0.30`, `TURN_THROTTLE 0.20`, `STEER_ANGLE 0.50`, min radius 0.28 m, skid speed 1.5 m/s | already present | `calibration.py` (`throttle_at_max_speed 0.3`, `min_turn_radius_m 0.28`); `shapes.TURN_SPEED_MPS 0.25` echoes the slower turn |
| `_move_for_duration`: `move()` then `time.sleep` then `stop_car()` | dropped | report 07 section 2.3 and 3: the car holds the last command for the whole sleep (no watchdog); upstream's 20 Hz stream with a trailing zero in `finally` is the driver |
| `DeepRacerTool(AgentTool)` with `execute|start|status|stop`, `TaskStatus` machine, thread pool, `ToolResultEvent` stream | dropped | report 07 section 3: retire the custom AgentTool; `MobileBaseRobot` tools plus the intervention gate replace it; the state-machine ideas live on as `PlanRun` and its tests |
| Flask dashboard with SSE step streaming | dropped | the portal's `WS /ws` over `events.jsonl` (CONTRACTS section 4) |
| Monkey-patch of the stream topic to `/camera_pkg/display_mjpeg` | already present | `tools.ConsoleClient` targets the 2.x route directly |

## Phase 3: adaptive visual navigation

| Earlier feature | Status | Where |
|---|---|---|
| `camera_stream.py` MJPEG SOI/EOI parser | already present | `tools.iter_jpeg_frames` / `first_jpeg` (report 07: the reference parser) |
| Camera wake `PUT /api/vehicle/media_state` | already present | `ConsoleClient` |
| `vision_assessor.py`: one Bedrock Converse call per step, continue/replan/abort | absorbed, re-expressed | the decider's two typed questions per hop in `gate.DeciderGate.decide`; `policies.VisionPolicy.advise` maps Proceed/Guide/Deny to continue/re-plan/stop |
| `camera_policy.py` `CameraPolicy(NavigationPolicy)`, `has_vision` duck typing | absorbed | `VisionPolicy(base)` wraps any policy; no duck typing, the gate always looks |
| Up to 3 re-plans per run | absorbed | `policies.MAX_REPLANS = 3` |
| Skip assessment for steps under 0.5 s | dropped | every hop is gated; a 0.5 s hop is the unit of motion |
| `asyncio.wait_for(assess, 4.0 s)` | absorbed, tightened | the decider budget is 1.5 s (CONTRACTS section 7) |
| `safe_continue()` on timeout, API error, parse error, unknown action | **dropped, reversed** | report 07 section 2.4 design flaw: fail-open; `VisionPolicy` fails closed (table in `tests/unit/test_policies.py`), the gate denies on `vision unavailable` |
| Dashboard routes `/frame`, `/vision_status`, `/reinit`, `/camera/reconnect` | dropped | portal frames come from `frame` events; reconnects are the transport's |
| `voice-poc/nova_sonic_agent.py` | already present | `voice.py` on `strands.bidi` |

## Phase 4: voice

| Earlier feature | Status | Where |
|---|---|---|
| `voice_agent.py` on Nova Sonic, `_TranscriptOutput`, `run_voice_text` | already present | `voice.py` (bidi, PTT, text mode) |
| `deepracer_auth_poc.py` CSRF login probe | already present | `ConsoleClient.login` |
| `navigate_tool.py`: `navigate(instruction)` plans and executes a whole manoeuvre in one tool call | dropped, split | one tool call must not be a whole plan: `plan_deepracer` returns the plan, each hop is its own gated `drive_deepracer` |
| `deepracer_emergency_stop()` | already present | `stop_deepracer()` (never gated) |

## Phase 5: DeepRacer + AWS MCP

| Earlier feature | Status | Where |
|---|---|---|
| `ask_aws_docs` via `awslabs.aws-documentation-mcp-server` and a nested Nova Lite agent | dropped | not a beat (report 11); the booth has no internet guarantee and the showcase is one claim, not a menu |
| Same `navigate`/vision stack as phase 4 | see phases 3 and 4 | |

## `aws_deepracer_control_v2` (HTTP client)

| Earlier feature | Status | Where |
|---|---|---|
| CSRF login flow | already present | `ConsoleClient.login` (with re-login, which the old client lacked) |
| `set_manual_mode` / `start_car` / `stop_car` over HTTP | already present on ROS | `vehicle_state` 0 then `enable_state` (CONTRACTS section 0) |
| `move(angle, throttle, max_speed)` single shot over HTTP | dropped | report 07 section 1: quantised throttle path, `success: true` even when dropped; the ROS servo topic is the command surface |
| `get_battery_level`, sensor status, device info | already present | `tools.battery_level` (ROS service) and `ConsoleClient.api_get` |
| Model upload / load, calibration PUTs | dropped | calibration is read, never written (CONTRACTS section 9); no RL model in the show |
| `load_model` undefined-name bug, cached-forever token | dropped | defects, not features |

## `use_cases/` library (13 named platforms)

| Earlier feature | Status | Where |
|---|---|---|
| `RobotTools` nine-function protocol + four physics constants | absorbed as `MobilePlatform` (5 verbs) | `platforms.py`; `docs/dev/platforms.md` maps each old name |
| `deepracer.py` adapter | this project | `DeepRacerRobot` + `DeepRacerPlatform` |
| `rover`, `roomba`, `lawnmower`, `hospital_cart`, `solar_inspection` (differential, `/cmd_vel`) | documented only | `platforms.md`: `MobileBaseRobot` subclasses upstream |
| `drone`, `underwater_rov` (MAVLink), `boat` | documented only | `platforms.md` |
| `camera_dolly`, `pipeline_crawler` (TCP/serial JSON) | documented only | `platforms.md` |
| `robot_arm` (MoveIt2) | documented only | `platforms.md` |
| `warehouse_robot` (listed, never existed) | dropped | not in the clone |
| `lawnmower copy.py` | dropped | stray duplicate |
| `load_tools()` by file path, `USE_CASE=<name>` swap | dropped | the strands-robots registry is the contract (report 07 section 3) |

## Kiro steering and specs

| Earlier rule (`phase2-safety.md`) | Here |
|---|---|
| `stop_car()` in `finally` | the driver's trailing zero and `execute_plan`'s terminal stop |
| 5 s cap in validator and executor | 2 s cap in `Calibration`, `validate_plan` and the driver |
| `stop_on_failure=True` | `execute_plan` aborts at the first failed hop or non-Proceed verdict |
| plans end in `stop` | `Plan.terminal_stop` |
| calibration never changes without re-measuring | calibration is read-only (CONTRACTS section 9) |
| `y|yes` only | the upstream gate's accepted answers |
| `DEEPRACER_PASSWORD` never logged | credentials only in `~/.config/deepracer/env` |
| `is_error()` as the single predicate | structured tool results |

## Dropped, in one list, with the report 07 reason

1. Custom `DeepRacerTool(AgentTool)`: upstream `MobileBaseRobot` tools and the intervention gate replace it (section 3).
2. `_move_for_duration` sleep-and-stop loop: no watchdog, the car holds the command through the sleep (sections 2.3, 3).
3. `safe_continue()` fail-open vision fallback: reversed to fail closed (section 2.4).
4. HTTP quantised throttle path and its 60 deg/s rotation calibration: ROS path must be re-measured (sections 1, 2.1).
5. Plaintext credentials in the repo: env file only (CLAUDE.md).
6. `y|yes` REPL and Flask dashboards: upstream gate and the portal (section 3).
7. `navigate()` one-call manoeuvre: a plan is many gated hops.
8. Spiral-out, parallel-park, "figure-forward": no room in the pen, no beat.
9. `ask_aws_docs` MCP tool: not a beat, needs the internet.
10. Model upload/load and calibration writes: read-only calibration, no RL in the show.
11. Twelve non-DeepRacer adapters, `warehouse_robot`, `lawnmower copy.py`: documented in `platforms.md`, not built.

Physics stops the car; the decider explains. Everything absorbed above is on the explanation
side of that line: the plan is what the rover says it will do, and every hop still asks the gate.
