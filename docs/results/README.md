# Measured results

Every number the README, the article and the submission cite comes from a file in this
directory, with the command that produced it. Physics stops the car; the decider explains.
Each note is `<topic>-YYYY-MM-DD.md` with raw output in a sibling directory of the same name.

## Index

| File | Date | What it holds |
|---|---|---|
| [decider-benchmark-2026-10-14.md](decider-benchmark-2026-10-14.md) | 2026-10-14 | Four checkpoints on the booth laptop (M4 Pro): per-question p50/p95, memory, load time, 140/140 envelope answers with `deterministic_check` against 110/140 without, the seven drawn frames. Raw: `decider-benchmark-2026-10-14/` |
| [decider-calibration-2026-10-14.md](decider-calibration-2026-10-14.md) | 2026-10-14 | Why a person at desk distance read `unclear` 0.58-0.67 on eleven real frames, and the person yes/no that now catches 10 of 11 at 0.95 for about 95 ms more |
| [decider-text-questions-2026-10-22.md](decider-text-questions-2026-10-22.md) | 2026-10-22 | The three text questions on the real 2B: 462 / 498 ms p50 / p95 for one three-question request, 0 of 72 over budget; `args_grounded` grounded at or above 0.78 against invented at or below 0.63 (`YES = 0.65` kept, 0 confident errors); Nova Pro on the same question 69/72 at 797 / 4069 ms and about 0.13 USD per 1000 decisions. Raw: `decider-text-questions-2026-10-22/` |
| [wheels-off-2026-10-14.md](wheels-off-2026-10-14.md) | 2026-10-14 | Real car on a stand: the PWM-enable fix, stop and barge-in latency to PWM neutral (35 ms, 22 ms), deadman trip (278 ms), first publish (47 ms). Raw: `wheels-off-2026-10-14-measurements.jsonl`, `wheels-off-2026-10-14-samples/` |
| [voice-audio-2026-10-14.md](voice-audio-2026-10-14.md) | 2026-10-14 | Nova Sonic voice path with real audio, push-to-talk and the barge-in hook timings. Raw: `voice-audio-2026-10-14/` |
| [portal.md](portal.md) | 2026-10-14 | First rendered Pit Wall captures and what each view shows. Raw: `portal/` (captures, `pitwall-sim.webm`) |
| [filming-protocol.md](filming-protocol.md) | 2026-10-14 | What to film and capture for the showcase, and what is captured automatically |
| [five-use-cases-2026-10-15.md](five-use-cases-2026-10-15.md) | 2026-10-15 | One run of the five use cases on the current architecture |
| [beats-car-2026-10-14/README.md](beats-car-2026-10-14/README.md) | 2026-10-14 | Beats on the car, wheels off, camera not seen: the gate denied every drive with `vision unavailable` (fail closed) |
| [beats-car-2026-10-14-evening/README.md](beats-car-2026-10-14-evening/README.md) | 2026-10-14 | Seven beats on the car after the persistent publisher: 3 of 7 pass, and why the rest did not |
| [beats-car-2026-10-15-person-gate/README.md](beats-car-2026-10-15-person-gate/README.md) | 2026-10-15 | Marshal on the car with the person question in the gate: person denied in 456 ms, gate 681-727 ms per hop, no motion after a Deny |
| [beats-sim-fastpub-2026-10-14/README.md](beats-sim-fastpub-2026-10-14/README.md) | 2026-10-14 | Seven beats on the sim stack after the persistent-publisher change |
| [beats-sim-shapes-2026-10-14/README.md](beats-sim-shapes-2026-10-14/README.md) | 2026-10-14 | The Shapes booth beat on the sim stack |
| [beats-sim-two-bodies-2026-10-14/README.md](beats-sim-two-bodies-2026-10-14/README.md) | 2026-10-14 | Two Bodies on the sim stack: one line to the DeepRacer and the MuJoCo twin, one stop all |
| [kiosks-2026-10-14/README.md](kiosks-2026-10-14/README.md) | 2026-10-14 | Headless captures of the Frame Judge and Simon Says kiosks and the egress panel |
| [pit-stop-2026-10-14/README.md](pit-stop-2026-10-14/README.md) | 2026-10-14 | The race engineer over SSH under the Cedar leash: calibration review, refused write, review with memory |
| `beats-sim-portal-2026-10-14/` | 2026-10-14 | Raw only: Pit Wall captures and logs of the Marshal and Apology beats on the sim stack (`manifest.json`) |

The fake decider used by the sim runs is a script, not a model; sim verdicts prove the wiring,
and the model's own numbers are the benchmark and calibration notes.

## 2026-10-14 wheels-off session

One page on what the real DeepRacer did on 2026-10-14, on a stand, wheels off the ground.
Details: `wheels-off-2026-10-14.md` (every number, every command), `beats-car-2026-10-14/`
(events.jsonl and the pass/fail log of the beats that could run).

### What moved

- Steering sweep and a 0.3 throttle hop moved the wheels on the stand once the two PCA9685 PWM
  outputs were enabled. Root cause of the morning's "duty changes, nothing moves": the stock servo
  node writes `period` and `duty_cycle` to `/sys/class/pwm/pwmchip0/pwm0` (throttle) and `pwm1`
  (steering) but never writes `enable`. Durable fix installed: `deepracer-pwm-enable.service`
  (oneshot after `deepracer-core`, waits for the channels, writes 1, logs). Preflight now reports
  `pwm_outputs: ok|disabled|unknown` and refuses to go on anything but `ok`.
- Throttle +0.3 produces 1 405 500 ns against a 1 446 000 ns rest; steering +/-0.5 produces
  1 575 000 / 1 325 000 ns against 1 450 000 ns rest. Forward/left are still unverified: that
  needs wheels on the floor.

### Numbers (ms, laptop event to the car's PWM at neutral unless stated)

| Path | servo_msg zero | PWM neutral | Notes |
|---|---|---|---|
| `stop_deepracer()` during a 2 s 0.3 drive | 238 -> 71 | **234 -> 35** | driver path; evening: persistent publisher (wheels-off section 11) |
| `AgentRuntime.stop_all()` (barge-in) during a 2 s 0.3 drive | 253 -> 31 | **266 -> 22** | evening numbers after the persistent publisher |
| Pull the plug: heartbeat and stream die together | 322 -> 291 | **307 -> 278** | servo held 0.3 until the deadman's zeros: no watchdog in the stock node |
| Red Light beat on the car (model in the loop) | | 253 (barge-in to stop) | drive itself denied: no camera |
| Pull the Plug beat on the car | | 253 (cut to tripped), re-armed in 1335 | 10/10 pass criteria met except motion (no camera) |
| Steering stream, heartbeat cut (evening, persistent publisher, new deadman) | | **47** first publish to PWM (was 442); **257** cut to PWM at mid; re-zero while tripped observed | throttle held at 0, wheels-off section 10 |

Deadman: trip gap 317-318 ms; LED red on trip, green on re-arm, **off** when idle (30 s) - fixed
on 2026-10-14, the red tail LED seen on the bench was the trip indicator left on.

**Evening re-measure** (same day, after a reboot): the transport keeps one advertised publisher per
topic, so the stop's zero pair no longer pays `rosbridge_action`'s 200 ms advertise settle (230 of
the morning's 234 ms). The arrows in the table are morning -> evening, both wheels off on the stand
(`wheels-off-2026-10-14.md` section 11; sim rehearsal in `beats-sim-fastpub-2026-10-14/`). The deadman
gained LED green on first arm and re-zeroing of non-zero `manual_drive` while tripped (installed,
verified at the PWM: section 10).

### What was blocked that day

- **Camera.** The console reported `camera_status: not_connected`, the MJPEG stream yielded no
  frame, so the gate denied every drive with `vision unavailable` (fail closed, as designed). The
  camera was plugged in afterwards (`/dev/video0`, `/dev/video1` exist, `uvcvideo` loaded) but the
  running `camera_node` started before it; it needed `systemctl restart deepracer-core` then
  `systemctl restart deepracer-rosbridge`, run by hand (commands in `beats-car-2026-10-14/README.md`).
  Beats blocked on it: Marshal, Apology, Blindfold, Sign and the rolling half of Red Light.
  Preflight (no-go, explicit) and Pull the Plug passed. The 2026-10-15 run
  (`beats-car-2026-10-15-person-gate/`) has the camera.
- **Floor driving.** Direction sign, steering side and the 10-of-10 pen protocol need the floor.
- **Idle heartbeat margin.** On this Wi-Fi link the 5 Hz idle heartbeat tripped the deadman four
  times during a beat with no drive in flight (gaps 302-306 ms). Harmless on a still car, but the
  screen shows `tripped`; the Car team should consider 10 Hz idle (CONTRACTS section 3 change).
- **Stop path cost.** 230-270 ms of every stop was `rosbridge_action` (lock, advertise, publish);
  the persistent zero publisher landed the same evening and cut it to tens of ms.
