# Development plan: harness, portal, repos, team context, and what I need from you

Written 2026-10-12. Scope: build, test and deploy the seven live beats of report 11 on the
architecture of report 12, autonomously, with a testing harness that runs without the car,
a portal to present and command everything, KrewHQ as the context layer between agent
teams, and a fork-and-pin policy for upstream fixes.

## 1. Repositories (clean, latest)

| Repo | Purpose | Notes |
|---|---|---|
| `Vivek0712/strands-robots-deepracer` (new, this directory) | the project: agent, driver glue, car packages, portal, harness, beats, docs | `~/strands-robots-deepracer` sits inside the HOME git repo; it must become its own nested repo (`git init` here) so history and remote are clean. Needs your OK (item D1). |
| `Vivek0712/robots` (existing fork of strands-labs/robots) | upstream fixes as branches, each a PR: `fix/deepracer-manual-mode-state`, `feat/rosbridge-ackermann-robot`, `feat/deadman-heartbeat` | project pins `strands-robots @ git+https://github.com/Vivek0712/robots@<branch>`; PRs raised and not waited for; switch to a release later |
| `Vivek0712/strands-decider` (existing fork) | branch `feat/gemma4-image-audio` (your PR #67) plus anything the demo needs | pinned the same way |
| `Vivek0712/krewhq` (existing) | team context layer | used as-is; a `deepracer` project added to the org map |

Layout of the project repo:

```
strands-robots-deepracer/
  pyproject.toml            uv, python 3.12, pins to the forks
  src/deepracer_agent/      driver (rosbridge Ackermann), tools, decider gate, voice, beats
  car/                      ROS 2 package: deadman_node + systemd unit + install script
  portal/                   FastAPI + WebSocket backend, React/Vite frontend (built output committed)
  harness/                  fake car (rosbridge mock + MJPEG mock), fixtures, recorded frames
  tests/                    unit | sim | car (wheels_off) | pen markers
  beats/                    one script per beat, runnable in sim and on car
  docs/context/             this bundle
  .krewhq/                  team map and handoff templates
```

## 2. Testing harness (test strands-robots use case first, car second)

Four layers, each a pytest marker and a `make` target.

| Layer | Marker | What runs | Needs |
|---|---|---|---|
| 0 unit | (none) | driver maths, gate decisions, tool schemas, with upstream's `_transport_stand_in` recorder pattern | nothing |
| 1 sim | `sim` | the **fake car**: a websocket server speaking the rosbridge protocol subset (advertise, publish, call_service, subscribe) that emulates the real ctrl_pkg semantics: drops `manual_drive` unless mode is 0 and enabled, drops out-of-range values, never times out (no watchdog), answers battery, LED and calibration services; plus a fake MJPEG HTTP server replaying recorded frames; plus the decider server. The whole stack (agent, gate, portal, voice in text mode) runs end to end with no hardware | laptop only |
| 2 car, wheels off | `wheels_off` | contract suite on the real car on a stand: arm, hop, trailing zero, deadman trips when the heartbeat stops, Wi-Fi-pull test, stop-latency measurement, camera frame rate, battery | car on a stand, IP, SSH |
| 3 pen | `pen` | the seven beats on the floor in the 2x2 m pen, each run filmed; pass is 10 of 10 | pen, you present |

The fake car is the most valuable piece: it encodes the car's gotchas from report 02 as
executable behaviour, so a regression (for example arming with the wrong state) fails in CI
rather than on the floor. The MuJoCo twin joins as a second sim body in week 3.

## 3. Portal ("Pit Wall")

A standalone web portal, not the upstream dashboard, because the beats need a single screen
contract and a command surface the dashboard does not have. Reuses upstream pieces where
they exist (HITL approval event, audit records, mesh status).

| Panel | Content | Source |
|---|---|---|
| Live view | MJPEG frame with the latest decider class and probability overlaid | car MJPEG via laptop proxy; decider server |
| Thought | one line of agent reasoning or the tool call in flight | agent stream |
| Verdict | big-type Proceed / Guide / Confirm / Deny and the reason; LED badge mirrors the car LED | intervention handler |
| Audit | one card per event (command, verdicts, approval, stop, frame) | strands-robots audit store |
| Command | text box to issue a command (Simon Says kiosk), approve/deny buttons for the gate's Confirm, big red STOP ALL | agent + gate |
| Voice | push-to-talk button; browser mic PCM over WebSocket to the bidi agent; transcript and barge-in markers | `strands.bidi` with Nova Sonic |
| Pre-flight | battery, link RSSI, deadman heartbeat, mode, calibration, camera fps, decider latency | car services + harness |
| Body | which body is active (car or twin); plan runs in twin first | registry |

Backend FastAPI + WebSocket on the laptop, frontend React/Vite with the built output
committed so nothing needs Node at show time. The same portal drives sim and car.

## 4. Audio on the car

Facts: the DeepRacer has 4x USB-A, 1x USB-C, 1x micro-USB, 1x HDMI, Wi-Fi 802.11ac, and
no speaker or headphone jack. Checked on the car over SSH on 2026-10-14 (stock Foxy image):
`rfkill list` shows only `phy0: Wireless LAN`, `bluetoothctl list` reports no controller, and
`/proc/asound/cards` is empty. The car has no Bluetooth radio and no sound card, so option 3
below is out and option 2 needs a USB speaker (record in `car/bootstrap/foxy-rosbridge.md`).

Options, in order of reliability:

1. Voice from the laptop or a booth speaker (default for v1). The bidi agent already lives
   on the laptop; zero car changes.
2. USB speaker plugged into the car, driven by a small `speak` node that plays PCM pushed
   from the laptop. Reliable on Ubuntu with ALSA; needs one cheap USB speaker.
3. Bluetooth speaker paired to the car. Ruled out: the car exposes no Bluetooth controller.

## 5. KrewHQ as the team context layer (optional maintainer tooling)

Agent teams: **Car** (driver, deadman, ROS packages), **Portal**, **Intelligence** (decider
gate, voice, VLM tools), **QA** (harness, beats, pen runs). Each agent session starts with
`krewhq session-start` and `krewhq recall` scoped to the `deepracer` project, captures as it
works, promotes decisions and gotchas, and ends with `krewhq handoff` to the next team; the
next session runs `krewhq pickup`. Humans see the ledger in the KrewHQ UI. The spoke CLI
is installed locally; the token is in `~/.krewhq/config.toml`. KrewHQ is optional maintainer
tooling: skip this whole section if you do not have it; nothing in the repo needs it to run.

Blocker today, diagnosed: the maintainer's EC2 pilot hub (instance id, address and
security group `<redacted>`) is running, but its security group allows port 8443 only from
an old public IP, so the hub is simply firewalled off. Fix is one reversible rule (item B4):

```bash
aws ec2 authorize-security-group-ingress --profile heisenberg --region us-east-1 \
  --group-id <redacted> --protocol tcp --port 8443 --cidr <my-ip>/32
```

At the venue the IP changes again; `deploy/aws/cloud-pilot.sh` should get an `allow-me`
step, or the hub moves behind the travel router's VPN. Alternative: local hub via
`deploy/docker/docker-compose.yml` (no cost, no firewall, but no cross-machine sharing).

## 6. Fork-and-pin policy for upstream issues

When strands-robots, strands-agents, strands-decider or harness-sdk blocks us: branch on the
fork, fix with upstream's house rules (changelog.d fragment, refusal-table tests, AGENTS.md),
open the PR, pin the project to the fork branch, and continue. Do not wait for merge; do not
switch to a newer upstream release during this development. Known first PRs: manual mode is
state 0; rosbridge-capable Ackermann driver; deadman heartbeat contract; decider client image
and audio support if not yet released.

## 7. Build order (four weeks, autonomous once dependencies are met)

| Week | Car team | Portal team | Intelligence team | QA team |
|---|---|---|---|---|
| 1 | reflash or verify image, rosbridge on car, mode-state PR, one wheels-off hop, deadman node + systemd | skeleton, live MJPEG, audit feed | decider server on the Mac, benchmark E2B vs E4B, text and image latency | fake car with real ctrl semantics, unit + sim CI green |
| 2 | rosbridge Ackermann driver, registry entry, camera/battery/LED tools, latency measurement | verdict, command, approve/deny, STOP ALL | intervention gate (envelope + frame class), fail-closed tests | wheels-off contract suite passes on the car |
| 3 | pen setup, calibration on ROS path | PTT voice panel, pre-flight panel, body switch | bidi agent with drive/stop/look tools, one scripted barge-in, VLM look tool | seven beats scripted, run in sim and pen, filmed |
| 4 | spares, battery plan | polish, kiosk mode | Sign and Apology prompts, recorded Pit Stop and Two Bodies | daily rehearsal, 90 percent cut rule, go/no-go |

## 8. What I need from you

### A. Hardware and physical access (I cannot do these)

1. **The car on the network and reachable from this Mac.** Its IP, which car (stock or
   Evo), and which image it runs (stock Ubuntu 20.04 / Foxy or community 24.04 / Jazzy). If
   stock, a decision whether I may plan a reflash to the community image; you flash the USB
   stick and boot it, I prepare the steps and verify afterwards.
2. **Console password and SSH.** The sticker password, SSH enabled in the console settings
   (or I enable it over the API once logged in), and the SSH password. Put them in a file
   outside the repo, for example `~/.config/deepracer/env` with `DEEPRACER_IP`,
   `DEEPRACER_PASSWORD`, `DEEPRACER_SSH_USER`, `DEEPRACER_SSH_PASSWORD`. I read it from
   there and never copy it anywhere.
3. **A stand** so the car can run wheels-off for the contract suite, and later a 2x2 m pen
   with a low lip for the beats.
4. **Audio choice:** laptop or booth speaker for v1 (recommended), or a USB speaker for the
   car. A push-to-talk headset for the laptop either way.
5. **Spare drive battery** and the compute battery charged for test sessions.

### B. Accounts and services

1. **AWS profile `heisenberg`** with Bedrock model access enabled in us-east-1 for Nova
   Sonic 2.5, Nova Pro and a Claude model for the look tool. I verified the profile works;
   the model-access list is checked in section 9.
2. **GitHub:** permission to create `Vivek0712/strands-robots-deepracer` (public or
   private, your choice) and to push branches and open PRs on your `robots` and
   `strands-decider` forks.
3. **Permission to turn this directory into its own git repository** (`git init` inside
   `~/strands-robots-deepracer`) so it is a clean repo and not part of the HOME repo.
4. **KrewHQ hub:** start the EC2 pilot hub (costs while running) or approve a local Docker
   hub. Also confirm the org map should get a `deepracer` project with the four teams.

### C. Decisions

1. Confirm the seven beats of report 11 as the scope, and the fork-and-pin policy of
   section 6.
2. Standalone portal (recommended) versus extending the upstream dashboard.
3. Repo visibility and whether the recorded beats and frames may be committed (frames of
   people never are).

### D. Standing permissions for autonomous work

1. SSH into the car, install `ros-jazzy-rosbridge-suite` (or Foxy equivalent), open port
   9090, install the deadman node as a systemd unit, and restart `deepracer-core`. These
   modify the car; I will keep a rollback script and never touch calibration without asking.
2. Run long-lived local processes: portal server, decider server, fake car, rosbridge client.
3. Create branches and PRs on the three forks and pin the project to them.
4. Drive the car wheels-off without asking each time; on the floor only when you are present.

### E. Not needed from you

Nothing on the car's compute beyond rosbridge and the deadman node; no GPU; no Node at show
time; no AgentCore for the motion loop.

## 9. Pre-verified on this machine (2026-10-12)

See the verification block appended below after the checks ran.

Verified 2026-10-12 on this Mac:

| Check | Result |
|---|---|
| GitHub CLI | logged in as Vivek0712, https protocol |
| AWS profile `heisenberg` | account `<redacted>`, IAM user heisenberg |
| Bedrock us-east-1 model list | `amazon.nova-2-5-sonic`, `amazon.nova-2-sonic-v1:0`, `amazon.nova-pro-v1:0`, `amazon.nova-2-lite-v1:0` present (listed, access to be confirmed by a first call) |
| KrewHQ spoke CLI (optional maintainer tooling) | installed locally; token configured |
| KrewHQ hub EC2 `<redacted>` (optional) | state running, but HTTP to port 8443 does not connect; diagnosed below |
| Docker | 28.3.2 |
| Node / npm | v22.13.1 / 10.9.2 (for building the portal frontend) |
| Python / uv | 3.12.11 / 0.7.19 |
| Decider weights in HF cache | 2B hobson v19, v21; Gemma 4 E4B v1-2610; Qwen3.5-2B-Base |
