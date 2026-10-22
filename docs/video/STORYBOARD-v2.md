# Demo video storyboard, v2 (production design pass)

Companion to `DESIGN.md`, which fixes every token used here (grid, type, colour, curves,
durations, chrome). This file applies them shot by shot to the 17 entries of `shots.yaml`
(the 15 script shots; 1b and 13 are two entries each). Shot ids, order and durations are the
measured ones from `render check` on 2026-10-22 and do not move; neither does the VO text,
the measured sentence onsets, any number, any honesty label or the safety line. Everything
visual is new: layout, type, colour use, motion, transitions, depth, texture.

Coordinates are 1920x1080 frame units, x right, y down; `x0..x1, y0..y1` for boxes, `(x, y)`
for the top-left of a text box. Times are seconds from the shot's start; anchors `s<N>`,
`s<N>%<p>`, `s<N>+<d>` are resolved from the measured Polly sentence onsets listed per shot
(the resolved seconds are given in brackets so a reviewer can check the frame without the
resolver). Curves and durations are named per `DESIGN.md` section 7: enter 480, exit 240,
camera 720, draw 240 (underline) or 360 (leader) or 480 (focus frame), stagger 60.

Sketches: 64 columns by 18 rows including the border; one inner character is about 31 x 67
px. The top border is the rail; `. . .` marks the caption zone (y 940..1040), which holds
nothing essential on any shot.

## Revision 2 (after `reviews/v2-design-review.md`, 2026-10-22)

Applied, by review finding number; no id, duration or anchor changed.

1. (1, HIGH) Shot 4 re-keyed to the voice: the DeciderGate stop moves to s2%45; a fourth stop
   at s3 on the on-car deadman node with a red focus frame and step row 4; four badges on the
   pull-back, plus a cyan command trace (taste 4) ending at the deadman in red.
2. (2, HIGH) Shot 8: the step label is the only orange; terminal underlines take evidence and
   zone colours (cyan for the argument values, red for 0.18, cyan for 0.404 and Confirm, amber
   for Guide). DESIGN 3.1 updated.
3. (3, HIGH) Shot 5: the two option-set rows and the two `choice` sub-labels are cut; rows end
   at 748.
4. (4, HIGH) Shot 12: sidebar 96..520, tab strip 520..1824 (tab 520..800), gutter 544..580,
   code at x 600.
5. (5, MED) Shots 3, 9, 12: the title rides the incoming plate with the kicker (frame 0, no
   second entrance). DESIGN 7.2 updated.
6. (6, MED) Shot 6: each zone is two beats keyed to the words (tick and value at the onset,
   segment and label on "confident yes" / "confident no" / "operator"). (21) `0.35` and
   `0.65` placed. (23) Divider top retracts 200 to 340 with the scale travel.
7. (7, MED) Shot 6: the row-7 note moves under the left column at (120, 780) and (120, 814),
   240 ms after the gate line.
8. (8, MED) Shot 7: the three zones tint the bar tracks (red 1370..1496, cyan 1496..1604,
   green 1604..1730 at 10 percent); shot 8 values are coloured by zone. The scale is one
   character from 5 through 8.
9. (9, 10, MED) Number badges: disc ink, digit bg, inside the safe margin at the group box's
   top-left plus (24, 24); focus frames cyan, except the deadman node (red: physics). DESIGN
   11 updated.
10. (11, MED) Shot 7: `ANSWER`, `0.65` and the dotted line enter at s1%80+0.3 as a quiet
    setup; s2 is the label and the leader only.
11. (12, MED) Shot 9: the heading is a span reveal (`in 456 ms` at s1%78); the withheld
    frame's outline is on from frame 0, the hatch and `WITHHELD` fill it at s2.
12. (13, MED) Shot 12: verdict underlines in reading order with a 120 ms stagger; reason
    underlines dropped, the ink-dim to ink recolour kept.
13. (14, MED) Shot 8: a quiet ink underline on `"deterministic_check": "ok"` at s5%40.
14. (16, taste 3) Hook: hard open, spotlight with the freeze at 0.7, bloom period 330 ms, title
    box 560..664 with 120 px of air under DENY, title and rail alone at 1.06.
15. (17) Shot 1b-feed concept line corrected.
16. (18) Undefined sizes resolved: shot 9 `p = 0.9485` in Mono 28; shot 11 headers in
    Lower-third 32 Medium; `badge-docked` Mono-XS 20 added to the scale.
17. (19) Shot 8 nodes at y+20. (20) The shot 6 zone lift is dropped. (22) Shot 5 skeleton
    names recolour in place; only the bar and the question enter.
18. (24) Cards with a kicker and a title carry no lower-third: `The numbers` dropped on 11;
    shot 9 keeps `On the car, 2026-10-15`; shot 8 keeps its lower-third (no title).
19. (25) Shot 10: the honesty pill sits in the verdict card's empty stretch, right edge 1884,
    y 580..620. (26) Leftover coordinates removed.
20. (27) Shot 11: `31` right edge 1080, `of 72` at (1094, 572). Taste: `0 of 72` does not
    count; the 0 lands and the green tick draws on.
21. (28) Shot 12 terminal 588..920, rows from 640, nine full rows, the tenth faded under the
    panel edge. (29) Active tab edge in ink at 60 percent. (30) Code lines enter one by one,
    60 ms stagger.
22. (31, taste 5) Shot 14: URL 32 cyan, author line Body-XS 26, tags Mono-S 22, 24 px spacing;
    the safety line is the only headline; the rail stays full for 240 ms before the dip.
23. (32) The mark is `docs/video/build/clips/svg-strands-mark.png` downscaled into the 96 px
    box (or the SVG re-rendered at 192 px with the Chrome recipe). (33) Rail draw-on defined.
    (34) Multi-region spotlight defined as sequential single spotlights, marked new.
24. (35, taste 2) Shot 3: leaders draw from the dot outward to the label; only the Decider's
    dot pings; Harness and Box arrive settled at 70 percent.
25. (36) Accent bars: 2 px on content rows, 3 px on chrome; the quote card bar is 3 px.
26. Shot 8 terminal panel ends at 848 (header 200..232, lines from 256) so its shadow stays
    out of the bottom band. Shot 4 events at each stop spread with the 60 ms stagger.

Declined, with the reason: (15) the hall still stays at 2.0 s (the coordinator confirms it is
the author's own approved event photo); taste "middle dot in the kicker" (these files are plain
ASCII by the project's writing rule; the renderer may substitute U+00B7 for the kicker's
separator at draw time, the text stays `.`).

## Measured timeline (fixed)

| Entry | Start | Dur | Chapter | Transition in | Sentence onsets (from shot start) |
|---|---|---|---|---|---|
| s01-hook-a | 0.00 | 4.00 | 1 | hard open (no fade) | VO at 1.06 |
| s01b-feed | 4.00 | 1.60 | 1 | cut | VO at 0.56 (runs into s01b-car) |
| s01b-car | 5.60 | 2.40 | 1 | cut | none |
| s02-hook-b | 8.00 | 5.50 | 1 | cut | s1 0.35, s2 2.15, s3 4.01 |
| s03-what-it-is | 13.50 | 9.50 | 2 | push-left | s1 0.45, s2 2.34 (ends 7.09) |
| s04-architecture | 23.00 | 12.20 | 2 | cut | s1 0.37, s2 2.74, s3 6.75 |
| s05-questions | 35.20 | 18.60 | 3 | push-left | s1 1.07, s2 2.96, s3 8.63, s4 14.56 |
| s06-rows | 53.80 | 27.00 | 3 | cut | s1 0.37, s2 2.64, s3 6.47, s4 10.17, s5 12.65, s6 15.15, s7 18.67, s8 20.78, s9 22.91 |
| s07-one-request | 80.80 | 16.43 | 3 | cut | s1 0.36, s2 4.60, s3 7.43, s4 10.84, s5 13.02 |
| s08-recorded-run | 97.23 | 26.50 | 3 | cut | s1 0.36, s2 2.23, s3 6.15, s4 11.84, s5 14.36, s6 20.83, s7 23.11 |
| s09-on-the-car | 123.73 | 9.50 | 4 | push-left | s1 0.36, s2 6.44 |
| s10-sim-deny | 133.23 | 10.00 | 4 | cut | s1 0.36, s2 6.27, s3 8.14 |
| s11-numbers | 143.23 | 12.83 | 4 | cut | s1 0.36, s2 6.59 |
| s12-pattern | 156.07 | 9.20 | 5 | push-left | s1 0.36, s2 2.33 |
| s13a-mumbai-speaker | 165.27 | 2.00 | 5 | cut | VO at 0.38 |
| s13b-mumbai-hall | 167.27 | 2.00 | 5 | dissolve 12 f | none |
| s14-close | 169.27 | 8.00 | 5 | dissolve 12 f | s1 0.47, s2 2.52, s3 4.39; dip to black 7.28..8.00 |

Total 177.27 s (2:57.3). Transitions run inside the incoming shot (DESIGN section 8) so the
table is also the final timeline.

## Chrome present on every card (z-order 90 and above)

| z | Element | Where | Notes |
|---|---|---|---|
| 99 | grain | full frame | last, before encoding |
| 98 | vignette | full frame | before text, after images; listed here for the order of the two full-frame passes |
| 97 | rail | 0..1920, 0..3 | the full-width track draws on over 720 ms at shot 1 +1.06; the fill and head follow the global time from then on; leaves with the final dip |
| 96 | honesty pill(s) | right edge 1824, y 62..102 (and 110..150) | frame 0 of the shot; on the verdict card on shot 10 |
| 95 | kicker | (96, 72) | Menlo 22 caps orange; cards only |
| 94 | badge | right-aligned 1824, y 866 and 896 | shots 3 to 9, 11; in the tab strip on 12; hidden elsewhere |
| 93 | lower-third | bar 96..99 x 872..908, text (116, 878) | plate only over footage or a screenshot; not on cards that have a kicker and a title (shots 5, 6, 7, 11) |
| 92 | title | (96, 104) | Title 56; enters on its anchor on cut shots; on push shots (3, 9, 12) it is part of the incoming plate with the kicker |

Content layers run z 10 to 80 and are listed per shot. Transitions are z 100 (they composite
the outgoing plate over everything).

---

## Shot 1, s01-hook-a (0.00, 4.00 s): the Deny, then the title

Concept: the car refuses on screen before anyone has spoken, the LED goes red, and the title
lands on top of the frozen refusal with the weight of a verdict.

```
+--------------------------------------------------------------+
|                             [SIM, FAKE DECIDER, DRAWN FIGURE]|
|                                                              |
|       +------------------------------------------------+     |
|       | LIVE VIEW  (dim 40%)   | VERDICT   (*) LED RED  |    |
|       |      ( o )             |                        |    |
|       |      /|\               |   DENY   (lit)         |    |
|       |      / \               |   person in frame 0.97 |    |
|       |   This car can refuse an order.    (Display 96) |    |
|       |  [class]      [0.97]   | THOUGHT  I stopped ... |    |
|       |                        |                        |    |
|       |                        |                        |    |
|       +------------------------------------------------+     |
|                                                              |
|                                                              |
|  . . . . . . . . . caption zone, empty . . . . . . . . . .   |
|                                                              |
+--------------------------------------------------------------+
```

Layout: the Pit Wall is a screen, so it lives in a panel (DESIGN section 4): `232..1688,
160..824` (1456 x 664, centred on x 960, radius 12, border, shadow). Inside it the webm crop
source `0..910, 40..455` (live view plus the verdict and thought panels; the command, voice and
audit areas are dropped) at 1.60x. Nothing else on the canvas but chrome.

Three beats: the verdict at 0.4, the freeze and the spotlight at 0.7, the title and the rail at
1.06. After 1.06 nothing moves but the 3 percent push until the cut.

Layers (z):
- 10 bg + vignette. Hard open on frame 0 (no fade from black): the PROCEED-to-DENY flip is
  the story and a fade would eat half of it.
- 20 panel with the clip `docs/results/portal/pitwall-sim.webm`, in 2.5 s, out 3.2 s, then the
  3.2 s frame held. Timeline: +0.0 clear frame, PROCEED; +0.2 the figure walks in; +0.4 DENY
  lands and the LED label turns red; +0.7 freeze.
- 30 LED bloom: red, centred on the LED dot at (1556, 188), radius 24, alpha 0.60 to 0.15, two
  pulses with a 330 ms period from +0.4, so the second pulse's fall hands off to the title at
  1.06. The only bloom on the shot.
- 40 spotlight mask over the panel from +0.7 with the freeze (480 ms): regions kept at 100
  percent are the DENY word `1040..1370, 280..440` and the LED label `1540..1680, 164..212`;
  the rest of the panel dims to 40 percent. The frame has resolved to DENY and the LED before
  the voice starts.
- 50 title `This car can refuse an order.`, Display 96 Bold ink, one line (1262 px), centred
  on x 960, text box `329..1591, 560..664`: over the dimmed floor, 120 px of air under the
  DENY region and clear of the chips at 709. Entrance at +1.06 (the first word): fade plus 16
  px rise, 480 ms, enter curve. Nothing else enters on that frame but the rail.
- 97 rail: the full-width track draws on from x 0 over 720 ms from +1.06 (draw curve); the
  fill and the orange head follow the global time from then on.
- 96 honesty pill `SIM, FAKE DECIDER, DRAWN FIGURE` top-right, frame 0 (one pill; it fits).

Camera: after the freeze, a push-in 1.00 to 1.03 on the panel content from +0.7 to +4.0,
drift curve, centred on the DENY word (1205, 360), so the verdict grows slightly above the
title.

Pointers: none beyond the bloom and the spotlight. No box, no arrow.

Honesty label: `SIM, FAKE DECIDER, DRAWN FIGURE`. Badge hidden.

Exits: none inside the shot; the title and the dim hold to the cut.

Transition out: hard cut to 1b-feed at 4.00 (the panel geometry persists, the picture changes).

The viewer understands: a car's command was refused by a judgement, a light went red, and
this film is about that refusal. They also know, from the pill, that this frame is a simulation.

## Shot 1b-feed, s01b-feed (4.00, 1.60 s): the car's own camera

Concept: the first real picture: what the car saw under the earlier planner, in a panel where
the sim's panel was, so "stock DeepRacer" lands on a real feed.

```
+--------------------------------------------------------------+
|               [REAL CAR, PHASE-3 VISION PLANNER, PRE-DECIDER]|
|                  +-------------------------+                 |
|                  |  blocky camera feed     |                 |
|   (blur fill     |  tile floor, toy car    |   (blur fill    |
|    of the feed,  |  two tiles ahead        |    of the feed) |
|    25 percent)   |                         |                 |
|                  |                         |                 |
|                  |                         |                 |
|                  |-------------------------|                 |
|                  | REPLAN  Car in front... |                 |
|                  | [Replan #1: turn left ] |                 |
|                  | CONTINUE  ...           |                 |
|                  +-------------------------+                 |
| | A stock AWS DeepRacer  (lower-third on a plate)            |
|  . . . . . . . . . caption zone, empty . . . . . . . . . .   |
|                                                              |
+--------------------------------------------------------------+
```

Layout: the clip `docs/video/build/clips/phase3-replan-1080p.mp4` 2.8 s to 4.4 s, crop
`391..1524, 27..1060` (the feed image and its log plate), scaled 0.70 to 793 x 723, in a panel
at `564..1357, 120..843`. Behind it, full-bleed, the same crop scaled to cover, gaussian blur
32, 25 percent brightness. The feed is 8x nearest-neighbour from a 141 px source; it is not
sharpened (ASSETS section 8). The recording is a screen, so it is in a panel; the next entry
is footage, so it goes full-bleed.

Layers (z): 10 bg; 15 blur fill (drifts 4 px right over the entry, drift curve); 20 panel
with the crop; 93 lower-third `A stock AWS DeepRacer` on a plate `80..568, 860..920`, bar then
text, entering at +0.56 (the first word) with fade plus 16 px from the left; 96 pill `REAL CAR,
PHASE-3 VISION PLANNER, PRE-DECIDER` top-right, frame 0; 97 rail.

Camera: none on the clip (it is 1.6 s and already moving in its own log).

Pointers: none.

Honesty label: `REAL CAR, PHASE-3 VISION PLANNER, PRE-DECIDER`. Badge hidden.

Transition out: hard cut to 1b-car at 1.60; the lower-third and the pill persist without
re-entering.

The viewer understands: this is a real car with a real camera, and the earlier planner (not
the decider) is what they are seeing.

## Shot 1b-car, s01b-car (5.60, 2.40 s): the real car turns

Concept: the one clip where the real car visibly steers, full-bleed, nothing drawn on it.

```
+--------------------------------------------------------------+
|                 [REAL CAR, PHASE-3 VISION PLANNER, PRE-DECIDE|
|                      |                  |                    |
|   (darkened blur     |   portrait phone |    (darkened blur  |
|    of the column)    |   footage, tile  |     of the column) |
|                      |   floor          |                    |
|                      |                  |                    |
|                      |     [toy car]    |                    |
|                      |                  |                    |
|                      |    DeepRacer     |                    |
|                      |    turning left  |                    |
|                      |                  |                    |
|                      |                  |                    |
|                      |                  |                    |
| | A stock AWS DeepRacer  (persists)                          |
|  . . . . . . . . . caption zone . . . . . . . . . . . . .    |
|                      |                  |                    |
+--------------------------------------------------------------+
```

Layout: `docs/video/build/clips/phase3-thirdperson-1080p.mp4` 4.6 s to 7.0 s, placed
`0..1920, 0..1080` as cut (the phone column fitted to 1080 over its own darkened blur). Real
footage: full-bleed, no panel.

Layers (z): 20 clip; 93 lower-third (held from 1b-feed, same plate); 96 pill (held); 97 rail.

Camera: none; the hand-held footage carries its own motion.

Pointers: none. Nothing is ever drawn over the real car.

Honesty label: held. Badge hidden.

Transition out: hard cut to shot 2 at 2.40.

The viewer understands: the car moves on its own, on a real floor, and the frame has told
them it is pre-decider.

## Shot 2, s02-hook-b (8.00, 5.50 s): here is why

Concept: back to the frozen refusal, now explained in three cues, each named by the voice:
the person, the two chips, the DENY, then the promise "Here is why."

```
+--------------------------------------------------------------+
|      Here is why. (s3)      [SIM, FAKE DECIDER, DRAWN FIGURE]|
|                                                              |
|       +------------------------------------------------+     |
|       | LIVE VIEW              | VERDICT   (*) LED RED  |    |
|       |      ( o )  spotlight  |  +------+              |    |
|       |      /|\   on figure   |  | DENY | red focus    |    |
|       |      / \     (s1)      |  +------+   (s2)       |    |
|       |                        |   person in frame 0.97 |    |
|       |  [class]      [0.97]   | THOUGHT  I stopped ... |    |
|       |   cyan focus (s1%60)   |                        |    |
|       |                        |                        |    |
|       +------------------------------------------------+     |
|              Physics stops the car. The decider explains.    |
|                                                              |
|  . . . . . . . . . caption zone, empty . . . . . . . . . .   |
|                                                              |
+--------------------------------------------------------------+
```

Layout: the same panel `232..1688, 160..824` with the webm 3.2 s freeze frame, same crop and
scale, undimmed, no push (every coordinate below is fixed). The title from shot 1 is gone.

Layers (z):
- 20 panel with the still (`docs/results/portal/pitwall-sim.webm` at 3.2 s).
- 40 spotlight: at s1 (0.35) `A person in the frame.` the figure region, an ellipse centred
  (640, 533) radii 200 x 260 with a 48 px feather, stays at 100 percent and the rest of the
  panel dims to 40 percent over 480 ms. At s1%60 (1.0) the mask widens to add the two chips;
  at s2 (2.15) it adds the DENY word. The mask lifts to 70 percent (not 100) at s3 so the
  frame calms while the line lands.
- 45 focus frames, cyan, 2 px, radius 8, drawing on clockwise over 480 ms: FRAME CLASS chip
  `272..544, 709..789` and PROBABILITY chip `851..1006, 709..789`, both at s1%60 (1.0), the
  second 60 ms after the first.
- 46 focus frame, red, on the DENY word `1062..1346, 296..424` at s2 (2.15) `The hop was
  refused.`; a red glow is not used here (the frame is enough; the LED is already red).
- 50 `Here is why.` Title-S 48 Bold ink at (232, 92) (aligned to the panel's left edge, text
  box 92..148), entrance at s3 (4.01), fade plus 16 px rise.
- 55 safety footer `Physics stops the car. The decider explains.` Body-S 28 ink-dim,
  right-aligned to x 1688 at y 852 (box 852..888), present from frame 0 (chrome of this shot).
- 96 pill as shot 1; 97 rail.

Camera: none.

Pointers: the spotlight and the three focus frames. No circle, no arrow, no chip highlight
fill.

Honesty label: `SIM, FAKE DECIDER, DRAWN FIGURE`. Badge hidden.

Exits: none; everything holds to the push.

Transition out: push-left into shot 3 (chapter change), 720 ms camera curve, running inside
shot 3's first 0.72 s with this shot's final frame as the outgoing plate.

The viewer understands: the refusal has a cause (a person), evidence (a class and a
probability) and a verdict (DENY), and the film will now explain the machinery.

## Shot 3, s03-what-it-is (13.50, 9.50 s): driven as a Strands robot

Concept: the stock car as a hero object, with seven Strands roles landing on its body as
leaders with dots, in the order the voice names them; the Decider is the one in orange.

```
+--------------------------------------------------------------+
| THE SYSTEM . 1 OF 2                                          |
| Driven as a Strands robot                                    |
|                                                              |
|        Decider on the camera ----o          o---- Harness    |
|                                   \__                        |
|                                      (  car  )  o-- Agents   |
|                                     ( render ) o--- Bidi     |
|      strands-robots on the drive --o(        )               |
|                                      (______)                |
|       The deadman on the servos ---------o   o-- Box around  |
|                                                  the process |
|                                                              |
|                                                              |
| | Vivek Raja, AWS AI Hero          Agent: Amazon Nova Pro .. |
|                                    Judge: Strands Decider .. |
|  . . . . . . . . . caption zone, empty . . . . . . . . . .   |
+--------------------------------------------------------------+
```

Layout: `docs/video/build/clips/layers/base.png` (the figure's HTML rendered with the
callouts hidden: car, glow, dark background) crop source `200..1600, 60..860`, scale 1.0,
placed `260..1660, 120..920`. The car's body spans about `704..1293, 149..615`. The seven
callouts are not the baked layers any more; they are drawn (DESIGN section 11: leader with a
dot) with the v2 labels, so they obey the type scale and the accent rule.

Anchor dots (frame coordinates at the shot's start, converted from the v1 render): Decider
(966, 297); strands-robots (762, 529); deadman (1046, 563); Harness (1069, 236); Agents
(1108, 361); Bidi (1244, 393); Box (964, 639). They live in the figure layer and move with the
push-in; the leaders are re-anchored every frame.

Labels, Label-L 36 Medium: left column right-aligned to x 640 (leader ends at x 656); right
column left-aligned at x 1360 (leader ends at x 1344). The car points out its parts: the dot
fills first, then the leader draws from the dot outward to the label's edge, then the label
enters. Text and leader:

| Callout | Label text | Text box | Leader (from the dot to) | Anchor (resolved) |
|---|---|---|---|---|
| Agents | `Agents as the loop` | (1360, 330) | (1344, 352) | s2 (2.34) |
| Bidi | `Bidi as the voice` | (1360, 440) | (1344, 462) | s2%25 (3.53) |
| strands-robots | `strands-robots on the drive` | right edge 640, y 500 | (656, 522) | s2%40 (4.24) |
| Decider, orange | `Decider on the camera` | right edge 640, y 270 | (656, 292), orange | s2%50 (4.72) |
| deadman | `The deadman on the servos` | right edge 640, y 620 | (656, 642) | s2%85 (6.38) |
| Harness | `Harness on the compute` | (1360, 220) | (1344, 242) | +7.40, settled |
| Box | `Box around the process` | (1360, 640) | (1344, 662) | +7.46, settled (stagger) |

Named callouts (the first five): the dot fills (240 ms), the leader draws outward over 360 ms
(draw curve), the label enters at the leader's end (fade plus 16 px from the car side, 480
ms). Only the Decider's dot pings (the ring r 5 to 14, 480 ms): one accent, one ping. Harness
and Box are not named by the voice, so they arrive already settled: label at 70 percent,
leader without a ping, 480 ms, as one staggered pair. At +8.5 the other four non-Decider
callouts settle to 70 percent over 240 ms; the Decider stays orange at 100.

Layers (z): 10 bg; 20 figure (push-in 1.00 to 1.04 over the whole shot, drift curve, centred
on (998, 400); the glow beneath the car is part of the same layer); 30 leaders and dots; 40
labels; 92 title `Driven as a Strands robot`, part of the incoming plate with the kicker (frame
0, no second entrance: the push is its entrance); 93 lower-third `Vivek Raja, AWS AI Hero` at
s1+0.24 (0.69); 94 badge on a plate (the figure's dark glow is under it) at s2; 95 kicker `THE
SYSTEM  .  1 OF 2` on the plate; 97 rail.

Camera: push-in as above. Parallax: the figure's glow is the same PNG, so the parallax here is
the push alone; the labels do not move, which reads as depth against the moving car.

Pointers: the leaders and dots. No label plates (the labels sit on bg, not on the car).

Honesty label: none (the figure is a render of a stock car, not footage or a measurement; v1
carried none here either). Badge shown.

Transition in: push-left from shot 2 (0.00 to 0.72). Transition out: hard cut to shot 4.

The viewer understands: six Strands pieces are on this one car and the Decider is the one
that judges the camera; the author's name is on the frame.

## Shot 4, s04-architecture (23.00, 12.20 s): the guided zoom

Concept: the architecture figure explored by a camera that goes where the voice goes (Bedrock,
the Strands layers, the DeciderGate, then the on-car deadman), with a focus frame on each
group, a four-line step panel that fills as the clauses land, and a pull-back where the
command's path draws itself across the whole figure.

```
+--------------------------------------------------------------+
| THE SYSTEM . 2 OF 2                                          |
|  +-----------------------------------------------+           |
|  | zoomed figure region (vector, 3840 wide)      |  figure   |
|  |   +---------------------------+ cyan focus    |  outside  |
|  |   | Strands Agents            | frame (s2)    |  the      |
|  |   +---------------------------+               |  frame    |
|  |   +-------------------------------------+     |  dims to  |
|  |   | strands-robots  every command ...   |     |  40 pct   |
|  |   +-------------------------------------+     |           |
|  +-----------------------------------------------+           |
|                                  +--------------------------+|
|                                  | 1 Nova Pro proposes ...  ||
|                                  | 2 Strands Agents runs .. ||
| | Architecture                   | 3 Decider 2B judges, ... ||
|                                  | 4 On-car deadman: stops  ||
|  . . . . . . caption zone . . .  +--------------------------+|
+--------------------------------------------------------------+
```

Layout: the still `docs/video/build/clips/figs/fig-architecture-3840.png`. Views are [cx,
cy, scale] of the figure (1.0 = the whole figure fitted to the frame); a view's visible region
is cx plus or minus 0.5/scale horizontally and cy plus or minus 0.5/scale vertically, and a
figure point (nx, ny) lands at frame x = (nx - cx + 0.5/scale) * scale * 1920, y = (ny - cy +
0.5/scale) * scale * 1080. Group bounds below are normalised figure coordinates taken from
the SVG groups (the v1 region measurements on the 1600x900 PNG, divided by 1600 and 900):
Amazon Bedrock 0.025..0.390 x 0.033..0.170; Strands Agents 0.044..0.219 x 0.303..0.430;
strands-robots 0.044..0.487 x 0.464..0.713; DeciderGate plus Decider 2B 0.238..0.494 x
0.303..0.430; the deadman node inside the DeepRacer box 0.688..0.963 x 0.489..0.661. The
engineer confirms each by rendering one frame per stop before keying; the stop-2 and stop-3
frame boxes below are the v1 measured ones and agree with the formula to within 4 px.

| At | View [cx, cy, scale] | Move | Shows (the words) |
|---|---|---|---|
| 0.00 | [0.5, 0.5, 1.0] | hold | the whole figure |
| 0.80 | [0.269, 0.25, 2.0] | 720 ms camera curve | Amazon Bedrock: Nova Pro ("Nova Pro proposes the move") |
| s2 (2.74) | [0.272, 0.53, 1.8] | 720 ms | Strands Agents and the strands-robots layer ("A Strands intervention handler") |
| s2%45 (4.54) | [0.366, 0.367, 3.0] | 720 ms | DeciderGate and Decider 2B ("asks the decider before the tool runs") |
| s3 (6.75) | [0.790, 0.620, 2.4] | 720 ms | the DeepRacer box with the deadman node ("The on-car deadman needs none of it"); cx 0.790 puts the figure's right edge on the frame edge |
| 10.90 | [0.5, 0.5, 1.0] | 720 ms | the whole figure again, the trace and four badges |

Layers (z):
- 20 figure under the camera.
- 40 spotlight: outside the current focus frame the figure dims to 40 percent; lifts for the
  two full views. Each stop's spotlight is a single region; the previous one lifts over the
  same 480 ms as the next one lands.
- 45 focus frames (2 px, radius 8, draw on clockwise 480 ms), in frame coordinates at each
  stop. Stop 1, cyan: Amazon Bedrock `24..1424, 72..368`, at +1.40. Stop 2, cyan: Strands
  Agents `173..778, 99..345` at s2+0.6 (3.34) and strands-robots `173..1706, 380..827` at
  s2+0.66 (stagger). Stop 3, cyan: DeciderGate plus Decider 2B `223..1699, 335..745` at
  s2%45+0.6 (5.14). Stop 4, red (the physical layer): the deadman node `488..1756, 200..646`
  at s3+0.6 (7.35). Each frame exits (240 ms) when the next move begins.
- 46 number badges (disc r 18 ink, digit in bg colour, HN Medium 22), at the group box's
  top-left plus (24, 24), never outside the safe margin: `1` at (96, 96) at +1.46; `2` at (197,
  123) at s2+0.72; `3` at (247, 359) at s2%45+0.66; `4` at (512, 224) at s3+0.66; each enters 60
  ms after its focus frame and exits with its stop. On the pull-back at 11.40, with a 60 ms
  stagger: `1` at (120, 96), `2` at (120, 352), `3` at (480, 352), `4` at (1344, 552).
- 47 command trace on the pull-back (taste 4): a 2 px cyan leader without an arrowhead, drawn
  on over 720 ms (draw curve) from 11.40 along the command's path in the full view: (398, 184)
  Bedrock's bottom centre, to (253, 327) Strands Agents' top centre, to (421, 396) its right
  edge, to (457, 396) the DeciderGate's left edge, to (948, 396) its right edge, to (1320, 396)
  the DeepRacer box's left edge, to (1320, 621) the deadman node's left edge centre; the last
  60 px of the trace are red and end in a red dot r 5 at (1320, 621). The trace and the badges
  are the only things that move after the pull-back.
- 60 step panel, surface at 92 percent, radius 12, border, right column: grows upward as rows
  arrive: one row `1272..1824, 780..848`, two `740..848`, three `700..848`, four `660..848`
  (move curve, 240 ms). Rows Body-XS 26 at x 1296, y panel top + 24, pitch 40: `1 Nova Pro
  proposes the move` at +1.40 (orange); `2 Strands Agents runs the tools` at s2+0.6 (orange;
  row 1 to ink-dim); `3 Decider 2B judges, before the tool runs` at s2%45+0.6 (orange; row 2
  to ink-dim); `4 On-car deadman: stops without the laptop` at s3+0.6 (orange; row 3 to
  ink-dim). Row 4 stays orange through the pull-back: the step row is the only orange content
  on the shot (the kicker is chrome).
- 93 lower-third `Architecture` on a plate (alpha 0.72) whenever the figure is under it (every
  stop); no plate on the full views if the bottom-left is bg.
- 94 badge bottom-right on a plate (under the step panel's bottom edge at 848; badge y 866 and
  896).
- 95 kicker `THE SYSTEM  .  2 OF 2`; no title (the figure fills the title band at the stops).
- 97 rail.

Camera: the six keyframes above, every move 720 ms on the camera curve; the figure is a
vector render so the 3.0x stop stays sharp. No dead stretch over 3 s: the stops land at 0.80,
2.74, 4.54, 6.75 and 10.90, each with its focus frame, badge and row spread by 60 ms.

Pointers: focus frames, number badges and the trace. The v1 outline boxes are replaced by the
focus frames; the v1 "commands 20 Hz" arrow is gone; the trace is a leader without a head.

Honesty label: none (a drawn figure of the build; v1 carried none). Badge shown.

Transition in: hard cut from shot 3. Transition out: push-left into shot 5 (chapter change).

The viewer understands: the agent proposes, a Strands intervention asks the local decider
before the tool runs, and the on-car deadman is a separate physical layer.

## Shot 5, s05-questions (35.20, 18.60 s): what is asked, and what comes back

Concept: the decision layout opens: the five questions on the left, what an answer looks like
on the right, and the probability scale is met for the first time.

```
+--------------------------------------------------------------+
| THE DECISION . 1 OF 4        [Agent/Judge]  (no pill: a card)|
| Five typed questions, two requests                           |
| Request 1: the words              | What comes back          |
| |inside_envelope  Is the proposed | noul = a yes/no question |
| |                 movement ...    | answered as a probability|
| |args_grounded    Are the tool's  |   0 to 1, not a sentence |
| |(orange)         argument ...    | so code can compare it   |
| |intent           What did the    |   to a number            |
| |                 user most ...   |                          |
| Request 2: the frame, 480x360 JPEG| 0.0                  1.0 |
| |person           Is a person ... | =========================|
| |                 in front ...    |                          |
| |frame            What is directly|                          |
|                                   |                          |
|                                   |       Agent: Amazon Nova |
|  . . . . . . . . . caption zone . . . . Judge: Strands . . . |
+--------------------------------------------------------------+
```

Layout: the decision split (DESIGN section 1): left `96..1094`, right `1118..1824`, divider at
x 1106 from y 200 to 848 (1 px, ink 12 percent). The split, the divider, the kicker slot and
the bottom band hold through shots 5, 6, 7 and 8.

Left column (asked):
- Skeleton at s1 (1.07) `Five typed questions.`: the five question names, Mono 26 ink-mute,
  at their final positions, entering top to bottom with a 60 ms stagger (fade plus 16 px from
  the left). They are a count of five. On its row's anchor a name recolours ink-mute to ink
  (orange for `args_grounded`) in place over 240 ms; it does not enter a second time.
- `Request 1: the words` Caption 22 Medium ink-dim at (96, 200), s3 (8.63).
- Row 1 at s3%28 (9.80): accent bar 2 px cyan `96..98, 244..316` (draws top to bottom 240
  ms); name `inside_envelope` at (120, 248) recolours; question `Is the proposed movement
  inside the envelope the operator briefed?` Body-S 28 ink at (420, 244), wraps inside 674 px
  to two lines (244..316).
- Row 2 at s3%44 (10.47): bar orange `96..98, 344..416`; `args_grounded` at (120, 348)
  recolours to orange; `Are the tool's argument values grounded in what the user actually
  said?` at (420, 344), two lines. This row stays orange: it is the Guardrails question.
- Row 3 at s3%78 (11.90): bar cyan `96..98, 444..516`; `intent` at (120, 448); `What did the
  user most recently ask the robot to do?` at (420, 444), two lines. No option set and no
  `choice` sub-label: the voice never says them, and the set did not fit the column.
- `Request 2: the frame, 480x360 JPEG` Caption 22 at (96, 556), s4 (14.56).
- Row 4 at s4%42 (16.03): bar cyan `96..98, 600..636`; `person` at (120, 604); `Is a person
  visible in the frame?` at (420, 600), one line.
- Row 5 at s4%67 (16.91): bar cyan `96..98, 668..740`; `frame` at (120, 672); `What is
  directly in front of the car in this camera frame?` at (420, 668), two lines. No option set.
  Rows end at 748.
- Row entrance: the bar draws first (240 ms), the name recolours and the question enters at
  +60 ms (fade plus 16 px from the left, 480 ms).

Right column (what comes back):
- `What comes back` Caption 22 ink-dim at (1118, 200), s2 (2.96).
- `noul = a yes/no question` Body 32 ink at (1118, 244), s2.
- `answered as a probability, 0 to 1, not a sentence` Body 32 at (1118, 316), wraps to two
  lines inside 706 px (316..400), s2%37 (4.77).
- `so code can compare it to a number` Body 32 at (1118, 424), s2%58 (5.80).
- The probability scale: `0.0` Mono-S 22 ink-dim at (1118, 504), `1.0` right-aligned to 1824
  at y 504, rule 4 px ink-mute `1118..1824, 538..542` drawing on left to right over 720 ms
  (draw curve) from s2%58+0.3 (6.10). No marker: no value is being shown.

Layers (z): 10 bg; 30 divider; 40 skeleton names; 50 rows and headers; 60 right column text;
65 scale; 92 title `Five typed questions, two requests` at s1 (1.07) (this push shot's title
waits for its sentence because s1 is 0.35 s after the push ends); 94 badge (no plate); 95
kicker `THE DECISION  .  1 OF 4` with the push; 97 rail. No pill: the card quotes the
questions from the repo, nothing is recorded or measured here (as v1). No lower-third: the
kicker and the title name the card.

Camera: none. Cards do not move.

Pointers: the accent bars only.

Honesty label: none. Badge shown.

Transition in: push-left from shot 4 (0.00 to 0.72); the kicker and divider arrive with it;
the title waits for s1. Transition out: hard cut to shot 6; the chrome, the divider and the
scale persist (the scale then travels, see shot 6).

The viewer understands: five typed questions, three about the words and two about the frame;
every answer is a probability between 0 and 1, which is why code can act on it.

## Shot 6, s06-rows (53.80, 27.00 s): from a probability to an action

Concept: the scale from shot 5 grows to full width and gains its two thresholds, then four
cases get their verdict chips one by one, and the fail-closed rule closes the card.

```
+--------------------------------------------------------------+
| THE DECISION . 2 OF 4                                        |
| From a probability to an action                              |
|                                                              |
| 0.0                 0.35               0.65             1.0  |
| ====================|==================|===================  |
|  0.35 or below:      between: ask the    0.65 or above:      |
|  confident no        operator            confident yes       |
|                                                              |
| |a person in frame                | [DENY]                   |
| |an invented distance             | [GUIDE]  re-plan         |
| |unsure, in the band              | [CONFIRM]  ask the oper. |
| |otherwise                        | [PROCEED]                |
| |a late or missing decider        | [DENY]                   |
|                                   | The gate never fails open|
| Row 7 on the car: Confirm (...)   |                          |
|  . . . . . . . . . caption zone . . . . Agent/Judge . . . .  |
+--------------------------------------------------------------+
```

Layout: the scale band `y 220..300` spans the full content width; the rows below use the
decision split (case left, verdict right).

The scale:
- On the cut the shot-5 scale is on screen at its old place (`1118..1824, 538..542`) and the
  title `From a probability to an action` is on the plate (chrome on the cut). At s1 (0.37)
  `Two thresholds make the action.` the scale travels to `96..1824, 260..264` over 720 ms
  (move curve) with its `0.0` and `1.0` labels riding along to (96, 226) and right-aligned
  1824 at y 226; the divider's top retracts from 200 to 340 over the same 720 ms on the move
  curve, so the scale band is uninterrupted.
- Zone segments: red `96..701`, cyan `701..1219`, green `1219..1824` (0.35 at x 701, 0.65 at
  x 1219 on a 1728 px rule). Before a zone is spoken its segment is ink-mute at 35 percent.
- Each zone is two beats keyed to its words. s2 (2.64) `Zero point six five`: a 2 px tick
  `1218..1220, 254..270` turns green and `0.65` Mono-XS 20 green lands centred on the tick at
  y 232; s2%60 (4.94) `a confident yes`: the green segment recolours (240 ms) and `0.65 or
  above: confident yes` Body-S 28 green enters centred on x 1521 at y 284.
- s3 (6.47) `Zero point three five`: tick `700..702, 254..270` red and `0.35` Mono-XS 20 red
  centred on the tick at y 232; s3%60 (8.69) `a confident no`: the red segment and `0.35 or
  below: confident no` centred on x 398 at y 284.
- s4 (10.17) `Between them`: both ticks extend to `254..278` in cyan for 240 ms and settle (a
  draw, not a pulse); s4%50 (11.41) `the operator is asked`: the cyan segment and `between:
  ask the operator` centred on x 960 at y 284. Six events across ten seconds, each on its
  words.

The rows, pitch 84: y 372, 456, 540, 624, 708. Each row: accent bar 2 px in the verdict colour
`96..98, y-2..y+38`; case Body 32 ink at (120, y); chip at (1118, y-2); consequence Body-S 28
ink-dim at (chip right edge + 24, y+4).

| Anchor (resolved) | Case | Chip | Consequence |
|---|---|---|---|
| s5 (12.65) | `a person in frame` | DENY red | |
| s6 (15.15) | `an invented distance` | GUIDE amber | `re-plan` |
| s7 (18.67) | `unsure, in the band` | CONFIRM cyan | `ask the operator` |
| s8 (20.78) | `otherwise` | PROCEED green | |
| s9 (22.91) | `a late or missing decider` | DENY red | |

Row entrance: the bar draws (240 ms), the case enters from the left and the chip from the
right at +60 ms (480 ms, chip scale 0.92 to 1.00 with its bloom), the consequence at +120 ms.
The chip's bloom is the row's only cue; nothing on the scale moves after s4%50.

- `The gate never fails open.` Body-S 28 ink at (1118, 764), s9%62 (25.10).
- Note, Body-XS 26 ink-dim, two lines under the left column where the rows end at 748:
  `Row 7 on the car: Confirm (the marshal may approve` at (120, 780) and `a bigger hop); in
  the library: Guide.` at (120, 814), width up to 974, entering at s9%62+0.24 (25.34).

Layers (z): 10 bg; 30 divider (top retracting 200 to 340 with the scale travel, bottom 848);
40 scale, ticks, values and zone labels; 50 rows; 60 closing lines; 92 title `From a
probability to an action` on the cut (chrome); 94 badge; 95 kicker `THE DECISION  .  2 OF
4`; 97 rail. No lower-third.

Camera: none.

Pointers: the accent bars, the ticks and the zone recolours.

Honesty label: none (thresholds from the repo; v1 carried none). Badge shown.

Transition in: hard cut from shot 5 with the scale carried over. Transition out: hard cut to
shot 7; the chrome and divider persist.

The viewer understands: two thresholds, three zones; a person means Deny, an invented
distance means Guide, unsure means the operator is asked, otherwise Proceed, and a missing
decider is a Deny.

## Shot 7, s07-one-request (80.80, 16.43 s): one real request, one real answer

Concept: a real request on the left, its three probabilities growing on the right past the
YES line, joined by one thin evidence leader from "0.2" to the grounded bar.

```
+--------------------------------------------------------------+
| THE DECISION . 3 OF 4         [RECORDED 2026-10-22, REAL ...]|
| One real request, one real answer                            |
|                                                              |
| REQUEST (state)                   | ANSWER          0.65     |
| "conversation": "user: Move       |                  :       |
|   forward 20 centimetres."      | args_grounded   ####: 0.907|
|          ~~~~~~~~~~~~~ cyan       |    o---leader    :       |
| "command": {"tool": "move",     | inside_envelope #####:0.948|
|   "arguments": {... "distance_m": 0.2}}         :            |
|                                ~~~ cyan           :          |
| "envelope": "distance_m <= 0.5 .. | intent        #####:0.959|
|   |heading_deg| <= 90",           |   move_forward   :       |
| "deterministic_check": "ok"       |                          |
|                                   | [PROCEED]   583 ms       |
|                                   |                          |
|  . . . . . . . . . caption zone . . . . Agent/Judge . . . .  |
+--------------------------------------------------------------+
```

Left column (the request), Mono 28 / 44 at x 96, line n at y 248 + 44 n, keys ink-dim and
values ink:
- `REQUEST (state)` Mono-S 22 ink-dim at (96, 200), s1 (0.36).
- Line 0 `"conversation": "user: Move forward 20 centimetres."` at s1; underline, cyan, under
  `20 centimetres.` (`703..955`, y 282) drawing on at s1%35 (1.60) `twenty centimetres`, the
  span recolouring to cyan.
- Lines 1 and 2 `"command": {"tool": "move",` and `  "arguments": {"heading_deg": 0,
  "distance_m": 0.2}},` at s1%42 (1.84); underline cyan under `0.2` (`922..972`, y 370) at
  s1%80 (3.18) `zero point two`.
- Lines 3 to 5 `"envelope": "distance_m <= 0.5 per call,` / `  |heading_deg| <= 90",` /
  `"deterministic_check": "ok"` at s3 (7.43) `Inside the envelope`.

Right column (the answer):
- Setup beat at s1%80+0.3 (3.48), in the quiet between "zero point two" and "Grounded":
  `ANSWER` Mono-S 22 ink-dim at (1118, 200); the YES line `0.65` Mono-XS 20 green centred on
  x 1604 at y 222 and a dotted green vertical (dash 4, gap 4, 1 px) `x 1604, 252..548`; and
  the three bar tracks, tinted with the zones the viewer learned on shot 6: red `1370..1496`,
  cyan `1496..1604`, green `1604..1730` at 10 percent (0.35 at x 1496 and 0.65 at x 1604 on
  a 360 px scale for 1.0 from x 1370). The scale is one character from 5 through 8.
- Rows at y 268, 368, 468: label Mono 26 ink at (1118, y+4); bar track `1370..1730, y-6..y+22`
  (28 tall, radius 4, tinted as above); fill from zero over 600 ms (draw curve), ink-dim until
  the fill crosses x 1604, green after; value Mono 26 ink right-aligned to 1824 at y+4,
  entering when the fill stops. s2 (4.60) is the `args_grounded` label and the leader only.

| Row | Label | Fill end | Value | Label at | Fill from | Value at |
|---|---|---|---|---|---|---|
| 1 | `args_grounded` | x 1697 (0.907) | `0.907` | s2 (4.60) | s2%20 (5.02) | 5.62 |
| 2 | `inside_envelope` | x 1711 (0.948) | `0.948` | s3 (7.43) | s3%43 (8.89) | 9.49 |
| 3 | `intent`, with `move_forward` Mono-S 22 ink-dim at (1118, 508) | x 1715 (0.959) | `0.959` | s4 (10.84) | s4%33 (11.56) | 12.16 |

- Evidence leader: 1.5 px cyan at 70 percent from the right end of the `0.2` underline (984,
  370) to a dot at (1360, 276), 8 px left of the grounded bar, drawing on over 360 ms at s2
  (4.60) `Grounded`; the dot pings once. It crosses the divider; that is the point.
- Chip PROCEED at (1118, 586) at s5 (13.02), with its bloom.
- `583 ms`: counter Title-S 48 Bold ink, digits in a fixed box right edge x 1470 at y 580,
  counting 0 to 583 over 600 ms from s5%38 (14.10) (55 percent opacity while counting), unit
  `ms` Body 32 ink-dim at (1484, 592).

Layers (z): 10 bg; 30 divider; 40 request text; 45 underlines; 50 answer labels and tracks;
55 fills and values; 58 YES line; 60 leader and dot; 70 chip and counter; 92 title `One real
request, one real answer` at s1; 94 badge; 95 kicker `THE DECISION  .  3 OF 4`; 96 pill
`RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`; 97 rail. No lower-third (as v1).

Camera: none.

Pointers: two underlines, one leader, one dotted threshold. No arrow, no bracket, no boxes.

Honesty label: `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`. Badge shown.

Transition in: hard cut from shot 6. Transition out: hard cut to shot 8 (the chrome, divider
and bottom band hold; the columns swap content).

The viewer understands: the user said twenty centimetres, the tool call said 0.2, so the
grounding question scored 0.91, the envelope 0.95, the intent matched, and the real decider
said Proceed in 583 ms.

## Shot 8, s08-recorded-run (97.23, 26.50 s): the recorded run, step by step

Concept: a real terminal on the left with a cursor and two typing rhythms (human and
machine), and a step timeline on the right that lights one node per clause.

```
+--------------------------------------------------------------+
| THE DECISION . 4 OF 4         [RECORDED 2026-10-22, REAL ...]|
| +------------------------------+ |  o "Go." carries no dist. |
| | o o o                        | |  o Nova Pro guesses 2 m   |
| | USER : Go.                   | |  o check fails: 2 > 0.5;  |
| | {"arguments": ... "distance_m": 2},  o GUIDE: re-plan      |
| |  "deterministic_check": "distance_m 2 > 0.5",              |
| |  "args_grounded": 0.18, "verdict": "Guide", o grounded 0.40|
| |  "reason": "outside envelope ..."}  o CONFIRM: the operator|
| | {"arguments": "distance_m": 0.5},  o scripted operator: no |
| |  ... "args_grounded": 0.404,   | |                         |
| |  "verdict": "Confirm",         | |  | A guessed distance   |
| | CONFIRM (operator asked): ...  | |    moved nothing.       |
| | OPERATOR: no (this cell auto-answers False)                |
| | AGENT: (thinking omitted) ..._  | |                        |
| | Recorded run, 2026-10-22: the real decider judges Nova Pro |
|  . . . . . . . . . caption zone . . . . Agent/Judge . . . .  |
+--------------------------------------------------------------+
```

Left column: a terminal panel `96..1094, 200..848` (surface, radius 12, border, shadow; it
ends inside the content band so its shadow stays out of the bottom band), header strip
`200..232` with the three dots at (116, 216), (132, 216), (148, 216) r 5 ink 20 percent, no
title. Text Mono-term 24 / 32 at x 120, line n at y 256 + 32 n (18 lines, the last at
800..824; the panel's inner bottom is 824). The 18 lines are the v1 lines verbatim
(`shots.yaml` s08 `lines`), nothing pre-shown. Cursor: block 13 x 26 ink after the last typed
character, blinking 530 ms, visible while idle and while a human line types, hidden while a
machine row prints.

Colour rule on this shot: the current step label is the only orange. Terminal underlines use
the evidence colour (cyan, as the same argument values were underlined on shot 7) and the
zone colours the viewer learned on shot 6 (red below 0.35, cyan in the band) and the verdict
colours (amber Guide, cyan Confirm), so 0.18 and 0.404 are read on the same scale as 0.907.

Schedule (a line starts at its anchor or after the previous line ends, whichever is later):

| Line(s) | Class | Anchor (resolved) | Underline (2 px, 6 px under the baseline) |
|---|---|---|---|
| 0 `USER : Go.` | human 24 cps | s1%67 (1.61) | |
| 1 | machine 80 cps | s2%40 (3.80) | `"distance_m": 2` cyan (evidence) at s2%40+0.4 |
| 2 | machine | s3 (6.15) | `"distance_m 2 > 0.5"` cyan at s3+0.4; the line-1 underline settles to 50 percent |
| 3 | machine | s3%33 (8.03) | `0.18` red (0.35 or below: confident no) at s3%33+0.4 |
| 4 | machine | s3%83 (10.87) | `"Guide"` amber (verdict) at s3%83; the `0.18` underline settles |
| 5 | machine | s4 (11.84) | `"distance_m": 0.5` cyan at s4+0.4; earlier cyan settles |
| 6 | machine | s5 (14.36) | `0.404` cyan (the band) at s5+0.4; then at s5%40 (about 16.6, "inside the unsure band") a quiet underline in ink at 60 percent on `"deterministic_check": "ok"`: the check passed, so the grounding alone is unsure |
| 7, 8 | machine | s5%67 (18.70) | `"Confirm"` cyan (verdict) at s5%67+0.4; `0.404` settles |
| 9, 10, 11 | machine | after line 8 (about 19.6) | |
| 12 `OPERATOR: no (this cell auto-answers False)` | human 24 cps | s6 (20.83) or after line 11 (about 21.1) | the whole line cyan when typed |
| 13 to 17 | machine | s7 (23.11) | |

The agent's reply finishes typing at about 25.7; the cursor rests after `clarification.` to the
cut. Typing never overlaps the next clause by more than 0.4 s (the OPERATOR line is the tight
one; it is typed by a human, slowly, which is the point; the human rate never drops below 24
cps).

Right column: a step timeline. Vertical line 2 px ink 12 percent at x 1134 from y 256,
growing (draw curve, 240 ms) to each new node; nodes r 6 at (1134, y+20), centred on the
label's text box; labels Body 32 at (1160, y), pitch 60. The current node and label are orange
(a 1 px ring r 12 orange at 50 percent around the node, no glow); earlier ones recolour to
ink-dim over 240 ms.

| y | Label | Anchor (resolved) |
|---|---|---|
| 236 | `"Go." carries no distance` | s2 (2.23) |
| 296 | `Nova Pro guesses 2 m` | s2%40 (3.80) |
| 356 | `check fails: 2 > 0.5; grounded 0.18` | s3 (6.15) |
| 416 | `GUIDE: re-plan` | s3%83 (10.87) |
| 476 | `Nova Pro proposes 0.5 m` | s4 (11.84) |
| 536 | `grounded 0.40: the unsure band` | s5 (14.36) |
| 596 | `CONFIRM: the operator is asked` | s5%67 (18.70) |
| 656 | `scripted operator: no` | s6 (20.83) |

Closing caption at s7+0.7 (23.81): accent bar 3 px orange `1118..1121, 740..776`, text `A
guessed distance moved nothing.` Label-L 36 Medium ink at (1140, 736); the last node recolours
to ink-dim as the caption lands (one orange at a time).

Layers (z): 10 bg; 30 divider; 40 terminal panel; 45 terminal text; 48 underlines; 50
cursor; 60 timeline line and nodes; 62 labels; 70 caption; 93 lower-third `Recorded run,
2026-10-22: the real decider judges Nova Pro` (no plate; the panel ends at 848 and the
lower-third starts at 860); 94 badge; 95 kicker `THE DECISION  .  4 OF 4`; 96 pill `RECORDED
2026-10-22, REAL DECIDER + NOVA PRO`; 97 rail. No title: the lower-third names the shot.

Camera: none.

Pointers: underlines on the terminal; the timeline nodes. No boxes.

Honesty label: `RECORDED 2026-10-22, REAL DECIDER + NOVA PRO`. Badge shown.

Transition in: hard cut from shot 7. Transition out: push-left into shot 9 (chapter change).

The viewer understands: "Go." carried no distance, the model guessed two metres, the
arithmetic check caught it and the decider said Guide; the re-plan at half a metre scored in
the unsure band so the operator was asked and said no; the car never moved on a guess.

## Shot 9, s09-on-the-car (123.73, 9.50 s): measured on the real car

Concept: the on-car proof as a quiet statement beside the shape of the frame that is not
being shown, so "the frames stay private" has a picture.

```
+--------------------------------------------------------------+
| THE PROOF . 1 OF 3    [MEASURED ON THE CAR 2026-10-15, REAL ]|
| Measured on the real car   [FRAMES WITHHELD: THEY SHOW A ...]|
|                                                              |
|                                                              |
|   +---------------+   On the car: a person in frame was      |
|   | / / / / / / / |   denied in 456 ms                       |
|   |/ / / / / / / /|                                          |
|   | / / WITHHELD /|   person_in_frame   p = 0.9485           |
|   |/ / / / / / / /|                                          |
|   | / / / / / / / |   whole gate 681 to 727 ms per hop; no   |
|   |/ / / / / / / /|   motion event after the deny            |
|   +---------------+   Source: docs/results/beats-car-...     |
|                                                              |
|                                                              |
| | On the car, 2026-10-15             Agent: Amazon Nova Pro  |
|  . . . . . . . . . caption zone . . . . Judge: Strands . . . |
+--------------------------------------------------------------+
```

Layout: halves at cols 1-4 and 5-12. Left: the withheld frame, a panel `96..576, 300..660`
(480 x 360, the camera's frame size named on shot 5), surface, 1 px border, radius 8. Its
outline is on the plate from frame 0 (the hole reads as a frame, not a layout gap); at s2 the
diagonal hatch (1 px lines at 45 degrees every 24 px, ink at 6 percent) and `WITHHELD` Mono-S
22 ink-dim centred at (336, 466) fill it (fade, 480 ms). It is an empty frame, not a picture
of anything. Right, x 672..1824:
- Heading as a span reveal, Heading 40 Medium ink at (672, 300), measured as one line (about
  924 px): span 1 `On the car: a person in frame was denied` at s1 (0.36); span 2 `in 456 ms`
  at s1%78 (3.85) `four hundred fifty six`, each fade plus 16 px rise. The number lands on its
  words, not three seconds before them.
- `person_in_frame   p = 0.9485` Mono 28 ink at (672, 380), s1%45 (2.37).
- `whole gate 681 to 727 ms per hop; no motion event after the deny` Body-S 28 ink-dim at
  (672, 450), one line (about 915 px), s2 (6.44).
- `Source: docs/results/beats-car-2026-10-15-person-gate` Mono-S 22 ink-dim at (672, 510),
  s2+1.2 (7.64).

Layers (z): 10 bg; 40 withheld frame (outline on the plate, hatch and label at s2); 50 text;
92 title `Measured on the real car` Title 56, on the incoming plate with the kicker (frame 0,
no second entrance); 93 lower-third `On the car, 2026-10-15` (kept: it carries the date in
the band where the viewer reads it); 94 badge (the judge here is the real decider, so the
badge is true); 95 kicker `THE PROOF  .  1 OF 3`; 96 two pills `MEASURED ON THE CAR
2026-10-15, REAL DECIDER` (y 62..102) and `FRAMES WITHHELD: THEY SHOW A PERSON` (y 110..150);
97 rail.

Camera: none.

Pointers: none.

Honesty labels: the two pills above. Badge shown.

Transition in: push-left from shot 8 (chapter change). Transition out: hard cut to shot 10.

The viewer understands: on the real car the same gate denied a hop with a person in frame in
456 ms, the number is sourced, and the frames are withheld because they show a person.

## Shot 10, s10-sim-deny (133.23, 10.00 s): the Deny in the simulator

Concept: the Pit Wall as the product's own screen, read by a spotlight that follows the voice
(figure, chips, DENY, the rover's line), then the whole screen recedes under the safety line.

```
+--------------------------------------------------------------+
| PIT WALL       [Row 3: person in frame -> Deny]      run OPEN|
|  +------------------------+  SIM ARMED RED LED 8/10 OPEN     |
|  | LIVE  (spotlight on    |  VERDICT  +--------+             |
|  |        the figure)     |           |  DENY  | red focus   |
|  |         ( o )          |           +--------+             |
|  |         /|\            |  person in frame (p=0.97)        |
|  |         / \            |  +----------------------+ cyan   |
|  | ["Someone is in front  |  | CLASS   | PROBABILITY| focus  |
|  |   of me. I stopped."]  |  +----------------------+        |
|  | [class] [0.97] [Deny]  |  STOP  DENY 92 ms (not marked)   |
|  +------------------------+  [ STOP ALL ]                    |
|  ROVER log ...                                               |
|       Physics stops the car. The decider explains. (s2, s3)  |
|                                                              |
| | Pit Wall, the simulated car   [SIM, FAKE DECIDER, DRAWN ..]|
|  . . . . . . . . . caption zone . . . . . . . . . . . . .    |
+--------------------------------------------------------------+
```

Layout: `docs/article/img/fig-portal-stage.png` at `0..1920, 0..1080`, native, no push, the
one full-bleed screen (DESIGN section 4 exception) so every coordinate is 1:1 with the
screenshot.

Layers (z):
- 20 the screenshot.
- 40 spotlight, 48 px feather, outside at 40 percent, built as sequential single spotlights
  (new to the renderer: each added region is its own 480 ms fade; the union is what the viewer
  sees): at s1%15 (1.16) `a figure in the frame` the figure ellipse centred (620, 520) radii
  240 x 330; at s1%35 (2.22) `row three` the CLASS and PROBABILITY chips `1234..1700,
  314..388`; at s1%55 (3.28) `a Deny` the DENY word `1232..1540, 158..262`; at s1%80 (4.60)
  `the rover says why` the quote card's box `150..1110, 300..376`.
- 45 focus frames: cyan on the CLASS and PROBABILITY chips `1234..1700, 314..388` at s1%35
  (not the LATENCY chip at x 1710 and beyond: that is a fake-stack number); red on the DENY
  word `1232..1540, 158..262` at s1%55 (the UI's own verdict word keeps its verdict colour).
- 50 quote card at s1%80 (4.60): plate `150..1110, 300..376` (bg at 72 percent, radius 8)
  with a 3 px orange bar at x 150, text `"Someone is in front of me. I stopped."` Medium Italic
  44 ink at (176, 314). Exits at s2 (6.27), 240 ms, so it never sits under the safety line
  (round-3 finding 6).
- 55 caption `Row 3: person in frame -> Deny` Medium 36 ink on a plate `754..1313, 8..62` in
  the header's empty stretch, from +0.3, above the title-safe margin on purpose (as v1).
- 60 safety line at s2 (6.27): the whole screenshot dims to 30 percent over 480 ms (the
  spotlight closes); `Physics stops the car. The decider explains.` Display-M 72 Bold ink,
  centred on x 960, text box y 492..572, measured as one line; its first span `Physics stops
  the car.` enters at s2, its second span `The decider explains.` at s3 (8.14), each with fade
  plus 16 px rise. No band plate: the dim is the plate.
- 93 lower-third `Pit Wall, the simulated car` on a plate (over the ROVER log).
- 96 pill `SIM, FAKE DECIDER, DRAWN FIGURE` as an opaque pill in the verdict card's empty
  stretch, right edge x 1884, y 580..620 (the top-right is the Pit Wall's own status chips and
  the bottom-right is its HOLD TO TALK button; on the card it reads as a sticker, not as
  product UI). It stays at 100 percent through the dim at s2.
- 97 rail. Badge hidden.

Camera: none.

Pointers: the spotlight and two focus frames. The `92 ms` stop card and the `257 ms` latency
chip are never marked.

Honesty label: `SIM, FAKE DECIDER, DRAWN FIGURE`.

Transition in: hard cut from shot 9. Transition out: hard cut to shot 11.

The viewer understands: in the simulator row three is a Deny, the rover says why in a
sentence, and the line the film repeats is that physics stops the car and the decider
explains.

## Shot 11, s11-numbers (143.23, 12.83 s): the numbers

Concept: four measured numbers as a clean data moment: two bars on one shared "of 72" scale
make the one comparison, and the latency sits against its budget.

```
+--------------------------------------------------------------+
| THE PROOF . 3 OF 3                      [MEASURED 2026-10-22]|
| Measured on the booth laptop: 72 timed calls                 |
|                                                              |
| o Strands Decider 2B, local   | o Amazon Nova Pro on Bedrock |
|                               |                              |
|  462 ms                       |  0.13 USD                    |
|  median, three questions ...  |  per 1000 decisions          |
|  ####______________| 1.5 s    |                              |
|                               |                              |
|                               |                              |
|  0 of 72                      |  31 of 72                    |
|  over the 1.5 s budget        |  over the 1.5 s budget       |
|  |___________________________ |  ############________________|
|                               |                              |
|                                      Agent: Amazon Nova Pro  |
|  . . . . . . . . . caption zone . . . . Judge: Strands . . . |
+--------------------------------------------------------------+
```

Layout: halves, left `96..948`, right `972..1824`, divider at x 960 from y 200 to 848.

Headers at s1 (0.36) and s2 (6.59): a 12 px disc at (102, 214) orange (left) and ink-dim
(right); `Strands Decider 2B, local` and `Amazon Nova Pro on Bedrock` Lower-third 32 Medium
ink at (120, 200) and (996, 200).

Row 1, y 250:
- Left, s1%19 (1.24): counter `462` Display 96 Bold ink, digits in a fixed box with its right
  edge at x 330, counting 0 to 462 over 600 ms (55 percent opacity while counting), unit `ms`
  Body 32 ink-dim at (344, 302); caption `median, three questions in one request` Body-XS 26
  ink-dim at (96, 366); bar track `96..726, 410..422` (630 px = 1500 ms, ink 8 percent) with
  the fill growing to x 290 (462 of 1500) in green over 600 ms (draw curve) from s1%19+0.3; a
  2 px tick at x 726 (`724..728, 404..428`) ink-dim with `1.5 s budget` Mono-XS 20 ink-dim
  right-aligned to x 726 at y 432.
- Right, s2%73 (10.06): counter `0.13` (decimals 2) Display 96 with its right edge at x 1190,
  unit `USD` Body 32 ink-dim at (1204, 302); caption `per 1000 decisions` at (972, 366). No
  bar: cost has no budget on this card.

Row 2, y 520, the one comparison on a shared scale (630 px = 72 calls):
- Left, s1%56 (2.96): `0` Display 96 (right edge x 170) lands as a plain entrance (a counter
  from 0 to 0 is a non-event, so it does not count), unit `of 72` Body 32 ink-dim at (184,
  572); caption `over the 1.5 s budget` at (96, 636); bar track `96..726, 680..692`; fill:
  zero, drawn as a 2 px green tick `96..98, 676..696` that draws on top to bottom over 240 ms:
  the tick is the fact.
- Right, s2%27 (7.88): counter `31` (right edge x 1080, so the 3 starts inside the column),
  `of 72` at (1094, 572); caption `over the 1.5 s budget` at (972, 636); bar track `972..1602,
  680..692`; fill amber growing from x 972 to x 1243 (31 of 72) over 600 ms from s2%27+0.3.

Layers (z): 10 bg; 30 divider; 40 headers; 50 counters and units; 55 captions; 60 tracks,
ticks, fills; 92 title `Measured on the booth laptop: 72 timed calls` at s1 (0.36) (it lands
with the first words; the kicker arrived on the cut); 94 badge; 95 kicker `THE PROOF  .  3 OF
3`; 96 pill `MEASURED 2026-10-22`; 97 rail. No lower-third: the kicker and the title name
the card.

Camera: none.

Pointers: none; the bars are the comparison.

Honesty label: `MEASURED 2026-10-22`. Badge shown.

Transition in: hard cut from shot 10. Transition out: push-left into shot 12 (chapter change).

The viewer understands: the local decider answers in 462 ms median and never missed the 1.5 s
budget in 72 calls; Nova Pro on Bedrock missed it 31 times and costs 0.13 USD per thousand
decisions.

## Shot 12, s12-pattern (156.07, 9.20 s): the reusable pattern, as a code editor

Concept: the pattern shown where a developer lives: a file tree, an editor tab with the three
lines of wiring and two underlined spans, a status bar with the repo path, and a terminal
that bursts the demo's stdout.

```
+--------------------------------------------------------------+
| THE PATTERN                         [FAKE DECIDER, STDOUT ..]|
| Drop it into your own agent                                  |
| +----------+-[three lines of wiring]--- Agent / Judge ------+|
| | three    | 1 decider = Decider(timeout=1.5)               ||
| | files..  | 2 agent = Agent(      ~~~~~~~~~~~ cyan         ||
| | patterns/| 3     model=BedrockModel(model_id="us.amazon..| |
| |  _client | 4                        region_name="us-east-1 |
| |  tool_.. | 5     tools=[move],                            ||
| |  frame_..| 6     interventions=[MotionGate(decider)],     ||
| |  README  | 7 )   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ orange  ||
| +----------+-- github.com/Vivek0712/.../patterns/strands ---+|
| +-----------------------------------------------------------+|
| | o o o  make pattern-demo, against the fake decider ...    ||
| | {"tool": "move", .. "verdict": "Proceed", "reason": ... _ ||
| | {"tool": "move", ... "verdict": "Guide", ...   (burst)    ||
| +-. . . . . . . . . caption zone . . . . . . . . . . . . --+ |
+--------------------------------------------------------------+
```

Editor panel `96..1824, 200..556` (surface, radius 12, border, shadow):
- Sidebar `96..520` for the panel's full height, 1 px right border; header `three files,
  upstream names` Caption 22 ink-dim at (120, 212); tree rows Mono-S 22 ink at x 120, y 252,
  284, 316, 348, 380: `patterns/strands/`, `  _client.py`, `  tool_call_intervention.py`
  (351 px, ending at 471, inside the sidebar), `  frame_intervention.py`, `  README.md`. Rows
  enter with a 60 ms stagger at s2 (2.33) `Three files`; the `README.md` row sits on surface-2
  (the active file: the snippet is from the README).
- Tab strip `520..1824, 200..236` (surface-2): one tab `three lines of wiring` Caption 22
  ink on surface with a 2 px top edge in ink at 60 percent, `520..800`; the badge docked at the
  right as one line badge-docked Mono-XS 20 ink-dim right-aligned to x 1800 at y 208: `Agent:
  Amazon Nova Pro on Bedrock | Judge: Strands Decider 2B, local`. The badge never leaves the
  tab strip.
- Gutter `544..580`: line numbers 1 to 7 Mono-XS 20 ink-mute right-aligned to x 576.
- Code Mono 26 / 38 at x 600, line n at y 258 + 38 n, the seven v1 lines verbatim (the longest
  is 928 px and ends at 1528), entering one line at a time top to bottom with a 60 ms stagger
  (420 ms in all) from s2%30 (3.80) `three lines of wiring` (fade plus 16 px rise each).
  Underlines: cyan under `timeout=1.5` at s2%40 (4.29); orange under
  `interventions=[MotionGate(decider)]` at s2%50 (4.78), the one orange content element.
- Status bar `96..1824, 516..556` (surface-2): the path
  `github.com/Vivek0712/strands-robots-deepracer/tree/main/patterns/strands` Mono-S 22 cyan at
  (544, 525). This replaces the lower-third on this shot.

Terminal panel `96..1824, 588..920` (inside the bottom band's top edge; nothing of it is
essential below 900): header strip `588..624` with the dots and the title `make pattern-demo,
against the fake decider (a script, not the model)` Mono-XS 20 ink-dim at (172, 598); rows
Mono-S 22 / 28 at x 120 from y 640: lines 7 to 9 of `docs/video/build/clips/pattern-demo.txt`
wrapped at 118 characters with a two-space continuation (10 lines; nine full rows end at 892;
the tenth, the deny row's error tail, is cut by the panel's bottom edge under a 24 px fade to
the panel colour). Burst class, 560 cps, from s2%62 (5.36) `make pattern demo`, finishing at
about 7.4; the cursor blinks after the last character. Verdict underlines in reading order
with a 120 ms stagger from +7.5: green under `"verdict": "Proceed"` (7.50), amber under
`"verdict": "Guide"` (7.62), red under `"verdict": "Deny"` (7.74); the three `"reason": ...`
values recolour from ink-dim to ink over 240 ms with their verdict, no underline.

Layers (z): 10 bg; 40 editor panel; 42 sidebar; 44 tab strip and badge; 46 gutter; 48 code;
50 underlines; 52 status bar; 60 terminal panel; 62 terminal text and cursor; 64 terminal
underlines; 92 title `Drop it into your own agent` Title 56 on the incoming plate with the
kicker (frame 0, no second entrance); 95 kicker `THE PATTERN`; 96 pill `FAKE DECIDER, STDOUT
VERBATIM`; 97 rail.

Camera: none.

Pointers: underlines only.

Honesty label: `FAKE DECIDER, STDOUT VERBATIM`. Badge shown (in the tab strip).

Transition in: push-left from shot 11 (chapter change). Transition out: hard cut to shot 13a.

The viewer understands: three files with the upstream names, three lines of wiring, and a
make target that runs the gate offline, printing Proceed, Guide and a fail-closed Deny with
their reasons; the path is on screen.

## Shot 13a, s13a-mumbai-speaker (165.27, 2.00 s): Mumbai, the speaker

Concept: two seconds of the author on stage with the car, full-bleed, breathing in.

```
+--------------------------------------------------------------+
|                                                              |
|                     +------------------+                     |
|   (darkened blur    |  portrait photo  |    (darkened blur   |
|    of the photo,    |  speaker on stage|     of the photo)   |
|    drifting 4 px)   |  holding the car |                     |
|                     |                  |                     |
|                     |  push 1.00->1.03 |                     |
|                     |                  |                     |
|                     |                  |                     |
|                     |                  |                     |
|                     |                  |                     |
|                     |                  |                     |
|                     +------------------+                     |
| | AWS Community Day Mumbai, 17 October 2026  (plate)         |
|  . . . . . . . . . caption zone . . . . . . . . . . . . .    |
|                                                              |
+--------------------------------------------------------------+
```

Layout: `docs/article/img/event-speaker-with-car.jpg` fitted to height, `555..1365, 0..1080`,
over its own blur fill (24 px, 35 percent). Real photo: full-bleed, no panel.

Layers (z): 15 blur fill (drifts 4 px left over the shot, drift curve); 20 photo (push-in
1.00 to 1.03 over 2.0 s, drift curve, about its centre; it drifts 8 px right as the fill goes
left: the two-layer parallax); 93 lower-third `AWS Community Day Mumbai, 17 October 2026` on
a plate, entering at +0.38 (the first word); 97 rail. No pill (an approved event photo, as
v1); badge hidden.

Camera: as above.

Pointers: none.

Transition in: hard cut from shot 12. Transition out: 12-frame cross-dissolve into 13b.

The viewer understands: this was shown to a room.

## Shot 13b, s13b-mumbai-hall (167.27, 2.00 s): Mumbai, the hall

Concept: the room, breathing out.

```
+--------------------------------------------------------------+
|                                                              |
|        +----------------------------------------+            |
|  (blur |  landscape photo of the hall           |  (blur     |
|  fill) |  audience watching the slide           |   fill)    |
|        |                                        |            |
|        |  pull-out 1.03->1.00                   |            |
|        |                                        |            |
|        |                                        |            |
|        |                                        |            |
|        |                                        |            |
|        |                                        |            |
|        |                                        |            |
|        +----------------------------------------+            |
| | AWS Community Day Mumbai, 17 October 2026  (held)          |
|  . . . . . . . . . caption zone . . . . . . . . . . . . .    |
|                                                              |
+--------------------------------------------------------------+
```

Layout: `docs/article/img/event-hall.jpg` fitted to height, `240..1680, 0..1080`, over its
blur fill. Camera: pull-out 1.03 to 1.00 over 2.0 s (drift curve), the mirror of 13a, so the
pair reads as one breath; the fill drifts 4 px the other way.

Layers (z): 15 fill; 20 photo; 93 lower-third held from 13a (no re-entrance); 97 rail.

Transition in: 12-frame dissolve from 13a (inside this shot's first 0.40 s). Transition out:
12-frame dissolve into shot 14.

The viewer understands: the same, with the audience.

## Shot 14, s14-close (169.27, 8.00 s): the close

Concept: a confident resolve: the URL first (the voice says "below"), then the safety line in
two spans on its two sentences, the tags, the mark, a slow exhale, and the only dip to black.

```
+--------------------------------------------------------------+
|                                                              |
|           (cover render at 30 percent, slow push-in)         |
|                                                              |
|                                                              |
|                                                              |
|         Physics stops the car.  The decider explains.        |
|                                                              |
|          github.com/Vivek0712/strands-robots-deepracer       |
|                                                              |
|     Vivek Raja, AWS AI Hero  |  Article on AWS Builder Center|
|                                                              |
|              #strands-decider-2b   #guardrails               |
|                                                              |
|                                                   [S mark]   |
|                                                              |
|  . . . . . . . . . caption zone, empty . . . . . . . . . .   |
+--------------------------------------------------------------+
```

Layout: `docs/article/img/cover.png` scaled to `0..1920, 0..1080` at 30 percent brightness,
push-in 1.00 to 1.04 over the 8.0 s (drift curve); its own glow ribbons give the two-layer
look (the render is a composite, so the parallax is the push alone). The stack is centred on
x 960.

Layers (z) and entrances. The safety line is the only headline; the URL, the author line and
the tags are support, set small, with 24 px between them:
- 20 cover.
- 50 URL `github.com/Vivek0712/strands-robots-deepracer` URL 32 Menlo cyan (851 px), centred,
  text box y 468..506, at s1 (0.47) `Repo and article below.` (fade plus 16 px rise).
- 52 author line `Vivek Raja, AWS AI Hero  |  Article on AWS Builder Center` Body-XS 26 ink,
  centred, text box y 530..564, at s1+0.24 (0.71).
- 60 safety line `Physics stops the car. The decider explains.` Title 56 Bold ink, centred
  as one measured line, text box y 372..436: span 1 `Physics stops the car.` at s2 (2.52),
  span 2 `The decider explains.` at s3 (4.39), each fade plus 16 px rise. Between 2.52 and
  5.19 the two spans are the only thing that moves.
- 65 tags `#strands-decider-2b   #guardrails` Mono-S 22 orange, centred, text box y 588..618,
  at s3+0.8 (5.19); the two tags enter with a 60 ms stagger as one element.
- 70 the Strands mark: `docs/video/build/clips/svg-strands-mark.png` (the Chrome render of
  `logos/strands-mark.svg`) cropped to its mark and downscaled with lanczos into the 96 px box
  `1728..1824, 824..920` (the bottom band, clear of the caption zone); or the SVG re-rendered
  at 192 px with the Chrome recipe in ASSETS and downscaled 2x. No glow, fade in at s1 (0.47).
- 97 rail: completes its fill at 7.04 and holds full for 240 ms before the dip takes it.
- Dip to black: the whole frame, including the rail, fades to `#000000` over the last 0.72 s
  (7.28 to 8.00, camera curve). The audio is already silent after 5.59.

Camera: the push-in. Nothing else moves after 5.2; the last 2.1 s before the dip are the
exhale.

Pointers: none.

Honesty label: none (as v1). Badge hidden.

Transition in: 12-frame dissolve from 13b. Transition out: dip to black; end of film.

The viewer understands: where the repo and the article are, who made it, the two hackathon
tags, and the one sentence the film wants remembered.

---

## Renderer primitives required for v2

Names the engineer can implement one by one; the ones marked (exists) are in
`docs/video/render/` today and need the v2 behaviour added.

| Primitive | What it must do |
|---|---|
| `ease(name, t)` | the seven named cubic-bezier curves in `DESIGN.md` section 7, evaluated per frame; every tween takes a curve name, never linear |
| `enter(el, at, dur, curve, travel, from)` / `exit(...)` (exists as `anim`) | fade plus 16 px travel (up, left, right) or scale 0.92 to 1.00; exit 240 ms with 8 px |
| `stagger(list, 60 ms)` | offsets sibling entrances on the same anchor |
| `anchor resolver` (exists) | `s<N>`, `s<N>%<p>`, `s<N>+<d>` from the measured Polly onsets, plus `after: <line>` for terminals |
| `draw_on line` | underline (2 px, left to right, 240 ms), leader (1.5 px, 360 ms, from a dot outward to a label edge, re-anchored per frame; a polyline variant for the shot 4 trace with a colour change on its last segment), rule (the scale), rail |
| `dot ping` | r 5 fill plus a ring r 5 to 14 fading over 480 ms; spent only on named parts (the Decider on shot 3, the evidence dot on shot 7) |
| `focus frame` | 2 px rounded rect drawing on clockwise over 480 ms; exits 240 ms; cyan, red only on the UI's DENY word and the deadman node |
| `spotlight mask` (new: multi-region) | dims everything outside a region (rect or ellipse, 48 px feather) to 40 percent; a shot may stack several single spotlights, each with its own 480 ms fade in, and the viewer sees their union; each lifts on a curve. The existing `SpotlightOverlay` is one region with moves; this is new |
| `glow` (exists as `glow` on `image`) | chip bloom (radius 18, 0.45 to 0.20) and the LED bloom (radius 24, two pulses); refused on any other element |
| `vignette` | radial 18 percent at the corners, every shot, before text |
| `grain` | monochrome gaussian sigma 3, per frame, after everything, before encoding |
| `panel` (exists as `panel`) | surface fill, radius, 1 px border, inner shadow, drop shadow, optional header strip with three dots and a title; sidebar, tab strip, gutter and status bar for the editor |
| `pill` | the honesty label and badge container; opaque over footage |
| `lower_third` (exists) | the v2 geometry: bar 96..99 x 872..908, text at (116, 878), plate only over footage; bar draws before the text |
| `kicker` | Menlo 22 caps orange at (96, 72) |
| `progress rail` | 3 px at y 0..3, five segments; the full-width track draws on from x 0 over 720 ms at shot 1 +1.06 (draw curve); from then on the fill and the orange 16 px head follow the global time (so at the end of the draw the fill is already at about x 19); holds full for 240 ms at the end and leaves with the final dip |
| `parallax still` (extends `still` and `zoom`) | two layers (subject, fill) drifting opposite ways on the drift curve; push-in 1.00 to 1.03/1.04 about a given centre; anchored overlays transform with the layer |
| `camera` (exists) | keyframed views with the camera curve over 720 ms |
| `element move` | an element's box tweened between two positions (the scale travelling on shot 6, the step panel growing on shot 4) |
| `push transition` | 720 ms push-left inside the incoming shot's first frames, outgoing final frame as a frozen plate, camera curve, no timeline change |
| `dissolve` | 12-frame cross-dissolve inside the incoming shot |
| `dip to black` | end only, 720 ms |
| `cursor` (exists as `cursor: true`) | block 13 x 26, 530 ms blink, after the last typed char, hidden while a machine row prints |
| `typing classes` (extends `cps`) | human 24, machine 80, burst 560; `after: <line>` sequencing; 50 ms line pause |
| `ticker` / `scroll` | whole-line terminal scroll on the move curve (not needed on shot 8 as laid out; required if a later edit adds lines) |
| `underline highlight` (replaces `highlight` boxes) | measured from the font, recolours the span, settles to 50 percent when the next cue of the same colour lands |
| `bar grow` (exists as `bar`) | track plus fill from zero over 600 ms on the draw curve, recolour at a threshold x, zero drawn as a 2 px tick |
| `threshold line` (exists as `dotted`) | dash 4 gap 4, with a label above |
| `scale` | the probability rule with end labels, zone segments that recolour, ticks, zone labels |
| `counter` (exists) | 600 ms count on the count curve, 55 percent opacity while counting, fixed digit box, unit on the baseline |
| `chip` (exists) | the v2 chip geometry with the bloom and the 0.92 scale entrance |
| `span reveal` | one measured text line whose spans enter at different anchors (the safety line on shots 10 and 14, the heading on shot 9) |
| `recolor` (exists) | 240 ms on the move curve; also ink-mute to ink in place (shot 5 skeleton names) |
| `hatch fill` | 45 degree 1 px lines every 24 px inside a panel (the withheld frame), fading in after the outline |
| `number badge` (exists as `badge`) | disc r 18 ink with the digit in bg colour, scale 0.6 to 1.0 in 240 ms, never outside the safe margin |
| `image` (exists) | loads PNG only (no cairosvg): the mark comes from `build/clips/svg-strands-mark.png` or a Chrome re-render |
| `check` extensions | fail when text enters y 940..1040, when two orange content elements overlap in time, when any tween has no curve, when an element lands more than 240 ms before or 480 ms after its anchor |
