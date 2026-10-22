#!/usr/bin/env bash
# One-line entry point for a freshly flashed car with no SSH yet. Run at the car's console:
#   curl -fsSL http://<laptop-ip>:8000/bootstrap.sh | sudo bash
# It installs openssh-server, fetches car/bootstrap/ from the laptop, runs
# install_deepracer_stack.sh, and reports each stage back to the laptop's http log.
# SSH key setup happens afterwards from the laptop (car/connect/car.sh setup-key), with the
# user's own password; this script does not touch authorized_keys or sudoers.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
SERVER=${SERVER:?SERVER must be set (laptop http base URL)}
U=${SUDO_USER:-$(id -un)}
echo "[remote-bootstrap] user=$U server=$SERVER"
report() { curl -fsS -m 5 "$SERVER/report?stage=$1&user=$U&ip=$(hostname -I | awk '{print $1}')&host=$(hostname)" -o /dev/null || true; }
report start
apt-get update -y
apt-get install -y --no-install-recommends openssh-server curl ca-certificates git ufw
systemctl enable --now ssh
ufw allow OpenSSH >/dev/null || true
report ssh_ready
echo "[remote-bootstrap] SSH ready: ssh $U@$(hostname -I | awk '{print $1}')"
mkdir -p /opt/strands-bootstrap && curl -fsSL "$SERVER/bootstrap.tar.gz" | tar -xz -C /opt/strands-bootstrap
if bash /opt/strands-bootstrap/bootstrap/install_deepracer_stack.sh 2>&1 | tee /var/log/strands-bootstrap.log; then
  report stack_done
else
  report stack_failed; exit 1
fi
echo "[remote-bootstrap] finished; log at /var/log/strands-bootstrap.log"
