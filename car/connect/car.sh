#!/usr/bin/env bash
# Laptop-side helper. Reads ~/.config/deepracer/env (never the repo) and talks to the car.
#   car.sh setup-key      first login with the image password, installs the SSH key, then key-only
#   car.sh ssh [cmd...]   key-based ssh
#   car.sh push <src> <dst>
#   car.sh bootstrap      copies car/bootstrap/ to the car and runs install_deepracer_stack.sh
#   car.sh preflight      runs the read-only report
set -euo pipefail
ENVF=${DEEPRACER_ENV:-$HOME/.config/deepracer/env}
[ -f "$ENVF" ] || { echo "missing $ENVF (see car/connect/env.example)" >&2; exit 2; }
set -a; . "$ENVF"; set +a
. "$(dirname "${BASH_SOURCE[0]}")/resolve-host.sh"   # DEEPRACER_HOST=auto or stale -> find the car
KEY=$(eval echo "${DEEPRACER_SSH_KEY:-~/.ssh/id_ed25519_deepracer}")
T="${DEEPRACER_SSH_USER:-deepracer}@${DEEPRACER_HOST:?set DEEPRACER_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o BatchMode=yes -i "$KEY")
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
  setup-key)
    [ -f "$KEY" ] || ssh-keygen -t ed25519 -N "" -C "deepracer-dev" -f "$KEY" -q
    PUB=$(cat "$KEY.pub")
    expect -f - "$T" "$DEEPRACER_SSH_PASSWORD" "$PUB" <<'EXP'
set timeout 25
lassign $argv target pw pub
spawn ssh -o StrictHostKeyChecking=accept-new -o PubkeyAuthentication=no -o PreferredAuthentications=password $target "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qF '$pub' ~/.ssh/authorized_keys 2>/dev/null || echo '$pub' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; echo KEY_INSTALLED"
expect {
  -re "(?i)password:" { send "$pw\r"; exp_continue }
  "KEY_INSTALLED"     { }
  "Permission denied" { puts "\nPASSWORD REJECTED"; exit 3 }
  timeout             { puts "\nTIMEOUT"; exit 4 }
  eof                 { }
}
expect eof
EXP
    ssh "${SSH_OPTS[@]}" "$T" 'echo "key login ok on $(hostname)"' ;;
  ssh)       shift; exec ssh "${SSH_OPTS[@]}" -t "$T" "$@" ;;
  push)      scp "${SSH_OPTS[@]}" -r "$2" "$T:$3" ;;
  bootstrap) scp "${SSH_OPTS[@]}" -r "$HERE/bootstrap" "$T:~/bootstrap"
             ssh "${SSH_OPTS[@]}" -t "$T" 'sudo bash ~/bootstrap/install_deepracer_stack.sh' ;;
  preflight) scp "${SSH_OPTS[@]}" "$HERE/bootstrap/preflight.sh" "$T:~/preflight.sh"
             ssh "${SSH_OPTS[@]}" "$T" 'bash ~/preflight.sh' ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
