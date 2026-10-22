# Writing a section of the deck

The deck is one HTML file assembled from section fragments. You write ONE fragment,
`sections/<NN>-<name>.html`, containing only `<section class="slide">…</section>` elements (no
`<html>`, `<head>`, `<script>`, no inline `<style>` beyond small per-element styles), plus
`sections/<NN>-<name>.notes.md` with: the sources you used (URLs, with what each one confirmed),
anything you could NOT verify (mark it "per speaker, unverified" and keep it out of the slide or
label it), and the speaker notes per slide.

Rules
- Use only the classes in `framework.css` (read it): `.kicker`, `h1/h2/h3`, `.grid.c2/.c3/.c4`,
  `.card`, `.pill`, `.big`, `.logo-row`, `.figure` (+`.caption`), `.timeline > .t`, `.loop`,
  `.flow`, `.pulse`, `.reveal` (staged items appear one by one on key press), `.center`, `.muted`,
  `.small`, `.safety`. Put speaker notes in `<aside class="notes">` inside the slide (hidden).
- Each slide: one idea, a kicker, a title, enough text to understand it without the speaker (two
  to five short bullets or a paragraph), and one illustration: an image/video from the official
  repo (download it to `assets/<section>/…` with curl and reference it as `assets/…`), a CSS
  diagram built from the framework classes, or a small animation (CSS keyframes are allowed in a
  `<style>` INSIDE your section fragment, scoped with a unique class prefix for your section).
- Logos: official only, downloaded into `assets/logos/` (PNG or SVG), referenced by relative
  path, with the source URL in the notes. Never fabricate a logo. If a logo cannot be fetched, use
  a text badge styled with `.pill` and say so in the notes.
- Facts: every number, date and name must come from a source you fetched and name in the notes.
  Claims given by the speaker that you cannot verify online are labelled "per speaker" in the
  notes and phrased carefully on the slide.
- Assets must be real files you fetched (check the HTTP status and the file size); no hotlinks in
  the slide, so the deck works offline at the venue.
- Media: `<video autoplay muted loop playsinline>` for repo videos (download mp4/gif; a GIF is an
  `<img>`).
- Keep each fragment self-contained; do not reference other sections' assets.
- Safety line to use whenever the DeepRacer or the gate appears: "Physics stops the car; the
  decider explains."
