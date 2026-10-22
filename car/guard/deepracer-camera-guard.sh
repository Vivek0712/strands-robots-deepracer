#!/usr/bin/env bash
# Mitigation for the OOM hazard in car/bootstrap/foxy-rosbridge.md: with no camera attached the
# stock camera_node logs ~500 errors/s and the Foxy launch parent grows to 2.5 GB in about an hour.
# Every 30 s (systemd timer):
#   * /dev/video0 absent on MISSES_TO_KILL consecutive runs and a camera_node process exists: kill it.
#     One miss is not enough: plugging a USB stick into the car resets the hub and the camera is gone
#     for about a minute (2026-10-17: the guard killed the node on that blink and the show lost its eyes).
#   * web_video_server (the console's MJPEG backend, port 8080) not listening while deepracer-core runs:
#     relaunch it (it segfaults under stream churn and the stock image never restarts it).
#   * /dev/video0 present, deepracer-core running and no camera_node process: relaunch the node the way
#     the stock launcher does (namespace camera_pkg, resize_images true), so a camera that comes back
#     gets its node back without a core restart.
# The pattern is anchored on the stock binary path so it can never match this script's own command
# line (bash .../deepracer-camera-guard.sh) or the launcher.
set -u
STAMP=/run/deepracer-camera-guard.logged
MISSES=/run/deepracer-camera-guard.misses
MISSES_TO_KILL=${MISSES_TO_KILL:-3}
PATTERN='^/opt/aws/deepracer/lib/camera_pkg/lib/camera_pkg/camera_node( |$)'

relaunch() {
  # shellcheck disable=SC1091
  source /opt/ros/foxy/setup.bash
  # shellcheck disable=SC1091
  [ -f /opt/aws/deepracer/lib/setup.bash ] && source /opt/aws/deepracer/lib/setup.bash
  nohup ros2 run camera_pkg camera_node --ros-args -r __ns:=/camera_pkg -r __node:=camera_node \
    -p resize_images:=true 2>&1 | systemd-cat -t deepracer-camera-guard &
  disown
}

relaunch_video_server() {
  # shellcheck disable=SC1091
  source /opt/ros/foxy/setup.bash
  # shellcheck disable=SC1091
  [ -f /opt/aws/deepracer/lib/setup.bash ] && source /opt/aws/deepracer/lib/setup.bash
  nohup ros2 run web_video_server web_video_server --ros-args -r __ns:=/web_video_server \
    -r __node:=web_video_server 2>&1 | systemd-cat -t deepracer-camera-guard &
  disown
}

# The console's MJPEG route is nginx -> web_video_server:8080. That node segfaults under rapid
# stream add/remove churn (2026-10-17, exit -11) and nothing in the stock image restarts it.
if systemctl is-active --quiet deepracer-core && ! ss -ltn 2>/dev/null | grep -q ":8080 "; then
  if ! pgrep -f "web_video_server/lib/web_video_server/web_video_server" >/dev/null; then
    logger -t deepracer-camera-guard "web_video_server is not listening on 8080: relaunching it"
    relaunch_video_server
  fi
fi

if [ -e /dev/video0 ]; then
  rm -f "$STAMP" "$MISSES"
  if ! pgrep -f "$PATTERN" >/dev/null && systemctl is-active --quiet deepracer-core; then
    logger -t deepracer-camera-guard "/dev/video0 is back and camera_node is not running: relaunching it"
    relaunch
  fi
  exit 0
fi

n=$(( $(cat "$MISSES" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$MISSES"
[ "$n" -ge "$MISSES_TO_KILL" ] || exit 0
PIDS=$(pgrep -f "$PATTERN" || true)
[ -n "$PIDS" ] || exit 0
kill -TERM $PIDS 2>/dev/null || true
if [ ! -e "$STAMP" ]; then
  logger -t deepracer-camera-guard "no /dev/video0 for $n checks: killed camera_node pid(s) $PIDS (stock node floods logs and leaks memory headless)"
  touch "$STAMP"
fi
exit 0
