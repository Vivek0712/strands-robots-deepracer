#!/usr/bin/env bash
# Enable the PCA9685 PWM outputs the stock servo node forgets to switch on.
#
# Finding (2026-10-14, aws-deepracer-core 2.0.383.0, Foxy): after boot the servo node exports
# /sys/class/pwm/pwmchip0/pwm0 (throttle) and pwm1 (steering), writes period and duty_cycle, but
# never writes 1 to each channel's `enable`. The ESC and steering servo then see no pulses at all,
# so a correct ServoCtrlMsg on /ctrl_pkg/servo_msg moves the duty_cycle file and nothing else.
# This oneshot waits for the two channels to be exported with a non-zero period (the servo node
# needs about 10 s after deepracer-core starts), writes 1 to both enable files and logs what it
# found. It never touches period, duty_cycle, polarity or calibration, and never restarts
# deepracer-core. Physics stops the car; this only lets physics hear the servo node.
set -u
CHIP=${DEEPRACER_PWM_CHIP:-/sys/class/pwm/pwmchip0}
WAIT_S=${DEEPRACER_PWM_WAIT_S:-60}
TAG=deepracer-pwm-enable
CHANNELS="0 1"   # pwm0 throttle, pwm1 steering

log() { logger -t "$TAG" "$*"; echo "[$TAG] $*"; }

ready() {
  local n
  for n in $CHANNELS; do
    [ -e "$CHIP/pwm$n/enable" ] || return 1
    [ -r "$CHIP/pwm$n/period" ] || return 1
    [ "$(cat "$CHIP/pwm$n/period" 2>/dev/null || echo 0)" != "0" ] || return 1
  done
  return 0
}

i=0
until ready; do
  i=$((i + 1))
  if [ "$i" -ge "$WAIT_S" ]; then
    log "pwm0/pwm1 not exported with a period after ${WAIT_S}s; is deepracer-core (servo_node) up? nothing written"
    exit 1
  fi
  sleep 1
done

rc=0
for n in $CHANNELS; do
  f="$CHIP/pwm$n/enable"
  before=$(cat "$f" 2>/dev/null || echo "?")
  if [ "$before" != "1" ]; then
    if ! echo 1 > "$f" 2>/dev/null; then
      log "pwm$n: writing 1 to $f failed (enable=$before)"
      rc=1
      continue
    fi
  fi
  after=$(cat "$f" 2>/dev/null || echo "?")
  log "pwm$n enable $before -> $after (period $(cat "$CHIP/pwm$n/period") ns, duty $(cat "$CHIP/pwm$n/duty_cycle") ns, waited ${i}s)"
  [ "$after" = "1" ] || rc=1
done
exit $rc
