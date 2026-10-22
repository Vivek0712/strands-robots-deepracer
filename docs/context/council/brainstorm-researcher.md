# Brainstorm: use cases that prove something about Physical AI (researcher view)

Premise. The DeepRacer has no encoders, no odometry, no watchdog, one camera. That is not a
weakness to hide; it is the cleanest possible test bed for the claim that Physical AI is a
closed loop: every action is a hypothesis about the world, and the only way to know it was
right is to look again. "An LLM calling move()" never looks again. Every use case below has a
verify stage with a number on screen, and a stated way to fake it so the builder knows what
not to do.

Vocabulary: sense -> judge -> act -> verify; pillars in brackets. "Decider" runs on the
laptop GPU; "gate" is the strands-robots approval gate or the documented low-speed envelope.

---

### 1. Say it, then prove it (closed-loop grounding)
- Claim: a VLM plan step is a prediction, not a command. Each step carries an expected
  observation; the loop measures the residual and replans on error.
- Loop: sense frame, detect target bbox, convert x-centre to bearing via measured camera FOV
  [robots frame buffer, agent tool] -> judge: VLM proposes a short arc AND predicts the
  post-move bearing [Agents SDK] -> act: gated drive [robots gate] -> verify: re-detect,
  residual = predicted minus observed; Decider yes/no "is target centred?" as a second,
  calibrated opinion [Decider]; residual over threshold triggers replan.
- Evidence on screen: per-step predicted vs observed bearing, residual trace, count of
  replans. Some steps must visibly miss and recover.
- Fake: VLM says "done" with no measurement. Real: residuals are shown and non-zero.
- Prereq: measure horizontal FOV once (tape, a ruler, five minutes); bbox detector (VLM
  bbox or a small YOLO on the laptop). No LiDAR.

### 2. Know when you don't know (calibrated deferral)
- Claim: a calibrated classifier turns confidence into an act / slow / ask policy with a
  measurable risk-coverage trade-off. This is selective prediction on a real robot.
- Loop: sense frame [robots] -> judge: Decider "path clear?" probability [Decider]; bands:
  over 0.9 act, 0.6 to 0.9 halve speed and re-observe, under 0.6 defer to the human via an
  intervention [Agents SDK interventions] -> act [gate] -> verify: when the human answers,
  log agreement; when it acted, log whether the next frame contradicted it.
- Evidence on screen: a reliability diagram and ECE computed from booth-style frames
  labelled before the conference, live coverage and selective-risk counters, "deferred N
  times, human agreed M times".
- Fake: a softmax threshold with no calibration data. Real: the diagram is from at least 300
  labelled frames and the deferral band is chosen from it.
- Prereq: 300 to 500 frames from the booth-like floor (people, feet, cables, clear),
  labelled; one evening. No LiDAR (Evo LiDAR helps label ground truth faster).

### 3. Where am I? Ask the posters (monocular topological world model)
- Claim: without odometry a rover can build a topological map (nodes = distinctive views,
  edges = the actions that joined them) good enough to return to a named place.
- Loop: explore in gated short hops [robots]; at each stop embed the frame (SigLIP or CLIP
  on the laptop) and caption it [Agents SDK tool, harness long-term memory] -> judge: new
  node if cosine distance to all nodes is above a threshold, else merge -> act: on "go back
  to the Strands poster", retrieve the node, plan a path over edges, execute them -> verify:
  arrival similarity above threshold; Decider yes/no "same place as the stored image?"
  [Decider]; on failure re-localise to nearest node and retry.
- Evidence on screen: the graph growing live, current node, retrieved image beside the live
  frame with the similarity score, one re-localisation.
- Fake: pre-recorded waypoints. Real: the graph is built that morning from that booth.
- Prereq: embedding model on the laptop; threshold tuned on about 50 same/different pairs.
  No LiDAR (Evo scan matching would stabilise edges; optional).

### 4. Move to see better (active perception)
- Claim: perception is an action. Viewpoint selection driven by a readability score raises
  recognition confidence; the rover chooses rotate vs approach from the observation.
- Loop: "what does that sign say?" [Bidi] -> sense: crop and OCR/VLM read with a Decider
  score 0 to 1 for readability [Decider] -> judge: if bbox small, approach; if at frame edge,
  rotate toward; if glare, change angle; budget of 3 moves [Agents SDK] -> act [gate] ->
  verify: re-read, score must rise; stop at threshold or budget.
- Evidence on screen: readability score vs step, the chosen move and the rule that chose it,
  final text. At least one run where it rotates rather than advances.
- Fake: fixed "drive forward 0.3 m then read". Real: the action depends on the frame.
- Prereq: calibrate readability score on about 100 crops. No LiDAR.

### 5. System 2 keeps score on System 1 (supervising a reflex policy)
- Claim: a supervisor over a fast reflex policy can intervene pre-emptively on rising
  risk, and its intervention latency is a measured distribution, not an anecdote.
- Loop: on-board RL model drives at capped throttle [robots mode services] -> sense: frames
  and, on Evo, LiDAR [robots] -> judge: Decider per frame for person and off-surface; a
  rising-risk trend over N frames triggers throttle reduction before the hard stop
  [Decider, Agents SDK hooks] -> act: manual mode + stop [robots] -> verify: latency from
  the first person-positive frame timestamp to the motor-zero ack, recorded per trial.
- Evidence on screen: time-to-stop histogram with p50 and p95 over 20 or more trials,
  live risk trace, mode flips, spoken explanation of what it saw.
- Fake: a human on the e-stop; no timing. Real: the p95 is printed and defended.
- Prereq: 20 rehearsal trials, decider frames for person and off-surface, the upstream
  mode-state fix. Evo LiDAR recommended as redundant person channel; not required.

### 6. Teach, then test (learning from demonstration with pre-conditions)
- Claim: a demonstration is (observation, action) pairs, not an action list. Replay is
  conditioned on the visual state matching the demo at each segment, so it refuses when the
  world changed.
- Loop: user teaches a route by voice or joystick; recorder stores frames and commands
  [robots recorder] -> judge at replay: before each segment, compare live frame embedding to
  the demo frame; Decider yes/no "does the scene match?" [Decider] -> act: gated replay of
  the segment [robots replay policy, gate] -> verify: post-segment frame also compared;
  bail with "the room looks different here" on mismatch.
- Evidence on screen: demo frame vs live frame similarity per segment; a chair moved into
  the path makes it stop at exactly that segment.
- Fake: blind replay of commands. Real: the moved chair causes a refusal at the right place.
- Prereq: embedding threshold from use case 3. No LiDAR.

### 7. Stuck, and knows it (failure recovery from expected motion)
- Claim: a robot with no encoders can detect motion failure by comparing expected to
  observed optical flow, then recover.
- Loop: command issued -> expected flow magnitude and direction from a command-to-flow table
  built in rehearsal -> sense: Farneback flow on consecutive frames [robots frame buffer]
  -> judge: observed far below expected = blocked; direction mismatch = pull or slip
  [Agents SDK post-action hook, Decider yes/no "did the car move?" as cross-check] -> act:
  stop, reverse 0.1 m, re-observe, replan or ask [gate] -> verify: flow returns to expected.
- Evidence on screen: expected vs observed flow vectors, the "stuck" declaration within one
  second of someone holding the car, the recovery action.
- Fake: a timeout. Real: hold the car and watch the numbers diverge.
- Prereq: 10 minutes of rehearsal driving to build the table (shares data with use case 8).
  No LiDAR.

### 8. It measures itself (self-calibration from a single camera)
- Claim: kinematic parameters (metres per second per throttle, yaw per steer) can be
  estimated with no encoders from monocular observation of a known-size target, and drift
  can be detected and corrected in a governed loop.
- Loop: a printed AprilTag of known size on the floor -> act: throttle t for one second, then
  steer s for one second [gate] -> sense: tag scale change gives distance travelled; tag
  bearing change gives yaw [robots frame buffer] -> judge: fit speed(t) and yaw(s); compare
  to the stored calibration; if drift above threshold, the harness over SSH proposes a PWM
  offset and asks [Harness SDK SSH sandbox, Cedar intervention] -> act: set_car_cal [robots
  calibration services] -> verify: re-measure and show the new fit.
- Evidence on screen: fitted throttle-to-speed curve with data points, before and after a
  deliberately perturbed calibration, the proposal, the approval, the re-measurement.
- Fake: reading the calibration file aloud. Real: the perturbation is corrected by
  measurement, and the numbers are different after the write.
- Prereq: one printed tag, FOV measurement, pupil-apriltags on the laptop, 15 minutes of
  runs. No LiDAR (Evo LiDAR gives a second distance source for a cross-check).

### 9. Can I fit? (language to traversability affordance)
- Claim: grounding instructions like "go between the chairs" or "under the table" is a
  geometric feasibility question about the body (0.28 m turning radius, about 0.2 m width,
  height), not an object-label question.
- Loop: parse instruction [Bidi, Agents SDK] -> sense: VLM localises the region; gap width
  from LiDAR on Evo, or from a monocular reference (floor tile, badge) on stock [robots] ->
  judge: compare gap and required turn to the body envelope; Decider yes/no "traversable?"
  as a calibrated second opinion [Decider] -> act or decline with numbers [gate] -> verify:
  on execution, flow and frame confirm passage; on decline, say why.
- Evidence on screen: measured gap with the body envelope overlaid, go/no-go with numbers,
  one physically narrow gap refused.
- Fake: VLM answers "yes" without a measurement. Real: numbers, and a correct refusal.
- Prereq: body envelope measured; on stock, a reference object; on Evo, the best-effort
  LiDAR echo fix. **Evo LiDAR strongly recommended.**

### 10. Same mind, different body, measurably (multi-embodiment transfer)
- Claim: skills expressed in body-agnostic terms (bearing, distance, readability) plus a
  per-body kinematic adapter learned by use case 8 transfer across bodies, measured by the
  same task metric.
- Loop: run "centre the poster" (use case 1) on the DeepRacer and on a Yahboom M3 Pro or the
  MuJoCo twin [robots registry, mesh] -> same agent, same prompts [Agents SDK] -> verify:
  steps-to-centre and residuals logged per body.
- Evidence on screen: side-by-side metric table, the registry entry as the only diff,
  each body's auto-estimated kinematics.
- Fake: two scripted demos. Real: one metric, two bodies, no code change.
- Prereq: a second body or the twin; calibration for each. No LiDAR.

---

## Rank: novelty a robotics person would respect
1. 8 It measures itself: encoder-free kinematic self-calibration closed by a governed write.
2. 2 Know when you don't know: selective prediction with a real reliability diagram on a robot.
3. 3 Where am I? Ask the posters: live monocular topological map and verified return.
4. 7 Stuck, and knows it: expectation-vs-flow failure detection with recovery.
5. 4 Move to see better: observation-driven viewpoint selection with a confidence curve.
(Honourable: 5 with a real p95; 9 only with LiDAR.)

## Rank: feasible in 4 weeks by one person
1. 2 Know when you don't know: labelling, a decider, a diagram; mostly offline work.
2. 5 System 2 keeps score on System 1: extends the planned Act 5 with timestamps.
3. 1 Say it, then prove it: bbox plus FOV, builds the measurement scaffold everything else reuses.
4. 6 Teach, then test: recorder exists; add an embedding check per segment.
5. 7 Stuck, and knows it: OpenCV flow and a rehearsal table; 8 is a close sixth and shares data.

## Build note
Use cases 1, 7 and 8 share one scaffold (FOV measurement, bbox or tag bearing, a rehearsal
log of commands against observed image change). Build that first; it is the "look again"
primitive.
