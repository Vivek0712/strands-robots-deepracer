# docs/video/render: shot-list video renderer

Deterministic renderer for the 3-minute hackathon demo. A writer edits one YAML (or JSON)
shot list and re-renders with one command; the output is a 1920x1080, 30 fps H.264 MP4 with
Amazon Polly voice-over, transitions, an `.srt` caption sidecar and -16 LUFS loudness.

Everything is drawn in a 1920x1080 reference space. `--draft` renders the same list at 960x540,
15 fps with the macOS `say` voice (no Polly) for fast iteration; the numbers in the shot list
do not change between draft and final.

## Usage

```sh
# validate schema, assets, timing, words per minute (no rendering)
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
/ `--duck-level -22` (dB relative), `--burn-captions`, `--no-vo`,
`--fade-out 0.6`, `--force` (ignore the segment cache), `--font-sans/--font-sans-bold/--font-mono`
(`path[:ttc-index]`; defaults Helvetica Neue and Menlo, falling back to Arial and DejaVu),
`--build-dir` (segment cache; default `docs/video/build`), `--vo-cache` (default
`docs/video/build/vo`), `--profile heisenberg --region us-east-1` for Polly.

Run from the repo root so `docs.video.render` resolves and relative asset paths work.
PyYAML is optional: a `.json` shot list with the same structure always works.

## Pipeline

1. VO lines go to Polly (generative, then neural, then standard as fallbacks), cached by a
   hash of voice, engine and text under `build/vo/polly/`. Draft uses `say` (`build/vo/say/`).
2. `duration: auto` shots take `vo_offset + VO length + 0.4 s`.
3. Each shot renders to its own MP4 segment in `build/segments/<id>-<hash>.mp4`; unchanged shots
   are reused. Clips and stills come through ffmpeg (scale/pad or crop, no stretching); cards,
   terminals, tables, JSON, text and pointers are drawn with Pillow and composited in Python.
4. Segments join with `xfade` (fade, dip_to_black, dissolve, wipes) or a straight cut.
5. The voice, un-muted clip audio and optional music are mixed in numpy, music is ducked
   with a smoothed envelope, then two-pass `loudnorm` to -16 LUFS, AAC 192k, `+faststart`.
6. `<out>.srt` is written from the VO text; `--burn-captions` also draws the same cues.

## Shot list

Top level is either a list of shots or a mapping:

```yaml
voice: Matthew           # optional defaults, CLI flags win
engine: generative
music: docs/video/raw/bed.mp3
fade_out: 0.6
auto_pad: 0.4
base_dir: .              # asset paths resolve against this
defaults:                # applied to every shot
  transition: {kind: fade, duration: 0.5}
shots: [...]
```

Common keys on every shot:

| key | meaning |
|---|---|
| `id` | unique name, used for the segment cache and captions |
| `kind` | `clip`, `still`, `card`, `terminal`, `table`, `json`, `split` |
| `duration` | seconds, or `auto` (needs `vo`); `min` is the floor for `auto` |
| `black_in` / `black_out` | seconds of dip from or to black inside the shot (no overlap) |
| `vo` | Polly text; SSML allowed when it starts with `<speak>` |
| `vo_offset` | seconds after the shot start before the voice begins (default 0) |
| `transition` | into this shot: `{kind: cut\|fade\|dip_to_black\|dissolve\|wipeleft\|..., duration: 0.5}`; the first shot's fade is a fade from black |
| `text` | list of overlays, see below |
| `pointers` | list of arrows/boxes/circles/underlines |

A transition of `d` seconds overlaps the two shots, so the timeline is shorter than the sum of
durations; `check` prints the real start of every shot.

### Palette and fonts

Colours follow `docs/video/STORYBOARD.md`: `bg #0b0b10`, `ink #f2f2f7`, `ink-dim #a0a0ad`, `orange
#ff6b3d`, `cyan #3ddcff`, `violet #7c5cff`, `green #3fb950`, `amber #ffb347`, `red #ff4d4f`
(`text` and `muted` are aliases of `ink` and `ink-dim`). Font kinds: `sans`, `sans_bold`,
`sans_medium`, `sans_medium_italic` (Helvetica Neue indices 0, 1, 10, 11), `mono`, `mono_bold`
(Menlo 0, 1). Safe margins are 96 x 72 px; `check` measures every overlay with the real font
and fails when text leaves the safe frame, its plate or its `max_x` (opt out of the frame rule
with `safe: false`).

### Text overlays

`{kind, text, pos, size, color, in, out, anim, width, align, font}`

- `kind`: `title` (Bold 64), `subtitle`, `lower_third` (Medium 32 on a 56 px plate with a 2 px
  orange bar, default pos `[112, 964]`), `caption` (Medium 40), `label` (Regular 30), `mono`
  (Menlo 28), `code`, `counter` (Bold 96; `text: "{n} ms p50"` with `count: {from, to, over,
  decimals}` counts up, the rest of the line is drawn at `unit_size` in `unit_color`), `chip`
  (Menlo Bold 30 on a solid plate of colour `bg:`), `bullet`, plus three non-text kinds:
  `chips` (`items`, `gap`, `pad`, `plate_color`, `plate_alpha`), `panel` (`box`, `color`,
  `alpha`, `radius`, `bar`) and `image` (`src`, `box`, `glow: {color, radius, alpha}`).
- `pos`: `tl tc tr ml mc mr bl bc br` (inside the safe margins) or `[x, y]` in 1920x1080
  units; `anchor: tl|tc|tr|...` says which corner of the block `[x, y]` is (right-align a
  label with `anchor: tr`).
- `in` / `out`: seconds relative to the shot. Overlays hold until the cut unless `out` is set.
- `anim`: `fade` (default, `fade:` seconds), `slide_up`, `slide_left` (24 px), `typewriter`
  (`cps`), `none`. `recolor: [{at, color}]` changes the colour later (step label stacks).
- `plate`: `true` or `{color, alpha, pad, pad_y, radius, box: [x0, y0, x1, y1], y: [y0, y1],
  bar: {color, width, x}}`; `#0b0b10` at 60 percent with 16 px padding by default.
- `highlight: [{match, color, at}]` draws a 3 px rounded box with a 12 percent fill around a
  substring, measured with the font (never by character index), and recolours the match.
- `leading` sets the line height in px; `width` the wrap width; `nowrap: true` keeps lines.

### Pointers

`{kind: arrow|box|circle|underline|highlight|bracket|bar|dotted|badge, from: [x, y], to: [x, y],
color, width, in, out}`. Arrows, underlines and brackets draw on over 0.25 s (4 px strokes, 12
px heads); boxes, circles and highlights use `from`/`to` as the bounding box; `highlight` is a
3 px rounded rectangle with a 12 percent fill (`fill`, `radius`); `bar` fills from `from` to
`to` over `grow` seconds and switches to `color_after` once it crosses `threshold_x`;
`dotted` is a dotted rule (`dash`); `badge` is a filled circle of radius `r` with a `label`
(no `to`); `pulse: {count, period}` blinks instead of holding; `stages: [{to, at}]` extends an
arrow later. Coordinates are 1920x1080 units.

### Kinds

- `clip`: `src`, `start`, `end` (seconds in the source; after `end` the last frame holds),
  `speed`, `fit: contain|cover`, `loop: true`, `mute: true` (drop the source audio; it is
  otherwise mixed in and ducked under the voice), `gain` dB, `zoom`, `crop: [x0, y0, x1, y1]`
  (source pixels), `place: [x0, y0, x1, y1]` (frame rectangle the crop is scaled into),
  `fill: blur` with `fill_blur` (px) and `fill_brightness` (the same crop scaled to cover the
  frame, blurred and darkened, behind a narrow placement), `blend: true` (ffmpeg
  `minterpolate=mi_mode=blend` for 10 to 15 fps GIFs), `brightness`.
- `still`: `src` (png/jpg/webp, `.svg` via `rsvg-convert` or macOS `qlmanage`, or a video with
  `at:` seconds for a freeze frame), `fit`, `zoom`, `crop`, `place`, `fill`, `brightness`,
  `dim: {at, to, over}` (darken the whole image later), `regions: [{box, at, settle_at,
  settle_to}]` with `base_brightness` (the image starts dim and regions light up, earlier ones
  settling), `layers: [{src, at, fade, settle_at, settle_to}]` (RGBA PNGs sharing the crop and
  placement, faded in on time; the shot-3 callouts are rendered from the figure's HTML with
  headless Chrome, see `docs/video/build/clips/layers/`).
- `zoom` (Ken Burns, clip or still): `{from: [cx, cy, scale], to: [cx, cy, scale], ease: true}`
  with `cx, cy` as 0..1 of the frame and `scale >= 1`.
- `card`: `bg` colour, `[c1, c2]` gradient or `{colors: [...], angle: 60}`; `logo: {src, pos,
  width}`; text and pointers only.
- `terminal`: `src` text file (`line_range: [first, last]`, 1-based; `wrap: 118` with
  `wrap_indent`) or `lines`; `cps` (40), `start` (0.3 s), `line_pause`, `schedule: [{line,
  at}]` (a line waits for its time), `pre: N` (the first N lines pre-shown in `pre_color`),
  `chrome: false` with `pos`, `width`, `leading`, `size`, `font`, `color` for a bare text
  column (or `frame: [x, y, w, h]`), `cursor`, `title`, `highlight: [{match, color, at, line}]`
  (with `at` a timed box is drawn around the match, measured from the font). Lines starting
  with `$ ` get a green prompt in the chrome variant.
- `table`: `rows` (first row is the header unless `header: false`), `row_every` (0.6 s),
  `start`, `title`, `size` (34), `highlight: {row: 3, color: red, at: 2.0}` (a list is fine).
- `json`: `data` (mapping), `text` (JSON string) or `src` file; pretty-printed and typed at
  `cps` (60) with syntax colours; `reveal: [{match: '"verdict": "Deny"', color: red, at: 3.0}]`
  draws a highlight box around the match (`at` defaults to just after typing finishes).
- `split`: picture in picture `main: {shot}` + `pip: {shot: {...}, pos: br, scale: 0.3,
  border: cyan}`, or side by side `left: {...}` + `right: {...}`. Children are shots without
  `vo`/`transition`; they may carry their own `text` and `pointers`. Raise `size` on text in a
  small PiP child since it is scaled down with the child.

### Example

The real shot list is `docs/video/shots.yaml` (16 entries for the 15 script shots, every
primitive above in use). See `docs/video/build/test/sample.yaml` (one shot of every kind, rendered to
`sample-draft.mp4` and `sample.mp4` in the same folder) for a complete, working example.

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
    - {kind: lower_third, text: "Guardrails pattern\nbefore_tool_call", pos: bl, in: 0.4}
  pointers:
    - {kind: arrow, from: [1400, 300], to: [1180, 420], color: orange, in: 2.5}
```

## Notes and limits

- Fonts and `say` voices are macOS defaults; on Linux pass `--font-*` and use `--no-vo` or Polly.
- Ken Burns is done in Python (crop + resize per frame) rather than `zoompan`, so stills and
  clips behave identically and the result is deterministic.
- Burned captions are drawn by the renderer (no libass needed) at `bc`; avoid placing other
  `bc` overlays on shots with a VO when `--burn-captions` is on.
- Polly failures fall back to `say`, then to silence with an estimated length; the log says which.
- The segment cache key includes the shot, duration, size, fps, fonts and caption text, not the
  bytes of the source media; pass `--force` after replacing an asset in place.
