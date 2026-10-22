# Section B: Physical AI and strands-robots, zero to hero

Fragment: `sections/02-physical-ai.html` (10 slides). Assets: `assets/02/` (41 files: 40 fetched with
HTTP 200 and non-zero size on 2026-10-17, plus one local MP4 transcode; sizes listed at the end).
Nothing is hotlinked. Slides reference 17 of them; the rest are spares kept on disk.

Review pass (2026-10-17, reviewer): every load-bearing number re-fetched; corrections are marked
"(review)" below. Driver count was 17 in the first draft and is 19 at `main`; the Huang quote's
source was mis-cited (techstrong URL is the toolchain article); the AWS blog does not name
strands-robots (the repo README does); the GPU sentence on slide 9 was narrower than the docs.

## Naming note for the merge

The brief asked for the "Physical AI Open Chain Toolkit". No project by that exact name exists on the
web or on GitHub (searched 2026-10-17, exact phrase in quotes, plus GitHub org searches). The very
recent launch that matches the description is the **Physical AI Toolchain on AWS** (blog 7 Oct 2026,
repo `aws-samples/sample-the-physical-ai-toolchain-on-aws`). Slide 8 is written about that, with its
real name. If the speaker meant something else, the slide needs a rewrite; everything on it is
verifiable as written.

## Sources used, and what each confirmed

### strands-labs/robots (official repo), fetched from raw.githubusercontent.com at `main`, 2026-10-17

- `README.md`: the h2 "Control, simulate, and train robots with natural language"; the README
  paragraph "A prompt reaches the agent; the agent calls the robot tool; a policy turns the observation
  into an action chunk; the backend ... executes it"; the "What you get" table (150+ robots across 8
  categories; trainers `lerobot_local`, `cosmos3`, `ppo`/`fast_sac`/`fast_td3`, `sagemaker`; ROS 2 row;
  mesh row); install line `uv pip install "strands-robots[sim-mujoco]"`; Apache-2.0; Python 3.12+.
  The three README SVGs (`hero_loop.svg`, `architecture_flow.svg`, `mesh_network.svg`).
- GitHub API `repos/strands-labs/robots` (2026-10-17): description "Control robots and physical
  hardware with natural language through Strands Agents."; 186 stars; 39 forks; 19 open issues;
  licence Apache-2.0; created 2026-02-19; pushed 2026-10-16; homepage strands-labs.github.io/robots.
- GitHub API releases: 7 releases: v0.3.8 (2026-02-23), v0.4.0 (2026-06-17), v0.4.1 (2026-07-01),
  v0.5.0 (2026-08-04), v0.5.1 (2026-08-06), v0.5.2 (2026-09-17), v0.5.3 (2026-10-07).
- `strands_robots/registry/robots.json`: 77 curated robots; categories arm 23, humanoid 21, hand 9,
  mobile 8, mobile_manip 8, bimanual 5, aerial 2, expressive 1 (8 categories); 39 with a `hardware`
  block. `strands_robots/registry/urdf_robots.json`: 80 entries. 77 + 80 = 157, which is how
  `docs/hooks/facts.py` derives `{{n:robots}}` ("robots.json plus the robot_descriptions URDF tail"),
  and matches the README's "150+".
- `strands_robots/registry/policies.json`: 16 providers (mock, lerobot_local, cosmos3, moveit2, curobo,
  wbc, holosoma, wbc_gait, wbc_latent, kimodo, protomotions, remote, rl, microduck, flux3_action,
  rsl_rl_onnx).
- `strands_robots/drivers/__init__.py` `_SHIPPED_DRIVERS`: 19 entries at `main` on 2026-10-17
  (feetech, dynamixel, franka, g1, go2, reachy, microduck, robotiq, booster, rby1, ur, xarm, kinova,
  kuka, stretch, spot, crazyflie, earthrover, yahboom_m3pro). (review: the first draft said 17.)
- `pyproject.toml`: `requires-python = ">=3.12"` (the "Python 3.12+" pill).
- `examples/rosbridge/curiosity_agent.py` at `main`: `RosbridgeRobot.from_curiosity(host=...)`.
  `strands_robots/drivers/ros/ackermann_robot.py` at `main`: `AckermannRosRobot.from_deepracer(
  node_name="deepracer")`, "converts internally with a bicycle model" to normalized servo pairs.
- `docs/learn/ros2.md`: the three-transport table; `use_ros` actions are `action_send_goal` (Nav2 is
  not named anywhere, so the slide says "actions"). `docs/learn/training/lerobot.md`: GR00T N1.7
  through `lerobot_local`.
- `docs/index.md`, `docs/concepts/architecture.md` ("Registry is the source of truth ... Code reads the
  row; it never hard-codes a robot"; the seven-layer rule), `docs/concepts/glossary.md` (gate,
  transport, twin, interrupt, e-stop, envelope definitions), `docs/concepts/robots.md` (the envelope),
  `docs/learn/agents.md` (the four-step gate order; the allowlist table; the audit row; "There is no
  dry_run flag; the dry run is mode='sim'"), `docs/learn/simulation/index.md` (four backends table:
  mujoco, newton, isaac, mjlab), `docs/learn/training/index.md` (lifecycle validate/prepare/train/
  status/export; `list_trainers()` output; hardware floors), `docs/learn/training/rl.md` (SimEnv,
  VecSimEnv, PPO/FastSAC/FastTD3, `pip install 'strands-robots[rl]'`), `docs/learn/dashboard.md`
  (`strands-robots dashboard --open`, port 8090, five tabs, two e-stops, consent card),
  `docs/start/index.md` (the ladder with times), `docs/start/install.md`, `docs/start/first-robot.md`,
  `docs/start/first-agent.md` ("77 actions"; interrupt `robot-command-approval`),
  `docs/start/first-policy.md` (SmolVLA, 865 MB, 90 steps in 20.8 s on a laptop CPU),
  `docs/start/see-it.md`, `docs/start/teach-it.md` (record, verify, label, train, deploy and measure).
- Repo media used on slides (all under `docs/assets/`, `examples/` of the repo): listed below.

### Local reference documents

- `~/Documents/strands-0.5x/robots-deepdive-docs/` (README, 01, 02, 04, 06; generated 2026-09-04 at
  HEAD 5b4c4552): the 77-action tool spec pinned by test; the sim/hardware/teleop/registry layering;
  the in-process trainer design; the then-missing dashboard server (now shipped at `main`, see slide 6
  notes).
- `docs/context/01-strands-robots-code-deepdive.md` (this repo, worktree at d504fedd, 2026-10-12):
  `_command_gate.py` blocklist and `gate_motion` order, approve vocabulary `y|yes|approve|approved`,
  interrupt ids `use_ros-command-approval` etc., `_hitl_audit.py`, the three ROS transports,
  `AckermannRosRobot.from_deepracer`, `RosbridgeRobot.from_curiosity`.
- `~/strands-robots-ros2` (the speaker's repo, github.com/Vivek0712/strands-robots-ros2, last commit
  2026-06-25): the Curiosity rover over rosbridge in Gazebo; `curiosity_rover.gif` copied to
  `assets/02/` under its CC BY-NC-ND 4.0 note (author Vivek Raja), not placed on a slide in this
  draft; available if the merge wants it on slide 5.

### Physical AI research (web, 2026-10-17)

- NVIDIA glossary "What is physical AI?" https://www.nvidia.com/en-us/glossary/generative-physical-ai/ :
  the definition quoted on slide 1; the three-computer framing (DGX train, Omniverse+Cosmos simulate,
  Jetson Thor run).
- Google DeepMind RT-2 blog, 28 Jul 2023: "Robotic Transformer 2 (RT-2) is a novel vision-language-
  action (VLA) model".
- Physical Intelligence pi0 blog (pi.website/blog/pi0), 31 Oct 2024: "a general-purpose robot
  foundation model that we call pi0".
- NVIDIA press release, GTC 18 Mar 2025: GR00T N1 "the world's first open, fully customizable
  foundation model for generalized humanoid reasoning and skills"; Newton physics engine with Google
  DeepMind and Disney Research; Huang: "The age of generalist robotics is here."
- CES Jan 2025 Huang quote: Fortune video, 8 Jan 2025, "Nvidia CEO says 'ChatGPT moment' for robotics
  is just around the corner", reporting the 6 Jan 2025 keynote line "The ChatGPT moment for general
  robotics is just around the corner." NVIDIA's own Cosmos press release of 6 Jan 2025 quotes him as
  "The ChatGPT moment for robotics is coming." (review: the techstrong URL in the first draft is the
  Oct 2026 toolchain article and carries no Huang quote; citation replaced.) Cosmos announced at the
  same keynote (NVIDIA press release, 6 Jan 2025).
- AWS Strands Agents launch 16 May 2025: The New Stack "AWS launches its take on an open source AI
  agents SDK"; AWS Open Source blog for the 1.0 release confirms "since launching as a preview in May
  2025".
- IFR press release "World Robotics 2025 report: Industrial Robots", Frankfurt 25 Sep 2025:
  542,000 installed in 2024; 4,664,000 operational stock (+9%); Asia 74%; China 295,000; 2025 forecast
  575,000.
- IFR press release "Service Robots See Global Growth Boom", Frankfurt 7 Oct 2025: almost 200,000
  professional service robots in 2024 (+9%); logistics 102,900 (+14%); hospitality >42,000; cleaning
  >25,000; agriculture ~19,500; consumer close to 20 million (+11%). IFR notes figures come from a
  sample of 294 suppliers.
- Humanoids 2025: IDC count of about 18,000 units (Jan 2026, via en.jiemian.com, itbrief.co.uk and
  faxiangongchang.com; the IDC report itself was not opened); Goldman Sachs 15,000-20,000 (Jan 2026
  note via itiger). Secondary reporting of analyst estimates; the slide labels the stat "(analyst
  estimate)", the source "IDC est., Jan 2026, via press", and the small print "analyst estimates
  ... differ by method". Vendor rankings under that total are disputed (Unitree vs AgiBot); not used.

### Physical AI Toolchain on AWS (slide 8)

- AWS Physical AI blog "Introducing AWS Physical AI Toolchain", 7 Oct 2026, authors Abhishek
  Srivastav, Adam Weber, Ali Shahrokni, Steven DeVries, Ignacio Sanchez, Jathavan Sriram; names the
  repo, "a curated collection of reference architectures, Infrastructure as Code, and deployment
  automation", and "an AI-driven orchestration layer built on the Strands Agents SDK". (review: the
  blog does not mention strands-robots at all; every strands-robots quote on slide 8 is from the
  repo README or `strands-agents-on-aws/README.md`, and the slide title says "Strands Agents and
  strands-robots" for that reason. The repo was created 9 Jul 2026, so the slide says "announced"
  on 7 Oct 2026, not "open-sourced".)
- aboutamazon.com "How AWS is helping companies build physical AI machines that think": five pillars;
  SageMaker, EC2 GPU, IoT Greengrass, Bedrock AgentCore; NVIDIA Isaac Sim / Isaac Lab / GR00T / Cosmos;
  customers NEURA Robotics (CEO David Reger quote), RLWRLD, Config.
- GitHub API `repos/aws-samples/sample-the-physical-ai-toolchain-on-aws` (2026-10-17): Apache-2.0,
  56 stars, 18 forks, created 2026-07-09, pushed 2026-10-16. Commits API: the `strands-agents-on-aws`
  component was added 2026-07-29 ("Add Strands Agents agentic orchestration component").
- Repo `README.md`: the one-line description; four pillars plus "Agentic AI Orchestration Layer at the
  center"; component table (Foundation, Cosmos, Isaac Lab, Isaac GR00T, DreamZero, Isaac Sim, OSMO,
  Strands Agents, Isaac Lab Arena preview; Edge Deployment planned); cost table (GR00T full ~$79,
  11 h on ml.g5.12xlarge; Isaac Lab RL ~$10-30; Cosmos 3 Predict ~$37/h).
- Repo `strands-agents-on-aws/README.md`: "the natural-language control plane that ties them together
  and drives the robot at the end of the loop"; "The agent is the feedback arrow of the flywheel";
  AgentCore hosting "Planned"; `pai agent sim --robot so101 --task "pick up the red cube"`.
- Secondary coverage disagrees on the launch date (7, 8 or 12 Oct 2026); the slide uses the AWS blog
  date, 7 Oct 2026.

## Not verified / not claimed

- "Physical AI Open Chain Toolkit" by that name: not found; see the naming note.
- MAVLink: not supported anywhere in strands-robots at `main` (README and file tree searched). Not on
  the slide.
- Gazebo: not a strands-robots backend; appears only on the far side of rosbridge in the Curiosity
  example. Stated that way in the slide-5 notes.
- The docs page `learn/training/index.md` says "the nine trainers" in its description while its fence
  prints eight; the slide says eight (the fence output).
- Huang's exact CES 2025 wording varies by outlet; marked on the slide notes.
- Humanoid shipment counts are analyst estimates relayed by secondary outlets; labelled.
- "The DeepRacer's transport is ROS 2 over rosbridge" (slide 10): this project's own design, per
  CLAUDE.md, not an upstream claim. Per speaker; the card says "in this project" for that reason.
- The slide-9 GPU sentence: install.md says a GPU is "only needed for the Newton and Isaac backends
  and for policy inference at speed", but the simulation table also needs an NVIDIA GPU for mjlab and
  the training floors need one for `lerobot_local` and `cosmos3`, so the slide lists all of them
  instead of calling Newton and Isaac the only places. (review)
- Star and fork counts (186 / 39) are a 2026-10-17 snapshot; re-check the morning of the talk.
- The Curiosity rover example is a control example, not a training example; the brief's suggestion to
  put it on the Train slide was not followed for that reason.

## Speaker notes per slide

1. **Physical AI.** Read NVIDIA's definition, then the one-sentence contrast: a software agent writes
   text, a physical agent writes motor commands and the world grades the answer. Walk the timeline
   left to right: RT-2 named the model class (Jul 2023), pi0 made it a general robot foundation model
   (Oct 2024), Cosmos and GR00T N1 made simulation and synthetic data the training ground (Jan and
   Mar 2025), Strands Agents (May 2025) is the third force, the one this talk uses. Huang's "ChatGPT
   moment" line was a prediction; Fortune's Jan 2026 follow-up says he softened it to "nearly here".
2. **The world.** Four IFR/IDC numbers; do not read forecasts as facts. Then the point of the slide:
   under every body the same five layers are settling (prompt, agent, policy, backend, motor), which is
   exactly the README's architecture sentence, so the SDK is a map of the field, not a product shape.
3. **What strands-robots is.** Amazon-built, Strands Labs org, Apache-2.0, born Feb 2026, seven
   releases, v0.5.3 on 7 Oct 2026. One `Robot()` call, sim by default, `mode="real"` is an explicit
   opt-in ("Real servos never move by accident", README). The four pillars map to the talk title.
4. **The core loop.** The animated highlight walks prompt, agent, gate, transport, robot; the dot is
   the observation returning. Spell the four gate steps in order. Say that the blocklist is about
   physical surfaces, matched on the last path segment, so `/manual_drive`, `/vehicle_state` and
   `/enable_state` cover the DeepRacer. Then the safety line, slowly: the gate explains and asks; the
   pen, the hop cap and the marshal's thumb stop the car.
5. **Transports.** Three ROS wires, one gate. Point at the GIF (an agent driving turtlesim through
   `use_ros`). The thumbnails are registry robots. Mention Curiosity (the speaker's own rosbridge
   demo in Gazebo) and that the DeepRacer bridge is `AckermannRosRobot.from_deepracer()` with a bicycle
   model to a normalised servo pair. Safety line again.
6. **Simulate.** `Robot("so101")` is already a world and a 77-action tool. Four backends. The twin
   definition from the glossary, and the dry-run quote. The dashboard screenshot is the Fleet tab;
   the agent tab puts a consent card in front of any real motion.
7. **Train.** The lifecycle verbs; eight trainers at `main`; imitation vs RL; the flywheel drawing
   is the Teach-it rung (record, verify, label, train, deploy and measure). Close: the same
   `create_policy` call runs the checkpoint in sim and, behind the gate, on the robot.
8. **Toolchain.** Give the real name and date. Four pillars round an agentic centre; the Strands
   component is where strands-robots lives, quoted. The README's own cost table shows what a
   fine-tune costs. The payoff line: a Strands agent in front of a robot is now the published AWS
   reference shape, which is what the DeepRacer section builds on.
9. **Ladder.** Five steps with the real commands; every fence on those pages ran against the commit
   on a laptop with no GPU. `strands-robots doctor` first.
10. **Cheat-sheet.** Six words, read each card's first clause. Hand over with the safety line.

## Assets in `assets/02/` (bytes, source path in strands-labs/robots unless stated)

| file | bytes | source |
|---|---|---|
| hero_loop.svg | 35834 | docs/assets/hero_loop.svg (slide 3) |
| architecture_flow.svg | 28516 | docs/assets/architecture_flow.svg (spare) |
| mesh_network.svg | 34984 | docs/assets/mesh_network.svg (spare) |
| d01_what_is.dark.svg | 86870 | docs/assets/drawings/ (spare) |
| d02_layers.dark.svg | 82574 | docs/assets/drawings/ (spare) |
| d03_same_checkpoint.dark.svg | 83507 | docs/assets/drawings/ (spare) |
| d04_gate_chain.dark.svg | 84525 | docs/assets/drawings/ (spare; the gate drawing) |
| d08_data_flywheel.dark.svg | 81619 | docs/assets/drawings/ (slide 7) |
| d10_agent_and_robot.dark.svg | 82565 | docs/assets/drawings/ (spare) |
| d11_sim_backends.dark.svg | 84801 | docs/assets/drawings/ (spare) |
| d13_trainer_lifecycle.dark.svg | 85488 | docs/assets/drawings/ (spare) |
| d16_ros2_transports.dark.svg | 83471 | docs/assets/drawings/ (spare) |
| use_ros_agent_square.gif | 300058 | docs/assets/img/use_ros_agent_square.gif (slide 5) |
| mujoco-1.webm | 156566 | docs/assets/sim/mujoco-1.webm (slide 6) |
| mujoco-1.mp4 | 126497 | local transcode of mujoco-1.webm (ffmpeg libx264, yuv420p, no audio); slide 6 `<source>` fallback (review) |
| newton-1.webm | 489766 | docs/assets/sim/ (spare) |
| isaac-1.webm | 258798 | docs/assets/sim/ (spare) |
| mjlab-1.webm | 313251 | docs/assets/sim/ (spare) |
| mujoco-1.png | 79216 | docs/assets/sim/ (poster, spare) |
| same-checkpoint-1.png | 99968 | docs/assets/sim/ (spare) |
| first-robot-1.png | 83539 | docs/assets/sim/ (spare) |
| talk-to-it-1.png | 83355 | docs/assets/sim/ (spare) |
| fleet.dark.png | 37221 | docs/assets/dashboard/ (slide 6) |
| agent.dark.png | 45468 | docs/assets/dashboard/ (spare) |
| devices.dark.png | 62603 | docs/assets/dashboard/ (spare) |
| evacuation.gif | 105258 | examples/fleet/assets/ (spare) |
| arm_wave.gif | 205197 | examples/mujoco_gs/assets/ (spare) |
| architecture.svg | 71596 | examples/lerobot/architecture.svg (spare) |
| so100.webp, unitree_g1.webp, unitree_go2.webp, spot.webp, crazyflie.webp, stretch3.webp, shadow_hand.webp, aloha.webp, reachy_mini.webp, yahboom_m3pro.webp | 7024, 10242, 11502, 13106, 4948, 4454, 10250, 16212, 7100, 8208 | docs/assets/img/robots/ (slide 5) |
| toolchain_flywheel.png | 180672 | aws-samples/sample-the-physical-ai-toolchain-on-aws flywheel.png (slide 8; Apache-2.0) |
| toolchain_arch-diagram.png | 865990 | same repo, arch-diagram.png (spare) |
| curiosity_rover.gif | 1009406 | github.com/Vivek0712/strands-robots-ros2 assets/ (speaker's own, CC BY-NC-ND 4.0; spare) |

Note: `.webm` (VP9) plays in Chromium and Firefox and in Safari 14.1+ on macOS 11.3+. Slide 6 now
lists the WebM first and `mujoco-1.mp4` (H.264) as a second `<source>`, so an old Safari or an
Edge/Windows box without VP9 still plays the clip. Verified in headless Chrome 155 on 2026-10-17:
readyState 4, 960x540, playing, no error. The repo ships no MP4; the one here is a local transcode.
