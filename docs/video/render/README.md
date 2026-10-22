# docs/video/render: shot-list video renderer

Deterministic renderer for the 3-minute hackathon demo. A writer edits one YAML (or JSON)
shot list and re-renders with one command; the output is a 1920x1080, 30 fps H.264 MP4 with
Amazon Polly voice-over, transitions, an `.srt` caption sidecar and -16 LUFS loudness.

Everything is drawn in a 1920x1080 reference space. `--draft` renders the same list at 960x540,
15 fps with the macOS `say` voice (no Polly) for fast iteration; the numbers in the shot list
do not change between draft and final. Version 3 (`RENDER_VERSION = "3"`) adds the motion
layer: named easing curves, entrances and exits, draw-on strokes, spotlight, glow, vignette
and grain, parallax stills, eased push and whip transitions, a richer terminal, data
elements, a code panel and camera holds. A shot list that uses none of the new keys renders
exactly as it did under version 2 (verified frame by frame on `docs/video/shots.yaml`; the one
difference is a bug fix: a `counter` whose number is longer than its template, like
`{n} USD` with `0.13`, no longer loses its last letters).
Version 4 (`RENDER_VERSION = "4"`) adds the production-design layer used by
`docs/video/shots-v2.yaml`: the seven named curves of `DESIGN.md`, transitions that run inside
the incoming shot, a global progress rail, stacked spotlights, span reveals, letter-spacing, eased
recolours and position tweens, the v2 panel (shadow, border, header, hatch, hollow), the terminal
typing classes, pointer kinds `path` and `node`, dot-first leaders with a ping, a subject push-in
and parallax drift with attached pointers, and two `check` rules. `docs/video/shots.yaml` still
renders identically (verified against the v1 film, mean difference under 2/255).

## Usage

```sh
# validate schema, assets, timing, words per minute, text fit (no rendering)
.venv/bin/python -m docs.video.render check docs/video/shots.yaml

# synthesise every VO line with Polly (cached) and print durations
.venv/bin/python -m docs.video.render vo docs/video/shots.yaml

# fast draft: 960x540, 15 fps, macOS `say`
.venv/bin/python -m docs.video.render build docs/video/shots.yaml --out docs/video/draft.mp4 --draft

# final: 1920x1080, 30 fps, Polly Matthew (generative), libx264 crf 18, AAC 192k
.venv/bin/python -m docs.video.render build docs/video/shots.yaml --out docs/video/demo.mp4

# contact sheet for review
.venv/bin/python -m docs.video.render frames docs/video/demo.mp4 --every 2 --sheet docs/video/build/sheet.png
```

Useful `build` flags: `--voice Joanna`, `--engine neural`, `--music bed.caf` (looped with a
2 s equal-power crossfade and ducked under the voice), `--music-lufs -30 --duck-lufs -38`
(absolute bed loudness; the voice is pre-normalised to -16 LUFS first) or `--music-level -14`
/ `--duck-level -22` (dB relative), `--burn-captions`, `--no-vo`, `--vo-rate 90`,
`--draft-vo polly`, `--fade-out 0.6`, `--force` (ignore the segment cache),
`--font-sans/--font-sans-bold/--font-mono` (`path[:ttc-index]`; defaults Helvetica Neue and
Menlo, falling back to Arial and DejaVu), `--text-engine auto|basic|raqm`, `--build-dir`
(segment cache; default `docs/video/build`), `--vo-cache` (default `docs/video/build/vo`),
`--profile heisenberg --region us-east-1` for Polly.

Run from the repo root so `docs.video.render` resolves and relative asset paths work.
PyYAML is optional: a `.json` shot list with the same structure always works.

## Pipeline

1. VO lines go to Polly (generative, then neural, then standard as fallbacks), cached by a
   hash of voice, engine and text under `build/vo/polly/`. Draft uses `say` (`build/vo/say/`).
   With `vo_sentences: true` each sentence is a separate Polly call, stitched with
   `vo_gap_ms` of real silence; the sentence onsets are measured from the audio.
2. `duration: auto` shots take `vo_offset + VO length + auto_pad` (0.4 s), floored by `min`.
3. Each shot renders to its own MP4 segment in `build/segments/<id>-<hash>.mp4`; unchanged shots
   are reused. Clips and stills come through ffmpeg (scale/pad or crop, no stretching); cards,
   terminals, tables, JSON, code, text and pointers are drawn with Pillow and composited in
   Python. The post pass (vignette, grain) runs on every composed frame before encode.
4. Segments join with `xfade` (fade, dip_to_black, dissolve, wipes) or a straight cut; the
   eased `push_left`, `push_right` and `whip` transitions are rendered in Python from the
   overlap of the two segments and spliced in. Letterbox bars and the global fade-in are
   applied to the joined video.
5. The voice, un-muted clip audio and optional music are mixed in numpy, music is ducked
   with a smoothed envelope, then two-pass `loudnorm` to -16 LUFS, AAC 192k, `+faststart`.
6. `<out>.srt` is written from the VO text; `--burn-captions` also draws the same cues.

## Shot list

Top level is either a list of shots or a mapping:

```yaml
title: "This car can refuse an order"
voice: Matthew           # optional defaults, CLI flags win
engine: generative
vo_sentences: true       # one Polly call per sentence; onsets measured for s<N> anchors
vo_gap_ms: 600           # silence stitched between sentences (vo_sentences)
vo_breaks: 400           # SSML <break> after each sentence instead (single-call synthesis)
vo_rate: 92              # SSML prosody rate in percent (neural honours it; generative ignores it)
min_gap: 0.55            # build fails when a stitched sentence boundary carries less silence
music: docs/video/raw/bed.mp3
music_lufs: -30
duck_lufs: -38
fade_out: 0.6
fade_in: 0.0             # global fade from black (the first shot's `transition: fade` also works)
auto_pad: 0.4
base_dir: .              # asset paths resolve against this
ease: ease_out           # v3: default curve for every element (see Easing); unset = legacy
vignette: 0.35           # v3 post pass, 0..1 edge darkening
grain: 0.03              # v3 post pass, luminance grain (fraction of full scale, seeded)
grain_seed: 7
grain_size: 2            # px per grain clump; 1 is per-pixel noise (costly to encode)
grain_cap: 16            # Mbit/s cap on the final file at 1080p while grain is on (0 = none)
letterbox: 0             # 0 = no bars; 2.39 = bars to that aspect; > 20 = bar height in px
text_engine: auto        # raqm when Pillow has libraqm (kerning, ligatures), else basic
defaults:                # applied to every shot
  transition: {kind: fade, duration: 0.5}
snippets: {...}          # any extra top-level key is ignored (YAML anchors live here)
shots: [...]
```

Common keys on every shot:

| key | meaning |
|---|---|
| `id` | unique name, used for the segment cache and captions |
| `kind` | `clip`, `still`, `card`, `terminal`, `table`, `json`, `code`, `split` |
| `duration` | seconds, or `auto` (needs `vo`); `min` is the floor for `auto` |
| `black_in` / `black_out` | seconds of dip from or to black inside the shot (no overlap) |
| `vo` | Polly text; SSML allowed when it starts with `<speak>` |
| `vo_offset` | seconds after the shot start before the voice begins (default 0) |
| `transition` | into this shot, see Transitions |
| `text` | list of overlays, see below |
| `pointers` | list of arrows, strokes, boxes, circles, underlines |

A transition of `d` seconds overlaps the two shots, so the timeline is shorter than the sum of
durations; `check` prints the real start of every shot.

### Time anchors

Any time inside a shot (`in`, `out`, `at`, `schedule`, camera `at`, spotlight `moves`, ...)
may be a string anchor on the VO's sentences: `"s3"` is the onset of sentence 3, `"s3%40"`
is 40 percent into it (word position), `"s3+0.4"` is 0.4 s after it, `"s3%40-0.2"` combines
both. With `vo_sentences: true` the onsets are measured from the synthesised audio; otherwise
(or before synthesis) they are estimated from the word count at 176 wpm, and `check` marks
them with `*`. `vo_offset` is added for you.

### Easing

Curves: `linear`, `ease_out` (cubic-bezier 0.16, 1, 0.3, 1), `ease_in_out` (0.65, 0, 0.35, 1),
`ease_in` (0.32, 0, 0.67, 0), `spring` (back-out, about 5 percent overshoot) and `smooth`
(the pre-v3 smoothstep). Any element, pointer, camera keyframe, zoom, table or transition
takes `ease: <name>`. The default is resolved as: the element's `ease`, else the top-level
`ease`, else `smooth` for the pre-v3 element kinds (fade, slide_up, slide_left, typewriter,
counter, arrow, box without `draw_ms`, numeric camera eases, `zoom: {ease: true}`) and
`ease_out` for everything new. Set `ease: ease_out` at the top level to move the whole film
on one curve; leave it unset to keep an old shot list identical. `pop` entrances use `spring`
unless told otherwise; spotlight moves and push transitions use `ease_in_out`.

### Palette and fonts

Colours follow `docs/video/STORYBOARD.md`: `bg #0b0b10`, `ink #f2f2f7`, `ink-dim #a0a0ad`, `orange
#ff6b3d`, `cyan #3ddcff`, `violet #7c5cff`, `green #3fb950`, `amber #ffb347`, `red #ff4d4f`
(`text` and `muted` are aliases of `ink` and `ink-dim`). Font kinds: `sans`, `sans_bold`,
`sans_medium`, `sans_medium_italic` (Helvetica Neue indices 0, 1, 10, 11), `mono`, `mono_bold`
(Menlo 0, 1). Text is laid out by Pillow's RAQM engine (kerning, ligatures) when the build has
libraqm, else the basic engine; `check` prints which. Safe margins are 96 x 72 px; `check`
measures every overlay at its rest position with the real font and fails when text leaves the
safe frame, its plate or its `max_x` (opt out of the frame rule with `safe: false`). Entrance
offsets do not count: an element is measured where it ends up.

### Text overlays

`{kind, text, pos, size, color, in, out, anim, anim_ms, out_anim, out_ms, ease, stagger, glow,
width, align, font}`

- `kind`: `title` (Bold 64), `subtitle`, `lower_third` (Medium 32 on a 56 px plate with a 2 px
  orange bar, default pos `[112, 964]`), `caption` (Medium 40), `label` (Regular 30), `mono`
  (Menlo 28), `code`, `counter` (Bold 96; `text: "{n} ms p50"` with `count: {from, to, over,
  decimals}` counts up, the rest of the line is drawn at `unit_size` in `unit_color`), `ticker`
  (see Data elements), `chip` (Menlo Bold 30 on a solid plate of colour `bg:`; `verdict:
  Proceed|Guide|Confirm|Deny` picks green/amber/cyan/red), `bullet`, plus the non-text kinds
  `chips` (`items`, `gap`, `pad`, `plate_color`, `plate_alpha`), `panel` (`box`, `color`,
  `alpha`, `radius`, `bar`), `image` (`src`, `box`, `glow: {color, radius, alpha}`, a soft
  ellipse behind the image), `spotlight`, `bar`, `rail` (see below).
- `pos`: `tl tc tr ml mc mr bl bc br` (inside the safe margins) or `[x, y]` in 1920x1080
  units; `anchor: tl|tc|tr|...` says which corner of the block `[x, y]` is (right-align a
  label with `anchor: tr`).
- `in` / `out`: seconds (or anchors) relative to the shot. Overlays hold until the cut unless
  `out` is set.
- `anim`: the entrance. Pre-v3: `fade` (default; `fade:` seconds, 0.4 when `in` > 0),
  `slide_up` (36 px), `slide_left` (24 px), `typewriter` (`cps`), `none`. v3: `rise` (fade plus
  24 px up), `scale_in` (0.96 to 1), `wipe` (left-to-right mask with an 8 px soft edge),
  `blur_in` (gaussian 8 px to 0), `pop` (0.8 to 1 on `spring`, for chips). `anim_ms` is the
  entrance length in milliseconds (default 400). `out_anim` is the exit, the entrance run
  backwards in time (a `rise` sinks, a `wipe` un-wipes); it defaults to the entrance for v3
  anims and to a fade otherwise, over `out_ms` (default 300) before `out`.
- `stagger: 60`: a multi-line block (bullets, label stacks, mono blocks) enters one line at a
  time, 60 ms apart; on `chips` one chip at a time. Separate entries stagger by hand
  (`in: "s2"`, `in: "s2+0.06"`, ...).
- `glow: {color, radius, strength, pulse: {period, low}}` on text, chips, bars and `chip`:
  the element is rendered to a layer, blurred by `radius` px and added underneath (bloom).
  `pulse` breathes the strength between `low` and 1 on an eased sine every `period`
  seconds (LED look).
- `recolor: [{at, color}]` changes the colour later (step label stacks).
- `plate`: `true` or `{color, alpha, pad, pad_y, radius, box: [x0, y0, x1, y1], y: [y0, y1],
  bar: {color, width, x}}`; `#0b0b10` at 60 percent with 16 px padding by default.
- `highlight: [{match, color, at}]` draws a 3 px rounded box with a 12 percent fill around a
  substring, measured with the font (never by character index), and recolours the match.
- `leading` sets the line height in px; `width` the wrap width; `nowrap: true` keeps lines.

### Data elements

- `ticker`: `{kind: ticker, from: 0, to: 462, over_ms: 900, decimals: 0, thousands: true, unit:
  "ms", size: 96, ease: ease_out}` counts up with easing; the unit is drawn at `unit_size`
  (37.5 percent) in `unit_color`. `text: "{n} of 72"` templates the number like `counter`.
- `bar`: `{kind: bar, box: [x0, y0, x1, y1], value: 0.91, max: 1.0, color: green, track:
  panel_border, radius: 4, marker: 0.65, marker_color: ink-dim, label: "{v:.2f}", label_pos:
  end|follow|none, label_size: 28, label_color: ink, over_ms: 800, in, ease, glow}`: the fill
  grows to `value` with easing while the label counts up (`{v}` value, `{pct}` percent);
  `marker` draws a threshold tick.
- `chip` with `verdict`, `glow` and `anim: pop` (see above).
- `rail`: `{kind: rail, n: 7, active: 3, pos: bottom|top, labels: [...], color: orange,
  dim_color: panel_border, width: 1200, gap: 10, thickness: 4, margin: 36, label_size: 20,
  fill_ms: 600, glow: true, in, ease}`: a chapter progress rail; chapters before `active` are
  lit at 55 percent, the active one fills left to right and glows. It sits outside the safe
  frame on purpose and is not fit-checked.

### Spotlight

`{kind: spotlight, shape: rect|circle, box: [x0, y0, x1, y1]` (or `center: [cx, cy], r: 200`)`,
feather: 60, dim: 0.7, radius: 16, in, out, anim_ms, out_ms, ease, moves: [{at: "s2", box: [...],
over_ms: 600, ease: ease_in_out}, ...]}`: a full-frame mask that dims everything except the
window; `feather` (40 to 80 px looks right) is the soft edge. Each move eases the window to a
new box (or center and radius) starting at `at`, so one spotlight can walk across regions on
sentence anchors.

### Pointers

`{kind: arrow|line|leader|box|circle|underline|highlight|bracket|bar|dotted|badge, from: [x, y],
to: [x, y], color, width, in, out, draw_ms, ease}`. Arrows, underlines and brackets draw on over
0.25 s (4 px strokes, 12 px heads); `line` (2 px, round caps) and `leader` (a line plus an end
dot of radius `dot`, 5) draw on along their length over `draw_ms` (default 360; 240 to 480 is
the intended range); a `box` with `draw_ms` draws its perimeter on clockwise from the top-left
corner with round caps (without it, boxes keep the pre-v3 grow and fade); circles and
highlights use `from`/`to` as the bounding box; `highlight` is a 3 px rounded rectangle with a
12 percent fill (`fill`, `radius`); `bar` fills from `from` to `to` over `grow` seconds and
switches to `color_after` once it crosses `threshold_x`; `dotted` is a dotted rule (`dash`);
`badge` is a filled circle of radius `r` with a `label` (no `to`); `pulse: {count, period}`
blinks instead of holding; `stages: [{to, at}]` extends an arrow later. Coordinates are
1920x1080 units.

### Kinds

- `clip`: `src`, `start`, `end` (seconds in the source; after `end` the last frame holds),
  `speed`, `fit: contain|cover`, `loop: true`, `mute: true` (drop the source audio; it is
  otherwise mixed in and ducked under the voice), `gain` dB, `zoom`, `crop: [x0, y0, x1, y1]`
  (source pixels), `place: [x0, y0, x1, y1]` (frame rectangle the crop is scaled into),
  `fill: blur` with `fill_blur` (px) and `fill_brightness` (the same crop scaled to cover the
  frame, blurred and darkened, behind a narrow placement), `blend: true` (ffmpeg
  `minterpolate=mi_mode=blend` for 10 to 15 fps GIFs), `brightness`.
- `still`: `src` (png/jpg/webp, `.svg` via `rsvg-convert` or macOS `qlmanage`, or a video with
  `at:` seconds for a freeze frame), `fit`, `zoom`, `camera`, `crop`, `place`, `fill`,
  `brightness`, `dim: {at, to, over}` (darken the whole image later), `regions: [{box, at,
  settle_at, settle_to}]` with `base_brightness` (the image starts dim and regions light up,
  earlier ones settling), `layers: [{src, at, fade, settle_at, settle_to, depth}]` (RGBA PNGs
  sharing the crop and placement, faded in on time; the shot-3 callouts are rendered from the
  figure's HTML with headless Chrome, see `docs/video/build/clips/layers/`).
- Parallax: under a `zoom`, every layer is cropped with its own view, its motion relative to
  the start scaled by `1 + depth`. `depth: 0` locks a layer to the picture, positive values
  are nearer (move more), negative values further (move less). On a 6 percent pan with a 12
  percent push-in, `depth: 0.05` drifts about 6 to 13 px over the shot; keep it between 0.02
  and 0.1 so foreground elements stay inside the frame.
- `zoom` (Ken Burns, clip or still): `{from: [cx, cy, scale], to: [cx, cy, scale], ease}` with
  `cx, cy` as 0..1 of the frame and `scale >= 1`; `ease` is `true` (smoothstep), `false`
  (linear) or a curve name.
- `camera` (still): keyframed views `[cx, cy, scale]` of the whole fitted picture, held between
  eased moves; the tightest view is cropped 1:1 from the source fitted at the largest scale.
  A list of `{at, view, ease}` where a numeric `ease` is the move length in seconds (0.6
  default, pre-v3 form), or `{keys: [...], settle: 0.01, ease: ease_in_out}` where each key is
  `{at, view, ease: <curve>, over: 0.6}` or `{at, hold: true}` (repeat the previous view; a
  named hold point). `settle` is a micro push over every hold: the scale drifts by that
  fraction (1 percent) on an `ease_in_out` from the end of the last move to the next keyframe,
  so the picture never sits dead still; a per-key `settle` overrides it.
- `card`: `bg` colour, `[c1, c2]` gradient or `{colors: [...], angle: 60}`; `logo: {src, pos,
  width}`; text and pointers only.
- `terminal`: `src` text file (`line_range: [first, last]`, 1-based; `wrap: 118` with
  `wrap_indent`) or `lines`; `cps` (40), `start` (0.3 s), `line_pause`, `schedule: [{line,
  at}]` (a line waits for its time), `pre: N` (the first N lines pre-shown in `pre_color`),
  `chrome: false` with `pos`, `width`, `leading`, `size`, `font`, `color` for a bare text
  column (or `frame: [x, y, w, h]`), `cursor`, `title`, `highlight: [{match, color, at, line,
  soft}]` (with `at` a timed box is drawn around the match, measured from the font; `soft:
  true` draws a feathered band instead). Lines starting with `$ ` get a green prompt in the
  chrome variant. v3: `jitter: 0.4` (per-character timing varies by up to 40 percent, seeded by
  `seed`), per-line pauses as `lines: [{text, pause_ms}]` or `pauses: [{line, ms}]`, `syntax:
  json` (keys cyan, strings green, numbers orange on JSON-looking lines), `cursor_hz` (2.2),
  `cursor_style: block|bar`, `scanlines: 0.06` (off by default). The block cursor blinks
  while typing and disappears when the last line is done.
- `table`: `rows` (first row is the header unless `header: false`), `row_every` (0.6 s) or
  `stagger` (ms), `start`, `title`, `size` (34), `highlight: {row: 3, color: red, at: 2.0}` (a
  list is fine), v3 `anim: rise|fade` with `row_ms` and `ease` (each row rises in on its own).
- `json`: `data` (mapping), `text` (JSON string) or `src` file; pretty-printed and typed at
  `cps` (60) with syntax colours; `reveal: [{match: '"verdict": "Deny"', color: red, at: 3.0}]`
  draws a highlight box around the match (`at` defaults to just after typing finishes).
- `code`: an editor panel. `src`/`lines`/`text` (with `line_range`), `title` (file name in the
  title bar), `size` (26), `lang: python|json|none`, `start_line` (1), `numbers: true`, `start`
  (0.3), `stagger` (30 ms per line), `anim: rise|fade|none`, `line_ms`, `ease`, `accent`,
  `highlight: [{lines: [13, 17], at: 1.5, color: orange}]` (a soft band plus an accent bar in
  the gutter, fading in on the curve), `frame`, `bg`, `font`, `leading`. Python colours:
  keywords violet, def/class names cyan, strings green, numbers orange, decorators amber,
  comments dim.
- `split`: picture in picture `main: {shot}` + `pip: {shot: {...}, pos: br, scale: 0.3,
  border: cyan}`, or side by side `left: {...}` + `right: {...}`. Children are shots without
  `vo`/`transition`; they may carry their own `text` and `pointers`. Raise `size` on text in a
  small PiP child since it is scaled down with the child.

### Transitions

`transition: {kind, duration, ease, direction}` on the shot being entered, or a bare kind name.
`cut` (default); the ffmpeg `xfade` kinds `fade`, `dip_to_black`, `dissolve`, `wipeleft`,
`wiperight`, `slideleft`, `slideright`, `fadegrays` (0.5 s default, linear inside ffmpeg,
`ease` ignored); and the eased kinds rendered by the renderer: `push_left` and `push_right`
(both frames move; `ease` defaults to `ease_in_out`), `whip` (a fast push, 0.25 s default,
with directional motion blur from the push velocity; `direction: left|right`). The first
shot's `fade` is a fade from black; `fade_in` at the top level does the same for any first
shot. Transition lengths are capped at half of either shot.

### Post pass and global look

`vignette` (0.35 is a gentle edge; dithered so it does not band on flat dark backgrounds),
`grain` (0.02 to 0.04 is film-like; luminance only, a seeded tile bank rolled per frame, so
renders are reproducible and cached segments stay valid; `grain_size` 2 draws the noise at
half resolution and upsamples it, soft clumps rather than pixel noise), `letterbox` and
`fade_in` are top-level keys. Vignette and grain are applied to every segment frame before
encode (grain means every frame is encoded fresh; the composition cache still skips redrawing
unchanged frames); letterbox bars are drawn on the joined video so pushes do not move them.
Grain is expensive to encode: at crf 18 x264 spends 50 to 110 Mbit/s keeping it, so while
grain is on the final file is capped at `grain_cap` (16 Mbit/s at 1080p, scaled by pixel
area; about 20 Mbit/s measured, 450 MB for three minutes) and segments at three times that.
Set `grain_cap: 0` for an uncapped master.

### Example

The real shot list is `docs/video/shots.yaml` (16 entries for the 15 script shots). See
`docs/video/build/test/sample.yaml` (one shot of every original kind plus a few v3 options)
and `docs/video/build/test/motion.yaml` (18 short shots, no VO, every v3 primitive; rendered
to `motion-draft.mp4` and `motion.mp4` in the same folder, proof frames in `proof/`).

```yaml
- id: deny
  kind: json
  duration: auto
  vo: "The answer maps to a Strands intervention. Deny means the car never moves."
  vo_offset: 2.0
  data: {verdict: Deny, frame: person_in_frame}
  reveal:
    - {match: '"verdict": "Deny"', color: red}
  text:
    - {kind: lower_third, text: "Guardrails pattern\nbefore_tool_call", pos: bl, in: 0.4, anim: rise}
    - {kind: chip, text: "DENY", verdict: Deny, pos: [1500, 300], in: "s2", anim: pop, glow: {color: red, radius: 18, strength: 0.8}}
  pointers:
    - {kind: leader, from: [1400, 300], to: [1180, 420], color: orange, in: 2.5, draw_ms: 400}
```

## Notes and limits

- Fonts and `say` voices are macOS defaults; on Linux pass `--font-*` and use `--no-vo` or Polly.
- Ken Burns and the camera are done in Python (crop + resize per frame) rather than
  `zoompan`, so stills and clips behave identically and the result is deterministic.
- Glow is an additive blend of a blurred colour layer (bloom on dark backgrounds); on a bright
  picture it reads as a tint. The `image` kind keeps its older soft ellipse glow.
- `scale_in`, `pop` and `blur_in` resample the finished text block, so very small text under
  them is a little softer during the entrance; it is sharp at rest.
- Whip blur averages 6 to 40 push positions per frame; at 15 fps draft it is coarser.
- Burned captions are drawn by the renderer (no libass needed) at `bc`; avoid placing other
  `bc` overlays on shots with a VO when `--burn-captions` is on.
- Polly failures fall back to `say`, then to silence with an estimated length; the log says which.
- The segment cache key includes the shot, duration, size, fps, fonts, text engine, the global
  look (ease, vignette, grain, seed) and caption text, not the bytes of the source media; pass
  `--force` after replacing an asset in place.

## Version 4 additions (the v2 film)

Everything below is opt-in; a shot list without these keys renders as under version 3.

- Curves: `enter`, `exit`, `move`, `camera`, `draw`, `count`, `drift` join the `ease` names
  (cubic-bezier values in `DESIGN.md` section 7).
- Top level: `vignette_inner` (radius of the half-diagonal inside which the vignette is zero,
  0.38 by default, 0.60 in v2) and `rules: {caption_zone: [940, 1040], one_accent: true, accent:
  orange}`. `check` then fails any measured text box that enters the caption zone (unless the
  element says `safe: false` or `caption_zone_ok: true`) and any two content elements in the
  accent colour whose on-screen stretches overlap by more than 0.25 s; `chrome: true` exempts an
  element and parts sharing an `accent_group` count as one (a callout's dot, leader and label; a
  step's node and label).
- Transitions: `transition: {kind: push_left|push_right|dissolve|fade, duration, ease, inside:
  true}` runs inside the incoming shot's first `duration` seconds over a frozen plate of the
  outgoing shot's last frame, so the timeline is not shortened. `black_out` takes a shot-level
  `black_ease` (the v2 dip to black on `camera`).
- Text overlays: `track` (letter-spacing as a fraction of the em, glyph by glyph), `caps`,
  `middot` (draws ` . ` as a middle dot), `alpha`, `settle: [{at, alpha, over_ms, ease}]` (an
  alpha settle), `move: [{at, pos, over_ms, ease}]` (a position tween), `recolor` entries with
  `over_ms`/`ease` (an eased blend instead of a hard switch), `anim: rise_left|rise_right` with
  `travel` px, `scale_from` for `scale_in`, `count_alpha` (digits at that opacity while a counter
  runs), `glow.settle: {to, over_ms}` (a chip bloom settling after its entrance), `highlight`
  entries with `style: underline` (2 px, `gap` px under the baseline, drawing on over `draw_ms`
  on the `draw` curve, `settle_at`/`settle_to` for a quieter line later, `alpha`, `recolor:
  false` to leave the text alone), a plate `border: {color, alpha, width}`, and `spans: [{text,
  in, anim, ...}]` (a span reveal: one measured line whose parts enter on their own anchors).
- `panel` (v2 form, any of these keys): `border`, `shadow: {blur, alpha, dy}`, `inner_shadow`,
  `header: {h, color, dots, title, title_size, title_color, title_x}`, `hatch: {spacing, color,
  alpha}`, `hollow: true` (shadow, corner bites and border only, framing a clip placed under it),
  `move: [{at, box, over_ms, ease}]`, `recolor: [{at, color, alpha, over_ms, ease}]`, `anim:
  grow_down|grow_right|rise` with `anim_ms`/`ease`, `out_ms`/`out_ease`.
- `image`: `crop`, `autocrop: true`, `knockout: {color, tolerance}` (a flat background made
  transparent), `anim_ms`/`ease`.
- New overlay kinds: `bloom` (`center`, `r`, `color`, `alpha_peak`, `alpha_floor`, `pulses`,
  `period_ms`: the LED) and `progress_rail` (`segments` in px, `chapters` in global seconds,
  `track_color`, `track_alpha`, `fill_color`, `head_color`, `head_px`, `draw_on: {at, ms, ease}`;
  the renderer injects the shot's global start, and the segment cache key includes it).
- `spotlight`: `regions: [{at, box | center + r | rx, ry, shape: rect|ellipse, fade_ms, out,
  out_ms, ease}]` stacks single spotlights (the viewer sees their union; the mask lifts when no
  region is active) and `lift: [{at, dim, over_ms}]` tweens the outside darkness.
- Pointers: `path` (`points`, `draw_ms`, `tail: {px, color}` for a colour change on the last
  stretch, `end_dot: {r, color}`), `node` (a disc `r` with `ring: {r, alpha, width}` while it is
  the current step, fading with its `recolor`), leaders with `dot_at: start` (the dot fills over
  `dot_ms`, then the line draws outward) and `ping: true` (a ring r 5 to 14 over 480 ms),
  `alpha`, `recolor`, `settle`, `out_ms`/`out_ease`, `radius` on a drawn `box` (rounded corners),
  `radius` on a `bar`, `label_color`/`label_font` on a `badge`, `attach: true` (coordinates
  follow the base picture's `subject_zoom`/`drift`), and `z` on any overlay or pointer (pointers
  default to 50, texts to 60; a stable sort keeps the old order).
- `clip` and `still` with `place`: `subject_zoom: {from, to, start, end, center, ease, clip}`
  (a push-in of the placed picture about a centre, clipped to its box by default) and `drift:
  {subject: [dx, dy], fill: [dx, dy], ease}` (the two-layer parallax; the fill drift applies to
  stills). `still.dim` takes an `ease`.
- `terminal`: `panel: {box, color, radius, header, shadow, border, inner_shadow}` (a v2 panel
  under a bare column placed with `pos`/`width`/`bottom`), schedule entries with `cps` and
  `delay` (typing classes per line), `cursor_hold` (the cursor rests after the last line),
  `cursor_hide_fast: 60` (hidden while a line at or above that rate prints), `cursor_blink_ms`,
  `cursor_w`/`cursor_h`, `fade_bottom` px, and `highlight` entries with `style: underline`,
  `settle_at`/`settle_to`, `from` (the colour a recolour starts from) and `width: 0` (recolour
  only).
