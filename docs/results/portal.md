# Pit Wall evidence (2026-10-14)

The portal had never been seen rendered before this pass. Everything below was produced by
`portal/evidence/capture.py` in headless Chromium at 1920x1080 and lives under
`docs/results/portal/` (fake runtime) and `docs/results/beats-sim-portal-2026-10-14/` (real
runtime, live beats). No real people appear: the live view and the audit thumbnails are the QA
harness's drawn frames (`harness/frames/*.jpg`, a stick figure, a box, lane lines). Physics stops
the car; the decider explains; these pictures are how the explanation looks on a screen.

Reproduce in one command: `make evidence` (installs the `evidence` extra and Chromium, starts its
own fake stack on the override ports 9191 / 8190 / 8192 / 8211 and the portal on 8865, writes nine
PNGs and `pitwall-sim.webm`). Nothing it starts outlives the command.

## docs/results/portal/ (fake runtime, `PORTAL_FAKE_RUNTIME=1`)

| File | What it shows | WS op that produced it |
|---|---|---|
| `01-main-idle.png` | Main view on connect: IDLE verdict, LED off, live view from the fake console, empty audit, pre-flight not run, STOP ALL ready. | none (snapshot on connect) |
| `02-main-preflight-go.png` | Pre-flight panel: GO with the run time, eight checks green (battery, camera fps, link RTT, mode 0 manual, enabled, deadman armed, decider latency, calibration), LED green. | `{"op":"preflight"}` |
| `03-main-clear-hop-moving.png` | A clear hop while it moves: Proceed / path clear, heartbeat armed, `motion start` card, command card `drive_deepracer(linear=0.3, duration=0.67)`. | `{"op":"command","text":"go forward 20 cm"}` |
| `04-main-person-deny.png` | Person in frame: DENY in red, class `person_in_frame`, p = 0.97, LED red, `stop · deny` with its latency, the thought "I stopped because the decider said...", the stick-figure frame on the live view and in the verdict thumbnail. | fake console `/control?label=person_in_frame`, then `command` "go forward, there is a person ahead" |
| `05-main-confirm-pending.png` | Outside the envelope: CONFIRM in blue, the pulsing "Confirm needed" row with Approve / Deny in the Command panel, pending `req-0003`. | `command` "go fast for 3 seconds" |
| `06-main-approved-moving.png` | After Approve: `approval approved by operator`, frame verdict Proceed, `motion start` for 3 s, LED green. | `{"op":"approve","request_id":"req-0003","approved":true}` |
| `07-main-stop-all.png` | STOP ALL during that motion: `stop · operator 219 ms`, `motion end` after 0.5 s / 10 msgs, LED amber. | `{"op":"stop_all"}` |
| `08-kiosk-simon-guide.png` | `/?kiosk=simon`: an attendee typed "go forward past the box" in the kiosk's own box; the gate answered GUIDE (obstacle near, p = 0.81, speed halved), the box frame on the live view. | the kiosk form (Enter) -> `command` with `beat: "simon"` |
| `09-kiosk-judge.png` | `/?kiosk=judge`: live view large, class and probability chips, verdict with thumbnails, frame cards. | none (snapshot) |
| `pitwall-sim.webm` | 1280x720 recording of the whole main-view sequence above (about 20 s, 1.4 MB). | all of the above |

`manifest.json` holds the same captions with the byte sizes. All PNGs are under 310 KB.

## docs/results/beats-sim-portal-2026-10-14/ (real runtime, live beats)

Stack: `python -m harness.stack` and the portal **without** the fake runtime (`GET /api/state`
said `runtime: deepracer_agent`), both on the override ports, `DEEPRACER_BODY=sim`,
`AWS_PROFILE=heisenberg`, `AWS_DEFAULT_REGION=us-east-1`, and the headless pre-grant
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state` (the audit shows it as
`approval by pregrant`). Then `python -m beats all --body sim` with `PORTAL_URL` pointing at that
portal, while `capture.py watch` sat on the WebSocket.

Outcome: **7/7 PASS** (`beats.log`): preflight 1361 ms, marshal hop verdicts 1-4 ms, apology used
`why_stopped`, blindfold, sign, red light barge-in to stop 263 ms, pull the plug cut to tripped
314 ms. `events.jsonl` is the run's 249 events (plus the portal's own `body` event); the model
was Nova Pro through Bedrock.

| File | What it shows |
|---|---|
| `01-beats-marshal-deny.png` | Live: the Marshal beat's Deny from the real gate and fake decider, `stop · deny 1 ms`, the frozen frame in the verdict and frame cards. From the single-beat rerun (see below); the full run's version had the old Thought layout. |
| `02-beats-apology.png` | The Apology answer in the Thought panel ("I stopped because my decider saw a person in the frame at 97 percent..."), replayed from `events-rerun-marshal-apology.jsonl` up to seq 85 with `capture.py replay`. The live watcher could not photograph it: see "last events of a process" below. |
| `03-beats-final-audit.png` | Live: the audit panel alone after all seven beats. |
| `04-beats-final-main.png` | Live: the whole screen after Pull the Plug: `stop · deadman 329 ms`, the thought "link lost: no heartbeat leaving the laptop", the BARGE-IN marker from Red Light. Taken with the build before the Thought and Voice fixes below. |

`beats-rerun-marshal-apology.log` and `events-rerun-marshal-apology.jsonl` are the second,
two-beat run (marshal + apology, both PASS) used for 01 and 02. `portal.log`, `stack.log` and
`watch.log` are the services' logs from the full run.

## Rendering bugs found and fixed (portal/frontend, dist rebuilt)

1. **Panels did not fill their grid cells.** The grid wrappers were plain blocks, so every panel
   collapsed to its content height: the audit list ran over the pre-flight panel and the pre-flight
   GO badge fell below the footer. Wrappers are now flex columns and the panel stretches.
2. **Live view never worked against the fake console** (backend, `portal/backend/console.py`):
   `login()` skipped the CSRF login when the password was empty, but the fake console (like the
   real one) answers 401 on the MJPEG route until a session exists. The login now always runs and a
   401/403 mid-stream triggers one re-login.
3. **Pre-flight overflow**: eight table rows plus GO did not fit the bottom row at 1080p. Now a
   two-column grid with GO (and the run time) on top; decider `n/a` is neutral, not red, since the
   runtime decides go/no-go.
4. **Idle verdict** rendered as a grey bar (an em dash at 96 px, weight 900); it now reads IDLE.
5. **Live-view chips showed the envelope verdict's probability** (0.23) with no class; the chips
   now follow the latest frame-stage verdict.
6. **Thought clipping**: the real agent's thoughts are paragraphs, not one line; the panel showed
   the middle of the text. Now three lines with an ellipsis.
7. **Kiosk verdict** was the same size as on the main view with half the screen empty; kiosks get
   the big variant (up to 170 px).
8. **Voice barge-in time**: Red Light emits `t_ms` as an epoch stamp (1791959994377); the panel
   showed "at 1791959994377 ms". An epoch-sized value is now shown as clock time.

## Known UI issues left

- `thought` events from the real runtime are full paragraphs (`<thinking> ...`), against the
  "one line" contract; the panel clamps, but the source (Car / Intelligence) should emit one line.
- The real runtime on `sim` emits no `led` events, so the LED badge stays OFF during a Deny; the
  fake runtime shows red. Owner: Car.
- `preflight` on `sim` from the real runtime leaves `mode`, `enabled` and `decider_latency_ms`
  null (shown `n/a`) while saying GO.
- Red Light's `voice.barge_in.t_ms` is an epoch stamp, not "ms since PTT down" (CONTRACTS §4).
  Owner: Intelligence.
- The beats' EventLog uses its own session id (`s-20261014-0639`) inside the portal's run dir, so
  `frame_ref` thumbnails resolve only because the audit tries the portal's session first.
- **Last events of a process can miss the portal**: the EventLog posts from a daemon thread, and a
  beat that exits right after its final `say` (seq 86-87 of the rerun) is written to
  `events.jsonl` but never reaches `POST /api/events`. `watch` therefore cannot photograph the last
  line of a single beat; `replay` exists for that. Owner: Car (`events.py` should flush on close).
- Audit timestamps and hints are 13 px: fine on the laptop, not meant for 5 m. The verdict
  (96-170 px), thought (26 px), reason (24 px) and STOP ALL are the 5 m elements.
- Not exercised here: the voice panel with a real microphone (headless has none) and the CAR body
  switch (sim only, by instruction).
