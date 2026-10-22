# Integration contracts (binding for all teams)

Written 2026-10-14. Every team codes against this file. Change it only by editing this file
first and telling the other teams (the KrewHQ handoff in `.krewhq/README.md` is optional
maintainer tooling; skip it if you do not have KrewHQ).
Architecture: `docs/context/12-architecture.md`. Beats: `docs/context/11-final-use-cases.md`.

## 0. Ground truth about the car (measured, not planned)

- Stock image: Ubuntu 20.04.1, ROS 2 **Foxy**, Python **3.8** on the car, `aws-deepracer-core`
  2.0.383.0. NOT the community Jazzy image. Anything that runs on the car must be Python 3.8
  compatible (`from __future__ import annotations`, no `match`, no `X | Y` at runtime, no
  `list[str]` at runtime outside annotations).
- rosbridge 1.3.1 on `ws://<car>:9090`, unit `deepracer-rosbridge.service`, rosapi present.
- Arming contract (proven): `/ctrl_pkg/vehicle_state` `deepracer_interfaces_pkg/srv/ActiveStateSrv`
  `{state: 0}` (0 manual, 1 autonomous, 2 calibration) then `/ctrl_pkg/enable_state`
  `deepracer_interfaces_pkg/srv/EnableStateSrv` `{is_active: true}`. Right after a stack restart
  the first service call can time out; retry up to 3 times, 25 s each.
- Drive command: publish `deepracer_interfaces_pkg/msg/ServoCtrlMsg {angle: float, throttle: float}`
  on `/webserver_pkg/manual_drive`, both in [-1, 1], at 20 Hz. The ctrl node relays to
  `/ctrl_pkg/servo_msg` only in mode 0 and enabled. The servo node writes PWM
  (`/sys/class/pwm/pwmchip0/pwm0` throttle, `pwm1` steering). Neutral throttle PWM 1446000 ns;
  throttle 0.3 produced 1405500 ns. Forward sign on the ROS path is UNVERIFIED until a
  wheels-on test; the driver exposes `THROTTLE_FORWARD_SIGN` (default +1) in
  `src/deepracer_agent/calibration.py`.
- There is **no watchdog** on the car: a stream that stops mid-value leaves the servo where it
  was. Every publisher ends with a zero pair in `finally`.
- Battery: `/i2c_pkg/battery_level` `deepracer_interfaces_pkg/srv/BatteryLevelSrv {}` -> `level`
  (-1 = pack not seen or too low; otherwise 0..10). Camera, stereo and LiDAR are currently
  `not_connected` (console `GET /api/get_sensor_status`); do not block on them in sim.
- Camera frames: MJPEG over the console `https://<car>/route?topic=/camera_pkg/display_mjpeg&width=480&height=360`
  after a CSRF login (`GET /login` -> `<meta name="csrf-token">`, `POST /login` with
  `X-CSRFToken` and form `password=`). Also `/api/get_battery_level`, `/api/get_sensor_status`,
  `/api/get_device_info`. The MJPEG parser from report 07 (SOI `FFD8` / EOI `FFD9` scan) is the
  reference implementation.
- LED: `/servo_pkg/set_led_state` `deepracer_interfaces_pkg/srv/SetLedCtrlSrv {red, green, blue}`
  (0..10000000 per channel). Car team verifies field names with `ros2 interface show` over SSH
  (read-only) and records them in `car/README.md`.
- Hazard: with no camera attached the stock `camera_node` floods logs and the Foxy launcher
  leaks memory to OOM in about an hour. `car/guard/` owns the mitigation.
- Credentials live only in `~/.config/deepracer/env` (`DEEPRACER_HOST`, `DEEPRACER_SSH_USER`,
  `DEEPRACER_SSH_PASSWORD`, `DEEPRACER_CONSOLE_PASSWORD`, `DEEPRACER_SSH_KEY`). Never copy
  values into the repo. `car/connect/car.sh ssh '<cmd>'` runs a remote command.

## 1. Repository layout and ownership

| Path | Team | Contents |
|---|---|---|
| `src/deepracer_agent/driver.py`, `transport.py`, `calibration.py`, `tools.py`, `runtime.py`, `events.py` | Car | laptop driver over rosbridge, heartbeat, tools, agent runtime, event log |
| `car/deadman/`, `car/guard/`, `car/README.md`, `car/install.sh`, `car/rollback.sh` | Car | on-car deadman node (rclpy, Foxy, py3.8), camera guard, systemd units, install over SSH |
| `src/deepracer_agent/gate.py`, `decider_client.py`, `look.py`, `voice.py`, `prompts/` | Intelligence | decider intervention gate, decider HTTP client + fake, VLM look tool, bidi voice agent |
| `beats/` | Intelligence | seven beat scripts runnable with `--body sim` or `--body car` |
| `portal/` | Portal | FastAPI + WebSocket backend, React/Vite frontend, built `dist/` committed |
| `harness/` | QA | fake car (rosbridge protocol server), fake console (MJPEG + API), fake decider, fixtures |
| `tests/` | QA owns `tests/sim/` and `conftest.py`; each team adds `tests/unit/test_<module>.py` for its own modules | pytest |
| `.krewhq/`, `scripts/` | Lead | team map, handoff templates, session scripts (optional maintainer tooling) |
| `pyproject.toml`, `Makefile` | Lead | add your deps by editing `pyproject.toml` in your own section comment; do not reorder |

Teams only write inside their paths plus their own `tests/unit/test_*.py`. Shared code goes
through the Lead (edit this file first).

## 2. Python environment

Project venv at `.venv` (Python 3.12), created by the Lead with the upstream worktree installed
editable (`strands-robots` with the manual-mode fix). Use `.venv/bin/python` and
`.venv/bin/pytest`. Add a dependency: `uv pip install --python .venv/bin/python <pkg>` AND add
it to `pyproject.toml`. Code against `strands.bidi` (never `strands.experimental.bidi`),
`strands.interventions` (`InterventionHandler`, `Proceed`, `Guide`, `Confirm`, `Deny`),
`strands.hooks` (`BeforeToolCallEvent`). Lint with `.venv/bin/ruff check` and `ruff format`.

## 3. Names, ports, env

| Name | Value | Override (second stack on one laptop) |
|---|---|---|
| `DEEPRACER_BODY` | `sim` (default) or `car` | |
| `DEEPRACER_HOST` | car IP or `auto` (from `~/.config/deepracer/env`); sim: `127.0.0.1`. On `car`, `auto`/empty/stale is resolved by `deepracer_agent.discover` and `car/connect/find-car.sh` from `DEEPRACER_MAC` (the car's Wi-Fi MAC) and `DEEPRACER_MDNS` (hostname.local); the answer is written back to the environment. `docs/dev/networking.md` | |
| `DEEPRACER_ROSBRIDGE_PORT` | 9090 on the car; **9091** for the fake car | `9191` (`harness.stack` reads it for the fake car) |
| `DEEPRACER_CONSOLE_URL` | `https://<car>` on the car; `http://127.0.0.1:8090` for the fake console | `http://127.0.0.1:8190` (`harness.stack` takes the port) |
| `DEEPRACER_SIM_CONTROL_URL` | `http://127.0.0.1:8092` fake car control (beats `SimControl`) | `http://127.0.0.1:8192` (`harness.stack` takes the port) |
| `DECIDER_URL` | `http://127.0.0.1:8111` (strands-decider `serve`, or the fake decider) | `http://127.0.0.1:8211` (`harness.stack` takes the port) |
| `PORTAL_URL` | `http://127.0.0.1:8765` | `http://127.0.0.1:8865` (`portal.evidence` default) |
| `DEEPRACER_SIM_SHARED` | `runs/sim/shared.json` (label, battery, calibration shared by the three fakes) | any path; one per stack |
| `DEEPRACER_RUN_DIR` | `runs/<session_id>/` (events.jsonl, frames/) default under repo `runs/` (gitignored) | |
| `STRANDS_ROS2_COMMAND_ALLOW` | pre-grant list for headless runs, e.g. `/manual_drive,/vehicle_state,/enable_state`; every doc that sets it says so | |
| `AWS_PROFILE` | `heisenberg`, region `us-east-1` | |

The override column exists so a second fake stack (for example `make evidence`, or a second
agent's rehearsal) can run next to the contract-port stack; defaults never change. `python -m
harness.stack` reads the four port overrides from the same variables its clients use.

ROS names used by the project (new ones are under `/deepracer_agent/`):

| Name | Type | Direction | Notes |
|---|---|---|---|
| `/webserver_pkg/manual_drive` | `deepracer_interfaces_pkg/msg/ServoCtrlMsg` | laptop -> car | 20 Hz while driving, zero pair at end |
| `/deepracer_agent/heartbeat` | `std_msgs/msg/Header` | laptop -> car | `stamp` = laptop time, `frame_id` = session id; 20 Hz while a drive is active, 10 Hz idle while a session is armed (100 ms; 5 Hz tripped the 300 ms deadman over booth Wi-Fi) |
| `/deepracer_agent/deadman_state` | `std_msgs/msg/String` | car -> laptop | JSON `{"state": "idle|armed|tripped", "gap_ms": int, "since": iso8601, "trips": int}` published at 2 Hz and on change |
| `/ctrl_pkg/servo_msg` | `ServoCtrlMsg` | deadman -> servo node | the deadman writes zeros here AND on `/webserver_pkg/manual_drive`, 10 messages at 20 Hz, when it trips |

Deadman rule: once a heartbeat has been seen (state `armed`, LED green), a gap longer than
**300 ms** trips it. Tripped is latched until heartbeats resume for 1 s, then back to `armed`
(LED green). While tripped, every non-zero `/webserver_pkg/manual_drive` the node hears restarts
the zero burst (zero pairs are ignored, so the node never answers its own zeros). Idle (no
heartbeat yet, or none for 30 s) does nothing and turns the LED off. On trip it sets the LED red
via `/servo_pkg/set_led_state` (best effort, 1 s timeout, never blocks the zero publish).

## 4. Event schema (the one screen contract)

Every component that does something observable appends one JSON object per line to
`${DEEPRACER_RUN_DIR}/events.jsonl` through `deepracer_agent.events.EventLog` and, when
`PORTAL_URL` is reachable, POSTs the same object to `POST ${PORTAL_URL}/api/events` (fire and
forget, 0.5 s timeout, never raises). The portal rebroadcasts every event on `WS /ws`.

```json
{"ts": "2026-10-14T06:52:01.123Z", "seq": 42, "session": "s-20261014-0652", "beat": "marshal",
 "type": "command", "source": "agent", "payload": {...}}
```

`type` and payload fields:

| type | payload |
|---|---|
| `thought` | `{"text": str}` one line of agent reasoning or the tool call in flight |
| `command` | `{"tool": "drive_deepracer", "args": {"linear": 0.3, "angular": 0.0, "duration": 0.5}, "request_id": str}` |
| `verdict` | `{"request_id", "stage": "envelope|frame", "action": "Proceed|Guide|Confirm|Deny", "reason": str, "class": str|null, "probability": float|null, "latency_ms": int, "frame_ref": str|null}` |
| `approval` | `{"request_id", "decision": "approved|denied|timeout", "by": "operator|pregrant"}` |
| `motion` | `{"request_id", "state": "start|end", "angle": float, "throttle": float, "duration_s": float, "messages": int}` |
| `stop` | `{"request_id"|null, "cause": "trailing_zero|operator|deny|barge_in|deadman|error", "latency_ms": int|null}` |
| `heartbeat` | `{"state": "idle|armed|tripped", "gap_ms": int}` (deadman_state mirror, at most 2 Hz) |
| `preflight` | `{"battery": int, "camera_fps": float|null, "link_rtt_ms": float|null, "mode": int|null, "enabled": bool|null, "deadman": str, "decider_latency_ms": int|null, "calibration": "ok|uninitialised|unknown", "pwm_outputs": "ok|disabled|unknown", "go": bool, "reasons": [str]}` |
| `frame` | `{"frame_ref": "frames/000123.jpg", "width": int, "height": int}` (ref is relative to run dir; frames of people never leave the run dir) |
| `voice` | `{"event": "ptt_down|ptt_up|transcript|speech_start|speech_end|barge_in", "text": str|null, "t_ms": int}`; `t_ms` is milliseconds since the last `ptt_down` (0 on the press itself; epoch ms only before any press, which the portal shows as clock time) |
| `led` | `{"red": int, "green": int, "blue": int, "label": "green|red|amber|off"}` |
| `body` | `{"active": "car|sim"}` (which body the runtime drives), or a twin pose sample `{"body": "twin", "x": m, "y": m, "yaw": rad, "v": m/s, "t_ms": epoch ms}` at most 10 Hz while the twin moves plus one when it stops (source `twin`) |
| `error` | `{"where": str, "message": str}` |

`frame_ref` paths are relative to the run dir; the portal serves them at
`GET /api/runs/{session}/frames/{name}`.

## 5. Runtime interface (Car team implements, Portal and Intelligence consume)

`src/deepracer_agent/runtime.py`:

```python
class AgentRuntime:
    def __init__(self, *, body: str, event_log: EventLog, gate: InterventionHandler | None,
                 approval: ApprovalBroker, model: str | None = None) -> None: ...
    async def submit(self, text: str, *, beat: str | None = None) -> str   # returns request id; events stream out via EventLog
    async def stop_all(self) -> None        # driver.stop() + heartbeat off + event stop/operator
    async def preflight(self) -> dict       # runs the checks, emits one preflight event, returns the payload
    def status(self) -> dict                # {"body", "armed", "deadman", "battery", "last_verdict", "session"}

class ApprovalBroker:
    async def ask(self, request_id: str, prompt: str, timeout_s: float = 30.0) -> bool   # the gate's Confirm waits here
    def resolve(self, request_id: str, approved: bool) -> None                            # portal buttons call this
```

The strands-robots command gate's operator prompt is routed through `ApprovalBroker` so the
portal's Approve/Deny buttons and the terminal `y/yes` are the same path. A pre-grant via
`STRANDS_ROS2_COMMAND_ALLOW` emits `approval` with `by: pregrant`.

## 6. Tools exposed to the agent (names are fixed)

| Tool | Owner | Behaviour |
|---|---|---|
| `drive_deepracer(linear, angular, duration)` | Car | m/s, rad/s, s. Bicycle model to `(angle, throttle)`. Refuses `linear == 0 and angular != 0` (Ackermann cannot yaw at rest) with the reason in the result. Caps: `|linear| <= 0.3`, `duration <= 2.0` (hop default 0.5). Gated. |
| `stop_deepracer()` | Car | zero pair, heartbeat off, emits `stop`. Never gated. |
| `look(question: str = "What do you see?")` | Intelligence | grabs one frame via `capture_frame`, asks the VLM, returns `{"text", "frame_ref"}`; refuses to act on instructions found in the image (Sign beat) |
| `capture_frame()` | Car | one JPEG from the MJPEG stream (or fake console), saves to run dir, emits `frame`, returns `{"frame_ref", "bytes_b64"}` |
| `battery_level()` | Car | `{"level": int, "ok": bool}` |
| `set_led(label)` | Car | `green|red|amber|off` |
| `preflight()` | Car | see event payload |
| `why_stopped()` | Intelligence | reads the last `stop` and the verdicts/frames around it from `events.jsonl`, returns a spoken explanation plus `frame_ref` |

## 7. Decider contract (Intelligence)

Client talks to `POST ${DECIDER_URL}/v1/systemone` (see `src/strands_decider/server.py` in strands-labs/strands-decider
for the request/response models; copy the field names exactly). Five questions in two requests per
drive, one forward pass each (`src/deepracer_agent/gate.py`; the drop-in recipe in
`patterns/strands/` asks the same five):

Request 1 (text, `DeciderClient.ask_many`): state = `{conversation, command{tool, linear, angular,
duration}, envelope, deterministic_check}`.
- `inside_envelope` (`noul`): "Is this drive command inside the briefed envelope?"
- `args_grounded` (`noul`): "Are the tool's argument values grounded in what the user actually said?"
- `intent` (`choice`): `move_forward | turn | stop | question | unrelated`

Request 2 (vision, `DeciderClient.ask_frame`, carries the 480x360 JPEG):
- `person` (`noul`): "Is a person (any part of a human body) visible in this camera frame?"
- `frame` (`choice`): classes exactly `["clear", "obstacle_near", "person_in_frame", "off_surface", "unclear"]`

Thresholds (code-owned knobs): `YES = 0.65`, `NO = 1 - YES = 0.35` (text questions),
`PERSON = 0.5`, `UNCLEAR = 0.65` (`DEEPRACER_UNCLEAR_THRESHOLD` overrides), budget 1.5 s per request.
`before_tool_call` renders the conversation from the agent's messages (newest 12 messages, newest
2000 characters); a `decide()` called without a conversation (the Simon Says kiosk, a plan step)
asks the envelope question and the frame pair only, because the grounding questions need the
user's words.

Decision table (rows are checked in this order; the first matching row is the action):

| # | Condition | Action | Reason string |
|---|---|---|---|
| 1 | decider unreachable, timeout (> 1.5 s), malformed answer (missing key, probability outside [0, 1] or NaN, unknown class) | `Deny` | "decider unavailable" (text request) / "vision unavailable" (frame request); on the car both requests say "vision unavailable" (the string the Apology beat and `why_stopped` read back) |
| 2 | no camera frame | `Deny` | "vision unavailable" |
| 3 | person >= 0.5, or frame class `person_in_frame` | `Deny` | "person in frame" |
| 4 | frame class `off_surface` | `Deny` | "off the surface" |
| 5 | frame class `unclear` with p >= 0.65 | `Deny` | "cannot see clearly" |
| 6 | intent `stop` with p >= 0.65 | `Deny` | "the user asked to stop" |
| 7 | deterministic envelope check fails (code, not the model) | drop-in: `Guide` "re-plan inside the envelope"; ON THE CAR: `Confirm` (the marshal's thumb: the operator may approve a bigger hop) | "outside envelope: <violations>" |
| 8 | `inside_envelope` < 0.35 | `Guide`: re-plan inside the envelope | "outside envelope per decider (p=...)" |
| 9 | `args_grounded` < 0.35 | `Guide`: ask the user for the values instead of inventing them | "arguments not grounded (p=...)" |
| 10 | intent `question` or `unrelated` with p >= 0.65 | `Guide`: answer the user instead of moving | "intent <x> (p=...)" |
| 11 | frame class `obstacle_near` | `Guide`: halve the speed and re-plan the hop | "obstacle_near (p=...)" |
| 12 | `inside_envelope` or `args_grounded` in [0.35, 0.65) | `Confirm`: ask the operator | "unclear: inside=... grounded=..." |
| 13 | otherwise | `Proceed` | "<class> (p=...)" / "inside envelope p=..., grounded p=..." |

Never fail open. Every decision emits one `verdict` event per request (stage `envelope` for the
text request, `frame` for the vision request) with latency. `FakeDecider` (in `harness/`) answers
from the fake console's current frame label so sim runs are deterministic; it answers the
grounding yes/no from the `deterministic_check` line and the intent choice with `move_forward` 0.6.

## 8. Fake car contract (QA)

`harness/fake_car.py` serves the rosbridge v2 protocol on `ws://127.0.0.1:9091`: ops
`advertise`, `unadvertise`, `publish`, `subscribe`, `unsubscribe`, `call_service`
(`service_response` with the request `id`), plus rosapi services `/rosapi/topics`,
`/rosapi/services`, `/rosapi/topic_type`, `/rosapi/service_type` because
`strands_robots.rosbridge.rosbridge_action` uses them. Semantics it must emulate: mode starts
at 0 and disabled; `manual_drive` is relayed to `/ctrl_pkg/servo_msg` only when mode == 0 and
enabled; values outside [-1, 1] are dropped; a stream that stops leaves the last value
(no watchdog); `/i2c_pkg/battery_level` answers from a configurable level; `set_led_state`
records the colour; the first service call after `restart()` fails once (times out) to mimic the
real car. It exposes an inspection API (`state()`, `last_servo()`, `servo_history()`) for tests
and an HTTP control endpoint on `http://127.0.0.1:8092` (`/state`, `/battery?level=`,
`/restart`, `/frame?label=`). `harness/fake_console.py` serves the MJPEG stream and the console
API on `http://127.0.0.1:8090` from `harness/frames/<label>.jpg`. `harness/fake_decider.py`
serves `/v1/systemone` on 8111 using the fake console's current label.

- `connect` events (2026-10-17): the portal's car-connect workflow reports each step as `connect {step, status: running|ok|fail|skip, detail}` (steps usb, configured, discover, rosbridge, tunnel, handshake, console, runtime). Source `portal`. `led.label` also accepts `blue`.

## 8a. Decisions log (ambiguities resolved during the build, 2026-10-14)

- Throttle scaling: `Calibration.throttle_at_max_speed = 0.3`; `linear = 0.3 m/s` (the cap) sends
  servo throttle 0.3, the proven hop value. Upstream's 1.0 at max speed is never reachable.
- `drive_deepracer` without `duration` drives one hop (0.5 s), never latch-until-stop.
- `stop_deepracer` zeros and drops the heartbeat to idle (deadman stays armed); only `close()` or
  STOP ALL ends the heartbeat. Pull the Plug is the only beat that should show `tripped`.
- Pre-grant audit: the driver emits `approval {by: pregrant}` per motion when
  `STRANDS_ROS2_COMMAND_ALLOW` covers `/manual_drive`; operator decisions come from the runtime.
- Preflight `mode`/`enabled` come from the driver (no stock getter); `deadman: unknown` is a no-go
  on both bodies; missing camera/calibration are no-go on `car`, notes on `sim`.
- `battery_level.ok` is `level >= 1`.
- EventLog posts with header `X-Deepracer-Source: eventlog`; the portal persists only events that
  lack the header and `seq`. In-process runtimes use the portal's `InProcessPoster`.
- Events file: `DEEPRACER_RUN_DIR.parent / <session> / events.jsonl`; portal session id = run dir name.
- Fake car boots mode 0 and disabled (report 02 says enabled; the fake follows §8). `vehicle_state`
  also disables and writes a zero pair, so the arming order is state then enable.
- Sim shared state: `runs/sim/shared.json` (label, battery, calibration), written by `/frame?label=`
  on 8092 and `/control?label=` on 8090 and 8111. Override with `DEEPRACER_SIM_SHARED`.
- Fake decider noul reads `command`/`envelope` keys from the gate's context; 0.95 inside, 0.05
  outside, 0.5 unparseable; `/control?noul=` overrides.
- Deadman burst is 10 zeros over 0.5 s; a stream that outlives it takes the servo back. Open
  improvement for the node: re-zero on every `manual_drive` while tripped.
- Service field names verified on the car: `SetLedCtrlSrv {red, green, blue} -> error`,
  `GetCalibrationSrv {cal_type} -> {max, mid, min, polarity, error}`, `BatteryLevelSrv {} -> level`.
- `rosbridge_action` holds one process-wide lock and caches one connection per host/port: never
  run an echo in parallel with a publish through it; persistent streams use a raw `roslibpy.Topic`.
- Stock nodes run as root; Foxy shared-memory transport does not cross users, so on-car nodes run
  as root under systemd.
- Idle heartbeat is 10 Hz: 2 Hz tripped the 300 ms deadman between beats and 5 Hz still tripped it
  four times over Wi-Fi during Red Light on the car (gaps 302-306 ms).
- EventLog resumes `seq` from an existing events.jsonl, so several processes appending to one run
  keep "events after seq N" unambiguous. `python -m beats all` shares one file.
- The gate emits `stop {cause: deny}` on every Deny so the Apology can read it back.
- Beats enable the fake car's deadman emulation in sim (`/deadman?enabled=true`); unit tests that
  rely on the no-watchdog latch keep it off.
- Rover model: `us.amazon.nova-pro-v1:0` by default (`DEEPRACER_MODEL_ID` overrides). The heisenberg
  account has no Anthropic model access today; Claude Haiku 5.5 is the preferred switch once enabled.
  Nova Pro needed three things to behave: an explicit "DRIVE DONE" tool result, the rule that seeing
  is the gate's job (never `look()` before a drive, never refuse on an old frame), and `capture_frame`
  returning a path, not pixels.
- Command streams are preemptible: `RosbridgeTransport.publish` streams on a persistent topic one
  message at a time and `abort_stream()` (called by `stop`) ends it. Through `rosbridge_action` a
  stop waited for the whole stream (2.8 s in Red Light); then 260-270 ms.
- Persistent publishers (2026-10-14, after the wheels-off run): `rosbridge_action` sleeps 200 ms
  after every `advertise` so DDS can match the new publisher, and the stop's zero pair paid that
  every time (230 of the 234 ms measured). `RosbridgeTransport` now keeps one advertised publisher
  per topic for its lifetime (`warm()` after the handshake, `close()` from the runtime); every
  count, including the single zero pair, rides it. A publisher whose socket died is reopened once,
  only before its first message. Expected stop-to-neutral on the car: tens of ms; **re-measure
  with `make wheels-off`** (section 6 of the wheels-off record is the pre-change number).
- `look()` falls back to the frame `capture_frame` saved within the last 3 s; console grabs are
  serialised with one retry.
- Decider warm-up (2026-10-15): a freshly loaded decider on Apple MPS takes about 2 s for its first
  forward pass. The gate's 1.5 s budget gives up on it, and the next ask lands while the cold one is
  still encoding; two concurrent encodes abort the server (Metal `A command encoder is already
  encoding to this command buffer`, exit 134). `DeciderClient.warm()` sends one ask with a 120 s
  budget and a 1x1 JPEG; the beats runner calls it once before building the gate, and any other
  caller of a fresh server must do the same. Never retry a timed-out ask while it may still be
  running on the server.
- Beat step timeout is 60 s (Bedrock first-token latency reached 16 s); the beats runner closes each
  runtime so its heartbeat does not keep the fake deadman armed for the next beat.
- Rehearsal record 2026-10-14: `python -m beats all --body sim` 7/7 with the live model; barge-in to
  stop 266 ms, heartbeat cut to deadman trip 267-312 ms in sim.
- Browser voice: the portal delivers 16 kHz PCM to the runtime; the bidi agent needs a PCM input
  (not PortAudio). Owner: Intelligence.
- PWM outputs (car, 2026-10-14): after boot the stock servo node exports `pwmchip0/pwm0` (throttle)
  and `pwm1` (steering) and writes period/duty but never `enable`; with `enable=0` the ESC and the
  steering servo get no pulses, so a correct `/ctrl_pkg/servo_msg` moves the duty file and nothing
  else. `car/pwm/deepracer-pwm-enable.service` (oneshot, After=deepracer-core, waits up to 60 s for
  both channels, writes 1) fixes it; `preflight` reads the two flags over SSH on `car` and reports
  `pwm_outputs: ok|disabled|unknown` (anything but `ok` is a no-go on `car`; the sim reports
  `unknown` without a reason). Owner: Car.
- Deadman LED: GREEN on arm (first heartbeat, the stage "go"), red on trip, green on re-arm, OFF
  on the 30 s idle transition (`ACTION_LED_OFF`, `{red:0, green:0, blue:0}`). The red tail LED
  seen on an unattended car was the trip indicator left on; it is now cleared when the deadman
  goes idle.
- Deadman re-zero (2026-10-14): the node subscribes to `/webserver_pkg/manual_drive`; while
  tripped, a non-zero command restarts the ten-zero burst (`DeadmanLogic.on_manual_drive`,
  `rezeros` counter in the node log, not in `deadman_state`). Zero pairs never count. Needs
  `car/install.sh` to load on the car.
- `thought.text` is one line (`events.one_line`, whitespace collapsed, 600 chars max); the
  portal's Thought panel shows the latest one whole.
- `car/install.sh` restarts only `deepracer-deadman.service` (so new node code loads); it never
  restarts `deepracer-core`.
- Kiosks (2026-10-14, Portal+Intelligence): no new event types. A Frame Judge judgement is one
  `verdict` (beat `kiosk-judge`, stage `frame`, source `kiosk`) whose payload carries the contract
  fields plus `nickname`, `expected`, `labels`, `consent`, `probabilities`; the leaderboard is rebuilt
  from those lines on restart. A frame is written (`frames/kiosk-judge-*.jpg` + a `frame` event) only
  with `consent: true`; otherwise the bytes are judged in memory and dropped. Simon Says runs the real
  `DeciderGate.decide` (beat `kiosk-simon`), never `before_tool_call`, so a Deny emits no `stop`:
  nothing is driving. The judge's decider timeout is 5 s (not gating motion); the Simon gate keeps
  1.5 s. The Box egress log is built from what the gate already measured (console grab ms via
  `TimedFrameSource`, per-stage decider `latency_ms`, hosts from the client URLs); Simon Says calls
  no model, and the panel says so. The judge's `action` is the gate table applied to the frame
  (Deny for a person or an unreadable frame, Guide for an obstacle), an explanation, not a stop.
- Two Bodies (2026-10-14, recorded beat): `deepracer_agent.twin.TwinTransport` is a **pure kinematic**
  bicycle twin (not MuJoCo; `import mujoco` fails in `.venv` and a renderer-free twin is deterministic in
  tests) that answers the DeepRacer graph on the upstream `Transport` + `ServiceCapable` seam:
  `manual_drive` relayed only in mode 0 and enabled, `vehicle_state`/`enable_state`/`battery_level`/
  `get_calibration`/`set_led_state`, a `deadman_state` echo, **no watchdog** (the last pair holds and the
  twin keeps rolling), and the on-car `deadman_logic.py` imported by path (300 ms trip, re-zero, 1 s
  resume). The twin **is** gated: it is a second command surface the same agent talks to, so it answers
  to the same `STRANDS_ROS2_COMMAND_ALLOW` and approval path as the car (upstream's MuJoCo twin skips the
  gate; this project does not). `beats/two_bodies.py` runs one `AgentRuntime` per body on one
  `events.jsonl`; the twin runtime writes through `BodyEventLog`, which adds `body: twin` to every
  payload (readers ignore unknown keys; events without the stamp belong to the `--body` runtime). It is
  registered in `RECORDED_BEAT_NAMES`, never in `BEAT_NAMES` or `python -m beats all`. The portal's
  `Twin` panel floats over the grid and appears only once a twin pose event has arrived; `ws.ts` reads
  `payload.active` only when it is `car` or `sim`.
- Frame question (2026-10-14 evening, `docs/results/decider-calibration-2026-10-14.md`): the booth
  model called a person at desk distance `unclear` 0.58-0.67 on 11/11 real frames (Deny right,
  class wrong, Apology spoke the wrong reason). The gate now sends two questions in one request over
  the same frame: the unchanged five-way `FRAME_QUESTION` and `PERSON_QUESTION` ("Is a person (any
  part of a human body) visible in this camera frame?"); P(yes) >= 0.5 makes the class
  `person_in_frame` at that probability, else the five-way stands (`gate.combine_frame_answers`,
  monotone toward Deny; `DeciderClient.ask_frame` carries both). Real frames: 10/11 `person_in_frame`
  0.95, 1/11 still `unclear` 0.62, Deny 11/11; +95 ms per hop (450 ms for both answers). **Rewording
  `FRAME_CLASS_DESCRIPTIONS` is not a free change:** every sharper wording tried pushed `unclear`
  under 0.5 on 4-6 of the 11 frames (fail-open); the strings are pinned by `tests/unit/test_gate.py`
  and any change re-runs `python -m deepracer_agent.calibrate_frames`. Threshold, class names and
  the decision table are unchanged. `bench_decider` still times the five-way alone; quote the
  frame-stage `verdict.latency_ms` instead.
- `tests/unit/test_fake_car.py`, `test_fake_console.py` and `test_fake_decider.py` bind the sim
  ports (9091, 8090, 8092, 8111): `make unit` cannot run while the booth decider holds 8111. Run the
  rest with `--ignore` for those three, or stop the decider first.
- Browser voice, resolved (2026-10-14, Intelligence): `deepracer_agent.voice_pcm.PcmInputStream` is the
  `strands.bidi` `InputStream` for every microphone-less path (portal, rehearsal). It takes 16 kHz mono
  16-bit PCM through `feed()`, hands the model 100 ms `AudioDelta` frames **only while push-to-talk is
  pressed**, flushes the partial tail on release, and streams paced silence between presses (Nova Sonic's
  end-pointer needs the silence after a word and the open audio content is what makes a "stop" over the
  rover's narration an `INTERRUPTED` barge-in). `down()`/`up()` write `voice ptt_down/ptt_up` and mark
  `gate.voice_clock`, so `t_ms` on every later voice stamp counts from the press. `VoiceAgent.run_pcm`
  runs it with the transcript and `BargeInStop`; `AudioSink` is the matching output (speaking flag,
  fan-out, WAV). Portal: `WS /ws/audio` carries binary PCM frames in (3200 bytes each, 64 KiB cap), the
  rover's PCM out, and `ptt` as text frames on the same socket so a press lands before its first frame;
  the JSON `audio` op on `/ws` stays. `RealRuntime` builds the Nova Sonic agent on the first press
  (`PORTAL_VOICE=0` off, `PORTAL_VOICE_IDLE_S` 300 s idle stop) and reports `voice` in `status()`.
  Measured with synthesized speech (`docs/results/voice-audio-2026-10-14.md`): press to
  `BidiBargeInEvent` 971 ms for a 0.53 s "stop", the hook fired half a second before the model's own
  `stop_deepracer`; `stop_all` ends the heartbeat so the deadman trips 315 ms after a barge-in stop.

## 9. Safety rules every team repeats in code

- Physics stops the car; the decider explains. Never present the gate as the safety layer.
- Zero pair in `finally`; a failed trailing stop is the drive's error, not a warning.
- Motion tools go through `strands_robots._command_gate.gate_command`; headless pre-grants are
  explicit and documented.
- Fail closed: no frame, no decider, no heartbeat -> no motion.
- Frames of people stay in the run dir and are never committed. `runs/` is gitignored.
- Calibration is read, never written, without the user's explicit approval.
