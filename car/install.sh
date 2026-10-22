#!/usr/bin/env bash
# Install the deadman node, the camera guard and the PWM-enable oneshot on the car, from the laptop.
#   bash car/install.sh            (reads ~/.config/deepracer/env; never writes the password anywhere)
#   bash car/install.sh --dry-run  (copy only, no sudo)
# What it does on the car (all under /opt/deepracer-agent):
#   1. copies car/deadman, car/guard and car/pwm to ~/deepracer-agent-src (rsync, scp fallback)
#   2. colcon builds deepracer_deadman in /opt/deepracer-agent/ws with Foxy + the stock stack sourced
#   3. installs deepracer-deadman.sh, the guard script, the pwm script, the four units; daemon-reload;
#      enable --now; restarts ONLY deepracer-deadman so the new node code is loaded
# It never restarts deepracer-core, never touches calibration, never reboots.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVF=${DEEPRACER_ENV:-$HOME/.config/deepracer/env}
[ -f "$ENVF" ] || { echo "missing $ENVF (see car/connect/env.example)" >&2; exit 2; }
set -a; . "$ENVF"; set +a
. "$HERE/connect/resolve-host.sh"   # DEEPRACER_HOST=auto or stale -> find the car
: "${DEEPRACER_HOST:?}" "${DEEPRACER_SSH_PASSWORD:?sudo needs DEEPRACER_SSH_PASSWORD}"
KEY=$(eval echo "${DEEPRACER_SSH_KEY:-~/.ssh/id_ed25519_deepracer}")
T="${DEEPRACER_SSH_USER:-deepracer}@${DEEPRACER_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o BatchMode=yes -i "$KEY")
DRY=${1:-}

echo "[install] copying car/deadman, car/guard and car/pwm to $T:~/deepracer-agent-src"
ssh "${SSH_OPTS[@]}" "$T" 'mkdir -p ~/deepracer-agent-src'
if command -v rsync >/dev/null && ssh "${SSH_OPTS[@]}" "$T" 'command -v rsync >/dev/null'; then
  rsync -az --delete -e "ssh ${SSH_OPTS[*]}" "$HERE/deadman" "$HERE/guard" "$HERE/pwm" "$T:~/deepracer-agent-src/"
else
  ssh "${SSH_OPTS[@]}" "$T" 'rm -rf ~/deepracer-agent-src/deadman ~/deepracer-agent-src/guard ~/deepracer-agent-src/pwm'
  scp -q "${SSH_OPTS[@]}" -r "$HERE/deadman" "$HERE/guard" "$HERE/pwm" "$T:~/deepracer-agent-src/"
fi
[ "$DRY" = "--dry-run" ] && { echo "[install] dry run: copied only"; exit 0; }

# The remote script runs as root via `sudo -S bash -c` (never `sudo -S tee`, see foxy-rosbridge.md);
# the password goes in on stdin and is never written to a file on either side.
REMOTE=$(cat <<'REMOTE_EOF'
set -euo pipefail
SRC=/home/${SUDO_USER:-deepracer}/deepracer-agent-src
WS=/opt/deepracer-agent/ws
mkdir -p /opt/deepracer-agent "$WS/src" /var/log/deepracer-agent
rm -rf "$WS/src/deepracer_deadman"
cp -r "$SRC/deadman" "$WS/src/deepracer_deadman"
rm -f "$WS/src/deepracer_deadman/"*.service "$WS/src/deepracer_deadman/"*.sh
set +u
source /opt/ros/foxy/setup.bash
source /opt/aws/deepracer/lib/setup.bash
set -u
cd "$WS"
colcon build --packages-select deepracer_deadman --event-handlers console_direct+ 2>&1 | tail -5
install -m 0755 "$SRC/deadman/deepracer-deadman.sh" /opt/deepracer-agent/deepracer-deadman.sh
install -m 0755 "$SRC/guard/deepracer-camera-guard.sh" /opt/deepracer-agent/deepracer-camera-guard.sh
install -m 0755 "$SRC/pwm/deepracer-pwm-enable.sh" /opt/deepracer-agent/deepracer-pwm-enable.sh
install -m 0644 "$SRC/deadman/deepracer-deadman.service" /etc/systemd/system/deepracer-deadman.service
install -m 0644 "$SRC/guard/deepracer-camera-guard.service" /etc/systemd/system/deepracer-camera-guard.service
install -m 0644 "$SRC/guard/deepracer-camera-guard.timer" /etc/systemd/system/deepracer-camera-guard.timer
install -m 0644 "$SRC/pwm/deepracer-pwm-enable.service" /etc/systemd/system/deepracer-pwm-enable.service
systemctl daemon-reload
systemctl enable deepracer-deadman.service
systemctl restart deepracer-deadman.service   # ours only; deepracer-core is never restarted
systemctl enable --now deepracer-camera-guard.timer
systemctl enable --now deepracer-pwm-enable.service
sleep 3
systemctl is-active deepracer-deadman.service deepracer-camera-guard.timer deepracer-pwm-enable.service
for n in 0 1; do echo "pwm$n enable=$(cat /sys/class/pwm/pwmchip0/pwm$n/enable 2>/dev/null || echo missing)"; done
echo "[install] on-car install done"
REMOTE_EOF
)
echo "[install] building and installing on the car (sudo)"
printf '%s\n' "$DEEPRACER_SSH_PASSWORD" | ssh "${SSH_OPTS[@]}" "$T" "sudo -S -p '' bash -c $(printf '%q' "$REMOTE")"
echo "[install] verify from the laptop: DEEPRACER_BODY=car .venv/bin/python -m deepracer_agent.transport --check-deadman"
