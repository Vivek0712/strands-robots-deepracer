# Submission package: Strands Decider 2B hackathon

Draft. Items in square brackets are placeholders the author fills before submitting; the scanner
reports each one as WARN until it is replaced.

## Title

Physical AI on AWS DeepRacer: a rover that drives on natural language, judges every move, and answers to your voice

## Pitch

A stock AWS DeepRacer becomes a Strands robot. strands-robots drives it over ROS 2 through
rosbridge, a Strands Agents loop on Amazon Bedrock (Amazon Nova Pro) turns spoken or typed
instructions into bounded 20 cm hops, and before every hop a local Strands Decider 2B answers
five typed questions in two requests: is the move inside the envelope the marshal briefed, are
its arguments grounded in what the user said, what did the user ask for, is a person in the
frame, and what is in front of the camera right now. The answers map to the Strands intervention
verdicts Proceed, Guide, Confirm or Deny, so a guessed distance is sent back, a person in frame
stops the hop, and the rover says why. Strands Bidi gives it a push-to-talk voice through Amazon
Nova Sonic, a Strands Harness race engineer services it over SSH under a Cedar policy, and
Strands Box fences the process. Physics stops the car (pen lip, hop cap, on-car deadman,
marshal's thumb); the decider explains.

## Tags

#strands-decider-2b #guardrails

## Declared pattern

Declared pattern: Guardrails. Before every motion tool call, the agent verifies with Strands
Decider 2B that the call is inside the envelope the operator briefed, that its argument values
are grounded in what the user actually said, and that the live camera frame allows the move.

## The decision handed to Decider 2B

Model: `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, served locally with
`strands-decider serve ... --vision`, called on `POST /v1/systemone` from a Strands
`InterventionHandler.before_tool_call`. Source of truth for the names:
`patterns/strands/tool_call_intervention.py` (`QUESTIONS`, `YES`) and
`patterns/strands/frame_intervention.py` (`FRAME_QUESTIONS`, `FRAME_CLASSES`); the on-car gate
`src/deepracer_agent/gate.py` asks the same five questions.

Five questions in two requests, one forward pass each:

| Name | Type | Question | Options or criteria |
|---|---|---|---|
| `inside_envelope` | noul | Is the proposed movement inside the envelope the operator briefed? | state carries the conversation, the command, the envelope text and `deterministic_check` computed in code |
| `args_grounded` | noul | Are the tool's argument values grounded in what the user actually said? | same request |
| `intent` | choice | What did the user most recently ask the robot to do? | move_forward, turn, stop, question, unrelated |
| `person` | noul | Is a person visible in the frame? | second request, over the live 480x360 JPEG |
| `frame` | choice | What is directly in front of the car in this camera frame? | clear, obstacle_near, person_in_frame, off_surface, unclear |

Thresholds, owned by code: `YES = 0.65`, `NO = 0.35` (text questions), person 0.5, unclear 0.65,
budget 1.5 s. The rows are checked in this order; the first matching row is the action.

| # | Condition | Action | Reason string |
|---|---|---|---|
| 1 | decider unreachable, timeout (> 1.5 s), malformed answer (missing key, probability outside [0, 1] or NaN, unknown class) | Deny | "decider unavailable" (text request) / "vision unavailable" (frame request) |
| 2 | no camera frame | Deny | "vision unavailable" |
| 3 | person >= 0.5, or frame class person_in_frame | Deny | "person in frame" |
| 4 | frame class off_surface | Deny | "off the surface" |
| 5 | frame class unclear with p >= 0.65 | Deny | "cannot see clearly" |
| 6 | intent stop with p >= 0.65 | Deny | "the user asked to stop" |
| 7 | deterministic envelope check fails (code, not the model) | drop-in: Guide "re-plan inside the envelope"; on the car: Confirm (the marshal's thumb: the operator may approve a bigger hop) | "outside envelope: <violations>" |
| 8 | inside_envelope < 0.35 | Guide: re-plan inside the envelope | "outside envelope per decider (p=...)" |
| 9 | args_grounded < 0.35 | Guide: ask the user for the values instead of inventing them | "arguments not grounded (p=...)" |
| 10 | intent question or unrelated with p >= 0.65 | Guide: answer the user instead of moving | "intent <x> (p=...)" |
| 11 | frame class obstacle_near | Guide: halve the speed and re-plan the hop | "obstacle_near (p=...)" |
| 12 | inside_envelope or args_grounded in [0.35, 0.65) | Confirm: ask the operator | "unclear: inside=... grounded=..." |
| 13 | otherwise | Proceed | "<class> (p=...)" / "inside envelope p=..., grounded p=..." |

The on-car gate and the drop-in library differ only on row 7: on the car a failed envelope
check goes to the marshal as a Confirm, in the library it is a Guide back to the model. On a
Deny the narrator (`portal/backend/narrator.py`) speaks at once: "Someone is in front of me. I
stopped." for a person, "I've lost my eyes. I will not drive blind." for unclear.

The decider is the explanation layer, never the safety layer. The on-car deadman, the hop cap,
the pen lip and the marshal's thumb on the drive-battery switch stop the car without a model.

## Measured latency

From `docs/results/decider-benchmark-2026-10-14.md` (Apple M4 Pro, MPS, booth model
`strands-decider-2B-qwen3.5-v1-2610` with `--vision`): the envelope noul and the frame choice
together cost 490 ms at p50 and 498 ms at p95 (noul 141/144 ms, choice 349/354 ms), the server
holds 5.4 GB and loads in 9.4 s, and it answered all 140 envelope questions correctly with the
deterministic check in the state (110 of 140 without it). Adding the person yes/no to the frame
request cost about 95 ms (`docs/results/decider-calibration-2026-10-14.md`). On the car the full
gate ran 681 to 727 ms per hop and a person was denied in 456 ms
(`docs/results/beats-car-2026-10-15-person-gate/README.md`). Every timed call stayed under the
gate's 1.5 s fail-closed budget.
Text questions on the real 2B decider (`docs/results/decider-text-questions-2026-10-22.md`, 24
labelled cases, 72 timed calls): 462 ms p50 / 498 ms p95 for the three-question request, 0 of 72
over the 1.5 s budget; `args_grounded` grounded cases all at or above 0.78 and invented all at or
below 0.63, so `YES = 0.65` / `NO = 0.35` gave 0 confident errors with 6 unsure answers sent to
Confirm; `inside_envelope` 69/72 right, 0 confident errors; `intent` 66/72 (the `question` class is
never chosen; both misses still ended in Guide via `args_grounded`). Amazon Nova Pro
(`us.amazon.nova-pro-v1:0`) on the same `args_grounded` question: 69/72 right, client p50 797 ms /
p95 4069 ms, 31 of 72 calls over the 1.5 s budget (provider-side p50 391 ms, so the tail is the
network), about 0.13 USD per 1000 decisions at list price via the AWS Price List API; the local
2B is 0 USD marginal after the laptop.

## Links

| Deliverable | Status |
|---|---|
| Repo | https://github.com/Vivek0712/strands-robots-deepracer |
| Article | [ARTICLE URL: pending], source `docs/article/article.md` |
| Video | https://youtu.be/oMHml_LT_tY (2:57, under the 3 minute limit) |

## Originality

This agent is original work, built from 14 October 2026 in a private repository for AWS
Community Day Mumbai (17 October) and for this hackathon, and first published for this
submission; it was not published before the hackathon window opened on 16 October 2026. Two
earlier public repositories by the author are its seeds: `Vivek0712/aws_deepracer_control_v2`
(an HTTP client for the DeepRacer console, 2021) and `Vivek0712/strands-agentic-deepracer` (a
Strands and Nova planner over that client, March 2026); the measured motion constants, the plan
validator and the MJPEG parser carried over from them (`docs/context/07-prior-github-use-case-work.md`).
Neither contains the strands-robots body, the Decider gate, the Bidi voice or the Harness race
engineer. Upstream contributions this agent builds on (strands-labs/robots, strands-decider PR
#10 for the vision path) are cited in the article.

## Pre-submit checklist

- [ ] A1 Decider 2B makes a decision that changes the agent's action (gate.py, patterns/strands)
- [ ] A2 Agent model on Amazon Bedrock (Nova Pro), named in code
- [ ] A3 Article published; the Decider section quotes the questions and options
- [ ] A4 Repo public; URL in this file and in the article
- [ ] A5 patterns/strands/ has _client.py, tool_call_intervention.py, README.md with "How to use"
- [ ] A6 Video under 3 minutes; URL in this file
- [ ] A7 Tags #strands-decider-2b and #guardrails on the article and the form, no second pattern tag
- [ ] A8 Originality statement above is true
- [ ] No secrets, no tracked .env, no photos of bystanders (scanner: `make scan`)
- [ ] `make scan` exits 0
