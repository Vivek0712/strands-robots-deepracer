# Demo video storyboard, v3

Companion to `SCRIPT.md` v3 (same shot numbers). v3 reworks shots 3, 4, 5, 6, 7, 8 and 11
for the author's note that the argument and probability passages ran through: those cards now
show one idea at a time, each reveal keyed to the voice-over clause that names it, with fewer
words per card and larger type (body 36 px, mono 30 px). Shots 1, 1b, 2, 9, 10, 12, 13 and 14
are unchanged from v2. One block per shot: an ASCII frame sketch,
where the asset sits, where the text and pointers sit, the transition in and out. The colour,
type and text-style spec comes first so every card is rendered the same way. Exact pixel
coordinates for every overlay and pointer are in the "Shot list for the renderer" section of
`SCRIPT.md`; this file explains the layout and the reasons.

Durations are "auto": the renderer sizes each shot's picture to its Polly audio (shot start to
last word plus 0.5 s), never below the minimum stated in `SCRIPT.md`. Every offset below is
relative to the shot's own start.

## Canvas and safe margins

- 1920x1080, 30 fps, 16:9. Export H.264, 12 Mbps or higher, AAC stereo 48 kHz, voice at
  -16 LUFS integrated. No music, no room tone: the renderer adds nothing to the audio track;
  the VO is written so no gap between spoken lines exceeds 2 s (the closing hold after the last
  word is the one planned silence).
- Background everywhere: `#0b0b10`. Dips between sections are to `#000000`.
- Title-safe margin: `SAFE_X = 96`, `SAFE_Y = 72` (the renderer's `docs/video/render/draw.py`
  values; v1 said 54, v2 adopts 72 so one number exists). Every word and pointer stays inside.
  Lower-third plates are 56 px tall with their bottom edge at y 1008; text baseline at y 992.
- In the sketches the outer box is the 1920x1080 frame and the dotted line is the title-safe
  margin. One character is 30 px wide and 60 px tall (64 characters by 18 rows).
- Source of truth for colours is the table below. `draw.py` currently carries `#4cc9f0`,
  `#ff7a1a`, `#f3f4f6`, `#8b8f98`; it should adopt these hexes (this file does not edit it).

## Colour

| Token | Hex | Used for |
|---|---|---|
| bg | `#0b0b10` | every background |
| ink | `#f2f2f7` | body text, titles |
| ink-dim | `#a0a0ad` | footnotes, source labels, dimmed figure regions |
| orange | `#ff6b3d` | the Decider and the Guardrails pattern, pointers and highlights on rendered cards |
| cyan | `#3ddcff` | structure: outline boxes, the Confirm chip, URL; pointers and highlights on portal frames |
| violet | `#7c5cff` | the Strands mark halo only |
| green | `#3fb950` | PROCEED chip, bars under the budget line |
| amber | `#ffb347` | GUIDE chip, the over-budget bar, the "unsure" number |
| red | `#ff4d4f` | DENY chip, the LED pulse, the DENY-word highlight, the deadman outline |
| plate | `#0b0b10` at 60 percent | behind any text that sits on footage or a photo |

Pointer rule: cyan on portal frames (shots 1, 2, 10), where red and orange already mean
something in the UI; orange on rendered cards (shots 4 to 9, 11, 12). Pointers are 4 px strokes
with a 12 px arrowhead, drawn in 0.25 s with an ease-out, and stay until the shot cuts.
Highlights are 3 px rounded rectangles (radius 8 px) with a 12 percent fill of the same colour.
The circle on shot 2 is 4 px.

Contrast on `#0b0b10` (measured): orange 6.9:1, cyan 12.0:1, ink-dim 7.6:1, red 6.0:1, amber
11.5:1, green 7.7:1. No orange text under 20 px.

## Type

- Sans: Helvetica Neue, `/System/Library/Fonts/HelveticaNeue.ttc` (index 0 Regular, 1 Bold;
  Medium and Medium Italic by index per `ASSETS.md` section 6). Inter is not installed.
- Mono: Menlo, `/System/Library/Fonts/Menlo.ttc` (index 0 Regular, 1 Bold). JetBrains Mono
  is not installed.
- Character widths used for the coordinates in `SCRIPT.md`: Menlo 28 = 16.85 px, Menlo 26 =
  15.65 px, Menlo 24 = 14.45 px per character; Helvetica Neue Bold 64 about 32 px per character
  (52 characters per 1728 px line), Bold 72 about 36 px (48 per line).

| Style | Font | Size | Colour | Where |
|---|---|---|---|---|
| Title | Helvetica Neue Bold | 64 px (56 px where noted), tracking -1 percent | ink | top-left at (96, 72), or as noted |
| Section lower-third (left) | Helvetica Neue Medium | 32 px | ink on a plate, 16 px padding, 2 px orange left bar | bottom-left, plate bottom at y 1008 |
| Honesty label (right) | Menlo | 28 px, all caps | ink-dim on a plate | bottom-right; two lines when longer than 740 px |
| Caption | Helvetica Neue Medium | 40 px (36 px on shot 10) | ink; on a plate when over footage | as noted per shot |
| Step label stack | Helvetica Neue Regular | 30 px on shot 4, 32 px on shot 8, 40 px leading | ink, the current line orange, earlier lines ink-dim | right column, each line on its own plate when over a figure |
| Callout label (shot 3) | Helvetica Neue Medium | 30 px | ink (orange for the Decider) on a plate | straddling the top edge of each baked callout box |
| Code | Menlo | 30 px on the explanatory cards (shots 5, 7, 8), 28 px on shot 12's code panel, 24 px on shot 12's terminal | ink; strings cyan, numbers amber, keys ink-dim | code panels and terminals |
| Verdict chip | Menlo Bold | 30 px, all caps, 10 px padding, radius 6 px | text `#0b0b10` on green, amber, cyan or red | shots 6, 7 |
| Card body (shots 5, 6, 7, 11) | Helvetica Neue Regular | 36 px (32 px for the one-line descriptions under a number) | ink; ink-dim for descriptions | the explanatory cards |
| Badge (Agent / Judge) | Menlo | 22 px, two lines | ink-dim on a plate | top-right under the safe margin, or as noted; hidden on fake-stack frames (shots 1, 2, 10) and on the car (1b, 13) |
| Counter | Helvetica Neue Bold | 96 px numerals, units 36 px | ink, unit ink-dim | shot 11, four numbers, one per VO clause |
| Quote card | Helvetica Neue Medium Italic | 44 px | ink on a plate with a 4 px orange left bar | shot 10 |
| Safety line | Helvetica Neue Bold | 72 px on shot 10, 56 px on shot 14, centred | ink | shots 10, 14; small 26 px ink-dim footer on shot 2 |
| URL | Menlo | 48 px | cyan | shot 14 |

## Transitions and motion

- Hard cut by default. Dip to black 0.3 s only into shot 3 and into shot 14; the dip is the
  first 0.3 s of the receiving shot and that shot's VO starts after it (+0.4 s).
- Figures with reveals (shots 3, 4): the figure starts dim (callouts hidden on shot 3, 25
  percent brightness on shot 4); each region comes to 100 percent over 0.4 s; already revealed
  regions settle at 70 percent.
- Reveal pace on the explanatory cards (shots 5, 6, 7, 8, 11): one idea at a time, revealed
  exactly when the voice reaches it; every reveal carries an `at` time in `SCRIPT.md` keyed to
  the VO clause (estimated at 176 wpm, re-keyed to Polly's sentence marks at render time).
  Elsewhere nothing new appears faster than 3 words per second plus 1 s of reading time; shot 3
  callouts every 1.25 s (3 to 4 word labels, the previous one stays).
- Cards build in place: rows and bands slide 24 px from the left over 0.3 s with a 2 px leading
  bar; nothing bounces. Counters count up over 1.0 s and stop on the exact value. Probability
  bars fill over 1.2 s.
- GIF handling (shot 1b): `docs/media/car-hop.gif` is a portrait phone clip pillarboxed inside
  its own 640x360 canvas; the content is x 217..422. Crop to that column, fit to 1080 tall
  (618x1080, 3x, lanczos), centre at x 651. Behind it a copy of the same crop scaled to cover
  1920x1080, gaussian blur 24 px, at 35 percent brightness. Convert 12 fps to 30 fps with frame
  blending (ffmpeg `minterpolate=mi_mode=blend`) so the car's motion does not stutter.
- Webm handling (shots 1, 2): `docs/results/portal/pitwall-sim.webm` is 1280x720; crop to the
  live view plus verdict panel, source x 0..910, y 40..720, scale 1.59x to 1447x1080, anchored
  at x 0. The audit column is dropped; the right 473 px of the frame are bg and carry the text.
  The DENY window is webm 2.9 to 3.5 s; the figure is in frame 2.7 to 3.5 s; the freeze frame
  is webm 3.2 s.
- Stills (shot 13): fitted to height with the same darkened blur fill as the GIF.

## Shots

### Shot 1, HOOK A (auto, min 4.0 s)

```
+----------------------------------------------------------------+
|PIT WALL  (webm crop, 1447 px wide)         [LED RED]<-pulse  . |
|. LIVE VIEW            | VERDICT                       |        |
|.  +----------------+  |                               | This   |
|.  |   ( o )        |  |   D E N Y                     | car    |
|.  |   /|\  figure  |  |   person in frame (p=0.97)    | can    |
|.  |   / \          |  |                               | refuse |
|.  | [class] [0.97] |  +-------------------------------+ an     |
|.  +----------------+  | THOUGHT  I stopped because... | order. |
|. COMMAND              | VOICE                         |        |
|.  [ STOP ALL ]        |  HOLD TO TALK                 | SIM,   |
|.                      |                               | FAKE   |
|. Physics stops the car; the decider explains. (baked) | DECIDER|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . DRAWN F.|
+----------------------------------------------------------------+
```

- Picture: black for 0.0 s; the webm crop plays from webm 2.5 s at native speed: a clear frame,
  PROCEED; at +0.2 the figure walks in; at +0.4 DENY lands and the `LED RED` label turns red;
  at +0.7 (webm 3.2 s) freeze and hold for the rest of the shot.
- Text, all in the right column (x 1500..1824, bg, no plate needed): the title in three lines,
  `This car` / `can refuse` / `an order.`, Bold 56 px, fading in at +1.0 over 0.3 s. The honesty
  label `SIM, FAKE DECIDER,` / `DRAWN FIGURE` in two lines at the column's bottom from frame 0.
- Pointers (cyan rule, red for the LED): a red pulse rectangle around the `LED RED` label at
  +0.4, two pulses of 0.3 s. Nothing else; let the DENY land.
- Badge: hidden (the judge on screen is the fake decider).
- In: from black at frame 0. Out: hard cut.

### Shot 1b, THE CAR (4.0 s fixed)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|. [A stock AWS DeepRacer]  (plate)                             .|
|.          [ darkened blur of the crop fills the frame ]       .|
|.                    +------------------+                      .|
|.                    |                  |                      .|
|.                    |  car-hop.gif     |                      .|
|.                    |  content column  |                      .|
|.                    |  618 x 1080      |                      .|
|.                    |  (the car drives |                      .|
|.                    |  away and back)  |                      .|
|.                    |                  |                      .|
|.                    +------------------+                      .|
|.                          [REAL CAR, PHASE-1 RECORDING, UNGATED]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Picture: the GIF crop as described under "GIF handling", all 4.0 s native, no hold needed.
- Text: caption `A stock AWS DeepRacer` on a plate top-left from +0.2; honesty label on a plate
  bottom-right from frame 0.
- Pointers: none. Badge: hidden.
- In: hard cut. Out: hard cut.

### Shot 2, HOOK B (auto, min 4.0 s)

```
+----------------------------------------------------------------+
|PIT WALL  (same freeze frame as shot 1)     [LED RED]         . |
|. LIVE VIEW            | VERDICT                       | Here   |
|.  +----------------+  |  +-----------+ red highlight  | is why.|
|.  |  .-( o )-.     |  |  | D E N Y   |                |        |
|.  | (  /|\  cyan)  |  |  +-----------+                |        |
|.  |  '-/ \-' circle|  |   person in frame (p=0.97)    |        |
|.  | [class]--[0.97]|  +-------------------------------+        |
|.  |   cyan boxes + arrow                              |        |
|.  +----------------+  | VOICE                         | Physics|
|. COMMAND              |  HOLD TO TALK                 | stops  |
|.  [ STOP ALL ]        |                               | the car|
|.                      |                               | SIM,   |
|. (baked footer)                                       | FAKE.. |
+----------------------------------------------------------------+
```

- Picture: the frozen webm frame (webm 3.2 s), same crop and position as shot 1, held.
- Text, right column: `Here is why.` Caption 40 px at the top of the column at +4.0 (when the
  VO reaches it); the safety footer `Physics stops the car.` / `The decider explains.` in
  26 px ink-dim above the honesty label from frame 0; the honesty label as in shot 1.
- Pointers (cyan; red only for DENY): circle around the stick figure at +0.3; highlight boxes
  on the two live-view chips (`FRAME CLASS person_in_frame`, `PROBABILITY 0.97`) and an arrow
  from the circle's lower-right edge to the probability chip at +1.0; red highlight on the
  DENY word at +2.5 (VO "The hop was refused").
- Badge: hidden.
- In: hard cut. Out: dip to black (the dip belongs to shot 3).

### Shot 3, WHAT IT IS (auto, min 9.5 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  Driven as a Strands robot                                   .|
|.                                                              .|
|.  [Decider on the camera]            [Harness on the compute] .|
|.  +-----------+                      +-----------+            .|
|.  +-----------+--.      ====CAR====  +-----------+            .|
|.  [strands-robots on the drive]      [Agents as the loop]     .|
|.  +-----------+---.    (render)      +-----------+            .|
|.  +-----------+     '--.             [Bidi as the voice]      .|
|.  [The deadman on the servos]        +-----------+            .|
|.  +-----------+                      [Box around the process] .|
|.  +-----------+                      +-----------+            .|
|.  Physics stops the car; the decider explains. (baked footer) .|
|.  | Vivek Raja, AWS AI Hero       [Agent: Nova Pro / Judge: 2B].|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Picture: `docs/article/img/fig-deepracer-strands.png` cropped to y 100..900 (drops the baked
  title and subtitle; the baked footer, the safety line, stays), scaled 0.9x to 1440x720 at
  (240, 190). The seven callout boxes, their leader lines and dots are hidden at the start and
  revealed one by one from the figure's HTML source layers. Order and times: Decider +0.5,
  strands-robots +1.75, deadman +3.0, Harness +4.25, Agents +5.5, Bidi +6.75, Box +8.0. At
  +9.5 all but the Decider settle at 70 percent. The VO says less in v3 (two sentences); the
  picture and the labels carry the stack.
- Text: title `Driven as a Strands robot` Bold 64 at (96, 72) from +0.4. One callout label per
  box, 30 px Medium on a plate straddling the box's top edge, appearing with its box. Lower-third
  left `Vivek Raja, AWS AI Hero`. Badge plate bottom-right at +3.0.
- Pointers: none drawn; the baked leader lines are the pointers.
- In: dip to black 0.3 s. Out: hard cut.

### Shot 4, ARCHITECTURE (auto, min 9.5 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  (1)+--------------------------+      1 Nova Pro proposes     .|
|.     | Amazon Bedrock  Nova Pro |        the move              .|
|.     +--------------------------+      2 Strands Agents runs   .|
|.  (2)+--------+(3)+-----------+          the tools             .|
|.     | Agents |   |DeciderGate|  --->  3 Decider 2B judges,    .|
|.     +--------+   | + 2B (or) | (5)+-+   before the tool runs  .|
|.  (4)+----------------------+  |car| 4 strands-robots carries  .|
|.     | strands-robots       |  |dead|   it over rosbridge      .|
|.     +----------------------+  |man | 5 On-car deadman: stops  .|
|.     (figure at 25 percent, regions light up)  without the laptop
|.                                   [Agent / Judge badge plate] .|
|.  | Architecture                                               .|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Picture: `docs/article/img/fig-architecture.png` scaled 0.8x to 1280x720 at (96, 200), at 25
  percent brightness. Regions light to 100 percent in three groups, 3 s apart: Bedrock and
  Strands Agents at +0.3; DeciderGate with the local Decider 2B at +3.3; strands-robots and the
  DeepRacer with its deadman node at +6.3. Earlier groups settle at 70 percent.
- Text: label stack top-right at x 1392, 30 px Regular, wrapping inside 432 px, added with each
  group, current line orange. Lower-third left `Architecture`. Badge plate under the stack.
- Pointers (orange): numbered badges 1 to 5 at each region's top-left corner as it lights; a
  cyan outline on each lit region, orange on region 3, red on the deadman sub-box; one orange
  arrow along the figure's own "commands 20 Hz" line from the laptop to the car with group 2.
- In: hard cut. Out: hard cut.

### Shot 5, THE DECISION, part 1: what is asked, and why (auto, min 20.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  Five typed questions, two requests                          .|
|.  noul = a yes/no question                           (+2.4)   .|
|.  answered as a probability, 0 to 1, not a sentence  (+4.8)   .|
|.  so code can compare it to a number                 (+6.1)   .|
|.  Request 1: the words                               (+9.2)   .|
|.  | inside_envelope   Is the proposed movement inside the      .|
|.  |                   envelope the operator briefed?  (+10.9) .|
|.  | args_grounded     Are the tool's argument values grounded  .|
|.  | (orange)          in what the user actually said? (+11.9) .|
|.  | intent  choice    What did the user most recently ask the  .|
|.  |                   robot to do?  move_forward turn stop ... .|
|.  Request 2: the frame, 480x360 JPEG                 (+15.7)  .|
|.  | person            Is a person visible in the frame? (+17.4)|
|.  | frame   choice    What is directly in front of the car ... .|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered card, one idea at a time. The three key lines (Regular 36) arrive with the clauses
  that explain what a noul question is and why its answer is a probability; then the `Request
  1` header and each row as the voice names it; then `Request 2` and its two rows. Nothing
  else on the card: no type chips (the `choice` tag sits under the two choice names in small
  mono), no endpoint line, no tag. Rows: name Menlo 30 at x 96, question Regular 36 at x 520
  (the longest fits one line at about 1190 px; the `args_grounded` question may wrap to a
  second line), option sets Menlo 26 ink-dim under the two choice rows.
- Keyed times (from the shot start, VO at +1.0): key lines +2.4, +4.8, +6.1; header 1 +9.2;
  rows +10.9, +11.9, +14.0; header 2 +15.7; rows +17.4, +18.4. Rows stay on screen once shown.
- Pointers: a 2 px leading bar on each row, orange for `args_grounded`.
- Badge plate bottom-right; lower-third left `The five questions`.
- In: hard cut. Out: hard cut.

### Shot 6, THE DECISION, part 2: how a probability becomes an action (auto, min 22.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  From a probability to an action                             .|
|.      1.0 |                                                   .|
|.          |##  0.65 or above: confident yes (+2.4)            .|
|.    green |##                     a person in frame   [DENY]  (+11.6)
|.       ---+--- 0.65                                           .|
|.     cyan |::  between: ask the operator (+9.2)               .|
|.          |::                     an invented distance [GUIDE] (+13.6)
|.       ---+--- 0.35                 re-plan                   .|
|.      red |##  0.35 or below: confident no (+5.8)             .|
|.          |##                     unsure, in the band [CONFIRM] (+15.7)
|.      0.0 |                         ask the operator          .|
|.                                  otherwise         [PROCEED] (+16.7)
|.                                  a late or missing decider [DENY] (+17.8)
|.  | Thresholds and actions        The gate never fails open. (+20.5)
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered card in two halves. Left: one large vertical probability ruler (700 px for 1.0).
  The YES tick, its green shade above and the line `0.65 or above: confident yes` arrive at
  +2.4; the NO tick, its red shade below and `0.35 or below: confident no` at +5.8; the cyan
  band between them and `between: ask the operator` at +9.2. Right: four example rows, Regular
  36 with a verdict chip at x 1560, one per clause: `a person in frame` DENY +11.6; `an
  invented distance` GUIDE with `re-plan` +13.6; `unsure, in the band` CONFIRM with `ask the
  operator` +15.7; `otherwise` PROCEED +16.7. Then `a late or missing decider` DENY at +17.8
  and `The gate never fails open.` at +20.5, with the small row 7 note (Confirm on the car,
  Guide in the library) under it.
- The 13-row table itself is not on screen any more; the four examples are the four actions,
  which is what the voice explains. The full table is in the article and SUBMISSION.md.
- Pointers: none beyond the ticks and shades.
- Badge plate top-right; lower-third left `Thresholds and actions`.
- In: hard cut. Out: hard cut.

### Shot 7, THE DECISION, part 3: one real request and answer, read slowly (auto, min 13.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  One real request, one real answer     [Agent / Judge badge] .|
|.  REQUEST (state)                  ANSWER         YES 0.65    .|
|.  "conversation": "user: Move                        :        .|
|.     forward [20 centimetres."] ]  (+0.3)            :        .|
|.  "command": {"tool": "move",     ] cyan  args_grounded ####:# 0.907 (+4.7)
|.    "arguments": {"heading_deg":  ] bracket          :        .|
|.       0, "distance_m": [0.2]}},  ]--orange arrow--> :        .|
|.  (+2.0)                           inside_envelope #####:## 0.948 (+6.8)
|.  "envelope": "distance_m <= 0.5 per call,            :        .|
|.     |heading_deg| <= 90",         intent move_forward ####:### 0.959 (+9.5)
|.  "deterministic_check": "ok"  (+6.8)                         .|
|.                                   [ PROCEED ] (+10.9)  583 ms (+11.6)
|.                       [RECORDED 2026-10-22, REAL DECIDER + NOVA PRO]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered split card, read in the order the voice reads it. Left: the conversation line
  arrives with "the user said twenty centimetres" and `20 centimetres.` is highlighted; the
  tool call arrives with "the tool call says zero point two" and `0.2` is highlighted, with a
  cyan bracket joining the two; the envelope and the arithmetic check arrive with "inside the
  envelope". Right: the bars arrive in the spoken order, grounded (0.907) first, then inside
  the envelope (0.948), then intent (0.959); the dotted YES rule at 0.65 turns each bar green
  as it crosses; the PROCEED chip and `583 ms` land on their words.
- Values from gate log row 1 of the recorded run, key order as in the log. Mono 30 px.
- Pointers: the two cyan highlights and the bracket; one orange arrow from the bracket to the
  grounded bar at +4.7.
- Honesty label bottom-right; badge plate top-right; no lower-third left.
- In: hard cut. Out: hard cut.

### Shot 8, THE RECORDED RUN, step by step (auto, min 22.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  USER : Go.                            (+1.0)    "Go." carries no distance
|.  {"arguments": {..., "distance_m": [2]},  (+3.0) Nova Pro guesses 2 m
|.   "deterministic_check": ["distance_m 2 > 0.5"], (+5.4) check fails: 2 > 0.5;
|.   "args_grounded": [0.18], "verdict": ["Guide"], (+6.8)   grounded 0.18
|.   "reason": "outside envelope: distance_m 2 > 0.5"} (+8.8) GUIDE: re-plan
|.  {"arguments": {..., "distance_m": [0.5]},  (+9.9) Nova Pro proposes 0.5 m
|.   "deterministic_check": "ok", "args_grounded": [0.404], (+12.3) grounded 0.40:
|.   "verdict": ["Confirm"],                          (+15.7)  the unsure band
|.   "reason": "unclear: inside=0.88 grounded=0.40"}          CONFIRM: the
|.  CONFIRM (operator asked): The decider is unsure about        operator is asked
|.    this move (inside envelope p=0.88, grounded p=0.40). Allow it?
|.  [OPERATOR: no (auto-answered by the test cell)]  (+17.7) scripted operator: no
|.  AGENT: The move could not be completed because the ... (+19.8)
|.                                                   A guessed distance moved nothing. (+20.5)
|.  | Recorded run, 2026-10-22: the real decider judges Nova Pro [RECORDED 2026-10-22, ...]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered terminal replay, Menlo 30 (975 px wide), 38 px leading, 17 lines, left column; no
  pre-shown header or first turn (shot 7 showed the first turn). Each line is typed when the
  voice reaches the clause that explains it, and its highlight lands 0.4 s later, so the judge
  reads one line per clause: `USER : Go.`; the 2 m call; the failed arithmetic check; grounded
  0.18; the Guide verdict and reason; the 0.5 m call; grounded 0.404; the Confirm verdict,
  reason and the operator question; `OPERATOR: no (auto-answered by the test cell)`; the
  agent's reply. Values are verbatim with keys omitted.
- Right column: one short step label per clause (Regular 32, current line orange) and the
  closing caption `A guessed distance moved nothing.` at +20.5; the badge plate under the
  labels.
- Highlights: orange on the two `distance_m` values and the failed check, amber on `0.18` and
  `"Guide"`, cyan on `0.404`, `"Confirm"` and the OPERATOR line. No arrows.
- Lower-third left `Recorded run, 2026-10-22: the real decider judges Nova Pro`; honesty label
  right.
- In: hard cut. Out: hard cut.

### Shot 9, MEASURED ON THE CAR (auto, min 6.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  Measured on the real car              [Agent / Judge badge] .|
|.                                                              .|
|.                                                              .|
|.      On the car: a person in frame was denied in 456 ms      .|
|.                                                              .|
|.                 person_in_frame   p = 0.9485                 .|
|.                                                              .|
|.    whole gate 681 to 727 ms per hop; no motion event after   .|
|.                          the deny                            .|
|.      Source: docs/results/beats-car-2026-10-15-person-gate   .|
|.                                                              .|
|.  | On the car, 2026-10-15   [MEASURED ON THE CAR 2026-10-15, REAL DECIDER]
|.                             [FRAMES WITHHELD: THEY SHOW A PERSON]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered card on bg, no footage: the frames of this run show the operator at the desk and
  stay out of the repo, which the label says. Replaces the v1 gate-blink shot over ungated
  footage.
- Lines, centred: 48 px Bold at +0.3; Menlo 40 at +4.0; 36 px Regular ink-dim at +6.5; 26 px
  ink-dim source line at +8.5. Honesty label (two lines) and lower-third from frame 0; badge
  plate top-right (the judge here is the real decider, so the badge is true).
- Pointers: none.
- In: hard cut. Out: hard cut.

### Shot 10, THE DENY IN THE SIMULATOR (auto, min 10.0 s)

```
+----------------------------------------------------------------+
|PIT WALL ... [Row 3: person in frame -> Deny] (plate)        . |
|.  +---------------------------+  SIM ARMED RED LED ...        .|
|.  | LIVE  stick figure        |  VERDICT                      .|
|.  |        ( o )              |  +--------+ red highlight     .|
|.  |        /|\  --cyan arrow--|->| DENY   |                   .|
|.  |        / \                |  +--------+                   .|
|.  | ["Someone is in front of me. I stopped."] quote card      .|
|.  | [class][0.97][Deny]       |  [CLASS person_in_frame][0.97] cyan box
|.  +---------------------------+  STOP  DENY 92 ms (not marked).|
|.  ROVER ... I stopped because the decider said: person in frame
|.         Physics stops the car. The decider explains. (+7.5)  .|
|.  | Pit Wall, the simulated car         [SIM, FAKE DECIDER, DRAWN FIGURE]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Picture: `docs/article/img/fig-portal-stage.png`, native 1920x1080, no push-in (so every
  coordinate stays fixed). At +7.5 the screenshot dims to 40 percent behind a plate band and
  the safety line.
- Text: caption `Row 3: person in frame -> Deny` 36 px on a plate at top-centre (the header's
  empty stretch, x 754..1250) at +0.3; quote card `"Someone is in front of me. I stopped."`
  (the narrator line from `portal/backend/narrator.py`) on the lower part of the live view at
  +5.0; safety line 72 px centred at +7.5; lower-third left `Pit Wall, the simulated car`;
  honesty label right. Badge hidden.
- Pointers (cyan; red for DENY): arrow from the figure's right arm to the CLASS chip and a
  cyan highlight around the CLASS and PROBABILITY chips at +1.0; red highlight on the DENY
  word at +2.5. The `92 ms` stop card is not marked: it is a fake-stack number.
- In: hard cut. Out: hard cut.

### Shot 11, THE NUMBERS (auto, min 10.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  Measured on the booth laptop: 72 timed calls        [badge] .|
|.  # Strands Decider 2B, local        # Amazon Nova Pro on Bedrock (+5.8)
|.                                                              .|
|.   462 ms                 (+1.3)                              .|
|.   median, three questions in one request                     .|
|.                                                              .|
|.   0 of 72                (+3.4)     31 of 72           (+7.1).|
|.   over the 1.5 s budget             over the 1.5 s budget    .|
|.                                                              .|
|.                                     0.13 USD           (+9.5).|
|.                                     per 1000 decisions       .|
|.  | The numbers                          [MEASURED 2026-10-22] .|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Rendered card, two 840 px columns, four numbers only, each counting up over 1.0 s when the
  voice reaches it: 462 ms (+1.3) and 0 of 72 (+3.4) for the local decider; 31 of 72 (+7.1) and
  0.13 USD (+9.5) for Nova Pro. One line of Regular 32 ink-dim under each number says what it
  is. No bars, no p95, no footnote; the full table with p95, provider-side latency and the
  marginal-cost qualifier is in `docs/results/decider-text-questions-2026-10-22.md` and the
  article.
- Lower-third left `The numbers`; honesty label `MEASURED 2026-10-22`; badge plate top-right.
- In: hard cut. Out: hard cut.

### Shot 12, THE REUSABLE PATTERN (auto, min 10.7 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.  Drop it into your own agent                        [badge]  .|
|.  three files, upstream names   three lines of wiring         .|
|.  patterns/strands/             decider = Decider([timeout=1.5])
|.    _client.py                  agent = Agent(                .|
|.    tool_call_intervention.py       model=BedrockModel(model_id="us.amazon.nova-pro-v1:0",
|.    frame_intervention.py                              region_name="us-east-1"),
|.    README.md                       tools=[move],             .|
|.                                    [interventions=[MotionGate(decider)]],
|.  make pattern-demo, against the fake decider (a script, not the model)
|.  {"tool": "move", ... "verdict": ["Proceed"], "reason": "[inside
|.    envelope p=0.95, grounded p=0.95]", "latency_ms": 1.5}    .|
|.  {"tool": "move", ... "verdict": ["Guide"],  "reason": "[outside envelope: distance_m 2 > 0.5]" ...
|.  {"tool": "move", ... "verdict": ["Deny"], "reason": "[decider unavailable: failing closed, no motion]" ...
|.  | github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands  [FAKE DECIDER, STDOUT VERBATIM]
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Two rows. Row 1 (y 160..560): the file tree in a 480 px panel at x 96 and the wiring snippet
  in a 1208 px panel at x 616, both Menlo 28, the `model=BedrockModel(...)` line wrapped by hand
  after the model id. Row 2 (y 600..912): the terminal, full width, Menlo 24, 32 px leading,
  the three JSON rows from `docs/video/build/clips/pattern-demo.txt` lines 7-9 verbatim,
  wrapped at 118 characters (10 lines). Rendering from the text file (the exact stdout) gives
  fixed coordinates; a screen capture of the same command may replace it if it is captured at
  1920x1080 with Menlo 24 and cropped to the same three rows.
- Times: row 1 at +0.3 (both panels), highlights `timeout=1.5` (cyan) at +1.5 and
  `interventions=[MotionGate(decider)]` (orange) at +2.5; the terminal types in from +4.5 over
  2 s; verdict highlights (green, amber, red) and the orange reason highlights at +7.0.
- Lower-third left carries the path in Menlo 26; honesty label right `FAKE DECIDER, STDOUT
  VERBATIM`; badge plate top-right.
- In: hard cut. Out: hard cut.

### Shot 13, MUMBAI (4.0 s fixed)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.                                                              .|
|.   [darkened blur]   +------------------+   [darkened blur]   .|
|.                     |                  |                     .|
|.                     | event-speaker-   |   then, at +2.0:    .|
|.                     | with-car.jpg     |   event-hall.jpg    .|
|.                     | 810 x 1080       |   1440 x 1080       .|
|.                     |                  |   centred           .|
|.                     |                  |                     .|
|.                     +------------------+                     .|
|.                                                              .|
|.  | AWS Community Day Mumbai, 17 October 2026                 .|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Two stills, 2.0 s each, hard cut between: `event-speaker-with-car.jpg` fitted to height
  (810x1080 at x 555) then `event-hall.jpg` fitted to height (1440x1080 at x 240), each over a
  darkened blur fill. The hall photo is the approved event photo, used as published by the
  organisers; if a second has to go later, cut the hall still, never the speaker still.
- Text: lower-third left only. Badge hidden.
- In: hard cut. Out: dip to black (belongs to shot 14).

### Shot 14, CLOSE (auto, min 8.0 s)

```
+----------------------------------------------------------------+
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
|.        [ cover.png at 40 percent brightness, full frame ]    .|
|.                                                              .|
|.         Physics stops the car. The decider explains.         .|
|.                                                              .|
|.          github.com/Vivek0712/strands-robots-deepracer       .|
|.                                                              .|
|.     Vivek Raja, AWS AI Hero  |  Article on AWS Builder Center .|
|.                                                              .|
|.              #strands-decider-2b   #guardrails               .|
|.                                                              .|
|.                                                  (Strands mark)
|.   (YouTube captions land at y 940-1040: nothing sits there)  .|
|. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . |
+----------------------------------------------------------------+
```

- Backdrop: `docs/article/img/cover.png` scaled to 1920x1080 at 40 percent brightness.
- Centre stack fading in over 1.0 s from +0.4: the safety line 56 px Bold; the URL Menlo 48 px
  cyan; the author line 30 px ink-dim; the two tags Menlo 32 px orange. The author line sits
  above the tags so a caption sidecar (YouTube draws captions at y 940..1040) never covers it.
  The Strands mark 96 px bottom-right with a soft violet halo.
- Hold; fade to black over the last 0.5 s of the shot. The audio is already silent.
- In: dip to black 0.3 s. Out: fade to black.

## Honesty labels, checklist for the editor

- Every frame from the fake stack carries `SIM, FAKE DECIDER, DRAWN FIGURE` (shots 1, 2, 10),
  and the Judge badge is hidden on those shots.
- Every frame of the car carries `REAL CAR, PHASE-1 RECORDING, UNGATED` (shot 1b). No shot
  animates a gate event over that footage.
- Every transcript or number carries its date and source: `RECORDED 2026-10-22, REAL DECIDER
  + NOVA PRO` (shots 7, 8), `MEASURED ON THE CAR 2026-10-15 ...` (shot 9), `MEASURED
  2026-10-22` (shot 11), `FAKE DECIDER, STDOUT VERBATIM` (shot 12).
- The fake decider's `0.97` appears on screen only inside the labelled portal frames and is
  never spoken as a judgement.
- The word "safety" never appears next to the decider; the safety line appears on shots 2
  (footer), 10 and 14 in the exact wording `Physics stops the car. The decider explains.`
- No third party is identifiable except in the approved AWS Community Day crowd photo (shot
  13), used as published by the organisers.
- Captions: build an SRT from Polly speech marks (one cue per sentence, 42 characters per line,
  two lines) and upload it as a sidecar, never burnt in; attach the read-through copy as the
  submission transcript.
