# Filming protocol: videos and images the showcase needs

Everything laptop-side is captured automatically (events.jsonl, decider verdicts, frames from the
car camera, portal screenshots and the Playwright recording under `docs/results/portal/`). The car
itself has no camera attached yet and nothing on the laptop can film the pen, so the physical
videos are shot by a person. This is the shot list, so the footage matches the screen record.

## Rules

- Phone in landscape, 1080p, on a small tripod at pen height; the Pit Wall on a second screen
  behind the pen so one frame holds both the car and the verdict.
- Say the beat name and the take number out loud at the start of every take; the portal shows the
  same beat name, so footage and `events.jsonl` can be lined up by the clock.
- Nobody in the pen except the volunteer the beat calls for; never film a stranger without asking.
  Frames saved by the car during a take stay in the run dir and are never committed.
- Ten takes per beat (`tests/pen/README.md` sheet). A beat ships only at 10 of 10.
- Wheels off the ground for every first take of the day (preflight, hop, deadman).

## Shot list, in stage order

| # | Beat | Shot | What must be visible |
|---|---|---|---|
| 1 | Pre-flight | car on the stand, LED | LED turning green on "go", the preflight table on screen |
| 2 | Marshal | wide, pen from the side | three 20 cm hops; the volunteer's foot entering frame; LED red; the Deny card |
| 3 | Apology | medium, presenter and screen | the question asked, the frozen frame and probability on screen while the answer is spoken |
| 4 | Blindfold | close, hand over the lens | hand, "unclear" verdict, "No.", hand lifts, hop completes |
| 5 | The Sign | close on the sign, then screen | the sign text readable, the rover reading it aloud, no motion |
| 6 | Red Light | wide, with audio | the roll, the word "stop", wheels stopping, the two millisecond timestamps on screen |
| 7 | Pull the Plug | wide, router in frame | the plug pulled, the car stopping within a second, the deadman trip card |

## Pre-recorded beats (labelled as recorded on the screen)

- **Pit Stop**: screen recording of `ops/race_engineer.py` over SSH to the car: read calibration,
  find the offset, ask under the Cedar leash (`DEEPRACER_OPERATOR_CONFIRMED` unset, so the write is
  refused; then set, so it is allowed), fix, drive straight. Record with the portal audit panel
  beside the terminal. Do this on the stand, not on the floor.
- **Two Bodies**: the same agent on the car and on the MuJoCo twin on screen; "stop all" halts
  both. Depends on the twin registry entry (week 3 item, not built yet).

## Where the files go

`docs/results/videos/<beat>-take<NN>.mp4` are NOT committed (size, and attendee faces). Keep them
in the shared drive the team agrees on and list them in `docs/results/README.md` with the take
numbers that passed. Still images that contain no people may be committed under
`docs/results/images/`.
