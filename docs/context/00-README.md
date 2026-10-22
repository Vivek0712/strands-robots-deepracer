# Agentic DeepRacer on strands-robots: project context bundle

Ground research completed 2026-10-12. This directory is the single source of truth
for building an agent-driven AWS DeepRacer on top of upstream `strands-labs/robots`
(strands-robots). Read this file first, then the numbered reports as needed.
Bare `docs/...` paths inside these reports cite the upstream strands-robots, strands-decider
and deepracer-custom-car repositories, not this one.

| File | What it holds | Size |
|---|---|---|
| `00-README.md` | This index: executive summary, headline findings, cheat-sheets, decisions | |
| `01-strands-robots-code-deepdive.md` | Upstream strands-robots v0.5.3 (main @ d504fedd): layering, command gate, ROS/rosbridge/RTPS transports, `use_ros`/`use_rosbridge` tools, `AckermannRosRobot`, examples (inlined), tests as contract, mesh, dashboard voice, deps, history, 13 gaps | 2345 lines |
| `02-deepracer-ros-http-stack.md` | DeepRacer device status 2026, hardware, every ROS 2 package/topic/service with verbatim `.msg`/`.srv`, webserver HTTP API route table with source, community HTTP clients, community OS, control semantics, three control recipes, simulation options | 783 lines |
| `03-strands-box-deciders-bidi.md` | Strands Box (sandbox engine), Strands Deciders (API, models, Strands intervention gate), bidi voice agents (`strands.bidi` API, models, I/O, events), SDK release train, AgentCore relevance | 1065 lines |
| `04-prior-local-work.md` | Everything already built locally: merged PRs, unmerged branches, design specs, Curiosity rosbridge harness, `strands-robots-ros2` runtimes, DeepRacer device evidence, dev-machine audit | 412 lines |
| `05-benchmark-and-environment.md` | Local install + test benchmark of upstream, installed versions, control-path comparison matrix | |
| `06-gaps-and-roadmap.md` | Synthesized gap list with plug-in points and the proposed build order | |
| `07-prior-github-use-case-work.md` | The two GitHub repos built before/during strands-robots: `aws_deepracer_control_v2` HTTP client and the three-phase `strands-agentic-deepracer` (measured car constants, planner + rotation validator, MJPEG frame buffer, Nova Pro vision loop, 13-platform use-case contract, Kiro safety rules), mapped onto strands-robots today | |
| `08-harness-sdk.md` | Strands Harness SDK monorepo: packages, `create_harness` API, sandbox seam, interventions sugar, subagents, CLI; where it fits | |
| `09-showcase-use-cases.md` | Seven-act showcase ladder (Marshal, Pit Crew, Race Engineer, Scout, Supervisor, Paddock, Boxed Driver) with the pillar map and recommendation | |
| `10-conference-showcase.md` | Conference reframe: a rover that understands the room. Ten walk-up booth demos, five stage acts, ambient host mode, venue realities, build order | |
| `11-final-use-cases.md` | Council verdict and the final showcase: seven live beats on one spine, booth kiosks, pre-recorded cuts, cuts list, build order. Supersedes 09 and 10 | |
| `12-architecture.md` | Where each component runs (car vs laptop vs GPU box vs cloud), the voice-to-motion path step by step, stop paths and owners, proven-vs-to-build table | |
| `13-dev-plan-and-dependencies.md` | Repos, four-layer testing harness with a fake car, Pit Wall portal, car audio options, KrewHQ team-context usage, fork-and-pin policy, four-week team plan, and the dependency list for the user | |
| `council/` | Brainstorm lenses, merged 24-candidate pool, five advisor responses, anonymized peer reviews, letter key | |

## Executive summary

**Most of the plumbing already exists upstream, written largely by you.** strands-robots
v0.5.3 ships `AckermannRosRobot` with a `from_deepracer()` preset, a `rosbridge`
transport with `RosbridgeRobot` and `use_rosbridge`, `use_ros` with actions, a
`MobileBaseRobot` seam, a command gate that already blocklists `/manual_drive`,
`/vehicle_state` and `/enable_state`, and a dashboard voice console on `strands.bidi`.
PRs #995, #1110 and the Ackermann branch (#1035, re-landed as #2689) are yours.

**But the DeepRacer path upstream has never been driven on a real car, and it has a
mode bug.** `from_deepracer()` calls `/ctrl_pkg/vehicle_state` with `state=1`. The
car's `ctrl_node.cpp` declares `enum CtrlState { manual, autonomous, calibration }`,
so `1` is **autonomous**. In that mode `ManualDriveCtrl` is inactive and every
`/webserver_pkg/manual_drive` message is silently dropped. With a model loaded,
`enable_state true` would start the car driving itself. Manual is `0`. This is the
first upstream fix to ship (see 06).

**The right laptop-side architecture is rosbridge, not rclpy.** `AckermannRosRobot`
is hard-wired to the rclpy transport. The stock car is Ubuntu 20.04 / ROS 2 Foxy /
Python 3.8, the community car is Ubuntu 24.04 / Jazzy, and this Mac has no ROS 2 at
all. The proven pattern is the Curiosity harness: agent in a Python 3.12 process,
roslibpy to `ws://<car>:9090`, car runs `rosbridge_server`. rosbridge is not
installed on stock or community cars; one `apt install ros-$ROS_DISTRO-rosbridge-suite`
fixes that.

**Deciders and bidi voice are ready to compose in.** Deciders (2B Qwen3.5 or Gemma 4
torsos, calibrated yes/no/choice/score in one forward pass, 115-400 ms) plug in as a
`strands.interventions.InterventionHandler.before_tool_call` gate on `drive_*` and as
a frame classifier on the MJPEG stream. `strands.bidi.BidiAgent` with
`BedrockNovaSonicModel` gives spoken teleop. Both demand strands-agents >= 1.57.2
(installed system pip has 1.38; the upstream venv has 1.57.2; PyPI latest 1.59.0).

**Strands Box is not robotics hardware.** It is an open-source Rust sandbox engine
(macOS Seatbelt + Cedar-compatible Dogwood policies) released 2026-10-07 as v0.1.0
developer preview. It is relevant only as a way to sandbox the agent's shell/python
tools, not as a robot runtime.

**Your earlier GitHub work is the calibration and use-case seed.** `strands-agentic-deepracer`
(Mar 2026) holds the only measured motion constants (throttle 0.30 gives about 0.40 m/s,
1.5 s of half-lock turn is 90 deg), a plan validator with a closed-loop rotation check,
an MJPEG frame buffer and a Nova Pro continue/replan/abort loop. Its custom AgentTool,
sleep-and-stop motion loop and fail-open vision fallback are superseded by upstream's
gated `drive` tools and must not be carried forward as-is. Report 07 has the mapping.

## Headline findings (each verified in the referenced report)

1. **Mode bug upstream.** `state=1` is autonomous, not manual. Verified against
   `ctrl_node.cpp` (enum) and `webserver_pkg/vehicle_control.py`
   (`drive_mode_state = 0 if drive_mode == "manual" else 1`). Report 02 §4; local
   sources at `~/strands-deepracer/aws-deepracer-ctrl-pkg`.
2. **No watchdog on the car.** The last PWM persists until a new message or a
   mode/enable transition. strands-robots' trailing-zero stop and
   `failed_halt_error` are the only safety net; every client must publish zero on
   exit. Report 02 §6, §9.
3. **Sign and quantisation traps.** The webserver negates both angle and throttle and
   quantises `|a|,|t|` to {0.3, 0.5, 0.8}; the ROS topic path does neither. HTTP
   throttle +0.8 and ROS throttle -0.8 are the same physical direction with the
   default motor polarity -1. Out-of-range values are dropped, not clamped. Report 02 §6.
4. **LiDAR is best-effort QoS.** `/rplidar_ros/scan` is BEST_EFFORT; upstream
   `use_ros echo` and `get_scan_*` subscribe RELIABLE and will see nothing until the
   QoS-adaptive echo branch (`fix/use-ros-echo-qos`, never opened) lands. Report 04 §2.
5. **Device status.** The AWS DeepRacer console retired 2025-12-15; cars are no longer
   sold. Open-source "DeepRacer on AWS" (aws-solutions, v1.3.2 2026-10-07) and the
   community `deepracer-custom-car` (v2.1.9.9, 2026-08-11, Ubuntu 24.04 + Jazzy) are
   the live stacks. `github.com/aws-deepracer` is dormant since 2024-05. Report 02 §1.
6. **No DeepRacer anywhere in upstream docs or sim.** The word does not appear under
   `docs/`; there is no MJCF/URDF asset, no registry entry, no mesh peer, no camera,
   battery, LED or calibration tool surface. Report 01 §12.
7. **Your own device history.** The car was reachable at 192.168.0.3 / .4 / .8 and
   192.168.1.42 in earlier sessions; `~/strands-deepracer` holds all AWS DeepRacer
   packages cloned plus PoC agents. Those earlier PoC files held plaintext car passwords
   and are not part of this repo; car credentials live only in `~/.config/deepracer/env`
   (see `car/connect/env.example`); never commit them. Report 04 §8.

## Cheat-sheet: the DeepRacer control contract

| Item | Value | Source |
|---|---|---|
| Manual-drive topic | `/webserver_pkg/manual_drive` (`deepracer_interfaces_pkg/msg/ServoCtrlMsg {float32 angle, float32 throttle}`, both in [-1, 1]) | 02 §2, §3 |
| Internal relay | ctrl_node re-publishes on `/ctrl_pkg/servo_msg` only when mode==manual and enabled | 02 §3 |
| Mode service | `/ctrl_pkg/vehicle_state` `ActiveStateSrv {int8 state}`: 0 manual, 1 autonomous, 2 calibration | 02 §4 |
| Enable service | `/ctrl_pkg/enable_state` `EnableStateSrv {bool is_active}`; must follow every mode change | 02 §4 |
| LiDAR | `/rplidar_ros/scan` `sensor_msgs/LaserScan`, BEST_EFFORT | 02 §2 |
| Camera | `/camera_pkg/display_mjpeg` (`sensor_msgs/Image` 640x480 stock; `/compressed` on community); HTTP `GET /route?topic=/camera_pkg/display_mjpeg&width=480&height=360` | 02 §2, §3 |
| Battery | `/i2c_pkg/battery_level` service; HTTP `GET /api/get_battery_level` | 02 §2, §3 |
| Geometry | wheelbase 0.164 m, track 0.162 m, wheel radius 0.03 m, max steer 0.5236 rad (30 deg) | 02 §2 |
| PWM | 20 ms period; servo 1.20/1.45/1.70 ms pol +1; motor 1.311/1.446/1.6035 ms pol -1 (`calibration.json`) | 02 §3 |
| HTTP login | `GET /` scrape `<meta name="csrf-token">`, `POST /login` form `password=` + `X-CSRFToken`, cookie `deepracer_token` (1 h, single token file) | 02 §3 |
| HTTP drive | `PUT /api/drive_mode {"drive_mode":"manual"}`, `PUT /api/start_stop {"start_stop":"start"}`, `PUT /api/manual_drive {"angle","throttle","max_speed"}` at ~10 Hz | 02 §3, §7 |
| rosbridge | not preinstalled; `apt install ros-$ROS_DISTRO-rosbridge-suite`, launch `rosbridge_websocket_launch.xml`, `ufw allow 9090/tcp` | 02 §7(b) |
| DDS | `ROS_DOMAIN_ID=0`, Fast DDS default; Wi-Fi multicast flaky, use discovery server or CycloneDDS unicast | 02 §5, §7(a) |

## Cheat-sheet: strands-robots surfaces you will touch

| Surface | Where | Notes |
|---|---|---|
| `AckermannRosRobot` | `strands_robots/drivers/ros/ackermann_robot.py:173` | standalone, rclpy only; tools `drive_<node>(linear, angular, duration)`, `stop_<node>()`, `get_scan_<node>()`; defaults wheelbase 0.164, max_speed 1.5 m/s, max_steering 0.5236 rad, max_duration 10 s, 20 Hz; yaw-at-rest refused (changelog.d/3541) |
| `MobileBaseRobot` + `Transport` seam | `strands_robots/drivers/ros/_mobile_base.py` | override `_cmd_fields` for the bicycle model; `RosBridgedRobot` (rclpy Twist) and `RtpsRobot` subclass it; `RosbridgeRobot` and `AckermannRosRobot` do not yet |
| rosbridge transport | `strands_robots/rosbridge.py`, `tools/use_rosbridge.py` | roslibpy, one `Ros` per (host, port), two-segment type strings |
| Command gate | `strands_robots/_command_gate.py:74-92` | blocklist by final path segment includes `/manual_drive`, `/vehicle_state`, `/enable_state`; `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state` for headless runs; every new transport module needs a `_GATE_SUITES` entry |
| Layering | `scripts/check_import_layers.py:84-152` | core -> registry -> drivers|mesh -> sim|policies -> app -> tools -> dashboard; no upward imports |
| Voice | `strands_robots/dashboard/voice.py` | `BidiAgent` + `BedrockNovaSonicModel` (`amazon.nova-2-sonic-v1:0`) or `OpenAIRealtimeModel`; reaches robots only via mesh `MeshBridge.send_cmd` |
| House rules | `AGENTS.md` | changelog.d fragment per PR, refusal tables, 900-word doc pages, docs hooks; never edit CHANGELOG.md [Unreleased] |
| Install | `pyproject.toml` | python >= 3.12; strands-agents >= 1.57.2; extras `rosbridge`, `ros2` (cyclonedds only; rclpy from a distro), `voice`, `dashboard`, `mesh` |

## Decisions taken in this research pass

- Build against upstream main, not the stale local clones (`~/strands-robots-prs` and
  `~/Documents/strands-0.5x/robots` are 1300+ commits behind). A read-only worktree of
  upstream main is the reference while developing.
- Laptop-side control goes through rosbridge; on-car control may use rclpy. HTTP is
  the fallback and the only path that needs no change on the car.
- Contribute fixes upstream first (mode bug, QoS echo), then build the project-specific
  driver, decider gate and voice teleop in this repo.
- Deciders run local or on a GPU host, never on AgentCore, for anything in the motion
  loop (7 s/question warm on a 2 vCPU microVM).
