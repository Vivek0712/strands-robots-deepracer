# Decider benchmark on the booth laptop, 2026-10-14

The gate asks the decider two questions before every hop: is the command inside the briefed
envelope (noul), and what is in front of the camera (choice over five classes). This note
measures those two questions, as the gate builds them, against every strands-decider checkpoint
that could be loaded on this Mac, and picks the booth model. Physics stops the car; the decider
explains. These numbers say how fast and how well it explains.

**Recommendation: `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` with `--vision` on MPS for
the booth.** Both questions together cost 490 ms at p50 (p95 498 ms), it holds 5.4 GB, it loads
in 10 s, and it was right on 6 of the 7 drawn frames (including the stick figure). Gemma 4 E2B
is the only model that got all 7 drawn frames, but it costs 1.12 s per hop, holds 11 GB, and
crashed the MPS server twice when the very first request carried an image: use it for recorded
cuts, not the live pen. E4B could not be measured (see "What did not run").

## Method

- Tool: `src/deepracer_agent/bench_decider.py`. It imports `ENVELOPE_QUESTION`, `FRAME_QUESTION`,
  `FRAME_CLASS_DESCRIPTIONS` and `envelope_context()` from `gate.py` and sends them through the
  same `DeciderClient` the gate uses, so the payload is byte-for-byte the gate's.
- Frames: the seven harness frames (`harness/frames.py`, 480x360 JPEG, quality 85, drawn with
  Pillow; no real person appears in any of them). Each frame: one warm-up call (excluded), then
  10 timed `choice` calls. Expected classes: clear->clear, obstacle_near->obstacle_near,
  person_in_frame->person_in_frame, off_surface->off_surface, unclear->unclear,
  hand_over_lens->unclear, sign->clear or unclear.
- Envelope: 14 fixed commands against the default `Envelope` (|linear| <= 0.3 m/s,
  |angular| <= 1.0 rad/s, duration <= 2 s), 7 inside and 7 outside, 10 repeats each, run twice:
  `as_gate` (the gate's state, which includes the `deterministic_check` line) and `blind` (that
  line removed, so the model has to compare the numbers itself).
- Latency is the client round trip on localhost, nearest-rank p50/p95. The server's shared-prefix
  cache is per request (questions fork a shared state), so repeats are not cache hits.
- Memory is `/usr/bin/footprint -p PID` (MPS weights live in IOAccelerator memory and do not show
  in `ps` RSS: the v19 server showed 139 MB RSS while holding 5.4 GB).
- Machine: Apple M4 Pro, 24 GB, macOS 15.7. Server: the author's local strands-decider checkout (branch
  `feat/gemma4-image-audio`, commit `c51a823`, the author's upstream PR #67), its own `.venv`,
  Python 3.12.11, torch 2.14.1, transformers 5.19.0. During the runs the machine was loaded by
  other sessions: swap 38-41 GB used of 40-43 GB, disk at 98 percent. Expect the booth laptop,
  running only the demo, to do a little better, not worse.
- Raw output per model: `docs/results/decider-benchmark-2026-10-14/{v19,v21,q2610,e2b}.{json,md}`.

### Commands

```bash
# in the strands-decider checkout (strands-labs/strands-decider, PR #67 branch for --audio)
.venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19         --vision --port 8111 --device mps
.venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21         --vision --port 8111 --device mps
.venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610    --vision --port 8111 --device mps
.venv/bin/strands-decider serve StrandsAgents/strands-decider-E2B-gemma4-v1-2610    --vision --port 8113 --device mps
# in ~/strands-robots-deepracer, one model at a time:
.venv/bin/python -m deepracer_agent.bench_decider --url http://127.0.0.1:8111 --repeats 10 --out runs/bench/<name>
```

`--vision` is required for every checkpoint, Gemma 4 included: without it the server answers a
request carrying `images` with HTTP 422. E2B ran on 8113 because another agent's fake decider
took 8111 for a moment mid-run; the port makes no difference to the numbers.

## Results

| model | base | load s | footprint | noul p50/p95 ms | choice p50/p95 ms | gate p50/p95 ms | frames agree | envelope as_gate | envelope blind |
|---|---|---|---|---|---|---|---|---|---|
| 2B-hobson-v19 | Qwen3.5-2B-Base | 16.9 | 5.4 GB | 138 / 140 | 344 / 351 | 482 / 491 | 5/7 | 140/140 | 70/140 |
| 2B-hobson-v21 | Qwen3.5-2B-Base | 11.0 | 5.3 GB | 137 / 140 | 342 / 349 | 479 / 489 | 5/7 | 140/140 | 70/140 |
| **2B-qwen3.5-v1-2610** | Qwen3.5-2B-Base | 9.4 | 5.4 GB | 141 / 144 | 349 / 354 | **490 / 498** | **6/7** | 140/140 | 110/140 |
| E2B-gemma4-v1-2610 | gemma-4-E2B-it | 19.2 | 11 GB | 182 / 207 | 937 / 978 | 1119 / 1185 | **7/7** | 140/140 | 100/140 |
| E4B-gemma4-v1-2610 | gemma-4-E4B-it | not run | about 15 GB (published) | - | - | - | - | - | - |

"gate" is noul p50 + choice p50 (the two questions run one after the other), without the frame
grab. Load time is from process start to a healthy `/health` with the weights already in the OS
page cache (the first load of each base from a cold disk was not isolated). Every timed call of
every 2B model was under the gate's 1.5 s per-question deny budget; E2B had one 4.8 s call, see
below.

### Frames: chosen class and its mean probability

| frame | expected | v19 | v21 | 2610 | E2B |
|---|---|---|---|---|---|
| clear | clear | clear 0.50 | clear 0.44 | clear 0.50 | clear 0.32 |
| obstacle_near | obstacle_near | **clear 0.39** (obstacle 0.37) | **clear 0.39** (obstacle 0.26) | **clear 0.42** (obstacle 0.22) | obstacle_near 0.48 |
| person_in_frame | person_in_frame | **clear 0.49** (person 0.21) | **clear 0.41** (person 0.26) | person_in_frame 0.56 | person_in_frame 0.56 |
| off_surface | off_surface | off_surface 0.41 | off_surface 0.29 | off_surface 0.41 | off_surface 0.39 |
| unclear | unclear | unclear 0.60 | unclear 0.45 | unclear 0.66 | unclear 0.76 |
| sign | clear or unclear | clear 0.68 | clear 0.56 | clear 0.62 | clear 0.41 |
| hand_over_lens | unclear | unclear 0.65 | unclear 0.50 | unclear 0.75 | unclear 0.63 |

Every model, on every repeat, returned the same class for a given frame (the server is
deterministic at temperature-scaled readout); the probabilities are the calibrated readout, not
sampling noise. Two gate-relevant readings: the dark frames (Blindfold, hand over the lens) are
`unclear` at 0.60-0.76 for every model, so the Deny at p >= 0.5 fires; and the Sign card is
`clear`, so the gate neither reads nor obeys it, which is the point of that beat.

### Envelope: with and without the deterministic check

With the gate's `deterministic_check` line in the state, every model answered all 140 envelope
questions correctly (mean P(inside): 2610 0.89 inside vs 0.09 outside; E2B 0.83 vs 0.15; v19
0.75 vs 0.27). Without it, v19 and v21 said yes to every command (50 percent); 2610 reached 79
percent (wrong on `far_too_long`, `too_sharp`, `too_sharp_negative`); E2B 71 percent (wrong on
`way_too_fast`, `too_fast_backward`, `too_sharp`, `too_sharp_negative`). This is the
robots-decider doctrine measured: numeric bounds belong in code (`Envelope.violations`), the
decider turns the result into a calibrated, explainable number. Keep the deterministic check in
the state; never ask a 2B model to compare `1.5 > 1.0` on its own.

## Stop-latency budget

Report 12 budgets a decider Deny at 300-700 ms end to end and told week 2 to measure it. The gate
is frame grab + noul + choice, sequential:

| model | two questions p50 | p95 | headroom under 700 ms for the frame grab |
|---|---|---|---|
| 2B (v19, v21, 2610) | 480-490 ms | 489-498 ms | about 200 ms |
| E2B | 1119 ms | 1185 ms | none: 1.1 s before any frame grab |

The 2B models fit the budget if the console grab takes under about 200 ms (the Car team's
`capture_frame` number, not measured here). E2B does not fit the 300-700 ms budget on this Mac;
it does fit the gate's 1.5 s per-question fail-closed timeout, so it would drive, slowly. Two
things to build in regardless of model:

- **Warm the server before the first hop.** E2B's first text request took 6.1 s and its first
  image request 4.7 s (Metal pipeline compilation); the 2B models' first calls were under a
  second. One timed E2B call hit 4.8 s after the warm-up and would have been a
  Deny("vision unavailable") in the gate. A warm-up pair (one noul, one choice with a real frame)
  at Pre-flight, and a keep-alive every 30 s between beats, removes this.
- **E2B: the first request must be text.** Twice, an image request as the very first call after
  load killed the MPS server with a Metal assertion (`failed assertion _status <
  MTLCommandBufferStatusCommitted`, then `A command encoder is already encoding to this command
  buffer`, exit 134). With a text request first it ran the whole benchmark. Not seen on the
  Qwen3.5 models.

## What the drawn frames can and cannot tell us

These are Pillow drawings: a grey floor with two white lines, an orange box, a black stick
figure, a red edge on beige carpet, a near-black frame, a white card with text, a uniform dark
frame. They validate the pipeline end to end (JPEG in, the gate's exact class vocabulary and
descriptions, calibrated probabilities out), the two dark-frame Denies, that the Sign card is not
obeyed, and relative latency and memory. They say almost nothing about real booth frames: a
stick figure is not a shoe at the pen edge, an orange rectangle is not a cone, and a drawn
carpet edge is not the real pen lip under hall lighting. The 2B models' misses on the drawn box
and the drawn figure are not evidence they miss real obstacles or real people, and E2B's 7/7 is
not evidence it catches them. The 300 labelled booth frames planned for week 3 (real camera,
real pen, real feet and hands, with and without the lights dimmed) are the only way to get a
per-class confusion matrix and to set the Deny threshold from measured probabilities instead of
the 0.5 default. The bench already takes `--frames-dir`; pointing it at labelled real frames
with the same seven file names is the week 3 run.

## What did not run

- **E4B.** The adapter was partly cached (no `head.safetensors`, no
  `lora/adapter_model.safetensors`) and its base `google/gemma-4-E4B-it` (16.0 GB) was not
  present. The disk was at 98 percent with 17-19 GB free and swap already at 40 GB, so pulling 16
  GB would have filled it; the earlier E2B attempt showed what happens then (disk hit 1.3 GB free
  and the server died). Published numbers: about 15 GB bf16, 139 ms per text question on an L4.
  Run it on a machine with 30 GB of free disk and nothing else loaded: same serve command with
  `strands-decider-E4B-gemma4-v1-2610`, port 8111, `--vision`.
- **E2B base download.** `google/gemma-4-E2B-it` (10.3 GB, ungated, no token needed) came down at
  about 16 MB/s in 10 minutes. Note the Gemma 4 deciders sit on the `-it` bases
  (`strands_decider_config.json`); the pretrained `google/gemma-4-E2B` was fetched by mistake
  first and removed.
- **Audio "stop" detection (report 11).** Not measured; synthetic PCM without real speech would
  prove nothing. To run it on recorded hall noise: serve E2B or E4B with `--audio` (implies
  `--vision`), record 2 s PTT clips as 16 kHz mono WAV with and without someone saying "stop",
  and POST `{"state": "", "audio": ["<base64 wav>"], "questions": {"stop": {"type": "noul",
  "instructions": "Did someone say stop?"}}}` to `/v1/systemone`; log `noul` per clip and pick the
  threshold from the two distributions. Per docs/audio.md each 40 ms of audio is one token and a
  clip is a per-utterance judge (seconds), not a per-frame one.

## How to start the booth decider

```bash
# pip install strands-decider, or run from a strands-labs/strands-decider checkout
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 \
    --vision --port 8111 --device mps
curl -s http://127.0.0.1:8111/health      # "model":"strands-decider-2B-qwen3.5-v1-2610","vision":true
```

It is healthy about 10 s after start (weights in page cache; allow a minute from a cold disk) and
holds 5.4 GB. Warm it with one text and one image request before the first beat (the bench with
`--repeats 1 --labels clear --no-blind` does exactly that). The gate reads `DECIDER_URL`, default
`http://127.0.0.1:8111`. Port 8111 is also the fake decider's port in the sim stack: `make unit`
and `make sim` bind it, so stop the real server before running them, and do not run them while
the car is live on the real decider. `make decider` in the Makefile lacks the checkpoint and
`--vision`; use the command above until the Lead updates the target.
