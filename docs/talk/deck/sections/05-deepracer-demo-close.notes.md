# Section 05: DeepRacer, the showcase, the demo, the close (12 slides)

Written 2026-10-17. Every fact on the slides traces to one of the sources below. Items the
speaker supplied that could not be verified online are marked "per speaker" and phrased that way
on the slide or kept in the notes.

## Sources fetched (URL, what it confirmed)

Official AWS DeepRacer
- https://aws.amazon.com/deepracer/ : "a fully autonomous 1/18th scale race car driven by
  reinforcement learning"; 3D racing simulator; "now available as an open-source product that
  customers can deploy in their own AWS accounts". Image downloaded:
  `assets/05/deepracer-car-official.png` (932x650 PNG, 557 KB, from
  d1.awsstatic.com/.../ba8a00817019d843f21a6e39c78d8159...png).
- https://press.aboutamazon.com/2018/11/aws-announces-the-deepracer-league-drl : dateline
  "SEATTLE--(BUSINESS WIRE)--Nov. 29, 2018"; "launched the AWS DeepRacer League (DRL), the first
  global, autonomous racing league, open to everyone"; "Starting in early 2019, 20 AWS Summits
  worldwide will host a DeepRacer series tournament"; "1/18th scale AWS DeepRacer car driven by a
  reinforcement learning model built in Amazon SageMaker".
- https://aws.amazon.com/blogs/machine-learning/aws-deepracer-evo-is-coming-soon-enabling-developers-to-race-their-object-avoidance-and-head-to-head-models-in-exciting-new-racing-formats
  (2 Dec 2019): stereo camera + LIDAR on Evo; "Stereo cameras allow the car to detect the distance
  to an object"; object avoidance and dual-car head-to-head races; "My Garage" console section;
  "updated reward functions". Images downloaded: `assets/05/deepracer-evo-official.png` (250x174,
  55 KB, not used on a slide, kept as a spare) and `assets/05/deepracer-console-my-garage.jpg`
  (400x531, 26 KB, the garage sensor diagram, slide 2).
- https://aws.amazon.com/blogs/machine-learning/aws-deepracer-device-software-now-open-source/
  (27 Apr 2021, David Smith): "Ubuntu-based computer on wheels powered by the Robot Operating
  System (ROS)"; the device software is open source. Its screenshots are terminal captures, not
  used.
- https://docs.aws.amazon.com/deepracer/latest/developerguide/what-is-deepracer.html (now the
  "DeepRacer on AWS" implementation guide, publication date September 2026): "educational
  ecosystem built around a fully autonomous 1/18th scale race car driven by reinforcement
  learning"; train and evaluate in the simulator; "download your trained models for deployment to
  your AWS DeepRacer vehicle"; "Provides option to customize reward function"; built on Amazon
  SageMaker AI; source at github.com/aws-solutions/deepracer-on-aws.
- https://github.com/aws-deepracer/aws-deepracer (README): "The AWS DeepRacer Evo vehicle is a
  1/18th scale Wi-Fi enabled 4-wheel ackermann steering platform that features two RGB cameras and
  a LiDAR sensor". Image downloaded: `assets/05/deepracer-circle-sticker-official.png`
  (media/deepracer_circle_sticker.png, 900x900, 60 KB, slide 8).
- Evo launch date cross-check: the AWS What's New post of 1 Dec 2019 and TechCrunch coverage
  surfaced by search; the blog above is the cited source.

The speaker's own repos and this project's research bundle
- `~/strands-robots-ros2` (github.com/Vivek0712/strands-robots-ros2, v0.1.0, first commit
  2026-06-25): README "Mars Curiosity Rover Agent", "Believed to be the first Amazon Nova-driven
  NASA Curiosity Mars rover", teleop `move` and Nav2 `navigate_to`, rosbridge runtime. Media
  copied: `assets/05/curiosity-rover-agent.gif` (1.0 MB, CC BY-NC-ND 4.0 by Vivek Raja per
  assets/MEDIA-LICENSE.md; attribution on the slide), `assets/05/deepracer-phase1-http-demo.gif`
  (2.0 MB, from strands-agentic-deepracer, the speaker's own), `assets/05/curiosity-rover-web-ui.png`
  (1.3 MB, spare, not on a slide). NASA/JPL-Caltech own the Curiosity meshes (third-party sim
  mark-gl/curiosity_mars_rover_ws); the repo states NASA is not affiliated.
- `docs/context/07-prior-github-use-case-work.md`: repo dates (aws_deepracer_control_v2
  2021-02-21 to 2021-11-01, MIT; strands-agentic-deepracer 2026-03-10 to 2026-03-17), the three
  phases plus voice and MCP, measured constants (FWD_THROTTLE 0.30, TURN_THROTTLE 0.20,
  STEER_ANGLE 0.50, min turn radius 0.28 m, skid speed 1.5 m/s), `_move_for_duration` sleep and
  stop, `DeepRacerTool(AgentTool)`, `safe_continue()` fail-open, `success: true` on dropped moves.
- `docs/dev/absorbed-from-prior-repo.md`: "36 items absorbed or already present, 11 dropped";
  the dropped list; 2 s hop cap from `Calibration.max_duration_s`.
- `docs/context/04-prior-local-work.md` (via the project memory excerpt): upstream PR #995 merged
  2026-07-02, #1110 merged 2026-07-31 ("rosbridge transport ... NASA Curiosity Gazebo verified
  live"), #1035 closed and re-landed as #2689 on 2026-08-24, #1722 re-landed as #2696 with
  Co-authored-by.
- `docs/context/11-final-use-cases.md`: council verdict 2026-10-12; the seven beats table; the
  booth and recorded beats; the "decider is the explanation layer, not the safety layer" blind
  spot; "One spine, many beats"; strands-decider PR #10 merged 2026-10-03, PR #67 opened
  2026-10-12.
- `docs/context/12-architecture.md`: where things run, the diagram, stop paths table, physical
  safety row, Box egress note.
- `docs/dev/CONTRACTS.md` section 3: the deadman rule (300 ms gap, latched until 1 s of
  heartbeats, re-zero of non-zero manual_drive while tripped, LED red via
  /servo_pkg/set_led_state), ports 9091 / 8090 / 8111 / 8765, STRANDS_ROS2_COMMAND_ALLOW.
- `docs/results/wheels-off-2026-10-14.md`: section 11 evening numbers (stop() to PWM neutral
  34.8 ms; stop_all() barge-in 22.4 ms; heartbeat cut to deadman tripped 293.6 ms; heartbeat cut to
  PWM neutral 278.3 ms; morning 233.8 / 266.4 / 306.5 ms); section 10 first publish to PWM 47 ms
  (was 442); section 6 root cause (rosbridge_action 200 ms post-advertise sleep); the 100 Hz
  on-car sampler method and the one-way correction 2.6 to 16.5 ms.
- `docs/results/beats-car-2026-10-15-person-gate/README.md`: gate 681 to 727 ms per hop,
  envelope 225 to 252 ms, frame 429 to 475 ms, person denied in 456 ms at p 0.9485, decider
  `strands-decider-2B-qwen3.5-v1-2610`, Nova Pro, first ask 1978 ms and the warm() fix.
- `docs/results/five-use-cases-2026-10-15.md`: sim 7/7 (Pre-flight 1.3 s, Deny person_in_frame
  0.97, barge-in to stop 1 ms, trip 296 ms, re-arm 1.6 s); car (Pre-flight 4.2 s, three hops
  denied 0.95, trip 272 ms, re-arm 1.4 s); Pit Stop read-only "offset of 6000"; Two Bodies stop
  all 2 ms; Blindfold, Sign, Red Light on the car pending a clear pen.
- `src/deepracer_agent/`: `gate.py` GateMode enforce | advisory | off; `voice.py` on
  `strands.bidi`, model id `amazon.nova-2-5-sonic`, `BargeInStop` hook; `showtools.py` remember /
  recall / metrics / blink_led; `tools.py` LED service; `portal/frontend/src` views Stage,
  Operator, Settings; `portal/backend/narrator.py` Narrator. Git log: portal starts in advisory
  (commit 48338d8), the rover speaks its line on each verdict (58b5b98).

Hackathon and community
- https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/agent-experience-hackathon
  (fetched 2026-10-17): "Agent Experience Hackathon: Strands Decider"; About: "Build a working
  agent on AWS that does something cool, using Strands Decider 2B"; start 16 Oct 2026 12:00 AM
  PDT; submission deadline 23 Oct 2026 11:59 PM PDT; Gate 1 week of 26 Oct, Gate 2 week of 2 Nov,
  winners week of 9 Nov; three winners each $5,000 in AWS credits + swag bundle ~$600 (jacket,
  backpack, keyboard) + certificate; pool $16,800; eligibility 18+ with a Builder Center profile;
  submission requirements (agent with Decider 2B + Bedrock, Builder Center article, public repo
  with a reusable decision pattern, demo video under 3 minutes, tags #strands-decider-2b plus one
  pattern tag); judging 30 / 30 / 25 / 15. Cover image downloaded:
  `assets/05/agent-experience-hackathon-cover.webp` (1200x675, 18 KB, from
  prod-assets.cosmic.aws.dev/a/3KT86eQ8bTEDF7DP5exvjYdbCzb/aws-.webp). The same URL is the
  `bannerImage` of the user group's hackathon record, so it is the official poster.
- https://builder.aws.com/content/3KOe6GhV7Wbo4n6LZdbHCw6S4hW/aws-agent-experience-hackathon-2026-win-aws-swag-and-credits
  (community article by Vu Pham, 8 Oct 2026): same prize facts; its hero image downloaded as
  `assets/05/agent-experience-hackathon-hero.webp` (1305x398, 11 KB, spare, not on a slide).
- https://www.awsugmdu.in/hackathons/hack-1791983611639-283032ee : the page is a JavaScript
  app; its data comes from
  https://2q4zt5zl9e.execute-api.us-east-1.amazonaws.com/dev/hackathons/hack-1791983611639-283032ee
  (public, fetched 2026-10-17): title "Agent Experience Hackathon: Strands Decider", description
  "Build a working agent on AWS that does something cool, using Strands Decider 2B to make a
  meaningful decision, for a chance to win $5,000 in AWS credits and an AWS Builder swag bundle",
  startDate 2026-10-16, submissionDeadline 2026-10-23, prizes "$5,000 in AWS credits and an AWS
  Builder swag bundle", kit enabled with apiKeys true, teams 1 to 3, participants 39, teamCount 18
  (updatedAt 2026-10-16), skills Python / Strands / Decision Models / LLM, bannerImage as above.
  The site has no separate poster beyond that banner.
- https://www.meetup.com/aws-user-group-madurai/events/317006753 : "Builders Skill Sprint -
  Strands Month", Sunday 18 October 2026, 10:00 AM IST, online, hosts Poobalan P. and 2 others;
  description matches the LinkedIn post text the speaker gave, word for word, including "Three
  winning teams will each receive $5,000 in AWS credits and an AWS Builder swag bundle." Event
  image downloaded: `assets/05/meetup-skill-sprint-event.jpeg` (360x203, 8 KB; the larger size
  was not served).
- lnkd.in resolution (curl, 2026-10-17): https://lnkd.in/gqeUhPM7 interstitial points to
  https://www.meetup.com/aws-user-group-madurai/events/317006753 ; https://lnkd.in/gA4HnPFX points
  to https://awsugmdu.in/hackathons .
- https://builder.aws.com/community/@vivekraja : "Vivek Raja P S"; About text "Senior AI
  Solutions Architect at Aivar Innovations, an AWS partner company. He is an AWS AI Hero and leads
  AWS User Group Madurai."; links GitHub github.com/Vivek0712 and LinkedIn
  linkedin.com/in/meetvivekraja; no X handle listed (re-checked 2026-10-17 by the reviewer).
- https://www.awsugmdu.in : JavaScript app; team data endpoints are 403, so no organizer handles
  could be read from the site.

## Not verified online (per speaker, or placeholders)
- "NASA JPL appreciated it" (slide 3): per speaker; the slide says "(per speaker)".
- The $25 AWS credits photo offer (slide 11): per speaker; mechanics (tag, platform, deadline,
  how the winner is picked) are not defined anywhere. Decide before the talk.
- X handle (slide 11): placeholder "[SPEAKER: add X handle or delete this line]".
- "Tomorrow's virtual session" (slide 11) assumes the talk is on Saturday 17 Oct 2026. The "an hour
  from your first Strands Decider call to a hackathon submission" line paraphrases the Meetup
  description's opening "Got an hour? Build an AI agent. Submit a hackathon entry."
- Slide 11's $25 line now says "from me personally (my offer, not AWS's)" so nobody reads it as an
  AWS programme.
- Blindfold, Sign and Red Light have passed on the sim but not yet on the car (pending a clear
  pen at the time of writing); slide 7's notes say how to answer if asked.
- No official logos were fetched for this section; the thank-you slide uses `.pill` text badges.

## Speaker notes per slide
Each slide carries the same notes in its `<aside class="notes">`; summary here.

1. What is AWS DeepRacer: 1/18th RL car, league 29 Nov 2018 with 20 Summits in 2019, Evo stereo
   + LiDAR Dec 2019, device software open source Apr 2021 ("Ubuntu-based computer on wheels powered
   by ROS"). The stage car is hardware R2.1, stock image, mono camera, no LiDAR.
2. How it used to run: reward function, train in the simulator, download to the car; "DeepRacer
   on AWS" open-source solution on SageMaker AI (Sept 2026 guide); "My Garage". The last bullet
   (no way to ask why or say no) is your framing.
3. Journey: 2021 HTTP client fork; Mar 2026 five phases in a week; Jun 2026 Curiosity repo, Jul
   2026 PR #1110; Aug to Oct 2026 Ackermann upstream and decider PR #10; Oct 2026 the showcase
   (council 12 Oct, wheels-off numbers on the car 14 Oct, sim beats 15 Oct). "NASA JPL appreciated
   it" is per speaker.
4. First attempt: fail-open `safe_continue()`, sleep-and-stop with no watchdog, custom AgentTool
   and a y/yes REPL that was theatre; kept the constants, MJPEG parser and validator; 36 absorbed,
   11 dropped.
5. Architecture: Bedrock (Nova Pro, Nova Sonic) -> Strands Agents tools -> Decider gate (two
   questions, four verdicts, three modes) -> strands-robots gate + driver over rosbridge -> car;
   Bidi voice with BargeInStop; Pit Wall portal Stage / Operator / Settings; Box optional; on-car
   deadman; physics row. End on the safety line.
6. Safety layers with numbers: pen and 2 s cap; first publish 47 ms; deadman 278 ms (300 ms
   rule); barge-in 22 ms, operator stop 35 ms (were 230 to 270 ms); gate 681 to 727 ms, person
   denied in 456 ms at p 0.95; the marshal's thumb.
7. Seven beats: what each shows; sim 7/7 on 15 Oct; car results and what is still pending.
8. Live run order: Pre-flight, manoeuvre, metrics, LED, remember my name, Blindfold, foot in
   frame. Gate to enforce before the last two. Push-to-talk. Nobody in frame.
9. Takeaways: physics stops / decider explains; deadman on the body; fail closed; measure on the
   device's clock (the library settle cost about 200 ms: 233.8 to 34.8 ms); one spine, many beats.
10. Hackathon: dates, prizes, judging, the Sunday session, the three links.
11. Connect and offer: $25 credits (per speaker, define the mechanics), tomorrow's session,
    handles from Builder Center, X placeholder.
12. Thank you: likely questions and their answers.

## Review log (2026-10-17, section reviewer)
Re-verified by fetching the sources again: league press release (Seattle, 29 Nov 2018, "first
global, autonomous racing league", 20 Summits, 1/18th); Evo blog (2 Dec 2019, stereo cameras,
LIDAR, object avoidance, head-to-head, "My Garage"); open-source blog (27 Apr 2021, David Smith,
"Ubuntu-based computer on wheels powered by the Robot Operating System (ROS)"); Builder Center
hackathon page (16 Oct 12:00 AM PDT to 23 Oct 11:59 PM PDT, three winners, $5,000 credits + ~$600
swag, pool $16,800, judging 30/30/25/15); awsugmdu.in hackathon API record (same title, dates,
prizes, kit with API keys, 39 participants, 18 teams); Meetup 317006753 (Sunday 18 October 2026,
10:00 AM IST, online, hosts Poobalan P. and 2 others, $5,000 line, free API access, Kiro
workflow); lnkd.in/gqeUhPM7 -> the Meetup event and lnkd.in/gA4HnPFX -> awsugmdu.in/hackathons;
Builder Center profile (name, About text, GitHub, LinkedIn, no X). Repo files re-read:
wheels-off-2026-10-14.md sections 6, 10, 11 (34.8 / 22.4 / 278.3 / 293.6 / 47 ms; morning 233.8 /
266.4 / 306.5), beats-car-2026-10-15-person-gate/README.md (681-727, 225-252, 429-475, 456 ms at
p 0.9485), five-use-cases-2026-10-15.md (sim 7/7; car Pre-flight 4.2 s, three hops denied 0.95,
trip 272 ms, re-arm 1.4 s; Blindfold, Sign, Red Light pending), 11-final-use-cases.md (the seven
beats, kiosks, recorded beats, the blind-spot quote), absorbed-from-prior-repo.md (36 / 11, 2 s
cap), report 07 (constants, dates, safe_continue, success: true), report 04 (PR numbers and
dates), CONTRACTS.md section 3.

Corrections made: slide 3 "car moved 14 Oct" -> "wheels-off numbers on the car 14 Oct" (the
14 Oct run was on a stand, no free driving); slide 9 "cost 230 ms" -> "A 200 ms sleep hid in a
library" (233.8 -> 34.8 ms is a 199 ms difference); slide 11 $25 offer marked as the speaker's
personal offer on the slide itself; slide 5 Bidi caption no longer claims the hook "stamps both
times" on the slide (kept in the notes). Layout: every slide trimmed to roughly 90 to 115 words of
body text (slides 5, 6 and 7 are diagram and card slides whose labels and screen lines push the
raw count higher); slide 1 hero image capped at 400 px and the track at 200 px so the caption no
longer overlaps the footer; slide 3 timeline items given right padding so the columns no longer
run into each other; slide 7 reveals cut from 8 to 6 (beats 01 and 02 are shown from the start);
slide 10 cover capped at 380 px and the Meetup image reduced to 360 px wide so the column no longer
overflows; the slide-1 car gets a static position on the top of the oval inside an @supports
fallback, so a browser without CSS Motion Path shows a parked car, not a broken layout. Rendered
all 12 slides at 1920x1080 in headless Chrome after the edits: no overflow, no overlaps.
