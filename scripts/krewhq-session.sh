#!/usr/bin/env bash
# KrewHQ session helper for the four agent teams (see .krewhq/README.md).
#   scripts/krewhq-session.sh start <team>
#   scripts/krewhq-session.sh capture <team> <type> "<title>" "<text>"
#   scripts/krewhq-session.sh handoff <team> <to-team>
# Fails open: a hub outage never blocks a session (exit 0 on read paths).
set -uo pipefail
# Optional maintainer tooling: without a krewhq CLI this script prints one line and exits 0.
K="${KREWHQ_BIN:-$(command -v krewhq 2>/dev/null || echo /nonexistent/krewhq)}"
# Local pilot hub (deploy/docker hub with ~/.krewhq-org/projects/deepracer/team-map.yaml mounted).
# Override with the EC2 hub once its security group admits this machine.
export KREWHQ_HUB_URL="${KREWHQ_HUB_URL:-http://127.0.0.1:8443}"
# No default token: set KREWHQ_TOKEN in your shell (the hub asserts the identity it names).
export KREWHQ_TOKEN="${KREWHQ_TOKEN:-}"
export KREWHQ_TEAM="${KREWHQ_TEAM:-${2:-deepracer}}"
export KREWHQ_REPO="${KREWHQ_REPO:-strands-robots-deepracer}"
REPO_REF="https://github.com/Vivek0712/strands-robots-deepracer"
cmd=${1:-}; team=${2:-}
[ -x "$K" ] || { echo "[krewhq] CLI not found at $K; continuing without team context"; exit 0; }
[ -n "$team" ] || { echo "usage: $0 start|capture|handoff <team> ..."; exit 2; }
ticket="deepracer-$team"
case "$cmd" in
  start)
    "$K" session-start --ticket "$ticket" --branch "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)" || true
    "$K" recall --ticket "$ticket" "$team handoff contracts gotchas deepracer" || true
    "$K" handoffs 2>/dev/null | head -20 || true
    ;;
  capture)
    type=${3:-fact}; title=${4:-untitled}; text=${5:-}
    "$K" capture --surface cli --ticket "$ticket" --type "$type" --title "$title" "$text" || true
    ;;
  handoff)
    to=${3:?to-team required}
    "$K" handoff "deepracer-$to" --from-pending all --ref "$REPO_REF" || true
    "$K" sync || true
    ;;
  *) echo "unknown command $cmd"; exit 2;;
esac
exit 0
