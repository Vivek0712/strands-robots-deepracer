# The five use cases on the current architecture, 2026-10-15 (02:20-02:40 IST)

One run of everything the council verdict puts in front of an audience
(`docs/context/11-final-use-cases.md`): the seven-beat spine, the Frame Judge kiosk, the Simon
Says kiosk, Pit Stop and Two Bodies, on the code at this commit, against the sim stack and, where
the bench allows it, the real car wheels off. The phase each exercises is in
`docs/dev/phases.md`. Physics stops the car; the decider explains.

Setup: live vision decider `strands-decider-2B-qwen3.5-v1-2610` on `:8111` (warmed once), sim stack
on the override ports (`9191/8192/8190/8211`) so it could run beside it, live model
`us.amazon.nova-pro-v1:0`, car at 192.168.0.2 found by `DEEPRACER_HOST=auto`, headless pre-grant
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state` declared. The car's camera
looked at the operator at the desk the whole time, so every car hop that needed a clear pen was
denied by design.

| Use case | Sim | Car (wheels off, operator in frame) |
|---|---|---|
| 1 Spine, seven beats | 7/7 PASS: Pre-flight go 1.3 s; Marshal 2 hops then Deny `person_in_frame` 0.97; Apology names class and probability; Blindfold deny then finish; Sign read and refused; Red Light barge-in to stop 1 ms; Pull the Plug trip 296 ms, re-arm 1.6 s | Pre-flight PASS (go, 4.2 s); Marshal: three hops denied `person_in_frame` 0.95, gate 681-727 ms, no motion (the two "clear" hops cannot pass with a person in view); Apology PASS; Pull the Plug PASS (trip 272 ms, re-arm 1.4 s); Blindfold, Sign, Red Light wait for a clear pen |
| 2 Frame Judge kiosk | `tests/unit/test_kiosk.py` 44 passed; live `/kiosk/labels`, `/kiosk/judge` (clear 0.93, consent false so no frame kept), `/kiosk/leaderboard` on the portal at `:8865` | booth only (same code, decider on `:8111`) |
| 3 Simon Says kiosk | live `/kiosk/simon`: "Hop forward twenty centimetres" Proceed; "Drive forward at two metres per second for ten seconds" was **Proceed as a 0.3 m/s hop** before the fix and is now Confirm, "outside envelope: 2 > 0.3 m/s; duration 10 > 2 s", re-plan "forward at 0.3 m/s for 2 s" | booth only |
| 4 Pit Stop | `tests/unit/test_race_engineer.py` 20 passed | read-only run over SSH: calibration read, steering mid 1450000 against remembered 1456000, "offset of 6000", no write attempted (operator unconfirmed) |
| 5 Two Bodies | PASS 6/6: one line started both bodies in 2.7 s, "stop all" halted the fake car and the twin in 2 ms each, twin rolled 4.4 cm and froze | the car as the first body waits for a clear pen |

Suites on the same code: unit 815 passed, 1 skipped (run beside the live decider with
`DECIDER_URL=http://127.0.0.1:8311`); kiosk and decider-client files re-run after the fixes below.

## What the run changed

- `DeciderClient.warm()` and the beats runner's warm-up call: the first ask to the freshly loaded
  decider took 1978 ms, the gate's 1.5 s budget gave up, and the next ask crashed the server
  (Metal command-encoder assertion, exit 134). Record: `beats-car-2026-10-15-person-gate/`.
- Simon Says reads number words: `words_to_digits` in `beats/kiosk.py`, six parser cases in
  `tests/unit/test_kiosk.py`. Before the fix an over-envelope sentence in words was silently
  planned as a default hop and shown as Proceed.
- `tests/conftest.py` builds the session sim stack from the port overrides, so the unit suite runs
  beside a live decider instead of failing 54 tests on `8111`.

## Noise, not defects

- One sim Marshal run reported `vision unavailable` on hop 2 while a kiosk smoke was grabbing
  frames from the same fake console in the same second; the fake console answered five grabs at
  70 ms right after, and the re-run with the stack idle passed 5/5. A booth runs one consumer per
  camera; the portal's kiosk and a beat on the same fake console is a test-rig overlap.
- `ConnectionResetError` tracebacks in the fake console log are clients closing MJPEG streams.

## Still needs the car with a clear pen and the operator present

Marshal's two clear hops, Blindfold, Sign, Red Light on the car; the pen session (10 of 10 per
beat); the physical router yank; the Pit Stop confirmed write
(`DEEPRACER_OPERATOR_CONFIRMED=1`, operator at the keyboard); Two Bodies with the car as the first
body; the videos per `filming-protocol.md`.
