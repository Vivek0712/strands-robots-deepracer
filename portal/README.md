# Pit Wall portal

One screen for every beat, the same for the fake car and the real DeepRacer. FastAPI +
WebSocket backend (`portal/backend/`), React + Vite + TypeScript frontend (`portal/frontend/`,
built `dist/` committed so show day needs no Node). Big type, dark theme, readable from 5 m.

**Physics stops the car; the decider explains.** The pen, the hop cap, the on-car deadman and
the marshal's thumb stop the car. This portal shows why something happened and lets a human
approve, deny or press STOP ALL; it is never the safety layer. That line stays in the footer of
every layout and in `GET /api/state`; do not remove it.

## Run

```
make portal                      # .venv/bin/python -m portal.backend.app on PORTAL_URL (default :8765)
open http://127.0.0.1:8765/      # Pit Wall
make portal-build                # only when the frontend changed: npm ci && npm run build, commit dist/
```

Environment (CONTRACTS section 3): `PORTAL_URL` (port), `DEEPRACER_RUN_DIR` (`runs/<session>/`; the
portal's session id is the directory name, frames are served from its parent), `DEEPRACER_BODY`,
`DEEPRACER_CONSOLE_URL` (`http://127.0.0.1:8090` fake console, `https://<car>` real console),
`DEEPRACER_CONSOLE_PASSWORD` (read from `~/.config/deepracer/env` at run time, used for the console
CSRF login, never logged), `DECIDER_URL`. `PORTAL_FAKE_RUNTIME=1` forces the built-in fake agent.

Which agent answers the operator: `portal/backend/runtime_adapter.py` imports
`deepracer_agent.runtime` lazily and builds `AgentRuntime` + `ApprovalBroker` + `DeciderGate`
(+ `look`/`why_stopped`) exactly as `deepracer_agent.voice._load_runtime_pieces` does. When that
import fails, or `PORTAL_FAKE_RUNTIME=1`, `portal/backend/fake_runtime.py` plays the agent with
realistic event sequences driven by keywords in the command text ("person", "hand", "box", "fast",
"back", "20 cm", "2 s", "what do you see", "stop"). `GET /api/state` says which one is live
(`"runtime": "deepracer_agent" | "fake"`).

Same portal for sim and car: the body is a label on events and a switch in the header; events,
verdicts, approvals and stops have the same shape from both. Plan in sim first (fake car on 9091,
fake console on 8090, fake decider on 8111: `make fake-car fake-console fake-decider`), then
`DEEPRACER_BODY=car` with the real services in `~/.config/deepracer/env`.

## HTTP

| Route | Purpose |
|---|---|
| `POST /api/events` | Any CONTRACTS section 4 event. 202 with `{accepted, seq, persisted}`; 422 with `{accepted: false, reason}` for a malformed one (missing `type`, unknown `type`, missing or non-ISO `ts`, non-object `payload`, bad `seq`/`session`/`beat`/`source`). Rebroadcast to every WebSocket. Appended to `runs/<event.session>/events.jsonl` only when the sender did not already write it: header `X-Deepracer-Source: eventlog` or a present `seq` means an EventLog numbered and wrote it. |
| `GET /api/state` | session, run dir, body, runtime name and status, counts, latest event per type, pending approvals, the safety line |
| `GET /api/runs/{session}/frames/{name}` | JPEG from `runs/<session>/frames/`; refuses paths that escape the runs root |
| `GET /api/stream/mjpeg` | proxy of the console MJPEG (CSRF login server side); 502 when the console is down, the live view retries every 3 s |
| `GET /health` | `{ok, session, runtime, clients}` |
| `POST /kiosk/judge` | Frame Judge: `{nickname, consent?: bool, expected?: str, frame_b64?: str}`. Grabs one console frame (or takes the tablet's JPEG), asks the decider over the live label card, answers `{class, probability, latency_ms, probabilities, action, reason, wrong, fool_score, frame_saved, frame_ref, egress}`. The frame is written to `runs/<session>/frames/kiosk-judge-*.jpg` (plus a `frame` event) **only** when `consent` is true; otherwise it is judged in memory and dropped. One `verdict` event, beat `kiosk-judge`, per call. 422 with a reason for a bad body, 503 `vision unavailable` when the console gives no frame. |
| `GET` / `POST /kiosk/labels` | The presenter's label card: the five frame classes plus labels added live (`{label, description?}`; `{label, remove: true}` takes one off; never below two, at most 12). A new label is on the next question at once; nothing is retrained. Each change is one `thought` event. |
| `GET /kiosk/leaderboard` | Best fools: one row per nickname (its judgement with the highest `fool_score` = 1 for a wrong class + (1 - probability)), ranked, plus the last ten judgements. Rebuilt from `events.jsonl` on restart. |
| `POST /kiosk/simon` | Simon Says: `{text}` through `beats.kiosk.parse_command` and the real `DeciderGate` (`verdict` events, beat `kiosk-simon`); answers `{action, reason, card, class, probability, latency_ms, stages, replan, egress, egress_note}`. `replan` is the slower plan the gate implies (half speed on Guide, clipped to the envelope on Confirm). `egress` is the Box egress log: the console grab and the decider questions with host and ms, from what the gate measured; no model is called. `GET /kiosk/simon` returns the session history. |
| `GET /` | the built frontend; a placeholder page if `dist/` is missing |

## WebSocket `/ws`

Server to browser: `{"op":"snapshot","events":[last 200],"state":{...}}` on connect, then
`{"op":"event","event":{...}}` per event, `{"op":"ack","for":<op>,...}` or
`{"op":"error","for":<op>,"reason":...}` per operator op, `{"op":"pong"}` for `ping`.

Browser to server:

| op | fields | routed to |
|---|---|---|
| `command` | `text`, optional `beat` | `runtime.submit(text, beat=)`; ack carries `request_id` |
| `approve` | `request_id`, `approved: bool` | `ApprovalBroker.resolve`; same path as the terminal `y/yes` |
| `stop_all` | | `runtime.stop_all()`: zero pair, heartbeat off, `stop` event cause `operator` |
| `preflight` | | `runtime.preflight()`; one `preflight` event; ack carries `go` |
| `body` | `active: "car" \| "sim"` | body switch; `body` event |
| `ptt` | `state: "down" \| "up"` | voice PTT markers (`voice` events); PTT during motion is a barge-in stop in the fake |
| `audio` | `pcm_b64` (16 kHz mono int16, about 100 ms per frame, max 64 KiB) | the voice agent's audio feed; no ack per frame |
| `ping` | | `pong` |

## Panels (report 13 section 3)

Live view (MJPEG with frame class and probability overlaid), Thought (last line of reasoning or the
tool call in flight), Verdict (huge Proceed / Guide / Confirm / Deny with the reason, LED badge
mirroring `led` events), Audit (one card per command, verdict, approval, stop, motion, frame with
thumbnail), Command (text box, Approve/Deny that appear when a Confirm is pending, big red STOP
ALL), Voice (hold to talk: browser mic to 16 kHz PCM over the socket; transcript and barge-in
markers), Pre-flight (table with green/red cells and GO / NO GO), Body (SIM / CAR switch in the
header). Keyboard: hold **space** = push-to-talk (not while typing), **Escape** = STOP ALL. The
WebSocket reconnects with backoff and the snapshot rebuilds the screen.

## Kiosks (booth, all day)

Both pages are tablet-first (one column under 900 px, header and footer wrap under 700 px) and talk
to the `/kiosk/*` routes over HTTP; the WebSocket still carries their verdicts to the audit. They are
the decider explaining all day, never a safety claim: nothing on either page moves the car.

`/?kiosk=judge` Frame Judge (`panels/Judge.tsx`): live view, nickname, "I am holding" (a label from
the card, optional), the consent switch, JUDGE THIS FRAME. The card shows the class, probability,
decider latency in ms, what the gate's table would say about that frame, a probability bar per label,
and whether the frame was kept ("frame saved with consent: frames/..." or "judged in memory, not
saved"). The label card lets the presenter add a label live ("shoe"); the next question is asked over
the new list, no retraining. Best fools: wrong class first, then lowest probability, one row per
nickname, thumbnail only for consented frames.

`/?kiosk=simon` Simon Says (`panels/Simon.tsx`): a text box with example chips, the big
Proceed / Guide / Confirm / Deny card with class, probability and gate latency, the slower re-plan the
gate would take, the two stage chips, a history list and the Box egress log beside it (host and ms of
every outbound call the kiosk made for that answer: camera console grab, decider envelope question,
decider frame question; "no model call" is stated on the panel).

Evidence: `python -m portal.evidence.kiosks` (attach to a running portal on `PORTAL_URL`, or
`--stack` to start a fake stack and portal first) drives both pages through the UI and writes
`docs/results/kiosks-<date>/` (thirteen PNGs, `manifest.json`, `leaderboard.json`,
`simon-history.json`).

## Evidence (`make evidence`)

`portal/evidence/capture.py` is the headless visual QA: it starts its own fake stack and a portal
with `PORTAL_FAKE_RUNTIME=1` on the **override ports** below, opens the main view and both kiosks
in Chromium at 1920x1080, drives the fake agent through the WebSocket ops (`preflight`, `command`,
`approve`, `stop_all`) and writes nine optimised PNGs plus `pitwall-sim.webm` to
`docs/results/portal/` (what each one shows: `docs/results/portal.md`). `python -m
portal.evidence.capture watch` attaches to a running portal fed by `python -m beats all` and
screenshots the Marshal deny, the Apology and the final audit. Playwright is the optional
`evidence` extra (`uv pip install --python .venv/bin/python -e ".[evidence]"` then
`.venv/bin/python -m playwright install chromium`); `make evidence` does both and runs the capture.

| Variable | Contract default | Override used by `make evidence` |
|---|---|---|
| `PORTAL_URL` | `http://127.0.0.1:8765` | `http://127.0.0.1:8865` |
| `DEEPRACER_ROSBRIDGE_PORT` | `9091` (fake car) | `9191` |
| `DEEPRACER_SIM_CONTROL_URL` | `http://127.0.0.1:8092` | `http://127.0.0.1:8192` |
| `DEEPRACER_CONSOLE_URL` | `http://127.0.0.1:8090` | `http://127.0.0.1:8190` |
| `DECIDER_URL` | `http://127.0.0.1:8111` | `http://127.0.0.1:8211` |
| `DEEPRACER_SIM_SHARED` | `runs/sim/shared.json` | `runs/portal-evidence-<stamp>/shared.json` |

The defaults never change; the overrides exist so the evidence run (or a second rehearsal) can
sit next to a stack that already holds the contract ports. `python -m harness.stack` reads the
same four variables, so `DEEPRACER_ROSBRIDGE_PORT=9191 DEEPRACER_CONSOLE_URL=http://127.0.0.1:8190
DEEPRACER_SIM_CONTROL_URL=http://127.0.0.1:8192 DECIDER_URL=http://127.0.0.1:8211 .venv/bin/python
-m harness.stack` starts a second fake garage. Set the same variables (plus `PORTAL_URL`,
`DEEPRACER_RUN_DIR`, `AWS_PROFILE=heisenberg`, `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`,
a headless pre-grant that the audit records as `approval by pregrant`) on the portal and on
`python -m beats all --body sim` and the Pit Wall shows the live run.

## Tests

`.venv/bin/pytest -q tests/unit/test_portal_backend.py tests/unit/test_kiosk.py` (TestClient, recorder
runtime, tmp run dir, refusal tables; the kiosk tests prove no frame is written without consent).
`.venv/bin/ruff check portal/backend portal/evidence`.
