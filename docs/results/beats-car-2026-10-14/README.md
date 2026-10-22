# Beats on the car, 2026-10-14, wheels off, camera not seen

Command per beat (PORTAL_URL unset; the pre-grant is said here as the docs require):

```
set -a; . ~/.config/deepracer/env; set +a
DEEPRACER_BODY=car AWS_PROFILE=heisenberg AWS_DEFAULT_REGION=us-east-1 \
STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state \
.venv/bin/python -m beats <preflight|red_light|pull_the_plug> --body car
```

Run dir `runs/s-20261014-0649/`; `events.jsonl` here is its copy (103 events). No frames were
captured (no camera), so none are included.

| Beat | Result | Why |
|---|---|---|
| preflight | PASS | explicit no-go: `camera: no frames in 1 s`; battery 11, deadman armed, calibration ok, pwm_outputs ok, 2530 ms |
| red_light | FAIL on "the rover started rolling" only | the gate denied the drive (`vision unavailable`, no frame); barge-in to stop_all 253 ms, `stop` cause `barge_in` logged, wheels stopped |
| pull_the_plug | PASS | cut to tripped 253 ms, re-armed 1335 ms after heartbeats resumed, `stop` cause `deadman` logged; no motion before the cut (denied, no frame) |

Not run, blocked on the camera: marshal, apology, blindfold, sign. Each needs a frame for the gate
to allow a drive or for `look()` to answer.

## Unblocking the camera (user runs these; the session tooling refused the remote sudo write)

The camera is plugged in (`/dev/video0`, `/dev/video1`, `uvcvideo` loaded) but `camera_node` started
before it. With the throttle PWM at neutral (`cat /sys/class/pwm/pwmchip0/pwm0/duty_cycle` = 1446000):

```
printf '%s\n' "$DEEPRACER_SSH_PASSWORD" | bash car/connect/car.sh ssh 'sudo -S -p "" systemctl restart deepracer-core'
sleep 20
printf '%s\n' "$DEEPRACER_SSH_PASSWORD" | bash car/connect/car.sh ssh 'sudo -S -p "" systemctl restart deepracer-rosbridge'
bash car/connect/car.sh ssh 'systemctl is-active deepracer-core deepracer-rosbridge deepracer-deadman deepracer-pwm-enable; cat /sys/class/pwm/pwmchip0/pwm0/enable /sys/class/pwm/pwmchip0/pwm1/enable; journalctl -t deepracer-pwm-enable --no-pager | tail -2'
```

`deepracer-pwm-enable` is `PartOf=deepracer-core.service`, so the restart re-runs it; both flags must
read 1 afterwards. Then check the camera and the flood:

```
DEEPRACER_BODY=car .venv/bin/python -c "from deepracer_agent.tools import ConsoleClient as C; c=C(); print(c.api_get('get_sensor_status'), c.frame_rate(1.0), len(c.capture_frame() or b''))"
bash car/connect/car.sh ssh 'journalctl -u deepracer-core --since "2 min ago" | grep -c "Publishing camera images to topics failed"'
```

Expect `camera_status: connected`, frame_rate above 10, a JPEG of tens of kB, flood count 0. Then:

```
DEEPRACER_BODY=car AWS_PROFILE=heisenberg AWS_DEFAULT_REGION=us-east-1 \
STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state .venv/bin/python -m beats all --body car
```

and copy `runs/<session>/events.jsonl` here; copy frames only if they contain no people.
