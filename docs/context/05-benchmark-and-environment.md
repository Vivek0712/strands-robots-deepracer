# Benchmark and environment (2026-10-12)

## Upstream install and test run on this Mac

Machine: macOS 15.7 (Darwin 24.6.0), Apple Silicon arm64, Python 3.12.11, uv 0.7.19,
Docker 28.3.2. No ROS 2 (no `/opt/ros`, no `ros2`), no Gazebo, no Foxglove.

Reference checkout: read-only git worktree of `strands-labs/robots` upstream main
@ d504fedd (v0.5.3 + 50 commits), created from `~/Documents/strands-0.5x/robots`
(remote `upstream` added). Recreate with:

```bash
cd ~/Documents/strands-0.5x/robots && git fetch upstream --tags
git worktree add -f <dir> upstream/main
cd <dir> && UV_PROJECT_ENVIRONMENT=.venv uv sync --python 3.12 \
  --extra dev --extra rosbridge --extra mesh --extra dashboard --extra voice --extra sim-mujoco
```

Result: `uv sync` succeeds on macOS with those extras. Not installed: `cyclonedds`
(the `ros2` extra), `pyaudio`/`sounddevice` (needed only for local mic voice I/O).

Resolved versions in that venv:

| Package | Version |
|---|---|
| strands-robots | 0.5.4.dev50+gd504fedd |
| strands-agents | 1.57.2 (PyPI latest 1.59.0, 2026-10-08) |
| roslibpy | 1.8.1 |
| eclipse-zenoh | 1.9.0 |
| mujoco | 3.11.0 |
| fastapi | 0.141.1 |

System pip (outside the venv) still has strands-agents 1.38.0, which predates
`strands.bidi`; do not develop against it.

## Targeted test suite (the DeepRacer/rosbridge/voice contract)

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider --no-cov \
  tests/mesh/test_ackermann_robot.py tests/mesh/test_ackermann_command_gate.py \
  tests/mesh/test_rosbridge_robot.py tests/mesh/test_rosbridge_robot_command_gate.py \
  tests/mesh/test_drive_command_numeric_domains.py tests/mesh/test_drive_contract_fleet_scope.py \
  tests/mesh/test_drive_reports_a_refused_trailing_stop.py \
  tests/test_every_ros_transport_consults_the_command_gate.py \
  tests/test_examples_never_report_a_refused_command.py \
  tests/drivers/test_ros_mobile_bases_live_in_drivers.py \
  tests/test_dashboard_voice_agent_builds_on_the_installed_strands.py \
  tests/test_strands_agents_floor_ships_the_imported_api.py
```

| Metric | Value |
|---|---|
| Tests | 254 passed, 3 skipped, 0 failed |
| Wall time | 14.5 s (19.7 s including coverage) |
| Coverage gate | fails at 7.4% only because this is a subset; the repo gate is 80% on the full suite |

The 3 skips are environment-conditional (rclpy / cyclonedds absent). The whole-tree
command the maintainers use is `hatch run whole-tree-check`.

## Signatures observed in the installed package

```python
AckermannRosRobot(node_name: str, servo_topic: str, scan_topic: str | None = None, *,
    servo_type: str = 'deepracer_interfaces_pkg/msg/ServoCtrlMsg', scan_type: str | None = None,
    wheelbase_m: float = 0.164, max_speed: float = 1.5, max_steering_rad: float = 0.5236,
    max_duration: float = 10.0, publish_rate: float = 20.0,
    init_services: list[dict[str, Any]] | None = None)

BidiAgent(model: BidiModel | str | None = None, tools=None, system_prompt=None, messages=None,
    record_direct_tool_call=True, load_tools_from_directory=False, agent_id=None, name=None,
    description=None, hooks=None, state=None, storage=None)
```

`strands.bidi` modules present at 1.57.2: `agent`, `hooks`, `io` (audio, console,
configs), `models` (bedrock, openai, google), `types` (agent, content, events, io, media).

## Control-path comparison matrix

| | (a) rclpy / DDS | (b) rosbridge websocket | (c) HTTPS webserver |
|---|---|---|---|
| Change needed on car | none | install rosbridge_suite, open 9090 | none |
| Laptop needs | ROS 2 matching the car distro + locally built `deepracer_interfaces_pkg`; Linux or Docker | roslibpy only; any OS, Python 3.12 | requests only |
| Works from this Mac today | no | yes | yes |
| strands-robots support | `AckermannRosRobot` (needs mode fix) | `RosbridgeRobot` is Twist-only; Ackermann variant missing | none; `EarthRoverDriver` is the HTTP template; your `strands-robots-ros2` `deepracer_v2` client exists |
| Value fidelity | exact floats | exact floats | quantised to {0.3, 0.5, 0.8}, negated, scaled by `max_speed` |
| Mode handshake | `vehicle_state 0` + `enable_state true` via services | same, via `call_service` | `drive_mode manual` + `start_stop start` |
| Camera | raw `Image` 640x480 over DDS (heavy); `/compressed` only on community stack | same topics as base64 JSON; use `throttle_rate` | MJPEG multipart `GET /route?...` (cheapest) |
| LiDAR | needs BEST_EFFORT subscription | rosbridge handles QoS server-side | not exposed |
| Latency / rate | lowest; servo_node caps at 50 Hz | one JSON hop; 10-20 Hz fine | ~10 Hz practical; one token file, browser login evicts the agent |
| Safety | no watchdog; trailing zero required | same | same; `manual_drive` returns success even when not in manual mode |

Recommendation: (b) for the agent on the laptop or a cloud host, (a) for an on-car
agent process, (c) for a zero-touch demo and for the MJPEG camera feed in all cases.
