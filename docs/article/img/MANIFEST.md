# Article graphics manifest

Figures for "How I built an intelligent self-driving rover with every kind of Strands" (AWS Builder
Center). Dark Strands theme: background `#0b0b10`, text `#f2f2f7`, accents orange `#ff6b3d`, amber
`#ffb347`, violet `#7c5cff`, cyan `#3ddcff`, green `#3fb950`, red `#ff4d4f`; Inter and JetBrains
Mono with system fallbacks. Every PNG was verified to open with PIL on 2026-10-22; all are under the
size limits (cover 2 MB, others 4 MB). Hand-written SVG sources for the diagrams and the chart are
in `svg/` so a figure can be edited without redrawing it. The GIFs the article embeds live in
`docs/media/` (see `docs/media/MANIFEST.md`).

AWS product renders and logos are AWS marketing assets used for an AWS community talk and Builder
Center article; not licensed for reuse.

| File | Pixels | Bytes | Shows | Sources |
|---|---|---|---|---|
| `cover.png` | 1200×675 | 602,019 | Cover, no text: the official AWS DeepRacer product render over a dark Strands-coloured background (violet, orange and cyan glows), the Strands mark at left with a halo, and seven subtle "strand" bezier curves, one carrying a row of dots as the 20 Hz heartbeat. | `docs/talk/deck/assets/05/deepracer-car-official.png`, `docs/talk/deck/assets/logos/strands-mark.svg` |
| `fig-architecture.png` | 1600×900 | 290,761 | The idealised show architecture: Amazon Bedrock (Nova Pro, Nova Sonic) at the top; the laptop with the Strands Agents runtime and tools, DeciderGate, the local Strands Decider 2B, the strands-robots layer (MobileBaseRobot driver, command gate + audit, rosbridge transport, heartbeat + deadman monitor), the shared CameraStream, the Strands Box boundary with its egress policy, the Pit Wall portal and the operator; the travel router (one SSID, DHCP reservation) with four labelled flows (commands 20 Hz, heartbeat 20 Hz, MJPEG back, deadman state back); the DeepRacer with rosbridge_server :9090, ctrl_pkg → servo_pkg → PCA9685 PWM, the deadman node with the 300 ms rule in red (measured 278 ms), camera_node + web_video_server, the camera guard, and the physical stops. | `docs/context/12-architecture.md`, `docs/talk/deck/sections/05-deepracer-demo-close.html` ("How the demo is wired"), `src/deepracer_agent/` (runtime, gate, driver, camera, connect), `car/deadman/` |
| `fig-safety-ladder.png` | 1600×1000 | 209,169 | The six safety layers in order with their measured numbers: pen and hop cap (0.3 m/s, hop ≤ 2 s); strands-robots command gate (first publish → PWM 47 ms); on-car deadman (300 ms rule, 278 ms heartbeat cut → PWM neutral); STOP ALL / barge-in 22 ms and operator stop 35 ms (234 before the persistent publishers); decider gate 681–727 ms per hop, person denied in 456 ms (violet: explains, never the safety layer); the marshal's thumb. Red = physics or the car's own code. | `docs/results/wheels-off-2026-10-14.md` §10–11, `docs/results/beats-car-2026-10-15-person-gate/README.md`, `docs/context/12-architecture.md` |
| `fig-gate-flow.png` | 1600×900 | 246,237 | One hop through the DeciderGate: `drive_deepracer(linear, angular, duration)` → envelope question (noul, beside the deterministic check) → frame grab (no frame or > 1.5 s → Deny, fail closed) → person question + five-way class in one request → merge toward Deny (person p ≥ 0.5 overrides the five-way, most severe wins) → Proceed / Guide (half speed) / Confirm (operator) / Deny (stop + narrator line). Thresholds 0.5 and the unclear bar 0.65; the enforce / advisory / off modes; measured 225–252 / 429–475 / 681–727 ms. | `src/deepracer_agent/gate.py`, `docs/results/beats-car-2026-10-15-person-gate/README.md`, `docs/results/decider-calibration-2026-10-14.md` |
| `fig-portal-stage.png` | 1920×1080 | 279,069 | Real screenshot of the Pit Wall Stage view in SIM mode on the fake stack: the frozen frame the gate judged `person_in_frame` 0.97, the DENY verdict card, the stop card (cause deny, 92 ms), the rover's lines and the STOP ALL / HOLD TO TALK controls. Fake runtime (`portal/backend/fake_runtime.py`) because `strands_robots` is not installed in this `.venv`; events came from `preflight`, "go forward 20 cm", "what do you see" and "someone's foot is in front of you, go forward". | `portal/` on ports 8866 / 9191 / 8192 / 8190 / 8211 (never 8765 or 8111), Chrome headless 1920×1080 |
| `fig-portal-operator.png` | 1920×1080 | 308,453 | Real screenshot of the Operator view: pre-flight, maneuver shapes, talk, LED, metrics, gate mode (enforce / advisory / off), throttle calibration, body switch, a pending Confirm ("outside the briefed envelope") with Approve / Deny, STOP ALL, voice, event filter and the audit column with the Deny verdict and its frame thumbnail. | same session as the Stage view, after "go fast, sprint across the pen" |
| `fig-portal-settings.png` | 1920×1080 | 150,752 | Real screenshot of the Settings view: car connection (host 127.0.0.1, not connected), car address override (host / MAC / mDNS), car Wi-Fi USB-stick writer, decider URL (`http://127.0.0.1:8211`, the fake decider) and voice status. | same session |
| `fig-latency.png` | 1600×900 | 126,842 | Chart of the measured milliseconds in two panels on linear scales so 22 and 727 both read. Stop paths to PWM neutral: barge-in STOP ALL 22, operator stop 35 (ghost bar 234 before the persistent publishers), first publish to PWM 47, deadman cut to zero 278, with the 300 ms deadman rule as a reference line. Decider gate per hop: envelope 225–252, frame 429–475, person denied 456, whole gate 681–727 (ranges shown as a lighter extension). Palette `#f0582c` / `#7c5cff` validated with the dataviz skill's `validate_palette.js` against `#0b0b10` (all checks pass). | `docs/results/wheels-off-2026-10-14.md` §10–11, `docs/results/beats-car-2026-10-15-person-gate/README.md` |
| `fig-deadman-timeline.png` | 1600×700 | 108,631 | Timeline of the deadman rule on the car's clock: heartbeats at 20 Hz, the last one, the > 300 ms gap, the trip, ten zero servo pairs at 20 Hz (a 500 ms burst), the tripped latch with LED red, heartbeats resuming, a steady second then re-arm (LED green), and, after an axis break, idle with the LED off after 30 s of silence. Measured 278 ms cut → PWM neutral, 294 ms to `tripped`, Pull the Plug re-armed in 1.4 s. | `car/deadman/deepracer_deadman/deadman_logic.py`, `docs/results/wheels-off-2026-10-14.md` §11, `docs/results/beats-car-2026-10-15-person-gate/README.md` |
| `svg/*.svg` | — | 13–26 KB each | Hand-written SVG sources for `fig-architecture`, `fig-safety-ladder`, `fig-gate-flow`, `fig-latency`, `fig-deadman-timeline` (native shapes and text only; rasterised with Chrome headless at 1:1). | generated by the scripts in the session scratchpad `article-graphics/` |

## Not produced

- `fig-frozen-frame.png`: the corridor frame the gate judged "unclear 0.54" was expected at
  `<scratchpad>/last-frame.jpg`, but no such file exists anywhere under the session scratchpad,
  so the composition was skipped. Drop the JPEG in place and re-run; the Stage card style to copy
  is in `fig-portal-stage.png` (frame class / probability / frame verdict chips bottom-left).

## How the portal screenshots were taken

Fake stack on the override ports (`DEEPRACER_ROSBRIDGE_PORT=9191`, control `:8192`, console
`:8190`, decider `:8211`, `DEEPRACER_SIM_SHARED` in the scratchpad) and the portal on
`PORTAL_URL=http://127.0.0.1:8866` with `DEEPRACER_BODY=sim`, `AWS_PROFILE=heisenberg`,
`STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`. The `beats marshal`
run could not start (`deepracer_agent.runtime.AgentRuntime` needs `strands_robots`, which is not
installed in this `.venv`), so the portal's built-in fake runtime answered the commands over
`/ws`; the fake console served `harness/frames/person_in_frame.jpg` for the Deny. Chrome headless
`--window-size=1920,1080 --virtual-time-budget=8000`. The stack and the portal were stopped
afterwards; ports 8765 and 8111 were never touched.

| fig-deepracer.png | 1200x? official AWS DeepRacer product render (byte-identical to docs/talk/deck/assets/05/deepracer-car-official.png; source aws.amazon.com/deepracer) | the stock car, section 1 |
| event-speaker-with-car.jpg | 1200x1600 (from eventpics/IMG_2492 2.heic, the author's photo) | the speaker holding the car on stage, section 1 |
| event-car-on-stage.jpg | 1600x1150 (eventpics/IMG_2578.jpg) | the car on the AWS plinth, section 11 |
| event-hall.jpg | 1600x1200 (eventpics/5eba3277...jpg) | the hall watching the interventions slide, section 11 |
| fig-deepracer-strands.png | 1600x900 | the stock car with seven Strands callouts (camera: Decider; drive: strands-robots; servos: deadman; compute: Harness; loop: Agents; voice: Bidi; process: Box); source img/svg/fig-deepracer-strands.html over the official product render | section 1 |

| cover.png (v2) | 1200x675, no text | the stock car large on a perspective grid, lit cyan and orange, with three Strands ribbons flowing from the Strands mark into the car; source img/svg/cover.html; the first cover is kept as cover-v1.png |
| `cover.png` (v3, "Seen") | The car facing the viewer; a cyan beam from its camera sweeps the floor and turns red on a drawn figure. No text. 1200x675. | Made for this article from the official render and the Pit Wall stick figure; source `svg/cover-candidates/cover-B.html`. |
| `cover-v2.png` | Previous cover (car on a grid with Strands ribbons). | Kept for reference. |
| `cover-options/cover-judged.png`, `cover-options/cover-strands.png` | The two other v3 candidates. | Sources in `svg/cover-candidates/`. |
| `cover.png` (v3 final, "Judged") | The car lit from front and above, a red tail light, a floor-projected probability scale in red, cyan and green with ticks at 0.35 and 0.65 and a green marker in the proceed zone. No text. 1200x675. | Made for this article from the official render; source `svg/cover-candidates/gen_A2.py` and `cover-A2.html`. |
| `cover-options/cover-seen.png` | The "Seen" candidate, previously the cover. | Source `svg/cover-candidates/cover-B.html`. |
