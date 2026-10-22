# Sourced by car.sh and install.sh after ~/.config/deepracer/env: makes DEEPRACER_HOST a host
# that answers today. "auto", empty, or an address that no longer answers on 22/9090 is
# replaced by find-car.sh (mDNS, then the car's MAC in the ARP table, then a ping sweep).
_rh_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"  # bash or zsh
_rh_answers() { nc -z -w 1 "$1" 22 2>/dev/null || nc -z -w 1 "$1" 9090 2>/dev/null; }
# The portal's connect workflow (deepracer_agent.connect) exports DEEPRACER_SSH_HOST when the stack
# talks to the car through an SSH tunnel (DEEPRACER_HOST is then 127.0.0.1): ssh/scp go to the car.
if [ -n "${DEEPRACER_SSH_HOST:-}" ] && _rh_answers "$DEEPRACER_SSH_HOST"; then
  export DEEPRACER_HOST="$DEEPRACER_SSH_HOST"
elif [ -z "${DEEPRACER_HOST:-}" ] || [ "${DEEPRACER_HOST}" = "auto" ] || ! _rh_answers "$DEEPRACER_HOST"; then
  _rh_found=$("$_rh_dir/find-car.sh" 2>/dev/null) || {
    echo "resolve-host: car not found (DEEPRACER_HOST=${DEEPRACER_HOST:-unset}); is it on this network?" >&2
    exit 3
  }
  [ "${DEEPRACER_HOST:-}" = "$_rh_found" ] || echo "resolve-host: car is at $_rh_found" >&2
  export DEEPRACER_HOST="$_rh_found"
fi
