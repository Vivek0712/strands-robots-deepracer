# Wheels-off results, 2026-10-14 (layer 2: real car on a stand)

Car `amss-abcd`, hardware R2.1, stock Ubuntu 20.04 / ROS 2 Foxy, `aws-deepracer-core` 2.0.383.0,
rosbridge 1.3.1 on 9090. Drive pack connected, ESC armed, wheels off the ground, user present with a
thumb on the switch. Every motion in this session was throttle 0.3 (session cap 0.5) for at most
2 s, and every test ended with a zero pair. Physics stops the car; the decider explains.

Raw rows: `wheels-off-2026-10-14-measurements.jsonl`; 100 Hz PWM samples per test:
`wheels-off-2026-10-14-samples/`. Both are copies of `runs/wheels-off-2026-10-14/`.

## Commands

```
# the suite (9 tests, 31.5 s)
make wheels-off
# the same, with the measurement rows printed
set -a; . ~/.config/deepracer/env; set +a; .venv/bin/pytest -q -m wheels_off tests/car -s -v

# the PWM-enable oneshot and the deadman LED fix, installed by
bash car/install.sh
bash car/connect/car.sh ssh 'systemctl is-active deepracer-pwm-enable deepracer-deadman deepracer-camera-guard.timer'
bash car/connect/car.sh ssh 'cat /sys/class/pwm/pwmchip0/pwm0/enable /sys/class/pwm/pwmchip0/pwm1/enable'

# the live deadman check (arm, silence, trip; then 30 s to idle and LED off)
DEEPRACER_BODY=car .venv/bin/python -m deepracer_agent.transport --check-deadman --hold 3 --wait 4
```

How the PWM numbers were taken: `tests/car/remote_sampler.py` runs on the car (Python 3.8, no
root) and reads `pwm0`/`pwm1` `duty_cycle` every 10 ms; the laptop stamps its own events onto the
car's clock by writing a mark down the same SSH channel (`tests/car/pwm_sampler.py`). The one-way
delay of that channel (half the minimum ping RTT, 2.6 to 16.5 ms here) is added as the
correction and is the error bar.

## 1. Install evidence (car/pwm, car/deadman)

| Check | Result |
|---|---|
| `systemctl is-active deepracer-pwm-enable deepracer-deadman deepracer-camera-guard.timer` | `active active active` |
| `journalctl -t deepracer-pwm-enable` | `pwm0 enable 1 -> 1 (period 20000000 ns, duty 1446000 ns, waited 0s)`, `pwm1 enable 1 -> 1 (period 20000000 ns, duty 1450000 ns, waited 0s)` (flags were hand-set earlier this boot; a cold boot is the real test) |
| `pwm0/enable`, `pwm1/enable` | `1`, `1` |
| preflight `pwm_outputs` (SSH read) | `ok` |
| deadman restarted by install.sh | `ActiveEnterTimestamp 02:31:40 EDT`; `deepracer-core` untouched (up since 23:53:31) |

## 2. Deadman check with LED (`--check-deadman --hold 3 --wait 4`)

| Step | Measured |
|---|---|
| armed within 3 s | yes (`gap_ms 0`) |
| tripped after silence | yes, deadman-reported gap **318 ms** |
| zeros on `/ctrl_pkg/servo_msg` | 3 of 3 echoed messages `angle 0.0, throttle 0.0` |
| LED on trip | pwm2 duty `0 -> 10000000` (red) at 02:33:33 |
| idle after 30 s | `deadman -> idle` logged 02:34:02 (29.7 s after the last heartbeat) |
| LED on idle | pwm2 duty `10000000 -> 0` between the 02:33:59 and 02:34:04 samples: **off** |

Node log: `LED service call timed out after 1.0s (ignored)` on both LED calls, yet the LED channel
changed. The stock `set_led_state` service acts but answers late (or not at all); the node's
1 s best-effort timeout is correct behaviour and the warning is noise.

## 3. Link, battery, PWM outputs

| Row | Value |
|---|---|
| rosbridge `status` round trip | 271 ms (includes the first dial) |
| `/deepracer_agent/deadman_state` in topic list | yes |
| `/i2c_pkg/battery_level` | **11** (earlier today `-1`; the pack is seen now) |
| `pwm_outputs` | `ok` (`active`, `1`, `1`) |

## 4. Hop PWM (direction cannot be asserted remotely; recorded)

`publish /webserver_pkg/manual_drive {angle 0, throttle +0.3}` x20 at 20 Hz (1 s), then the zero pair.

| Quantity | Value |
|---|---|
| throttle PWM at rest | 1 446 000 ns |
| throttle PWM during the hop | **1 405 500 ns** (only value seen; 40 500 ns below neutral) |
| steering PWM during the hop | 1 450 000 ns (unchanged) |
| first publish -> PWM leaves neutral | 442 ms (raw 439.9 + one-way 2.6). Includes `rosbridge_action`'s connect + advertise |
| zero pair sent -> PWM back at neutral | 352 ms (raw 349.7 + 2.6). Through `rosbridge_action` (lock, advertise, 2 messages) |
| final sample | 1 446 000 ns (neutral restored) |
| direction | **UNVERIFIED**: +0.3 moves the duty below the mid. Forward or reverse needs wheels on the floor (`THROTTLE_FORWARD_SIGN`) |

## 5. Steering sweep (angle +0.5 / -0.5 at zero throttle, 0.5 s each)

| Quantity | Value |
|---|---|
| steering PWM at rest | 1 450 000 ns |
| angle +0.5 | 1 575 000 ns (+125 000) |
| angle -0.5 | 1 325 000 ns (-125 000) |
| throttle PWM during the sweep | 1 446 000 ns only (no throttle leak) |

Which side is left needs eyes on the car; the two excursions are symmetric about the rest value.

## 6. Stop latency through the product driver (`DeepRacerRobot.stop`)

`drive(linear 0.3, duration 2.0)` on the preemptible stream; `stop(cause="operator")` after ~0.4 s.

| From `stop()` call to | ms |
|---|---|
| `stop()` returning | 259.3 |
| first zero pair on `/ctrl_pkg/servo_msg` (laptop echo) | **238.5** |
| throttle PWM at neutral (car sysfs) | **233.8** (raw 230.0 + one-way 3.8) |
| `stop` event `latency_ms` (the zero publish itself) | 258 |

The drive result read `DRIVE DONE ... moved for 0.51 s ... 40 messages`: the stream was interrupted
after 0.51 s. The 230 ms is almost all `rosbridge_action` (process-wide lock, advertise, publish) for
the zero pair; the car side is a few ms.

Root cause found afterwards: `rosbridge_action._publish` sleeps 200 ms after `advertise` so DDS can
match the new publisher. `RosbridgeTransport` now keeps one advertised publisher per topic
(`warm()` after the handshake), so the zero pair skips the settle. This table is the PRE-change
measurement; rerun `make wheels-off` for the new number.

## 7. Barge-in path (`AgentRuntime.stop_all` during a 2 s 0.3 drive)

| From `stop_all()` call to | ms |
|---|---|
| `stop_all()` returning | 257.2 |
| first zero pair on `/ctrl_pkg/servo_msg` | **253.0** |
| throttle PWM at neutral | **266.4** (raw 249.9 + one-way 16.5) |
| `stop` event (cause `operator`) `latency_ms` | 256 |
| heartbeat off -> deadman reports `tripped` | 422.1 (deadman gap 317 ms + 2 Hz state publish) |
| deadman `stop` event | cause `deadman`, `latency_ms` 89 (laptop-side mirror) |

`stop_all` ends the heartbeat on purpose, so the on-car deadman trips afterwards and re-zeros a car
that is already still; `runtime.status()` then reads `deadman: tripped`, `armed: false`.

## 8. Pull the plug: deadman trip latency to PWM neutral

A raw 0.3 stream (20 Hz) and the 20 Hz heartbeat stopped in the same instant after 10 messages,
as a laptop that vanished mid-drive would.

| From the cut to | ms |
|---|---|
| deadman reports `tripped` (laptop) | 322.4 |
| first zero pair on `/ctrl_pkg/servo_msg` | 322.3 |
| throttle PWM at neutral (car sysfs) | **306.5** (raw 299.8 + one-way 6.7) |
| PWM held at 1 405 500 after the cut | yes, until the deadman's zeros: **no watchdog in the servo node** |

The deadman's own `gap_ms` read 890 at the moment the monitor was sampled (it had kept counting);
the trip fired at the 300 ms boundary plus one 20 ms tick.

## 9. Deadman through `rosbridge_action` alone

40 heartbeats at 20 Hz (2 s: a tripped deadman needs 1 s steady to re-arm), silence, echo 4 states.

| Row | Value |
|---|---|
| trips before / after | 4 / 5 |
| states echoed | `armed, tripped, tripped, tripped` |

## Test bugs fixed in this run

- `tests/conftest.py` applied the sim defaults (`DEEPRACER_ROSBRIDGE_PORT=9091`, `DEEPRACER_BODY=sim`)
  to the car layer, so every car test dialled `ws://<car>:9091` and burned 3 x 25 s on the handshake
  (161 s, all failed). The car layers (`-m wheels_off`, `-m pen`) now get body `car`, port 9090 and the
  console at `https://$DEEPRACER_HOST`.
- The deadman-only test could pass trivially from an already tripped state; it now checks the trip
  counter went up by one and sends 2 s of heartbeats so a tripped deadman re-arms first.
- The old hop test sampled PWM over a 20 Hz bash loop and inferred stop latency from the laptop clock;
  it is replaced by the 100 Hz car-side sampler with laptop marks.

## Product observations (not test bugs)

- 230-270 ms from a stop call to the zero pair is the `rosbridge_action` path (one process-wide lock,
  advertise, publish). A persistent zero publisher would cut it to tens of ms. Logged for the Car team.
- The stock LED service does not answer within 1 s but does act.
- `/i2c_pkg/battery_level` reads 11 (console API also 11) with the pack connected; the earlier `-1`
  was the monitor lead.

## 10. Evening re-measure after the persistent publisher and the deadman update (steering only)

Car back from a reboot at 192.168.0.2 (found by `DEEPRACER_HOST=auto`), `car/install.sh` loaded the
deadman with LED-green-on-arm and re-zero. Throttle was kept at 0 (no wheel motion; the operator had
not yet confirmed the stand; script `tests/car/steer_deadman_check.py`), so the steering servo carries the measurement: `manual_drive {angle 0.5,
throttle 0}` streamed 3 s at 20 Hz, heartbeat cut at 0.7 s, sampler on `pwm1` at 100 Hz.

| Quantity | Before (sections 4, 6) | Now |
|---|---|---|
| first publish -> PWM leaves rest | 442 ms (incl. `rosbridge_action` connect + advertise + 200 ms settle) | **47 ms** (raw 39.9 + one-way 7.4) |
| heartbeat cut -> deadman zero at the servo (PWM back to mid) | 307-322 ms | **257 ms** (raw 249.8 + 7.4) |
| PWM while the stream kept sending 0.5 after the trip | held the last value (no watchdog) | **alternates 1 575 000 / 1 450 000**: every non-zero `manual_drive` while tripped is re-zeroed |
| last stream message -> PWM at mid | | 327 ms (the relayed 0.5 and the deadman's zero race; the burst wins) |
| throttle PWM during the whole test | 1 446 000 only | 1 446 000 only |
| final steering PWM | | 1 450 000 (mid) |

Deadman journal: `deadman -> armed`, `deadman -> tripped` (gap 311 ms in the `--check-deadman`
run), then one `re-zeroing (n)` warning per non-zero message heard while tripped.

Open: after `car/install.sh` restarted the deadman while the stock stack kept running, the node's
`set_led_state` calls time out (1 s) although the same service answers rosbridge in 141 ms and the
node's topics (heartbeat in, zeros out) work. Before the restart (node from boot) the LED worked.
Consistent with the Foxy rmw_fastrtps behaviour where a service client started after its server
gets no responses until the server restarts. Fix: reboot the car after an install (everything
starts together), which also restored rosbridge's view of the graph this morning. The LED is a
stage cue; the zeros do not depend on it.

## 11. `make wheels-off` after the reboot, car on the stand, operator present (9 of 9)

Same suite as sections 1-9, same car, after the persistent publisher, the deadman update and a reboot.
`runs/wheels-off-2026-10-14/measurements.jsonl` holds the rows.

| From | To | Morning (ms) | Evening (ms) |
|---|---|---|---|
| `stop()` call | throttle PWM at neutral | **233.8** | **34.8** (raw 29.7 + one-way 5.1) |
| `stop()` call | `stop()` returns | 259.3 | 29.8 |
| `stop_all()` (barge-in) | throttle PWM at neutral | **266.4** | **22.4** (raw 19.5 + 2.9) |
| `stop_all()` call | `stop_all()` returns | 257.2 | 1.0 |
| heartbeat cut | deadman `tripped` on the state topic | 322.4 | 293.6 |
| heartbeat cut | throttle PWM at neutral (deadman's zeros) | 306.5 | **278.3** (raw 274.8 + 3.5) |
| hop command (`rosbridge_action`, not the transport) | PWM leaves neutral | 442 | 325.4 (still pays the 200 ms settle: this test publishes through upstream's action on purpose, as the reference) |
| hop trailing zero (`rosbridge_action`) | PWM at neutral | 352 | 225.2 |

The two product paths (operator stop, barge-in) are now an order of magnitude under the morning's
numbers, and under the 300 ms deadman gap, so the laptop's own stop lands before the deadman would
have to act. The deadman itself is unchanged in principle (300 ms gap + one message); its 278 ms
includes the 20 Hz heartbeat phase. The hop rows go through `rosbridge_action` directly as the upstream
reference and keep its settle; the driver does not use that path any more.
