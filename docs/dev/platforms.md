# Platforms: one protocol, one real car, one fake, and where the twelve old adapters went

The earlier repo (`Vivek0712/strands-agentic-deepracer`, `use_cases/`) carried twelve platform
adapters behind a nine-function `RobotTools` protocol so one planner could drive "any robot"
(report 07 section 2.5). None was run on hardware, the DeepRacer adapter itself raised
`TypeError` on first use, and `lawnmower copy.py` was a stray duplicate. strands-robots already
has the real version of that idea: a registry of drivers behind one `HardwareDriver` contract,
with `MobileBaseRobot` for anything that takes `(linear, angular)` on a ROS topic. This project's
driver is a DeepRacer and nothing else by design (CONTRACTS section 1), so the idea is absorbed as
one small abstraction and this page; no code for the other platforms lives here.

## The abstraction: `src/deepracer_agent/platforms.py`

| Name | What it is | Who satisfies it |
|---|---|---|
| `DriveStop` (Protocol) | `drive(linear, angular, duration)`, `stop()`: all `execute_plan` needs | `DeepRacerRobot` directly, `SimPlatform`, `DeepRacerPlatform` |
| `MobilePlatform` (Protocol) | `DriveStop` plus `capture_frame()`, `battery()`, `preflight()`: what the beats, plans and kiosks rely on | `DeepRacerPlatform`, `SimPlatform` |
| `DeepRacerPlatform` | the real car: composes the Car team's `DeepRacerRobot`, `ConsoleClient` and `Preflight`; `from_runtime(AgentRuntime)` | the gate, caps and zero pair are the driver's, untouched |
| `SimPlatform` | a fake car in memory: the driver's refusals (finite numbers, speed cap, hop cap, no yaw at rest), the bicycle model for its pose, `commands`/`stops` recorders, `fail_after` | unit tests of `execute_plan` and the policies run on it with no sockets |

`SimPlatform` is not the fake car in `harness/` (the QA team's rosbridge-protocol server). It is
the in-process stand-in a unit test uses; the harness fake is what `python -m beats shapes --body
sim` drives through the real transport.

## Where the twelve adapters map

Classification: the kinematic class decides the planner; the transport decides the upstream
driver family. "Would be" means what the adapter would become if someone built it on
strands-robots; nothing below is built here.

| Earlier adapter | Kinematics | Transport in the old code | Would be upstream | Shape plans apply? |
|---|---|---|---|---|
| `deepracer.py` | Ackermann (min radius 0.28 m) | HTTP console (broken: `move()` had no `duration`) | **this project**: `DeepRacerRobot(MobileBaseRobot)` over rosbridge `ServoCtrlMsg` | yes: this is what `shapes.py` plans for |
| `rover.py` | differential | rosbridge `/cmd_vel` Twist | `MobileBaseRobot` subclass, `cmd_vel` Twist (upstream has this already) | yes, and it can also pivot: the no-yaw-at-rest rule would relax |
| `roomba.py` (Create 3) | differential | rosbridge `/cmd_vel` Twist | `MobileBaseRobot` subclass | yes |
| `lawnmower.py` (+ stray `lawnmower copy.py`) | differential | rosbridge `/cmd_vel` + `/boundary` | `MobileBaseRobot` subclass plus a boundary read tool | yes; the pen becomes the boundary polygon |
| `hospital_cart.py` | differential, slow (0.6 m/s cap) | rosbridge `/cmd_vel` + `/floor_map` | `MobileBaseRobot` subclass with a tighter `max_linear` | yes |
| `solar_inspection.py` | differential | rosbridge `/cmd_vel` | `MobileBaseRobot` subclass plus thermal/RGB read tools | yes (straight and slalom rows along panels) |
| `camera_dolly.py` | 1-DOF track + pan | TCP or serial JSON | a `HardwareDriver`, not a mobile base | only `straight`/`back`; no turns |
| `pipeline_crawler.py` | 1-DOF in a pipe (turn radius infinite) | TCP JSON | a `HardwareDriver`, not a mobile base | only `straight`/`back` |
| `drone.py` | holonomic, yaws in place | MAVLink via DroneKit | a `HardwareDriver` with its own verbs (`takeoff`, `land`); not `MobileBaseRobot` | geometry yes, kinematics no: the bicycle model does not apply |
| `boat.py` | Ackermann-like (rudder, radius 1.5 m) | MAVLink via DroneKit | a `HardwareDriver`; could reuse the plan validator with a 1.5 m radius | yes with a much larger pen |
| `underwater_rov.py` (ArduSub) | holonomic, 6-DOF thrusters | MAVLink via DroneKit | a `HardwareDriver` with depth verbs | geometry only |
| `robot_arm.py` | arm (6-DOF end effector) | MoveIt2 via rosbridge | an arm driver (upstream has arm drivers); not mobile at all | no |
| `warehouse_robot.py` | listed in the old README and Kiro spec, absent from the clone | | | |

Counts: 6 differential (`MobileBaseRobot` subclasses), 2 Ackermann-like (this car and the boat),
2 holonomic (drone, ROV), 2 one-degree-of-freedom (dolly, crawler), 1 arm.

## What the old `RobotTools` protocol became

| Old function / constant | Here |
|---|---|
| `connect()` | the driver's manual-mode handshake in `DeepRacerRobot.enable` (retried; CONTRACTS section 0) |
| `move_forward(s)`, `move_backward(s)`, `turn_left(s)`, `turn_right(s)` | one verb, `drive(linear, angular, duration)`; the bicycle model turns it into the servo pair |
| `stop()` | `stop()`; also the trailing zero every timed drive sends from `finally` |
| `is_error(msg)` | tool results are structured (`status: error`), no string sniffing |
| `reset_client()` | `RosbridgeTransport` reconnects; the heartbeat and deadman cover a dead link |
| `activate_camera()` | `ConsoleClient.capture_frame` (fails closed: no frame, no motion) |
| `PHYSICS_MIN_TURN_RADIUS_M` | `Calibration.min_turn_radius_m` (measured 0.28) and `bicycle_min_turn_radius_m` (model, 0.284) |
| `PHYSICS_MAX_CORNER_SPEED` | not needed: `Calibration.max_speed_mps` is 0.3, far below the 1.5 m/s skid speed |
| `PHYSICS_FWD_SPEED_MS`, `PHYSICS_TURN_SPEED_MS` | `shapes.Geometry.cruise_mps` (0.3) and `turn_mps` (0.25) |
| `PLATFORM_NAME`, `PLATFORM_DESC` | `MobilePlatform.name` |

Physics stops the car; the decider explains. A platform, real or fake, only moves when a gated
command says so.
