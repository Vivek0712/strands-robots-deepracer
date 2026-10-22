# D. Prior local work: strands-robots, DeepRacer, Ackermann, rosbridge, deciders

Consolidated 2026-10-12 from read-only inspection of the local machine. All paths absolute.
Upstream reference: strands-labs/robots is at v0.5.3 (2026-10-12); the local clone
`~/strands-robots-prs` has `origin/main` fetched to `c5d2a5c2` (2026-10-05).

## 0. Executive summary

| Asset | Where | State | Reuse value for a DeepRacer project |
|---|---|---|---|
| `AckermannRosRobot` (DeepRacer over rclpy) | upstream `strands_robots/drivers/ros/ackermann_robot.py` (521 lines) | MERGED upstream (user's PR #1035 closed, re-landed by maintainer as #2689 on 2026-08-24; fragment `changelog.d/1035-ackermann-ros-robot.md` kept) | Drop-in: `AckermannRosRobot.from_deepracer("deepracer")`, needs sourced ROS 2 on the agent host or on the car |
| `use_rosbridge` + `RosbridgeRobot` (ROS1/remote over WebSocket, pure pip) | upstream `strands_robots/rosbridge.py`, `tools/use_rosbridge.py`, `drivers/ros/rosbridge_robot.py` | MERGED upstream as #1110 (2026-07-31, authored by the user) | The proven no-ROS-on-laptop transport; DeepRacer can be reached the same way if `rosbridge_server` runs on the car |
| `MobileBaseRobot` + `Transport` seam | upstream `strands_robots/drivers/ros/_mobile_base.py` | User's PR #1722 closed; re-landed by maintainer as #2696 (2026-08-24) with `Co-authored-by: Vivek Raja`; moved to `drivers/ros` in #4140 (2026-09-29) | The base class any new DeepRacer transport (e.g. a rosbridge-Ackermann or HTTP-console Ackermann) should subclass: override `_cmd_fields` only |
| `use_ros` actions + `navigate_to` | upstream `strands_robots/ros.py` + `tools/use_ros.py` | MERGED as #995 (2026-07-02/03, authored by the user) | Nav2 goal path if DeepRacer ever runs Nav2 |
| QoS-adaptive `echo` + `param_*` | `~/strands-robots-cont/robots` branches `fix/use-ros-echo-qos`, `feat/use-ros-params` | NEVER OPENED as PRs; NOT in upstream (`_qos_for_topic`, `param_list` absent from upstream `use_ros.py`) | Still relevant: `/rplidar_ros/scan` is BEST_EFFORT; without the QoS fix `get_scan` on a real DeepRacer returns empty |
| Curiosity Gazebo rosbridge harness | `~/strands-robots-curiosity` (compose + Dockerfile + agent.py) and `~/strands-robots-cont/robots` branch `feat/curiosity-sim-harness` (`examples/rosbridge/curiosity_sim/*`) | Local only; upstream kept just `examples/rosbridge/curiosity_agent.py` | Template for a Gazebo-in-Docker + rosbridge + py3.12 agent-container pattern |
| `strands-robots-ros2` (RuntimeAdapter package) | `~/strands-robots-ros2` (Vivek0712/strands-robots-ros2, v0.1.0, 2026-06-25) | Published; original parts PolyForm Noncommercial | `deepracer_v2` runtime (HTTP console client, CSRF login, manual_drive), `ros2` runtime (registry-driven, QoS profiles, DeepRacer handshake), `twist_to_servo_norm`, `aws_deepracer` registry entry, Nav2 skills |
| DeepRacer physical-car work | `~/strands-deepracer` (AWS DeepRacer upstream pkgs + poc + edge + 5-phase agent repo), `~/strands-robots` old fork (`deploy.py`, `setup_deepracer.sh`, `Dockerfile.deepracer`, `cmdvel_to_servo_pkg` demo) | Evidence of real car access at 192.168.0.3 / .4 / .8 (ssh user `deepracer`) in 2026-03 to 2026-05 | Verified topic/service/field names; console REST API path; onboard install script |
| Decider-on-robots | `robots-decider` (the author's local checkout behind strands-labs/robots PR #4573) | PR #4573 (`DeciderJudge`) CLOSED, not merged; issue #4572 proposes robot-trained decider | Pattern for advisory, abstaining yes/no vision checks (never authoritative) |

Dev machine: macOS 15.7 (Darwin 24.6), arm64 Apple Silicon, python3.12.11, uv 0.7.19, Docker 28.3.2, NO ROS 2 (no `/opt/ros`, no `ros2`), no brew ROS/Gazebo/MuJoCo/Foxglove. `~/strands-robots-prs/.venv-lite` (py3.12) has `strands-robots 0.4.2.dev687` editable, `roslibpy 1.8.1`, `strands-agents 1.50.2`.

---

## 1. `~/Documents/strands-0.5x/robots-deepdive-docs/` (7 files, 164,738 bytes)

Generated 2026-09-04/05 from the clone at `~/Documents/strands-0.5x/robots` (branch `main`, HEAD `5b4c4552`). They describe v0.5.x as of **Sep 5 2026**; upstream is now v0.5.3 (2026-10-12), so two things have moved since: (a) the ROS mobile bases are described under `strands_robots/mesh/` but moved to `strands_robots/drivers/ros/` in #4140 (2026-09-29); (b) the shared transports became `strands_robots/ros.py` and `strands_robots/rosbridge.py` (#3871/#3873, 2026-09-19).

### README.md (read fully)
- Four-layer stack **Agent -> Policies -> Backends -> Robots**; `Robot("so100")` returns a backend engine that is itself a Strands `AgentTool`. ~98k lines Python.
- Ten cross-cutting principles worth copying into any new driver: single-owner modules; membership-over-truthiness for "was this supplied"; monotonic clocks for spans; refuse before mutating; verdicts must be earned ("sending a stop is not landing one"); silent-failure doctrine (values that would produce a finite, successful, wrong run are refused at preflight); fail-closed asymmetrically ("stopping is never gated, anywhere"); non-finite numbers are a security bug class; refusals name the caller's spelling with difflib suggestions and stable machine codes (`refusal_codes.py`); claims vs expectations at trust boundaries.
- Gaps flagged: `ros2_bridge=True` MuJoCo-only; `describe()/save_episode()/run_multi_policy()` Python-only; RL trainers leak `VecSimEnv` executor; **FastAPI dashboard server + PWA is NOT in the repo** (only `strands_robots/dashboard/` support layer); repo convention: never touch `CHANGELOG.md [Unreleased]`, write a `changelog.d/` fragment.

### 01-robot-core.md (27 KB)
`Robot()` factory (name/mode/driver resolution, sim path, mesh opt-in, `.run()` Device Connect); `HardwareRobot` (3182 lines, wraps lerobot; kwarg dual gate; serial-candidate refusals); teleop (`Teleoperator()`, `TeleopMixin`); registry (`robots.json`, aliases, discovery, asset auto-download, `register_robot`); drivers seam (`HardwareDriver` runtime-checkable Protocol, 12 shipped drivers: dynamixel, feetech, franka, g1, go2, reachy, microduck, robotiq, booster, ur, crazyflie, earthrover); `bus_access.py`; `_serial_discovery.py`; tools layer; `doctor.py`; `refusal_codes.py`; `device_connect/`.
**ROS-relevant**: section 8 documents `_command_gate.py` as the single owner of operator approval for anything commanding a ROS 2 graph with `COMMAND_BLOCKLIST` = `/cmd_vel`, `/joint_command`, `/joint_trajectory`, **`/manual_drive`**, e-stop and motor-enable services, nav actions; matching on the final path segment; pre-approve via `STRANDS_ROS2_COMMAND_ALLOW`, bypass via `BYPASS_TOOL_CONSENT=true`. Tool table lists `use_ros` (cancels goal on timeout), `use_rtps` (pure cyclonedds, can act as a robot), `use_rosbridge` ("third transport over rosbridge WebSocket (reaches ROS 1). Shares `_command_gate`").

### 02-simulation.md (30 KB)
`SimEngine` ABC (5102 lines), MuJoCo (reference + only AgentTool), Newton, Isaac (7390 lines); 77-action tool surface; dataset recording; domain randomization; terrain; Gaussian-splat hybrid rendering.
**ROS-relevant** section 5: sim ROS 2 bridge is three symmetric layers (`RosTelemetryBase`, `RosTelemetryBridge`, `SimRosBridge` 41 lines) publishing `/<robot>/joint_states` and `/<robot>/<camera>/image_raw`; publish-only; MuJoCo-only. Explicitly: "Four sibling agent tools: `use_ros` (rclpy), `use_rtps` ..., `use_rosbridge` (roslibpy WebSocket, reaches ROS 1 - declares a narrower port domain because autobahn's `range(0, 65535)` stops one short), plus `RosBridgedRobot`/`AckermannRosRobot`. **There is no rosbridge/RTPS exposure of the sim**." No DeepRacer sim model exists in strands-robots.

### 03-policies-inference.md (24 KB)
`Policy` ABC (3 abstract members, well-known goal kwargs, action-chunk format); factory three-stage resolution; 15 registered providers; transports GR00T (ZMQ+msgpack), Cosmos3 (WebSocket+msgpack), lerobot_local, lerobot_async (gRPC), remote `PolicyServer`/`RemotePolicy`; observation flow; inference security. No DeepRacer/Ackermann mention.

### 04-training.md (22 KB)
Trainer ABC, TrainSpec, shared-domain gates, LeRobot trainer (no shell-out, LoRA, RA-BC, SARM), GR00T/Cosmos3/SageMaker, RL stack (SimEnv, PPO, FastSAC), DatasetRecorder, verify_dataset, episode_labels. No DeepRacer mention.

### 05-mesh-fleet.md (29 KB)
Zenoh mesh, presence, tell/broadcast, E-STOP + resume, audit log, mTLS/ACLs, IoT Core transport, bridge transport.
**Section 6 "Robot classes in mesh/" (verbatim, the most relevant passage):**
> `MobileBaseRobot` (`_mobile_base.py:239`) owns the invariant half - validation, clamping, `drive(linear, angular, duration)`, `init_services` handshake, stop/get_pose/get_scan, `tools` built from wired capabilities. Subclasses supply a `Transport` protocol object and `_cmd_fields()` (kinematics: identity Twist vs bicycle model). Module docstring is candid the classes were originally mirrored copies (a safety fix had to be found N times).
> - Capabilities split into Transport (required publish/echo) + optional ServiceCapable/ActionCapable - use_rtps has neither.
> - Non-finite inputs refused, not clamped (nan sails through min/max).
> - `duration` validated before any side effect including the handshake.
> - Every timed non-zero command followed by a zero command in try/finally - and **sending the stop is not landing it**: the halt's verdict is read, and a successful hold over a refused stop reports **error**.
> - `stop` never gated on handshake/limits but NOT exempt from the transport command gate - the gate is keyed on the surface, not the payload.
> - **AckermannRosRobot** - steering cars (DeepRacer). Keeps the fleet (linear, angular) vocabulary, converts via bicycle model to angle/throttle; `_REST_VELOCITY_EPS` (atan2 noise near v=0 -> hard steering); two-step manual-mode handshake; **no get_pose** (stock platform has no odometry - "a class that pretended otherwise would be lying").
> - **RosbridgeRobot** - does NOT subclass MobileBaseRobot; WebSocket to rosbridge_server, reaches ROS 1 (NASA Curiosity Gazebo); "rosbridge is unauthenticated by default - trusted networks."

(Note: as of upstream Sep 19 `RosbridgeRobot` still imports `failed_halt_error`/`LATCHED_VELOCITY` from `_mobile_base` but remains its own class.)

### 06-fleet-examples-dashboard.md (28 KB)
Five fleet orchestration examples (capability dispatch, cross-zone transport, failover, evacuation, work-order ingress), Rerun fleet dashboard, `strands_robots/dashboard/` support layer (WebAuthn/JWT auth, `agent_motion.py` physicality verdict, `agent_hitl.py`, `safety_state.py`, `log_redaction.py`), and the confirmed absence of the FastAPI server (`__main__.py` `_COMMANDS = ("doctor", "verify-dataset")`). One `cmd_vel`-adjacent mention: evacuation example stops bases with "zeroed twist + mj_forward".

---

## 2. Design specs and plans in the HOME git repo (`~/strands-robots-cont/docs/superpowers/`)

Present on disk (not just in git). Files:
- `specs/2026-07-02-use-ros-qos-params-design.md` (9.6 KB) + `plans/2026-07-02-use-ros-qos-params.md` (41 KB)
- `specs/2026-07-03-ackermann-ros-robot-design.md` (10.3 KB) + `plans/2026-07-03-ackermann-ros-robot.md` (44 KB)
- `specs/2026-07-04-rosbridge-curiosity-design.md` (10.4 KB) + `plans/2026-07-04-rosbridge-curiosity.md` (63 KB)

Also in `~/strands-robots-cont/`: `PR_DESCRIPTION.md` (the #995 body), `PR_REVIEWS.md` (R1-R16 review notes on #739/#742/#743 that motivated the QoS and trailing-zero work), `0001-feat-use-ros-actions.patch` (365 insertions across `mesh/ros_bridge.py`, `tools/use_ros.py`, two test files), and `robots/` = a clone of fork Vivek0712/robots with remotes `origin` (fork) and `upstream` (strands-labs), `upstream/main` stale at `4d4293f` 2026-07-06.

Feature branches in `~/strands-robots-cont/robots` (all pushed to the fork `origin`):
```
feat/use-ros-actions      513d095, 731e2e5                              -> upstream PR #995 MERGED 2026-07-02
fix/use-ros-echo-qos      745b693, d905e76, 07f72b8                     -> never opened
feat/use-ros-params       967ad72, 0708f8d, 65b4305 (stacked on QoS)    -> never opened
feat/ackermann-ros-robot  972841b..667db13 (6 commits, 2026-07-03/04)   -> PR #1035 CLOSED; re-landed as #2689
feat/rosbridge-curiosity  76f177f..7b8da54 (8 commits, 2026-07-04..06)  -> PR #1110 MERGED 2026-07-31
feat/curiosity-sim-harness fb6e38f (adds examples/rosbridge/curiosity_sim/*) -> not upstream
```

`gh pr list --repo strands-labs/robots --author Vivek0712 --state all` (run 2026-10-12):
```
4573 CLOSED            feat/decider-episode-judge      feat(episode-judge): Strands Decider as an episode-judge backend ...
4270 MERGED 2026-09-30 contrib/manipulation-optional-mixin
4232 MERGED 2026-09-29 contrib/register-robot-without-asset
4177 MERGED 2026-09-29 contrib/simengine-capability-profile
4176 MERGED 2026-09-29 contrib/registry-unfolded-overlay-key
4175 MERGED 2026-09-29 contrib/py-typed
3212 CLOSED            feat/mesh-peer-retention
3206 MERGED 2026-09-05 feat/rl-fast-td3
3205 MERGED 2026-09-17 feat/dashboard-mesh-bridge
1722 CLOSED            feat/mobile-base-abstraction    refactor(mesh): MobileBaseRobot + Transport
1110 MERGED 2026-07-31 feat/rosbridge-curiosity        feat: rosbridge transport (use_rosbridge + RosbridgeRobot) - NASA Curiosity Gazebo verified live
1035 CLOSED            feat/ackermann-ros-robot        feat(mesh): AckermannRosRobot - Ackermann ROS 2 cars (AWS DeepRacer)
 995 MERGED 2026-07-02 feat/use-ros-actions            feat(tools): ROS 2 action support in use_ros + goal-level navigate_to
```
Upstream landing commits (authorship): `3a4c6078` #2689 Ackermann and `19d4588b` #2696 MobileBaseRobot were committed by maintainer `./c²` (cagataycali) on 2026-08-24 (the #2696 body carries `Co-authored-by: Vivek Raja <vivekraja98@gmail.com>`); `c038f9f9` #1110 and `735f3323` #995 are authored by `Vivek Raja P S`. Upstream kept the user's fragment numbers `changelog.d/1035-ackermann-ros-robot.md`, `1110-rosbridge-transport.md`, `1722-mobile-base-abstraction.md`.

### 2.1 Spec: use_ros QoS-adaptive echo + parameters (2026-07-02)

Key sections verbatim:

> **Motivation** ... 1. **`echo` cannot read sensor topics on real robots.** `_echo` subscribes with a bare depth-10 profile, which defaults to RELIABLE/VOLATILE. Hardware sensor topics (`/scan`, camera streams, IMU) are published BEST_EFFORT (rmw sensor-data profile), and a RELIABLE subscription never matches a BEST_EFFORT publisher - the agent sees an empty result and no error. Latched topics (`/tf_static`, `/map`) have the same failure through durability. 2. **No parameter surface.**

> **PR-A Behavior**: `echo` automatically matches the QoS that live publishers offer, using the same policy as `ros2 topic echo` (ros2cli, Galactic+): Reliability: RELIABLE only if **all** live publishers offer RELIABLE; otherwise BEST_EFFORT. Durability: TRANSIENT_LOCAL only if **all** live publishers offer TRANSIENT_LOCAL; otherwise VOLATILE. Depth stays 10. No live publishers: today's default profile. No new tool parameters. No schema change.

> **Implementation**: new private helper `def _qos_for_topic(node, topic: str) -> "QoSProfile"` ... `node.get_publishers_info_by_topic(topic)`, fold the offered profiles ... Any failure inside QoS discovery degrades to the current default profile.

> **PR-B**: three new `use_ros` actions `param_list` / `param_get` / `param_set` with new params `node_name`, `param_name`, `param_value`; implemented as plain service calls to `<node>/list_parameters`, `/get_parameters`, `/set_parameters` (`rcl_interfaces/srv/*`). Converters `_param_value_to_py` / `_py_to_param_value` (`bool` checked before `int`). `param_set` with `successful == False` -> structured error carrying `reason`.

> **Decision log**: Approach 1 (adaptive, ros2cli-equivalent) approved over explicit named profiles ... Verification vehicle: TurtleBot4 ROS 2 sim (the Curiosity rover sim is ROS1/rosbridge and cannot exercise rclpy `use_ros`).

Plan status: tasks 1-8 were executed (commits exist on both branches); Task 9 ("STOP for user confirmation before anything public") was never completed - no issues or PRs were opened. The plan records the local baseline "76 failed / 6 errors on full `test`" and the live-verification commands:
```
python -c "from strands_robots.tools.use_ros import use_ros; print(use_ros(action='echo', topic='/scan', timeout=5.0))"
python -c "from strands_robots.tools.use_ros import use_ros; print(use_ros(action='param_get', node_name='/amcl', param_name='max_beams'))"
```
Relevance: the DeepRacer's `/rplidar_ros/scan` is a BEST_EFFORT sensor topic; `AckermannRosRobot.get_scan()` forwards to `echo`, so on real hardware it will return empty until this fix (or a `qos` parameter) exists upstream. The three commits on `fix/use-ros-echo-qos` need rebasing onto the new `strands_robots/ros.py` (`_echo` moved there, line ~276).

### 2.2 Spec: AckermannRosRobot (2026-07-03) - verbatim key sections

> **Motivation**: `RosBridgedRobot` covers differential-drive bases: Twist on `cmd_vel`, `/odom` for pose. An Ackermann car exposes neither. The AWS DeepRacer - the most widely owned ROS 2 car - takes normalized `{angle, throttle}` (`deepracer_interfaces_pkg/msg/ServoCtrlMsg`) on `/webserver_pkg/manual_drive`, publishes no odometry, and must first be switched into manual mode by a two-step service handshake (`/ctrl_pkg/vehicle_state` then `/ctrl_pkg/enable_state`). Today a strands agent cannot drive it at all. The same shape applies to F1TENTH and most RC-scale Ackermann platforms.

> **Architecture**: One new module, `strands_robots/mesh/ackermann_robot.py`, beside `ros_bridge.py` and following it exactly: the class owns **no ROS 2 state**; every method forwards through `use_ros` (`publish` for servo commands, `service_call` for the handshake, `echo` for lidar).

> **1. Pure bicycle model**
> ```python
> def _twist_to_servo(linear, angular, *, wheelbase_m, max_speed, max_steering_rad) -> tuple[float, float]:
>     """(linear m/s, angular rad/s) -> (angle_norm, throttle_norm), both in [-1, 1]."""
> ```
> - `abs(linear) < 1e-3` -> `(0.0, 0.0)` (rest: no yaw at rest on Ackermann; avoids the atan2 singularity).
> - `delta = atan2(wheelbase_m * angular, linear)`, clamped to `[-max_steering_rad, +max_steering_rad]`, normalized by `max_steering_rad`.
> - `throttle = clamp(linear / max_speed, -1, 1)`.

> **2. Constructor** `AckermannRosRobot(node_name, servo_topic, scan_topic=None, *, servo_type="deepracer_interfaces_pkg/msg/ServoCtrlMsg", scan_type=None, wheelbase_m=0.164, max_speed=1.5, max_steering_rad=0.5236 (~30 deg), max_duration=10.0, publish_rate=20.0, init_services=None)`
> `from_deepracer(node_name, **overrides)`: `servo_topic="/webserver_pkg/manual_drive"`, `scan_topic="/rplidar_ros/scan"`, `init_services=[{"service": "/ctrl_pkg/vehicle_state", "type": "deepracer_interfaces_pkg/srv/ActiveStateSrv", "fields": {"state": 1}}, {"service": "/ctrl_pkg/enable_state", "type": "deepracer_interfaces_pkg/srv/EnableStateSrv", "fields": {"is_active": True}}]`. "The request field names (`state`, `is_active`) are taken from `deepracer_interfaces_pkg` and must be re-verified against the package source during implementation."

> **3. Methods**: `enable()` runs `init_services` in order, idempotent; `drive(linear, angular, duration=None, count=1)` **same signature and contract as `RosBridgedRobot.drive`** - enable first; `duration > max_duration` -> structured error (reject, don't clamp); clamp linear; convert; publish `count = max(1, round(duration * publish_rate))`; **trailing zero** in `try/finally` when sustained; `stop()` single zero, does NOT require `enable()`; `get_scan(timeout=5.0)`; **no `get_pose`**.

> **4. Agent tools**: `drive_<suffix>` (description states "Ackermann steering: cannot turn in place; min turning radius ~<wheelbase_m / tan(max_steering_rad)> m"), `stop_<suffix>`, conditional `get_scan_<suffix>`. `enable()` is not exposed as a tool.

> **Testing** (`tests/mesh/test_ackermann_robot.py`, rclpy-free): bicycle-model matrix (straight, rest, left/right vs hand-computed atan2, steering clamp, reverse, throttle clamp); drive forwarding; trailing zero (incl. when main publish errors); duration reject; enable order/once/failure aborts; constructor validation; `from_deepracer` wiring pinned; conditional scan tool; min-turning-radius in description.

> **Verification**: Live verification on a physical DeepRacer (availability unconfirmed): car on blocks ... Stated honestly as pending if not run by submission.

> **Out of scope**: Odometry/pose estimation (no wheel encoders on DeepRacer); camera streaming tools (`/camera_pkg/display_mjpeg`); AckermannDriveStamped output mode; registry entry.

> **Decision log**: Approach A (new class) approved over example-only and translator-hook-on-RosBridgedRobot. `drive(linear, angular)` contract kept identical to `RosBridgedRobot` (uniform fleet vocabulary) rather than exposing (speed, steering_angle). DeepRacer wiring lives in `from_deepracer()`, not in constructor defaults for topics. `enable()` auto-runs before first drive and is not an agent tool.

Implementation deviation worth knowing (branch commit 667db13 and upstream): `_twist_to_servo` uses `atan2(wheelbase_m * angular, abs(v))` and restores the sign for reverse, because the naive form "lands in the second quadrant when linear is negative, commanding near-full opposite steering while backing up". Upstream later added `_rest_command_error` (#3541): `drive(linear=0.0, angular=1.0)` is refused by name instead of silently sent as a zero servo pair.

Verified against `~/strands-deepracer/aws-deepracer-interfaces-pkg` sources: `ServoCtrlMsg` = `float32 angle; float32 throttle` (ratios w.r.t. calibration min/max); `ActiveStateSrv` request `int8 state`, response `int32 error`; `EnableStateSrv` request `bool is_active`, response `int32 error`. `webserver_pkg/constants.py: MANUAL_DRIVE_TOPIC = "manual_drive"`; `vehicle_control.py` route `/api/manual_drive` publishes `ServoCtrlMsg` on `pub_manual_drive`. Camera topics `video_mjpeg` and `display_mjpeg` in `camera_pkg`. Servo PWM range `SERVO_MIN 1200000 .. SERVO_MAX 1700000` (servo_mgr.hpp).

The plan's example file (`examples/deepracer_agent.py`) is now upstream as `examples/ros2/deepracer_agent.py`, with the gate note:
```
export STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state
```
and `if result.stop_reason == "interrupt": raise RuntimeError(...)`.

### 2.3 Spec: rosbridge transport + Curiosity (2026-07-04) - verbatim key sections

> **Motivation**: strands-robots speaks only ROS 2: `use_ros` is in-process rclpy; `use_rtps` is DDS. An enormous fleet of robots - including the canonical NASA Curiosity Gazebo simulation (ROS1 Noetic) - is reachable only through rosbridge's WebSocket JSON protocol. rosbridge also has a property no existing transport offers: **no sourced ROS environment at all** - pure pip (`roslibpy`), so an agent on macOS/CI/anywhere can drive a robot across the network.

> **Architecture**:
> ```
> use_ros       (rclpy)      <->  RosBridgedRobot / AckermannRosRobot
> use_rosbridge (roslibpy)   <->  RosbridgeRobot          <- NEW pair
> ```

> **Component 1 `use_rosbridge`**: optional extra `rosbridge = ["roslibpy>=1.7"]`; module-level cache `dict[(host, port)] -> roslibpy.Ros`; signature `use_rosbridge(action, host="localhost", port=9090, topic=None, service=None, type=None, fields=None, timeout=5.0, count=1, rate=10.0)`; actions `status`, `list_topics` (`/rosapi/topics`), `list_services`, `echo` (type via `/rosapi/topic_type`, unsubscribe in `finally`), `publish` (advertise/publish/unadvertise), `service_call`. Types are TWO-segment `_TYPE_RE = ^[A-Za-z0-9_]+/[A-Za-z0-9_]+$`.

> **Component 2 `RosbridgeRobot`**(node_name, cmd_vel_topic, odom_topic, scan_topic=None, *, host="localhost", port=9090, cmd_vel_type="geometry_msgs/Twist", odom_type=None, scan_type=None, max_linear=2.0, max_angular=1.0, max_duration=30.0, publish_rate=10.0). `from_curiosity(node_name="curiosity", host="localhost", port=9090, **overrides)`: `cmd_vel_topic="/curiosity_mars_rover/ackermann_drive_controller/cmd_vel"`, `odom_topic="/curiosity_mars_rover/odom"`. "The rover's `ackermann_drive_controller` consumes Twist directly, so no client-side kinematic model is needed."

> **Live verification (autonomous, on this Mac)**: 1. Docker container: ROS1 Noetic + Gazebo Classic headless, `mark-gl/curiosity_mars_rover_ws` built with the driving-subset whitelist, `rosbridge_server` + `rosapi`, port 9090. 2. Scripted non-LLM check: `get_pose()`, `drive(linear=1.0, duration=3.0)`, `get_pose()`; assert displacement > threshold. 3. Agent run (Bedrock). 4. Evidence into the PR body.

> **Decision log**: Option 2 (tool + class pair) user-approved over class-only and use_ros-backend-mixing. Docker-local sim user-approved as the verification vehicle. `roslibpy` as optional `[rosbridge]` extra. ROS1 2-segment type validation deliberately distinct from `use_ros`'s 3-segment regex. Safety semantics copied from the reviewed `AckermannRosRobot` (finite guards, reject-don't-truncate, timed-command trailing zero, stop never gated).

Branch commit `e359375` records what live testing taught: "use_rosbridge survives bridge flaps - never stop the shared reactor, halt orphan retries, pre-connect action check, count guards, empty-echo disclosure". The backend docstring: "One roslibpy.Ros is created per (host, port) for the process lifetime and NEVER discarded: its ReconnectingClientFactory re-dials a dropped WebSocket by itself (observed live), while a freshly constructed Ros in a process that has seen reconnect churn can fail to connect at all (roslibpy/Twisted limitation, observed live) ... Calling ros.terminate() is never an option: it stops the process-wide, non-restartable Twisted reactor."

The PR #1110 title says "NASA Curiosity Gazebo verified live", so the Docker + scripted odometry proof did run.

---

## 3. `~/strands-robots-prs` (fork clone, branch `feat/mobile-base-abstraction`, last commit 2026-07-29)

Remotes: `origin` = strands-labs/robots (fetched to `c5d2a5c2` 2026-10-05), `fork` = Vivek0712/robots (`fork/main` at `c6c6251e` 2026-09-28). Local branches: `feat/decider-episode-judge` (checked out in a worktree), `feat/mobile-base-abstraction`, `main`, `pr1035`, `pr1110`. The `pr1035`/`pr1110` branches are the July-28 rebases of the Ackermann and rosbridge PRs onto then-main ("merge: bring branch up to main, move changelog entry to a news fragment").

`git diff --stat origin/main...HEAD` on `feat/mobile-base-abstraction`:
```
changelog.d/1722-mobile-base-abstraction.md |  35 +
docs/ros2-integration.md                    |  41 +-
strands_robots/mesh/__init__.py             |  10 +
strands_robots/mesh/_mobile_base.py         | 456 +
strands_robots/mesh/ros_bridge.py           | 210 +-
strands_robots/mesh/rtps_robot.py           | 126 +-
tests/mesh/test_mobile_base.py              | 468 +
tests/mesh/test_ros_bridge.py               |  27 +-
```
Status: PR #1722 CLOSED, but the design landed upstream verbatim-in-spirit as #2696 (2026-08-24) crediting the user, then hardened (#2758 grammar-per-seam, #2839 "report a timed drive whose trailing stop was refused", #3174 anchored allowlists) and relocated to `strands_robots/drivers/ros/_mobile_base.py` in #4140. The branch's `changelog.d/1722-mobile-base-abstraction.md` is in upstream `changelog.d/`. Conceptually identical: `Transport` Protocol (`twist_type`, `publish`, `echo`), optional `ServiceCapable`/`ActionCapable`, `_cmd_fields` as the kinematics seam, `supports()`, limits default `None` ("this platform declares no limit, never zero"). Upstream additions since: `tool_context: ToolContext | None` threaded through `enable/drive/stop` for the operator gate; `failed_halt_error` / `LATCHED_VELOCITY`; `partial_construction_repr`; `drivers.base.refuse`.

Current upstream `MobileBaseRobot.__init__` (what a new DeepRacer subclass must satisfy):
```python
MobileBaseRobot(node_name, cmd_vel_topic, transport: Transport, *,
                odom_topic=None, scan_topic=None, cmd_vel_type=None, odom_type=None, scan_type=None,
                max_linear=None, max_angular=None, max_duration=None, publish_rate=10.0,
                init_services=None)
def drive(self, linear=0.0, angular=0.0, duration=None, count=1, tool_context=None) -> dict
def _cmd_fields(self, linear, angular, lateral=0.0) -> dict   # the one override point for kinematics
```
Upstream `AckermannRosRobot` is NOT a `MobileBaseRobot` subclass (it imports `failed_halt_error` and `_check_topic` and forwards through `strands_robots.ros.ros_action` directly); `RosBridgedRobot` and `RtpsRobot` are.

`changelog.d/` convention confirmed: 30 numbered fragments + README; never edit `CHANGELOG.md`; `python scripts/assemble_changelog.py --check`; placeholder `0000` is refused.

---

## 4. `~/strands-robots-ros2` (Vivek0712/strands-robots-ros2, v0.1.0, last commit 475d6be 2026-06-25)

"ROS2 / HTTP / rosbridge mobile-robot runtimes for Strands Agents - extension for strands-robots". `requires-python >=3.10`, deps `strands-agents>=1.0,<2`; extras `rosbridge=[roslibpy>=1.5]`, `http=[requests]`, `upstream=[strands-robots>=0.4]`.

**License (important for reuse)**: multi-licensed. Components derived from upstream strands-robots (`runtime/*` except `rosbridge.py`, `registry/`, `robot.py`, `utils.py`) are Apache-2.0. **Original code** (`runtime/rosbridge.py`, the `curiosity` registry entry, `examples/`, the web UI) is **PolyForm Noncommercial 1.0.0** (`LICENSE-NONCOMMERCIAL.md`). Media (`curiosity_rover.gif`, `rover.png`) CC BY-NC-ND 4.0. The DeepRacer runtimes (`runtime/deepracer_v2`, `runtime/http`, `runtime/ros2`) fall in the Apache-2.0 bucket per the README table. The author is the user, so relicensing is at their discretion.

Layout:
```
src/strands_robots_ros2/
  __init__.py            Robot (lazy), RuntimeAdapter, build_runtime, get_robot
  robot.py               Robot(AgentTool): actions execute|start|status|stop|move; move(linear_x, angular_z, duration, rate_hz=20)
  runtime/base.py        RuntimeAdapter ABC: connect/disconnect/is_connected, observation_schema, action_schema,
                         safety_limits, command_rate_hz, get_observation, send_action, stop, capabilities()
  runtime/factory.py     build_runtime(): lerobot | ros2 | http | deepracer_v2 | rosbridge; merges top-level
                         drive_type/wheelbase_m/safety_limits/command_rate_hz/capabilities into the sub-block
  runtime/rosbridge.py   RosbridgeRuntime (roslibpy; Twist publish; cached observation subs)      [PolyForm NC]
  runtime/ros2/adapter.py  Ros2Runtime (registry-driven; preferred/fallback command interface; translator hook;
                         _maybe_call_enable_state() = DeepRacer vehicle_state/enable_state handshake;
                         named QoS profiles default|command|sensor|tf_static)
  runtime/ros2/lifecycle.py  Ros2Lifecycle singleton (own rclpy Context + MultiThreadedExecutor + spin thread)
  runtime/ros2/translators/deepracer.py  TwistToServoCtrl -> deepracer_interfaces_pkg/msg/ServoCtrlMsg
  runtime/http/adapter.py  HttpRuntime (auth strategies cookie_password|bearer|api_key|none; connect/disconnect
                         sequences; command_endpoint + translator; observation_endpoints with TTL cache)
  runtime/http/translators/twist_to_servo.py  twist_to_servo_norm(...) + TwistToServo (safe_state, action_schema with min_turning_radius)
  runtime/deepracer_v2/client.py  DeepRacerV2Client: GET / -> csrf meta -> POST /login (checks deepracer_token cookie),
                         PUT api/drive_mode {manual|auto}, api/start_stop, api/manual_drive {angle, throttle, max_speed},
                         GET api/get_battery_level, api/is_usb_connected, route?topic=/display_mjpeg MJPEG stream
  runtime/deepracer_v2/adapter.py  DeepRacerV2Runtime: login+set_manual_mode+start_car on connect; bicycle model; trailing zero
  registry/robots.json   aws_deepracer (ros2), aws_deepracer_http (deepracer_v2), turtlebot4 (ros2), curiosity (rosbridge)
  skills/nav2.py         navigate_to(x,y,yaw), get_pose, cancel_navigation via nav2_simple_commander  [PolyForm NC]
examples/curiosity_rosbridge.py, examples/ros2_nav2_navigate.py, examples/web/server.py (+index.html)
tests/test_rosbridge.py  fake roslibpy injected via sys.modules
docs/blog.md
```

`aws_deepracer` registry entry (verbatim numbers): `drive_type: ackermann`, `wheelbase_m: 0.164`, command `preferred.topic=/webserver_pkg/manual_drive`, `type=deepracer_interfaces_pkg/msg/ServoCtrlMsg`, `qos=command`, translator `...translators.deepracer:TwistToServoCtrl`; observation topics `image_left=/camera_pkg/display_mjpeg (sensor_msgs/msg/Image, qos sensor)`, `scan=/rplidar_ros/scan (LaserScan, sensor)`, `tf`, `tf_static`; `vehicle_state_service=/ctrl_pkg/vehicle_state` (`ActiveStateSrv`, target mode 1), `enable_state_service=/ctrl_pkg/enable_state` (`EnableStateSrv`); `safety_limits: max_linear_x 1.5, max_angular_z 3.0, max_steering_rad 0.5236, max_duration_per_command 10.0, command_watchdog_timeout 0.4`; `command_rate_hz 20`; aliases `deepracer, deepracer_evo, bumblebee`. `aws_deepracer_http`: `host_env [DEEPRACER_HOST, DEEPRACER_IP]`, `password_env DEEPRACER_PASSWORD`, `verify_ssl false`, `max_speed 1.0`; aliases `deepracer_http, deepracer_remote, deepracer_v2`.

Reusable bicycle model (Apache-2.0 bucket), `runtime/http/translators/twist_to_servo.py`:
```python
_REST_VELOCITY_EPS = 1e-3
def twist_to_servo_norm(*, linear_x, angular_z, wheelbase_m, max_linear_x, max_steering_rad):
    v = float(linear_x); omega = float(angular_z)
    if abs(v) < _REST_VELOCITY_EPS:
        return (0.0, 0.0)
    delta = math.atan2(float(wheelbase_m) * omega, v)
    delta = max(-float(max_steering_rad), min(float(max_steering_rad), delta))
    return (float(delta / float(max_steering_rad)), max(-1.0, min(1.0, v / float(max_linear_x))))
```
(Note: lacks the reverse-quadrant fix that the upstream `AckermannRosRobot._twist_to_servo` has.)

README also credits the companion `Vivek0712/strands-agentic-deepracer` and notes a pending arXiv paper "Design Principles of Agent-Powered Robotics Systems".

---

## 5. `~/strands-robots-curiosity` (the proven rosbridge pattern)

Layout: `docker-compose.yml`, `docker/Dockerfile`, `docker/entrypoint.sh`, `curiosity_agent/agent.py`, `curiosity_agent/framework_agent.py`, `curiosity_ws/` (a full catkin workspace clone of `mark-gl/curiosity_mars_rover_ws` with `build/` and `devel/` already compiled inside the container; `src/` = `curiosity_mars_rover_{control,description,gazebo,navigation,viz}`, `dependencies`).

`docker-compose.yml` (verbatim):
```yaml
services:
  curiosity:
    build: ./docker
    image: curiosity:noetic
    container_name: curiosity
    platform: linux/arm64
    networks: [cnet]
    ports: ["127.0.0.1:6081:6080"]   # noVNC (6081 to avoid clashing with u3's 6080)
    volumes:
      - ./:/workspace/curiosity:rw
    environment: [ "DISPLAY=:99" ]
    shm_size: '2gb'
    stdin_open: true
    tty: true
    command: ["bash","-c","tail -f /dev/null"]

  # py3.12 strands agent — talks to the ROS1 sim via rosbridge+roslibpy (no ros1_bridge).
  agent:
    image: python:3.12-slim
    container_name: curiosity-agent
    platform: linux/arm64
    networks: [cnet]
    depends_on: [curiosity]
    ports:
      - "127.0.0.1:5001:5000"   # web UI (prompt box + live view)
    volumes:
      - ./:/workspace/curiosity:rw
      - ~/strands-robots:/workspace/fork:ro   # the strands-robots fork (framework)
      - ~/strands-robots-ros2:/workspace/ext:ro   # the extension package
      - ${HOME}/.aws:/root/.aws:ro
    working_dir: /workspace/curiosity/curiosity_agent
    environment:
      - ROS_HOST=curiosity
      - ROS_PORT=9090
      - PYTHONPATH=/workspace/ext/src:/workspace/fork   # extension (strands_robots_ros2) + fork (strands_robots)
      - MODEL=${MODEL:-us.amazon.nova-lite-v1:0}
      - AWS_REGION=${AWS_REGION:-us-east-1}
      - AWS_PROFILE=${AWS_PROFILE:-heisenberg}
    command: ["bash","-c","pip install -q strands-agents roslibpy boto3 flask && tail -f /dev/null"]
    stdin_open: true
    tty: true

networks: { cnet: { driver: bridge } }
```

`docker/Dockerfile`: `FROM --platform=linux/arm64 osrf/ros:noetic-desktop-full` + gazebo-ros-pkgs, ros-control/controllers, navigation (move_base, dwa, amcl, gmapping, map-server), `teleop-twist-keyboard`, `rosbridge-suite`, `xvfb x11vnc novnc websockify`, `catkin-tools`; `entrypoint.sh` starts `Xvfb :99 -screen 0 1600x900x24`, `x11vnc -rfbport 5900`, `websockify --web=/usr/share/novnc 6080 localhost:5900`, then `source /opt/ros/noetic/setup.bash`.

Wiring: the ROS1 Noetic container (Python 3.8) and the py3.12 agent container share a Docker bridge network; the agent reaches `ws://curiosity:9090` via roslibpy (no `ros1_bridge`). `curiosity_agent/agent.py` is the minimal hand-rolled pattern: `roslibpy.Ros(host, port).run()`, advertise `geometry_msgs/Twist` on `/curiosity_mars_rover/ackermann_drive_controller/cmd_vel`, subscribe `nav_msgs/Odometry` on `/curiosity_mars_rover/odom` into a dict, three `@tool`s `drive(linear, angular, duration=3.0)` (publish at 10 Hz for duration then zero), `get_pose()` (quaternion -> yaw), `stop()`, `BedrockModel(us.amazon.nova-lite-v1:0)`. System prompt states the Ackermann constraint: "to TURN you must keep linear > 0". `framework_agent.py` does the same through `strands_robots.Robot("curiosity", robot="curiosity", host=..., port=...)` from the old fork's `RosbridgeRuntime`.

The cleaned-up, committed version (not upstream) is on `~/strands-robots-cont/robots` branch `feat/curiosity-sim-harness`: `examples/rosbridge/curiosity_sim/{Dockerfile,docker-compose.yml,start.sh,README.md}` - `FROM ros:noetic-robot`, clones `mark-gl/curiosity_mars_rover_ws` at build time, `catkin_make -DCATKIN_WHITELIST_PACKAGES='ackermann_drive_controller;curiosity_mars_rover_description;curiosity_mars_rover_control;curiosity_mars_rover_gazebo'`, `MODE=headless|gui`, `SIM_STARTUP_WAIT=50`, ports `9090` and `6080`. README notes "under emulation (Apple Silicon running the amd64 image) the real-time factor drops below 1.0".

---

## 6. `robots-decider` (the author's local checkout) and `VISION_DECIDER_RESEARCH.md`

Files: `PLAN.md` (2026-10-05), `ISSUE.md`/`ISSUE-post.md`, `PR.md`/`PR-post.md`, `bench_decider_judge.py`, `bench_results*.json`.

How deciders were applied to robots: a `DeciderJudge(url, *, timeout, n_frames, min_confidence=0.6)` in `strands_robots/tools/decider_judge.py` (branch `feat/decider-episode-judge` in `~/strands-robots-prs`) labels recorded episodes with ONE `POST /v1/systemone` request (up to 4 frames from `sample_frames(include_images=True)`) carrying three typed questions: `quality` (choice over `QUALITY_GRADES`), `failure_mode` (choice over `FAILURE_MODES` + none), `success` (yes/no). Writes through `write_label`, so deterministic verdicts stay authoritative; **calibrated abstention**: if any answer's confidence <= 0.6 (yes/no p in [0.2, 0.8]) nothing is written, episode reported `deferred`. Stdlib `urllib` client, no new dependency. 53 offline tests against a fake loopback decider.

PLAN.md's doctrine table for where a decider fits in robots: A episode judge (low risk, built), B task-completion probe in the policy run loop ("yes/no 'is the cube in the bin?' on the camera frame; must stay advisory; a stop is opt-in, never a start"), C skill/policy router, D gate triage ("must NEVER auto-approve; the human gate stays the only approval"). Open question recorded: "Hardware/sim for B and C: the Curiosity sim, DeepRacer, or MuJoCo arms?"

Result: on a 12-episode MuJoCo ladder both hobson-v19 and v21 sat at the constant-answer baseline, confidence correctly low, 12/12 deferred, ~1.75 s/episode on MPS. PR #4573 was CLOSED (not merged). Follow-up proposed in #4572: fine-tune a decider on robot episodes labelled by deterministic predicates.

`VISION_DECIDER_RESEARCH.md` (1 Oct 2026, 12 sections) is about building a Vision Decider from Qwen3.5-2B-Base's retained vision tower; `grep -n robot|deepracer|camera|gate` yields only the Strands intervention gating example (line 45) and the schedule gates (line 496) - no robot or DeepRacer content.

---

## 7. Dev machine capabilities (checked 2026-10-12)

```
uname -m            arm64 (Apple Silicon); macOS 15.7 (24G222), Darwin 24.6.0
python3.12          3.12.11
uv                  0.7.19
ros2                not installed; /opt/ros absent; brew has no ros/gazebo/gz/mujoco/foxglove
docker              /usr/local/bin/docker, Docker version 28.3.2 (arm64; Curiosity compose used platform linux/arm64)
pip3 (system)       strands-agents 1.38.0, strands-agents-tools 0.2.2, strands-amazon-nova 1.0.2, torch 2.10.0,
                    opencv-python 4.13.0.92 (+headless); NO roslibpy, rclpy, mujoco, lerobot, onnx, openvino, ultralytics
~/strands-robots-prs/.venv-lite (py3.12.11): strands-robots 0.4.2.dev687 (editable), strands-agents 1.50.2, roslibpy 1.8.1, numpy 2.5.1
~/strands-robots/.venv  exists (older fork)
```
Implication: rclpy-based `AckermannRosRobot` cannot run natively on this Mac; it must run on the car, in a ROS 2 Docker container, or the DeepRacer must expose `rosbridge_server` so the pure-pip `use_rosbridge` path is used from macOS.

Memory rules in force: HOME is the git root (scope every `git add` to project paths, never `git add .`); `changelog.d/` fragments only; python3.12 for strands repos; AWS profile `heisenberg` (account `<redacted>`, us-east-1) for deploys; Bedrock default `us.amazon.nova-lite-v1:0` in all local agents.

---

## 8. DeepRacer device evidence

- `~/.ssh/config`: no `deepracer` entry.
- Shell history (redacted): earlier sessions reached the car by ssh, scp, rsync and `strands_robots.deploy` at 192.168.0.3, .4, .8 and 192.168.1.42 (per-command list removed before publication).
- Config files: `~/strands-deepracer/edge/.env` and `example.env` set `DEEPRACER_IP=192.168.0.3`; phase-3/4/5 `.env.example` use `192.168.0.8`; `~/strands-robots/.env` has `DEEPRACER_IP` and `DEEPRACER_PASSWORD` keys. **Those earlier PoC files and `.env` held plaintext car passwords; none of them are copied into this repo. Car credentials live only in `~/.config/deepracer/env` (see `car/connect/env.example`).**
- No ARP/mDNS hit right now; the car is not currently on this network.
Conclusion: a physical DeepRacer Evo (ssh user `deepracer`, web console on https://<ip>, stock Foxy image) was repeatedly used between 2026-03 and 2026-05 on a 192.168.0.x LAN; its SSH password auth was replaced by key auth on .8.

### Other DeepRacer assets found
- `~/strands-deepracer/` (2026-03): clones of all AWS DeepRacer upstream ROS 2 packages (`aws-deepracer-*-pkg`, `aws-deepracer-launcher`, sample projects, `deepracer-env*`, `deepsim`, `ude`, `robots`, `robots-sim`), plus `poc/` (`drive_deepracer.py`, `vehicle_api_drive.py` using pip `aws_deepracer_control_v2`, `deepracer_camera_view.py`, shell helpers), `edge/` (Strands edge agent with six `@tool`s `deepracer_connect/move_forward/move_backward/turn_left/turn_right/stop`, Nova Lite), and a nested clone of `Vivek0712/strands-agentic-deepracer` (5 phases: planner, AgentTool architecture, Nova Pro closed-loop vision via MJPEG, voice, AWS MCP; `use_cases/` with 14 robot scenario scripts incl. `deepracer.py`). Phase-2 physics constants: `FWD_THROTTLE=0.30 -> ~0.40 m/s`, `TURN_THROTTLE=0.20`, `STEER_ANGLE=0.50 -> ~0.35 m arc radius (> 0.28 m minimum)`.
- `~/strands-agentic-deepracer/` (Nov 2025): a different project - an agentic DeepRacer **reward function** (Strands agent on AgentCore, Nova Micro, re:Invent 2018 track waypoints). Not a driving stack.
- `~/strands-robots/` (old fork clone of Vivek0712/robots, branches `feat/deepracer-example`, `feat/http-deepracer-runtime`, `feat/http-deepracer-nav2-slam`, `gazebo-sim-backend`, `ros2robot-dev`): origin of the `RuntimeAdapter` design; `strands_robots/deploy.py` (rsync+ssh push to `deepracer@<ip>`), `scripts/setup_deepracer.sh` (installs Python 3.12 via deadsnakes on the car, rsyncs, venv, reads `/opt/aws/deepracer/password.txt`, pushes `~/.aws`), `example/deepracer_drive.py` (U-turn via `Robot(robot="deepracer_http")`, system prompt with heading math and the "under-rotates 20-40% below 0.3 m/s" calibration), `example/deepracer/deepracer_ros2_navigation.py` (uses AWS `cmdvel_to_servo_pkg` on the car so `/cmd_vel` Twist works; host sources Foxy with `ROS_DOMAIN_ID=0`). `docs/impl/phase-deepracer-robot/`, `phase-ros2robot/` (nav2-tool, slam-tool, gazebo-backend specs), `docs/paper/main.tex`.

---

## 9. Reusable code path index

Upstream (install `strands-robots` >= 0.5.x; python3.12):
- `strands_robots/drivers/ros/ackermann_robot.py` - `AckermannRosRobot.from_deepracer(node_name)`; `_twist_to_servo` (sign-correct); `_rest_command_error`; gate pre-approval `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`.
- `strands_robots/drivers/ros/_mobile_base.py` - `MobileBaseRobot`, `Transport`, `ServiceCapable`, `ActionCapable`, `positive_finite`, `failed_halt_error`, `LATCHED_VELOCITY`.
- `strands_robots/drivers/ros/rosbridge_robot.py` - `RosbridgeRobot.from_curiosity(...)`; pattern for a `from_deepracer_rosbridge` preset if rosbridge runs on the car.
- `strands_robots/rosbridge.py` - `rosbridge_action(..., gate=...)`, `never_gated`, `GATE_TOOL`, `_HOST_RE`, `_transport_port_error`; `strands_robots/ros.py` - `ros_action`, `_RosBackend`, `_echo` (QoS fix target), `_action_send_goal`.
- `strands_robots/tools/use_rosbridge.py`, `tools/use_ros.py`, `_command_gate.py` (blocklist includes `/manual_drive`).
- `examples/ros2/deepracer_agent.py`, `examples/rosbridge/curiosity_agent.py`.
- Tests to mirror: `tests/mesh/test_ackermann_robot.py`, `tests/mesh/test_ackermann_command_gate.py`, `tests/mesh/test_mobile_base.py`, `tests/tools/test_use_rosbridge.py`.

Local, not upstream:
- `~/strands-robots-cont/robots` branches `fix/use-ros-echo-qos` (3 commits) and `feat/use-ros-params` (3 commits): QoS-adaptive echo + params; needs rebase onto `strands_robots/ros.py`.
- `~/strands-robots-cont/robots` branch `feat/curiosity-sim-harness`: `examples/rosbridge/curiosity_sim/{Dockerfile,docker-compose.yml,start.sh,README.md}`.
- `~/strands-robots-curiosity/docker-compose.yml`, `docker/`, `curiosity_agent/agent.py`.
- `~/strands-robots-ros2/src/strands_robots_ros2/runtime/deepracer_v2/client.py` (console REST client, Apache bucket), `runtime/ros2/adapter.py` (`_maybe_call_enable_state`, `_make_qos_profile`), `runtime/ros2/lifecycle.py`, `registry/robots.json` (`aws_deepracer`, `aws_deepracer_http`), `skills/nav2.py` (PolyForm NC).
- `~/strands-robots` branch `feat/deepracer-example`: `strands_robots/deploy.py`, `scripts/setup_deepracer.sh`, `example/deepracer_drive.py`; working tree `example/deepracer/deepracer_ros2_navigation.py` + README (cmdvel_to_servo_pkg path).
- `~/strands-deepracer/aws-deepracer-interfaces-pkg` (msg/srv ground truth), `aws-deepracer-webserver-pkg/webserver_pkg/vehicle_control.py` (REST -> ROS mapping), `aws-deepracer-ctrl-pkg`, `aws-deepracer-servo-pkg`, `aws-deepracer-camera-pkg`.
- `robots-decider/bench_decider_judge.py` (the author's local checkout) + `~/strands-robots-prs` branch `feat/decider-episode-judge` (`strands_robots/tools/decider_judge.py`).

---

## 10. Gaps and recommendations for the new DeepRacer project

1. **No ROS 2 on the Mac.** Three viable control paths from this laptop: (a) run `rosbridge_server` on the car (ROS 2 Foxy has `ros-foxy-rosbridge-suite`) and drive via `use_rosbridge`/`RosbridgeRobot` - pure pip, proven on Curiosity; a `MobileBaseRobot` subclass with a rosbridge `Transport` and the Ackermann `_cmd_fields` override would give a DeepRacer-over-rosbridge class in ~100 lines; (b) run the agent on the car (`setup_deepracer.sh` installs py3.12 onboard) with `AckermannRosRobot` under sourced Foxy; (c) the console REST path (`DeepRacerV2Client` / `aws_deepracer_control_v2`), no ROS at all, already battle-tested in 2026-03..05.
2. **Lidar read is broken on hardware until the QoS fix lands** (`/rplidar_ros/scan` BEST_EFFORT vs RELIABLE default). Rebase `fix/use-ros-echo-qos` onto `strands_robots/ros.py` and open it, or expose a `qos` knob. rosbridge does not have this issue.
3. **No odometry on stock DeepRacer**; the ROS2 registry entry in strands-robots-ros2 only subscribes `tf`/`tf_static`. Any closed-loop behaviour needs the camera (`/camera_pkg/display_mjpeg`, or REST `route?topic=/display_mjpeg`) - the Phase-3 `camera_stream.py`/`vision_assessor.py` pattern and the decider abstention pattern (fit B in PLAN.md) are the prior art.
4. **Live DeepRacer verification of `AckermannRosRobot` was never done** (spec said "availability unconfirmed", upstream fragment says pending). The car was last seen at 192.168.0.3/.4/.8.
5. **Licensing**: anything lifted from `strands-robots-ros2`'s `runtime/rosbridge.py`, `skills/nav2.py`, `examples/` or the `curiosity` registry entry is PolyForm Noncommercial; the DeepRacer runtimes and translators are Apache-2.0.
6. **Repo hygiene**: HOME is a git repo - scope adds; follow `changelog.d/` fragments; deepdive docs predate #4140, so read `strands_robots.mesh.*` as `strands_robots.drivers.ros.*`.
