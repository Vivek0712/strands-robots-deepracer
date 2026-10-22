# v2 design review: DESIGN.md and STORYBOARD-v2.md

Reviewer role: motion design and art direction, pre-production. Inputs: `DESIGN.md`,
`STORYBOARD-v2.md`, `SCRIPT.md` (v3 VO, locked), `shots.yaml` (measured onsets), `ASSETS.md`,
the v1 frames in `build/frames/` and the v1 contact sheet. Text widths below were measured
with Pillow on the real faces (Helvetica Neue ttc 0/1/10/11, Menlo ttc 0/1) at the storyboard's
sizes and tracking. Nothing here touches the VO, the onsets, the shot order or the durations.

## Verdict

**Produce with fixes.** The system is real (grid, bands, one accent, named curves, a cue
vocabulary that replaces arrows) and most shots obey it. Six things stop it from going to a
top studio as written: shot 4 is one sentence behind the voice and never shows the deadman;
shot 8 breaks the one-orange rule on every clause; two text runs do not fit their boxes (shot
5 row 5 options, shot 12 sidebar); three chapter titles rise during the push that brings them
in; shot 6 sags to four events per ten seconds at the film's longest card; and the decision
chapter's probability scale changes geometry between shots 6 and 7 instead of travelling.
All are fixable inside the locked VO, timings and assets.

## Scores (1 to 5)

| Area | Score | One line |
|---|---|---|
| Coherence | 4 | The system holds; eleven violations listed, most small, two structural (shot 4 and shot 8 orange) |
| Hierarchy and legibility | 3 | Two overflows, three "more than 12 words at once" moments, two double focal points |
| Motion | 3 | Keyed to anchors throughout, but shot 4 is keyed to the wrong sentence and three titles fight the push |
| Rhythm | 3 | 10 to 12 events per 10 s in chapters 1 and 2, 4 to 5 through shot 6, five dead stretches over 3 s |
| Hook | 4 | DENY plus red LED at 0.4 s, title at 1.06 with weight; the title and the spotlight land on the same frame |
| Decision chapter | 4 | A judge can restate the decision; the scale should travel into 7 and 8 instead of being re-drawn |
| Honesty | 5 | Labels present, consistent, sim marked, phase-3 marked pre-decider, decider never the safety layer |
| Feasibility | 4 | Every element maps to a primitive; eight ambiguities for the engineer listed |
| Taste | 3 | Correct and restrained; the five moves a top film would add are below |

## Findings

Severity: HIGH blocks production as written; MED a judge or a trained eye would notice; LOW
polish. "Exact fix" stays inside the locked VO, onsets and durations.

| # | Sev | Shot | Finding | Exact fix |
|---|---|---|---|---|
| 1 | HIGH | 4 | The camera is one sentence behind the voice. Stop 3 (DeciderGate and Decider 2B at 3.0x) is keyed to s3 (6.75) whose words are "The on-car deadman needs none of it"; the deadman is never shown; step row 3 "Decider 2B judges, before the tool runs" lands at s3+0.6 under the deadman sentence; the pull-back at 10.9 plays in silence. The storyboard's "viewer understands … the on-car deadman is a separate physical layer" is not on screen. | Move the DeciderGate stop to s2%45 (about 4.5, "asks the decider"), focus frame and row 3 at s2%45+0.6. Add a fourth stop at s3 (6.75): the DeepRacer box's deadman node, view taken from the SVG (about [0.74, 0.62, 2.4]), red focus frame on the deadman sub-box at s3+0.6, step row 4 `4 On-car deadman: stops without the laptop` (panel grows to 660..848). Pull-back stays at 10.9 with four badges. This also removes the 3.4 s dead stretch (3.34 to 6.75). |
| 2 | HIGH | 8 | Two orange content elements on screen at once on every clause: the current step label (orange) and the terminal underline (`"distance_m": 2` orange at 4.2, `"distance_m 2 > 0.5"` at 6.55, `"distance_m": 0.5` at 12.24). DESIGN 3.1 calls this a bug and the storyboard's own `check` extension would fail it. Also inconsistent with shot 7, where the same request values were underlined cyan. | The step label is the one orange. Terminal underlines take the evidence and zone colours the viewer learned on shots 6 and 7: `"distance_m": 2`, `"distance_m 2 > 0.5"`, `"distance_m": 0.5` cyan (evidence); `0.18` red (0.35 or below, confident no, as the shot-6 scale painted it, not amber); `0.404` cyan (the band); `"Guide"` amber and `"Confirm"` cyan (verdict colours); the OPERATOR line cyan. Update DESIGN 3.1 ("the current row's underline on the terminal") to match. |
| 3 | HIGH | 5 | Row 5 options `clear   obstacle_near   person_in_frame   off_surface   unclear` at Mono-S 22 measures 819 px in a 674 px box (420..1094): it crosses the divider at 1106 by 133 px. At Mono-XS 20 it is 735 px, still over. The voice never says the options. | Cut both option-set rows (row 3 and row 5) and the two `choice` sub-labels; the names and questions are what the voice says. If the options must stay, wrap row 5 to two lines at y 788 and 818 (ends 848, touching the band edge) and accept 18 words landing at once. |
| 4 | HIGH | 12 | Sidebar row `  tool_call_intervention.py` at Mono-S 22 measures 351 px; the sidebar is 96..420 with text at x 120, so the row ends at 471, 51 px past the sidebar border and into the code area. | Sidebar 96..520, tab strip 520..1824 (tab 520..800), gutter 544..580 right-aligned to 576, code at x 600 (longest line 928 px ends at 1528). |
| 5 | MED | 3, 9, 12 | The title enters on its anchor (0.45, 0.36, 0.36) while the 720 ms push-left is still sliding the whole frame: the title rises 16 px on the enter curve inside a frame moving on the camera curve. Two curves on one element in two directions. | On push shots the title is part of the incoming plate (frame 0, no second entrance), as DESIGN 7.2 already allows for chrome; the kicker and the title arrive together. Shot 5 (s1 at 1.07) is fine as written. |
| 6 | MED | 6 | Rhythm trough. Events per 10 s drop to 4 to 5 across the film's longest card (27 s). Dead stretches while the voice continues: 2.9 to 6.47 (3.6 s, "a confident yes") and 6.7 to 10.17 (3.5 s, "a confident no"). Each zone cue lands as one event at the sentence onset. | Split each zone into two beats keyed to meaning: at s2 the tick turns green and `0.65` lands above it; at s2%60 ("a confident yes") the segment recolours and `or above: confident yes` enters. Same at s3 / s3%60 (red) and s4 / s4%50 (cyan). Six events instead of three, each on its words. |
| 7 | MED | 6 | The closing note's second line (Body-XS 26, line 34) at y 830 ends at 864: outside the content band (200..848), 2 px above the badge (866). Twenty words land at once at s9%62 (`The gate never fails open.` plus the two-line note). | Keep `The gate never fails open.` at (1118, 764). Move the note under the left column where rows end at 748: two lines at (120, 780) and (120, 814), width up to 974, entering 240 ms after the gate line. |
| 8 | MED | 5 to 8 | The probability scale is met on 5 and read on 6, then re-drawn on 7 as 360 px bar tracks with one green dotted `0.65`; the red and cyan zones vanish, and on 8 the values 0.18 and 0.404 are read against nothing. | Carry the zones onto shot 7's bar tracks: track tinted red 1370..1496, cyan 1496..1604, green 1604..1730 at 10 percent (0.35 at x 1496 is a measured threshold, allowed), the dotted `0.65` as written. On 8, colour the values by zone (finding 2) so 0.18 and 0.404 are read on the same scale. |
| 9 | MED | 4 | Three orange content elements at once at s3+0.6: orange step row, orange number badge, orange focus frame; on the pull-back three orange badges plus the orange row. DESIGN 11 defines the badge as orange, which sets up the conflict. | Number badges: disc ink, digit bg. All focus frames cyan. The step row is the only orange content on the shot. Edit DESIGN 11 accordingly. |
| 10 | MED | 4 | Number badges at (40, 90) and (48, 36) sit outside the title-safe margin (96, 72); badge 1 on the pull-back is 36 px from the top edge next to the rail. | Place badges at the group box's top-left plus (24, 24) inside the margin; on the pull-back `1` at (120, 96). |
| 11 | MED | 7 | Overloaded onset at s2 (4.60): `ANSWER` header, `0.65` label, dotted YES line, `args_grounded` label and the evidence leader all enter together, fill at 5.02, value at 5.62: six to seven events inside a second. | `ANSWER`, the `0.65` label and the dotted line enter at s1%80+0.3 (about 3.5, in the 1.4 s between "zero point two" and "Grounded"), a quiet setup beat. s2 is the label and the leader only. |
| 12 | MED | 9 | Dead stretch 2.85 to 6.44 (3.6 s) while the voice says "…denied in four hundred fifty six milliseconds"; the number is on screen from 0.36, three seconds before it is spoken. Title (5 words) and heading (11 words) land together at s1: 16 words at once. | Title rides in with the push (finding 5). Heading as a span reveal: `On the car: a person in frame was denied` at s1, `in 456 ms` at s1%78 (about 5.1), each fade plus 16 px. The withheld panel's 1 px outline is present from frame 0 (the hole reads as a frame, not a layout gap); hatch and `WITHHELD` fill it at s2. |
| 13 | MED | 12 | Six cues land on one frame at +7.5 (three verdict underlines, three reason recolours with 1 px underlines) in silence, after a 560 cps burst. | Verdict underlines in reading order with a 120 ms stagger (Proceed, Guide, Deny); drop the reason underlines, keep the ink-dim to ink recolour. |
| 14 | MED | 8 | Dead stretch 14.76 to 18.70 (3.9 s) while the voice says "inside the unsure band". | At s5%40 (about 16.1) a quiet ink underline (60 percent) on `"deterministic_check": "ok"` in line 6: the check passed, so the grounding alone is unsure. One event on its words. |
| 15 | MED | 13b | `event-hall.jpg` is held 2.0 s; ASSETS 2.3 flags it "approved for the article only, 1 s at most" (audience visible). Not a design fault but it reaches the screen. | Confirm the video approval in writing before the render, or shorten the hall still to 1.0 s and extend the speaker still to 3.0 s (the SCRIPT's own first cut). The two-still breath still works at 3 plus 1. |
| 16 | LOW | 1 | The title (1262 px, y 440..544) touches the lit DENY's region (280..440) and straddles the live-view and verdict panels; it lands on the same frame as the spotlight dim and the rail draw. The push-in under it starts at 0.7. | Title text box y 560..664 (over the dimmed floor, clear of the chips at 709): 120 px of air under DENY. Spotlight at 0.7 with the freeze, not 1.06, so the frame has resolved to DENY and LED before the voice; title and rail alone at 1.06. Bloom period 330 ms so the second pulse hands off to the title at 1.06. Consider a hard open instead of the 0.24 fade: the PROCEED to DENY flip is the story and the fade eats half of it. |
| 17 | LOW | 1b-feed | Concept says "in the same panel the sim just occupied"; the layout uses a different panel (564..1357 x 120..843, portrait crop). The prose is wrong, the layout is right. | Fix the concept line: "in a panel where the sim's panel was". |
| 18 | LOW | 9 | `Mono 34` is not in the type scale (Mono is 28, 26, 24, 22, 20; URL 44). Shot 11 headers use `Medium 28`, also undefined. Shot 12 docks the badge at Mono-XS 20; DESIGN 9 says the badge is Mono-S 22. | `person_in_frame   p = 0.9485` in Mono 28. Shot 11 headers in Lower-third 32 Medium or Body-S 28 Regular. Either add `badge-docked: Mono-XS 20` to the scale or dock at 22. |
| 19 | LOW | 8 | Node centre at y+14 against a Body 32 label whose box centre is y+21: nodes sit 7 px high. | Nodes at (1134, y+20). |
| 20 | LOW | 6 | DESIGN 11 forbids pulsing beyond the LED; shot 6 lifts the cyan band to a lighter tint for 480 ms and back at s7 and the green at s8 (a pulse). | Keep it if the team wants it (it ties the row to the zone) and write the exception into DESIGN 11, or drop it: the chip bloom already marks the row. |
| 21 | LOW | 6 | The sketch shows `0.35` and `0.65` above the ticks; the text never places them. | Place `0.35` and `0.65` Mono-XS 20 in the zone colour centred on the tick at y 232 (finding 6 uses them). |
| 22 | LOW | 5 | The skeleton draws the five names at their final positions at s1; each row's entrance then says the name "enters … from the left" again. | The skeleton name recolours ink-mute to ink over 240 ms on its row's anchor; only the bar and the question enter. |
| 23 | LOW | 6 | The divider is 200..848 on 5, 7 and 8 and 340..848 on 6; the scale travels across y 260 at 0.37 to 1.09; nothing says how the divider's top gets from 200 to 340. | "The divider's top retracts 200 to 340 over the same 720 ms on the move curve." |
| 24 | LOW | 5, 6, 7 | No lower-third on 5, 6, 7; lower-third plus badge on 8; title plus lower-third on 9 and 11. The bottom band "holds on every cut" but its content differs. | Decide once: cards with a kicker and a title carry no lower-third (drop `The numbers` on 11; keep `On the car, 2026-10-15` on 9 because it carries the date, or move the date into the pill, which already has it). 8 keeps it because it has no title. |
| 25 | LOW | 10 | The honesty pill at 860..900 bottom-right sits over the product's HOLD TO TALK button (the v1 frame shows the collision). | Put the opaque pill in the verdict card's empty stretch, right edge 1884, y 580..620; it reads as a sticker on the card, not as product UI. |
| 26 | LOW | 10 | Leftover editing note in the layer text: "plate `150..300, 1110..376` corrected to `150..1110, 300..376`". | Keep only `150..1110, 300..376`. |
| 27 | LOW | 11 | `31` at Display 96 measures 104 px; the fixed box's right edge at 1070 leaves 98 px from the column's left (972): the 3 starts 6 px into the gutter. | Right edge 1080, `of 72` at (1094, 572). |
| 28 | LOW | 12 | The terminal's last row ends at 924 inside a panel ending at 932: 8 px of bottom padding against the 24 px rule; the panel's bottom sits in the bottom band. | Terminal 588..920, rows from 640, Mono-S 22 / 28 gives nine full rows to 892; let the tenth (the deny row's error tail) be cut by the panel's edge with a 24 px fade, or wrap at 124 characters to drop a line. |
| 29 | LOW | 12 | Tab's 2 px orange top edge plus the orange `interventions=[MotionGate(decider)]` underline plus the kicker: two content oranges. | Active tab edge in ink at 60 percent. |
| 30 | LOW | 12 | Seven code lines enter as one block (about 20 tokens at once). | Line by line, 60 ms stagger (420 ms total), top to bottom. |
| 31 | LOW | 14 | The URL (Menlo 44 cyan, 1170 px) sits 28 px under the safety line (Title 56, 1134 px): two headlines of equal weight when the line lands at s2. | URL 32 cyan, author line Body-XS 26, tags Mono-S 22; the stack's spacing closes to 24 px. The safety line is the only headline. |
| 32 | LOW | 14 | The mark is named as `strands-mark.svg`; the renderer's `image` loads PNG, cairosvg is not installed (ASSETS 6). | Use `build/clips/svg-strands-mark.png` downscaled to the 96 px box, or re-render the SVG at 192 px with the Chrome recipe. |
| 33 | LOW | 10, all | The DESIGN says the rail "draws on from x 0 to the current position" at 1.06, which is 11 px. Unclear whether the track draws too. | "The full-width track draws on from x 0 over 720 ms; the fill and head follow the global time from then on." |
| 34 | LOW | 1, 2, 10 | The spotlight on shots 2 and 10 adds regions over time (figure, then chips, then DENY). The existing `SpotlightOverlay` is one region with moves; the primitive list names the multi-region behaviour but the engineer should know it is new. | Note "new" in the primitive table and give each added region its own 480 ms fade. |
| 35 | LOW | 3 | Harness and Box callouts enter at +7.40 and +7.46, after the sentence ends at 7.09, with the full leader-and-ping ceremony, though the voice never names them. | Enter them already settled: label at 70 percent, leader without the ping, 480 ms, as one staggered pair. The ping is spent only on named parts. |
| 36 | LOW | chrome | Accent bars come in 2 px (rows), 3 px (lower-third, shot 8 caption), 4 px (shot 10 quote). DESIGN 11 does not list the accent bar as a cue. | Add "Accent bar: 2 px on content rows, 3 px on chrome; nothing at 4 px". Quote card bar 3 px. |

## 1. Coherence

The grid is obeyed on every card; bands are respected except findings 7 (shot 6 note into the
bottom band), 10 (shot 4 badges outside the margin), 28 (shot 12 terminal into the bottom
band) and shot 8's terminal panel ending at 856 (8 px past the content band; harmless, the
lower-third starts at 860, but the panel's 40 px drop shadow falls over the lower-third bar).
Type scale: three undefined sizes (finding 18). One accent: violated on shots 4 and 8
(findings 2, 9) and borderline on 12 (finding 29); clean everywhere else. Chrome positions are
consistent (kicker at (96, 72), pill right edge 1824, badge right-aligned, lower-third at the
same coordinates) with the documented exception on shot 10. Caption-safe zone: clean; the only
things at y 940..1040 are full-bleed footage, the cover and the Pit Wall's own footer. Cue
vocabulary: leaders, underlines, focus frames, spotlight, badges as defined; the accent bar is
used on five shots without being defined (finding 36); shot 8's node ring (1 px, r 12) is new
and fine.

## 2. Hierarchy and legibility

Measured overflows (Pillow, real fonts): shot 5 row 5 options (819 in 674, HIGH), shot 12
sidebar row (351 in 276 to the border, HIGH), shot 11 `31` (104 in 98, LOW). Everything else
fits: the longest title is shot 11 at 1168 px; shot 1's Display 96 title is 1262 px; shot 10's
Display-M 72 safety line is 1460 px; shot 9's Heading 40 is 924 px; shot 7's request lines are
under 920 px; shot 8's terminal lines are under 742 px; shot 12's longest code line is 928 px.
Shot 5's two-line questions wrap as stated (864 and 902 px in 674).

Words landing at once above twelve: shot 5 row 2 (14) and row 5 (18, finding 3); shot 6 close
(20, finding 7); shot 9 s1 (16, finding 12); shot 12 code block (about 20, finding 30). Double
focal points: shot 1 title against the lit DENY (finding 16); shot 14 URL against the safety
line (finding 31); shot 4 pull-back with three orange badges and an orange row (finding 9).

Busiest frames by element count: shot 3 at 8.5 (7 labels, 7 leaders, title, lower-third,
badge, kicker: 18 elements, about 47 words, all settled by then); shot 5 at 17.5 (about 24
elements, about 115 words accumulated); shot 8 at 25.7 (18 terminal lines, 8 nodes, 8 labels,
caption, lower-third, pill, badge). These are accumulations, not landings, and the dim-to-70
settle on 3 and the orange-to-ink-dim recolour on 8 keep one focal point.

## 3. Motion

Entrances are keyed to anchors throughout; the storyboard resolves every anchor to a second so
it can be checked. Elements moving while the voice is not about them: shot 4 stop 3 and row 3
(finding 1, the one real miss); shot 3's Harness and Box (finding 35); shot 12's two code
underlines at s2%40 and s2%50 (the voice says "three lines of wiring, and make pattern demo";
acceptable as look-here cues). Transitions fighting onsets: the three push-shot titles
(finding 5); shot 6's scale travel and title on the same frame at s1 (the scale is the right
visual for "Two thresholds make the action", the title should be chrome on the cut). Stagger and
durations are consistent with the system; the storyboard names a curve everywhere.

## 4. Rhythm

Events per 10 s (an event is any entrance, exit, recolour, draw-on, camera move or cut):

| Window | 0 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 | 110 | 120 | 130 | 140 | 150 | 160 | 170 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Events | 11 | 10 | 12 | 9 | 7 | 5 | 4 | 4 | 12 | 9 | 8 | 8 | 6 | 10 | 7 | 7 | 10 | 4 |

The film front-loads motion (chapters 1 and 2), sags through shot 6 (the longest card, 4 to 5
per 10 s), spikes on shot 7, settles through 8, dips on 9 and rises again on 10 and 12.
Dead stretches over 3 s while the voice continues: shot 4 3.34 to 6.75 (finding 1); shot 6
2.9 to 6.47 and 6.7 to 10.17 (finding 6); shot 8 14.76 to 18.70 (finding 14); shot 9 2.85 to
6.44 (finding 12); shot 11 3.56 to 6.59 (3.0 s, borderline, left alone). Overloaded stretches
(more than four events in 2 s): shot 4 at s2+0.6 (five on one frame; a 60 ms stagger is called
for and should be written in); shot 7 at s2 (finding 11); shot 12 at +7.5 (finding 13); shot 1
at 1.06 (finding 16).

## 5. The hook

The first second delivers: PROCEED on the clear frame, the figure at 0.2, DENY and the red
LED with its two-pulse bloom at 0.4, freeze at 0.7, title at 1.06 on the first word with the
rail drawing on. The title has weight (Display 96, one line). Three things dilute it: the
0.24 s fade from black eats half of the PROCEED-to-DENY flip; the spotlight dim lands on the
same frame as the title; the title touches the DENY region and straddles two panels. The
strongest version within the constraints is finding 16: hard open on PROCEED, the flip at 0.4,
spotlight with the freeze at 0.7, title and rail alone at 1.06 with 120 px of air under DENY,
bloom timed to hand off to the title.

## 6. The decision chapter as one explanation

The shared layout holds: split at 1106 on 5, 7 and 8; the scale band on 6 above the same
split; kicker slot and bottom band constant. The scale travels cleanly from 5 to 6 (labels
ride, geometry identical). It does not travel into 7, where it is re-drawn as 360 px bar tracks
with only the 0.65 line, and on 8 the values float (finding 8). Verdict chips are consistent on
6 and 7; on 8 the verdicts are caps words in step labels and underlined terminal tokens, not
chips. A judge comes out able to restate the decision: five typed questions, each a
probability; 0.65 and 0.35 make three zones; person means Deny, invented distance Guide,
unsure Confirm, otherwise Proceed, missing decider Deny; a real request scored 0.91, 0.95, 0.96
and got Proceed in 583 ms; "Go." was guessed at 2 m, caught by arithmetic, Guide; the 0.5 m
re-plan scored 0.40, Confirm, the operator said no. With findings 2 and 8 the chain reads on
one scale from 5 through 8. Optional: render the GUIDE and CONFIRM nodes on shot 8 as chips
(the chip geometry already exists) so the verdict vocabulary stays visual to the end.

## 7. Honesty

Every recorded, measured or simulated frame carries its pill; wording unchanged from v1;
pills never larger than Menlo 22, never coloured. The badge is hidden on the fake-stack frames
and on the car, shown where the judge is the real decider. Shot 1b marks the phase-3 planner
pre-decider on both parts. Shot 10's quote card is verbatim from `portal/backend/narrator.py`
(the narrator's fixed line for `person_in_frame`), so "the rover says why" is honest; the 92 ms
and 257 ms fake-stack numbers are never marked; the 0.97 is never spoken as a judgement. The
safety line sits on 2, 10 and 14 with the exact wording; the decider is never framed as the
stop. One open item: the hall photo's approval scope (finding 15). One caution for shot 12: the
tab-strip badge says `Judge: Strands Decider 2B, local` above a terminal that says fake decider;
the pill resolves it, and the badge describes the wiring, so it stands, but the engineer should
not let the badge drift down onto the terminal panel.

## 8. Feasibility

Every element maps to a primitive the renderer has (`anim`, `camera`, `panel`, `bar`,
`counter`, `chip`, `dotted`, `recolor`, `badge`, `cursor`, `SpotlightOverlay`, `RailOverlay`,
`BarOverlay`, bezier `ease` in `fx.py`, `push` in `fx.py`) or that the primitive table names.
Ambiguities to settle before the engineer starts: shot 4's Bedrock focus-frame bounds ("the
engineer takes the bounds from the SVG") and the badge positions outside the margin (findings
1, 10); shot 5's skeleton-versus-row entrance (finding 22); shot 6's divider retraction and the
unplaced `0.35`/`0.65` labels (findings 21, 23); shot 9's `Mono 34` (finding 18); shot 10's
leftover coordinates (finding 26); shot 14's SVG (finding 32); the rail's draw-on (finding 33);
the multi-region spotlight (finding 34); the seven named curves are not yet in `fx.py`'s
`EASES` (the table lists `ease(name, t)` as new, correct). Shot 8's terminal schedule was
checked against the onsets: with 80 cps machine rows and 24 cps human rows the OPERATOR line
starts about 21.2 and ends about 23.1 against s7 at 23.11; the reply ends about 25.7 inside the
26.5 s shot. It is tight but it holds; do not let the human rate drop below 24 cps.

## 9. Taste: five things a top-tier film would do here

1. Make the scale a character. One geometry from 5 through 8: the zones tint the tracks on 7
   and colour the values on 8 (findings 2, 8). The judge then sees every number land on the
   ruler they were taught, which is the whole argument of the chapter.
2. Let the car point out its parts. On shot 3 draw the leaders from the dot outward to the
   label (the car is the source), and let only the Decider's dot ping: one accent, one ping.
   Harness and Box arrive settled (finding 35).
3. Choreograph the hook as three beats, not one (finding 16): verdict at 0.4, freeze and
   spotlight at 0.7, title and rail at 1.06, with the bloom's second pulse timed to hand off to
   the title. Then nothing moves but the 3 percent push until the cut.
4. Fix shot 4's pull-back so the figure explains itself in motion: instead of three static
   badges, one 2 px cyan trace draws on over 720 ms along the command's path (Bedrock to Strands
   Agents to DeciderGate to the car, a leader without an arrowhead, allowed by DESIGN 11), ending
   at the deadman node in red. The four step rows stay as the written record.
5. Give the close a single headline. The safety line is the sentence the film wants remembered;
   the URL, author and tags are support (finding 31). Hold the two spans alone for their two
   sentences, with the rail completing under them, and let the dip to black take the frame with
   the rail still full for the last 240 ms before it fades.

Two smaller touches: the kicker's separator should be a middle dot (`THE DECISION · 2 OF 4`;
Menlo has U+00B7) rather than a period with two spaces; and shot 11's `0 of 72` should not
count (a counter from 0 to 0 is a non-event): land the `0` on the cut of its anchor and let the
2 px green tick draw on, which is the fact.
