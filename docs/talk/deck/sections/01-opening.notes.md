# Section 01 — Opening: sources and speaker notes

Written 2026-10-17. Six slides: title, speaker, Strands big picture, timeline, contributor, agenda.

## Assets (all fetched with curl, HTTP 200, sizes on disk)

| File | Source URL | Status | Bytes |
|---|---|---|---|
| `assets/logos/strands-wordmark.svg` | https://strandsagents.com/latest/assets/wordmark-github-dark.svg (linked from the strands-agents/harness-sdk README) | 200 | 2086 |
| `assets/logos/strands-mark.svg` | https://strandsagents.com/latest/assets/logo-github.svg | 200 | 1175 |
| `assets/logos/aws-hero-ai.svg` | https://builder.aws.com/assets/Hero_AI_Dark-DHxxTUMe.svg (the AI Hero badge the AWS Builder Center renders on https://builder.aws.com/community/@vivekraja; white fill, for dark backgrounds) | 200 | 10684 |
| `assets/logos/guinness-world-records.svg` | https://upload.wikimedia.org/wikipedia/en/f/f4/Guinness_World_Records_logo.svg (hosted on en.wikipedia, not Commons: the file page says it was deleted on Commons because it is PD/ineligible for copyright in the US but not in its source country; licence tag PD) | 200 | 10938 |
| `assets/logos/aws-ug-madurai.png` | https://awsugmdu.in/assets/logo-Tx1zCSPp.png (the logo asset referenced by the site's JS bundle at https://awsugmdu.in/assets/index-CVxutsBz.js) | 200 | 79375 |
| `assets/logos/aws-reinvent.png` | https://d1.awsstatic.com/onedam/marketing-channels/website/aws/en_US/events/approved/images/26fb240213f80570ec3ab8d25f2f82bc-aws-reinvent-2024-logo-white-2332x508.37b8fa7e0510491da7b3fe78658eed07152373ab.png (referenced by https://reinvent.awsevents.com/; the white "AWS re:Invent" wordmark, no year in the artwork) | 200 | 24053 |
| `assets/logos/aws-mark-builder-center.svg` | https://builder.aws.com/assets/logo-light-mode-Dbm9pHGK.svg (the only logo file builder.aws.com serves; it is the `aws` smile mark with alt text "AWS Builder Center", dark fill, so the slide inverts it with a per-element filter and adds a `.pill` text badge "AWS Builder Center") | 200 | 3530 |
| `assets/01/strands-agents-github-avatar.png` | https://github.com/strands-agents.png (organisation avatar, 460x460) | 200 | 3883 |

Logo fetch attempts that failed or were not usable:
- https://strandsagents.com/latest/assets/logo.png — 404.
- https://upload.wikimedia.org/wikipedia/commons/8/8c/Guinness_World_Records_logo.svg — 404; Commons has no GWR logo (API title lookups for five spellings all "missing"), hence the en.wikipedia PD file above.
- AWS Heroes programme page https://aws.amazon.com/developer/community/heroes/ (200) is a JS app that exposes only an OG banner; the badge was taken from the Builder Center profile instead.
- https://builder.aws.com has no "Builder Center" wordmark file (bundle grep), hence the pill.
- The re:Invent 2026 nav logo (RIV-navlogo-v2, 266x55, dark text) is too small and dark-on-light; the white wordmark PNG was used.

## Facts and their sources

### Strands Agents
- Open-sourced 16 May 2025: AWS Open Source Blog, "Introducing Strands Agents, an Open Source AI Agents SDK", Clare Liguori, https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/ ; same date on https://strandsagents.com/blog/introducing-strands-agents/ . Production users named at launch: Amazon Q Developer, AWS Glue, VPC Reachability Analyzer. Launch contributors: Accenture, Anthropic, Langfuse, mem0.ai, Meta, PwC, Ragas.io, Tavily. The "two strands of DNA: model and tools" naming is from the same post.
- Python v0.1.0 tagged 2025-05-16: GitHub releases API for strands-agents/harness-sdk (the repo formerly `sdk-python`; `repos/strands-agents/sdk-python` redirects to `harness-sdk`).
- 1.0 on 15 July 2025: AWS Open Source Blog, "Introducing Strands Agents 1.0: Production-Ready Multi-Agent Orchestration Made Simple", Ryan Coleman and Belle Guttman, https://aws.amazon.com/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/ (four primitives: agents-as-tools, handoffs, swarms, graphs; A2A; SessionManager; async `stream_async`). Release python/v1.0.0 published 2025-07-15 (Swarm orchestrator PR #416 in the notes).
- Hooks and Graph: python/v0.3.0, 2025-07-11 ("Implement the core system of typed hooks & callbacks" #304; "introduce Graph multi-agent orchestrator" #336).
- Interrupts: python/v1.13.0, 2025-10-17 ("hooks - before tool call event - interrupt" #987); v1.14.0 (2025-10-29) release notes section "Interrupting Agents".
- BidiAgent (voice, experimental) and Steering (experimental): python/v1.19.0, 2025-12-03 release notes. Bidi agents GA: https://strandsagents.com/blog/bidi-agents-now-ga/ dated 5 Oct 2026.
- Plugins: python/v1.28.0, 2026-02-25 ("add Plugin Protocol for agent extensibility" #1733).
- Interventions: python/v1.44.0, 2026-06-16 ("port HumanInTheLoop vended intervention to Python" #2750); typescript/v1.6.0 same day ("add Cedar vended intervention handler" #2365); steering intervention handler docs 2026-06-12 (#2624).
- TypeScript SDK: sdk-typescript v0.1.0 2025-12-03; v1.0.0 2026-04-30; blog https://strandsagents.com/blog/strands-agents-typescript-v1/ 30 Apr 2026.
- Agent SOPs: https://strandsagents.com/blog/introducing-strands-agent-sops/ 20 Nov 2025 (repo strands-agents/agent-sop created 2025-11-05).
- Strands harness: harness-python/v0.1.0, harness-typescript/v0.1.0, harness-cli/v0.1.0 all published 2026-09-21; blog https://strandsagents.com/blog/introducing-strands-harness/ 21 Sep 2026.
- Harness Optimizer: https://strandsagents.com/blog/introducing-harness-optimizer/ 10 Jul 2026.
- Latest SDK: python/v1.61.1 published 2026-10-15 (GitHub `releases/latest`). harness-sdk stars 8842, Apache-2.0 (GitHub API, 17 Oct 2026). "60 Python minor releases since 1.0": the feed runs v1.1.0 through v1.61.0 but v1.49 was never published, so sixty tags (reviewer recount, 17 Oct 2026; the first draft said 61).

### Strands Labs
- Launched 23 Feb 2026: AWS Open Source Blog, "Introducing Strands Labs: Get hands-on today with state-of-the-art, experimental approaches to agentic development" (Joy Chakraborty, Alessandro Achille, Arron Bailiss, Andrew Shamiya, Belle Guttman, Ryan Coleman), https://aws.amazon.com/blogs/opensource/introducing-strands-labs-get-hands-on-today-with-state-of-the-art-experimental-approaches-to-agentic-development ; launch projects Robots, Robots Sim, AI Functions; "without coupling experiments to the Strands SDK and its production use release cycle".
- strands-labs/robots created 2026-02-19; releases v0.3.8 (2026-02-23) to v0.5.3 (2026-10-07). strands-labs/robots-sim created 2026-02-19; ai-functions 2026-02-10; strands-for-cosmos 2026-06-12 (GitHub API).
- Strands Decider: repo strands-labs/strands-decider created 2026-09-29; announcement https://strandsagents.com/blog/introducing-strands-decider/ 1 Oct 2026; Gemma 4 models post 15 Oct 2026.
- Strands Box: repo strands-agents/box created 2026-10-02 (note: under strands-agents, not strands-labs); v0.1.0 published 2026-10-07; blog https://strandsagents.com/blog/strands-box-the-big-picture/ 7 Oct 2026 (developer preview, macOS on Apple silicon, Rust, Dogwood policies).
- stan: strands-agents/stan exists (created 2026-07-30) but is a PRIVATE repository, so no date or description is on any slide. The speaker's Builder Center headline lists "stan" among his Strands projects; the slide does not claim it.

### Speaker (verified)
- AWS Hero since 2021; AI Hero; leads AWS User Group Madurai; "80+ conference talks, including AWS re:Invent 2024 and 2025, with an upcoming session at re:Invent 2026"; research papers and patents in agentic AI, physical AI and IoT; Strands and OpenClaw contributions: https://builder.aws.com/community/@vivekraja (the old URL https://aws.amazon.com/developer/community/heroes/vivek-raja/ 301-redirects there).
- Named a Machine Learning Hero, Madurai, India, in the November 2021 cohort: https://aws.amazon.com/blogs/aws/meet-the-latest-aws-heroes-november-2021
- re:Invent 2026 dates 30 Nov - 4 Dec 2026, Las Vegas: https://www.aws.amazon.com/events/reinvent/
- microvm-ctl: https://github.com/Vivek0712/microvm-ctl public, Apache-2.0, created 2026-09-13, README verified locally at ~/microvm-ctl/README.md (PyPI `microvm-ctl`, `mvm` CLI, Step Functions and Lambda durable functions leases).
- Curiosity example: `examples/rosbridge/curiosity_agent.py` in strands-labs/robots, landed with PR #1110 (GitHub code search).

### Speaker (per speaker, unverified online; phrased carefully on the slide)
- "Youngest ever" AWS Hero: not stated on any AWS page found. Dropped from the slide in review (length); say it if you like.
- re:Invent 2026 session code COM305: not found in web search; the Builder Center profile confirms only "an upcoming re:Invent 2026 session". On the slide as "my 2026 session is COM305", in the first person, and the slide footnote says the session code is the speaker's own account.
- AWS Think Big (APJ) Award 2024 at re:Invent 2025, AWS Hero of the Year (APJ) 2024 at re:Invent 2024, Invent and Simplify Award at AWS Community Leaders Summit 2022: no public source found.
- AWS User Group Madurai "Best UG" nominations 2022-2025: no public source found; the group and his lead role are verified. Dropped from the slide in review (length).
- Guinness World Record holder: only self-published profiles (Weekday) repeat it; no GWR listing found. Kept because the speaker asked and the logo is a PD text logo; the record itself is not named on the slide, the bullet is in the first person ("my shelf") and the footnote labels it the speaker's own account.
- Multi-cloud certified, IIM Bangalore paper, exactly two patents, 80+ hackathons, mentor/blogger/content creator: per speaker (profile confirms "papers and patents" without counts). Dropped from the slide in review (length); the hobbies line stays.
- Review rule applied to slide 2 (17 Oct 2026): everything unverifiable is phrased as the speaker's own statement (first person) and a `.small` footnote separates what the Builder Center page confirms from what is "my own account".
- NASA JPL appreciating the Curiosity example: per speaker, kept in the notes only.

### Contributor slide (GitHub search API, `gh search prs --author Vivek0712`, 17 Oct 2026)
Merged: strands-labs/robots #995, #1110, #3205, #3206, #4175, #4176, #4177, #4232, #4270 (9); strands-labs/strands-decider #10; strands-agents/harness-sdk #4631; aws-samples/sample-OpenClaw-on-AWS-with-Bedrock #16; aws/aws-durable-execution-sdk-python #771. Total 13 merged across five repos. Re-verified per PR with the GitHub pulls API on 17 Oct 2026 (merged_at: #995 2026-07-02, #1110 2026-07-31, #3206 2026-09-05, #3205 2026-09-17, #4175-#4177 and #4232 2026-09-29, #4270 2026-09-30, decider #10 2026-10-03, harness-sdk #4631 2026-09-28, OpenClaw #16 2026-02-19, durable #771 2026-10-16).
Open: strands-decider #28, #30, #67; harness-sdk #4632. Closed unmerged: robots #1035 (AckermannRosRobot), #1722, #3212, #4573; strands-decider #23, #29, #31, #32, #33; harness-sdk #378, #381; strands-agents/stan #92; strands-agents/box #19; aws-durable-execution-sdk-python #775.
AckermannRosRobot in upstream main came from PR #2689 (merged 2026-08-24 by cagataycali), confirmed with `git log -S` in ~/Documents/strands-0.5x/robots; #1035 was closed the same day, so the slide says "the same day", not "later".

## Speaker notes per slide

1. Title. Thirty seconds. Name the promise: control, simulate, train, with natural language. Say the safety line once: physics stops the car; the decider explains.
2. Speaker. Under two minutes, bullets stage one by one. Make the COM305 plug and move on. Do not read the hobbies; let the room read them.
3. Big picture. The one idea: the model drives the loop, Strands connects it to tools. Launch date 16 May 2025, 1.0 on 15 July 2025, 1.61.1 this week. Everything later in the talk is a tool, a harness or a guard around that loop.
4. Timeline. Two staged blocks (2025, then 2026), not fourteen key presses. Top row fast; bottom row slow: Labs (robots), interventions (the gate), harness (race engineer), Decider (explainer), Box (sandbox). Each gets its own section. Not shown on the slide: Harness Optimizer (10 Jul 2026), Strands Evals and ToolSimulator, Decider Gemma 4 models (15 Oct 2026).
5. Contributor. Credibility, not a victory lap: thirteen merged PRs across six repos; the Curiosity rosbridge example is the memorable one. Do not mention stan.
6. Agenda. Read it as a story. Warn that the demo is live and that a sudden stop is the physical safety layer doing its job.

## For the merge
- The fragment carries a `<style>` block scoped with the `oa-` prefix (title background animation, agenda bars, small layout tweaks). Keep it with the fragment.
- All asset references are relative (`assets/logos/...`, `assets/01/...`), so the assembled deck must sit in `docs/talk/deck/`.
- Slide 2 turns `aws-mark-builder-center.svg` white with a `brightness(0) invert(1)` filter on `.oa-who .logo-row img.oa-invert` because the file is dark-on-light; the selector must outrank the framework's `.logo-row img { filter: drop-shadow(...) }`, which silently overrode the first draft's `.oa-invert` rule and left the mark near-black.
- `.reveal` is used on bullets, the two timeline year blocks, cards and agenda rows (the first agenda row is shown at once), so no slide stages more than six items; the `a` key in framework.js reveals a whole slide at once.

## Review (section A reviewer, 17 Oct 2026)
- Re-verified against GitHub and the blogs: every release tag date on the timeline, the three AWS blog dates, the seven strandsagents.com post dates, the November 2021 ML Hero cohort post, every PR number and merge state on slide 5. One correction: 61 minor releases became 60 (v1.49 was skipped).
- Slide 2 rewritten in the first person with a footnote separating verified items from the speaker's own account; per-speaker extras dropped for length (listed above).
- Slides 2, 3, 4 and 5 trimmed to roughly 90 body words; timeline labels raised from 16 to 18 px; timeline staged as two blocks, agenda as six.
