# car/: what runs on the DeepRacer itself

The stock car is Ubuntu 20.04, ROS 2 Foxy, Python 3.8 (`aws-deepracer-core` 2.0.383.0). Everything
here is Python 3.8 compatible and installed from the laptop over SSH. Nothing here drives the car;
these are the pieces of the safety story that must live on the car because they must survive the
laptop, the Wi-Fi and the router being pulled. Physics stops the car; the decider explains.

| Path | What |
|---|---|
| `connect/car.sh` | laptop helper: `car.sh ssh '<cmd>'`, `push`, `preflight` (reads `~/.config/deepracer/env`; `DEEPRACER_HOST=auto` finds the car, see `connect/find-car.sh` and `docs/dev/networking.md`) |
| `bootstrap/` | how rosbridge was installed on the Foxy image, plus the OOM hazard notes |
| `deadman/` | `deepracer_deadman` ament_python package: the heartbeat deadman node, unit, runner |
| `guard/` | `deepracer-camera-guard` oneshot + 30 s timer: kills the stock `camera_node` after the camera has been absent for three checks (a USB stick plugged into the car resets the hub for about a minute), and relaunches it when `/dev/video0` is back |
| `pwm/` | `deepracer-pwm-enable` oneshot: writes 1 to `pwmchip0/pwm0,pwm1/enable` after the stock servo node exports them (it never does) |
| `install.sh` / `rollback.sh` | install all three on the car (`sudo -S bash -c`, password on stdin only) and remove them again |

## Topics and services the project uses

| Name | Type (ROS 2 name; rosbridge uses the two-segment form) | Direction |
|---|---|---|
| `/webserver_pkg/manual_drive` | `deepracer_interfaces_pkg/msg/ServoCtrlMsg {float32 angle, float32 throttle}` in [-1, 1] | laptop -> car, 20 Hz, zero pair at the end |
| `/ctrl_pkg/servo_msg` | `ServoCtrlMsg` | ctrl node -> servo node; the deadman also writes zeros here |
| `/deepracer_agent/heartbeat` | `std_msgs/msg/Header` (`stamp` = laptop time, `frame_id` = session id) | laptop -> car, 20 Hz while driving, 5 Hz while armed |
| `/deepracer_agent/deadman_state` | `std_msgs/msg/String`, JSON `{"state": "idle|armed|tripped", "gap_ms": int, "since": iso8601, "trips": int}` | car -> laptop, 2 Hz and on change |
| `/ctrl_pkg/vehicle_state` | `srv/ActiveStateSrv {int8 state} -> {int32 error}`; 0 manual, 1 autonomous, 2 calibration | arming, step 1 |
| `/ctrl_pkg/enable_state` | `srv/EnableStateSrv {bool is_active} -> {int32 error}` | arming, step 2 (always after a mode change) |
| `/i2c_pkg/battery_level` | `srv/BatteryLevelSrv {} -> {int32 level}`; -1 = pack not seen or too low, else 0..10 | read |
| `/servo_pkg/set_led_state` | `srv/SetLedCtrlSrv {int32 red, int32 green, int32 blue} -> {int32 error}`, 0..10000000 per channel | LED |
| `/servo_pkg/get_calibration` | `srv/GetCalibrationSrv {int32 cal_type} -> {int32 max, int32 mid, int32 min, int32 polarity, int32 error}`; cal_type 0 steering, 1 throttle | read only, never written |

Field names verified 2026-10-14 with `ros2 interface show` over SSH on the car. Note the stock
`SetLedCtrlSrv.srv` comments label `green` as "BLUE channel" and `blue` as "GREEN channel"; the
field names are `red, green, blue` in that order and that is what the driver sends.

Gotcha: as the `deepracer` user, `ros2 topic list` shows only `/parameter_events` and `/rosout`.
The stock nodes run as root and Foxy's default FastRTPS shared-memory transport does not cross
users. Anything that must see the stock graph (the deadman) runs as root under systemd, exactly like
`deepracer-rosbridge.service`; for a hand check use `sudo -S ... ros2 topic list`.

## The deadman rule (CONTRACTS section 3)

- `idle`: no heartbeat yet, or none for 30 s. Does nothing.
- First heartbeat: `armed`, and the tail LED goes **green** (the stage "go").
- `armed` and the gap since the last heartbeat exceeds **300 ms**: `tripped`. The node publishes
  **ten zero `ServoCtrlMsg` at 20 Hz on both `/ctrl_pkg/servo_msg` and `/webserver_pkg/manual_drive`**,
  and sets the tail LED red through `/servo_pkg/set_led_state` (async, 1 s timeout, never blocks the zeros).
- While `tripped`, every non-zero `ServoCtrlMsg` the node hears on `/webserver_pkg/manual_drive`
  restarts the zero burst (a stream that outlived its heartbeat, a stale console slider). Zero pairs,
  including the node's own, are ignored, so there is no feedback loop. Count: `rezeros` in the log.
- `tripped` is latched until heartbeats have been arriving steadily (no gap over 300 ms) for **1 s**,
  then `armed` again and the LED goes green.
- `idle` after 30 s without a heartbeat (from `armed` or `tripped`): the LED goes **off**
  (`{red: 0, green: 0, blue: 0}`). The red LED is the trip indicator and nothing else; before this
  (2026-10-14) a tripped car left on the bench stayed red until something else touched the LED.
- `deadman_state` JSON goes out at 2 Hz and immediately on every change.

The rule is pure Python in `deadman/deepracer_deadman/deadman_logic.py` and is unit-tested on the
laptop (`tests/unit/test_deadman_logic.py`, no rclpy). `deadman_node.py` is the rclpy wrapper: a
50 Hz tick, a heartbeat subscriber, a `manual_drive` subscriber, a 20 Hz zero-burst timer, an async
LED client.

Laptop side: `deepracer_agent.transport.HeartbeatPublisher` ticks the heartbeat; the driver turns it
to 20 Hz around every command stream; `stop_deepracer` turns it off on purpose, so the deadman's zeros
back up the laptop's zero pair.

## Install, verify, roll back

```
bash car/install.sh              # rsync car/deadman + car/guard + car/pwm, colcon build in /opt/deepracer-agent/ws, enable units
bash car/connect/car.sh ssh 'systemctl is-active deepracer-deadman deepracer-camera-guard.timer deepracer-pwm-enable'
bash car/connect/car.sh ssh 'cat /sys/class/pwm/pwmchip0/pwm0/enable /sys/class/pwm/pwmchip0/pwm1/enable'   # 1 and 1
bash car/rollback.sh             # stop/disable/remove units, workspace and source copy (leaves the enable flags as they are)
```

`install.sh` restarts only `deepracer-deadman.service` (so a new node build is loaded); the guard timer
and the PWM oneshot are `enable --now`. It never restarts `deepracer-core`.

Verify the trip from the laptop (the car needs no drive battery; the servo node still relays):

```
set -a; . ~/.config/deepracer/env; set +a
DEEPRACER_BODY=car .venv/bin/python -m deepracer_agent.transport --check-deadman --hold 3 --wait 4
# heartbeats 3 s (armed), silence, expects tripped + zeros on /ctrl_pkg/servo_msg; 30 s later the
# node logs "deadman -> idle" and the tail LED goes off (pwm2..4 duty back to 0).
```

Files on the car after install: `/opt/deepracer-agent/ws` (colcon workspace), `/opt/deepracer-agent/deepracer-deadman.sh`,
`/opt/deepracer-agent/deepracer-camera-guard.sh`, `/opt/deepracer-agent/deepracer-pwm-enable.sh`,
`/etc/systemd/system/deepracer-deadman.service`, `/etc/systemd/system/deepracer-camera-guard.{service,timer}`,
`/etc/systemd/system/deepracer-pwm-enable.service`, logs in `/var/log/deepracer-agent`,
`journalctl -u deepracer-deadman` and `journalctl -t deepracer-pwm-enable`. `install.sh` never restarts
`deepracer-core`, never touches `/opt/aws/deepracer/calibration.json` and never reboots.

## PWM outputs: the stock servo node never enables them

Found 2026-10-14 with the drive pack connected and the ESC armed: steering sweeps and a 0.5 throttle
hop changed `/sys/class/pwm/pwmchip0/pwm0/duty_cycle` (throttle) and `pwm1/duty_cycle` (steering)
exactly as expected, and the wheels did not move. Both channels had `enable=0`. The stock
`servo_node` exports the five PCA9685 channels (pwm0 throttle, pwm1 steering, pwm2..4 tail LED)
about 10 s after `deepracer-core` starts and writes `period` and `duty_cycle`, but never writes
`enable`; the chip then outputs no pulses at all. `echo 1 > .../pwmN/enable` by hand and the same
hop moved the wheels (on the stand).

`pwm/deepracer-pwm-enable.sh` is the durable fix: a oneshot `After=deepracer-core.service`
(`PartOf=` too, so a core restart re-runs it) that waits up to 60 s for `pwm0` and `pwm1` to exist
with a non-zero period, writes 1 to both `enable` files, and logs `pwmN enable 0 -> 1` with the
period and duty it saw (`journalctl -t deepracer-pwm-enable`). It never writes period, duty,
polarity or calibration. `systemctl is-active deepracer-pwm-enable` reads `active` once it has
run (`RemainAfterExit=yes`). The laptop's `preflight` reads the two flags over SSH on `car` and
reports `pwm_outputs: ok|disabled|unknown`; anything but `ok` is a no-go.

Whether a positive throttle on the ROS path is forward is still unverified: it needs the wheels on
the floor (`THROTTLE_FORWARD_SIGN` in `src/deepracer_agent/calibration.py`).

## Camera guard

With no camera attached the stock `camera_node` logs about 500 errors a second and the Foxy launch
parent grows to 2.5 GB RSS in roughly an hour, after which the OOM killer takes out stock nodes and
rosbridge calls time out (`bootstrap/foxy-rosbridge.md`). `guard/deepracer-camera-guard.sh` runs every
30 s from a systemd timer: if `/dev/video0` is absent and a process matching the anchored stock binary
path `^/opt/aws/deepracer/lib/camera_pkg/lib/camera_pkg/camera_node` exists, it is killed and one line
is logged (`logger -t deepracer-camera-guard`) until the camera comes back. The pattern cannot match the
guard's own command line. The launcher logs `camera_node-1 process has died` and keeps the rest up.
The durable fix is still to plug the camera in.
