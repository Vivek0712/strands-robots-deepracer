# Repo aesthetics review, round 1 (2026-10-22)

Reviewer: `repo-aesthetics-reviewer` (read-only; this file is the only write). Snapshot: working
tree at 16:10 local, commit `8c320c4` plus uncommitted edits. During the review other agents edited
`README.md:285`, `.krewhq/README.md`, `docs/article/img/MANIFEST.md` and
`docs/context/00-README.md:97`; findings below were re-checked against the versions on disk at
16:15, so three earlier findings (EC2 ids in `.krewhq`, `fig-car-hop.gif` named in the manifest,
the "plaintext passwords sit in" wording) are already gone and are not listed.

Method: `README.md` rendered with Python-Markdown (tables, fenced code, md_in_html) inside a copy
of GitHub's markdown-body CSS for light (`#fff`/`#1f2328`) and dark (`#0d1117`/`#f0f6fc`),
screenshot with headless Chrome at 1000 px and 390 px, and read as images. Renders and GIF contact
sheets are in the session scratchpad
`<scratch>/aesthetics/`
(`readme-{light,dark}-{1000,390}.png`, `car-hop-sheet.png`, `pitwall-sheet.png`).

Rubric lines this review serves: B1.4 "Live run, the decision spoken and shown", B3.3 "Hero image,
badges, every rubric section, a notebook, LICENSE, contributor guide", B3.4 "Limits stated
plainly", and the AI scorer's cue list (README headings "The decision handed to Decider 2B",
"Reusable pattern", "Hackathon submission"; "a video link with a stated runtime").

## Findings

| Severity | File:line | Finding | Why it matters for the rubric | Suggested fix |
|---|---|---|---|---|
| HIGH | `README.md:1-29` | The hero has no call to action. Cover, title, tagline, eight badges and two GIFs, then prose. No "Read the article", "Copy the pattern", "Try it in 60 seconds" or "Watch the demo" link above the fold; the first link a judge can click is `strands-labs/robots` at line 32, which leaves the repo. | B3.3 anchors "Title, what it does, quick start, pattern pointer" at 3; the first screen must route the judge to the three things scored. The reviewer brief lists "the three calls to action (article, pattern, quick start) above the fold". | Add one centred line under the badges (line 18): `<p align="center"><a href="#quick-start"><b>Try it in 60 seconds</b></a> · <a href="patterns/strands/README.md"><b>Copy the Decider pattern</b></a> · <a href="docs/article/article.md"><b>Read the article</b></a> · <a href="#hackathon-submission"><b>Watch the demo (coming)</b></a></p>` |
| HIGH | `README.md:22`, `docs/media/car-hop.gif` | The "real car" hero GIF spends its first ~6 of 10 s on the phase-1 "DeepRacer Planner" web UI (dark chat panel, "Plan", "Execute" buttons, "By Vivek Raja P S" footer); the car appears only in the last ~4 s, portrait, pillar-boxed in black (contact sheet frames 0-4 vs 5-7). Frame 0, which every static preview and the GitHub mobile thumbnail shows, is the old UI, not the car. Caption at line 26 is honest ("phase 1 recording") but tells the judge the demo they are looking at is an older stack. | B1.2 "Surprise and delight" and B1.4 "Live run, the decision ... shown": the hero is the one place to show the DeepRacer moving under *this* stack with a verdict on screen. A Planner UI from March undercuts "original agent" (A8) on first glance. | Record a 6-8 s landscape GIF of the real car in the pen with the Pit Wall verdict overlaid (or picture-in-picture), under 3 MB, first frame = the car. Until then, trim `car-hop.gif` to the floor segment only (`ffmpeg -ss 6 -t 4`) and re-encode at 720x405; keep the caption. |
| HIGH | `README.md:294-297` | Two bold `TODO` lines in "Hackathon submission": no article URL, and "Demo video (under 3 minutes): TODO, placeholder: the recording is not made yet; do not treat this line as a link". The brief allows a marked video placeholder, but the phrasing is an internal note, not a reader-facing line. | A4 and A6 are pass/fail gates and the AI scorer keys on "a video link with a stated runtime". A judge who lands before the links are filled sees a draft. | Replace line 294-297 with a two-row table `| Article | Builder Center link, published <date> |` / `| Demo video | <link>, 2:40 |`; until published, use `_(publishing 2026-10-2x)_` and `_(recording 2026-10-2x, under 3:00)_`. Remove the words "do not treat this line as a link". |
| HIGH | `CITATION.cff:16`, `hackathon/SUBMISSION.md:71` | `repository-code: https://github.com/Vivek0712/strands-robots-deepracer` returns HTTP 404 today; `git remote -v` is empty; SUBMISSION has `[REPO URL: pending]`. There is no CI badge because there is no public repo to point one at. | A4 "Repo is public and the link is in the article and the submission form"; B3.3 at 5 expects "badges" that resolve (CI status from `.github/workflows/ci.yml`). Everything in this review is moot if the page is not public. | Push to the named repo, make it public, then add after line 10 of README: `<a href="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml"><img src="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>` and fill SUBMISSION line 71. |
| MEDIUM | `README.md:20-29`, `README.md:238-247` | The two side-by-side `<table>` blocks (GIF pair, Pit Wall pair) are fixed at `width="440"`/`"460"` per cell. At 390 px the table scrolls horizontally and the right image is off-screen (see `readme-dark-390-top.png`: only the left GIF and a sliver of the Pit Wall are visible). GitHub mobile and the social-preview crawler see the same. | B3.3; judges open links on phones from the submission form. Half the demo media disappears. | Replace each table with a single `<p align="center">` holding two `<img ... width="49%">` tags (GitHub honours percentage widths and they stack on narrow screens), captions as one `<sub>` line below. |
| MEDIUM | `README.md:57-146`, `patterns/strands/README.md:18-53` | The "decision" section is 90 lines, two 20-line JSON blocks and a 12-row table, and the same two JSON blocks are repeated verbatim in `patterns/strands/README.md`. Quick start does not appear until line 210 (screen 4 of 6 at 1000 px). The README is 2,645 words / 325 lines. | Section-order checklist puts quick start fourth; B3.3's 3-anchor is "quick start" on the landing page. A judge scrolling once (the 30-second test) never reaches `make venv`. | Keep the first JSON block, wrap the second (lines 101-119) in `<details><summary>The frame questions (second request, carries the image)</summary>` ... `</details>`, and move "Quick start" (210-230) to directly after "What it does" (after line 55), retitled "Try it in 60 seconds (no car)". |
| MEDIUM | `README.md:64-70`, `hackathon/SUBMISSION.md:41-56` | Naming and content drift between the two documents a judge reads together: README lists five questions (`inside_envelope`, `args_grounded`, `intent`, `person`, `frame`); SUBMISSION lists three with a different first name (`envelope`). README maps `frame unclear >= 0.65` to "I cannot see clearly" and `inside_envelope <= 0.35` to Guide; SUBMISSION:52 maps unclear to "I've lost my eyes" and SUBMISSION:54 maps "envelope answers no" to Confirm. | A3 "the exact question handed to the Decider" and B3.4 "Honesty of claims": two different option sets for the same decision reads as a draft. | Regenerate SUBMISSION's two tables from `patterns/strands/tool_call_intervention.py` `QUESTIONS` (the source README already mirrors) so names, thresholds and narrator lines are identical in both files; keep "envelope" only as prose. |
| MEDIUM | `README.md:9-18` | Eight shields.io static badges; all resolve (200). Six state facts that are backed (`pyproject.toml:5,10`, `LICENSE`, model ids in `src/`); "strands-robots: rosbridge driver" and "AWS Community Day Mumbai 2026: presented" are descriptive labels, not statuses. There is no dynamic badge at all (no CI, no tests count, no release). The row wraps to two lines at 1000 px (fine) and five at 390 px (fine). | B3.3 at 5: "badges" that mean something; the reviewer brief says "only ones that resolve and mean something (CI status ..., Python 3.12, license, hackathon tag)". | Keep Python, strands-agents, Decider, Bedrock, License, Hackathon (six). Fold "strands-robots" and "presented" into prose. Add the CI badge once the repo is public (see HIGH above). |
| MEDIUM | `README.md:266-285` | Layout table omits three top-level directories that exist and are tracked: `scripts/` (`krewhq-session.sh`), `.github/` (the CI workflow) and `.claude/` (seven reviewer subagent definitions). Every row it has is a real directory. | Checklist: "the layout table names every top-level directory that exists". A judge who opens `.claude/agents/` without context sees "reviewer subagents for the hackathon round" and wonders what it is. | Add rows: `| .github/ | CI: lint, unit and sim on every push |`, `| .claude/ | the seven read-only review agents used for the hackathon review rounds |`, `| scripts/ | maintainer helpers (KrewHQ session) |`. |
| MEDIUM | `docs/results/README.md:1-3,46-48` | Linked from README:318 as "Car evidence" but it is a single-day diary ("what the real DeepRacer did today", "The Lead authorised one restart; this session's tooling refused the remote sudo write, so the user runs it by hand"). It does not index the other 14 result files in the same directory (benchmark, calibration, kiosks, portal, voice, five-use-cases). | B3.4 "Numbers cited to files" is strong here, but the entry page reads as an internal log, not an evidence index; "Communication quality 25%". | Retitle to "Measured results (index)", add a table of every `docs/results/*.md` and `*/README.md` with one line each and its date, then keep the 2026-10-14 narrative under a `## 2026-10-14 wheels-off session` heading with "today" replaced by the date and the "Lead authorised" sentence removed. |
| MEDIUM | `docs/context/00-README.md:27-32,95-99`, `docs/context/council/*` | Research bundle is written in the second person to the author ("written largely by you", "PRs #995 ... are yours", "Your own device history ... 192.168.0.3"), and `council/` holds brainstorm/advisor/review transcripts with an `ANON_KEY.txt`. README:280 and :311 send judges here as "Start here". | To an outsider this is an internal working diary; it also dilutes the "Start here" path. B3.3 "repo navigation". | Keep the bundle (it is honest provenance) but (1) change README:311 "Start here" to point at `docs/context/12-architecture.md` and `docs/dev/CONTRACTS.md`, (2) add one line at the top of `00-README.md`: "Internal research notes written for the author during the build; kept for provenance.", (3) consider moving `council/` under `docs/context/history/`. |
| MEDIUM | `README.md:26`, `docs/media/car-hop.gif`, `docs/media/pitwall.gif` | Load weight: the README pulls 6.58 MB (10 files: cover 611 KB, `car-hop.gif` 2.17 MB, `pitwall.gif` 2.10 MB, `fig-deepracer-strands.png` 714 KB, four more PNGs, one JPG, one SVG). `car-hop.gif` is exactly 10.0 s (checklist limit "under 10 s"); `pitwall.gif` 7.8 s. Both under 5 MB. | Mobile judges on venue Wi-Fi; a 6.6 MB first paint is slow. | Re-encode both GIFs at 640 px wide, 12 fps, 128-colour palette (`gifsicle -O3 --colors 128`), target 1.2 MB each; or convert to MP4/WebM and link (GitHub does not autoplay video in READMEs, so GIF stays for the hero but can be smaller). |
| LOW | `docs/media/pitwall.gif` frame 0 | First frame of the Pit Wall GIF is almost entirely black (the window had not painted). Frame 0 is what static previews show. | Thumbnails on mobile and in link unfurls show a black box. | Drop the first 0.5 s when re-encoding. |
| LOW | `README.md:5-7` | Title "Agentic AWS DeepRacer on strands-robots" and tagline are centred HTML; fine in both themes. The badge group has no `<a>` wrappers, so none of the eight badges is clickable. | Minor; judges click badges expecting the pinned model or the hackathon page. | Wrap the Decider badge in a link to `https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` (verify) and the Hackathon badge in a link to the Builder Center hackathon page. |
| LOW | `docs/article/img/fig-deepracer.png` | RGBA with alpha 0 corners (transparent background, 932x650, 557 KB). Not referenced by README or article today, but it is the only transparent raster in `img/` and would float as a grey cut-out on a light Builder Center page if someone picks it. Every other PNG is opaque `#0b0b10` or `#06080b`; the SVG has an opaque `.bg` rect. | Dark/light safety of article figures. | Either delete it (the same bytes exist at `docs/talk/deck/assets/05/deepracer-car-official.png`) or flatten onto `#0b0b10`. |
| LOW | `docs/results/portal.md`, `docs/results/filming-protocol.md`, `tests/car/pwm_sampler.py`, `tests/car/remote_sampler.py`, `tests/car/steer_deadman_check.py` | Naming outliers: two undated result pages where the convention is `<topic>-YYYY-MM-DD.md`; three files under `tests/` without the `test_` prefix (they are samplers, not tests). Upper-case names `hackathon/RUBRIC.md`, `SUBMISSION.md`, `REVIEW-LOG.md`, `docs/dev/CONTRACTS.md`, `docs/article/FACTS.md`, `docs/talk/Control-simulate-train-robots.html`. No `.DS_Store` tracked, nothing over 10 MB (largest tracked: `docs/talk/Control-simulate-train-robots.html` 7.1 MB). | Naming hygiene checklist. | Rename `portal.md` -> `portal-2026-10-14.md` (and the folder), `filming-protocol.md` -> `filming-protocol-2026-10-15.md`; move the three samplers to `tests/car/tools/` or `scripts/car/`. Leave the shouting file names: they are conventional for top-level control documents. |
| LOW | `README.md:48,69,121,143` | Measured numbers in the README (141/144 ms, 490/498 ms, 456 ms, 681-727 ms, 278 ms, 35 ms, 22 ms) all cite a `docs/results/` file. Good. One claim has no source link: line 123 "only 79 percent without it" (SUBMISSION:67 says "110 of 140", which is 78.6 percent). | B3.4 at 5 "numbers all sourced". | Write "110 of 140 (79 percent)" and cite the benchmark page's section. |
| LOW | `.kiro/README.md:1-15` | Opens on "Open the repo root ... as the workspace in Kiro" as one dense 11-line paragraph; the last line ("Conventions confirmed 2026-10-22: kiro.dev/docs/...") is a note to self. | Reads fine for a Kiro user; the closing line is diary. | Split into "What loads" (bullets per steering file) and "Hooks"; drop or footnote the "Conventions confirmed" line. |
| INFO | `patterns/README.md`, `patterns/strands/README.md`, `notebooks/README.md`, `hackathon/README.md` | All four open well: a one-paragraph purpose, a table or a run block within the first screen, and the safety line. `patterns/strands/README.md` is the strongest page in the repo (questions as JSON, both decision tables, offline and live runs, the YES knob, "What this is not"). | B2.3 at 5 "Drop-in folder mirroring upstream names, QUESTIONS printed as JSON, a notebook". | None. |
| INFO | `.github/workflows/ci.yml` | One workflow: lint, unit, sim on push to `main` and `strands-agentic-deepracer` and on PRs. Installs `strands-robots` from `git+https://github.com/Vivek0712/robots@fix/deepracer-manual-state` (public, 200). No secrets, tokens, profiles or private hosts referenced; the comment at lines 5-7 is explicit that nothing else touches the network. | Checklist: CI present, nothing private. | None; add the badge once the repo is public. |
| INFO | `LICENSE`, `CONTRIBUTING.md`, `CITATION.cff`, `SECURITY.md` (absent), `.github/ISSUE_TEMPLATE/` (absent), social preview | LICENSE (Apache-2.0, 11.3 KB), CONTRIBUTING (safety rule first, workflow, pattern rules) and CITATION.cff (valid 1.2.0, keywords, two references) are present and consistent with `pyproject.toml:7`. Missing GitHub niceties: a social preview image (GitHub wants 1280x640; `cover.png` is 1200x675 and would be cropped top and bottom), `SECURITY.md`, issue/PR templates, `.gitattributes` to stop `docs/talk/*.html` (7.1 MB + 2 MB) and `portal/frontend/dist/*` from counting toward the language bar. | B3.3 at 5 lists LICENSE and contributor guide (present); the rest is what a top-3 page has. | See "What a top-3 page has" below. |

## Link check

- Files scanned: `README.md`, `patterns/README.md`, `patterns/strands/README.md`,
  `hackathon/*.md`, `docs/article/article.md`.
- 45 link targets, 0 broken, 0 missing files, 0 unresolved anchors. Every `<img src>` in
  `README.md` exists.
- External: 5 unique `https://github.com/...` targets, all 200.
- Badges: 8 shields.io URLs, all 200 (`curl -sI`).
- Not in a scanned file but reader-facing: `CITATION.cff:16` repository URL 404; SUBMISSION:71-73
  three `[... pending]` placeholders.

## Media table (every image the README pulls, plus the article-only outliers)

| Path | Bytes | Pixels | Mode | Corners | Dark-safe | Light-safe | Alt text | Note |
|---|---|---|---|---|---|---|---|---|
| `docs/article/img/cover.png` | 611,052 | 1200x675 | RGB | `#11101f`..`#07070c` | yes | yes (dark card on white, reads as a poster) | yes | hero |
| `docs/media/car-hop.gif` | 2,173,213 | 720x405, 100 frames, 10.0 s | P | dark | yes | yes | yes | frames 0-~60 are the phase-1 UI; car in last ~4 s; no person in the 8 sampled frames |
| `docs/media/pitwall.gif` | 2,095,744 | 720x405, 94 frames, 7.8 s | P | `#06080c` | yes | yes | yes | frame 0 nearly black; drawn stick figure only (allowed) |
| `docs/article/img/fig-architecture.png` | 290,761 | 1600x900 | RGB | `#0b0b10` opaque | yes | yes | yes | small type at 900 px; readable at 1000 px, not at 390 px |
| `docs/article/img/fig-deepracer-strands.png` | 713,748 | 1600x900 | RGB | `#0b0b10` opaque | yes | yes | yes | heaviest PNG; callout type small on phone |
| `docs/media/strands-stack.svg` | 5,042 | 1200x250 | SVG, `.bg` rect `#0b0b10` | opaque | yes | yes | yes (`<title>`/`<desc>` + alt) | fonts fall back to system sans; fine |
| `docs/article/img/fig-portal-stage.png` | 279,069 | 1920x1080 | RGB | `#06080b` | yes | yes | yes | real screenshot |
| `docs/article/img/fig-portal-operator.png` | 308,453 | 1920x1080 | RGB | `#06080b` | yes | yes | yes | real screenshot |
| `docs/article/img/fig-safety-ladder.png` | 209,169 | 1600x1000 | RGB | `#0b0b10` | yes | yes | yes | best figure on the page |
| `docs/article/img/event-car-on-stage.jpg` | 211,506 | 1600x1150 | RGB | n/a | yes | yes | yes | approved event photo; no face |
| README total | 6,897,757 (6.58 MB) | | | | | | | |
| `docs/article/img/fig-deepracer.png` (article-only, unused) | 557,111 | 932x650 | RGBA, alpha 0 corners | transparent | no (grey halo) | no | n/a | flatten or delete |
| `docs/media/curiosity.gif` (named in prose, not embedded) | 1,009,406 | 640x366, 137 frames, 13.7 s | P | dark | yes | yes | n/a | over the 10 s guideline; fine while not embedded |
| `docs/article/img/event-speaker-with-car.jpg`, `event-hall.jpg` | 468,255 / 326,758 | 1200x1600 / 1600x1200 | RGB | n/a | | | | the other two approved photos; article only |

All README images have alt text. No tracked image shows a person other than the three approved
event photos (`docs/article/img/event-*.jpg`); the harness frames with people are gitignored
(`harness/frames/.gitignore`), `eventpics/` is gitignored. Every raster the README uses is under 2 MB
except the two GIFs (2.17 and 2.10 MB, under the 5 MB GIF limit).

## Section order (actual)

1. Hero: cover, H1, tagline, 8 badges, two GIFs (lines 1-29)
2. Intro paragraph (31-37)
3. What it does, ending with the safety line in bold (39-55)
4. The decision handed to Decider 2B (57-146): table, JSON, JSON, merge table, measurements
5. Reusable pattern (148-173)
6. Architecture (175-208) with "The Strands stack" H3, SVG and table
7. Quick start (210-230)
8. Pit Wall (232-247)
9. Safety by physics (249-264)
10. Repository layout (266-285)
11. Hackathon submission (287-297) with two TODOs
12. Seen live (299-307)
13. Docs (309-321)
14. License (323-325)

Checklist order is: what it is, safety line, demo, quick start, architecture, pattern, layout,
results, article link, license. The rubric-named headings are all present and worded as the AI
scorer expects. The deviation that costs the most is quick start at position 7.

Headings: one H1 (HTML), twelve H2, one H3, all sentence case, no empty sections. Code blocks: 4
(json, json, python, bash). Tables: 4 markdown tables (5, 11, 6, 17 rows), all with consistent
column counts and header separators, plus two HTML tables for side-by-side media. At 1000 px no
table overflows; the 17-row layout table and the 11-row merge table are the tallest blocks.

Naming consistency in prose: README uses "Strands Decider 2B" (5), "Decider 2B" (11), "the decider"
(3), "decider gate" (4); the badge says "Strands Decider | 2B qwen3.5-v1-2610"; the article says
"Strands Decider" without "2B" 10 times. Product name "Pit Wall" (9) vs "portal" (10) are used for
the same thing; the folder is `portal/`. Acceptable, but pick "Pit Wall (the `portal/` app)" once
and then "Pit Wall".

## What a top-3 repo page has that this one does not (priority order)

1. A hero GIF of the real car under this stack with the verdict on screen (today: a phase-1 UI
   recording, car only in the tail).
2. Three calls to action under the badges, including a "Watch the demo" button (today: none).
3. A public repo URL that resolves, with a CI badge next to the license badge (today: 404).
4. A "Try it in 60 seconds" block on the first screen after "What it does" (today: line 210).
5. A 1280x640 social preview (`docs/media/social-preview.png`, uploaded in repo settings) so the
   link unfurls with the car, not the Planner UI frame.
6. A short README: 1,200-1,500 words, with the second JSON and the 11-row merge table behind
   `<details>` and the full version in `patterns/strands/README.md` (already there).
7. One line of plain limits in the README ("not measured: ..., the model misses: ...") that
   B3.4 scores at 5; the article has it, the README does not.
8. `SECURITY.md` (one paragraph: car passwords never in the repo; how to report), issue template,
   `.gitattributes` with `docs/talk/*.html linguist-vendored` and `portal/frontend/dist/* linguist-generated`.

## Scores (0-5)

| Area | Score | One line |
|---|---|---|
| Hero and first impression | 3 | Strong cover, clean title and badges in both themes; no CTA, the car GIF opens on an old UI, no demo link |
| Media quality and safety | 4 | Everything opaque, alt-texted, present, no faces; 6.6 MB page weight and two GIFs at the limit |
| Section order and tables | 3 | Rubric headings present; quick start buried at line 210; duplicated JSON; layout table misses `.github/`, `.claude/`, `scripts/` |
| Link integrity | 4 | 45/45 internal links and anchors resolve, 8/8 badges 200; repo URL in CITATION.cff and SUBMISSION placeholders are 404/pending |
| Naming hygiene | 3 | No DS_Store, nothing over 10 MB; question names and thresholds drift between README and SUBMISSION; two undated results pages; three non-`test_` files under `tests/` |

## Top 10 improvements with the exact edit

1. `README.md:18` (after the badge `</p>`): insert
   `<p align="center"><a href="#quick-start"><b>Try it in 60 seconds</b></a> &nbsp;·&nbsp; <a href="patterns/strands/README.md"><b>Copy the Decider pattern</b></a> &nbsp;·&nbsp; <a href="docs/article/article.md"><b>Read the article</b></a> &nbsp;·&nbsp; <a href="#hackathon-submission"><b>Watch the 3-minute demo</b></a></p>`
   (swap the last href for the video URL when it exists).
2. `docs/media/car-hop.gif`: replace with a 6-8 s landscape recording of the car in the pen with the
   Pit Wall verdict visible (PiP or overlay), first frame the car, under 2 MB; until then
   `ffmpeg -ss 6 -i car-hop.gif -t 4 -vf "scale=640:-1,fps=12" ...` and keep `README.md:26` caption.
3. `README.md:294-297`: replace the two TODO bullets with
   `| Article | Builder Center, publishing 2026-10-2x |` / `| Demo video | 2:xx, recording 2026-10-2x |`
   as a two-column table; delete "do not treat this line as a link".
4. Publish the repo at the URL in `CITATION.cff:16`; then `README.md:10` prepend
   `<a href="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml"><img src="https://github.com/Vivek0712/strands-robots-deepracer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>`
   and fill `hackathon/SUBMISSION.md:71`.
5. `README.md:20-29` and `238-247`: replace each `<table align="center">` with
   `<p align="center"><img src="docs/media/car-hop.gif" width="49%" alt="..."> <img src="docs/media/pitwall.gif" width="49%" alt="..."></p>` and one `<p align="center"><sub>left caption · right caption</sub></p>`.
6. Move `README.md:210-230` (Quick start) to after line 55 and retitle `## Try it in 60 seconds (no car)`; keep the `#quick-start` anchor by adding `<a id="quick-start"></a>` above it.
7. `README.md:101-119`: wrap in `<details><summary>The frame questions (second request, carries the image)</summary>` ... `</details>`; `README.md:126-138` likewise with summary "How the answers merge (most severe wins)". Add after line 146: "Full tables, thresholds and the YES knob: [patterns/strands/README.md](patterns/strands/README.md)."
8. `hackathon/SUBMISSION.md:41-56`: regenerate both tables from `patterns/strands/tool_call_intervention.py` `QUESTIONS` and the README:126-138 table so the five question names (`inside_envelope`, `args_grounded`, `intent`, `person`, `frame`), the thresholds (0.5 / 0.65 / 0.35) and the narrator lines match the README word for word.
9. `README.md:266-285`: add rows `| .github/ | CI: ruff, unit and sim on every push and PR |`, `| .claude/ | read-only review agents used for the hackathon review rounds |`, `| scripts/ | maintainer helpers |`.
10. `docs/results/README.md:1-5`: retitle `# Measured results`, add an index table of every `docs/results/*.md` and `*/README.md` (name, date, one line), move the existing text under `## 2026-10-14 wheels-off session`, replace "today" (lines 3, 31) with "2026-10-14" and delete the sentence at 46-48 beginning "The Lead authorised".

Also worth doing, below the top ten: a 1280x640 `docs/media/social-preview.png` from the cover
(car right, title left) uploaded in repository settings; `README.md:123` "only 79 percent" ->
"110 of 140 (79 percent)"; flatten or delete `docs/article/img/fig-deepracer.png`; re-encode both
GIFs to about 1.2 MB each and drop the black first frame of `pitwall.gif`; rename
`docs/results/portal.md` -> `portal-2026-10-14.md`; one "Limits" paragraph in the README (what was
not measured on the floor, what the 2B model missed on the drawn frames: 1 of 7).
