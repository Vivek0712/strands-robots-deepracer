# v2 QA: the rendered film

Reviewed: `docs/video/build/deepracer-decider-demo-v2.mp4` (177.27 s, 1920x1080, 30 fps, 5318
frames, H.264 16.1 Mbps, AAC 48 kHz stereo 147 kbps) with `deepracer-decider-demo-v2.srt`,
against `DESIGN.md`, `STORYBOARD-v2.md` (revision 2) and `shots-v2.yaml`, and against the
current v1 render `deepracer-decider-demo.mp4` (same 177.27 s timeline). Method as in
`round-3-video.md`: one frame per second at full size and at 854x480, contact sheets of 12
(15 pages each size), 30 fps strips of 17 frames at every shot boundary (8 either side), a 30
fps strip of the first 1.6 s, 39 frames of the end dip, per-frame measurements over all 177
one-second frames (1 percent and 0.1 percent luminance, grain standard deviation on a flat bg
patch, caption-zone content, safe-margin content, orange clusters with the kicker, rail and
lower-third bar masked out, rail fill position against the global clock), a whole-film motion
timeline from consecutive-frame differences at 320x180, an onset and ramp measurement for 88
anchor-keyed entrances (30 fps crops from 0.33 s before to 0.80 s after each anchor), the
stitched Polly JSON (onsets and durations) against silence detection at -45 dBFS, `ebur128`,
a sample-exact comparison of the v1 and v2 audio, and an SRT cue check. Zooms at 1:1 on the
LED, the title, the leaders, the chips, the counter, the terminals, the withheld frame, the
shot 10 bottom band, the shot 12 terminal edge and the close stack.

Working files (scratchpad, wiped between sessions):
`/private/tmp/claude-501/-Users-vivekrajaps-strands-robots-deepracer/730bd399-92ea-4b34-9bc2-a8347cd3ce22/scratchpad/v2qa/`
with `sheets_full/sheet_00..14.png`, `sheets_480/sheet_00..14.png`, `p480/f_000..176.png`,
`bounds/hook_first_1.6s.png`, `bounds/trans_<boundary>.png` (16), `bounds/end_dip.png`,
`bounds/rail_during_push_35.1.png`, `bounds/zoom_sheet_0.png`, `bounds/zoom_sheet_1.png`,
`bounds/v1_vs_v2.png`, `anchors.txt`, `motion/runs.txt`, `metrics.txt`, `orange2.txt`,
`audio/sil_deepracer-decider-demo-v2.txt`.

## Verdict: ship after fixes

v2 is the more professional film by a clear margin: every entrance is eased and lands on its
words, the pushes and dissolves run inside the incoming shot with no black flash, the chrome
is on frame 0 of every card, the decision chapter reads as one continuous explanation, and
every honesty label is where the storyboard puts it. Nothing is CRITICAL. Three things should
be fixed before upload because every judge sees them: (1) the progress rail rides the plates
during the four push transitions, so the orange head sweeps off the left edge and a new head
enters from the right, a progress indicator that resets four times; (2) on shot 4 the kicker
`THE SYSTEM . 2 OF 2` prints straight over the figure's `Amazon Bedrock` heading in both full
views (0:23.0 to 0:23.8 and 0:34.6 to 0:35.9, including the push into shot 5); (3) the SRT
gives the second piece of five split sentences 0.30 to 0.62 s (`number.`, `fifty six
milliseconds.`, `why.`), inherited from v1. All three are renderer or YAML fixes under an hour;
no re-recording, no re-timing.

## Scores (1 to 5)

| Dimension | Score | Why |
|---|---|---|
| Hook | 5 | PROCEED for 10 frames, the figure walks in at frame 5, DENY and the red LED at frame 11 (0.37 s) with a bloom, the spotlight settles the frame by 0.9 s, the title lands at 1.07 s on the first word with the rail drawing on under it; nothing else moves until the cut at 4.0 and the real car follows. The frame reads from the first second. |
| Clarity | 4 | The split, the divider, the kicker slot and the bottom band hold from shot 5 to shot 8, and the scale is one character (met on 5, thresholds on 6, tinted tracks on 7, zone-coloured values on 8), so the chapter reads as one explanation. Minus one for the first 12 s of shot 6, where the film's central mechanism is carried by the smallest type in the chapter on an otherwise empty card. |
| Proof | 4 | Unchanged substance: the recorded run (7, 8), the on-car card (9) with its source path and the withheld frame as a drawn hole, the simulator Deny (10), 72 timed calls (11). |
| Numbers | 5 | Counters land on the exact value, count at 55 percent so an intermediate frame (the `20` at 2:31) reads as transitional, `0 of 72` does not count, the p95 clipping of v1 is gone, every number carries its unit and date. |
| Pattern | 4 | File tree, three underlined lines of wiring, the status-bar path for 9 s, the burst with three verdict underlines, the URL again for 7 s at the close. The 22 px terminal rows and the 20 px docked badge are at the limit at 480p; the editor code (26 px) reads. |
| Pacing | 4 | Picture and voice are now locked: 88 measured entrances land within -0.33 and +0.14 s of their anchors (the early ones are camera moves and bar fills that start on the clause, by design), holds after the last word are 0.5 s. Minus one for three empty stretches: shot 5's first 8 s (five dim names), shot 6's first 12 s (a rule), shot 12's first 4.2 s (an empty editor and an empty terminal). |
| Legibility at 480p | 4 | Every essential word reads at 854x480: titles, questions, zone labels, chips, JSON, the shot 8 terminal (24 px), the code, the status-bar URL, the close stack. What does not resolve is non-essential 20 px texture: `1.5 s budget`, the docked badge on shot 12, gutter numbers. |
| Audio | 4 | Integrated -16.0 LUFS, true peak -1.5 dBTP, LRA 3.4 LU, no bed, no room tone, sample-identical to v1 (max absolute difference 0, lag 0). Inter-sentence silences 0.74 to 1.6 s (8 of 48 measure 0.74 to 0.76 at -45 dBFS). Minus one for the SRT's five flash cues. |
| Honesty | 5 | SIM, FAKE DECIDER, DRAWN FIGURE on 1, 2 and 10 (on the verdict card at 10, at 100 percent through the dim); REAL CAR, PHASE-3 VISION PLANNER, PRE-DECIDER on both 1b entries; RECORDED on 7 and 8; MEASURED on 9 (two pills) and 11; FAKE DECIDER, STDOUT VERBATIM on 12. Judge badge hidden on 1, 1b, 2, 10, 13, 14. The `257 ms` and `92 ms` fake-stack numbers are never marked. The decider is never the safety layer: the line is on 2, 10 and 14 and the deadman has its own red stop on shot 4. |
| Craft | 4 | Eased entrances everywhere (measured ramps 5 to 90 percent in 4 to 6 frames on the enter curve, 2 frames on the 240 ms draws), one accent at a time on every card frame, glow only on chips and the LED, vignette and grain present without banding, the pushes and dissolves clean. Minus one for the rail jump, the shot 4 kicker collision, and the architecture figure's own palette (violet, green, orange arrows) sitting inside a film that otherwise has one accent. |

## Findings

Severity: CRITICAL blocks the upload, HIGH is visible to every judge, MED is visible to an
attentive judge or on one device class, LOW is polish, INFO is a document correction.
Timecodes are mm:ss.s in the rendered file.

| # | Sev | Timecode | Shot | Finding | Exact fix |
|---|---|---|---|---|---|
| 1 | HIGH | 0:13.5 to 0:14.2, 0:35.2 to 0:35.9, 2:03.7 to 2:04.5, 2:36.1 to 2:36.8 | 3, 5, 9, 12 (push in) | The progress rail is part of the plates during a push: the outgoing rail (with its orange head at x 380 on 0:35.2) slides left off the frame while the incoming shot's rail enters from the right, head last. The head crosses the full width in 0.7 s four times in the film (`bounds/rail_during_push_35.1.png`). DESIGN 10 says the fill is computed from the global time and is correct across every transition; DESIGN 8 says chrome persists. | `compose.py`: draw elements flagged `chrome: true` (the rail, z 97) after the transition composite, or exclude z >= 97 from the frozen outgoing plate and from the push offset so the rail is rendered once per frame from the global clock. The kicker, pill and lower-third may keep riding the plates (that is their entrance); only the rail must not. |
| 2 | HIGH | 0:23.0 to 0:23.8, 0:34.6 to 0:35.9 | 4 | In both full views the kicker `THE SYSTEM . 2 OF 2` (orange, no plate) prints over the figure's `Amazon Bedrock` heading and the `Nova Pro` box text (`bounds/zoom_sheet_0.png`, `s04_kicker_collision_*`). At the stops it sits over figure lines and the green heartbeat arrow (0:30 to 0:33). The lower-third gets a plate here; the kicker does not. | `shots-v2.yaml` s04: give the kicker a plate as the lower-third has, `{<<: *kicker, text: "THE SYSTEM  .  2 OF 2", plate: {color: bg, alpha: 0.72, radius: 8, pad: 12}}`; or fit the two full views below the title band (view `[0.5, 0.5, 1.0]` placed at y 180..1080, scale 0.83) so the figure never enters y 62..170. The plate is the smaller change and keeps the storyboard's views. |
| 3 | MED | 0:42.8, 1:55.4, 2:08.3, 2:18.6, 2:42.7 | 5, 8, 9, 10, 12 | SRT split cues: the second piece of a sentence that was split for length gets 0.30 s (`number.`, `fifty six milliseconds.`, `why.`) or 0.62 s (`Confirm, the operator is asked.`, `runs it offline against a fake decider.`), and the pair ends 0.6 to 1.3 s before the speech does (sentence `On the car ...` speech ends 2:09.4, cue 41 ends 2:08.6). Identical to the v1 SRT (same md5), so not a regression, but YouTube will flash these. | `audio.py` `split_cue`: split a long sentence by the character share of its measured speech length (onset plus the stitched JSON duration less the 0.11 s tail), never shorter than 1.0 s per piece; or keep a two-line cue whole when it fits 2 x 42 characters (cues 13/14 and 43/44 do). Rewrite the SRT only; the mix does not change. |
| 4 | MED | 0:54.2 to 1:06.4 | 6 | Twelve seconds in which the card holds a 4 px rule, 20 px tick values and 28 px zone labels on an otherwise empty 1920x1080 (`sheets_full/sheet_04.png`, `sheet_05.png`). The voice is delivering the film's core mechanism ("Two thresholds make the action") and the picture gives it the least weight in the chapter. The six events land on their words (measured: 0.65 tick +0.04 s, green label -0.23 s, 0.35 tick +0.04 s, red label -0.33 s, cyan label -0.20 s against the storyboard brackets, all on the spoken words), so this is weight, not timing. | `shots-v2.yaml` s06: zone labels `*t_body` (32) instead of `*t_body_s`, tick values `*t_mono_s` (22), the rule 6 px (`y: [259, 265]`), and the three zone labels at y 288; or add the zone's verdict word under each label in its chip colour (`confident no = Deny`, `ask = Confirm`, `confident yes = Proceed`), which also pre-reads the rows. No anchor changes. |
| 5 | LOW | 0:23.0 to 0:35.2 | 4 | The architecture figure brings its own palette: the `commands . 20 Hz . ws:9090` arrows and the DeepRacer box title bar are orange (2 to 4 orange clusters per full-view frame, `orange2.txt`), its boxes are violet and green, and its 10 px footer and legend (`the next build's wiring: everything here ran on ...`) show at the bottom of the full views like a leftover caption. Every other frame of the film obeys the one-accent rule. | Re-export `fig-architecture-3840.png` with the arrow and edge colours in ink-dim, the DeepRacer header in ink, and the footer and legend rows stripped (they are not spoken); or accept as the article's figure. |
| 6 | LOW | 2:36.1 to 2:40.3 | 12 | After the push the editor shows only its sidebar header and the terminal only a blinking cursor for 2.3 s; the tree lands at 2:38.4 (s2 `Three files`) and the first code line at 2:40.3 (s2%30 `three lines of wiring`), so 4.2 s of an empty IDE. The timing matches the words; the picture is bare. | Optional: `shots-v2.yaml` s12: enter the tree rows at `s1` (2:36.4, `The pattern is a drop-in.`) as the "drop-in" picture and keep the code at `s2%30`; or pre-show the seven code lines in ink-mute on the plate and recolour to ink at `s2%30` (the shot 5 skeleton pattern). |
| 7 | LOW | 1:37.2 to 1:38.8 | 8 | A title-less card whose only content is an empty terminal with a blinking cursor for 1.6 s before `USER : Go.` types (s1%67). It reads as a loading state. | Optional: `shots-v2.yaml` s08 line 0 `in: "s1"` (1:37.6, `I type:`) so the typing starts on the words; the 24 cps human rate still finishes before s2. |
| 8 | LOW | 2:49.7 to 2:56.8 | 14 | Two Strands marks on one frame: the cover render's green ribbon S at 30 percent on the left and the 96 px mark bottom-right; the cover's cyan particle sits at about (690, 570), beside the author line. The URL at 32 px is legible at 480p (14 px) but is a step down from v1's 48. | Drop the 96 px mark (the cover already carries the mark), or crop the cover so the ribbon sits left of x 400; optionally URL 36. |
| 9 | LOW | 0:30.0 to 0:33.9 | 4 | At stop 4 the step panel (surface at 92 percent) and the badge plate sit on top of the figure's `camera_node -> web_video_server` box and the deadman box's bottom edge; legible, but the stop is the busiest frame in the film. | Accept, or at stop 4 use `cx 0.790, cy 0.560` so the deadman node sits higher and the panel covers the empty `camera guard` row instead. |
| 10 | LOW | whole film | 4, 11, 12 | At 480p the 20 px Mono-XS elements do not resolve (9 px): `1.5 s budget`, the docked `Agent ... | Judge ...` badge in the shot 12 tab strip, gutter numbers, the figure's own small text. None is essential. | Accept (DESIGN sets 20 px as the floor for texture). If the docked badge must read, Mono-S 22 fits: the strip has 1000 px free. |
| 11 | LOW | whole film | all | Inter-sentence silences measured at -45 dBFS: minimum 0.737 s, 8 of 48 between 0.74 and 0.76 s, the rest 0.76 to 1.6 s (`vo_gap_ms: 600` plus the 120 ms tails). Identical to v1. | None required. If 0.76 is a hard floor, `vo_gap_ms: 660` and re-measure every onset (all anchors move). |
| 12 | INFO | n/a | 4, 5, 6, 7, 8 | The storyboard's bracketed resolutions of percent anchors differ from the renderer's by up to 0.8 s (shot 4 `s2%45` 4.54 vs 4.24; shot 5 `s3%78` 11.90 vs 12.73; shot 6 `s2%60` 4.94 vs 4.54; shot 7 `s3%43` 8.89 vs 8.62). The renderer resolves against the measured sentence lengths (JSON durations exceed the -45 dBFS speech length by only 0.10 to 0.12 s) and lands on the words; the brackets were computed from estimated lengths. | Update the brackets in `STORYBOARD-v2.md` from `vo/stitched/*.json`; no render change. |

Nothing CRITICAL. No text is clipped (the shot 12 terminal's tenth row fits above the panel
edge at y 911; nothing is cut mid-glyph). No essential element sits in y 940..1040 on any card
(caption-zone content count is 0 on every card frame; only full-bleed footage, the Pit Wall's
own log, the figure's bottom row and the cover extend into it, as DESIGN 15 allows). No text
sits outside the title-safe margin except the shot 10 caption at y 8..62 (on purpose, as v1)
and the figure's own text at the shot 4 stops. No glow on anything but the chips and the LED
(zooms on the title, the URL, the mark, the leaders and the counter show none). No arrow,
circle or filled highlight anywhere. No linear motion found: every measured ramp is front
loaded (enter curve) or a 2 to 6 frame draw.

## Shot by shot

Timecodes are the storyboard's fixed timeline, confirmed by the boundary strips (every cut
is on the exact frame).

- Shot 1 (0:00.0 to 0:04.0): PROCEED frames 0 to 10, the figure at frame 5, DENY and the LED
  label red at frame 11 (0.37 s) with the bloom visible on the 1:1 zoom (radius about 24,
  two pulses), freeze and spotlight 0.77 to 0.94 s (eased, 5 frames), title 1.10 to 1.26 s
  (eased), rail draw-on 1.10 to 1.26 s. Push-in 1.03 present (below the motion threshold,
  as intended). Pill top-right from frame 0. Badge hidden. One orange cluster (none on
  content; the rail head). Legible at 480p: DENY, title, pill; the LED label is 7 px but the
  red dot and bloom read. Pass.
- Shot 1b-feed (0:04.0 to 0:05.6): hard cut, panel with the feed and its log plate, blur
  fill, lower-third bar then text at +0.56 (measured). Pill opaque. Pass.
- Shot 1b-car (0:05.6 to 0:08.0): full-bleed phone footage, lower-third and pill held with no
  re-entrance (strip at 5.60 shows both unchanged across the cut). Nothing drawn on the car.
  Pass.
- Shot 2 (0:08.0 to 0:13.5): figure spotlight 8.40 (measured 8.40 to 8.43 onset), the two
  cyan focus frames at 9.0, the red DENY frame at 10.2, `Here is why.` at 12.0 on its words,
  safety footer from frame 0. Mask lifts to 70 percent at s3. Pass.
- Shot 3 (0:13.5 to 0:23.0): push-left 13.50 to 14.23 (measured), title and kicker on the
  incoming plate, lower-third at 13.7 on `I am`, badge on a plate at s2. Leaders draw from
  the dot outward (zoom confirms the dots sit on the camera, the drive, the servos, the
  compute, the body and the base), the Decider in orange with the only ping, Harness and Box
  arrive settled at 70 percent at 20.9 to 21.0. Lower-third bar at x 96, left of the text
  (the v1 bug is gone on every lower-third). Pass. Taste: at 480p the labels are 16 px and
  read well; the car render is the film's best-looking object.
- Shot 4 (0:23.0 to 0:35.2): camera moves measured 23.83 to 24.53, 25.77 to 26.53, 27.30 to
  28.03, 29.77 to 30.53, 33.93 to 34.60, each 0.70 to 0.77 s with the motion peak mid-move
  (camera curve). Focus frames cyan on stops 1 to 3, red on the deadman at stop 4; number
  badges inside the margin; step rows 1 to 4 orange in turn with the previous row recolouring
  (the renderer's own table shows 2 to 4 orange counts only inside the 240 ms recolour). The
  pull-back draws the cyan trace ending red at the deadman. Findings 2, 5, 9. The 3.0x stop
  (0:28 to 0:29.8) is the best frame of the chapter.
- Shot 5 (0:35.2 to 0:53.8): push 35.23 to 35.90, kicker and divider on the plate, title at
  36.31 (s1 +0.04), skeleton names staggered 36.31 to 36.57, right column at 38.16, 40.04,
  41.10, scale draw 41.40 to 41.64, `Request 1` 43.87, rows at 45.40, 46.24, 47.94 (on
  `inside the envelope`, `grounded`, `what was asked`), `Request 2` 49.80, rows 51.33 and
  52.25. `args_grounded` the one orange. Everything legible at 480p (`p480/f_052.png`).
  Taste: 36.3 to 43.8 is five dim names and a right-column paragraph; it is calm rather than
  empty, but it is the second-sparsest stretch.
- Shot 6 (0:53.8 to 1:20.8): hard cut with the shot 5 scale carried (strip at 53.80), travel
  54.23 to 54.77 with the divider top retracting, six scale events on their words (measured
  above), rows at 66.52, 69.02, 72.57, 74.68, 76.81 (+0.07 to +0.10 against the anchors), each
  with the bar, the case from the left, the chip from the right with its bloom (ramp 0.23,
  0.53, 0.71, 0.82, 0.90), gate line 78.97, row-7 note 79.21. Chips are the brightest thing in
  their rows (zoom). Finding 4.
- Shot 7 (1:20.8 to 1:37.2): title and line 0 at 81.20, cyan underline on `20 centimetres.`
  at 82.44 (240 ms draw), lines 1 and 2 at 82.71, `0.2` underline 84.08, the ANSWER setup (the
  0.65 line and the three tinted tracks) at 84.38 in the quiet, `args_grounded` label and the
  evidence leader at 85.44 with the ping, fill 85.86 to 86.06 turning green past x 1604,
  `0.907` at 86.46, lines 3 to 5 and `inside_envelope` at 88.27, fill 89.46 (ink-dim until the
  threshold, visible at 1:29), `0.948` 90.03, `intent` 91.68, fill 92.20, `0.959` 92.76,
  PROCEED chip 93.82 exact with its bloom, `583 ms` counting 94.97 to 95.5 at 55 percent and
  snapping. The tinted tracks read nearer 25 percent than 10 (zoom), which helps. Pass; the
  leader crossing the divider is the chapter's best cue.
- Shot 8 (1:37.2 to 2:03.7): columns swap on a hard cut with the chrome, divider and bottom
  band held (strip at 97.23). `USER : Go.` types 98.61 to 99.38 (24 cps, cursor visible),
  machine rows at 80 cps with the cursor hidden, nodes at 99.50, 100.80, 103.42, 107.55,
  109.11, 111.63, 115.60, 118.10, each the one orange with the previous recolouring,
  underlines cyan for the argument values, red for `0.18`, amber for `"Guide"`, cyan for
  `0.404` and `"Confirm"`, the quiet ink underline on `"deterministic_check": "ok"` present
  (zoom at 1:57.5), the OPERATOR line typed cyan at 118.30, the agent's reply finishing
  before the push, the closing caption at 121.14 with its orange bar as the last node dims.
  18 lines fit without a scroll. Legible at 480p (`p480/f_122.png`). Finding 7 (the empty
  first 1.6 s).
- Shot 9 (2:03.7 to 2:13.2): push 123.73 to 124.47 with title and kicker on the plate, two
  pills from frame 0, the withheld frame's outline from frame 0, span 1 at 124.1, `p =
  0.9485` at 126.1, `in 456 ms` at 127.6 on the words, hatch and `WITHHELD` at 130.2, the
  gate line and the source path. Badge shown (true here). Pass; the quietest and most honest
  frame.
- Shot 10 (2:13.2 to 2:23.2): native full-bleed screenshot, caption plate in the header,
  spotlight stack figure 134.4, chips with the cyan frame 135.4, DENY red frame 136.5, quote
  card 137.8, quote exit and the 30 percent dim at 139.50 (measured 139.47 to 139.67), span 1
  at 139.5, span 2 at 141.4; the honesty pill sits in the verdict card at 100 percent through
  the dim; the lower-third stays bright on its plate (zoom). `257 ms` and `92 ms` unmarked.
  Pass. The v1 collision of the quote with the safety band is gone.
- Shot 11 (2:23.2 to 2:36.1): kicker and pill on the cut, title at 143.6, left header 143.6,
  `462 ms` counting 144.4 to 145.0 and the green bar to x 290 with the budget tick, `0 of 72`
  landing plain at 146.2 with the green tick, right header 149.8, `31 of 72` counting (the
  `20` at 2:31 is at 55 percent) and the amber fill to x 1243, `0.13 USD` at 153.9. Legible at
  480p; the budget label is 9 px. Pass.
- Shot 12 (2:36.1 to 2:45.3): push 156.07 to 156.80 with the editor and terminal panels, the
  title and kicker on the plate, badge docked in the tab strip, tree rows staggered from
  158.44 (`README.md` active), code lines from 160.33 with the cyan `timeout=1.5` underline
  landing with them and the orange `interventions=[MotionGate(decider)]` at 160.62, the
  status-bar path in cyan for the whole shot, the burst 161.9 to 163.4 at 560 cps, verdict
  underlines green, amber, red from 163.4 with the reasons recolouring. Ten terminal rows fit
  above the panel edge. Finding 6.
- Shot 13a and 13b (2:45.3 to 2:49.3): hard cut to the speaker (74.9 percent frame change,
  clean), lower-third on a plate at 165.65, push-in; 12-frame dissolve into the hall at
  167.27 to 167.67 inside 13b with the pull-out; the lower-third held. Pass.
- Shot 14 (2:49.3 to 2:57.3): 12-frame dissolve from the hall, the mark and the URL at
  169.74 (the URL's apparent early onset in `anchors.txt` is the dissolve), author line
  170.02, span 1 171.83, span 2 173.70 (each 5 frames to 90 percent), tags 174.50 with the
  stagger, the rail full from 176.31, the dip 176.55 to 177.27 on the camera curve (black
  by 177.13), audio silent from 174.9. The URL is on screen and legible for 6.8 s. Finding 8.

## Motion (30 fps)

Anchor onsets measured from the first frame whose region changed against the three frames
before the window; d is measured minus the storyboard's resolved time; ramp is frames from 5
to 90 percent of the final intensity (a 480 ms enter-curve fade reaches 90 percent in 4 to 6
frames; a 240 ms draw in 2 to 3). Full table in `anchors.txt` (88 rows).

| Shot | Entrance | Resolved | Measured | d | Ramp | Note |
|---|---|---|---|---|---|---|
| 1 | DENY (recorded flip) | 0.40 | 0.37 | -0.03 | UI | the webm's own state change |
| 1 | LED bloom | 0.40 | 0.37 | -0.03 | pulses | two pulses visible to 1.0 |
| 1 | spotlight | 0.70 | 0.77 | +0.07 | 11 f | 480 ms element curve |
| 1 | title | 1.06 | 1.10 | +0.04 | 5 f | eased, 16 px rise |
| 1 | rail draw-on | 1.06 | 1.10 | +0.04 | 17 f | 720 ms draw |
| 4 | camera moves 1 to 5 | 0.80, 2.74, 4.24, 6.75, 10.90 | 0.83, 2.77, 4.30, 6.77, 10.93 | +0.03 to +0.06 | 21 to 24 f | each 0.70 to 0.77 s, peak mid-move |
| 4 | step rows 1 to 4 | 1.40, 3.34, 4.84, 7.35 | land with the stops | n/a | 4 to 13 f | region moves with the camera, so measured from the renderer's land frames |
| 5 | title | 36.27 | 36.31 | +0.04 | 5 f | |
| 5 | rows 1 to 5 | 45.31, 46.15, 47.94, 51.25, 52.14 | 45.40, 46.24, 47.94, 51.33, 52.25 | +0.09 to +0.11 | bar 2 f, text 5 f | on `inside the envelope`, `grounded`, `what was asked`, `person`, `what is ahead` |
| 6 | scale travel | 54.17 | 54.23 to 54.77 | +0.06 | 720 ms | move curve, divider retracts with it |
| 6 | ticks and zones | 56.44, 58.34, 60.27, 62.16, 63.97, 65.00 | 56.48, 58.51, 60.31, 62.16, 64.11, 65.01 | -0.0 to +0.17 | 2 to 5 f | on the words |
| 6 | rows 1 to 5 | 66.45, 68.95, 72.47, 74.58, 76.71 | 66.52, 69.02, 72.57, 74.68, 76.81 | +0.07 to +0.10 | chips 4 f | chip scale plus bloom |
| 7 | underlines | 82.40, 83.98 | 82.44, 84.08 | +0.04, +0.10 | 2 f | 240 ms draws |
| 7 | labels, fills, values | see shot notes | -0.26 to +0.07 | | fills 6 f | fills start on the clause (`s%p`), values when the fill stops |
| 7 | PROCEED chip, 583 ms | 93.82, 94.90 | 93.82, 94.97 | 0.00, +0.07 | 4 f, 600 ms count | |
| 8 | nodes 1 to 8 | 99.46, 101.03, 103.38, 107.55, 109.07, 111.59, 115.60, 118.06 | 99.50, 100.80, 103.42, 107.55, 109.11, 111.63, 115.60, 118.10 | -0.23 to +0.04 | 1 to 4 f | node 2 and node 7 start on the clause, within the 240 ms rule |
| 8 | typed lines | human 24 cps, machine 80 cps | measured 23 f and 14 to 20 f ramps | | | cursor hidden during machine rows |
| 12 | tree, code, underlines, burst, verdicts | 158.40, 160.30, 160.36 / 160.85, 162.32, 163.57 | 158.44, 160.33, 160.33 / 160.62, 161.9, 163.37 | -0.23 to +0.04 | 8 f, 7 f, 1 f, burst, 19 f | the cyan underline lands with the code line, no gap |
| 14 | URL, author, spans, tags, dip | 169.74, 169.98, 171.79, 173.66, 174.46, 176.55 | 169.74, 170.02, 171.83, 173.70, 174.50, 176.79 (2 percent) | +0.04 | 5 f | dip on the camera curve, black at 177.13 |

Nothing moves while the voice is not about it: the motion timeline (`motion/runs.txt`, 89
runs above 0.3 percent of pixels) contains only the cuts, the five camera moves, the four
pushes, the real footage, the shot 2 and shot 10 spotlights, the quote exit, the scale
travel, the bar fills and the entrances listed above. Exits mirror: the quote card leaves in
0.2 s, focus frames leave as the camera starts, step rows recolour in 240 ms.

## Transitions

Checked 17 frames at all 16 boundaries (`bounds/trans_*.png`) and 39 frames at the end:
- Hard cuts at 4.00, 5.60, 8.00, 23.00, 53.80, 80.80, 97.23, 133.23, 143.23, 165.27: on
  the frame, no black, no repeated frame, chrome on frame 0 (kicker, title, pill, divider,
  badge), the scale carried across 53.80, the lower-third carried across 5.60 and 167.27.
- Push-left at 13.50, 35.20, 123.73, 156.07: start on the boundary frame, 0.72 s, camera
  curve (slow in and out), outgoing frozen plate pushed left, incoming shot playing from its
  own frame 0 with the kicker and title on the plate; the first words land in the last 40
  percent of the push as designed. No black, no cut mid-entrance. Finding 1 (the rail).
- Dissolves at 167.27 and 169.27: 12 frames inside the incoming shot, smooth.
- Dip to black 176.55 to 177.27 with the rail full from 176.31.

## Audio and captions

- `ebur128`: integrated -16.0 LUFS, true peak -1.5 dBFS, LRA 3.4 LU (both files). No bed, no
  room tone (the -45 dBFS silences are flat).
- v1 and v2 audio are sample-identical (8 kHz mono downmix max absolute difference 0,
  cross-correlation lag 0 samples); the two SRT files have the same md5.
- 48 inter-sentence silences: minimum 0.737 s, eight between 0.74 and 0.76 s, the rest
  longer; the first word at 1.06, the last at 174.86.
- SRT: 57 cues, no line over 42 characters, no three-line cue (the v1 round-3 findings 3 and
  4 are fixed); finding 3 above for the five split pieces under 1 s.

## As a judge

- The hook: DENY and the red LED inside 0.4 s, the frame settles under the title at 1.1 s,
  the real car at 4.0 s. Yes.
- One continuous explanation: shots 5 to 8 keep the split, the divider, the kicker slot, the
  pill slot and the bottom band; the scale travels from shot 5 into shot 6 and its three
  zones tint the bar tracks on 7 and colour the values on 8. The chapter is read as one card
  that changes content. Yes.
- Restating the decision from frames and captions alone: five typed questions with their
  text; a noul answered as a probability; 0.35 and 0.65 making Deny, Confirm, Proceed, plus
  Guide for an invented distance and Deny for a missing decider; one real request scoring
  0.907, 0.948, 0.959 and Proceed in 583 ms; a guessed 2 m scoring 0.18 and Guide, a re-plan
  at 0.5 m scoring 0.404 and Confirm, the operator saying no, the car never moving. Yes,
  with the sound off.
- Honesty: every simulator frame is labelled SIM, FAKE DECIDER, DRAWN FIGURE; the car
  footage is labelled PHASE-3 VISION PLANNER, PRE-DECIDER; the recorded run and the numbers
  carry their dates; the on-car card declares the withheld frames and draws the hole; the
  pattern demo says FAKE DECIDER, STDOUT VERBATIM and the terminal title says "a script, not
  the model"; the Judge badge is hidden on every fake-stack frame and on the car. The decider
  is never framed as the safety layer: shot 4 gives the deadman its own red stop with "needs
  none of it", and the line "Physics stops the car. The decider explains." is on 2, 10 and
  14.
- Ending: URL legible for 6.8 s, author line, both tags, the safety line as the only headline,
  the mark, a 2 s exhale, the dip. Yes.
- Length: 2:57.3, under 3:00, with the last word at 2:54.9.

## Taste

Compared with v1 (`bounds/v1_vs_v2.png`), v2 is clearly the more professional film: the Pit
Wall lives in a panel instead of filling the frame, the chrome is one system (kicker, title,
pill, lower-third with its bar in the right place, badge), the spotlight replaces every circle
and arrow, the probability scale is one object across four shots, the counters and bars behave
like instruments, the camera on shot 4 goes where the voice goes, the dissolves and the dip
look like film. The three places where v1 was arguably stronger: v1's shot 6 vertical ruler
had more presence than v2's thin rule; v1's URL was 48 px; v1's shot 12 showed the code at
once instead of an empty IDE for 4 s.

Five best moments:
1. 0:00.0 to 0:01.3: PROCEED to DENY, the LED, the spotlight and the title landing on the
   first word with the rail drawing on.
2. 0:28.0 to 0:29.8: the 3.0x stop on DeciderGate and Decider 2B, crisp vector type, the
   badge, the orange step row.
3. 1:25.4 to 1:26.5: the cyan leader from `0.2` across the divider to the `args_grounded`
   bar, the fill turning green past 0.65, `0.907` landing.
4. 1:45.3 to 1:48.4: the red `0.18`, the amber `"Guide"` and the orange step `GUIDE:
   re-plan`, three colour systems reading as one sentence.
5. 2:19.5 to 2:22.6: the Pit Wall receding to 30 percent under "Physics stops the car." and
   "The decider explains." in two spans.

Five weakest moments:
1. 0:54.2 to 1:06.4: the empty shot 6 card (finding 4).
2. 0:23.0 to 0:23.8 and 0:34.6 to 0:35.9: the shot 4 full views, kicker over `Amazon
   Bedrock`, the figure's own orange and its 10 px footer (findings 2, 5).
3. 0:35.2 to 0:35.9 and the three other pushes: the rail head sweeping off the frame
   (finding 1).
4. 2:36.1 to 2:40.3: the empty editor and terminal after the push (finding 6).
5. 0:36.3 to 0:43.8: five dim names on the left of shot 5 while the right column explains a
   noul; calm, but 7.5 s of near-empty left half.

Template, default or debug artefacts: the architecture figure's footer and legend row at the
full views (10 px, "the next build's wiring ..."), the figure's own palette, and the cover's
large ribbon S next to the 96 px mark on shot 14. The three-dot panel headers are a chosen
convention. No renderer debug text, no placeholder, no default font, no unreplaced token.

## Not verified

- I did not listen to the audio; every audio statement is measured.
- The glow level on chips (0.45 to 0.20) is visible at 1:1 but I could not separate it from
  the chip's own edge at 480p; it is not absent and not excessive.
- The v1 honesty label wording was not re-read from the v1 frames (its pills sit elsewhere);
  the v2 wording matches `STORYBOARD-v2.md` on every shot.
