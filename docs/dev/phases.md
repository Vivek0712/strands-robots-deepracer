# The five phases, rewritten on the architecture we have

The earlier `strands-agentic-deepracer` repo grew in phases (planner, AgentTool, closed-loop
vision; report 07). This repo kept the idea and changed the content: every phase below is a layer
of the one spine in `docs/context/12-architecture.md`, named by what it adds and by the test that
proves it. Physics stops the car; the decider explains. The phases are cumulative: phase N runs
with phases 1..N-1 unchanged.

| Phase | Adds | Where it lives | Proof |
|---|---|---|---|
| 1 Body | the car as a gated `MobileBaseRobot`: rosbridge transport with persistent publishers, manual-mode arming, heartbeat, the on-car deadman, pre-flight | `src/deepracer_agent/{transport,driver,discover,tools}.py`, `car/deadman`, `car/connect` | `make unit`, `make wheels-off` (9/9), beats Pre-flight and Pull the Plug |
| 2 Gate | authority by construction: the upstream command gate and pre-grant audit, the decider gate (envelope yes/no, person yes/no plus five-way class on the frame), Proceed/Guide/Confirm/Deny, the operator broker, the event log and `why_stopped` | `src/deepracer_agent/{gate,decider_client,runtime,events,look}.py` | `tests/unit/test_gate.py`, beats Marshal, Apology, Blindfold |
| 3 Senses | the camera as evidence, never as instruction: MJPEG grab, VLM `look`, sign reading refused by construction, shape plans validated against the pen, the two booth kiosks | `src/deepracer_agent/{plans,calibrate_frames}.py`, `beats/{sign,kiosk,shapes}.py`, `portal/backend/kiosk.py` | beats Sign and Shapes, `tests/unit/test_kiosk.py`, live `/kiosk/*` smoke |
| 4 Voice | push-to-talk Nova Sonic through `strands.bidi`, the barge-in that stops the wheels, real PCM in and out, browser audio over `/ws/audio` | `src/deepracer_agent/{voice,voice_pcm,voice_rehearsal}.py`, `portal/backend/app.py` | beat Red Light, `voice-audio-2026-10-14` rehearsal, `tests/unit/test_voice_*.py` |
| 5 Engineer and fleet | the harness race engineer (SSH sandbox, Cedar leash, memory) for Pit Stop; the kinematic twin and Two Bodies; the Pit Wall portal; the team context layer | `ops/race_engineer.py`, `ops/pit_stop.cedar`, `src/deepracer_agent/twin.py`, `beats/two_bodies.py`, `portal/`, `.krewhq/` | `tests/unit/test_race_engineer.py`, Pit Stop read-only on the car, beat Two Bodies |

## Phase 1, Body

What the phase is for: a laptop process that can move the car and, more importantly, that cannot
leave it moving. `RosbridgeTransport` keeps one advertised publisher per topic (stop-to-neutral
35 ms on the car, 234 ms before), `DeepRacerDriver` arms manual mode (`vehicle_state 0` then
`enable_state true`), publishes the 20 Hz heartbeat, and always ends with a zero servo pair. The
deadman node on the car trips 300 ms after the last heartbeat, publishes ten zeros on both servo
topics, re-zeros any late non-zero command and turns the tail LED red. Discovery finds the car by
MAC, mDNS or a sweep (`DEEPRACER_HOST=auto`), so a new hotel network needs no config change.

Run it: `make find-car`, `make wheels-off`, `make beat NAME=preflight BODY=car`,
`make beat NAME=pull_the_plug BODY=car`. On the bench 2026-10-15: pre-flight go in 4.2 s, heartbeat
cut to `tripped` 272 ms, re-armed 1.4 s after resume.

## Phase 2, Gate

What the phase is for: the agent proposes, the gate disposes, and the audit log remembers. Every
`drive_deepracer` goes through upstream's `_command_gate` (headless runs declare
`STRANDS_ROS2_COMMAND_ALLOW` and log a `pregrant` approval) and then through `DeciderGate`: an
envelope question on the numbers, then one request over the frame that asks "is a person visible"
and the five-way class, merged toward Deny (`combine_frame_answers`). Any decider failure is
`vision unavailable` and a Deny. `why_stopped` reads the last stop from `events.jsonl` with its
class, probability and frozen frame reference, which is the Apology.

Run it: `make beat NAME=marshal BODY=sim`, `apology`, `blindfold`; on the car the same with
`BODY=car`. On the bench 2026-10-15 with the operator in frame: three hops denied at
`person_in_frame` 0.95, gate 681-727 ms, no motion, Apology spoken with class and probability.

## Phase 3, Senses

What the phase is for: what the camera sees is evidence for the gate and the narrator, never a
command. `capture_frame` parses the MJPEG stream (one grab lock, one retry); `look` sends the
frame to Nova Pro for a caption; the Sign beat reads the paper aloud and the gate ignores it;
`plan_deepracer` turns "square of 60 cm" into validated hops inside the pen. The Frame Judge kiosk
asks the decider with the live label set and keeps a leaderboard; Simon Says parses typed commands
locally (number words included), asks only the decider, and shows the Confirm plus the slower
re-plan when a command is over the envelope.

Run it: `make beat NAME=sign BODY=sim`, `NAME=shapes`, `make portal` then `/kiosk/judge` and
`/kiosk/simon`. Calibration study: `python -m deepracer_agent.calibrate_frames`.

## Phase 4, Voice

What the phase is for: the rover is interruptible by a word. `VoiceAgent` runs `BidiAgent` on
Nova Sonic with the same gated tools; `BidiBargeInEvent` publishes the zero pair before the model
finishes its sentence (22 ms on the car, 971 ms from key press with real audio); `voice_clock`
stamps every voice event from the last push-to-talk press so Red Light can say "you said stop and
my wheels stopped N milliseconds later". The browser sends PCM over `/ws/audio` with a level meter.

Run it: `make beat NAME=red_light BODY=sim`, `python -m deepracer_agent.voice_rehearsal`.

## Phase 5, Engineer and fleet

What the phase is for: the agent is one of several things that touch the car, and each has a
leash. The race engineer is one `create_harness` call with an `SshSandbox` to the car and a Cedar
policy: it may read calibration and remember the offset, and the write needs the operator at the
keyboard (`DEEPRACER_OPERATOR_CONFIRMED=1`). The twin answers the car's own rosbridge graph, so
the unchanged driver and gate drive it, and "stop all" halts both bodies. The Pit Wall shows the
frame, thought, verdict, LED badge and the twin pen for every beat.

Run it: `python -m ops.race_engineer` (read-only by default), `make beat NAME=two_bodies
BODY=sim`, `make portal`. On the car 2026-10-15: calibration read over SSH, offset 6000 against the
remembered mid, no write attempted.

## Testing the five use cases against this architecture

The council verdict names five things the audience sees: the seven-beat spine, the Frame Judge
kiosk, the Simon Says kiosk, Pit Stop and Two Bodies. `docs/results/five-use-cases-2026-10-15.md`
is the dated run of all five on this code, sim and car.
