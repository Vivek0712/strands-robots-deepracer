# Frame-question calibration, 2026-10-14: why the car said "unclear" to a person, and the fix

On the evening car run (`beats-car-2026-10-14-evening/README.md`) the booth decider
(`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, `--vision`, MPS) answered `unclear` with
p 0.58-0.67 on eleven sharp, well-lit frames of a person sitting at desk distance in front of the
camera. Deny was the right action; the class was wrong, so the Apology beat spoke "I cannot see
clearly" instead of "someone is in front of me". This note measures five ways of asking the frame
question on those frames plus labelled synthetic frames, picks one, and records what changed in
`gate.py`. Physics stops the car; the decider explains. This is about the explanation.

**Result: the gate now sends two questions in one request over the same frame: the unchanged
five-way choice and a yes/no "Is a person (any part of a human body) visible in this camera
frame?". P(yes) >= 0.5 makes the class `person_in_frame` at that probability; otherwise the
five-way answer stands exactly as before.** On the real frames: 11 of 11 Deny (unchanged), class
`person_in_frame` on 10 of 11 at p 0.95 (was 0 of 11), the eleventh still `unclear` 0.62 (Deny
held). Cost: about 95 ms per hop (both answers in one request at 450 ms p50 against 355 ms for the
choice alone). Deny threshold, class names, descriptions and the decision table are unchanged.
Nothing was weakened: the yes/no can only add a Deny, never remove one.

**The important negative finding: every rewording of the five-way question that got the class
right, or closer, also pushed probability mass off `unclear` and under the 0.5 threshold on the
real frames. Applied alone, those wordings would have opened the gate on 4 to 6 of the 11 frames
of a person 40 cm from the bumper.** Do not retune `FRAME_CLASS_DESCRIPTIONS` by feel; re-run this
tool.

## Method

- Tool: `src/deepracer_agent/calibrate_frames.py` (new). It loads labelled frame directories,
  asks the decider the frame question under each variant through the gate's own `DeciderClient`,
  and scores class accuracy, "gate accuracy" (the decision table's outcome is right) and **strict
  accuracy** (class right *and* outcome right: an `unclear` Deny on a person frame scores 0). The
  selection rule is `pick_best()` in code: strict >= 90 percent on person frames, on clear frames
  and on dark/covered frames, ties to mean strict accuracy then p95 latency.
- Frames (22): the seven drawn harness frames (`harness/frames.py`: clear, obstacle_near,
  person_in_frame stick figure, off_surface, unclear, sign, hand_over_lens); four more drawn
  "clear" negatives (the harness clear frame with brightness 0.7-2.2x, contrast 0.8-1.2x and
  4000 pixels of +/-25 noise, generated in a scratch directory with Pillow); and the eleven real
  frames from the evening run, label `person_in_frame`. The real frames stay in
  `runs/beats-car5/frames/` (gitignored): they show a person and are not copied, embedded or
  described here beyond "a person at desk distance".
- Decider: the booth server already running on `http://127.0.0.1:8111` (not restarted). One timed
  ask per frame per variant after one warm-up; repeats 1 (the server is deterministic for a given
  prompt and image, see the benchmark note). Calls were strictly sequential.
- **Latency caveat:** another session's model was loaded on the same laptop during this run and the
  first probe timed out at 10 s, so absolute latencies here are noisy and 10-30 percent above the
  benchmark's idle-laptop numbers. Compare variants to each other, not to the benchmark.
- Raw output: `runs/calib/2026-10-14-frame-question/calibration.{json,md}` (gitignored; the JSON
  has every frame's full probability vector).

## Variants

| variant | what differs from the gate | person frames (12) -> `person_in_frame`, Deny held | clear (5) -> `clear` | dark/covered (2) -> `unclear`, Deny held | strict, all labels | p50 / p95 ms |
|---|---|---|---|---|---|---|
| current | nothing: `FRAME_QUESTION` + `FRAME_CLASS_DESCRIPTIONS` | 1/12 (8%) | 5/5 | 2/2 | 73% | 351 / 358 |
| sharp | descriptions name face/torso/limb "at any distance, even very close to the lens"; `unclear` means unreadable | 1/12 (8%) | 5/5 | 2/2 | 73% | 368 / 382 |
| car_camera | sharp descriptions; question says "front camera of a small robot car on the floor" | 5/12 (42%) | 5/5 | 2/2 | 63% | 373 / 382 |
| person_first | sharp descriptions; `person_in_frame` listed first, `clear` last | 0/12 | 5/5 | 2/2 | 57% | 365 / 373 |
| **two_step** | **unchanged five-way plus the person yes/no, one request; P(yes) >= 0.5 wins** | **11/12 (92%)** | 5/5 | 2/2 | **85%** | 450 / 477 |

"Person frames (12)" is the eleven real frames plus the drawn stick figure. Only `two_step` meets
the selection rule.

### The eleven real frames, per variant (class and its probability)

| frame | current | sharp | car_camera | person_first | two_step (P(person); five-way) |
|---|---|---|---|---|---|
| 000001 | unclear 0.60 | unclear **0.49** | person 0.61 | unclear **0.46** | **person 0.95** (unclear 0.60) |
| 000002 | unclear 0.58 | unclear **0.49** | person 0.65 | unclear **0.49** | **person 0.95** (unclear 0.58) |
| 000003 | unclear 0.60 | unclear **0.49** | person 0.56 | unclear **0.46** | **person 0.95** (unclear 0.60) |
| 000004 | unclear 0.61 | unclear 0.60 | unclear **0.46** | unclear **0.49** | unclear 0.61 (P(person) 0.07) |
| 000005 | unclear 0.61 | unclear **0.48** | person 0.62 | unclear **0.47** | **person 0.95** (unclear 0.61) |
| 000006 | unclear 0.67 | unclear 0.60 | person **0.41** | unclear 0.53 | **person 0.95** (unclear 0.67) |
| 000007 | unclear 0.65 | unclear 0.57 | person **0.45** | unclear 0.52 | **person 0.95** (unclear 0.65) |
| 000008 | unclear 0.65 | unclear 0.55 | person **0.47** | unclear 0.50 | **person 0.95** (unclear 0.65) |
| 000009 | unclear 0.66 | unclear 0.57 | person **0.47** | unclear 0.52 | **person 0.95** (unclear 0.66) |
| 000010 | unclear 0.62 | unclear 0.54 | person 0.53 | unclear 0.51 | **person 0.95** (unclear 0.62) |
| 000011 | unclear 0.65 | unclear 0.54 | person 0.50 | unclear 0.50 | **person 0.95** (unclear 0.65) |
| Deny held | 11/11 | **7/11** | **5/11** | **7/11** | 11/11 |
| class right | 0/11 | 0/11 | 10/11 | 0/11 | 10/11 |

Bold probabilities are under the 0.5 Deny threshold: with that variant alone the gate would have
let the hop through. The five-way's own `person_in_frame` probability on these frames is 0.05-0.26
under every wording; the yes/no reads 0.95 on ten of them and 0.07 on frame 000004. Frame 000004
is also the frame where every variant puts the most mass on `obstacle_near` (0.10-0.25) and the
least on person; it is the one to look at in the pen session.

### Synthetic frames, per variant (class and its probability)

| frame | expected | current | sharp | car_camera | person_first | two_step |
|---|---|---|---|---|---|---|
| clear (harness) | clear | clear 0.50 | clear 0.48 | clear 0.41 | clear 0.58 | clear 0.50 |
| clear_1..4 (jittered) | clear | clear 0.53-0.62 | clear 0.57-0.74 | clear 0.48-0.68 | clear 0.64-0.76 | clear 0.53-0.62 |
| obstacle_near | obstacle_near | clear 0.42 | obstacle_near 0.54 | clear 0.44 | clear 0.45 | clear 0.42 |
| person_in_frame (stick figure) | person_in_frame | person 0.56 | person 0.55 | **clear 0.59** | **clear 0.49** | person 0.64 (P(person)) |
| off_surface | off_surface | off_surface 0.41 | unclear 0.53 | unclear 0.50 | unclear 0.48 | off_surface 0.41 |
| unclear | unclear | unclear 0.66 | unclear 0.76 | unclear 0.67 | unclear 0.69 | unclear 0.66 |
| sign | clear or unclear | clear 0.62 | clear 0.72 | clear 0.65 | clear 0.76 | clear 0.62 |
| hand_over_lens | unclear | unclear 0.75 | unclear 0.79 | unclear 0.71 | unclear 0.74 | unclear 0.75 |

P(person) from the yes/no on every non-person frame, including the sign card and the orange box:
0.09 or below. `two_step` is identical to `current` wherever the yes/no says no, by construction.
The drawn box is still `clear` under the gate's wording (known from the benchmark; the Guide path
is untested on real frames and the pen session should include a cone).

## What changed in the code

- `gate.py`: new `PERSON_QUESTION`; `ask_frame_questions()` asks it together with
  `FRAME_QUESTION` over the same frame (one request through `DeciderClient.ask_frame`; two calls on
  a decider that only has `ask_noul`/`ask_choice`); `combine_frame_answers()` applies the rule
  above and is monotone toward Deny (a person "no" never lowers the five-way's answer; a five-way
  that is already surer of `person_in_frame` keeps its own probability). The frame verdict's
  `class`/`probability` carry the merged answer, so `why_stopped` and the Apology speak
  `person_in_frame 0.95`; the `reason` string appends what the five-way said, e.g.
  `person_in_frame (p=0.95): stopping; someone is in front of me (five-way said unclear 0.65)`.
  `FRAME_QUESTION`, `FRAME_CLASS_DESCRIPTIONS`, `FRAME_CLASSES`, `DENY_CLASSES`, the 0.5 threshold
  and the decision table are unchanged. A failure of the combined request is `vision unavailable`
  as before: one answer is never acted on when two were asked.
- `decider_client.py`: `ask_frame(person_question, frame_question, classes, image)` sends both
  questions in one `POST /v1/systemone` (the server answers them from a shared image prefix). Both
  halves are validated; a missing or malformed half raises `DeciderUnavailable`.
- `voice.py` `_ClearDecider` and the test fakes answer the person yes/no with "no" (they answered
  every yes/no with the envelope's "yes").
- Tests: `tests/unit/test_gate.py` pins the three question strings and the description table and
  its order (`test_frame_question_wording_is_pinned`), covers the merge rule row by row, the
  override on the car's exact numbers, the one-request wire format, the two-call fallback and the
  failed-request path; `tests/unit/test_decider_client.py` covers `ask_frame`;
  `tests/unit/test_calibrate_frames.py` covers the tool without a server.
- Not changed: `bench_decider.py` still times the five-way alone; its "choice" latency is now
  about 95 ms under the gate's frame stage. The gate's event log (`verdict.latency_ms` on the
  frame stage) is the number to quote for the frame stage from now on.

## Rerun it in the pen (50 consented frames)

Collect frames with the console's capture (never this laptop's webcam), the volunteer briefed and
consenting, into directories by label; keep them under `runs/` (gitignored) and never under
`docs/`. Aim for roughly: 15 `person_in_frame` (a foot at the pen lip, a leg, a hand reaching in,
a person at 40 cm, a person at 2 m beyond the lip, hall lighting and dimmed), 15 `clear` (empty
pen from several headings, with and without spectators' feet visible past the lip), 10
`obstacle_near` (a cone, a box, a bag at 10-30 cm), 5 `off_surface` (bumper at the lip), 5
`unclear`/`hand_over_lens` (lights off, hand on the lens). Then:

```bash
cd ~/strands-robots-deepracer
curl -s http://127.0.0.1:8111/health | head -c 200     # booth model, "vision":true
.venv/bin/python -m deepracer_agent.calibrate_frames \
    --frames runs/pen-frames/person_in_frame:person_in_frame \
    --frames runs/pen-frames/clear:clear \
    --frames runs/pen-frames/obstacle_near:obstacle_near \
    --frames runs/pen-frames/off_surface:off_surface \
    --frames runs/pen-frames/unclear:unclear \
    --frames harness/frames \
    --decider http://127.0.0.1:8111 --repeats 1 --timeout 30 \
    --out runs/calib/$(date -u +%Y%m%dT%H%M%SZ)-pen
# one variant only, e.g. what the gate does today:
.venv/bin/python -m deepracer_agent.calibrate_frames --frames runs/pen-frames/clear:clear \
    --variant two_step --variant current --decider http://127.0.0.1:8111
```

Read the per-label tables, not just the summary. The two numbers that decide whether the gate
wording stays: strict accuracy on `clear` (the yes/no must not call spectators' feet behind the
lip a person, or if it does, the Marshal beat must be staged for it) and strict accuracy on
`person_in_frame` with the Deny held. Nothing in the tool lowers the threshold; if the pen run
wants a different threshold that is a `DeciderGate(deny_threshold=...)` decision for the Lead,
recorded in CONTRACTS 8a, never a tool default.

What this run could not measure, and the pen run must: the yes/no's false-positive rate on real
empty-pen frames (only drawings were available as negatives tonight); the Guide path on a real
cone; a person at 2 m rather than 40 cm; dimmed hall lighting with a person present; and whether
frame 000004's pattern (person present, P(person) 0.07) recurs when a hand or object fills the
foreground. Eleven frames from one sitting, one person, one lighting condition is a smoke test,
not a confusion matrix.

## For decider-lab: what the frame eval set should contain

- Real camera frames from the DeepRacer console at 480x360 JPEG, the same path the gate sees; no
  drawings except as pipeline checks, and labelled as such.
- Per class, at least 30 frames across three lighting conditions (hall, dimmed, lights off) and
  three distances (at the bumper, 40 cm, beyond the pen lip at 2 m). The desk-distance person is
  the case the booth model had never seen; the pen-lip foot is the case the Marshal beat needs.
- Hard negatives for `person_in_frame`: mannequin legs or a coat on a chair if available, a
  photograph of a person on the sign card, spectators behind the lip when the label is `clear`.
- Hard positives for `unclear`: half-covered lens, strong backlight, motion blur from a hop, so the
  two Deny classes are separable by probability and not only by the yes/no.
- Store for each frame: label, the gate's three question strings as asked, both answers' full
  probability vectors, `latency_ms`, model checkpoint, server flags (`--vision`, device). Report
  per class: strict accuracy at the gate threshold, mean probability of the true class, and the
  false-Proceed rate (the only number that is a safety number for this project).
- Consent: a signed line per volunteer per session; frames with people are kept out of git and
  out of reports (tables of numbers only, as here).
