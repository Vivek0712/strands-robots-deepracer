#!/usr/bin/env bash
# Remove everything car/install.sh put on the car: units (deadman, camera guard, pwm enable), scripts,
# the colcon workspace, the source copy. The PWM enable flags are left as they are (disabling them would
# cut the servo pulses under a running stack).
# Leaves deepracer-core, deepracer-rosbridge and calibration untouched.
set -euo pipefail
ENVF=${DEEPRACER_ENV:-$HOME/.config/deepracer/env}
[ -f "$ENVF" ] || { echo "missing $ENVF" >&2; exit 2; }
set -a; . "$ENVF"; set +a
: "${DEEPRACER_HOST:?}" "${DEEPRACER_SSH_PASSWORD:?}"
KEY=$(eval echo "${DEEPRACER_SSH_KEY:-~/.ssh/id_ed25519_deepracer}")
T="${DEEPRACER_SSH_USER:-deepracer}@${DEEPRACER_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o BatchMode=yes -i "$KEY")
REMOTE=$(cat <<'REMOTE_EOF'
set -u
systemctl disable --now deepracer-camera-guard.timer 2>/dev/null || true
systemctl stop deepracer-camera-guard.service 2>/dev/null || true
systemctl disable --now deepracer-deadman.service 2>/dev/null || true
systemctl disable deepracer-pwm-enable.service 2>/dev/null || true
systemctl stop deepracer-pwm-enable.service 2>/dev/null || true
rm -f /etc/systemd/system/deepracer-deadman.service /etc/systemd/system/deepracer-camera-guard.service /etc/systemd/system/deepracer-camera-guard.timer /etc/systemd/system/deepracer-pwm-enable.service
systemctl daemon-reload
rm -rf /opt/deadracer-agent /opt/deepracer-agent /run/deepracer-camera-guard.logged
rm -rf "/home/${SUDO_USER:-deepracer}/deepracer-agent-src"
systemctl is-active deepracer-core deepracer-rosbridge
echo "[rollback] done; deadman, guard and pwm-enable removed"
REMOTE_EOF
)
printf '%s\n' "$DEEPRACER_SSH_PASSWORD" | ssh "${SSH_OPTS[@]}" "$T" "sudo -S -p '' bash -c $(printf '%q' "$REMOTE")"
