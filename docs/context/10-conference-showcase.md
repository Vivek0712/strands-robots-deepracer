# Conference showcase: a rover that understands the room

Drafted 2026-10-12. Supersedes the track-bound framing in report 09 for the conference
setting. The DeepRacer is treated as what it now is: a small rover with sight (camera,
LiDAR on Evo), speech (bidi), judgement (decider) and reasoning (agent + harness). The
conference floor is the world: people, badges, posters, booths, signs, cables, chairs.

## Reframe

Do not present a car that drives. Present a rover that understands the room it is in and
acts on that understanding with words and wheels. Every demo is a question an attendee can
ask or a situation they can create; the rover answers in speech, motion, or both.

## Booth-floor demos (walk-up, 1 to 3 min, no course)

| # | Prompt or situation | What the rover does | What the audience sees | Pillars |
|---|---|---|---|---|
| 1 | "What do you see?" | Describes the scene, reads badges and signs | Speech + frame with caption on screen | bidi, VLM tool |
| 2 | "Find the red backpack" | Observe, hypothesise, short arc, re-observe, approach to safe distance, announce | Search loop narrated; stops short of people | agent loop, drive tools, decider gate |
| 3 | "Follow me" | Tracks a person at distance, stops for cross traffic, asks for a wave when lost | Rover trailing an attendee | person tracking, decider person-too-close, locomotion envelope |
| 4 | "Take me to the AWS booth" | Harness fetches the floor plan, reasons a route, escorts a few metres narrating turns | Web knowledge turned into motion | harness web_fetch, agent, drive tools |
| 5 | Someone drops a cable | Slow loop of the booth, flags trip hazards with photo, logs them | Inspection report on screen | recorder, VLM, memory |
| 6 | "Who have you met?" | Recalls consented introductions and earlier questions | Memory across hours; "forget me" works | harness long-term memory, bidi |
| 7 | "Why did you just stop?" | Answers from its own audit log, shows the frame and verdict | Accountability | HITL audit, decider, dashboard |
| 8 | "Call that a victory lap" | Saves a voice-taught sequence, replays on request | Teach-by-doing | recorder, replay policy, memory |
| 9 | "Take this sticker to the green jacket" | Finds the person, delivers, waits, returns | Intent to action via perception | VLM, drive tools, small printed tray |
| 10 | "Which body are you in?" | Same agent, voice and memory on a different registered robot | Body swap in one sentence | strands-robots registry, mesh |

## Stage demos (scripted, 8 to 12 min)

| Act | Beat | Pillars |
|---|---|---|
| A, it sees | "What do you see?" reading the front row | bidi, VLM |
| B, it refuses | "Drive at full speed into the audience" declined with the envelope and the verdict on screen | decider gate, command gate |
| C, it judges another AI | On-board RL model laps the stage; volunteer steps in; agent takes manual control, stops, explains | mode services, vision decider, agent |
| D, it engineers itself | "You're pulling left": harness SSHes in, finds calibration drift, proposes, asks, applies, drives straight | harness, Cedar interventions, SSH sandbox |
| E, it is governed | Egress log shows only rover and Bedrock; asked for its password, it does not have it | Box |

## Ambient mode (all day between demos)

Booth host: greets approaching people, answers questions about Strands from the docs via
the harness, watches battery and asks to be charged, logs every question for an
end-of-day report. Screen shows live view plus current thought.

## Conference realities

- Wi-Fi: travel router; rover, laptop and decider box on it; only Bedrock traffic leaves.
- Noise: Nova Sonic with AEC, push-to-talk fallback on the laptop, lapel mic for presenter.
- Crowds: speed cap about 0.3 m/s, decider person-too-close class, physical e-stop on the table.
- Battery: about one hour of driving per pack; two packs, swap at lunch.
- Compute: vision, decider and voice on the laptop or a small GPU box, never on the rover.
- Consent: visible sign; names remembered only when offered; "forget me" demoed.

## Build order for a conference

Booth first: demos 1, 2, 7 and the ambient host (camera + voice + gate only, run all day).
Stage: Acts A, B, C. Demo 10 is the closer that moves the story from DeepRacer to Physical AI.

Prerequisites unchanged from report 06: upstream mode fix, best-effort LiDAR echo,
community Jazzy image with rosbridge, re-measured calibration on the ROS path.
