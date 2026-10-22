# Round 3: QA of the rendered video

Reviewed: `docs/video/build/deepracer-decider-demo.mp4` (157.5 s, 1920x1080, 30 fps, H.264
465 kbps, AAC 48 kHz stereo) with `docs/video/build/deepracer-decider-demo.srt`, against
`SCRIPT.md` v2, `STORYBOARD.md` v2 and `shots.yaml`. Method: one frame per second at full
resolution and at 854x480, contact sheets of 12 (14 pages each size), 30 fps strips of 11
frames around every cut, close-ups of every pointer and lower-third, `ffmpeg ebur128`
(integrated, true peak, LRA, momentary series), a speech-versus-bed modulation test, the
Polly cache metadata for the real VO durations, and a cue-by-cue SRT check.

Working files (scratchpad, wiped between sessions):
`/private/tmp/claude-501/-Users-vivekrajaps-strands-robots-deepracer/730bd399-92ea-4b34-9bc2-a8347cd3ce22/scratchpad/vreview/`
with `sheets_full/sheet_00..13.png`, `sheets_480/sheet_00..13.png`, `bounds/stack_1.png`,
`bounds/stack_2.png`, `bounds/hook_first_1.2s.png`, `zoom/lower_thirds_2x.png`,
`zoom/honesty_labels_2x.png`, `zoom/collisions.png`, `zoom/pointers_A.png`,
`zoom/pointers_B.png`, `audio/loudness.png`.

## Verdict: ship after fixes

The video is honest, complete and under three minutes (2:37.5), the Decider 2B decision
is readable from the frames alone, and every honesty label the script asks for is on
screen. It is not shippable as rendered because (1) the section lower-third draws its
orange accent bar through the third letter of the text on nine shots, (2) the shot 11
"4069 ms p95" label is cut to "ms p9" by the budget line, (3) the SRT has a 77-character
line and a third line on cue 20 and mid-shot cue drift up to 0.9 s, and (4) the Polly
voice runs at 176 wpm against a shot list timed for 150, so 25 percent of the runtime is
silence with the music bed swelling and card reveals landing after the words they
illustrate. All four are renderer or `shots.yaml` fixes; no re-recording or re-scripting
is needed.

## Scores (1 to 5)

| Dimension | Score | Why |
|---|---|---|
| Hook | 4 | DENY lands at frame 11 (0.37 s) with the LED turning red and a red pulse box; title in by 1.3 s; the real car at 4.0 s. The bed is the only sound for the first second. |
| Clarity | 4 | Five questions, the 13-row mapping and one real answer are on screen verbatim; the architecture figure at 25 percent is unreadable and only the label stack carries shot 4. |
| Proof | 4 | A real recorded run (shots 7, 8) and the on-car card (9) with its source path. The on-car shot is a text card by necessity. |
| Numbers | 4 | All numbers from `docs/results` with units and dates; minus one for the clipped "p95" label on the amber bar and for counters that pass through wrong intermediate values (208, 224, 794, 1831) for a second each. |
| Pattern | 4 | File tree, wiring, three verdicts with reasons, repo path for 11 s plus the close card for 8 s. The terminal rows are illegible at 480p; the highlights still show the shape. |
| Pacing | 2 | 117.9 s of speech in 157.5 s. Holds after the last word: 5.9 s (shot 5), 3.8 s (8), 3.3 s (3), 2.6 s (4 and 12), 2.1 s (9). Shot 5 rows 4 and 5 appear after their sentences; row 5 lands 1.9 s after the VO ends. |
| Legibility at 480p | 3 | Titles, labels, chips, counters and the close card read. Not legible: Menlo 20 badge (9 px), Menlo 22 option sets and key line, the Menlo 24 and 26 terminals (shots 8, 12), the Menlo 26 URL in the shot 12 lower-third (12 px, marginal). |
| Audio | 3 | Integrated -16.0 LUFS, true peak -1.5 dBTP, LRA 6.3 LU: correct for the target. Captions drift; the bed, which the script says does not exist, sits at about -30 LUFS in every gap and rises 8 LU each time a sentence ends. |
| Honesty | 5 | Every label present where the script places it; the Judge badge is hidden on all fake-stack and car frames; the OPERATOR line reads the verbatim auto-answer; the withheld frames are declared on screen. |
| Ending | 4 | Safety line, URL at 48 px cyan, author line, tags, Strands mark, 3 s hold, 0.5 s fade. The URL is readable at 480p. The last 3 s carry only the bed. |

## Findings

Severity: CRITICAL blocks the upload, HIGH is visible to every judge, MED is visible to an
attentive judge or on one device class, LOW is polish. Timecodes are mm:ss.s in the
rendered file; shot numbers follow `SCRIPT.md`.

| # | Sev | Timecode | Shot | Finding | Exact fix |
|---|---|---|---|---|---|
| 1 | HIGH | 0:13.5 to 2:29.5, every section lower-third | 3, 4, 5, 6, 8, 9, 11, 12, 13 | The known bug, confirmed: the 2 px orange accent bar is drawn at frame x 176, through the text ("Vive\|k Raja", "Archi\|tecture", "The \|decision", "Reco\|rded run", "On t\|he car", "The \|numbers", "gith\|ub.com", "AWS\| Community"). It should sit at x 96, 16 px left of the text. The offset equals the plate's left edge (80 px): the bar x is converted to layer coordinates once too few or once too many. | `docs/video/render/draw.py` `TextOverlay._compose_plate` (about line 635): the lower-third bar is created in frame units (`x / c.s - 16`) and then shifted by `- ux0 / c.s`, but `draw_plate` receives the plate box already shifted to layer coordinates, so the bar lands 80 px right. Set the bar in layer coordinates directly: `plate["bar"] = {"color": ..., "width": 2, "x": (pbox[0] - ux0) / c.s + 16}` and skip the later `- ux0` adjustment for that case (or make `draw_plate` take `bx = box[0] + canvas.px(16)` when the plate is a lower-third). Shot 12's explicit `bar: {x: 96}` goes through the same path and shows the same 80 px error, so fix the conversion, not the YAML. Re-render and check `zoom/lower_thirds_2x.png` equivalent. |
| 2 | HIGH | 2:06.5 to 2:14.5 | 11 | "4069 ms p95" renders as "4069 ms p9": the dotted budget line at x 1264 (y 330..534) is drawn after the counter and crosses the unit label; the "5" is not legible. The left column's "498 ms p95" is crossed by its line at x 376 too (legible, but struck through). | `shots.yaml` shot 11 pointers: replace each `dotted` with two segments that avoid the p95 text box (y 390..486): `{kind: dotted, from: [376, 330], to: [376, 386]}`, `{kind: dotted, from: [376, 486], to: [376, 534]}` and the same at x 1264. Alternative in `compose.py`: draw `dotted` pointers under the text layer. |
| 3 | HIGH | 1:38.3 to 1:46.3 | 9 | SRT cue 20 is three lines with a 77-character first line ("On the car, the same gate denied a hop with a person in frame in four hundred" / "fifty"); YouTube will render it as a wide two-line block or clip it. Cue 21 then starts with "six milliseconds". | `audio.py` `split_cue`/`wrap_caption`: the piece exceeds 84 characters because the sentence has no clause boundary; wrap it at a word boundary at 42 and split into two cues at "frame in", or allow `split_cue` to break at " in " when a piece is over 84. Check every cue has at most two lines of at most 42 characters before writing. |
| 4 | HIGH | whole file | all | Caption timing: cue starts at shot boundaries are exact (within 0.1 s), but mid-shot cues are placed by character proportion (`cues_for`) and drift against the spoken sentence boundaries: cue 7 +0.53 s, 12 -0.85, 15 +0.80, 16 +0.65, 18 +0.39, 19 +0.34, 21 +0.88, 23 -0.76, 26 -0.63, 27 -0.60 (positive = speech starts after the cue). Twelve of 33 cues exceed 0.3 s. | `audio.py` `_polly_synth`: request `SpeechMarkTypes=["sentence"]` in a second `synthesize_speech` call (output `json`), cache the marks next to the mp3, and let `cues_for` take the sentence offsets instead of the character ratio. Per-shot cost is one extra Polly call, free for speech marks. |
| 5 | HIGH | 0:13.5 to 2:37.5 | 3, 4, 5, 8, 9, 12 | Pace: the real Polly durations (plain generative cache) total 117.9 s for 345 words, 176 wpm while speaking, against the 150 wpm the shot minimums were sized for. Result: 39.6 s of no speech (25 percent). Holds after the last word: shot 5 5.9 s, shot 8 3.8 s, shot 3 3.3 s, shot 4 2.6 s, shot 12 2.6 s, shot 9 2.1 s. In shot 5 the VO says "Is a person visible" at about 0:45.5 and "What is in front of the car" at 0:47.0; row 4 appears at 0:48.0 and row 5 at 0:50.5, 1.9 s after the voice has finished, then the card sits static for 4.0 s. | `shots.yaml`: either (a) keep the voice and conform the picture: shot 5 rows at `in: 1.0, 2.6, 4.2, 5.8, 7.2` and `min: 11.0`; shot 3 `min: 12.5`; shot 4 `min: 10.5`; shot 8 caption `in: 19.5` and `min: 21.0`; shot 9 `min: 9.0`; shot 12 `min: 9.5` (saves about 12 s, picture ends near 2:25); or (b) slow the voice: the neural `<prosody rate="90%">` cache already exists and runs 5 to 10 percent longer, but it changes the voice character and still leaves 3 to 4 s holds. (a) is the better trade. |
| 6 | MED | 1:56.0 to 1:58.5 | 10 | The safety band plate (y 450..610) is drawn over the quote card (plate y 560..636): "Someone is in front of me. I stopped." sits 22 px under the safety line, half inside the band, dimmed by it, with the orange quote bar poking through. Two messages collide on the one frame a judge is told to remember. | `shots.yaml` shot 10: move the quote card up into the live view, `plate: {box: [150, 300, 1110, 376]}` and text `pos: [176, 314]` (over the figure's torso, clear of the chips at y 560), or give the quote `out: 7.5` so it leaves when the band arrives. |
| 7 | MED | whole file | all | Music bed: `shots.yaml` adds `/Library/Audio/Apple Loops/.../Mellow Drizzle Soft Pad.caf` at -30 LUFS, ducked to -38 under speech. `SCRIPT.md` v2 says "no music and no room tone" (coordinator's decision, no licensed bed). Measured: in every gap the bed sits at -30 to -31 dBFS RMS (momentary -26 to -31 LUFS) and rises about 8 LU within a second of each sentence ending; 14 LU under the voice is audible on a laptop, and the pumping is audible in the 6 s hold of shot 5 and the 3 s tail of shot 14. Modulation test: RMS spread 1.5 to 2.1 dB in the plateaus against 9 to 10 dB for speech, so this is the bed, not speech. | Decide once and document it: either delete `music`, `music_lufs`, `duck_lufs`, `music_crossfade` from `shots.yaml` and keep the script's "no music" line, or keep the Apple Loop (royalty-free for projects made with Apple software), set `music_lufs: -36`, `duck_lufs: -42`, lengthen the duck release in `audio.py` `duck_envelope` to about 2 s, and update `SCRIPT.md` section "Not applied" and `STORYBOARD.md` canvas notes. Fix 5 removes most of the gaps either way. |
| 8 | MED | 0:27.5, 0:39.5, 0:54.5, 1:05.0, 1:15.0, 1:38.0, 1:58.5, 2:14.5 | 4, 5, 6, 7, 8, 9, 11, 12 | Every cut into a card reads as a dip: elements with no `in` (title, lower-third, badge, honesty label, pre-shown terminal lines) fade in over about 0.3 s, so the first 6 to 9 frames after each cut are bare `#0b0b10`. `blackdetect` flags 0:39.5 (0.27 s), 1:05.0, 1:38.0 (0.33 s) and 2:14.5 as black although the storyboard asks for hard cuts with dips only into shots 3 and 14. Shot 4 starts with the figure at 25 percent and no label for 0.3 s, which also reads as a flash. | `compose.py`/`draw.py`: default `fade: 0` for overlays whose `in` is 0 or unset; keep the 0.3 s fade only when `in > 0`. Shot 4: set the first label pair and the R1/R2 outlines to `in: 0.0`. |
| 9 | MED | 0:13.5 to 2:29.5 | 3 to 12 | At 480p the Agent/Judge badge (Menlo 20, 9 px rendered), the shot 5 key line and option sets (Menlo 22, 10 px), the shot 6 row chips (Menlo 24, 11 px), the shot 8 terminal (Menlo 26, 11.5 px) and the shot 12 terminal (Menlo 24) do not resolve. The design knows this (the label stacks and highlights carry the argument) and they do resolve at 1080p on a laptop. | Accept for the terminals; raise the badge to Menlo 24 on a 2-line 60 px plate; raise the shot 5 option sets and key line to 26. No layout shifts needed: there is free space below each row. |
| 10 | LOW | 1:15.0 to 1:38.0 | 8 | Terminal lines differ from the script: `OPERATOR: no (this cell auto-answers False)` and `AGENT: (thinking omitted) The move could not be ...` are the verbatim transcript, where `SCRIPT.md` has `OPERATOR: no (auto-answered by the test cell)`. The rendered text is the more honest one. The closing caption "A guessed distance moved nothing." lands at 1:36.5, 2.3 s after the voice and 1.5 s before the cut. | Update `SCRIPT.md` shot 8 to the verbatim lines (no render change). Caption `in: 19.5` (covered by fix 5). |
| 11 | LOW | 0:08.0 to 0:13.5 | 2 | "Here is why." appears at +4.0 (0:12.0), after the words were spoken (0:11.0 to 0:11.9), and stays 1.35 s before the fade. | `shots.yaml` shot 2: `in: 3.0`. |
| 12 | LOW | 1:48.5 to 1:58.5 | 10 | The fake console's "257 ms" latency chip (inside the cyan highlight) and the "92 ms" stop card are fake-stack numbers on screen next to a cyan pointer; the label says SIM, FAKE DECIDER, but a judge skimming at 480p may read 257 ms as a measurement. | Narrow the cyan highlight to the CLASS and PROBABILITY chips only: `to: [1700, 388]` (the LATENCY chip starts at about x 1710). |
| 13 | LOW | 0:27.5 to 0:39.5 | 4 | Shot 4 is twelve seconds of a figure whose body text is 10 px and whose lit regions still read as dim boxes; the frame is 70 percent dark. It makes sense with the label stack but it is the visually weakest shot, and the on-car deadman box (red outline) is 1.5 s behind the words "The on-car deadman". | Lift `base_brightness` to 0.35 and the settled regions to 0.8; move group 3 to `at: 7.0` (the VO reaches "deadman" at about +6.7 at 176 wpm). |
| 14 | LOW | 1:58.5 to 2:02.0 | 11 | Counters count up over 1.0 s, so single frames show 208, 224, 794 and 1831 ms; anyone who pauses the video on a count frame sees a wrong number. | `count: {over: 0.5}` or start the count at 80 percent of the target. |
| 15 | LOW | 2:29.5 to 2:37.5 | 14 | The author line "Vivek Raja, AWS AI Hero \| Article on AWS Builder Center" is Regular 30 ink-dim at 40 percent cover brightness; at 480p it is readable but faint next to the 48 px URL. | `size: 34`, `color: ink`. |

Nothing CRITICAL. No text is outside the title-safe margin except the shot 10 caption,
which sits in the portal header on purpose and is inside the frame; no text sits on busy
footage without a plate; no pointer misses its target (checked: shot 2 circle, chip boxes
and arrow; shot 4 badges, outlines and the orange arrow to the car; shot 7 underlines and
arrow to the args_grounded bar; shot 10 arrow to the CLASS chip and both highlights; shot
11 arrow to the footnote; shot 12 six highlights). No duplicated frames or overlays
vanishing before a cut were found in the 15 boundary strips; the GIF in shot 1b is frame
blended and smooth.

## Shot by shot

Timecodes are the rendered boundaries (from `blackdetect`, scene scores and the 1 fps
sheets): 1 0:00.0, 1b 0:04.0, 2 0:08.0, 3 0:13.5, 4 0:27.5, 5 0:39.5, 6 0:54.5, 7 1:05.0,
8 1:15.0, 9 1:38.0, 10 1:48.5, 11 1:58.5, 12 2:14.5, 13a 2:25.5, 13b 2:27.5, 14 2:29.5,
end 2:37.5. The VO windows come from the Polly cache durations (plain generative Matthew),
which match the SRT cue ends to 0.1 s.

- Shot 1 (0:00.0 to 0:04.0): PROCEED with the clear frame for 11 frames, the figure and
  DENY at frame 11 (0.37 s), `LED RED` with a red pulse box from 0.4 s, the freeze at
  0.7 s. Title fades in 1.0 to 1.3 s; VO 1.0 to 2.8. Honesty label on the bg column from
  frame 0. Legible at 480p. Badge hidden. Pass.
- Shot 1b (0:04.0 to 0:08.0): the car drives away and back on the tiles, blur fill, the
  caption plate top-left, `REAL CAR, PHASE-1 RECORDING, UNGATED` plate bottom-right. VO
  4.5 to 7.0. Pass.
- Shot 2 (0:08.0 to 0:13.5): circle at 8.3, chip boxes and arrow at 9.0, red DENY
  highlight at 10.5, `Here is why.` at 12.0 (finding 11), safety footer from frame 0.
  VO 8.3 to 12.0. Fade to black 13.35. Pass with the LOW note.
- Shot 3 (0:13.5 to 0:27.5): from black over 0.3 s; callouts at 14.0, 15.8, 17.6, 19.4,
  21.2, 23.0, 24.8; settle at 26.8. VO 13.9 to 24.2, then 3.3 s of bed. Label plates
  legible at 480p; the baked callout text and the baked footer are decoration. Lower-third
  tick bug (finding 1). The 1.8 s cadence suits the voice until the last two callouts
  (Bidi, Box) land after "judges the command and the frame".
- Shot 4 (0:27.5 to 0:39.5): groups at 27.8, 32.0, 36.0; VO 27.8 to 36.9; 2.6 s hold.
  Label stack legible at 480p; figure not (by design). Findings 1, 8, 13.
- Shot 5 (0:39.5 to 0:54.5): rows at 40.5, 43.0, 45.5, 48.0, 50.5; VO 40.5 to 48.6; 5.9 s
  hold. Row text legible at 480p, options and key line not. Findings 1, 5, 9.
- Shot 6 (0:54.5 to 1:05.0): bands at 55.0, 57.5, 60.0, 62.5; footnotes at 60.0; the
  arrow grows band by band; the ruler shade pulses with CONFIRM; VO 54.8 to 64.1. Pass
  apart from findings 1 and 9.
- Shot 7 (1:05.0 to 1:15.0): typing 65.3 to 67.3; underlines at 66.5; bars at 67.5, 68.7,
  69.9 turning green past the YES rule; PROCEED and 583 ms at 71.3, held 3.7 s; VO 65.3
  to 73.6. `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO` on a plate. Pass.
- Shot 8 (1:15.0 to 1:38.0): typing at 40 cps with the highlights in the order spoken;
  label lines at 76.6, 81.0, 83.0, 87.0, 92.1; caption 96.5; VO 75.3 to 94.2; 3.8 s hold.
  Legible at 1080p only (the label stack is borderline at 480p). Findings 1, 5, 9, 10.
- Shot 9 (1:38.0 to 1:48.5): lines at 98.3, 102.0, 104.5, 106.5; VO 98.3 to 106.4; the
  two-line honesty label on its plate; the badge shown (true here). Pass apart from the
  tick and the caption cue (findings 1, 3).
- Shot 10 (1:48.5 to 1:58.5): caption plate at 108.8; arrow and chip highlight at 109.5;
  red DENY at 111.0; quote card at 113.5; dim and safety band at 116.0; VO 108.8 to
  117.2. Honesty label covers the portal's voice widget, legible. Findings 6, 12.
- Shot 11 (1:58.5 to 2:14.5): left counters 119.0, 120.0, "0 of 72" 121.5, cost 123.0;
  right 125.5, 127.0, "31 of 72" 128.5, cost 130.0; footnote and arrow 127.5; VO 118.8 to
  132.9. The amber bar reaches x 1744 and the arrow drops to the footnote. Finding 2
  (p95 label), 14 (count frames).
- Shot 12 (2:14.5 to 2:25.5): tree and wiring at 134.8; cyan `timeout=1.5` at 136.0;
  orange `interventions=[MotionGate(decider)]` at 137.0; terminal typed 139.0 to 141.0;
  six highlights at 141.5; VO 134.8 to 142.9; 2.6 s hold. URL in the lower-third for the
  whole 11 s (12 px at 480p, marginal). Findings 1, 9.
- Shot 13 (2:25.5 to 2:29.5): speaker still 2.0 s (the author with the car on stage,
  approved), hall still 2.0 s (approved crowd photo), plate lower-third, fade to black
  at 149.35. VO 145.8 to 148.5. Finding 1 on the plate.
- Shot 14 (2:29.5 to 2:37.5): from black 0.3 s; stack fades in 149.9 to 150.9; VO 149.9
  to 154.5; hold; fade to black 157.0 to 157.5. URL readable at 480p. Finding 15.

## Audio

- `ebur128`: integrated -16.0 LUFS, true peak -1.5 dBTP, LRA 6.3 LU, threshold -27.0.
  `astats`: peak -1.51 dBFS, RMS -19.8 dBFS, flat factor 0, two peak samples. No clipping.
- Speech: 345 words in 117.9 s of Polly audio (plain generative Matthew; the SSML neural
  and SSML generative caches are not the ones in the mix): 176 wpm while speaking, 135 wpm
  over the span from the first word (1.0 s) to the last (154.5 s). Voice momentary p50
  -16.1 LUFS, p90 -13.5, max -10.5.
- Gaps with no speech over 1.5 s: 2.8 to 4.5, 12.0 to 13.9, 24.2 to 27.8 (3.6 s), 36.9
  to 40.5 (3.6 s), 48.6 to 54.8 (6.2 s), 73.6 to 75.3, 94.2 to 98.3 (4.1 s), 106.4 to
  108.8 (2.4 s), 117.2 to 118.8, 132.9 to 134.8 (1.9 s), 142.9 to 145.8 (2.9 s), 148.5 to
  149.9, 154.5 to 157.5 (3.0 s, planned). The script's budget was 1.5 s.
- Bed: present (see finding 7), -30 to -31 dBFS RMS in the gaps, ducked to about -38
  under speech, release under 1 s, so the bed steps up about 8 LU at the end of every
  sentence. No abrupt level change inside the bed itself; the loop crossfades cleanly.
- Captions: 33 cues, 345 words, all cue starts at shot boundaries within 0.1 s of the
  speech onset; mid-shot drift as in finding 4; cue 20 malformed as in finding 3.
- Momentary plot: `audio/loudness.png` in the scratchpad (cyan momentary, orange
  short-term, yellow bands are SRT cues, white lines are shot boundaries).

## Transitions

Checked 11 frames (5 either side) at all 15 boundaries, `bounds/stack_1.png` and
`bounds/stack_2.png`:
- 0:04.0, 0:08.0, 2:25.5, 2:27.5: hard cuts, clean, no black, no repeated frame.
- 0:13.5 and 2:29.5: designed dips (0.15 s fade out plus 0.3 s from black), correct.
- 0:27.5, 0:39.5, 0:54.5, 1:05.0, 1:15.0, 1:38.0, 1:58.5, 2:14.5: hard cuts into cards
  whose static elements fade in over about 0.3 s, so they read as short dips (finding 8).
  1:48.5 (portal still) is instant and correct.
- No cut lands mid-animation: every reveal completes before its shot ends (the shot 8
  AGENT reply finishes typing at 97.5, cut at 98.0). No overlay disappears early.
- Longest static frame with nothing moving: shot 5 from 50.8 to 54.5 (3.7 s) and shot 3
  from 26.8 to 27.5 after the settle; shot 8 holds with the caption from 96.5 to 98.0.

## As a judge

- The decision: yes, from frames and captions alone. Question set (shot 5, verbatim with
  types and option sets), the mapping to Proceed/Guide/Confirm/Deny by thresholds (shot
  6), one real request with three probabilities and the verdict (shot 7), and the
  recorded Guide then Confirm then "asks instead of driving" (shot 8). A sound-off viewer
  gets it from the orange label stacks even where the terminals are too small.
- Reusable pattern: visible for 11 s with the repo path in the lower-third (Menlo 26) and
  again for 7.5 s at 48 px on the close card. Over 4 s on both counts.
- Could anything read as faked: no. The sim frames are labelled on every frame, the car
  footage is labelled ungated, the judge badge is hidden where the decider is fake, the
  recorded run shows its auto-answered operator, the on-car card declares the withheld
  frames, the pattern demo says "fake decider, stdout verbatim". The only soft spot is
  the fake console's 257 ms and 92 ms sitting under a cyan highlight (finding 12).
- Safety line: shot 2 footer, shot 10 at 72 px, shot 14 at 56 px, plus the portal's baked
  footer on every sim frame. The decider is never called a safety layer.
- Length: 2:37.5 picture, last word at 2:34.5. Under 3:00 with room for the fixes.

## Not verified

- I did not listen to the audio; every audio statement comes from measurement.
- The Apple Loop licence for distribution on Builder Center was not checked.
- Frame 0 from the 1 fps extraction shows DENY while the 30 fps strip from 0.0 shows
  PROCEED until frame 11; the 30 fps strip is the one I trust.
