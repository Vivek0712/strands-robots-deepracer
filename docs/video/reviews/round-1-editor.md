# Round 1 editor review: SCRIPT.md and STORYBOARD.md before the edit

Reviewer role: senior video editor and motion designer. Date: 2026-10-22. Inputs read:
`docs/video/SCRIPT.md`, `docs/video/STORYBOARD.md`. `docs/video/ASSETS.md` did not exist at
review time, so every asset was probed directly (ffprobe, PIL, contact sheets at one frame per
3 s for the YouTube source and finer for the webm and the GIF; all sheets were looked at, not
inferred). Text widths were measured with the real `HelveticaNeue.ttc` and `Menlo.ttc` on this
Mac, not estimated. Nothing outside this file was modified.

## Asset facts the script assumes but the files do not provide

| Asset | Measured | Script / storyboard assumes | Consequence |
|---|---|---|---|
| `docs/media/car-hop.gif` | 4.00 s, 48 frames at 12 fps, 640x360, but the picture is a portrait phone clip pillarboxed inside the GIF: content occupies x 217..422 only (206x360 px); black bars are baked in | 4 s, "scaled to 1600 wide with a blurred copy behind to fill the letterbox" | Scaling the whole GIF to 1600 wide gives a 515x900 car strip flanked by baked black bars that no blur-fill can remove. The content must be cropped to x 217..422 first; fitted to 1080 tall that is a 3x upscale (618x1080), soft but usable with a blur-fill. Shot 1 is 5 s on a 4 s asset. |
| `docs/results/portal/pitwall-sim.webm` | 7.80 s, 1280x720, VP9 25 fps, no audio. Timeline: 0.0-2.6 PROCEED (clear); 2.7 stick figure walks in; 2.9-3.5 DENY with `LED RED`; 3.6 CONFIRM (figure gone); 3.6-7.8 CONFIRM then PROCEED, LED amber | "the DENY segment", 7 s of picture with a freeze from 0:10 | The DENY segment is 0.6 s long and the figure is on screen for 0.9 s. At the storyboard's timing the red circle at 0:06 would circle an empty frame and the freeze at 0:10 would freeze a CONFIRM. The freeze must start at webm 3.2 s. |
| `fig-deepracer-strands.png` | 1600x900; a title ("One stock AWS DeepRacer, every kind of Strands"), a subtitle and a footer ("Physics stops the car; the decider explains.") are baked in top-left and bottom-left; the seven callouts already carry coloured leader lines (violet, green, red, orange, cyan, amber, grey); callout body text is about 14 px at native size | A new title top-left, cyan leader lines drawn as each callout appears | The two titles collide; the drawn cyan lines double the baked coloured lines; at 1728 wide the callout text is 15 px and unreadable on a 1080p stream. |
| `fig-architecture.png` | 1600x900, dense; body copy about 12 px at native size | Scaled to 1280x720 at 25 percent brightness, the 300 ms rule "in red" visible | At 0.8x the body copy is 9-10 px; nothing inside the figure is readable, including the 300 ms rule. The five label-stack lines must carry the shot alone (they do). |
| `fig-portal-stage.png` | 1920x1080 native; `SIM` chip, `RED LED` chip and the baked footer "Physics stops the car; the decider explains." are in the frame; a red `LIVE` badge top-left | As described | Correct and clean. Only note: the top-left caption position collides with the baked `PIT WALL` wordmark (see findings). |
| `cover.png` | 1200x675 | Backdrop at 40 percent | 1.6x upscale at 40 percent brightness: fine. |
| `event-speaker-with-car.jpg` | 1200x1600 portrait, the author alone on stage; the screen behind shows a Chrome address bar with a `file:///Users/...` home path, illegible at 1.5 s and fitted to height | As described | Fine. |
| `event-hall.jpg` | 1600x1200; roughly 80 attendees from behind, several faces visible in profile at the left and in the second and third rows | "No face other than the author's appears" | The checklist claim is wrong as written; the photo is the approved event photo, so keep it but reword the checklist (finding L4). |
| `strands-mark.svg` | present, 1175 bytes | Shot 14 | Fine. |
| `docs/video/raw/youtube-y_gZVc2tNDQ.mp4` | 173.0 s, 1920x1080, VP9 60 fps, AAC 44.1 kHz stereo. Captions are burned in (white Menlo on a black box, about 90 px tall, y 635..830 when two lines) for almost the entire runtime, plus a "Vivek Raja" name badge bottom-left in every talking-head shot | Optional alternative for shot 1 | See the YouTube section below. Nobody other than the author appears anywhere in the video. |
| `docs/video/build/clips/` | The scout has already produced `car-hop-1080p.mp4` (4.0 s, the GIF content cropped and pillarboxed to 618x1080 on black, not blur-filled), `pitwall-sim-1080p.mp4` (7.8 s) and sixteen `yt-*` cuts; the "clean" YouTube crops are 1.8x upscales of part of the car inset and run 3.8-4.0 s | Not referenced | Use `car-hop-1080p.mp4` as the shot 1 and 9 source but add the blur-fill; the YouTube crops are second choice (below). |

## Findings

Severity: Critical = the shot does not work as written; High = a judge will notice; Medium = quality; Low = polish or wording.

| Severity | Shot | Finding | Exact fix |
|---|---|---|---|
| Critical | 2 | The webm DENY segment is 0.6 s (webm 2.9-3.5 s), the figure is in frame only 2.7-3.5 s, and the CONFIRM verdict replaces DENY at 3.6 s. Playing "the DENY segment" from 0:05 and freezing at 0:10 leaves the circle (0:06) around an empty frame and freezes on CONFIRM. | Start the webm at 2.5 s at 0:05.0, play at native speed to webm 3.2 s (0:05.7, the figure is in and DENY and `LED RED` have landed at 0:05.4), freeze that frame for the rest of the shot. Draw the circle at 0:06.0, the arrow at 0:07.0, the LED pulse at 0:05.4 (as it goes red, not 0:08), `Here is why.` at 0:09. |
| Critical | 2, 10 (all overlays) | VO is longer than picture on seven shots. Counting the read-through copy with `wc -w` per shot at 150 wpm plus a 0.35 s sentence pause (Polly generative Matthew sits at 145-155 wpm and pauses at full stops; spoken numbers read slower): shot 3 needs 18.2 s for 16 s of picture, shot 4 19.4/18, shot 5 16.9/14, shot 6 11.1/10, shot 7 12.2/11, shot 10 12.6/10, shot 11 22.6/20, shot 13 3.2/3. Total VO estimate 2:52 against a 2:48 picture; the script's "last word at 2:46" assumes no pauses at all. | Render Polly first (one request per shot, keep the per-shot MP3s) and conform picture to the measured VO, not the other way round. Independently of that, trim words so no shot exceeds 150 wpm on its picture: shot 3 drop "driven as a Strands robot" from the VO (it is the on-screen title); shot 5 drop "Five typed questions in two requests." (it is the title) so the VO is only the five questions; shot 6 drop "Code owns the thresholds and"; shot 7 drop "One real answer."; shot 10 drop "On the Pit Wall,"; shot 11 drop "The local two B costs nothing per decision." (the 0 USD counter says it) and move its emphasis to the card; shot 13 fine once the stills run 2 s each (see timing table). That removes 31 words, about 13 s, and brings the VO to about 2:39 on a 2:48 picture. |
| High | 1, 9 | `car-hop.gif` is pillarboxed inside its own 640x360 canvas (content x 217..422). The storyboard's "1600 wide plus blurred copy behind" would show baked black bars with a blur behind them. Also 12 fps on a 30 fps timeline duplicates frames in a 2-3-2-3 pattern (visible stutter on the car's motion), and shot 1 is 5 s on a 4 s asset. | Crop to x 217..422 (206x360), fit to 1080 tall (618x1080, 3x, use lanczos), centre it, put a 24 px gaussian blur of the same crop scaled to 1920x1080 behind it at 60 percent brightness. Render the GIF at 12 fps with frame blending (`minterpolate` or ffmpeg `-vf tblend` is not needed; `fps=30` with `-vsync cfr` plus `minterpolate=mi_mode=blend` softens the stutter). Shot 1: hold the last frame for the fifth second (the car is stationary at the end of the return hop, so the hold is invisible); or move the car to 0:08-0:12 with the VO bridge in the alternative open below, which needs exactly 4 s. |
| High | 1, 9 | Title at 64 px white over the blurred GIF: the blurred copy is light grey (the tiled floor), so the title and the three-node strip (shot 9) sit on a bright field with no scrim. Measured: the floor averages about 70 percent luminance; white-on-that is under 2:1. | Put the title on the Section plate (60 percent `#0b0b10`, 16 px padding) or darken the blur-fill to 35 percent brightness; give the three-node strip in shot 9 a plate. Rule for the whole piece: any text over footage or a photo sits on a plate; only text on `#0b0b10` cards goes bare. |
| High | 3 | `fig-deepracer-strands.png` has its own baked title top-left; the storyboard's new 64 px title lands on top of it. The seven baked leader lines are already coloured per callout, so drawing cyan ones adds a second line to each. At 1728 wide the callout text is about 15 px and cannot be read. | Crop the figure to y 100..900 (drops the baked title and subtitle; the footer line stays, it is the safety line and belongs) and scale that 1600x800 to 1728x864 centred. Do not draw extra leader lines; reveal each callout box plus its baked line by mask. Add our own 30 px label stack top-right with the seven short names (`Decider on the camera`, `strands-robots on the drive`, ...) appearing with each callout, in the same style as shot 4's stack, because the baked text is decoration at this size. Reveal every 1.5 s is fine for a 3-4 word label (3 words per second plus 1 s = 2 s is the limit; 1.5 s is acceptable because the next label does not remove the previous). |
| High | 5 | Reveal is faster than reading. Each row carries a 10-12 word question plus an option set (the `frame` row has five options); at 3 words per second plus 1 s each row needs 4.5-5.5 s, the storyboard gives 2 s. The whole card holds about 70 words and 14 s of picture; it needs about 25 s to read. | Keep the verbatim questions (the judges value them) but show them one row at a time: rows at 0:47, 0:49.5, 0:52, 0:54.5, 0:57 (2.5 s), and render the option sets in Menlo 22 px ink-dim as the storyboard says but only for the two choice rows, in one line each. Accept that a viewer reads two rows fully; the VO names all five. Alternatively move the `person` and `frame` rows to a second beat at 0:57-1:00 under a "Request 2" header while rows 1-3 dim to 70 percent. |
| High | 6 | Same problem, worse: the DENY band is 15 words, GUIDE 12, and a band arrives every 2 s. Four bands plus the footnote are about 55 words in 10 s. | Replace the prose in each band with chips: `DENY  rows 1-6` then six small chips `decider down` `late` `no frame` `person` `off surface` `"stop"`; `GUIDE  rows 7-11` with `outside envelope` `not grounded` `question / unrelated` `obstacle near`; `CONFIRM  row 12` with `0.35 <= p < 0.65` `ask the operator`; `PROCEED  row 13` with `otherwise`. Chips scan in about half the time of a sentence. Keep the footnote (56 chars, 654 px at 26 px, fits) but bring it in at 1:06 with the CONFIRM band, not at the end. |
| High | 11 | The latency bars overflow the frame. Storyboard: 1500 ms = 420 px, so the Nova Pro p95 bar (4069 ms) is 1139 px long inside a column that is 864 px wide and starts at x = 960; the bar ends at x = 2099, outside the 1920 canvas. | Scale 1500 ms = 280 px: p95 4069 = 760 px, fits the column with the label; the dotted budget line sits at 280 px from the column's left edge on both columns. The 2B bars (462, 498) are 86 and 93 px, still legible as "short". |
| High | 12 | Panel 2 code does not fit a 576 px panel at Menlo 28 px (16.85 px per character, 34 characters per line): the `model=BedrockModel(...)` line is 79 characters (1343 px, wraps to three lines) and `interventions=[MotionGate(decider)]` is 35 characters (590 px, one character over). Panel 3 is a 1920 px terminal capture shrunk into 576 px; its 100-character JSON rows become 6 px type. | Change the layout to two rows: top row panels 1 and 2 side by side (panel 1 at 480 px, panel 2 at 1200 px, code at 28 px with the model line wrapped by hand after `model_id="us.amazon.nova-pro-v1:0",`), bottom row panel 3 at the full 1728 px, cropped from the capture to the three JSON rows at 100 percent (Menlo 20 px captured at 1920 wide reads as 20 px, borderline; capture at 24 px instead). Verdict chips sit at the right end of each row, no bracket needed. |
| High | 14 | The fade to black "over 0.5 s at 2:48" runs past the stated picture end of 2:48 and the audio spec says nothing about the tail. | Picture ends 2:48.5; start the fade at 2:48.0. Or start it at 2:47.5 and end at 2:48.0. Pick one and put the number in the script's duration line. |
| High | all | No sound plan beyond the VO. The script leaves 14 s of silence (hook freeze, transcript freeze, Mumbai stills, the closing hold) and the GIF and webm carry no audio; a VO-only 2:48 with dead air reads as unfinished. The -16 LUFS target in the storyboard is for the mix, and the mix is undefined. | Add a low instrumental bed at about -28 LUFS, ducked 6 dB under the VO (sidechain or keyframes), ending on the close with the last VO word; if the hackathon rules forbid music, add room tone at -45 LUFS so the silences are not digital zero, and keep the longest VO gap under 2 s by moving VO lines as in the timing table. |
| Medium | 2 | Pointer target ambiguous: in the webm (the older "main" layout) the LED is the header label `LED RED`, about 80x10 px at 720p (120x15 px at 1080p). A pulse on it reads as a glitch. Also the script lists the chips as `person_in_frame` `0.97` `Deny`: the webm's live view has only two chips (FRAME CLASS, PROBABILITY); the `Deny` frame-verdict chip exists only in the Stage layout (`fig-portal-stage.png`). | Scale the webm 1.5x and crop to the live view plus verdict panel (webm x 0..910, y 40..720, which becomes 1447x1080, anchored left; the audit column is dropped, nothing is lost). The LED label becomes about 180x22 px; pulse a 3 px red rounded rectangle around it with the 12 percent fill. Correct the script text to two chips. The `SIM, FAKE DECIDER, DRAWN FIGURE` label goes on the plate bottom-right over the remaining 470 px, which is now empty `#0b0b10`. |
| Medium | 2, 10 | Orange pointers on the portal frames compete with the red DENY, the red STOP ALL button and the red LED; orange and red at 4 px strokes read as the same colour at a glance. | On shots 2 and 10 use cyan for the arrows and the circle, keep red only for the LED pulse and the DENY highlight. Reserve orange for cards (shots 4-8, 11, 12), where it marks the Decider as the storyboard intends. |
| Medium | 10 | `Row 3: person in frame -> Deny` at top-left collides with the baked `PIT WALL  agentic DeepRacer on strands-robots` wordmark and the `1 Stage  2 Operator  3 Settings` tabs. | Put the caption on a Section plate at top-centre (x 700..1220 is empty header) or drop the caption and let the DENY highlight at 1:56 do its job. Drop the 1:58 highlight on `92 ms`: it is a fake-stack stop latency and inviting the judge to read a SIM number as a measurement undercuts shot 11's real ones. The arrow to `person_in_frame 0.97` at 1:54 and the DENY highlight at 1:56 are enough. |
| Medium | 7 | The orange arrow from `"distance_m": 0.2` to `args_grounded 0.907` points at the wrong evidence: grounding is the relation between `0.2` and the words `20 centimetres` in the conversation line. | Draw a cyan bracket joining `20 centimetres.` (line 1) and `0.2` (line 2), and one orange arrow from the bracket to the `args_grounded` bar. Also the three bars fill "2 s each" from 1:13 means the last bar completes at 1:19 and the chip lands at 1:19 with 2 s of picture left; the VO reaches "Proceed" at about 1:19.5. Fill the bars over 1.2 s each from 1:12.5 so the chip can land at 1:17 and hold 4 s. |
| Medium | 8 | The label stack's longest line, `5 Operator: no. The agent asks instead of driving.`, is 660 px at 30 px; the right third is 576 px, so it wraps. The terminal at Menlo 26 in the left two-thirds (1152 px, 73 characters per line) wraps every gate row (115 characters) to two lines and the AGENT line to three: 18 lines at 36 px leading = 650 px, which fits. | Shorten line 5 to `5 Operator: no. The agent asks, it does not drive.` (needs 560 px; or allow the wrap and give the stack 600 px). Keep the transcript wrapping; it reads as a terminal. Typing at 40 characters per second is right for Menlo 26 at reading pace; stop typing (freeze the cursor) while the VO says each number so the highlight box is the only motion. |
| Medium | 13 | 1.5 s per still is under the reading time for the lower third (7 words, 3.3 s) and the hall photo is the weakest frame in the piece at this length. | Run the speaker still for 2 s and the hall still for 2 s (4 s total, the extra second comes from shot 11's trim). If a second needs cutting later, cut the hall still, never the speaker still. |
| Medium | 3 to 12 | The judge/agent badge is Menlo 22 px ink-dim without a plate, bottom-left, on top of the section lower-third. On shots 4 (the figure's left column), 8 (the terminal) and 11 (the footnote) it overlaps content. | Give the badge its own plate and pin it top-right under the safe margin on shots 4-8 and 11 (where the top-right is free or holds the label stack: put the badge under the stack); on shots 3, 9, 10 keep it bottom-left. Or show it once, large, in shot 3 (it is spoken there) and retire it. |
| Medium | all | Honesty labels at Menlo 24 all caps ink-dim: on a 1080p stream fine (14 px per character); YouTube at 480p or a phone renders them 10 px tall, illegible. | 28 px, same plate. The longest label (`RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`, 44 characters) is 740 px at 28 px, still clear of the section lower-third on the left. |
| Medium | all | The renderer disagrees with the storyboard: `docs/video/render/draw.py` has `SAFE_Y = 72` (storyboard 54), cyan `#4cc9f0` (storyboard `#3ddcff`), orange `#ff7a1a` (`#ff6b3d`), text `#f3f4f6` (`#f2f2f7`), muted `#8b8f98` (`#a0a0ad`), and no amber, violet or green-for-LED tokens. | Pick one source of truth. Recommendation: the storyboard palette (it matches the article figures the video cuts to) and `SAFE_Y = 54` only if every lower-third baseline is recomputed; otherwise adopt 72 in the storyboard. Either way change one file, not both. |
| Low | 2 to 3, 13 to 14 | Dips to black (0.3 s) at 0:12 and 2:39 start exactly when the next VO line starts; the voice begins over black. | Start the VO of shots 3 and 14 at the end of the dip (0:12.3, 2:39.3) and let the dip begin 0.3 s inside the previous shot. |
| Low | 14 | Hierarchy: the 72 px safety line dominates a card whose job is the URL and the two tags. URL at Menlo 40 cyan (1080 px wide) is on screen from 2:40.8 to 2:48 = 7.2 s, over the 4 s minimum. | Safety line 56 px, URL 48 px (1296 px wide, fits), tags 32 px, author 30 px. Fade the stack in over 1.0 s instead of 1.5 s. |
| Low | all | Contrast on `#0b0b10` (WCAG, measured from the hexes): orange `#ff6b3d` 6.9:1, cyan `#3ddcff` 12.0:1, ink-dim `#a0a0ad` 7.6:1, red `#ff4d4f` 6.0:1, amber `#ffb347` 11.5:1, green `#3fb950` 7.7:1; chip text `#0b0b10` on red 6.0:1, on green 7.7:1. All pass AA for 24 px and above. Orange at 22 px (the `#guardrails` tag) still passes. | No change. Only avoid orange text under 20 px anywhere. |
| Low | storyboard checklist | "No face other than the author's appears" is false for `event-hall.jpg` (profiles visible). | Reword: "No third party is identifiable except in the approved AWS Community Day crowd photo, used as published by the organisers." |
| Low | 5 | `noul` is the correct Strands Decider question type (confirmed in `patterns/strands/_client.py`), but a judge may read it as a typo. | Add a 22 px ink-dim key under the title: `noul = yes/no as a probability, choice = one of a set`. |
| Low | script | The fallback order cuts picture (shot 11 footnote, shot 3 reveal pace) when the overrun is in the VO; neither saves a second of audio. | Replace with the VO-first fallback in the timing section below. |
| Low | captions | No SRT or caption plan although the brief's "sound off" test is about on-screen text, not accessibility; YouTube auto-captions will be wrong on "Nova Pro", "noul", "rosbridge", "two B". | Build the SRT from Polly speech marks (`--speech-mark-types sentence`), one cue per sentence, 42 characters per line maximum, two lines, and upload it as a sidecar; do not burn it in. Note that YouTube draws captions bottom-centre at y 940-1040, between the two lower thirds; they will cover the shot 14 author line, which is why the author line should sit above the tags, not below them. Also attach the read-through copy as the submission transcript. |

## YouTube source (`youtube-y_gZVc2tNDQ.mp4`): what is worth using

Watched as two 6x5 contact sheets at one frame per 3 s, then at 2-4 fps on the three car
segments. People: only the author appears, in a talking-head framing with a burned-in
"Vivek Raja" badge bottom-left; no other person at any time. Burned-in captions cover
y 635..830 for almost every second, so any crop must either avoid that band or sit in the gaps.

| Seconds | What | Crop | Verdict |
|---|---|---|---|
| 0:05.5-0:09.0 | Author holds the white-shell car to camera ("I have converted this AWS DeepRacer") | x 480..1600, y 0..630 (16:9, 1.7x upscale, caption band excluded; the name badge is excluded too) | Usable for 3 s if a human face is wanted in shot 3 under `I am Vivek Raja`; label `2026 PHASE-1 VIDEO`. Optional. |
| 0:31.5-0:38.7 | Car inset (portrait, x 1265..1832, y 35..1045, 567x1010) moving two seconds forward and two reverse on the same tiled floor as the GIF. This is the same clip as `car-hop.gif` at 2.75x the pixels and 60 fps | The inset, fitted to 1080 tall (1.07x) | The caption box overlaps the inset's lower-left and the car itself from 0:31.5 to 0:37.9; only 0:38.0-0:38.7 is clean. The scout's `yt-16-...-clean.mp4` (3.8 s) crops a sub-region to dodge the caption and runs 1.8x; it cuts the car at the bottom in its first two seconds. Use the GIF crop for shots 1 and 9; use YouTube 0:38.0-0:38.7 only as a 0.7 s button if a cleaner end frame is wanted. |
| 1:20.0-1:26.0 | Car inset, the 360-degree circle seen from above, car far from camera | x 1330..1832, y 35..1045 (caption clear in this window) | Clean but the car is 60 px tall; reads as "a thing turning". Not worth a slot in a 2:48 cut. |
| 1:27-1:30 | Circle, car near the camera | inset | Caption covers the car. Skip. |
| 2:13.5-2:17.0 | Detour around an obstacle inside the phase-2 planner UI (camera feed inset at x 690..1080) with the `REPLAN: Car in front detected, need to avoid it` log line | UI inset | Caption covers the lower half of the feed throughout; the UI is phase-2 and not what the submission is about. Skip. |
| 0:28-0:31, 1:03-1:21, 2:07-2:13 | Phase-1 and phase-2 planner UIs | full frame | Not this project's UI; a judge would take it for the current one. Skip. |

Net: the YouTube file contributes at most 3 s (author with car) plus a 0.7 s button; the GIF crop
stays the car source. Do not use any talking-head second without the top-of-frame crop, because
the burned captions and badge would fight our lower thirds.

## Alternative open (stronger hook, same assets)

The current open is 5 s of a small grey car on a grey floor in a pillarbox with a title. A judge
scrolling a playlist sees nothing red in the first three seconds. Proposed 0:00-0:12, same length,
same VO lines, reordered so the refusal is the first thing on screen:

| Time | Picture | Text | VO |
|---|---|---|---|
| 0:00.0-0:00.4 | Black, then the webm cropped to live view plus verdict (webm x 0..910, y 40..720, scaled 1.59x to 1447x1080, anchored left) starting at webm 2.5 s: a clear frame, PROCEED | `SIM, FAKE DECIDER, DRAWN FIGURE` from frame 0 on the plate bottom-right | silence |
| 0:00.4-0:01.0 | The figure walks in (webm 2.7 s), DENY lands and the LED turns red (webm 2.9 s); the LED pulse fires on the cut to red | | |
| 0:01.0 | Freeze on webm 3.2 s | Title `This car just refused an order.` on a plate, lower-right of the verdict panel, 0.3 s fade | `This car just refused an order.` (0:01.2-0:03.5) |
| 0:04.0-0:08.0 | Hard cut to the car (GIF content crop at 618x1080 with blur-fill), all 4 s native | `REAL CAR, PHASE-1 RECORDING, UNGATED` from the cut; title stays until 0:06 | `This is a stock AWS DeepRacer.` (0:04.5-0:06.5, moved up from shot 3) |
| 0:08.0-0:12.0 | Hard cut back to the DENY freeze; cyan circle at 0:08.3, cyan arrow to the `person_in_frame 0.97` chips at 0:09.0 | `Here is why.` top-centre at 0:10 | `A person in the frame. The light went red. Here is why.` (0:08.3-0:11.6) |
| 0:12.0 | Dip to black 0.3 s, shot 3 begins; shot 3's VO becomes `I am Vivek Raja. I drive it as a Strands robot. A Strands agent on Amazon Bedrock turns my words into bounded hops. Before each hop, a local Strands Decider two B judges the command and the frame.` (38 words, 16 s at 150 wpm with pauses: fits) | | |

Why it is stronger: red DENY in the first second (the thumbnail frame is also sorted), the real
car is still on screen by 0:04 and labelled, the VO never pauses for more than 1 s, and shot 3's
overrun is solved by moving one sentence forward. The SIM label is on frame 0, which keeps the
honesty rule intact and even strengthens it (the first thing a judge reads is the label).

## Revised timing table

Moves: the alternative open; shot 5 rows at 2.5 s; shot 7 bars faster; shot 11 trimmed one line
of VO and one second of picture; shot 13 to 4 s. Picture still ends at 2:48.5 with the fade.

| # | Start-End | Dur | Change from the script |
|---|---|---|---|
| 1 | 0:00-0:04 | 4 s | DENY landing from the webm, title at 0:01 |
| 1b | 0:04-0:08 | 4 s | the car (GIF crop), `This is a stock AWS DeepRacer.` |
| 2 | 0:08-0:12 | 4 s | DENY freeze, pointers, `Here is why.` |
| 3 | 0:12-0:28 | 16 s | figure cropped to drop the baked title; VO loses one clause (moved to 1b) |
| 4 | 0:28-0:46 | 18 s | unchanged; VO starts 0:28.3 |
| 5 | 0:46-1:00 | 14 s | rows at 0:47, 0:49.5, 0:52, 0:54.5, 0:57; VO drops the title sentence |
| 6 | 1:00-1:10 | 10 s | chips instead of prose; footnote in at 1:06 |
| 7 | 1:10-1:21 | 11 s | bars 1.2 s each from 1:12.5, chip at 1:17; VO drops `One real answer.` |
| 8 | 1:21-1:49 | 28 s | unchanged |
| 9 | 1:49-1:53 | 4 s | GIF crop with blur-fill, strip on a plate |
| 10 | 1:53-2:03 | 10 s | caption on a plate top-centre or dropped; no `92 ms` highlight; VO drops `On the Pit Wall,` |
| 11 | 2:03-2:22 | 19 s | bar scale 280 px per 1.5 s; footnote from 2:12; VO drops the last sentence |
| 12 | 2:22-2:35 | 13 s | two-row layout |
| 13 | 2:35-2:39 | 4 s | 2 s per still |
| 14 | 2:39-2:48.5 | 9.5 s | fade starts 2:48.0; URL 48 px |

Fallback order if the Polly render still runs long after conforming: (1) cut the hall still (1 s
saved at 2:37); (2) cut shot 4's VO sentence `The Strands Agents loop holds the tools.` (the label
stack line 2 says it; 1.8 s); (3) cut shot 8's `A guessed distance moved nothing.` from the VO
only, keep the caption (1.6 s); (4) shorten shot 12 to two panels on screen at once by dropping
the file-tree panel's reveal delay (1 s). Never cut shot 11's numbers or shot 7's real answer;
they are the evidence.

## Legibility and fit, measured

Measured with PIL on `HelveticaNeue.ttc` (Bold, Medium, Medium Italic, Regular) and `Menlo.ttc`
against the 1728 px safe width.

| Element | Size | Width | Fits 1728 px |
|---|---|---|---|
| Shot 6 title `Probabilities in. Code decides. Rows checked in order.` | Bold 64 | 1674 px | yes, 54 px to spare; the longest title in the piece |
| Shot 3 title | Bold 64 | 1564 px | yes |
| Safety line | Bold 72 | 1507 px | yes, centred |
| Shot 11 footnote (108 characters) | Regular 26 | 1266 px | yes, one line |
| Shot 14 URL | Menlo 40 | 1080 px | yes; at 48 px 1296 px, still yes |
| Shot 12 footer path (72 characters) | Menlo 28 | 1224 px | yes |
| Shot 8 gate row (115 characters) | Menlo 26 | 1840 px | no, wraps to two lines in the 1152 px terminal; acceptable |
| Shot 12 panel 2 model line (79 characters) | Menlo 28 | 1343 px | no in a 576 px panel; see the shot 12 fix |
| Shot 8 label line 5 | Regular 30 | 660 px | no in a 576 px stack; see the shot 8 fix |
| Honesty label, longest | Menlo 24 | 616 px | yes; at 28 px 740 px, yes |

Helvetica Neue Bold at 64 px averages 31-33 px per character on these strings, so the rule of
thumb for future titles is 52 characters per line at 64 px and 48 at 72 px.

## Verdict

Ready to render after these fixes: no, not as written; yes once the two Critical items are
applied (re-time shot 2 to the webm's real 0.6 s DENY window with the freeze at webm 3.2 s, and
render Polly first then conform picture to VO with the listed word trims), plus the five layout
Highs that break the frame (GIF content crop with blur-fill and a plate under the title, shot 3's
baked-title crop, shot 11's bar scale, shot 12's two-row layout, shot 14's end time). The rest is
quality and can follow in round 2 on the draft render. The alternative open is recommended but
not required; if it is taken, shot 3's VO shortens for free and the first second of the video
shows the refusal the title promises.
