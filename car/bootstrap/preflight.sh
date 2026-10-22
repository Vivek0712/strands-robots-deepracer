#!/usr/bin/env bash
# Read-only verification report for the car. Safe to run any time; changes nothing.
# Usage (on the car): ./preflight.sh        (sudo not required; some lines say "n/a" without it)
set -u
sec() { printf '\n== %s\n' "$*"; }
sec OS;        lsb_release -ds 2>/dev/null; uname -r; hostname; cat /etc/deepracer-custom-car.commit 2>/dev/null
sec Hardware;  cat /sys/class/dmi/id/product_name /sys/class/dmi/id/chassis_asset_tag 2>/dev/null; nproc; free -h | sed -n 2p; df -h / | sed -n 2p
sec Packages;  dpkg-query -W -f='${Package} ${Version}\n' 'aws-deepracer-*' 'ros-*-ros-core' 'ros-*-rosbridge-suite' 2>/dev/null
sec Services;  for s in deepracer-core deepracer-rosbridge ssh NetworkManager; do printf '%-22s %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null)"; done
sec Network;   ip -br addr | grep -v "^lo"; (command -v ufw >/dev/null && sudo -n ufw status 2>/dev/null) || echo "ufw: n/a"
sec Ports;     ss -ltnp 2>/dev/null | awk 'NR==1 || /:(22|80|443|9090|8080) /'
ROSD=$(ls -d /opt/ros/* 2>/dev/null | head -1)
sec ROS;       if [ -n "$ROSD" ] && [ -f "$ROSD/setup.bash" ]; then echo "distro: $(basename $ROSD)"
                 set +u; source "$ROSD/setup.bash" 2>/dev/null; [ -f /opt/aws/deepracer/lib/setup.bash ] && source /opt/aws/deepracer/lib/setup.bash 2>/dev/null; set -u; ros2 --version 2>/dev/null || echo "ros2 cli: n/a"; echo "RMW=${RMW_IMPLEMENTATION:-default} DOMAIN=${ROS_DOMAIN_ID:-0}"
                 timeout 20 ros2 topic list 2>/dev/null | grep -E "manual_drive|servo_msg|display_mjpeg|scan|battery|vehicle_state|rosbridge|rosapi" || echo "(no DeepRacer topics seen in 20 s)"
                 timeout 10 ros2 service list 2>/dev/null | grep -E "vehicle_state|enable_state|get_led|set_led|calibration|battery_level" || echo "(no ctrl_pkg services seen)"
                 python3 -c "import deepracer_interfaces_pkg.msg as m; print('ServoCtrlMsg importable:', hasattr(m,'ServoCtrlMsg'))" 2>&1 | tail -1
               else echo "no /opt/ros/<distro>"; fi
sec Camera;    ls /dev/video* 2>/dev/null || echo "no /dev/video*"; v4l2-ctl --list-devices 2>/dev/null | head -6
sec LiDAR;     ls -l /dev/ttyUSB* 2>/dev/null || echo "no /dev/ttyUSB* (no LiDAR)"
sec USB;       lsusb 2>/dev/null
sec Audio;     aplay -l 2>&1 | head -5; ls /proc/asound 2>/dev/null | head; cat /etc/modprobe.d/blacklist-audio.conf 2>/dev/null
sec Bluetooth; rfkill list 2>/dev/null; (command -v bluetoothctl >/dev/null && timeout 5 bluetoothctl list) || echo "bluetoothctl: not installed"; ls /sys/class/bluetooth 2>/dev/null || echo "no /sys/class/bluetooth"
sec Battery;   if [ -n "$ROSD" ]; then timeout 10 ros2 service call /i2c_pkg/battery_level deepracer_interfaces_pkg/srv/BatteryLevelSrv "{}" 2>/dev/null | tail -1 || echo "battery service n/a"; fi
sec Webserver; curl -sk -m 5 -o /dev/null -w 'https://localhost -> %{http_code}\n' https://localhost/ ; curl -sk -m 5 https://localhost/api/supported_apis 2>/dev/null | head -c 300; echo
