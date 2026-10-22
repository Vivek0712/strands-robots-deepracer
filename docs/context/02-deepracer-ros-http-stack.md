# AWS DeepRacer physical car: ROS 2 + HTTP control stack (research report)

Date of research: 2026-10-12. Purpose: give a strands-robots engineer everything needed to drive a
DeepRacer from an external Python agent via (a) rclpy/DDS, (b) rosbridge websocket, (c) the on-car
HTTPS webserver, plus simulation options. Every claim carries a URL. Source files were fetched raw
from GitHub on 2026-10-12 and quoted verbatim where load-bearing; "verified" means read from source,
"general ROS knowledge" is flagged where no DeepRacer-specific source exists.

Downloaded raw sources are cached under
`<scratch>/research/dl/`
(`iface/*.msg|*.srv`, `src/*.cpp|*.py`, `web/*.py`, `launcher/*.md`, `cc/*` for the community car,
`nav2/*` for the AWS Nav2 repo, `lshw/*` for the HTTP client).

---

## 0. Executive summary (the facts that matter for a driver)

| Question | Answer | Source |
|---|---|---|
| Is DeepRacer dead? | AWS console service ended **2025-12-15**; devices no longer sold. Replaced by self-hosted open-source **DeepRacer on AWS** (released 2026-01-26/27, v1.3.2 on 2026-10-07). Device OS images Ubuntu 16.04/20.04 are "no longer supported" by AWS; AWS shipped a **developer shim bootloader** (blog 2026-07-20) so the community stack (Ubuntu 24.04 + ROS 2 Jazzy, v2.1.9.9, 2026-08-11) can be installed. The aws-deepracer GitHub org is dormant (last real code push 2024-05) but not archived. | [FAQ](https://aws.amazon.com/deepracer/faqs/), [custom OS blog](https://aws.amazon.com/blogs/machine-learning/custom-os-installation-now-available-on-aws-deepracer-devices/), [DRoA changelog](https://github.com/aws-solutions/deepracer-on-aws/blob/main/CHANGELOG.md), [custom-car releases](https://github.com/aws-deepracer-community/deepracer-custom-car/releases) |
| Manual-drive topic | Webserver publishes `ServoCtrlMsg` on **`/webserver_pkg/manual_drive`**; `ctrl_node` (in manual mode AND enabled) re-publishes it on **`/ctrl_pkg/servo_msg`**; `servo_node` subscribes to `/ctrl_pkg/servo_msg` and `/ctrl_pkg/raw_pwm`. An external node may publish to either. | [ctrl_node.cpp](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg/blob/main/ctrl_pkg/src/ctrl_node.cpp), [servo_node.cpp](https://github.com/aws-deepracer/aws-deepracer-servo-pkg/blob/main/servo_pkg/src/servo_node.cpp) |
| Message | `deepracer_interfaces_pkg/msg/ServoCtrlMsg {float32 angle, float32 throttle}` in [-1,1] (or raw PWM ns on `raw_pwm`). | [ServoCtrlMsg.msg](https://github.com/aws-deepracer/aws-deepracer-interfaces-pkg/blob/main/deepracer_interfaces_pkg/msg/ServoCtrlMsg.msg) |
| Modes | `ActiveStateSrv.state`: **0 = manual, 1 = autonomous, 2 = calibration** (FTL sample adds 3). `EnableStateSrv.is_active` starts/stops the active mode. Node boots in manual mode, enabled. | [webserver constants.py MODE_DICT](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/constants.py), [ctrl_node.cpp init()](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg/blob/main/ctrl_pkg/src/ctrl_node.cpp) |
| Watchdog | **None** in stock `ctrl_node`/`servo_node`: the last PWM value persists until a new message or a mode/enable transition (which publishes `0,0`). Your agent must send its own zero on exit. | servo_mgr.cpp / ctrl_state.cpp (verified, see 6.5) |
| HTTP auth | `POST /login` (form `password=`, header `X-CSRFToken` from `<meta name="csrf-token">`) → cookie `deepracer_token` (uuid4, 1 h). nginx `auth_request /auth` guards all `/api/*` and `/route`. Password stored as **SHA-224 hex** in `/opt/aws/deepracer/password.txt`; default = `/sys/class/dmi/id/chassis_asset_tag` (the sticker), fallback `deepracer`. | [login.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/login.py), [nginx.default (community copy)](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/build_scripts/files/common/nginx.default) |
| HTTP drive | `PUT /api/drive_mode {"drive_mode":"manual"}` → `PUT /api/start_stop {"start_stop":"start"}` → `PUT /api/manual_drive {"angle":a,"throttle":t,"max_speed":m}` (a,t ∈ [-1,1], m ∈ [0,1]). Server **quantizes** |a|,|t| to {0.3,0.5,0.8}, negates both, and rescales throttle non-linearly by `max_speed`. | [vehicle_control.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/vehicle_control.py) |
| Camera over HTTP | `GET https://<ip>/route?topic=/camera_pkg/display_mjpeg&width=480&height=360` (nginx → `web_video_server` on `127.0.0.1:8080/stream`, auth cookie required). | nginx.default, [dev.to post](https://dev.to/mkreder/how-to-stream-video-from-the-deepracer-camera-mci) |
| Best community HTTP client | `lshw54/awsdeepracer_control` (PyPI `awsdeepracer-control` 0.2.0, 2023-09-25, MIT, targets console 2.0.383.0). | [repo](https://github.com/lshw54/awsdeepracer_control), [PyPI](https://pypi.org/project/awsdeepracer-control/) |
| Twist → servo | AWS ships `cmdvel_to_servo_pkg` (subscribes `/cmd_vel`, publishes `/cmdvel_to_servo_pkg/servo_msg`; MAX_SPEED 4 m/s, MAX_STEER 0.5236 rad; quantized output). It is NOT on the stock image. | [cmdvel_to_servo_node.py](https://github.com/aws-deepracer/aws-deepracer/blob/main/deepracer_nodes/cmdvel_to_servo_pkg/cmdvel_to_servo_pkg/cmdvel_to_servo_node.py) |
| Geometry | URDF: wheelbase **0.164 m** (hinge x=+0.082311, rear x=−0.081663), rear track **0.162 m**, front hinge track 0.159 m, wheel radius 0.03 m, chassis mass 1.9 kg. Default action space ±30°, 0.4/0.8 m/s. | [deepracer URDF](https://github.com/aws-deepracer/aws-deepracer/blob/main/deepracer_description/models/xacro/urdf/deepracer_stereo_cameras_and_lidar_urdf.xacro), [nav constants.py](https://github.com/aws-deepracer/aws-deepracer-navigation-pkg/blob/main/deepracer_navigation_pkg/deepracer_navigation_pkg/constants.py) |
| rosbridge | Not installed by stock or community images. `rosbridge_suite` is in rosdistro for foxy, humble, jazzy, kilted → `apt install ros-$ROS_DISTRO-rosbridge-suite`. | [rosdistro foxy](https://raw.githubusercontent.com/ros/rosdistro/master/foxy/distribution.yaml), [rosdistro jazzy](https://raw.githubusercontent.com/ros/rosdistro/master/jazzy/distribution.yaml) |

---

## 1. Device / league / software status as of 2026-10-12

### 1.1 Timeline

- **2018-11** DeepRacer announced at re:Invent (1/18 scale, Intel Atom). [newatlas](https://newatlas.com/amazon-web-services-deepracer/57447/)
- **2020-07-13** DeepRacer Evo + sensor kit (stereo cameras + LiDAR) on sale. [AWS ML blog](https://aws.amazon.com/blogs/machine-learning/aws-deepracer-evo-and-sensor-kit-now-available-for-purchase/)
- **2021-04** Device software open-sourced (ROS 2 Foxy stack, Ubuntu 20.04). [AWS open source blog](https://aws.amazon.com/blogs/opensource/aws-deepracer-is-now-open-source-and-ready-to-hit-the-road-with-ros-2), [TechCrunch](https://techcrunch.com/2021/04/27/amazon-announces-its-open-sourcing-deep-racer-device-software/amp/)
- **2024-12** Final DeepRacer League championship at re:Invent 2024; "Support for DeepRacer in the AWS console will continue through the end of 2025"; a deployable "AWS DeepRacer Solution" promised for Q2 2025. [AWS ML blog (final league)](https://aws.amazon.com/blogs/machine-learning/the-end-of-an-era-the-final-aws-deepracer-league-championship-at-reinvent-2024/), [road ahead](https://aws.amazon.com/blogs/machine-learning/celebrating-the-final-aws-deepracer-league-championship-and-road-ahead/)
- **2025-12-15** Console service retired. FAQ (verbatim): "As of December 15, 2025 AWS DeepRacer as a service is no longer available in the AWS Console" and "AWS DeepRacer Devices are no longer available for purchase on amazon.com." [FAQ](https://aws.amazon.com/deepracer/faqs/)
- **2026-01-26/27** "DeepRacer on AWS" open-source solution released (six weeks late per Lars Ludvigsen). Solution library repo [aws-solutions/deepracer-on-aws](https://github.com/aws-solutions/deepracer-on-aws/) (created 2026-01-12, Apache-2.0, CHANGELOG v1.3.2 2026-10-07). Docs: [solution overview](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/solution-overview.html). First impressions: [builder.aws.com](https://builder.aws.com/content/2otsNvwo08hywC4Ovpr7mi1ySyI/deepracer-is-back-first-impressions-of-deepracer-on-aws)
- **2026-07-20** AWS blog "Custom OS installation now available on AWS DeepRacer devices" (Don Barber, Lars Lorentz Ludvigsen): a self-service **developer shim** bootloader (download `https://s3.amazonaws.com/deepracer-public/shim/deepracer-developer-shim.zip`), blinks "DEVELOPER MODE" in Morse on the LEDs, reversible. States the stock "Ubuntu 16.04 and 20.04 versions ... are no longer supported." Points to [deepracing.io](https://deepracing.io) and [deepracer-custom-car](https://github.com/aws-deepracer-community/deepracer-custom-car). [blog](https://aws.amazon.com/blogs/machine-learning/custom-os-installation-now-available-on-aws-deepracer-devices/)
- The old developer-guide URLs (`docs.aws.amazon.com/deepracer/latest/developerguide/...`) now **redirect** to the DeepRacer-on-AWS solution docs (observed 2026-10-12 for `deepracer-vehicle-connect-wifi.html`, `deepracer-set-up-vehicle-test-drive.html`, `deepracer-how-it-works-overview-reinforcement-learning.html`). The vehicle chapters survive at [Use the vehicle](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/operate-your-vehicle.html): get-to-know, choose-wifi, [launch-device-console](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/launch-device-console.html), [calibrate](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/calibrate-your-vehicle.html), upload-model, [drive](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/drive-your-vehicle.html), [inspect-manage-settings](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/inspect-manage-settings.html), view-vehicle-logs, [update-and-restore-vehicle](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/update-and-restore-vehicle.html).

### 1.2 GitHub activity (github.com/aws-deepracer, 32 repos, none archived among the core packages)

Pushed dates from the GitHub API (2026-10-12):

| repo | last push | note |
|---|---|---|
| aws-deepracer-interfaces-pkg | 2025-07-03 | typo-fix PR only; last substantive 2021-05 |
| aws-deepracer-launcher | 2024-05-15 | readme edit; rplidar_ros bump 2022-05-12; 108 stars |
| aws-deepracer-inference-pkg | 2024-05-04 | |
| aws-deepracer-i2c-pkg | 2024-04-14 | |
| aws-deepracer-model-optimizer-pkg | 2024-03-15 | |
| aws-deepracer (Nav2/Gazebo) | 2023-07-27 | pinned |
| aws-deepracer-systems-pkg | 2023-04-01 | |
| aws-deepracer-notebooks | 2023-02-17 | pinned |
| aws-deepracer-camera-pkg, sensor-fusion-pkg | 2022-10-28 | |
| follow-the-leader, offroad sample projects | 2022-06-06 | |
| aws-deepracer-ctrl-pkg, device-info-pkg, mapping-sample | 2021-06-12 | |
| aws-deepracer-servo-pkg | 2021-11-08 | |
| aws-deepracer-webserver-pkg | 2021-07-28 | |
| aws-deepracer-navigation-pkg | 2021-05-27 | |
| ude*, deepsim, deepracer-env*, ros-kvs-streamer, ros-video-recorder | 2022-07-22 | **archived** (RL Lab) |

Source: [org page](https://github.com/aws-deepracer) + `https://api.github.com/orgs/aws-deepracer/repos`.

Community (github.com/aws-deepracer-community): `deepracer-custom-car` (pushed 2026-08-23, tags v2.1.9.9 2026-08-11, v2.1.9.8 2026-05-24, v2.1.9.7 2026-05-10, v2.1.9.5 2026-03-01, v2.1.8.8 2025-06-22), `deepracer-custom-console` (2026-08-04, TypeScript/Cloudscape, deb v2.2.9), `deepracer-simapp` (2026-10-03, 91 stars), `deepracer-for-cloud` (2026-08-09, 353 stars), `deepracer-utils` (2026-03-22, PyPI 1.5.6). Community site: [deepracing.io](https://deepracing.io). The task's "deepracer.community" did not surface; deepracing.io is the name AWS itself cites.

### 1.3 Hardware

Evo spec table, verbatim from AWS (2020-07-13): CAR "1/18th scale 4WD monster truck chassis"; CPU "Intel Atom Processor"; MEMORY "4 GB RAM"; STORAGE "32 GB (expandable)"; OS "Ubuntu OS 16.04.3 LTS, Intel OpenVINO toolkit, ROS Kinetic"; CAMERA "2 X 4 MP camera with MJPEG"; LIDAR "360 degree 12 meters scanning radius LIDAR sensor"; DRIVE BATTERY "7.4V/1100mAh lithium polymer"; COMPUTE BATTERY "13600 mAh USB-C PD"; WI-FI "802.11ac"; PORTS "4x USB-A, 1x USB-C, 1x Micro-USB, 1x HDMI"; INTEGRATED SENSORS "Accelerometer and Gyroscope". [AWS blog](https://aws.amazon.com/blogs/machine-learning/aws-deepracer-evo-and-sensor-kit-now-available-for-purchase/). Original (non-Evo) has one 4 MP camera, same compute. [i-programmer](https://www.i-programmer.info/news/105/12341.html). The IMU is **not** exposed by any stock ROS node (none of the 15 packages reads it; verified by package inventory below).

- Chassis: "The AWS DeepRacer device uses the WLToys A949 and A979 Remote Control (RC) car chassis." [AWS spare parts page](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-vehicle-chassis-parts.html). A979 retail length 25.3 cm. [elkjop](https://www.elkjop.no/product/sport-hobby-og-fritid/leker/radiostyrte-kjoretoy-og-tilbehor/wltoys-monster-a979-b-118-4wd-70kmh-komplett/200082)
- Camera module: "GeoSemiconductor GC6500 processor with an OmniVision OV4689 ... standard configuration uses a 1920x1080, resized to the requested resolution in the GC6500. The original camera package used 640x480 as input, and scaled down to 160x120 in software." [custom-car docs/camera.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/camera.md)
- LiDAR: Slamtec RPLIDAR (A1-class, UART via CP210x on `/dev/ttyUSB0`, 115200 baud, frame `laser`) per [deepracer_launcher.py](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/deepracer_launcher/launch/deepracer_launcher.py) and `start_ros.sh` ("CP210x UART Bridge" detection) in the community stack.
- Hardware revision detection: GPIO 383/387 → "R1.0"/"R1.1"/"R2.0"/"R2.1" ([device_info_node.py](https://github.com/aws-deepracer/aws-deepracer-device-info-pkg/blob/main/device_info_pkg/device_info_pkg/device_info_node.py)).
- PWM hardware: Intel PWM controller at `/sys/class/pwm/` (PCI `0000:00:17.0`), channel 0 = throttle (ESC), channel 1 = steering servo, 20 ms period; servo power enable via sysfs GPIO **436** (write 0 = enable). Battery via I2C `/sys/class/i2c-dev/` (PCI `0000:00:17.3`), level 0..11 ("The level conversion was given by pegatron"). Sources: [pwm.cpp](https://github.com/aws-deepracer/aws-deepracer-servo-pkg/blob/main/servo_pkg/src/pwm.cpp), [servo_mgr.hpp](https://github.com/aws-deepracer/aws-deepracer-servo-pkg/blob/main/servo_pkg/include/servo_pkg/servo_mgr.hpp), [battery_node.cpp](https://github.com/aws-deepracer/aws-deepracer-i2c-pkg/blob/main/i2c_pkg/src/battery_node.cpp).
- Geometry (from the AWS URDF, verified): rear wheel joints at x=−0.081663, y=±0.08105, z=0.01575; steering hinges at x=+0.082311, y=±0.079601; wheel cylinders radius 0.03 m, length 0.025 m; chassis mass 1.9068 kg. → wheelbase 0.1640 m, rear track 0.1621 m, front (hinge) track 0.1592 m. [deepracer_stereo_cameras_and_lidar_urdf.xacro](https://github.com/aws-deepracer/aws-deepracer/blob/main/deepracer_description/models/xacro/urdf/deepracer_stereo_cameras_and_lidar_urdf.xacro)

### 1.4 Stock software stack and access

- Stock "open-source" stack: Ubuntu 20.04 Focal, OpenVINO 2021.1.110, ROS 2 Foxy, Python 3.8; debs `aws-deepracer-core`, `aws-deepracer-util`, `aws-deepracer-device-console`, `aws-deepracer-sample-models`; service `deepracer-core.service`; install root `/opt/aws/deepracer/`. [getting-started.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/getting-started.md). Factory-restore media: [Ubuntu ISO](https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/ubuntu-20.04.1-20.11.13_V1-desktop-amd64.iso) + [factory_reset.zip](https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/factory_reset.zip); after restore "User: Deepracer / Password: deepracer" (the doc's capitalisation). [update-and-restore-vehicle](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/update-and-restore-vehicle.html)
- ROS 2 Foxy is EOL (docs say EOL; endoflife.date 2023-05-01; QNX docs 2023-06-20). Humble EOL May 2027, Jazzy EOL May 2029. [docs.ros.org EOL](https://docs.ros.org/en/foxy/Releases/End-of-Life.html), [endoflife.date](https://endoflife.date/ros2)
- Device console: `https://<ip>` (self-signed cert; accept the warning). "You can find the default password printed on the bottom of your vehicle (under HostName)." [launch-device-console](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/launch-device-console.html). Over USB-OTG the car is reachable as `https://deepracer.aws` (webserver `SERVER_NAME = "deepracer.aws"`; `/api/is_usb_connected` only reports true when `Referer` contains `deepracer.aws`). [constants.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/constants.py), [wifi_settings.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/wifi_settings.py)
- SSH: Settings → Device SSH → Enable (UI) [inspect-manage-settings](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/inspect-manage-settings.html). Under the hood `GET /api/enableSsh` runs `/usr/sbin/service ssh start` and `/usr/sbin/ufw allow ssh`; `GET /api/isSshEnabled` checks `systemctl status ssh` contains "active (running)" and `ufw status` matches `22.*ALLOW`. Default SSH creds `deepracer` / `deepracer` (`DEFAULT_USER`, `DEFAULT_SSH_PASSWORD`); `/api/isSshDefaultPasswordChanged` PAM-authenticates those. [ssh_api.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/ssh_api.py). Then `ssh deepracer@<ip>`. [getting-started.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/getting-started.md)
- Console password: SHA-224 hex digest in `/opt/aws/deepracer/password.txt`; if the file is missing the server resets it to the digest of `/sys/class/dmi/id/chassis_asset_tag` (the sticker) or `"deepracer"`. [login.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/login.py)

---

## 2. ROS 2 package map (stock Foxy stack; namespaces from `deepracer_launcher.py`)

All nodes are launched by `ros2 launch deepracer_launcher deepracer_launcher.py`, each in a namespace equal to its package name ([deepracer_launcher.py](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/deepracer_launcher/launch/deepracer_launcher.py)). Topic/service names below are fully qualified. End-to-end data flow (community diagram): [ros_data_flow_diagram.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/ros_data_flow_diagram.md).

```
camera_node ─/camera_pkg/video_mjpeg (CameraMsg)──┐
            ─/camera_pkg/display_mjpeg (Image)────┤
rplidar ────/rplidar_ros/scan (LaserScan)─────────┤
                                                   ▼
                                    sensor_fusion_node ─/sensor_fusion_pkg/sensor_msg (EvoSensorMsg)─► inference_node
                                                      ─/sensor_fusion_pkg/overlay_msg (Image)          │ /inference_pkg/rl_results (InferResultsArray)
                                                                                                        ▼
                                                                                   deepracer_navigation_node ─/deepracer_navigation_pkg/auto_drive (ServoCtrlMsg)─┐
webserver_publisher_node ─/webserver_pkg/manual_drive (ServoCtrlMsg)──────────────────────────────────────────────────────────────────────────────┤
                         ─/webserver_pkg/calibration_drive (ServoCtrlMsg, raw PWM)────────────────────────────────────────────────────────────────┤
                                                                                                                                                   ▼
                                                                                                                                              ctrl_node ─/ctrl_pkg/servo_msg ─► servo_node ─► /sys/class/pwm
                                                                                                                                                        ─/ctrl_pkg/raw_pwm  ─►
```

### 2.1 deepracer_launcher ([repo](https://github.com/aws-deepracer/aws-deepracer-launcher))
Launch-only package. Nodes launched (package/namespace/executable): camera_pkg/camera_node (param `resize_images: True`), ctrl_pkg/ctrl_node, deepracer_navigation_pkg/deepracer_navigation_node, deepracer_systems_pkg/{software_update_node, model_loader_node, otg_control_node, network_monitor_node, deepracer_systems_scripts_node}, device_info_pkg/device_info_node, i2c_pkg/battery_node, inference_pkg/inference_node, model_optimizer_pkg/model_optimizer_node, **rplidar_ros2/rplidar_scan_publisher in namespace `rplidar_ros`** (params `serial_port: /dev/ttyUSB0, serial_baudrate: 115200, frame_id: laser, inverted: False, angle_compensate: True`), sensor_fusion_pkg/sensor_fusion_node, servo_pkg/servo_node, status_led_pkg/status_led_node, usb_monitor_pkg/usb_monitor_node, webserver_pkg/webserver_publisher_node, **web_video_server/web_video_server** (namespace `web_video_server`). Dependencies pulled by `install_dependencies.sh`/`rosws`: `async_web_server_cpp`, `web_video_server` (PR #111 branch), `rplidar_ros` (Slamtec ros2 branch). Docs: [readme.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/readme.md), [getting-started.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/getting-started.md), [modes-of-operation.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/modes-of-operation.md), [projects.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/projects.md), [community-projects.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/community-projects.md) (DeepBlaster, DeepDriver, RoboCat).

Build on car (verbatim steps): `sudo su; systemctl stop deepracer-core; source /opt/ros/foxy/setup.bash; source /opt/intel/openvino_2021/bin/setupvars.sh; mkdir -p ~/deepracer_ws && cd ~/deepracer_ws; git clone https://github.com/aws-deepracer/aws-deepracer-launcher.git; cd aws-deepracer-launcher && ./install_dependencies.sh && rosws update && rosdep install -i --from-path . --rosdistro foxy -y && colcon build`; run with `ros2 launch deepracer_launcher deepracer_launcher.py`; install by `cp -r install/ /opt/aws/deepracer/lib` and `systemctl restart deepracer-core`.

### 2.2 ctrl_pkg — node `control_node` in ns `/ctrl_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg), [ctrl_node.cpp](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg/blob/main/ctrl_pkg/src/ctrl_node.cpp), [ctrl_state.cpp](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg/blob/main/ctrl_pkg/src/ctrl_state.cpp))
Note: the executable is `ctrl_node` and the launch `name` is `ctrl_node`, but the C++ constructs `CtrlNodeMgr("control_node")`; the launch name wins.

Subscribed (`rclcpp::QoS(KeepLast(1))` reliable):
- `/deepracer_navigation_pkg/auto_drive` ServoCtrlMsg (autonomous state)
- `/webserver_pkg/manual_drive` ServoCtrlMsg (manual state)
- `/webserver_pkg/calibration_drive` ServoCtrlMsg raw PWM (calibration state)

Published: `/ctrl_pkg/servo_msg` ServoCtrlMsg (manual+auto states), `/ctrl_pkg/raw_pwm` ServoCtrlMsg (calibration state).

Services provided (all `/ctrl_pkg/...`): `vehicle_state` ActiveStateSrv; `enable_state` EnableStateSrv (Reentrant callback group); `model_state` ModelStateSrv; `is_model_loading` GetModelLoadingStatusSrv; `get_car_cal` GetCalibrationSrv; `set_car_cal` SetCalibrationSrv; `get_car_led` GetLedCtrlSrv; `set_car_led` SetLedCtrlSrv; `autonomous_throttle` NavThrottleSrv; `get_ctrl_modes` GetCtrlModesSrv.

Service clients: `/servo_pkg/servo_gpio` ServoGPIOSrv, `/servo_pkg/set_calibration`, `/servo_pkg/get_calibration`, `/servo_pkg/set_led_state`, `/servo_pkg/get_led_state`, `/model_optimizer_pkg/model_optimizer_server` ModelOptimizeSrv, `/inference_pkg/load_model` LoadModelSrv, `/inference_pkg/inference_state` InferenceStateSrv, `/deepracer_navigation_pkg/navigation_throttle` NavThrottleSrv, `/deepracer_navigation_pkg/load_action_space` LoadModelSrv, `/camera_pkg/media_state` VideoStateSrv. Parameters: none declared.

State machine (verbatim, ctrl_node.cpp `init()`):
```cpp
stateList_ = { {autonomous, std::make_shared<SysCtrl::AutoDriveCtrl>(this->shared_from_this(), AUTO_DRIVE_TOPIC)},
           {manual, std::make_shared<SysCtrl::ManualDriveCtrl>(this->shared_from_this(), MANUAL_DRIVE_TOPIC)},
           {calibration, std::make_shared<SysCtrl::CalibrationCtrl>(this->shared_from_this(), CALIBRATION_DRIVE_TOPIC)} };
activeState_ = stateList_.find(manual);
activeState_->second->setStateActive(true);
...
enableVideo();   // calls /camera_pkg/media_state {activate_video: 1}
```
`getCtrlModesHdl` returns `for (int i = manual; i != numStates; i++)` → `[0,1,2]`; the webserver maps `MODE_DICT = {0:"manual", 1:"autonomous", 2:"calibration"}` and `drive_mode_state = 0 if drive_mode == "manual" else 1`, `CALIBRATION_MODE = 2`. **So manual = 0.** (The FTL sample project registers a 4th state and calls `vehicle_state "{state: 3}"`. [FTL README](https://github.com/aws-deepracer/aws-deepracer-follow-the-leader-sample-project))

`stateHdl` (vehicle_state): deactivates the current state (`setStateActive(false)` → publishes `angle=0, throttle=0` on `/ctrl_pkg/servo_msg` and re-enables servo GPIO), then switches `activeState_` to `req->state`; `error=0` on success. **It does not activate the new state** — you must call `enable_state {is_active: true}` afterwards.

`ManualDriveCtrl` (verbatim):
```cpp
void ManualDriveCtrl::servoCB(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr msg) {
    if(!isActive_ || !servoPub_) { return; }
    auto servoMsg = deepracer_interfaces_pkg::msg::ServoCtrlMsg();
    servoMsg.angle = msg->angle;
    servoMsg.throttle = msg->throttle;
    servoPub_->publish(std::move(servoMsg));  // Publish it along.
}
void ManualDriveCtrl::setStateActive(bool isActive) {
    isActive_ = isActive;
    // Stop car and straighten wheels when starting or stopping this state
    auto servoMsg = deepracer_interfaces_pkg::msg::ServoCtrlMsg();
    servoMsg.angle = 0.0;  servoMsg.throttle = 0.0;
    servoPub_->publish(servoMsg);
    enableGPIO(servoGPIOClient_);   // ServoGPIOSrv {enable: 0}  // 0 for enable and 1 for disable
}
```
`AutoDriveCtrl::setStateActive` additionally calls `/inference_pkg/inference_state {start: isActive, task_type: 0}` and only zeroes servo when deactivating. `CalibrationCtrl::servoCB` forwards to `/ctrl_pkg/raw_pwm`; `setCalibration` validates `min <= mid <= max`.

### 2.3 servo_pkg — node `servo_node` in ns `/servo_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-servo-pkg), [servo_node.cpp](https://github.com/aws-deepracer/aws-deepracer-servo-pkg/blob/main/servo_pkg/src/servo_node.cpp), [servo_mgr.cpp](https://github.com/aws-deepracer/aws-deepracer-servo-pkg/blob/main/servo_pkg/src/servo_mgr.cpp))
Subscribed: `/ctrl_pkg/servo_msg` ServoCtrlMsg (normalized), `/ctrl_pkg/raw_pwm` ServoCtrlMsg (raw duty ns). Services: `/servo_pkg/servo_gpio` ServoGPIOSrv, `/servo_pkg/set_calibration` SetCalibrationSrv, `/servo_pkg/get_calibration` GetCalibrationSrv, `/servo_pkg/set_led_state` SetLedCtrlSrv, `/servo_pkg/get_led_state` GetLedCtrlSrv. Parameters: none. (The webserver `constants.py` also lists `/servo_pkg/get_cal`, `servo_cal`, `servo_state`, `set_raw_pwm` — those are **stale names** not present in servo_node.cpp.)

Constants (servo_mgr.hpp, verbatim):
```cpp
#define CAL_FILE_VERSION 1
#define SERVO_MAX 1700000
#define SERVO_MID 1450000
#define SERVO_MIN 1200000
#define MOTOR_MAX 1603500
#define MOTOR_MID 1446000
#define MOTOR_MIN 1311000
#define POLARITY_SERVO_VAL 1
#define POLARITY_MOTOR_VAL -1
#define SERVO_PERIOD 20000000
#define GPIO_CHANNEL 436
```
(ns: period 20 ms = 50 Hz; defaults 1.20–1.70 ms steering pulse, 1.311–1.6035 ms ESC pulse.) Calibration file `/opt/aws/deepracer/calibration.json` with keys `Calibration.Servo{min,mid,max,polarity}`, `Calibration.Motor{...}`, `Calibration.version`; `cal_type` 0 = servo (steering), 1 = motor (throttle).

Mapping (verbatim):
```cpp
void ServoMgr::servoSubscriber(const ServoCtrlMsg::SharedPtr servoMsg) {
    auto setPWM = [&](auto &servo, auto value, auto type) {
        if (value < -1.0 || value > 1.0) { RCLCPP_ERROR(logger_, "Invalid servo request: %d", value); return; }
        ...
        float adjVal = value * itPolar->second;
        if (adjVal < 0)      servo->setDuty(itMid->second + adjVal * (itMid->second - itMin->second));
        else if (adjVal > 0) servo->setDuty(itMid->second + adjVal * (itMax->second - itMid->second));
        else                 servo->setDuty(itMid->second);
    };
    setPWM(throttle_, servoMsg->throttle, motor);
    setPWM(angle_, servoMsg->angle, servo);
    std::this_thread::sleep_for(std::chrono::nanoseconds(SERVO_PERIOD));   // 20 ms
}
void ServoMgr::rawPWMSubscriber(...) {
    if (servoMsg->throttle >= 0 && servoMsg->throttle <= SERVO_PERIOD) throttle_->setDuty(servoMsg->throttle);
    if (servoMsg->angle    >= 0 && servoMsg->angle    <= SERVO_PERIOD) angle_->setDuty(servoMsg->angle);
    std::this_thread::sleep_for(std::chrono::nanoseconds(SERVO_PERIOD));
}
```
Consequences: linear mapping each side of mid; polarity flips sign (motor default −1, so positive throttle → duty below mid); out-of-range values are **dropped, not clamped**; the subscriber sleeps 20 ms per message so the effective max command rate is ~50 Hz (subscription depth 1 / MessagePoolMemoryStrategy<…,1> → newer messages overwrite). The servo power GPIO (436) must be enabled (ctrl_node does this on every state change).

### 2.4 webserver_pkg — node `webserver_publisher_node` in ns `/webserver_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg))
Runs Flask on `0.0.0.0:5001` in a daemon thread (`app.run(host="0.0.0.0", port=5001, use_reloader=False, threaded=True)`); nginx terminates TLS on 443 and proxies. Publishes `/webserver_pkg/manual_drive` and `/webserver_pkg/calibration_drive` (ServoCtrlMsg). Subscribes `/deepracer_systems_pkg/software_update_pct` (SoftwareUpdatePctMsg, reliable keep-last 1). Service clients (attribute → service): vehicle_state_cli→`/ctrl_pkg/vehicle_state`, enable_state_cli→`/ctrl_pkg/enable_state`, get_cal_cli→`/ctrl_pkg/get_car_cal`, set_cal_cli→`/ctrl_pkg/set_car_cal`, get_revision_info_cli→`/device_info_pkg/get_device_info`, battery_level_cli→`/i2c_pkg/battery_level`, sensor_status_cli→`/sensor_fusion_pkg/sensor_data_status`, set_led_color_cli→`/ctrl_pkg/set_car_led`, get_led_color_cli→`/ctrl_pkg/get_car_led`, verify_model_ready_cli→`/deepracer_systems_pkg/verify_model_ready`, configure_lidar_cli→`/sensor_fusion_pkg/configure_lidar`, model_state_cli→`/ctrl_pkg/model_state`, is_model_loading_cli→`/ctrl_pkg/is_model_loading`, model_action_cli→`/deepracer_systems_pkg/console_model_action`, sw_update_state_cli→`/deepracer_systems_pkg/software_update_check`, begin_sw_update_cli→`/deepracer_systems_pkg/begin_update`, sw_update_status_cli→`/deepracer_systems_pkg/software_update_state`, set_throttle_cli→`/ctrl_pkg/autonomous_throttle`, get_ctrl_modes_cli→`/ctrl_pkg/get_ctrl_modes`, otg_link_state_cli→`/deepracer_systems_pkg/get_otg_link_state`. `call_service_sync(cli, req, timeout=10, sleep_time=0.01)` polls the future. Full route list in section 3.

### 2.5 camera_pkg — node `camera_node` in ns `/camera_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-camera-pkg), [camera_node.cpp](https://github.com/aws-deepracer/aws-deepracer-camera-pkg/blob/main/camera_pkg/src/camera_node.cpp))
Published: `/camera_pkg/video_mjpeg` CameraMsg (depth 1; 1 or 2 images, resized to **160x120** when `resize_images` is true — launcher sets True), `/camera_pkg/display_mjpeg` sensor_msgs/Image (depth 10; one camera, un-resized). Service: `/camera_pkg/media_state` VideoStateSrv (`activate_video: 1` starts publishing; ctrl_node calls it at boot). Parameter: `resize_images` (bool). Opens `/dev/video*` with OpenCV and requires FOURCC MJPG. No explicit fps/resolution setting in stock code (camera's default 640x480 MJPG; community doc confirms). Community stack: `camera_fps` default 30, `camera_resize` True, `camera_mode legacy|modern`, compressed image transport (`/camera_pkg/display_mjpeg/compressed`). [custom-car README](https://github.com/aws-deepracer-community/deepracer-custom-car#usage)

### 2.6 sensor_fusion_pkg — node `sensor_fusion_node` in ns `/sensor_fusion_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-sensor-fusion-pkg))
Subscribed: `/rplidar_ros/scan` sensor_msgs/LaserScan (best-effort keep-last 1), `/camera_pkg/video_mjpeg` CameraMsg, `/camera_pkg/display_mjpeg` Image. Published: `/sensor_fusion_pkg/sensor_msg` EvoSensorMsg (depth 1), `/sensor_fusion_pkg/overlay_msg` Image (LiDAR sector overlay). Services: `/sensor_fusion_pkg/sensor_data_status` SensorStatusCheckSrv, `/sensor_fusion_pkg/configure_lidar` LidarConfigSrv. Default LiDAR config (webserver constants): angles −150..150°, min_dist 0.15, max_dist 0.5, clipping 1.0, 64 values, 64 sectors (SECTOR variant: 8 sectors, clipping 0.5).

### 2.7 inference_pkg — node `inference_node` in ns `/inference_pkg` ([repo](https://github.com/aws-deepracer/aws-deepracer-inference-pkg))
Subscribes `/sensor_fusion_pkg/sensor_msg`; publishes `/inference_pkg/rl_results` InferResultsArray. Services `/inference_pkg/load_model` LoadModelSrv, `/inference_pkg/inference_state` InferenceStateSrv. OpenVINO engine; preprocess types grey/greyMask/greyThreshold/greyThresholdMask/greyDiff; model input 160x120x1 (webserver `MODEL_WIDTH=160, MODEL_HEIGHT=120, MODEL_CHANNELS=1, MODEL_PRE_PROCESS=1 (greyscale)`, `MODEL_PLATFORM=1` TF).

### 2.8 model_optimizer_pkg — node `model_optimizer_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-model-optimizer-pkg)): service `/model_optimizer_pkg/model_optimizer_server` ModelOptimizeSrv → OpenVINO IR xml under `/opt/aws/deepracer/artifacts/<model>/`.

### 2.9 deepracer_navigation_pkg — node `deepracer_navigation_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-navigation-pkg), [node](https://github.com/aws-deepracer/aws-deepracer-navigation-pkg/blob/main/deepracer_navigation_pkg/deepracer_navigation_pkg/deepracer_navigation_node.py))
Subscribes `/inference_pkg/rl_results`; publishes `/deepracer_navigation_pkg/auto_drive` ServoCtrlMsg; services `/deepracer_navigation_pkg/navigation_throttle` NavThrottleSrv (0..1 scale), `/deepracer_navigation_pkg/load_action_space` LoadModelSrv. Default action space (constants.py, verbatim): `[{speed:0.8, steering_angle:30.0}, {0.8,-30.0}, {0.8,0.0}, {0.8,15.0}, {0.8,-15.0}, {0.4,0.0}]`; `DEFAULT_SPEED_SCALES = [1.0, 0.8]`. Autonomous throttle = `throttle_scale * nonlinear(speed/max_speed)`; angle = steering/max_steering (so ±30° → ±1.0).

### 2.10 deepracer_systems_pkg ([repo](https://github.com/aws-deepracer/aws-deepracer-systems-pkg)) — nodes `software_update_node`, `model_loader_node`, `otg_control_node`, `network_monitor_node`, `deepracer_systems_scripts_node` (ns `/deepracer_systems_pkg`). Topics: pub `/deepracer_systems_pkg/software_update_pct` SoftwareUpdatePctMsg, `/deepracer_systems_pkg/network_connection_status` NetworkConnectionStatus; sub `/usb_monitor_pkg/usb_file_system_notification`. Services: `software_update_check` SoftwareUpdateCheckSrv, `begin_update` BeginSoftwareUpdateSrv, `software_update_state` SoftwareUpdateStateSrv ([UPDATE_UNKNOWN, UP_TO_DATE, UPDATE_AVAILABLE, UPDATE_PENDING, UPDATE_IN_PROGRESS]), `verify_model_ready` VerifyModelReadySrv, `console_model_action` ConsoleModelActionSrv, `get_otg_link_state` OTGLinkStateSrv. Clients to status_led and usb_monitor. Models live in `/opt/aws/deepracer/artifacts`.

### 2.11 device_info_pkg — `device_info_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-device-info-pkg)): service `/device_info_pkg/get_device_info` GetDeviceInfoSrv (hardware R1.0/R1.1/R2.0/R2.1 from GPIO 383/387; software version from apt cache of `aws-deepracer-core`).

### 2.12 status_led_pkg — `status_led_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-status-led-pkg)): services `/status_led_pkg/led_solid` SetStatusLedSolidSrv, `/status_led_pkg/led_blink` SetStatusLedBlinkSrv (side Wi-Fi/power LEDs; tail LEDs are servo_pkg PWM).

### 2.13 usb_monitor_pkg — `usb_monitor_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-usb-monitor-pkg)): pub `/usb_monitor_pkg/usb_file_system_notification` USBFileSystemNotificationMsg; services `usb_file_system_subscribe` USBFileSystemSubscribeSrv, `usb_mount_point_manager` USBMountPointManagerSrv.

### 2.14 i2c_pkg — `battery_node` ([repo](https://github.com/aws-deepracer/aws-deepracer-i2c-pkg)): service `/i2c_pkg/battery_level` BatteryLevelSrv → `level` 0..11 (−1 = not connected / read error; webserver maps 10 → "Full charge").

### 2.15 rplidar_ros (Slamtec fork, ros2 branch) — launched as package `rplidar_ros2`, executable `rplidar_scan_publisher`, ns `rplidar_ros` → topic **`/rplidar_ros/scan`** sensor_msgs/LaserScan, frame `laser`. The community Jazzy stack uses package `rplidar_ros`, executable `rplidar_composition` (Foxy: `rplidar_node`), same namespace. [launcher](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/deepracer_launcher/launch/deepracer_launcher.py), [Slamtec rplidar_ros](https://github.com/Slamtec/rplidar_ros/tree/ros2), [custom-car commit 2026-08-11 "Fix RPLIDAR launch failure on Jazzy (rplidar_composition)"](https://github.com/aws-deepracer-community/deepracer-custom-car/commits/main)

### 2.16 deepracer_interfaces_pkg — ALL definitions, verbatim ([repo](https://github.com/aws-deepracer/aws-deepracer-interfaces-pkg), files under `deepracer_interfaces_pkg/msg|srv/`)

Messages:
```
# CameraMsg.msg
sensor_msgs/Image[] images  # Image data read from cameras.

# EvoSensorMsg.msg
sensor_msgs/Image[] images    # Image data read from cameras.
float32[] lidar_data          # LiDAR distance data read from LiDAR sensor.

# InferResults.msg
int32 class_label   # Identifier for a particular class.
float32 class_prob  # Predicted probability value for the class.
float32 x_min
float32 y_min
float32 x_max
float32 y_max

# InferResultsArray.msg
InferResults[] results      # Array of inference results.
sensor_msgs/Image[] images  # Array of input images on which the inference was run.

# NetworkConnectionStatus.msg
bool network_connected  # True if connected to the network else False.

# ServoCtrlMsg.msg
float32 angle       # Angle ratio w.r.t steering_max/steering_min
                    # in calibration file or raw PWM value to be sent
                    # to the servo.
float32 throttle    # Throttle ratio w.r.t speed_max/speed_min
                    # in calibration file or raw PWM value to be sent
                    # to the motor.

# SoftwareUpdatePctMsg.msg
float32 update_pct  # [0-100] value to indicate the software update progress percentage
string status       # Value indicating the stage of the update process. Ex: checking, downloading, installing, etc,.

# USBFileSystemNotificationMsg.msg
string path             # Path of the file in the temp mount system.
string file_name        # File/folder name found.
string callback_name    # Callback name that was sent while subscribing to be notified.
string node_name        # Node name to manage dereferencing the mount point ...
```
Services (request `---` response):
```
# ActiveStateSrv.srv
int8 state            # Vehicle mode (manual, automatic, calibration) to activate after deactivating/resetting current
---
int32 error

# EnableStateSrv.srv
bool is_active        # Activate/Deactivate the current mode(manual, automatic, calibration).
---
int32 error

# NavThrottleSrv.srv
float32 throttle      # Throttle percentage scale value.
---
int32 error

# GetCtrlModesSrv.srv
---
int32[] modes
int32 error

# SetCalibrationSrv.srv
int32 cal_type        # Calibration type (steering/speed)
int32 max             # Maximum PWM value to be set as caibration.
int32 mid
int32 min
int32 polarity
---
int32 error

# GetCalibrationSrv.srv
int32 cal_type
---
int32 max
int32 mid
int32 min
int32 polarity
int32 error

# ServoGPIOSrv.srv
int32 enable          # Flag to enable/disable the GPIO port for servo/motor.   (0 = enable, 1 = disable per ctrl_state.cpp)
---
int32 error

# SetLedCtrlSrv.srv            # GetLedCtrlSrv.srv has the same three int32 fields as response only
int32 red             # Tail LED PWM value for RED channel.
int32 green           # (comment in source says BLUE; field order is red, green, blue)
int32 blue
---
int32 error

# BatteryLevelSrv.srv
---
int32 level

# SensorStatusCheckSrv.srv
---
int8 lidar_status
int8 single_camera_status
int8 stereo_camera_status
int32 error

# VideoStateSrv.srv
int8 activate_video   # Flag to activate camera node and start publishing images.
---
int32 error

# GetDeviceInfoSrv.srv
---
string hardware_version
string software_version
int32 error

# GetModelLoadingStatusSrv.srv
---
string model_loading_status
int32 error

# InferenceStateSrv.srv
int8 start            # Flag to start/stop inference.
int8 task_type        # Identifier of a particular type of inference (Ex: reinforcement learning).
---
int32 error

# LoadModelSrv.srv
string artifact_path
int8 task_type
int8 pre_process_type
int8 action_space_type
---
int32 error

# ModelOptimizeSrv.srv
string model_name
int32[] model_metadata_sensors
int32 training_algorithm
string img_format
int32 width
int32 height
int32 num_channels
int32 lidar_channels
int32 platform
---
string artifact_path
int32 error

# ModelStateSrv.srv
string model_name
int32[] model_metadata_sensors
int8 training_algorithm
int8 action_space_type
string img_format
int32 width
int32 height
int32 num_channels
int32 lidar_channels
int32 platform
int8 task_type
int8 pre_process_type
---
int32 error

# LidarConfigSrv.srv
bool use_lidar
float32 min_angle
float32 max_angle
int32 num_values
float32 min_distance
float32 max_distance
float32 clipping_distance
int32 num_sectors
int8 preprocess_type
---
int32 error

# ConsoleModelActionSrv.srv
string model_path
int32  action         # action=1 upload, action=0 delete
---
string status

# VerifyModelReadySrv.srv
string model_name
---
bool response_status

# BeginSoftwareUpdateSrv.srv
int32 sleep_time_before_reboot
---
bool response_status

# SoftwareUpdateCheckSrv.srv
int32 force_update_check
---
int32 software_update_state

# SoftwareUpdateStateSrv.srv
bool request
---
int32 update_state

# OTGLinkStateSrv.srv
---
bool link_state

# SetStatusLedSolidSrv.srv
int32 led_index
string color
float32 hold
---
int32 error

# SetStatusLedBlinkSrv.srv
int32 led_index
string color1
string color2
float32 delay
---
int32 error

# USBFileSystemSubscribeSrv.srv
string file_name
string callback_name
bool verify_name_exists
---
int32 error

# USBMountPointManagerSrv.srv
string node_name
int32 action
---
int32 error
```
Not in the stock package but used by samples: `SetMaxSpeedSrv {float32 max_speed_pct --- int32 error}` (aws-deepracer Nav2 repo's own copy of `deepracer_interfaces_pkg` and FTL). Community additions (deepracer-custom-car): `DeviceStatusMsg {cpu_percent, cpu_temp, cpu_freq, cpu_freq_max, memory_usage, free_disk, latency_mean, latency_p95, fps_mean}`, `LatencyMeasureMsg {float32 latency_ms}`, `GetDeviceStatusSrv`, and "Updated ServoCtrlMsg so latency measurements can travel through the control path" — **the community ServoCtrlMsg may therefore differ in type hash from stock**; always build the interfaces from the same tree as the car ([CHANGES.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/CHANGES.md)).

---

## 3. Webserver HTTPS API (Flask behind nginx)

### 3.1 Topology and auth (verified from source)

nginx (`/etc/nginx/sites-enabled/default`, community copy identical in spirit to stock, verbatim excerpt):
```nginx
server { listen 80 default_server; ... return 302 https://$http_host; }
server {
    listen 443 ssl http2 default_server;
    include snippets/self-signed.conf;
    root /opt/aws/deepracer/lib/device_console/;
    location /static/ { expires 1d; allow all; }
    location /login { ... proxy_pass http://0.0.0.0:5001/login; }
    location =/     { ... proxy_pass http://0.0.0.0:5001/; }
    location =/home { ... proxy_pass http://0.0.0.0:5001/home; }
    location /route { auth_request /auth; proxy_pass http://127.0.0.1:8080/stream; }
    location /      { auth_request /auth; ... proxy_pass http://0.0.0.0:5001/; proxy_buffering off; ... }
    location /auth  { internal; proxy_pass_request_body off; proxy_pass http://0.0.0.0:5001/auth; }
}
```
[nginx.default](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/build_scripts/files/common/nginx.default). The dev.to post confirms the stock file has the same `auth_request /auth;` line (it tells you to comment it out). [dev.to](https://dev.to/mkreder/how-to-stream-video-from-the-deepracer-camera-mci)

Flask app ([webserver.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/webserver.py), verbatim core):
```python
app = Flask(__name__, template_folder='/opt/aws/deepracer/lib/device_console/templates')
CORS(app)
csrf = CSRFProtect(); csrf.init_app(app)
app.register_blueprint(VEHICLE_LOGS_BLUEPRINT) ... MODELS_BLUEPRINT
app.config.update(DEBUG=True, SECRET_KEY='secret_', SESSION_COOKIE_SECURE=True, REMEMBER_COOKIE_SECURE=True)
```
Implications: (1) Flask-WTF `CSRFProtect` is global → every POST/PUT needs a CSRF token (header `X-CSRFToken`, or form field `csrf_token`); the token is rendered in the login page as `<meta name="csrf-token" content="...">` (all three community clients scrape it). (2) `SECRET_KEY` is the hard-coded string `'secret_'` — the CSRF token is therefore forgeable, but you still need the `deepracer_token` cookie. (3) The Flask port 5001 is bound on 0.0.0.0 with **no auth of its own** (auth is only nginx's `auth_request`); the stock ufw rule set allows "Nginx Full" and (after enable) ssh, so 5001 is normally blocked from the LAN — verify with `sudo ufw status` before relying on it.

Login ([login.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/login.py), verbatim excerpts):
```python
@LOGIN_BLUEPRINT.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        response = make_response(jsonify({"redirect": "/home"}), 200)
        with open(PASSWORD_PATH, "r") as file_ptr: pwd = file_ptr.readline()
        user_provided_pwd_hash = str(compute_password_digest(request.form["password"].encode("utf-8")))
        if hmac.compare_digest(user_provided_pwd_hash, str(pwd)):
            token = str(uuid.uuid4())
            with open(TOKEN_PATH, "w") as token_file: token_file.write(token)
            response.set_cookie("deepracer_token", token, max_age=datetime.timedelta(hours=1), secure=True)
            return response
        ...
        return "failure"          # HTTP 200 with body "failure" on bad password!

@LOGIN_BLUEPRINT.route("/auth", methods=["POST", "GET"])
def auth():   # "always called from nginx to check the authentication for all requests"
    status, cookie_val = check_authentication()
    if not status: return resp, 401
    resp.set_cookie("deepracer_token", cookie_val, max_age=datetime.timedelta(hours=1), secure=True)
    return resp, 200

def check_authentication():
    token = open(TOKEN_PATH).readline()          # /opt/aws/deepracer/token.txt
    cookie_val = str(request.cookies.get("deepracer_token"))
    return hmac.compare_digest(cookie_val, token), cookie_val

def compute_password_digest(message): return hashlib.sha224(message).hexdigest()

def reset_default():   # default password = /sys/class/dmi/id/chassis_asset_tag, else "deepracer"
```
Key gotchas: password is sent as **form-urlencoded** (`request.form["password"]`), not JSON; a wrong password still returns HTTP 200 (`"failure"` body) — check for the `deepracer_token` cookie; a single token file means **logging in from a second client invalidates the first** (one session at a time); the cookie is `secure=True` so use https; cookie lifetime 1 h, refreshed by every authenticated request (`/auth` re-sets it). The community console extends `COOKIE_DURATION`.

Other login routes: `GET /` and `GET /home` (render index or login page), `GET /logout` and `GET|POST /redirect_login` (clear cookie), `GET|POST /api/password` JSON `{"old_password","new_password"}` → `{"success":true}`.

### 3.2 Route catalogue (stock; methods and payloads from source)

Vehicle control ([vehicle_control.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/vehicle_control.py)):

| Route | Method | Request JSON | Response | ROS effect |
|---|---|---|---|---|
| `/api/manual_drive` | PUT/POST | `{"angle": -1..1, "throttle": -1..1, "max_speed": 0..1}` (all required; out-of-range → `{"success":false,"reason":"angle out of range"}`) | `{"success": true}` | publishes ServoCtrlMsg on `/webserver_pkg/manual_drive` with `angle = -categorize(angle)`, `throttle = -rescale(categorize(throttle), max_speed)` |
| `/api/drive_mode` | PUT/POST | `{"drive_mode": "manual" \| "auto"}` (anything not "manual" → 1) | `{"success": true}` / `{"success": false, "reason": "Error"}` | `/ctrl_pkg/vehicle_state {state: 0|1}` |
| `/api/start_stop` | PUT/POST | `{"start_stop": "start" \| "stop"}` (anything not "stop" → true) | `{"success": true}` | `/ctrl_pkg/enable_state {is_active}` |
| `/api/max_nav_throttle` | PUT/POST | `{"throttle": 0..100}` | `{"success": true}` | `/ctrl_pkg/autonomous_throttle {throttle: value/100}` |
| `/api/control_modes_available` | GET | – | `{"control_modes_available": ["manual","autonomous","calibration"], "success": true}` | `/ctrl_pkg/get_ctrl_modes` |

Manual-drive quantisation (verbatim):
```python
def get_categorized_manual_throttle(throttle):
    if abs(throttle) >= 0.8:   throttle = math.copysign(0.8, throttle)
    elif abs(throttle) >= 0.5: throttle = math.copysign(0.5, throttle)
    elif abs(throttle) > 0.0:  throttle = math.copysign(0.3, throttle)
    return throttle
# get_categorized_manual_angle is identical
def get_rescaled_manual_speed(categorized_throttle, max_speed_pct):
    if categorized_throttle == 0.0 or max_speed_pct == 0.0: return 0.0
    inverse_max_speed_pct = (1 - max_speed_pct)
    update_speed_scale_value = MANUAL_SPEED_SCALE_BOUNDS[0] + inverse_max_speed_pct * (MANUAL_SPEED_SCALE_BOUNDS[1] - MANUAL_SPEED_SCALE_BOUNDS[0])   # [1.0, 5.0]
    a = (1.0 / update_speed_scale_value**2) * (2.0 * DEFAULT_SPEED_SCALES[0] - 4.0 * DEFAULT_SPEED_SCALES[1])   # DEFAULT_SPEED_SCALES = [1.0, 0.8]
    b = (1.0 / update_speed_scale_value) * (4.0 * DEFAULT_SPEED_SCALES[1] - DEFAULT_SPEED_SCALES[0])
    return math.copysign(1.0, categorized_throttle) * (a * abs(categorized_throttle)**2 + b * abs(categorized_throttle))
```
Worked values from the source docstring: `max_speed 1.0`: 0.3→0.552, 0.5→0.8, 0.8→0.992; `max_speed 0.5`: 0.3→0.208, 0.5→0.333, 0.8→0.501; `max_speed 0.1`: 0.3→0.138, 0.5→0.225, 0.8→0.346. Both angle and throttle are **negated** before publishing (`msg.angle = -1.0 * ...`, `msg.throttle = -1.0 * ...`) — the console's joystick convention is inverted relative to ServoCtrlMsg, so via HTTP `throttle: +0.8` with motor polarity −1 drives *forward* on a stock-calibrated car; via ROS you publish the opposite sign for the same motion. Expect only 3 speed steps + 3 steering steps via HTTP.

Calibration ([calibration.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/calibration.py)): `PWM_ANGLE_CONVERSION = 10000`, `PWM_THROTTLE_CONVERSION = 4500`, `PWM_OFFSET = 1500000` (ns).

| Route | Method | Request | Response / effect |
|---|---|---|---|
| `/api/set_calibration_mode` | GET | – | `vehicle_state {state: 2}` then `enable_state {is_active: true}` → `{"success": true}` |
| `/api/get_calibration/<angle\|throttle>` | GET | – | `{"mid","min","max","polarity","success"}` in UI units: `(pwm - 1500000)/conversion`; min/max swapped when polarity is 0/false |
| `/api/set_calibration/<angle\|throttle>` | PUT/POST | `{"mid": int, "min": int, "max": int, "polarity": int}` (UI units) | `/ctrl_pkg/set_car_cal {cal_type: 0|1, min/mid/max: v*conversion+1500000, polarity}` |
| `/api/adjust_calibrating_wheels/<angle\|throttle>` | PUT/POST | `{"pwm": int}` (UI units) | publishes raw PWM on `/webserver_pkg/calibration_drive` (`angle = pwm*10000+1500000, throttle = -1` or vice-versa) |
| `/api/get_calibration_mode` | – | **does not exist** in source (task list item) | – |

Models ([models.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/models.py)): `GET /api/models` (list with sensor/algorithm/action-space metadata, `"is_select_disabled"` when required sensors missing), `PUT|POST /api/models/<model_folder_name>/<model_name>` (verify → optimize → configure LiDAR → `model_state` load; community client calls `api/models/<name>/model`), `GET /api/uploaded_model_list`, `PUT|POST /api/uploadModels` (multipart field `file`, `.tar.gz`), `PUT|POST /api/deleteModels` `{"filenames": [...]}`, `GET /api/is_model_installed`, `GET /api/isModelLoading` → `{"success": true, "isModelLoading": "<status>"}`.

Device info ([device_info_api.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/device_info_api.py)): `GET /api/get_device_info` → `{"hardware_version","software_version","success"}`; `GET /api/get_battery_level` → `{"battery_level": int, "success": true}` (10 = full, −1 = not connected per client mapping); `GET /api/get_sensor_status` → `{"camera_status","stereo_status","lidar_status"}` each `"connected"|"not_connected"|"error"`.

LED ([led_api.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/led_api.py)): `POST /api/set_led_color` `{"red","green","blue"}` 0..255 → PWM via `LED_SCALING_FACTOR = 39215`; `GET /api/get_led_color`.

Wi-Fi/USB ([wifi_settings.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/wifi_settings.py)): `GET /api/is_usb_connected` (true only if `Referer` contains `deepracer.aws` and OTG link up), `GET /api/get_network_details` → `{is_usb_connected, SSID, ip_address}`, `GET /api/available_wifi_info` (nmcli scan: ssid, signal, security), `POST /api/wifi_reset` `{"wifi_name","wifi_password"}` → `{"success", "ip_address"}`.

SSH ([ssh_api.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/ssh_api.py)): `GET /api/isSshEnabled` → `{"success","isSshEnabled","reason"}`, `GET /api/enableSsh`, `GET /api/disableSsh`, `GET /api/isSshDefaultPasswordChanged`, `POST|PUT /api/resetSshPassword` `{"oldPassword","newPassword"}`. (Task list's `/api/ssh_status` and `/api/enable_ssh` are not the real names.)

Software update ([software_update.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/software_update.py)): `GET /api/get_mandatory_update_status` → `{"success","status": bool}` (file `/opt/aws/deepracer/software_update_status.json`), `PUT|POST /api/set_mandatory_update_status` `{"update_completed": bool}`, `GET /api/is_software_update_available` → `{"success","status": bool}` (service timeout 180 s), `GET|POST /api/begin_software_update`, `GET /api/update_status` (Server-Sent Events `data: status:<s>|update_pct:<p> <i>`), `GET /api/server_ready`. (Task list's `/api/update_software`, `/api/is_update_available` are not the real names.)

Logs ([vehicle_logs.py](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg/blob/main/webserver_pkg/webserver_pkg/vehicle_logs.py)): `GET /api/logs/<log_type>/<int:num_lines>` where `log_type` is a constants attribute (`SYS` = `/var/log/syslog`), capped at 1000 lines → `{"success": true, "data": "<text>"}`. (No `/api/upload_log`.)

Video: `GET /route?topic=/camera_pkg/display_mjpeg&width=480&height=360` (plus any `web_video_server` query args such as `quality=`, `type=mjpeg`) → nginx auth → `web_video_server` `/stream`. Older 1.0.x consoles used `topic=/video_mjpeg` (thu2004 client), 2.0.x uses `/camera_pkg/display_mjpeg` (lshw54 client). The community stack sets `web_video_server default_transport: compressed`. `/api/supported_modes` does not exist; the real one is `/api/control_modes_available`.

Community-stack additions (deepracer-custom-car `webserver_pkg`, [CHANGES.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/CHANGES.md)): `GET /api/supported_apis` → `{"success", "apis_supported": [...]}` (lists registered `/api/*` rules — call this first to detect stock vs community), `GET /api/get_device_status` (cpu/temp/mem/disk/latency/fps from `DeviceStatusMsg`), `POST /api/emergency_stop` `{"usb_reset": bool}` (runs `systemctl restart deepracer-core`, optional `usbreset`), `GET /api/get_time`, `POST /api/set_timezone`.

### 3.3 Minimal verified Python client (derived from lshw54, matches webserver source)
```python
import requests, urllib3, re
urllib3.disable_warnings()
class DeepRacerHttp:
    def __init__(self, ip, password):
        self.url = f"https://{ip}/"; self.s = requests.Session(); self.s.verify = False
        html = self.s.get(self.url, timeout=10).text
        self.csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', html).group(1)
        r = self.s.post(self.url + "login", data={"password": password}, headers={"X-CSRFToken": self.csrf})
        assert r.status_code == 200 and "deepracer_token" in self.s.cookies, r.text   # body 'failure' on bad pw
        self.h = {"X-CSRFToken": self.csrf, "referer": self.url + "home", "origin": self.url,
                  "content-type": "application/json;charset=UTF-8", "x-requested-with": "XMLHttpRequest"}
    def put(self, path, body): 
        r = self.s.put(self.url + path, json=body, headers=self.h); j = r.json(); assert j.get("success"), j; return j
    def manual(self):  self.put("api/start_stop", {"start_stop": "stop"}); self.put("api/drive_mode", {"drive_mode": "manual"}); self.put("api/start_stop", {"start_stop": "start"})
    def move(self, angle, throttle, max_speed=0.5): return self.put("api/manual_drive", {"angle": angle, "throttle": throttle, "max_speed": max_speed})
    def stop(self): self.move(0, 0, 0); self.put("api/start_stop", {"start_stop": "stop"})
    def mjpeg(self, w=480, h=360): return self.s.get(self.url + f"route?topic=/camera_pkg/display_mjpeg&width={w}&height={h}", headers=self.h, stream=True)
```

---

## 4. Community / open-source control clients

| Project | URL | Lang | Transport & auth | API surface | Status |
|---|---|---|---|---|---|
| **lshw54/awsdeepracer_control** (PyPI `awsdeepracer-control` 0.2.0) | https://github.com/lshw54/awsdeepracer_control , https://pypi.org/project/awsdeepracer-control/ | Python (requests, bs4/lxml, requests-toolbelt) | HTTPS; GET `/` → `<meta name="csrf-token">`; POST `/login` form `password`, header `X-CSRFToken`; session cookie; `verify=False` | `set_manual_mode/set_autonomous_mode` (stop → `api/drive_mode`), `start_car/stop_car` (`api/start_stop`), `move(angle, throttle, max_speed)` (`api/manual_drive`), `set_throttle_percent` (`api/max_nav_throttle`), `get_models/get_uploaded_models/load_model/upload_model`, `get_calibration_angle/throttle`, `set_calibration_*`, `set_calibration_mode`, `get_battery_status`, `get_is_usb_connected`, `get_network_details`, `get_raw_video_stream` (`/route?topic=/camera_pkg/display_mjpeg&width=1920&height=1080`) | Targets console 2.0.383.0; last push 2023-09-25; 2 stars; MIT. **Best fit for stock 2.x.** |
| jacobcantwell/aws_deepracer_control_v2 (PyPI `aws-deepracer-control-v2` 0.1.5) | https://pypi.org/project/aws-deepracer-control-v2/ , https://github.com/jacobcantwell/aws_deepracer_control_v2 | Python | same flow | fork of thu2004 with "small fixes for API changes"; targets console 1.0.606.0 | last upload 2021-11-01 |
| thu2004/deepracer-vehicle-api (PyPI `deepracer-vehicle-api` 0.0.10) | https://github.com/thu2004/deepracer-vehicle-api | Python | same flow ("reverse engineered by capturing network traffic"); stream `/route?topic=/video_mjpeg&width=480&height=360` | adds `move_forward/backward/turn_left/right` helpers with `speed=-0.7` defaults (shows the inverted sign) | 2020-01-31; credits ARCC-RACE/deepracer-rc and gidutz/DeepBullFighting |
| strands-robots (local) `strands_robots/runtime/deepracer_v2/client.py` | `~/strands-robots/strands_robots/runtime/deepracer_v2/client.py` | Python stdlib HTMLParser + requests | same flow, also sends `csrf_token` form field, asserts `deepracer_token` cookie | manual/auto, start/stop, `move(angle, throttle, max_speed)`, battery, usb, `get_raw_video_stream` → **uses `topic=/display_mjpeg` (1.x name; should be `/camera_pkg/display_mjpeg` on 2.x)** | in-repo, feat branch |
| athackst/deepracer_joy | https://github.com/athackst/deepracer_joy , https://www.allisonthackston.com/articles/aws-deepracer-3-joy.html | ROS 1 (joy + joy_teleop YAML) | ROS 1 Kinetic-era stock stack: topic `/manual_drive` `ctrl_pkg/ServoCtrlMsg`, deadman service `/enable_state {isActive: true}`; axis 1 → throttle, axis 2 → angle, scale 1.0 | gamepad teleop | archived 2022-09-03; pre-ROS 2 topic names |
| Allison Thackston ros1_bridge write-up | https://www.allisonthackston.com/articles/aws-deepracer-5-ros1-bridge.html | ROS1↔ROS2 | bridges 2020 Kinetic stack to ROS 2 Eloquent; publishes `/auto_drive` after `/enable_state` | historical (2020-03-14) |
| AWS `cmdvel_to_servo_pkg` (aws-deepracer Nav2 repo) | https://github.com/aws-deepracer/aws-deepracer/tree/main/deepracer_nodes/cmdvel_to_servo_pkg | ROS 2 Python | subscribes `/cmd_vel` geometry_msgs/Twist (best-effort depth 1); publishes `servo_msg` in its own namespace (`/cmdvel_to_servo_pkg/servo_msg`); service `set_max_speed` SetMaxSpeedSrv | Twist → ServoCtrlMsg with `MAX_SPEED 4.0 m/s`, `MAX_STEER 0.523599 rad`, quantised to {0.5,0.8,1.0} throttle / {0.2,0.5,1.0} steering, `MAX_SPEED_PCT 0.68` | last push 2023-07-27; not installed on cars; its topic is **not** `/ctrl_pkg/servo_msg` — remap when launching |
| AWS `enable_deepracer_nav_pkg` | same repo | ROS 2 Python | calls `/camera_pkg/media_state {activate_video:1}` and `/servo_pkg/servo_gpio {enable:0}` | bring-up helper for Nav2 |
| Follow-the-Leader sample | https://github.com/aws-deepracer/aws-deepracer-follow-the-leader-sample-project | ROS 2 | adds ctrl state 3: `ros2 service call /ctrl_pkg/vehicle_state ... "{state: 3}"` then `enable_state "{is_active: True}"`; `/ftl_navigation_pkg/set_max_speed SetMaxSpeedSrv` | object-detection follow | 2022-06 |
| aws-deepracer-community/deepracer-custom-console | https://github.com/aws-deepracer-community/deepracer-custom-console | TypeScript (Cloudscape) | same Flask API; dev mode requires `WTF_CSRF_ENABLED=False` in `webserver.py` | replacement UI deb `aws-deepracer-community-device-console_2.2.9.0_all.deb` | 2026-08-04 |
| DeepRacer Event Manager (DREM) | https://github.com/aws-solutions-library-samples/guidance-for-aws-deepracer-event-management/ , https://aws.amazon.com/solutions/guidance/aws-deepracer-event-management/ | CDK/TS/Python | cars enrolled as SSM hybrid managed instances; model push via SSM RunCommand | fleet/model/timer management, not driving | active (Eviden case study 2024) |
| DeepRacer on AWS `car_activation.sh` | https://github.com/aws-solutions/deepracer-on-aws/blob/main/source/apps/website/public/car_activation.sh | bash | installs `amazon-ssm-agent.deb`, `amazon-ssm-agent -register -code -id -region`, tags `CarType`, resets console password, `apt-get install -y "aws-deepracer-*"` | car enrolment for wireless model deploy | v1.3.2 2026-10-07 |
| SSM port-forward to console (classmethod.jp) | https://dev.classmethod.jp/articles/awsdeepracer-vehicle-hybrid-instance/ | – | `AWS-StartPortForwardingSession` 443→localhost | remote console access | 2022-06-13 |
| deepracer-utils | https://github.com/aws-deepracer-community/deepracer-utils (PyPI 1.5.6, 2026-03-22) | Python | – | log/track analysis only, **not** a vehicle client | active |
| deepracer-for-cloud | https://github.com/aws-deepracer-community/deepracer-for-cloud | Shell/Docker | – | RL training env (ROS 2 Jazzy/Gazebo Harmonic simapp) | active (353 stars) |

No published ROS 2 node converting `ackermann_msgs/AckermannDrive(Stamped)` → ServoCtrlMsg was found (searches 2026-10-12); `cmdvel_to_servo_pkg` is the only AWS-provided Twist bridge. deepracer_joy's `logitech_dual_action.yaml` (verbatim) documents the ROS1-era mapping:
```yaml
teleop:
  drive:
    type: topic
    message_type: ctrl_pkg/ServoCtrlMsg
    topic_name: /manual_drive
    deadman_buttons: [4]
    axis_mappings:
      - {axis: 1, target: throttle, scale: 1.0}
      - {axis: 2, target: angle,    scale: 1.0}
  deadman:
    type: service
    service_name: /enable_state
    service_request: {isActive: true}
    buttons: [4]
```

---

## 5. Community custom OS: aws-deepracer-community/deepracer-custom-car

- Repo: https://github.com/aws-deepracer-community/deepracer-custom-car (merge of davidfsmith/deepracer-scripts and larsll/deepracer-pi). README: supports original DeepRacer on Ubuntu 20.04/Foxy (`install_scripts/aws-20.04`) and Ubuntu 24.04/Jazzy (`install_scripts/aws-24.04`, flash via `docs/flash-2404.md`), Raspberry Pi 4 (22.04/Humble, `rpi4-22.04`) and Pi 4/5 (24.04/Jazzy, `rpi-24.04`), WLToys A979 + Pi build. APT repo `https://aws-deepracer-community-sw.s3.eu-west-1.amazonaws.com/deepracer-custom-car`, key `CFB167A8F18DE6A634A6A2E4A63BC335D48DF8C6`, codenames `stable`/`experimental`, components `dr-focal`, `dr-noble`, `rpi4-jammy`, `rpi-noble` ([docs/apt.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/apt.md)). Packages: `aws-deepracer-core`, `aws-deepracer-community-device-console`. Releases: v2.1.9.9 (2026-08-11) … v2.1.8.8 (2025-06-22); an "experimental 2.3.0" line (structured runtime config, differential drive, IMU, camera rotation) is excluded from `main` ([CHANGES.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/CHANGES.md)).
- Flash 24.04 ([docs/flash-2404.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/flash-2404.md)): 32 GB USB built by `utils/usb-build.*` (BOOT 4 GiB / DEEPRACER 1 GiB / FLASH 20 GiB), ESC → BIOS → Boot From File → `BOOTx64.EFI`; 20–30 min; Wi-Fi via USB (`https://deepracer.aws`), `wifi-creds.txt` on FAT32 USB, or `nmcli`. Installs Ubuntu 24.04 + `ros-jazzy-ros-core` + OpenVINO 2024.6 + TensorFlow 2.17, **no X**. Hostname on sticker (e.g. `amss-abcd`); SSH `deepracer`/`deepracer`; console password from sticker; `https://<hostname>` or `deepracer.local`. Uses the AWS developer shim (blinks "DEVELOPER" in Morse ~21 s).
- Upgrade in place on 20.04 ([docs/upgrade-2004.md](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/docs/upgrade-2004.md)): `install-prerequisites.sh` stops deepracer-core, **disables IPv6, suspend and Wi-Fi power-save, enables SSH and opens the firewall**, removes desktop/snap; `install-deepracer.sh` adds the community apt repo and installs the two packages.
- What changes for an external agent: topic names and `ServoCtrlMsg` field names are unchanged (verified against the in-tree `src/aws-deepracer-interfaces-pkg/msg/ServoCtrlMsg.msg` list; CHANGES.md says ServoCtrlMsg was "updated so latency measurements can travel" — rebuild interfaces from the car's tree to be safe). Camera publishes `compressed` transport (`/camera_pkg/display_mjpeg/compressed`), fps param default 30, 640x480 → 160x120 resize at source. New topics `/device_info_pkg/device_status` (DeviceStatusMsg), `/inference_pkg/model_artifact`. Navigation node is C++ (`deepracer_navigation_node_cpp`). `web_video_server` runs with `default_transport: compressed`. HTTP additions: `/api/supported_apis`, `/api/get_device_status`, `/api/emergency_stop`, `/api/get_time`, `/api/set_timezone`; login cookie duration configurable. ([deepracer_launcher.py (community)](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/src/aws-deepracer-launcher/deepracer_launcher/launch/deepracer_launcher.py), [start_ros.sh](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/build_scripts/files/common/start_ros.sh), [deepracer-core.service](https://github.com/aws-deepracer-community/deepracer-custom-car/blob/main/build_scripts/files/common/deepracer-core.service))
- **rosbridge_server is NOT part of either stack** (no mention in launcher, start_ros.sh, install scripts, docs; grep of the repo for `rosbridge` returns nothing). `web_video_server` is included (stock: built from source for Foxy; Jazzy: binary exists in rosdistro).
- **ROS_DOMAIN_ID / RMW**: neither `start_ros.sh` nor `deepracer-core.service` sets `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION` or `ROS_LOCALHOST_ONLY` → defaults: domain **0**, RMW = **rmw_fastrtps_cpp** (ROS 2 default for both Foxy and Jazzy; general ROS knowledge, not DeepRacer-specific). The service runs as **root**; sourcing is `/opt/aws/deepracer/lib/setup.bash` then OpenVINO. To inject DDS settings system-wide, add `Environment=` lines to a systemd drop-in for `deepracer-core.service`.
- Installing rosbridge on the car: `sudo apt install ros-$ROS_DISTRO-rosbridge-suite` (rosdistro lists `rosbridge_suite` with packages `rosbridge_server`, `rosbridge_library`, `rosapi` for foxy [version tag `ros2`], humble [`humble`], jazzy [`jazzy`], kilted [`kilted`]) — but Foxy's apt repo is EOL/frozen (packages still downloadable as of the rosdistro file, availability of the Foxy mirror is not guaranteed). Then `ros2 launch rosbridge_server rosbridge_websocket_launch.xml` (port 9090; add `port:=9090 address:=0.0.0.0` as needed) **in a shell that has sourced `/opt/aws/deepracer/lib/setup.bash`** so `deepracer_interfaces_pkg` types resolve, and open the firewall (`sudo ufw allow 9090/tcp`). Sources: [rosdistro foxy](https://raw.githubusercontent.com/ros/rosdistro/master/foxy/distribution.yaml), [rosdistro jazzy](https://raw.githubusercontent.com/ros/rosdistro/master/jazzy/distribution.yaml), [rosbridge_suite README (ros2 branch)](https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/README.md) ("Humble release is tracked in the humble branch, Jazzy and later in ros2").
- Talking DDS over Wi-Fi from a laptop (general ROS knowledge + community reports): same `ROS_DOMAIN_ID`, same RMW on both ends, `ROS_LOCALHOST_ONLY=0`, multicast must pass the AP (many consumer/enterprise APs drop or rate-limit multicast → discovery fails). Mitigations: (1) Fast DDS discovery server on the car (`fastdds discovery -i 0 -l <car-ip> -p 11811`, laptop `ROS_DISCOVERY_SERVER=<car-ip>:11811`), (2) CycloneDDS with a unicast `<Peers>` list and `AllowMulticast=spdp` or `false`, (3) rosbridge over a single TCP websocket (robust to multicast/Wi-Fi quirks), (4) HTTPS API (no DDS at all). Reports of the pattern: [husarion multi-machine tutorial](https://husarion.com/tutorials/ros2-tutorials/6-robot-network/), [eProsima discovery server example](https://eprosima-dds-router.readthedocs.io/en/v2.0.0/rst/examples/ros_discovery_server_example.html). The local strands-robots note that `/ctrl_pkg/vehicle_state` "sometimes don't respond on the very first call after boot — DDS discovery hasn't fully converged" matches this.

---

## 6. Control semantics (verified)

6.1 **Units**: `ServoCtrlMsg.angle/throttle` ∈ [-1, 1] on `/webserver_pkg/manual_drive`, `/deepracer_navigation_pkg/auto_drive`, `/ctrl_pkg/servo_msg`; raw duty-cycle **nanoseconds** 0..20,000,000 on `/webserver_pkg/calibration_drive` and `/ctrl_pkg/raw_pwm`. Sign: `angle` positive = steering_max side after polarity (servo polarity +1 → duty toward `max`, i.e. 1.70 ms by default); `throttle` positive × motor polarity −1 → duty toward `min` (1.311 ms). Which physical direction that is depends on the ESC/servo wiring and the calibration "Reverse direction" flag — the console UI negates both fields, and the AWS calibration page notes "Vehicles distributed at AWS re:Invent 2018 might have their forward direction set in reverse." Always test at `max_speed ≈ 0.2` with wheels off the ground first. ([calibrate-your-vehicle](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/calibrate-your-vehicle.html))

6.2 **Calibration → PWM**: `duty = mid + v·pol·(max−mid)` for `v·pol>0`, `mid + v·pol·(mid−min)` for `v·pol<0`, `mid` at 0 (servo_mgr.cpp). Stored in `/opt/aws/deepracer/calibration.json`; defaults above. Console UI units: steering −10..10 ↔ `(pwm−1,500,000)/10,000`, throttle ↔ `/4,500`. The AWS calibration page: center steering by aligning one front wheel with its rear wheel ("AWS DeepRacer uses Ackermann front-wheel steering"); throttle: find the two noise onsets around zero and set stopped to their midpoint; "the action space for training doesn't support the maximum speed of more than 2 m/s"; set throttle limit 20–30 % above training max speed; backward speed unused autonomously.

6.3 **max_speed in manual mode**: webserver quantises |throttle| to {0.3, 0.5, 0.8} and maps through `y = a x² + b x` whose curve is set by `max_speed` (see 3.2). Via ROS you bypass this entirely — publish the final ratio. In autonomous mode the equivalent is `/ctrl_pkg/autonomous_throttle {throttle: 0..1}` (console sends `/api/max_nav_throttle {"throttle": 0..100}`), multiplied into the navigation node's non-linear speed mapping ([modes-of-operation.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/modes-of-operation.md): "servo_msg.throttle = maximum_speed_threshold * non_linear_scaled_speed = 0.4 * 0.8 = 0.32").

6.4 **Rates / QoS**: ctrl_node subscriptions and publishers are `KeepLast(1)` reliable; servo_node subscription depth 1 with a 20 ms sleep per message → ≥50 Hz input is pointless; 10–20 Hz is the practical command rate. `cmdvel_to_servo` uses BEST_EFFORT depth 1 on `/cmd_vel` — a reliable publisher will still match a best-effort subscriber, but a best-effort publisher will **not** match ctrl_node's reliable subscriber, so publish `/webserver_pkg/manual_drive` with RELIABLE QoS.

6.5 **Safety behaviour**: no watchdog/timeout anywhere in stock `ctrl_node`, `servo_node` or the webserver (grep of all sources for timer/timeout: the only timer in ctrl_node is a one-shot 1 s init timer; webserver has a 5 s heartbeat log). Consequences: a dropped connection leaves the last throttle applied; the only automatic zeroing is `setStateActive()` on `vehicle_state`/`enable_state` transitions (manual: on both enable and disable; auto: on disable). The community console adds `/api/emergency_stop` which restarts the whole `deepracer-core` service. An external agent **must** publish `{0,0}` (and ideally call `enable_state {is_active:false}`) on exit/cancel/exception. (The local strands-robots `topic-surface.md` claim of a "~400 ms cmd_vel_timeout" is **not supported by the stock source**; treat as unverified.)

6.6 **Direct `/ctrl_pkg/servo_msg` vs `/webserver_pkg/manual_drive`**: publishing straight to `/ctrl_pkg/servo_msg` bypasses the mode gate (works even in autonomous mode and competes with the navigation node — two publishers, depth 1, last-writer-wins), still goes through calibration, and still needs servo GPIO 436 enabled (it is after boot; call `/servo_pkg/servo_gpio {enable: 0}` to be sure). Publishing to `/webserver_pkg/manual_drive` is dropped unless manual mode is active and enabled, and is automatically zeroed on mode changes — the safer choice. `/ctrl_pkg/raw_pwm` takes raw ns and is unbounded except 0..20 ms — never use it for driving.

6.7 **Geometry & limits**: wheelbase 0.164 m, track 0.159–0.162 m (URDF, section 1.3); default action-space steering ±30°, speeds 0.4/0.8 m/s; `cmdvel_to_servo` clamps |ω|≤0.5236 rad and |v|≤4 m/s (nominal physical max, open-loop); AWS calibration doc caps training speed at 2 m/s; a re:Invent 2024 competitor reports "action space limited to about 20 degrees, which roughly matches the real car's steering angle" and 0.8–1.3 m/s to avoid slip ([hku aihub mirror](https://aihub.hkuspace.hku.hk/2025/02/28/aws-deepracer-closing-time-at-aws-reinvent-2024-how-did-that-physical-racing-go/)). The car is open-loop: "The AWS DeepRacer device is an open-loop system and does not have feedback to recognize the speed of the car" ([modes-of-operation.md](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/modes-of-operation.md)). Min turning radius ≈ L/tan(30°) ≈ 0.28 m.

6.8 **Camera**: stock camera_node → `/camera_pkg/video_mjpeg` CameraMsg (1 or 2 frames, 160x120 when `resize_images`), `/camera_pkg/display_mjpeg` Image (one camera, native 640x480 MJPG decoded to BGR); inference uses 160x120 **greyscale** (1 channel); console stream default 480x360 via `/route`. Frame rate = camera rate (community default 30 fps; original sensor can do 120 fps 1080p). LiDAR `/rplidar_ros/scan` (RPLIDAR A1 class, ~5.5–10 Hz typical — rate not in source).

---

## 7. Practical recipes for a strands-robots agent

Common prerequisite: car on Wi-Fi, IP known (`hostname -I` over SSH, or console Settings), console password from the sticker, SSH enabled via Settings → Device SSH (or `GET /api/enableSsh` after login). Check the stack: `GET /api/get_device_info` (software_version 2.x = stock Foxy; community reports extra fields) and `GET /api/supported_apis` (exists only on community stack).

### 7(a) rclpy on the same DDS domain (strands-robots `Ros2Runtime`)
Laptop needs: ROS 2 matching the car (**Foxy** for stock — EOL, hard to install on modern Ubuntu; Docker `ros:foxy` works; **Jazzy** for the community 24.04 image), and a locally built `deepracer_interfaces_pkg`:
```bash
mkdir -p ~/dr_ws/src && cd ~/dr_ws/src
git clone https://github.com/aws-deepracer/aws-deepracer-interfaces-pkg.git            # stock car
# or: git clone https://github.com/aws-deepracer-community/deepracer-custom-car.git and use src/aws-deepracer-interfaces-pkg  (community car)
cd ~/dr_ws && colcon build --packages-select deepracer_interfaces_pkg && source install/setup.bash
export ROS_DOMAIN_ID=0 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp   # match the car (defaults)
ros2 topic list | grep -E "ctrl_pkg|webserver_pkg|camera_pkg"                      # discovery check
```
Drive:
```bash
ros2 service call /ctrl_pkg/vehicle_state deepracer_interfaces_pkg/srv/ActiveStateSrv "{state: 0}"
ros2 service call /ctrl_pkg/enable_state  deepracer_interfaces_pkg/srv/EnableStateSrv  "{is_active: true}"
ros2 topic pub -r 10 /webserver_pkg/manual_drive deepracer_interfaces_pkg/msg/ServoCtrlMsg "{angle: 0.0, throttle: -0.3}"   # sign: see 6.1; start tiny
ros2 topic pub -1    /webserver_pkg/manual_drive deepracer_interfaces_pkg/msg/ServoCtrlMsg "{angle: 0.0, throttle: 0.0}"
ros2 service call /ctrl_pkg/enable_state  deepracer_interfaces_pkg/srv/EnableStateSrv  "{is_active: false}"
```
If discovery over Wi-Fi fails: run a Fast DDS discovery server on the car and set `ROS_DISCOVERY_SERVER=<car-ip>:11811` on both, or switch both to CycloneDDS with unicast peers (section 5). Alternative Twist path: build and run AWS `cmdvel_to_servo_pkg` on the car with a remap `servo_msg:=/ctrl_pkg/servo_msg` (its default publishes to `/cmdvel_to_servo_pkg/servo_msg`, which nothing consumes) and publish `geometry_msgs/Twist` on `/cmd_vel` — output is quantised, so the strands `TwistToServoCtrl` translator publishing `ServoCtrlMsg` directly gives finer control. Camera: subscribe `/camera_pkg/display_mjpeg` (`sensor_msgs/Image`, 640x480 BGR, ~30 Hz, heavy over Wi-Fi) or on the community stack `/camera_pkg/display_mjpeg/compressed` (`sensor_msgs/CompressedImage`).

### 7(b) rosbridge websocket (strands-robots rosbridge transport)
On the car (one-time): `sudo apt install ros-$ROS_DISTRO-rosbridge-suite && sudo ufw allow 9090/tcp`. Run: `source /opt/aws/deepracer/lib/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml` (optionally as a systemd unit `After=deepracer-core.service`). rosbridge needs the DeepRacer message types importable in its Python environment — sourcing the car's own install does that; no laptop-side build needed. Then from the laptop (roslibpy or raw JSON):
```json
{"op":"call_service","service":"/ctrl_pkg/vehicle_state","type":"deepracer_interfaces_pkg/srv/ActiveStateSrv","args":{"state":0},"id":"m"}
{"op":"call_service","service":"/ctrl_pkg/enable_state","type":"deepracer_interfaces_pkg/srv/EnableStateSrv","args":{"is_active":true},"id":"e"}
{"op":"advertise","topic":"/webserver_pkg/manual_drive","type":"deepracer_interfaces_pkg/msg/ServoCtrlMsg"}
{"op":"publish","topic":"/webserver_pkg/manual_drive","msg":{"angle":0.0,"throttle":-0.3}}
{"op":"publish","topic":"/webserver_pkg/manual_drive","msg":{"angle":0.0,"throttle":0.0}}
{"op":"call_service","service":"/ctrl_pkg/enable_state","type":"deepracer_interfaces_pkg/srv/EnableStateSrv","args":{"is_active":false},"id":"d"}
```
(Service response arrives as `{"op":"service_response","values":{"error":0},...}`.) Camera over rosbridge: `{"op":"subscribe","topic":"/camera_pkg/display_mjpeg/compressed","type":"sensor_msgs/msg/CompressedImage","throttle_rate":200}` on the community stack (base64 JPEG in `data`); on stock Foxy only the raw `Image` exists (640x480x3 base64 ≈ 1.2 MB/frame — use `throttle_rate` ≥ 500 ms or prefer the HTTPS MJPEG route). rosbridge JSON cannot carry raw bytes efficiently; see [rosbridge image Q&A](https://answers.ros.org/question/333329/). Humble vs Jazzy branch note: [rosbridge_suite README](https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/README.md).

### 7(c) HTTPS webserver (strands-robots `HttpRuntime`/`deepracer_v2`)
1. `GET https://<ip>/` → scrape `<meta name="csrf-token" content="…">`. 2. `POST https://<ip>/login` form `password=<sticker>` with header `X-CSRFToken` → expect cookie `deepracer_token` (HTTP 200 + body `failure` means wrong password). 3. `PUT /api/start_stop {"start_stop":"stop"}`; `PUT /api/drive_mode {"drive_mode":"manual"}`; `PUT /api/start_stop {"start_stop":"start"}`. 4. Loop at ~10 Hz: `PUT /api/manual_drive {"angle": a, "throttle": t, "max_speed": 0.3}` (remember 3-step quantisation and the server-side negation). 5. Stop: `PUT /api/manual_drive {"angle":0,"throttle":0,"max_speed":0}` then `PUT /api/start_stop {"start_stop":"stop"}`. All JSON calls need headers `X-CSRFToken`, `Content-Type: application/json`, and the session cookie; `verify=False` (self-signed). Frames: `GET /route?topic=/camera_pkg/display_mjpeg&width=480&height=360` (multipart/x-mixed-replace MJPEG; parse `--boundary` parts) with the same cookie. Telemetry: `GET /api/get_battery_level`, `GET /api/get_sensor_status`, `GET /api/get_device_info`. Gotchas: one token file → opening the console UI in a browser logs your agent out; cookie expires after 1 h idle; `/api/manual_drive` returns `{"success": true}` even when the car is not in manual mode (the ctrl_node silently drops the message).

---

## 8. Simulation without hardware

| Option | What it is | Fit for an Ackermann agent | Source |
|---|---|---|---|
| aws-deepracer-community/deepracer-simapp | The DeepRacer RL simapp (Robomaker/SageMaker/RL-Coach roles in one image) now on **ROS 2 Jazzy + Gazebo Harmonic, Ubuntu 24.04, TF 2.20**; Docker Hub `awsdeepracercommunity/deepracer-simapp:<ver>-cpu|gpu`, ECR `public.ecr.aws/deepracer-community/deepracer-on-aws-simapp`; tracks in `tracks.txt` | Built for RL training/eval (reward function), not interactive teleop; no ServoCtrlMsg/ctrl_pkg emulation | https://github.com/aws-deepracer-community/deepracer-simapp |
| deepracer-for-cloud (DRfC) | Scripts to run the simapp locally (Ubuntu 22.04–26.04 + NVIDIA) or on EC2/Azure; CPU-only on arm64/macOS (Colima, experimental) | Same as above | https://github.com/aws-deepracer-community/deepracer-for-cloud |
| aws-deepracer (Nav2 repo) | `deepracer_description` (xacro/URDF with cameras + LiDAR, `deepracer_drive` Gazebo plugin), `deepracer_bringup` launch files (`deepracer_sim.launch.py`, `deepracer_spawn.launch.py`, nav/SLAM demos), `cmdvel_to_servo_pkg`, teleop_twist_keyboard; ros_control joint controllers at 60 Hz | **Closest ROS 2 Gazebo twin** of the real car (same URDF dims); Foxy-era (2021–2023), needs porting to Gazebo Harmonic/Jazzy; sim takes `/cmd_vel`, real car takes ServoCtrlMsg → the same strands translator cannot be used unmodified | https://github.com/aws-deepracer/aws-deepracer , [intro doc](https://github.com/aws-deepracer/aws-deepracer/blob/main/introduction-to-the-ros-navigation-stack-using-aws-deepracer-evo.md) |
| Generic ROS 2 Ackermann Gazebo cars | e.g. COONEO/sim_car (Galactic, `cmd_ackermann`), CihatAltiparmak/car_sim (Foxy), alitekes1/ackermann-vehicle-gzsim-ros2 (Humble/Jazzy + Harmonic + Nav2) | Fine as a behavioural proxy; not DeepRacer-shaped | https://github.com/COONEO/sim_car , https://github.com/CihatAltiparmak/car_sim , https://oosmetrics.com/repo/alitekes1/ackermann-vehicle-gzsim-ros2 |
| Isaac Sim | No DeepRacer asset found (searched 2026-10-12); only a generic "Jetracer Track" environment exists in older Isaac asset lists; a USD would have to be built from the AWS URDF | Possible via URDF importer, nothing ready-made | https://docs.isaacsim.omniverse.nvidia.com/4.2.0/features/environment_setup/assets/index.html |
| MuJoCo | `mujoco_menagerie` has **no wheeled/Ackermann car** (71 models: humanoids, quadrupeds, arms, drones, one omnidirectional soccer base). MuJoCo's own examples include a simple `car.xml` (skid-steer toy, not Ackermann — verify in the mujoco repo `model/` folder) | strands-robots has a MuJoCo backend (`strands_robots/simulation/mujoco/{backend,simulation,mjcf_builder,physics}.py`) but no car MJCF; an Ackermann car would need a custom MJCF: chassis body, two steering hinge joints (±0.52 rad position actuators) + four wheel hinge joints (velocity actuators), wheelbase 0.164, track 0.162, wheel r 0.03 — the AWS URDF can be converted with MuJoCo's URDF loader (steering hinges → `joint type="hinge" axis="0 0 1"`) | https://github.com/google-deepmind/mujoco_menagerie |
| F1TENTH gym / Gym-Khana | 2-D Numba single-track/kinematic/Pacejka models, faster-than-real-time, LiDAR scans; `f1tenth_gym_ros` ROS 2 wrapper | Good lightweight proxy for Ackermann kinematics (1/10 scale, wheelbase 0.33 m — scale params to 0.164) | https://f1tenth-gym.readthedocs.io , https://gym-khana.readthedocs.io , https://github.com/f1tenth/f1tenth_simulator |
| Donkeycar sim | not researched in depth (gym-donkeycar Unity sim) | proxy only | – |

---

## 9. Cross-check against the local strands-robots work (for the caller)

Found in `~/strands-robots` (branch head `c369d07 feat(runtime): HttpRuntime + DeepRacerV2 + RemoteHttpPolicy`): `docs/impl/phase-deepracer-robot/topic-surface.md`, `example/deepracer/README.md`, `strands_robots/runtime/deepracer_v2/client.py`, `strands_robots/runtime/http/translators/twist_to_servo.py`, registry entry `aws_deepracer` (robots.json ~L967). Items this research contradicts or refines:

1. `topic-surface.md` says "Switch to manual mode (`state=1`)". **Stock source: manual = 0, autonomous = 1, calibration = 2.** `state=1` would put the car in autonomous mode (inference starts, manual_drive ignored).
2. `topic-surface.md` says `/camera_pkg/display_mjpeg` is "Stereo MJPEG … single image stream encoding both views". Stock `camera_node` publishes **one camera** on `display_mjpeg`; both cameras are in `/camera_pkg/video_mjpeg` (CameraMsg `images[]`).
3. `topic-surface.md` "cmd_vel_timeout is ~400 ms … controller stops the wheels if no message within ~400 ms" — **no such watchdog exists in stock ctrl_node/servo_node**; the trailing zero publish is essential, not a nicety.
4. `topic-surface.md` "stock Humble image" — there is no AWS Humble image; stock = Foxy (20.04), community = Jazzy (24.04) [Humble only on Pi4/22.04]. "Older Foxy images expose `/cmd` instead of `/webserver_pkg/manual_drive`" is unsupported; the ROS 1 Kinetic stack used `/manual_drive` and `/enable_state` (deepracer_joy).
5. `example/deepracer/README.md` says `cmdvel_to_servo_pkg` publishes to `/ctrl_pkg/servo_msg`; its constants publish `servo_msg` **relative**, i.e. `/cmdvel_to_servo_pkg/servo_msg` under the launch namespace — remap required.
6. `deepracer_v2/client.py` streams `route?topic=/display_mjpeg`; the 2.x console topic is `/camera_pkg/display_mjpeg`.
7. `twist_to_servo.py` default `wheelbase_m=0.164`, `max_steering_rad=0.5236` match the URDF and `cmdvel_to_servo` constants — good. Note the HTTP path quantises angle/throttle to 3 levels regardless of translator precision.

---

## 10. Source index

AWS blogs/docs: https://aws.amazon.com/deepracer/faqs/ · https://aws.amazon.com/blogs/machine-learning/custom-os-installation-now-available-on-aws-deepracer-devices/ · https://aws.amazon.com/blogs/machine-learning/the-end-of-an-era-the-final-aws-deepracer-league-championship-at-reinvent-2024/ · https://aws.amazon.com/blogs/machine-learning/celebrating-the-final-aws-deepracer-league-championship-and-road-ahead/ · https://aws.amazon.com/blogs/machine-learning/aws-deepracer-evo-and-sensor-kit-now-available-for-purchase/ · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/solution-overview.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/operate-your-vehicle.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/launch-device-console.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/calibrate-your-vehicle.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/drive-your-vehicle.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/inspect-manage-settings.html · https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/update-and-restore-vehicle.html · https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-vehicle-chassis-parts.html · https://builder.aws.com/content/2otsNvwo08hywC4Ovpr7mi1ySyI/deepracer-is-back-first-impressions-of-deepracer-on-aws · https://github.com/aws-solutions/deepracer-on-aws/ · https://aws.amazon.com/solutions/guidance/aws-deepracer-event-management/

AWS device code: https://github.com/aws-deepracer · aws-deepracer-launcher · aws-deepracer-ctrl-pkg · aws-deepracer-servo-pkg · aws-deepracer-webserver-pkg · aws-deepracer-camera-pkg · aws-deepracer-inference-pkg · aws-deepracer-model-optimizer-pkg · aws-deepracer-sensor-fusion-pkg · aws-deepracer-navigation-pkg · aws-deepracer-systems-pkg · aws-deepracer-device-info-pkg · aws-deepracer-status-led-pkg · aws-deepracer-usb-monitor-pkg · aws-deepracer-i2c-pkg · aws-deepracer-interfaces-pkg · aws-deepracer (Nav2) · aws-deepracer-follow-the-leader-sample-project · https://github.com/Slamtec/rplidar_ros/tree/ros2 · https://github.com/RobotWebTools/web_video_server/pull/111 · https://github.com/GT-RAIL/async_web_server_cpp

Community: https://deepracing.io · https://github.com/aws-deepracer-community/deepracer-custom-car (+ docs/flash-2404.md, upgrade-2004.md, apt.md, camera.md, CHANGES.md, ros_data_flow_diagram.md) · https://github.com/aws-deepracer-community/deepracer-custom-console · https://github.com/aws-deepracer-community/deepracer-simapp · https://github.com/aws-deepracer-community/deepracer-for-cloud · https://github.com/aws-deepracer-community/deepracer-utils · https://github.com/larsll/deepracer-pi · https://github.com/davidfsmith/deepracer-scripts · https://github.com/lshw54/awsdeepracer_control · https://pypi.org/project/awsdeepracer-control/ · https://pypi.org/project/aws-deepracer-control-v2/ · https://github.com/thu2004/deepracer-vehicle-api · https://github.com/athackst/deepracer_joy · https://www.allisonthackston.com/articles/aws-deepracer-3-joy.html · https://www.allisonthackston.com/articles/aws-deepracer-5-ros1-bridge.html · https://dev.to/mkreder/how-to-stream-video-from-the-deepracer-camera-mci · https://dev.classmethod.jp/articles/awsdeepracer-vehicle-hybrid-instance/ · https://repost.aws/questions/QUBX_rI3RYSYKUup6HDAWiew/how-to-use-deepracer-inferfaces-pkg · https://aihub.hkuspace.hku.hk/2025/02/28/aws-deepracer-closing-time-at-aws-reinvent-2024-how-did-that-physical-racing-go/

ROS ecosystem: https://raw.githubusercontent.com/ros/rosdistro/master/foxy/distribution.yaml · https://raw.githubusercontent.com/ros/rosdistro/master/jazzy/distribution.yaml · https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/README.md · https://index.ros.org/p/rosbridge_server/ · https://docs.ros.org/en/foxy/Releases/End-of-Life.html · https://endoflife.date/ros2 · https://husarion.com/tutorials/ros2-tutorials/6-robot-network/ · https://eprosima-dds-router.readthedocs.io/en/v2.0.0/rst/examples/ros_discovery_server_example.html

Simulation: https://github.com/google-deepmind/mujoco_menagerie · https://f1tenth-gym.readthedocs.io · https://gym-khana.readthedocs.io · https://github.com/f1tenth/f1tenth_simulator · https://github.com/COONEO/sim_car · https://github.com/CihatAltiparmak/car_sim · https://docs.isaacsim.omniverse.nvidia.com/4.2.0/features/environment_setup/assets/index.html
