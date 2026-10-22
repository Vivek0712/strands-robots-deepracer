# Demo video design system, v2

Companion to `STORYBOARD-v2.md`. This file fixes the look of the film: grid, type, colour,
surfaces, light, motion, transitions, chrome, cues, and the things the renderer must never do.
`STORYBOARD-v2.md` applies it shot by shot. Nothing here changes the voice-over, its measured
timing, the shot order, the shot durations (total 2:57.3), any number, any honesty label or
the safety line.

Reference quality: a developer-product keynote film. Dark, restrained UI; one accent used with
discipline; generous space; big confident type; every motion eased and purposeful; nothing
decorative that does not carry meaning.

## 1. Canvas and grid

- 1920x1080, 30 fps, 16:9. Export as before (H.264, 12 Mbps or higher, AAC 48 kHz, voice
  -16 LUFS integrated). No music, no room tone.
- Title-safe margin: 96 px left and right, 72 px top. The bottom is governed by the caption
  zone (section 15), not by a margin.
- 12-column grid inside the margins: column width 122 px, gutter 24 px, 1728 px total.

| Column | x range | Column | x range |
|---|---|---|---|
| 1 | 96..218 | 7 | 972..1094 |
| 2 | 242..364 | 8 | 1118..1240 |
| 3 | 388..510 | 9 | 1264..1386 |
| 4 | 534..656 | 10 | 1410..1532 |
| 5 | 680..802 | 11 | 1556..1678 |
| 6 | 826..948 | 12 | 1702..1824 |

- Halves: cols 1-6 = 96..948, cols 7-12 = 972..1824 (centre gutter 948..972).
- The decision split (shots 5 to 8): left cols 1-7 = 96..1094, right cols 8-12 = 1118..1824,
  divider at x 1106 (1 px, ink at 12 percent), y 200..848.
- Vertical bands, every card:

| Band | y range | Holds |
|---|---|---|
| rail | 0..3 | the chapter progress rail (section 10) |
| top band | 62..102 | kicker (left), honesty pill (right) |
| title band | 104..170 | the shot title, Title 56 |
| content | 200..848 | everything the shot is about |
| bottom band | 860..920 | lower-third (left), badge (right) |
| caption zone | 940..1040 | nothing essential, ever |

- Baseline rhythm: 8 px. Every y coordinate in the storyboard is a multiple of 4; text boxes
  snap to the 8 px rhythm where the font allows.
- Sketch convention in the storyboard: 64 columns by 18 rows including the border; one inner
  character is about 31 x 67 px.

## 2. Type

Faces available: Helvetica Neue Regular (ttc index 0), Bold (1), Medium (10), Medium Italic
(11); Menlo Regular (0), Menlo Bold (1). Sizes are px; line heights are px; tracking is a
percentage of the em.

| Style | Face | Size / line | Tracking | Use |
|---|---|---|---|---|
| Display | HN Bold | 96 / 104 | -2.0 | the hook title, the counters on shot 11 |
| Display-M | HN Bold | 72 / 80 | -1.5 | the safety line on shot 10 |
| Title | HN Bold | 56 / 64 | -1.5 | every card title, the safety line on shot 14 |
| Title-S | HN Bold | 48 / 56 | -1.0 | "Here is why.", "583 ms" |
| Heading | HN Medium | 40 / 48 | -1.0 | the headline on shot 9, the quote (Medium Italic 44) |
| Label-L | HN Medium | 36 / 44 | -0.5 | callout labels (shot 3), the closing caption (shot 8) |
| Body | HN Regular | 32 / 42 | 0 | card body: cases, key lines, step labels |
| Body-S | HN Regular | 28 / 36 | 0 | questions, consequences, footers, the author line |
| Body-XS | HN Regular | 26 / 34 | 0 | captions under numbers, the row-7 note |
| Lower-third | HN Medium | 32 / 40 | 0 | the section name, bottom-left |
| Caption | HN Medium | 22 / 28 | +2 | small headers on cards ("Request 1: the words") |
| Mono | Menlo | 28 / 44 | 0 | request JSON (shot 7), code (shot 12 editor: 26 / 38) |
| Mono-term | Menlo | 24 / 32 | 0 | the terminal on shot 8 (18 lines fit the panel with no scroll) |
| Mono-S | Menlo | 22 / 30 | 0 | option sets, the pattern-demo rows, the badge, the URL bar |
| Mono-XS | Menlo | 20 / 26 | 0 | gutters, line numbers, panel header text, the `0.35` / `0.65` values on the scale |
| badge-docked | Menlo | 20 / 26 | 0 | the Agent / Judge badge when docked in a panel's tab strip (shot 12 only) |
| Kicker | Menlo | 22 / 28, all caps | +8 | the chapter line above the title |
| Pill | Menlo | 22 / 28, all caps | +6 | honesty labels |
| Chip | Menlo Bold | 24 / 28, all caps | +4 | verdict chips |
| URL | Menlo | 32 / 40 | 0 | the repo URL on shot 14 (support under the safety line, not a second headline) |

Character widths for layout: Menlo 28 = 16.85 px, 26 = 15.65, 24 = 14.45, 22 = 13.25, 20 =
12.05 per character. Helvetica Neue Bold at 56 averages about 30 px per character on these
titles; Regular 32 about 15 px; Regular 28 about 13.3 px.

Rules: no text under 20 px. No orange text under 22 px. Titles never wrap. Body wraps at the
column width, never past it. Numbers that are spoken are never smaller than the text that
explains them.

## 3. Colour tokens

| Token | Value | Use |
|---|---|---|
| bg | `#0b0b10` | the canvas, every card |
| surface | `#13131a` | elevated panels: terminal, editor, step panel, the withheld frame |
| surface-2 | `#1a1a23` | panel header strips, the active tab, the active tree row |
| border | ink at 12 percent | the 1 px line around every panel and pill |
| ink | `#f2f2f7` | titles, body, numbers, code |
| ink-dim | `#a0a0ad` | secondary text, headers, captions, inactive step labels |
| ink-mute | `#6b6b78` | gutters, line numbers, the rail track, hatch lines |
| orange (accent) | `#ff6b3d` | the one accent: the thing the voice is naming right now |
| cyan | `#3ddcff` | structure and evidence: focus frames on portal UI, the CONFIRM chip, the URL, the "unsure" band |
| green | `#3fb950` | PROCEED, bars past the YES line, the "confident yes" zone, the Strands mark |
| amber | `#ffb347` | GUIDE, the over-budget bar, "unsure" values on the recorded run |
| red | `#ff4d4f` | DENY, the LED bloom, the DENY-word focus frame, the "confident no" zone |
| violet | `#7c5cff` | not used in v2 (the mark carries its own colours) |

Usage rules:

1. Orange goes only on the element the voice is naming at that moment: the current step
   label, the current callout, the kicker, the accent bar of the lower-third, the leader to the
   Decider, the `args_grounded` row, the `interventions=[...]` underline. When the voice moves
   on, the element recolours to ink or ink-dim over 240 ms. Two orange elements at once is a
   bug, with one exception: chrome (kicker, lower-third bar) plus one content element. On the
   terminal (shot 8) the step label is the one orange; the terminal's underlines never are.
2. Cyan is for "look here" on the portal UI (shots 2, 10), for the CONFIRM verdict, for the
   between band and values inside it (0.404), for evidence (the argument values `20
   centimetres.`, `0.2`, `"distance_m": 2`, `"distance_m 2 > 0.5"`, `"distance_m": 0.5`, the
   leader from "0.2" to the grounded bar, the OPERATOR line) and for the URL.
3. Verdict and zone colours appear only as verdict chips, verdict zones on the probability
   scale and the tinted bar tracks, bar colour after a threshold, values read against the
   scale (red for 0.18, cyan for 0.404), verdict words on the terminal (amber `"Guide"`, cyan
   `"Confirm"`), the focus frame on the UI's own DENY word, the deadman node's focus frame
   and trace end (red: the physical layer), and the LED bloom. The scale is one character from
   shot 5 through shot 8: a number is always read in the colour of the zone it falls in.
4. Everything else is ink, ink-dim or ink-mute on bg or surface.
5. Contrast on bg (measured in v1): orange 6.9:1, cyan 12.0:1, ink-dim 7.6:1, red 6.0:1,
   amber 11.5:1, green 7.7:1. ink-mute is for non-text or 20 px texture only.

## 4. Surfaces

- Panel: fill surface, radius 12, 1 px border, inner shadow (top edge 1 px ink at 6 percent,
  bottom edge 1 px black at 40 percent), drop shadow blur 40 alpha 0.5 offset (0, 12). Used for
  the hook window (shots 1, 2), the feed crop (1b-feed), the terminal (8), the editor and the
  terminal (12), the step panel (4), the withheld frame (9).
- Panel header strip: 36 px, fill surface-2, three 10 px dots at x +20, +36, +52 (ink at 20
  percent, no traffic-light colours), optional Mono-XS title centred.
- Pill: fill surface at 85 percent (100 percent over footage), 1 px border, radius 20, padding
  9 px vertical 18 px horizontal, height 40. Honesty labels and the badge use it.
- Plate (over footage or a screenshot only): bg at 72 percent, radius 8, padding 16 px. The
  lower-third and the quote card use it. On bg the plate is invisible (alpha 0) and the text sits
  at the same coordinates.
- Rule: real footage is full-bleed; screens, simulations and figures live inside a panel.
  The viewer learns the honesty labels from the geometry before reading them. Exception: shot
  10, where the Pit Wall screenshot is the product's own screen at native 1920x1080 and its
  chrome is part of the message; it stays full-bleed and its pointer coordinates stay 1:1.

## 5. Light: glow, bloom, vignette, grain, spotlight

- Glow is allowed on exactly two things: verdict chips and the LED. Chip glow: outer blur
  radius 18, alpha 0.45 on entrance settling to 0.20 over 480 ms, colour = the chip colour.
  LED bloom (shot 1): radius 24, alpha 0.60 to 0.15, two pulses of 300 ms. Nothing else blooms:
  no glow on titles, numbers, leaders, the mark or the URL.
- Vignette: constant on every shot including cards. Radial, zero inside r = 0.60 of the
  half-diagonal, 18 percent black at the corners, applied before text and chrome.
- Grain: constant, monochrome, gaussian sigma 3 levels (8-bit), regenerated each frame, full
  frame, applied after everything else and before encoding. It is not visible as texture; it
  keeps the dark gradients from banding and makes the dissolves look like film, not UI.
- Spotlight mask: everything outside a named region dims to 40 percent over 480 ms (element
  curve); the region is a rounded rectangle or an ellipse with a 48 px feather. It replaces
  arrows: the voice names a thing, the rest of the frame recedes. The mask lifts over 480 ms when
  the next region is named or at the cut. Where a shot names several things in turn (shots 2
  and 10) the mask is a stack of single spotlights, each with its own 480 ms fade in; the
  viewer sees their union. This multi-region form is new to the renderer.
- Background depth on cards: bg with the vignette only. No gradients, no shapes, no blobs.

## 6. Depth and camera

- Parallax stills (shots 3, 13a, 13b, 14): two layers. The subject layer drifts up to 8 px
  over the shot; the fill layer (blur fill or backdrop) drifts 4 px the opposite way. Drift
  follows the drift curve (section 7) over the whole shot length, never linear.
- Push-in: scale 1.00 to 1.03 (footage holds, shot 1 freeze) or 1.00 to 1.04 (shot 3, 14) over
  the shot or the hold, drift curve, about the frame centre unless a centre is given.
- Guided zoom (shot 4): keyframed views [cx, cy, scale]; every move takes 720 ms on the camera
  curve. The figure is a 3840-wide vector render so text stays sharp at 3.0x.
- Anchored overlays (leaders, dots, focus frames) are expressed in the layer's coordinates and
  transform with the camera, so a leader never detaches from its dot.

## 7. Motion language

Curves (named, with cubic-bezier values):

| Name | cubic-bezier | Use |
|---|---|---|
| enter | (0.16, 1.00, 0.30, 1.00) | every entrance: fade plus 16 px travel |
| exit | (0.70, 0.00, 0.84, 0.00) | every exit: fade plus 8 px travel |
| move | (0.65, 0.00, 0.35, 1.00) | repositions, recolours, the step panel growing |
| camera | (0.76, 0.00, 0.24, 1.00) | zooms, pushes, push-left transitions |
| draw | (0.22, 1.00, 0.36, 1.00) | underlines, leaders, focus frames, the rail, bars |
| count | (0.16, 1.00, 0.30, 1.00) | counters (same as enter) |
| drift | (0.37, 0.00, 0.63, 1.00) | parallax drift and slow push-ins across a whole shot |

Durations: micro 240 ms (underline, recolour, exit), element 480 ms (any element entering,
chips, focus frames, spotlight), camera 720 ms (zoom moves, push-left, the rail drawing on).
Stagger: 60 ms between siblings that enter on the same anchor (the three number badges on
shot 4, the Harness and Box callouts, the close stack's tag pair).

Rules:

1. No linear motion anywhere. Every tween names a curve.
2. No element appears without an eased entrance: fade 0 to 1 plus 16 px travel (up for
   titles and stacks, from the left for rows, from the right for right-column answers), or scale
   0.92 to 1.00 for chips and badges. Chrome that must be present on frame 0 (honesty pill,
   lower-third on a cut) enters with the transition that brings the shot in; it is part of the
   incoming frame, and the transition is its entrance. On push shots (3, 9, 12) the title is
   chrome too: it rides the incoming plate with the kicker and never gets a second entrance,
   so no element ever runs two curves in two directions at once. Shot 5 keeps its title on s1
   because the sentence starts 0.35 s after the push ends.
3. No cut without a defined transition (section 8).
4. Entrances are keyed to the sentence anchor they belong to (`s<N>`, `s<N>%<p>`,
   `s<N>+<d>` resolved from the measured Polly onsets). An element never lands more than 240 ms
   before its words and never more than 480 ms after them.
5. Exits are 240 ms. Elements that are still relevant hold to the cut; they do not exit early
   to make room.
6. Recolour (orange to ink-dim as the voice moves on) takes 240 ms on the move curve.
7. Nothing bounces, overshoots, spins, blurs in, or types letter by letter except the two
   terminals, which are real terminals.

## 8. Transition vocabulary

| Transition | Length | Where |
|---|---|---|
| hard cut | 0 | default; on the beat, between shots inside one chapter |
| cross-dissolve | 12 frames (400 ms) | between the two Mumbai stills; into the close card |
| push-left | 720 ms, camera curve | chapter changes: 2 to 3, 4 to 5, 8 to 9, 11 to 12 |
| dip to black | 720 ms | only at the end: the last 0.72 s of shot 14 |

Transitions never change the timeline. A push-left or a dissolve runs inside the incoming
shot's first 720 or 400 ms: the outgoing shot's final frame is held as a frozen plate and
pushed out (or faded) while the incoming shot plays from its own frame 0. Shot durations and VO
offsets stay exactly as measured. The first word of a chapter may land during the final 40
percent of a push; that is intended: the voice leads, the picture resolves under it.

Inside a chapter the chrome persists across the cut: the rail, the kicker position, the pill
and the lower-third slot do not re-enter; only the content cuts. Inside the decision chapter
(5 to 8) the divider, the kicker slot and the bottom band hold on every cut so the eye never
hunts.

## 9. Chrome: kicker, title, lower-third, honesty pill, badge

- Kicker: Menlo 22 caps, +8 tracking, orange, at (96, 72). Text: the chapter and its position,
  e.g. `THE DECISION  .  2 OF 4` (two spaces, a period, two spaces). Enters with the title's
  push or 240 ms before the title.
- Title: Title 56 Bold ink at (96, 104). Enters on its sentence anchor with fade plus 16 px
  rise, 480 ms. Never wraps; never shares the band with anything.
- Lower-third (one design everywhere): bottom-left. Accent bar 3 px orange at x 96, y 872..908.
  Text Lower-third 32 ink at (116, 878). Over footage or a screenshot: plate from x 80 to the
  text end plus 24, y 860..920. On bg: no plate, same coordinates. Enters with the shot's
  transition or on its anchor with fade plus 16 px from the left; the bar draws on top to bottom
  over 240 ms first, the text follows at +60 ms.
- Honesty pill: top-right, right edge x 1824, y 62..102, Pill type ink-dim on a pill. Two
  labels stack: y 62..102 and 110..150. Present from frame 0 of its shot. It never moves, except
  on shot 10, where the top-right is the Pit Wall's own status chips; there it sits bottom-right
  at y 860..900 on an opaque pill.
- Badge (Agent / Judge): bottom-right, two lines right-aligned to x 1824, Mono-S 22 ink-dim at
  y 866 and 896: `Agent: Amazon Nova Pro on Bedrock` / `Judge: Strands Decider 2B, local`. On a
  figure or footage it sits on a plate. Hidden on fake-stack frames (1, 2, 10) and on the car (1b,
  13), as before. On shot 12 it docks in the editor's tab strip (the bottom band is a terminal).
- Honesty labels are legible, consistent and never shouting: Menlo 22 caps on the pill, never
  larger, never coloured, never animated beyond the entrance. Their wording is unchanged from
  v1.

## 10. Progress rail

A 3 px rail at the top edge (y 0..3, x 0..1920) with five chapter segments separated by 6 px
gaps; it is the only element outside the title-safe margin and it is not text.

| Chapter | Shots | Time | Segment x |
|---|---|---|---|
| 1 This car can refuse an order | 1, 1b, 2 | 0.00..13.50 | 0..144 |
| 2 Driven as a Strands robot | 3, 4 | 13.50..35.20 | 150..382 |
| 3 The decision | 5, 6, 7, 8 | 35.20..123.73 | 388..1335 |
| 4 The proof | 9, 10, 11 | 123.73..156.07 | 1341..1687 |
| 5 The pattern | 12, 13, 14 | 156.07..177.27 | 1693..1920 |

Track: ink-mute at 35 percent. Fill: ink-dim, advancing with the timeline inside the current
segment; completed segments stay filled. Head: the leading 16 px of the fill is orange. Draw-on:
the full-width track draws on from x 0 over 720 ms (draw curve) when the hook title lands
(shot 1, +1.06); the fill and the head follow the global time from then on (at the end of the
draw the fill is already at about x 19). At the end the rail is full from 7.04 of shot 14,
holds full for 240 ms, and the dip to black takes it with the frame. The fill position is
computed from the global time, so it is correct across every transition.

## 11. Cues (replacing arrows, circles and boxes)

- Underline: 2 px in the cue colour, 6 px below the text's baseline, drawing on left to right
  over 240 ms (draw curve). The matched text recolours to the cue colour at the same time. Used
  on code, JSON and terminal spans.
- Leader with a dot: 1.5 px line at 70 percent alpha, drawing on over 360 ms. On the car
  (shot 3) the dot fills first and the leader draws from the dot outward to the label: the car
  points out its parts. On shot 7 it draws from the evidence span to a dot at the bar. The ping
  (a ring r 5 to 14, alpha 0.6 to 0, 480 ms) is spent only on a part the voice names: the
  Decider's dot on shot 3, the evidence dot on shot 7. Unnamed parts arrive settled at 70
  percent without a ping. A polyline leader with no head is allowed for a path (the command
  trace on shot 4's pull-back), with a colour change on its last segment.
- Focus frame: a 2 px rounded rectangle (radius 8) drawing on clockwise from the top-left
  corner over 480 ms, with the spotlight mask dimming the outside to 40 percent. Cyan
  everywhere, with two red exceptions: the UI's own DENY word (shots 2, 10) keeps its verdict
  colour, and the on-car deadman node (shot 4) is the physical layer. Never orange.
- Spotlight alone: for a region with no hard edge (the stick figure).
- Number badge: a disc r 18 ink with the digit in bg colour (HN Medium 22), scale 0.6 to 1.0
  over 240 ms, placed at the group box's top-left plus (24, 24) and never outside the safe
  margin. Used on shot 4 only. Badges are not orange: the step row is the shot's one accent.
- Accent bar: 2 px on content rows (the question rows, the case rows), 3 px on chrome (the
  lower-third, the closing caption on shot 8, the quote card on shot 10). Nothing at 4 px.
- Never: arrows, hand-drawn circles, filled highlight boxes, blinking, pulsing more than the
  LED's two pulses, tint lifts on the scale (the chip bloom marks a row; the scale holds).

## 12. Verdict chips

- Shape: pill, radius 6, height 40, padding 8 px vertical 14 px horizontal, text Chip (Menlo
  Bold 24 caps, +4) in bg colour on a solid fill.
- Colours: DENY red, GUIDE amber, CONFIRM cyan, PROCEED green.
- Glow per section 5. Entrance: scale 0.92 to 1.00 plus fade, 480 ms, enter curve; the glow
  blooms to 0.45 on the first frame and settles to 0.20 by the end of the entrance.
- Chips are the only element allowed a glow on a card, so a chip is always the brightest thing
  in its row.
- On the portal screenshots the UI's own DENY word is not a chip; it gets a red focus frame.

## 13. Counters, bars and scales

- Counter: counts from 0 to the value over 600 ms on the count curve and stops on the exact
  value. While counting, the digits render at 55 percent opacity and snap to 100 percent on the
  final frame, so a paused intermediate frame reads as transitional, not as a fact. Numbers are
  right-aligned inside a fixed box so proportional digits do not jitter the layout. Units sit on
  the baseline in Body 32 ink-dim after a 12 px gap. A value of zero does not count (0 to 0 is
  a non-event): the digit lands as a plain entrance and its bar's zero tick draws on.
- Bar: a track (ink at 8 percent, 12 px tall on shot 11, 28 px on shot 7, radius 4) and a fill
  that grows from zero over 600 ms on the draw curve. The fill colour switches on the frame the
  fill crosses a threshold (ink-dim to green at the YES line on shot 7). Zero-length bars draw a
  2 px tick at x 0 so "zero" is visible.
- Threshold line: a 1 px dotted vertical (dash 4, gap 4) in the threshold's colour with the
  value in Mono-XS above it.
- Probability scale (shots 5 to 8): a 4 px rule, 0.0 at the left and 1.0 at the right in
  Mono-S ink-dim above the rule; the threshold values `0.35` and `0.65` in Mono-XS in the zone
  colour centred on their ticks; zones recolour the rule segment and label themselves under it.
  The scale is one character through the chapter: met on shot 5, thresholds read on shot 6,
  the same three zones tinting the bar tracks on shot 7 (red, cyan, green at 10 percent), and
  the values on shot 8 coloured by the zone they fall in.

## 14. Terminal and editor

- Terminal: a panel with a header strip (three dots, optional Mono-XS title). Text Mono-term
  24 / 32 at x panel + 24, first line at header + 28. A block cursor 13 x 26 ink blinks at 530 ms on, 530
  off; it sits after the last typed character and hides while a machine row prints.
- Typing rhythm, three classes: human (typed input lines, 24 characters per second, a 120 ms
  pause before the first character), machine (JSON and log rows, 80 cps, no cursor), burst
  (`make pattern-demo` stdout, 560 cps). Line pause 50 ms between machine rows.
- Scroll: when a terminal fills, the content scrolls up by whole lines over 360 ms (move
  curve). Scrolling never happens while a highlighted line is being spoken.
- Editor (shot 12): sidebar (file tree, Mono-S, active row on surface-2), tab strip (36 px,
  active tab on surface-2 with a 2 px orange top edge), gutter with line numbers in ink-mute,
  code Mono 26 / 38, status bar 40 px with the path in cyan. Syntax colour is restrained:
  identifiers ink, strings ink-dim, punctuation ink-dim; the cues are the underlines.

## 15. Caption-safe zone

YouTube draws captions at about y 940..1040. Nothing essential sits there: no text, no
pointer, no number, no chip. The bottom band ends at y 920; the terminal on shot 12 ends at
932 and its last wrapped line is non-essential (the deny row's error tail). Full-bleed footage
and the cover may extend into the zone; the rail is at the top.

## 16. Do not

- Do not put two orange elements of content on screen at once.
- Do not draw an arrow, a freehand circle or a filled highlight box.
- Do not glow anything but a verdict chip or the LED.
- Do not animate linearly, and do not let any element pop in without a curve.
- Do not cut into a bare frame: chrome is on frame 0 of every card.
- Do not let text touch a panel edge: 24 px inside every panel, 16 px inside every plate.
- Do not place anything essential at y 940..1040.
- Do not invent a number, a marker position on a scale, or a filename. Markers appear only
  where a measured value exists.
- Do not show the Judge badge on a fake-stack frame or on the car.
- Do not use the music bed, a sound effect or room tone.
- Do not scale UI recordings above 1.6x or sharpen the phase-3 feed.
- Do not let a title wrap, a pill grow past one line, or the honesty label change wording.
- Do not use violet, gradients, drop shadows on text, or outlines on type.
- Do not let a counter show an intermediate value at full opacity, or count to zero.
- Do not give a title a second entrance on a push shot, or colour a number badge orange.
- Do not place a middle dot or any non-ASCII character in these documents; the renderer may
  substitute U+00B7 for the kicker's `.` separator at draw time.

## 17. Token sheet for the renderer

```yaml
canvas: {w: 1920, h: 1080, fps: 30, safe_x: 96, safe_y: 72, caption_zone: [940, 1040]}
grid: {cols: 12, col_w: 122, gutter: 24, left: 96, right: 1824}
bands: {top: [62, 102], title: [104, 170], content: [200, 848], bottom: [860, 920]}
decision_split: {left: [96, 1094], right: [1118, 1824], divider_x: 1106}
color:
  bg: "#0b0b10"
  surface: "#13131a"
  surface2: "#1a1a23"
  ink: "#f2f2f7"
  ink_dim: "#a0a0ad"
  ink_mute: "#6b6b78"
  orange: "#ff6b3d"
  cyan: "#3ddcff"
  green: "#3fb950"
  amber: "#ffb347"
  red: "#ff4d4f"
  border_alpha: 0.12
type:
  display: {face: sans_bold, size: 96, line: 104, track: -0.02}
  display_m: {face: sans_bold, size: 72, line: 80, track: -0.015}
  title: {face: sans_bold, size: 56, line: 64, track: -0.015}
  title_s: {face: sans_bold, size: 48, line: 56, track: -0.01}
  heading: {face: sans_medium, size: 40, line: 48, track: -0.01}
  label_l: {face: sans_medium, size: 36, line: 44, track: -0.005}
  body: {face: sans, size: 32, line: 42}
  body_s: {face: sans, size: 28, line: 36}
  body_xs: {face: sans, size: 26, line: 34}
  lower_third: {face: sans_medium, size: 32, line: 40}
  caption: {face: sans_medium, size: 22, line: 28, track: 0.02}
  mono: {face: mono, size: 28, line: 44}
  mono_code: {face: mono, size: 26, line: 38}
  mono_term: {face: mono, size: 24, line: 32}
  mono_s: {face: mono, size: 22, line: 30}
  mono_xs: {face: mono, size: 20, line: 26}
  kicker: {face: mono, size: 22, line: 28, caps: true, track: 0.08}
  pill: {face: mono, size: 22, line: 28, caps: true, track: 0.06}
  chip: {face: mono_bold, size: 24, line: 28, caps: true, track: 0.04}
  url: {face: mono, size: 32, line: 40}
  badge_docked: {face: mono, size: 20, line: 26}
ease:
  enter: [0.16, 1.00, 0.30, 1.00]
  exit: [0.70, 0.00, 0.84, 0.00]
  move: [0.65, 0.00, 0.35, 1.00]
  camera: [0.76, 0.00, 0.24, 1.00]
  draw: [0.22, 1.00, 0.36, 1.00]
  count: [0.16, 1.00, 0.30, 1.00]
  drift: [0.37, 0.00, 0.63, 1.00]
duration_ms: {micro: 240, element: 480, camera: 720, stagger: 60, count: 600, leader: 360}
travel_px: {enter: 16, exit: 8}
panel: {radius: 12, border_alpha: 0.12, shadow: {blur: 40, alpha: 0.5, dy: 12}, pad: 24}
pill: {radius: 20, pad_x: 18, pad_y: 9, height: 40, fill_alpha: 0.85}
plate: {alpha: 0.72, radius: 8, pad: 16}
chip: {radius: 6, height: 40, pad_x: 14, pad_y: 8, glow: {radius: 18, alpha_in: 0.45, alpha_hold: 0.20}}
led_bloom: {radius: 24, alpha_peak: 0.60, alpha_floor: 0.15, pulses: 2, period_ms: 300}
spotlight: {outside_alpha: 0.40, feather: 48, fade_ms: 480}
vignette: {inner: 0.60, corner_black: 0.18}
grain: {sigma: 3.0, mono: true}
parallax: {subject_px: 8, fill_px: 4}
rail: {y: [0, 3], gap: 6, track_alpha: 0.35, head_px: 16, draw_on_ms: 720, draw_on_at: 1.06, hold_full_ms: 240, segments: [[0, 144], [150, 382], [388, 1335], [1341, 1687], [1693, 1920]]}
badge_number: {r: 18, disc: ink, digit: bg, offset: [24, 24]}
accent_bar_px: {content: 2, chrome: 3}
focus_frame: {color: cyan, red_exceptions: [ui_deny_word, deadman_node]}
chapters_s: [[0.0, 13.5], [13.5, 35.2], [35.2, 123.73], [123.73, 156.07], [156.07, 177.27]]
cursor: {w: 13, h: 26, blink_ms: 530}
typing_cps: {human: 24, machine: 80, burst: 560, line_pause_ms: 50}
counter: {ms: 600, counting_alpha: 0.55}
bar: {ms: 600, track_alpha: 0.08, radius: 4}
transitions: {cut: 0, dissolve_frames: 12, push_ms: 720, end_dip_ms: 720}
```
