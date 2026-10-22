# Showcase use cases: Physical AI with DeepRacer on Strands

Drafted 2026-10-12 for the use-case discussion. Every idea below is bounded by what the car
can sense and do (report 02), what upstream strands-robots already gates (report 01), what
deciders, bidi, Box and the harness actually provide (reports 03 and 08), and what was
measured on the car before (report 07). Nothing here is built yet.

## What the car can offer a showcase

| Capability | Stock car | Evo | Path |
|---|---|---|---|
| Ackermann drive, about 0.4 m/s safe indoors, 30 deg steer, 0.28 m min radius | yes | yes | `drive_*` tools over rosbridge or ROS; HTTP fallback |
| Front camera, 480x360 MJPEG, about 15-30 fps | yes | stereo pair | HTTP `/route` stream or `/camera_pkg/display_mjpeg` |
| 360 deg LiDAR scan | no | yes | `/rplidar_ros/scan` (best-effort QoS) |
| Battery, USB, device info, LED colour, Wi-Fi | yes | yes | services / HTTP |
| On-board RL model in autonomous mode with throttle cap | yes | yes | `vehicle_state 1` + `max_nav_throttle` + `load_model` |
| Calibration of steering and throttle PWM | yes | yes | `get/set_car_cal`, HTTP calibration routes |
| Odometry, pose, Nav2 | no | no (community Nav2 only) | out of scope v1 |
| On-car compute | Intel Atom, 4 GB | same | too slow for deciders or VLMs; run them on the laptop or GPU host |

The strongest single fact for the narrative: the car has **no watchdog and no odometry**.
It is blind and trusting. Every layer of Strands we add is a layer of sight, judgement or
restraint on top of a car that would otherwise hold its last command forever.

## The showcase ladder

Seven acts, each adding one Strands pillar. They are designed so acts 1 to 3 are
independent (can be built in parallel and demoed alone) and acts 4 to 7 compose them.

### Act 1. Marshal: a decider stands between the agent and the throttle

**Pillars:** Strands Decider, strands-agents interventions, strands-robots command gate.

Every `drive_*` call passes a `strands.interventions.InterventionHandler.before_tool_call`
backed by a local 2B decider server (about 150 ms). Two questions per call:

- `noul`: "Is this command inside the briefed envelope?" with the envelope in the
  criteria (speed under 0.5 m/s, duration under 3 s, no reversal within 0.3 s of a turn,
  battery above 20 percent). P(true) under 0.9 returns `Confirm` (human), under 0.5
  returns `Deny`.
- `choice` on the latest camera frame: `{clear, obstacle_near, person_in_frame,
  off_surface, unclear}`. `person_in_frame` or `unclear` returns `Deny` and triggers
  `stop_*`. This is the earlier Nova Pro continue/replan/abort loop (report 07) rebuilt
  with calibrated probabilities and a **fail-closed** default.

The upstream operator gate (`tool_context.interrupt`) stays underneath; the decider only
decides whether a human is asked, never whether the car moves unasked. Deliverable: the
gate, a refusal-table test, and a decider-lab suite that scores it on recorded frames.
This is the "benchmark" story: show the calibration curve before and after fine-tuning
on 200 labelled frames from this room.

### Act 2. Pit Crew: drive the car by voice

**Pillars:** Strands bidi (Nova Sonic), strands-robots drive tools, Act 1 gate.

A `BidiAgent` with `BedrockNovaSonicModel` and the car's `drive`, `stop`, `battery`,
`look` (frame description) tools. Spoken "ease forward two seconds", "swing left", "stop".
Barge-in is the safety feature to show: saying "stop" mid-sentence fires
`BidiBargeInEvent`, the agent cancels the response and calls `stop_*`. A
`@tool(context=True)` `end_session` calls `agent.cancel()` and sends the zero servo pair.

Design constraint to state honestly: bidi cannot pause on an operator interrupt, so voice
motion needs a **pre-granted envelope** (`STRANDS_ROS2_COMMAND_ALLOW` plus the Act 1
decider with `Confirm` disabled and a tighter speed cap) and the dashboard e-stop in reach.
The transcript and every decider verdict land in the strands-robots HITL audit log.

### Act 3. Race Engineer: a harness agent runs the pit wall

**Pillars:** Strands Harness SDK (`create_harness`), Strands CLI, interventions, memory.

`create_harness(model=..., instructions=<car brief>, tools=[car_agent.as_tool()],
interventions="./pitwall.cedar")` with the harness sandbox pointed over SSH at the car.
It can `ros2 topic hz /camera_pkg/display_mjpeg`, read `calibration.json`, tail
`deepracer-core` logs, check battery, compare the community image version against the
docs via `web_fetch`, and write a post-run report. Subagent presets: `telemetry_analyst`
(reads recorded episodes), `calibration_tuner` (proposes PWM changes, never applies
without approval). Long-term memory keeps the car's quirks (sign convention, which Wi-Fi,
last calibration). The Cedar policy allows read-only shell on the car and denies any
`manual_drive`, `set_car_cal` or `systemctl` unless a human approves. Operator console is
`strands --agent ./pitwall/agent.py`.

This is the act where "agentic" is about engineering the robot, not steering it, and it is
the natural home for harness-sdk.

### Act 4. Scout: see, log, map, collect

**Pillars:** strands-robots recorder and episode labels, VLM tool, LiDAR on Evo, decider
labelling.

The agent explores a taped course: grab frame, describe it (Nova Pro or Claude), read the
LiDAR scan, decide the next short move, repeat; `dataset_recorder` captures frames,
commands and verdicts as episodes; a decider `score` tool grades each episode on a rubric
(stayed on surface, smooth, no near-miss) and writes `episode_labels`. Output: a labelled
dataset and a text map of the room. This is the data half of Physical AI and reuses the
DeciderJudge idea that was declined upstream as PR #4573.

### Act 5. Supervisor: System 2 watches System 1

**Pillars:** the car's own RL model, strands-robots mode services, Act 1 decider.

Load an RL model, set autonomous mode with a low `max_nav_throttle`, and let the agent
supervise: it watches frames through the vision decider and the LiDAR, and when the
decider says `off_surface` or `person_in_frame` it switches `vehicle_state` to manual and
stops, then explains what it saw. Show the layering explicitly: reflex policy on the car,
calibrated decider in the middle, reasoning agent on top. Fixes the upstream state bug on
the way, since this act needs both mode values to be right.

### Act 6. Paddock: fleet, twin and dashboard

**Pillars:** strands-robots mesh, dashboard, voice console, MuJoCo twin.

Register the car (`DeepRacerDriver`, registry entry) so it is a mesh peer with a dashboard
card, e-stop and audit. Add a MuJoCo Ackermann twin built from the AWS URDF and rehearse
every plan in the twin before metal ("dry run is `mode=sim`"). The dashboard voice
console can `stop_all`. With a second robot (another car, or the Yahboom) the fleet view
shows two peers and one audit stream.

### Act 7. Boxed Driver: governance around the whole agent

**Pillars:** Strands Box.

Run the laptop-side agent inside `box run --config box.toml`. The Dogwood policy allows
egress only to the car's IP on 443 and 9090 and to Bedrock; the egress gateway injects the
car's console password so the model never sees it (fixing the plaintext-secret problem in
the earlier repos); a temporal rule denies any `manual_drive` after an `abort` event until
a human `reset` event appears in the shared history. macOS Apple silicon only in 0.1.x, so
this wraps the dev-machine agent, not the car.

## How the pillars map

| Act | strands-robots | strands-agents | harness-sdk | Decider | Bidi | Box |
|---|---|---|---|---|---|---|
| 1 Marshal | gate, drive tools, audit | interventions | | motion + vision gate, decider-lab | | |
| 2 Pit Crew | drive/stop tools, audit | tools, hooks | | gate from Act 1 | BidiAgent, barge-in | |
| 3 Race Engineer | car agent as tool | sessions, memory | create_harness, SSH sandbox, subagents, CLI, Cedar | optional | | |
| 4 Scout | recorder, episode labels, LiDAR read | agent loop | | score rubric | | |
| 5 Supervisor | mode services, frame tool | agent loop | | vision gate | optional voice narration | |
| 6 Paddock | mesh, dashboard, twin, registry | | | | voice console stop_all | |
| 7 Boxed Driver | | | | | | policies, egress gateway, temporal rules |

## Recommendation

Build Acts 1, 2 and 3 first. They are independent, each shows exactly one new pillar on
top of the same gated car, and together they already make the complete pitch: a car that
is judged (decider), spoken to (bidi) and engineered (harness) through one Strands stack.
Act 5 is the strongest single demo moment and should follow once Act 1 is calibrated.
Acts 4, 6 and 7 are the depth for a longer talk or a blog series.

Prerequisites before any act touches metal: the two upstream fixes in report 06 (manual
mode is state 0; best-effort LiDAR echo), the community Jazzy image with rosbridge, and a
re-measured calibration on the ROS path.

## Open questions for the discussion

- Audience and venue: a 10-minute stage demo favours Acts 2 and 5; a workshop favours 1, 3, 4.
- Stock car or Evo: LiDAR changes Acts 4 and 5 materially.
- Where the decider runs: laptop GPU, a second machine on the LAN, or a cloud GPU with an
  acceptable round trip. Not AgentCore for the motion gate.
- Whether the voice act accepts a pre-granted envelope or insists on a human approving
  each move (then bidi narrates and a dashboard operator approves).

## What the audience sees

The physical fact: a 1/18-scale car at walking pace on a 2 by 3 metre taped course. Strands is
invisible unless it is on a screen and in the room, so every act needs three visible things:
the car doing something, a screen showing what the agent saw and decided, and a human doing
something the car responds to.

| Act | What happens on the floor | What is on the screen | The human beat |
|---|---|---|---|
| 1 Marshal | Car stops before anyone touches anything when a person steps in | Live frame + decider verdict (class, confidence, denied, ms); a typed over-limit command refused with reason | Volunteer steps onto the track; presenter types an unsafe command |
| 2 Pit Crew | Car moves and arcs on spoken commands; halts mid-sentence on "stop" while the agent's voice cuts off | Live transcript with the barge-in event marked | Presenter talks, no keyboard |
| 3 Race Engineer | Nothing moves | Terminal: agent SSHes into the car, reads calibration and topic rates, diagnoses a pull, proposes an offset, asks approval before writing | Presenter asks "the car pulls left, why?" and approves or declines |
| 4 Scout | Car explores in short hops, pausing | Split view: frame + LiDAR sweep; growing log and map sketch; afterwards scored episodes | None live; strong as replay |
| 5 Supervisor | Car's own RL model laps at low throttle; a shoe is placed on the track; agent flips to manual and stops; resumes when cleared | Frame + decider verdict; mode change; spoken explanation | Presenter places and removes the shoe |
| 6 Paddock | Plan runs in the MuJoCo twin on screen, then on the real car, and they match; "stop all" halts both | Dashboard fleet card (battery, mode, frame, red stop) beside the twin | Presenter says "stop all" |
| 7 Boxed Driver | Nothing moves | Egress log showing only car IP and Bedrock; a denied exfiltration attempt; transcript proving the agent never held the password | Thirty-second aside |

Stage set: the course on the floor, the car, one large screen in four quadrants (live frame
with verdict, transcript or agent log, dashboard card with stop button, scrolling audit log).
One presenter, one volunteer.

Ten-minute version: Act 2 then Act 5 with Act 1 running underneath both. Voice gets attention,
the shoe on the track gets the reaction, the verdicts on screen explain it. Act 3 reads better
in a workshop or blog post than on a stage.
