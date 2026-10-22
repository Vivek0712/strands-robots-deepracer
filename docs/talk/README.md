# The talk deck: "Control, simulate and train robots with natural language"

`docs/talk/deck/index.html` is the built deck (41 slides, 16:9, dark, self-contained with the
`assets/` folder). Open it in Chrome; `F` or the browser's full-screen for the projector.

Keys: `→` / space / click advance one staged item, then the next slide; `←` back; `Home`, `End`;
`a` shows every staged item on the current slide; `?` toggles the speaker notes panel (each
slide's `<aside class="notes">`). The URL hash is the slide number; `?all=1` shows all reveals.

Built from `sections/*.html` by `python docs/talk/deck/build.py` (framework.css + framework.js +
fragments, with checks: no scripts in fragments, no hotlinked media, every asset present). Each
section has a `.notes.md` beside it with every source, what it confirmed, and what is "per
speaker" (unverifiable online).

## Decisions left to the speaker (from the reviews)
- Say "Gemma 4", not "Gemini 4": the JevBench board's newest top entries are Gemma 4 LoRAs.
- "Number one on the leaderboard for a week" is not on any slide: the only trace online is your own
  issue #39 (estimated #1, local proxy scorer, unofficial). A dated board screenshot would let it in.
- The awards, the Guinness record, COM305 and "youngest Hero" appear as your own account, not as
  verified facts (slide 2 footnote). Confirm the Think Big award year.
- The $25 AWS credits photo offer is on the closing slide as your personal offer; the mechanics
  (where to post, tag, deadline) are yours to add.
- The X handle was removed (not listed on Builder Center or awsugmdu.in); GitHub, LinkedIn and
  Builder Center stay.
- "Physical AI Open Chain Toolkit" does not exist by that name; the slide covers the AWS Physical
  AI Toolchain (announced 7 Oct 2026), whose blog does not name strands-robots (the quotes are from
  the repo README).
- The JevBench and GitHub star numbers are 17 Oct 2026 snapshots; re-check the day before.
- Blindfold, Sign and Red Light have run on the sim, not yet on the car with a clear pen.
