#!/usr/bin/env bash
# Idempotent on-car bootstrap for the strands-robots DeepRacer (Ubuntu 24.04 / ROS 2 Jazzy).
#
# 1. Verifies Ubuntu 24.04 (noble) on the original Intel DeepRacer.
# 2. If the community DeepRacer stack (aws-deepracer-core) is missing, installs it exactly the
#    way aws-deepracer-community/deepracer-custom-car does (install-prerequisites.sh then
#    install-deepracer.sh from a pinned checkout), otherwise records the installed versions.
# 3. Installs ros-jazzy-rosbridge-suite and opens 9090/tcp (strands-robots talks to the car
#    over rosbridge from the laptop; nothing else on the car changes).
# 4. Installs deepracer-rosbridge.service (After=deepracer-core.service, sources the
#    DeepRacer overlay so deepracer_interfaces_pkg types resolve).
# 5. Never touches calibration, never changes vehicle_state, never upgrades aws-deepracer-*
#    packages that are already installed (set DR_UPGRADE=1 to allow that).
#
# Usage (on the car):  sudo ./install_deepracer_stack.sh [--rosbridge-only]
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMUNITY_REPO=https://github.com/aws-deepracer-community/deepracer-custom-car.git
COMMUNITY_REF=${COMMUNITY_REF:-main}
ROSBRIDGE_ONLY=0
[ "${1:-}" = "--rosbridge-only" ] && ROSBRIDGE_ONLY=1

log()  { printf '\n[bootstrap] %s\n' "$*"; }
die()  { printf '\n[bootstrap] FATAL: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "run with sudo"
. /etc/os-release
[ "${UBUNTU_CODENAME:-}" = noble ] || die "expected Ubuntu 24.04 (noble), got ${PRETTY_NAME:-unknown}"
[ "$(dpkg --print-architecture)" = amd64 ] || die "expected amd64 (original DeepRacer)"
export ROS_DISTRO=jazzy

log "host $(hostname), kernel $(uname -r), ${PRETTY_NAME}"
log "chassis asset tag (console password source): $(cat /sys/class/dmi/id/chassis_asset_tag 2>/dev/null || echo n/a)"

# ---------------------------------------------------------------- 2. DeepRacer stack
if dpkg -s aws-deepracer-core >/dev/null 2>&1; then
  log "aws-deepracer-core already installed:"
  dpkg-query -W -f='  ${Package} ${Version}\n' 'aws-deepracer-*' 2>/dev/null || true
  if [ "${DR_UPGRADE:-0}" = 1 ]; then
    log "DR_UPGRADE=1: upgrading aws-deepracer-* from the community repo"
    apt-get update -y && apt-get install -y --only-upgrade 'aws-deepracer-*'
  fi
elif [ "$ROSBRIDGE_ONLY" = 1 ]; then
  die "aws-deepracer-core missing and --rosbridge-only given"
else
  log "aws-deepracer-core missing: installing the community stack from $COMMUNITY_REPO@$COMMUNITY_REF"
  apt-get update -y && apt-get install -y --no-install-recommends git curl ca-certificates
  WS=/opt/deepracer-custom-car
  if [ ! -d "$WS/.git" ]; then git clone --depth 1 --branch "$COMMUNITY_REF" "$COMMUNITY_REPO" "$WS"; fi
  ( cd "$WS" && git rev-parse HEAD > /etc/deepracer-custom-car.commit && log "pinned commit $(cat /etc/deepracer-custom-car.commit)" )
  # community scripts: prerequisites (ssh, ufw, wifi power-save off, PWM, grub) then the stack
  bash "$WS/install_scripts/aws-24.04/install-prerequisites.sh"
  bash "$WS/install_scripts/aws-24.04/install-deepracer.sh"
  touch /var/run/strands-reboot-required
  log "fresh install done: GRUB and PWM changes need ONE reboot before deepracer-core will run"
fi

# apt repo + key present either way (image ships them; harmless if already there)
install -m 0644 "$HERE/aws_deepracer-community.list" /etc/apt/sources.list.d/aws_deepracer-community.list
install -m 0644 "$HERE/deepracer-community.asc" /etc/apt/trusted.gpg.d/deepracer-community.asc
[ -x /etc/rc.local ] || { install -m 0755 "$HERE/rc.local" /etc/rc.local; log "installed rc.local (PWM export)"; }

# ---------------------------------------------------------------- 3. rosbridge
if dpkg -s ros-jazzy-rosbridge-suite >/dev/null 2>&1; then
  log "ros-jazzy-rosbridge-suite already installed"
else
  if [ ! -f /etc/apt/sources.list.d/ros2.list ]; then
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" > /etc/apt/sources.list.d/ros2.list
  fi
  apt-get update -y
  apt-get install -y --no-install-recommends ros-jazzy-rosbridge-suite
fi
if command -v ufw >/dev/null; then ufw allow 9090/tcp >/dev/null && log "ufw: 9090/tcp allowed"; fi

# ---------------------------------------------------------------- 4. systemd unit
OVERLAY=/opt/aws/deepracer/lib/setup.bash
[ -f "$OVERLAY" ] || log "WARNING: $OVERLAY not found; rosbridge will only see base ROS types"
cat > /usr/local/bin/deepracer-rosbridge.sh <<'SH'
#!/usr/bin/env bash
set -e
source /opt/ros/jazzy/setup.bash
[ -f /opt/aws/deepracer/lib/setup.bash ] && source /opt/aws/deepracer/lib/setup.bash
exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 address:=0.0.0.0
SH
chmod 0755 /usr/local/bin/deepracer-rosbridge.sh
cat > /etc/systemd/system/deepracer-rosbridge.service <<'UNIT'
[Unit]
Description=rosbridge websocket (port 9090) for strands-robots
After=network-online.target deepracer-core.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/deepracer-rosbridge.sh
Restart=on-failure
RestartSec=3
Environment=ROS_DOMAIN_ID=0

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now deepracer-rosbridge.service
sleep 3
systemctl is-active deepracer-rosbridge.service && log "deepracer-rosbridge.service active" || die "deepracer-rosbridge.service failed: journalctl -u deepracer-rosbridge -n 50"

[ -f /var/run/strands-reboot-required ] && log "REBOOT REQUIRED (sudo reboot) before using the car"
log "done. Run preflight.sh for the verification report."
