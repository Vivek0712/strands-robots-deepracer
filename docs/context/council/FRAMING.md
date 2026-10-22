# Framed question for brainstorm agents and council advisors

## The decision
Which Physical AI showcase use cases should be built for a tech-conference demo of a small
rover that can see, speak, remember and reason, so that the demo lands with a live audience
AND genuinely exercises five Strands pillars: strands-robots (gated robot control, mesh,
dashboard, recorder), Strands Agents SDK (agent loop, tools, hooks, interventions, memory),
Strands Harness SDK (`create_harness`: batteries-included agent with shell/file/web tools over
a local, Docker or SSH sandbox, subagents, long-term memory, Cedar/natural-language
interventions, Strands CLI), Strands Decider (2B calibrated yes/no, choice and score model,
about 150 ms on a laptop GPU, usable as a tool-call intervention gate and as a frame
classifier), Strands Bidi (real-time voice agent on Nova Sonic with barge-in and tool use),
and Strands Box (Rust sandbox engine for the agent process on macOS: policy-gated shell,
python, egress with credential injection, temporal rules).

## Context (facts, verified in docs/context/ reports 00-10)
- The rover is an AWS DeepRacer (1/18 scale, Ackermann steering, about 0.3-0.4 m/s safe indoors,
  30 deg max steer, 0.28 m min turning radius). Stock sensors: one front 480x360 MJPEG camera.
  Evo variant adds a stereo camera pair and a 360 deg LiDAR. Battery about one hour of driving.
  Compute: Intel Atom, 4 GB, Ubuntu 20.04 / ROS 2 Foxy (or community Ubuntu 24.04 / Jazzy).
  Too slow for VLMs or deciders on board; those run on a laptop or small GPU box at the booth.
- No odometry, no pose, no watchdog: the car holds its last command until told otherwise.
  Control is over rosbridge websocket (laptop), rclpy (on-car), or the HTTPS console.
- The rover can also run its own on-board RL model in "autonomous mode" at a capped throttle.
- It can report battery, set an LED colour, read and write steering/throttle calibration.
- Upstream strands-robots already ships the gated `drive_<robot>(linear, angular, duration)`
  and `stop_<robot>()` tools with a human-in-the-loop approval gate on every motion command,
  an audit log, a fleet mesh, a dashboard with e-stop and a voice console, a dataset recorder,
  episode labelling, and a policy/training stack. The Yahboom M3 Pro and EarthRover are other
  supported mobile bases, so the same agent can move between bodies via a registry entry.
- Earlier work (March 2026) proved on this car: voice-free text planning of manoeuvres,
  a Nova Pro vision loop (continue/replan/abort) between steps, an MJPEG frame buffer.
- Setting: a tech conference. No taped course. A booth (open floor, crowds, noise, flaky
  Wi-Fi, people's feet) and possibly a stage slot of 8-12 minutes. Demos may be step by step
  and multiple. A travel router, laptop, small GPU box, lapel mic and a physical e-stop can be
  brought. A small 3D-printed tray on the rover is possible.
- The person building this is a solo AWS AI Hero / Strands contributor with upstream PRs
  merged; they will build over roughly four weeks and also want contributions back upstream.

## What is at stake
A live hardware demo in front of developers. A demo that is impressive but flaky, or safe but
boring, or that shows the pillars as five disconnected gimmicks, fails. The audience should
leave understanding why "Physical AI" means more than "an LLM calling a drive function".

## Non-negotiables
- A person stepping in front of the rover must always result in a stop; no fail-open paths.
- Motion commands stay behind the strands-robots approval gate or an explicitly pre-granted,
  documented low-speed envelope.
- Nothing on board can run a large model; vision, decider and voice live off-board.
- Consent for any memory of people; "forget me" must work.
- Buildable in about four weeks by one person, reusing upstream strands-robots.

## Candidate pool already on the table (from docs/context/09 and 10)
Booth: "What do you see?"; "Find the red backpack"; "Follow me"; "Take me to the AWS booth"
(harness fetches the floor plan); hazard sweep (cables); "Who have you met?" (memory);
"Why did you just stop?" (answers from audit log); "Teach it a trick" (voice-taught replay);
"Deliver this sticker"; "Which body are you in?" (same mind, different robot).
Stage: it sees; it refuses an unsafe command with the decider verdict on screen; it supervises
the on-board RL model and takes over when a volunteer steps in; it engineers itself (harness
over SSH finds calibration drift, asks, fixes); it is governed (Box egress log, never holds the
password). Ambient: booth host that greets, answers Strands questions, logs them, asks to be charged.
These are candidates, not decisions. Add, remove, merge, or replace freely.
