# Field-ops brainstorm: making the rover demo survive a conference floor

Constraints from docs/context/02 that drive everything below: **no watchdog** (last throttle
persists until a zero arrives, 6.5); **one HTTP session token** (a browser on the console logs
the agent out, 7c); `/api/manual_drive` says success even outside manual mode (silent drop);
HTTP drive is quantised to 3 steps, so fine control goes over rosbridge with RELIABLE QoS
(6.4); camera is cheapest as the HTTPS MJPEG `/route` stream; battery, LED, sensor status and
calibration are plain HTTPS calls in any mode. The car is 1.9 kg at 0.3 m/s: it hurts nobody,
but it gets kicked and lifted, and it runs off under a table if Wi-Fi drops mid-move.

## 1. Feasibility and failure-mode review of the current pool

Every motion demo inherits two base failures: Wi-Fi drop mid-move with no on-car watchdog,
and a foot or hand in the frame. Base mitigation for all: an on-car rclpy **deadman node**
(zero after 300 ms without heartbeat; small, upstreamable), moves capped at 0.5 s / 0.3 m/s,
and a **2 x 2 m low-lipped pen** (pool-noodle edge) so the rover cannot reach feet. Not
repeated per item.

| Candidate | Reliability | Top two failure modes | Mitigation | Fallback if it dies live |
|---|---|---|---|---|
| "What do you see?" | **High** | Nova Pro round trip 3-6 s on venue uplink; auto-exposure blown by booth LED/backlight so it describes "a bright blur" | Hotspot WAN failover on the travel router; aim camera at a matte backdrop, not aisle lights; cache last good caption | Presenter asks the audience "what does it see?" while the caption lands; worst case replay the morning's captions |
| "Find the red backpack" | **Medium** | Colour under coloured booth lighting (red backpack reads purple/brown; many red lanyards); search loop drifts out of pen while "hypothesising" | Decider yes/no "is the target in frame?" not colour; restrict to the pen; 2 hops max then ask | Freeze, say "show me", attendee holds it to the camera; becomes a caption demo |
| "Follow me" | **Low** | Tracking swaps to another person in a crowd; continuous motion outside the pen, which the deadman cannot save | Stage only, one volunteer, 3 m straight, speed 0.2, person-too-close stop | Cut it; replace with "look at me" (steer toward the person, no throttle) |
| "Take me to the AWS booth" | **Low** | Floor plan has no scale and the car has no pose; it confidently escorts the wrong way; crowds block | Reframe as "plan and narrate the route" (harness fetch + speech, zero motion); at most a symbolic first turn in the pen | Harness shows the plan and says the route aloud |
| Hazard sweep (cables) | **Medium** | A slow loop around a booth is a loop into ankles; VLM flags every black lanyard as a cable | 4-point pan from the pen corners, or hand-carry the rover with motors disabled and let it log | Replay a recorded sweep with the live log; still shows recorder + memory |
| "Who have you met?" | **High** | Nobody consented in the noise; memory recalls a name that was mis-transcribed | Consent via a tap on a tablet, not voice; store the typed name; "forget me" button on the same tablet | Works offline against the local store; no fallback needed |
| "Why did you just stop?" | **High** | Needs a prior live stop; raw audit log unreadable on screen | Seeded log from the morning; one card per event (frame, verdict, ms, rule) | None needed; local log, no uplink |
| "Teach it a trick" (voice replay) | **Medium** | Voice capture in noise; replay drifts on carpet (open loop, no odometry) | Teach by typed or slider moves; tricks under 1.5 m; replay only in the pen | Replay in the MuJoCo twin if the car is down |
| "Deliver this sticker" | **Medium-low** | Target moves; tray tips; "green jacket" is ambiguous in a crowd | Deliver to a cone or a volunteer at the pen edge | Hand the sticker from the tray as it says "delivered"; people laugh, intent-to-action still lands |
| "Which body are you in?" | **High** if the second body is the MuJoCo twin; **Low** if it needs a second physical robot shipped | A second robot doubles the battery/Wi-Fi/calibration failure budget; mesh discovery on a travel router | Twin is the second body; the real rover the third | Twin alone still tells the story |
| Stage A: it sees | **High** | Same as "what do you see?" plus stage lighting from the front | Same | Same |
| Stage B: it refuses | **High** | GPU box asleep/thermal; verdict unreadable from the audience | Dummy inference every 30 s; big-font verdict card; LED red | Rule-based envelope refusal shows the same card without the decider |
| Stage C: supervises RL model | **Low-medium** | On-board RL needs a track-like visual, on a stage it drives into the audience; mode flips (manual=0 / autonomous=1) over flaky Wi-Fi are the no-watchdog case | Only with a taped mini-oval in the pen and `max_nav_throttle` 20; rehearse the flip 20 times | A shoe in front of a gated manual creep: same beat, no RL |
| Stage D: engineers itself | **Low live, high pre-recorded** | 60-120 s of harness output over SSH over Wi-Fi; a bad calibration write kills every later demo | Run it that morning; on stage show the saved transcript and re-run only the "drive straight" check | Narrated transcript; car drives 1 m straight |
| Stage E: governed (Box) | **High** | Policy blocks an endpoint added that morning; nothing moves, audience bored | Freeze policy a week out; 30 s aside with one denied-exfiltration line | Static egress log screenshot |
| Ambient booth host | **Medium** | Open mic = constant false barge-ins and Sonic answering the neighbour's demo; uplink cost all day | No open mic: ambient host is **text + camera**; voice only on push-to-talk | Camera-only greeter with captions |

## 2. Eight use cases designed for reliability (and still impressive)

Design rules: short bursts, no floor plan, no quiet room, works in the pen, the LED as a
visible truth signal, compute off-board, and every one has a no-motion mode that is still a demo.

1. **Pre-flight go/no-go as the opening act.** The agent runs the checklist you would do anyway: battery, sensor status, calibration read-back, one MJPEG frame, rosbridge ping, RSSI, deadman heartbeat; speaks a go/no-go with reasons; LED green. Pillars: Agents SDK tools + hooks, strands-robots runtime, harness over SSH optional. Degrades to HTTP-only; failures become content ("it refused to move because its pack is at 2/10; that is the point").
2. **Frame judge (no motion).** Attendees hold anything to the camera. VLM captions it; the decider answers three yes/no questions with confidence and milliseconds: "person within 1 m?", "a conference badge?", "path clear?" Developers love the latency number. Pillars: Decider as frame classifier, Agents SDK, Bidi optional. Zero motion; runs all day as the ambient host.
3. **Red light / green light (the marshal in the pen).** The rover creeps in 20 cm gated hops; each hop needs a green decider verdict on the current frame; LED amber thinking, green approved, red denied. A volunteer puts a foot in the pen: red, stop, spoken reason. Pillars: strands-robots gate + audit, Decider intervention, Bidi narration. Stage C without the RL model; the most reliable "it stops for people" beat.
4. **Red-team the gate (kiosk).** A booth tablet: attendees type commands ("spin at full speed", "go to the coffee stand", "wiggle"). Cedar envelope + decider judge; denied gets a reason card, approved executes as a short pattern in the pen; Box egress log scrolls beside it. Pillars: Agents SDK interventions, Decider, Box, strands-robots gate. No mic; the deny path needs no uplink.
5. **Pattern teach and replay.** "Teach it a wiggle": three gated moves under 0.5 s each are planned on screen, approved once, executed; saved under a name; replayed on request later ("do the wiggle you learned from Priya"). Pillars: recorder, memory (consent via tablet), Agents SDK. Replay also works in the MuJoCo twin.
6. **"Why did you just stop?" accountability card.** Zero motion, local audit log, one card per event: frame, verdict, rule, latency, who approved. Pillars: HITL audit, Decider, dashboard. Works with no internet at all.
7. **Battery butler.** A battery hook blocks motion below level 3, LED goes blue, the rover asks to be charged and the harness logs the swap; the presenter swaps the pack on camera and the agent re-runs pre-flight. Turns a mandatory ops task into a demo of hooks + memory and gives you a scripted reason to pause whenever you need one.
8. **Twin first, body second.** Every motion plan runs in the MuJoCo twin on screen before the real rover; "stop all" halts both; "which body are you in?" answered by the registry. Pillars: strands-robots mesh/dashboard/twin, Agents SDK. If the car is down, the twin carries the whole demo and nobody knows.

## 3. Demo runbook skeleton

**Pre-show (T-60 min)**
- Travel router up on 5 GHz, own SSID, static DHCP leases for rover/laptop/GPU box; WAN = venue Ethernet if offered, else phone hotspot; test Bedrock round trip and record it.
- Rover on fresh drive pack + compute pack; `get_device_info`, `get_sensor_status`, `get_battery_level`, calibration read-back saved to a file (your rollback for stage D).
- Confirm mode: `vehicle_state` is **0 (manual)**, enabled; rosbridge on 9090; deadman node alive (kill the laptop heartbeat and watch wheels zero).
- Wheels off the ground: one 0.2-throttle pulse each way; confirm sign and zero.
- Close every browser tab pointing at the console (single session token).
- Warm the decider GPU; warm Nova Sonic with one utterance; load the seeded audit log and the morning's harness transcript.
- Pen assembled; cones placed; lapel mic and PTT button tested; e-stop reachable from the presenter's spot.
- Screens: live frame + verdict card + LED badge; dashboard/transcript; a muted window of pre-recorded golden runs for every demo.

**Per-demo reset (60 s)**
- `stop_all`, `enable_state false`, then `enable_state true` (publishes zero); LED back to white.
- Reposition rover to the pen start mark by hand; wipe the lens.
- Refresh HTTP session via a `get_battery_level` poll (keeps the 1 h cookie alive) and check battery >= 4.
- Clear the agent conversation; keep long-term memory.
- Check RSSI and Bedrock latency; if > 4 s, run a no-motion demo next.

**Battery plan.** Drive packs: three, rotate every 45 min, charger at the booth. Compute pack: keep the compute on wall power whenever static (it is most of the day). Hard rule: no motion demo below 3/10; the battery butler hook enforces it so you never argue with yourself.

**Wi-Fi plan.** Never join venue Wi-Fi with the rover. Only Bedrock traffic leaves the router. Camera over HTTPS MJPEG at 480x360, not rosbridge Image. If rosbridge drops: deadman zeros the wheels, the agent surfaces "lost link" and the next demo is a no-motion one.

**The e-stop, physically.** Three layers: (1) the rover's drive-battery switch on the rear of the chassis, which cuts the ESC with no software involved, so the presenter stands within arm's reach of the pen; (2) a big USB button on the table wired to `stop_all` + `enable_state false` + kill the agent process; (3) the pen lip and a foot. A dashboard e-stop alone is no e-stop on flaky Wi-Fi.

**When the model is slow.** LED amber means thinking; the presenter says so and uses the gap: "notice it is not moving while it thinks; nothing moves without a verdict." After 6 s, switch to the kiosk or the accountability card; after 15 s, play the golden run and say so.

## 4. Which pillars are hardest live, and how to hide a failure

- **Bidi (hardest).** Noise, false barge-ins, uplink latency. Headset/PTT only, three rehearsed phrases, and a text console rendering the identical transcript UI so a typed command looks like a transcription. Barge-in is one scripted moment, not a mode.
- **Harness over SSH (second).** Long, text-heavy, depends on SSH over Wi-Fi plus Bedrock. Run it before the slot; show the saved transcript; re-run only the last verification step live. Never write calibration live without the saved rollback.
- **strands-robots motion (third).** The no-watchdog car on venue Wi-Fi. Deadman + pen + short hops; the twin runs first so a dead car still shows the plan.
- **Decider (easy if local).** Only failure is the GPU box sleeping; keep it warm and have a rule-based envelope that produces the same red card.
- **Box (easiest).** Invisible by design; freeze the policy a week out. Its failure mode is blocking you, so never change policy at the venue.

Principle: every demo has a no-motion sibling, every screen widget renders from a seeded local store as well as live, and the LED is always truthful, so the story never depends on the thing most likely to die.
