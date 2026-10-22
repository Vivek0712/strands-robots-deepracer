# Stock Ubuntu 20.04 / ROS 2 Foxy car: rosbridge install (done 2026-10-14 on amss-abcd)

The car arrived as stock `aws-deepracer-core 2.0.113.0` (Foxy), not the community Jazzy image.
`install_deepracer_stack.sh` refuses non-noble on purpose; this is what was done by hand over SSH.

1. Console API `GET /api/enableSsh` (after login) opened SSH; `ssh-keygen -R <ip>` dropped the pre-flash host key.
2. The stock ROS apt key had expired (`EXPKEYSIG F42ED6FBAB17C654`). Fix: fetch
   `https://raw.githubusercontent.com/ros/rosdistro/master/ros.key`, dearmor to
   `/usr/share/keyrings/ros-archive-keyring.gpg`, replace `ros2-latest.list` with
   `deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu focal main`.
   `intel-openvino-2021.list` disabled (its TLS cert fails); `snapshots.ros.org/foxy/final` is signed by a
   key apt does not have (`AD19BAB3CBF125EA`), not needed because packages.ros.org still serves focal.
3. `apt-get install ros-foxy-rosbridge-suite` (1.3.1-1focal.20230527), `ufw allow 9090/tcp`.
4. `/usr/local/bin/deepracer-rosbridge.sh` sources `/opt/ros/foxy/setup.bash` and
   `/opt/aws/deepracer/lib/setup.bash`, then `ros2 launch rosbridge_server rosbridge_websocket_launch.xml
   port:=9090 address:=0.0.0.0`; `deepracer-rosbridge.service` (After=deepracer-core) enabled.

Gotcha for scripts: `echo "$pw" | sudo -S tee file` feeds the password to sudo and nothing to tee; the
file ends up empty. Use `sudo -S bash -c 'echo ... > file'`.

5. First start failed twice. (a) `Failed to get users home directory`: systemd gives no HOME, fixed with
   `Environment=HOME=/root` and `Environment=ROS_LOG_DIR=/var/log/deepracer-rosbridge` in the unit.
   (b) `Could not import 'rosidl_typesupport_c' for package 'rosbridge_msgs'`, really
   `librosbridge_msgs__rosidl_generator_c.so: undefined symbol: rosidl_runtime_c__String__copy`: the car's
   Foxy base is the 2021-02 build (`ros-foxy-rosidl-runtime-c 1.2.0`) and the rosbridge debs are the
   2023-05 final Foxy build (needs 1.3.1). Fixed by `apt-get install --only-upgrade ros-foxy-rosidl-runtime-c`
   (ABI-additive within Foxy; deepracer-core keeps running). The other 1177 upgradable packages were left alone.

## Hardware inventory from the stock image (read-only, 2026-10-14)

- Bluetooth: `rfkill list` shows only `phy0: Wireless LAN`; `bluetoothctl list` says "No default
  controller available" although `bluetooth.service` is active. The car exposes no Bluetooth radio
  to Linux, so a Bluetooth speaker cannot pair to the car. Showcase audio comes from the laptop (or a
  USB speaker on the car's hub); plan accordingly in report 12/13.
- Audio: `/proc/asound/cards` is empty ("no soundcards"); PulseAudio runs with no sink. No speaker on
  the car.
- USB: SanDisk Ultra (the OS stick), two `3554:fc00` devices (Compx 2.4G keyboard/mouse receivers
  plugged in for the console, not cameras), `214b:7250` hub. No UVC camera (`/dev/video*` absent,
  `uvcvideo` not loaded) and no CP210x serial adapter. The console agrees:
  `GET /api/get_sensor_status` returns camera, stereo and lidar all `not_connected`. The camera
  USB lead and the LiDAR lead must be reconnected to the compute board before any vision beat.
- Drive battery: `/i2c_pkg/battery_level` returns `-1` continuously (node logs `battery_life byte:0xc
  level:-1`) across a power cycle (car rebooted 19:58 car-time; earlier boot 18:58). The ESC and
  steering servo get power only from the 7.4 V vehicle pack, so PWM changes (seen on
  `/sys/class/pwm/pwmchip0/pwm0`) do not move the wheels until the pack is plugged into the ESC lead,
  switched on, and the ESC button held until its LED lights. The console shows a percentage when the
  node sees it.

## Stock updater and the camera-node memory leak (2026-10-14)

- The stock `software_update` node upgraded the car on its own at 19:39 car-time (apt history):
  `aws-deepracer-core` 2.0.113.0 -> 2.0.383.0, `device-console` 2.0.28.0 -> 2.0.196.0,
  `util` 2.0.10.0 -> 2.0.61.0, `sample-models`. The 19:57 reboot followed it. The hop was first
  proven on 2.0.113.0 and re-proven on 2.0.383.0 (ctrl relays throttle 0.3 on `/ctrl_pkg/servo_msg`).
- With no camera attached, the stock `camera_node` logs `Publishing camera images to topics failed
  ... ros_message argument is null` about 500 times a second from the moment it starts, whether or
  not `/camera_pkg/media_state activate_video=0` is called. The Foxy `ros2 launch` parent that
  captures that output grew to 2.5 GB RSS in about an hour on a 3.7 GB, no-swap car: `kswapd0`
  thrashing, load 30+, OOM kills of `software_update` and `device_info_node`, rosbridge service
  calls timing out ("No service response received"). The journal is volatile and the flood rotates
  it in about four minutes, so earlier evidence is lost.
- Mitigation applied this boot (not persistent): `systemctl restart deepracer-core` (memory back
  to 2.6 GB free), `systemctl restart deepracer-rosbridge` so rosapi re-discovers the restarted
  nodes, then `pkill -f camera_pkg/camera_node`. The launcher logs `camera_node-1 process has died
  (exit code -15)` and keeps the rest of the stack up; the flood stops, load drops below 4.
- Durable fix, in order of preference: (1) reconnect the camera; (2) if the car must run headless
  for long, a `deepracer-camera-guard` oneshot unit that kills `camera_node` when
  `/dev/video0` is absent, or a `MemoryMax=` on `deepracer-core` so the OOM killer hits the
  launcher first instead of the stock nodes. Neither has been installed; the user decides.
- Battery byte moved from `0xc` to `0x0`, level still `-1`: the drive pack is not seen.

## PWM outputs disabled after boot (2026-10-14, core 2.0.383.0)

- Symptom: drive pack connected, ESC armed (LED lit), console battery still `-1`; a steering sweep
  and a 0.5 throttle hop over rosbridge changed `/sys/class/pwm/pwmchip0/pwm0/duty_cycle` (throttle,
  neutral 1446000 ns) and `pwm1/duty_cycle` (steering) but the wheels and the steering did not move.
- Cause: `pwm0/enable` and `pwm1/enable` read `0`. The stock `servo_node` (log: `Servo syspath:
  /sys/class/pwm/pwmchip0`, five exports about 10 s after `deepracer-core` starts) writes `period`
  (20000000 ns) and `duty_cycle` but never writes `enable`. A PCA9685 channel with enable=0 outputs
  nothing, however correct the duty is. The console's own calibration page presumably enables them
  on a different path; nobody had run it on this boot.
- Hand fix this boot: `echo 1 > /sys/class/pwm/pwmchip0/pwm0/enable` and the same for `pwm1`; the
  same hop then moved the wheels on the stand. The flags survive duty writes (checked after several
  hops) and are not reset by the servo node.
- Durable fix: `car/pwm/deepracer-pwm-enable.{sh,service}` installed by `car/install.sh`: oneshot,
  `After=deepracer-core.service`, `PartOf=deepracer-core.service`, waits up to 60 s for both channels
  to exist with a non-zero period, writes 1 to both `enable` files, logs the before/after values with
  `logger -t deepracer-pwm-enable`. Verified: `systemctl is-active deepracer-pwm-enable` = `active`,
  both flags 1. The laptop preflight reports `pwm_outputs` (CONTRACTS section 4) so a boot where the
  oneshot lost the race is a visible no-go, not a silent car.
- Battery: the i2c node still reads level `-1` with changing raw bytes while the pack powers the ESC;
  the thin monitor lead is the suspect (user checking). The ESC does not need it to move.
- The red tail LED on an idle car was our deadman's trip indicator left on after the last trip; the
  deadman now turns the LED off when it goes idle after 30 s (`ACTION_LED_OFF`).
