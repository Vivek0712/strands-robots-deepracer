---
inclusion: fileMatch
fileMatchPattern: ["patterns/**", "src/deepracer_agent/gate.py"]
---

# Strands Decider 2B decision patterns

Applies when editing the pattern library (`patterns/`) or the project gate
(`src/deepracer_agent/gate.py`). The upstream reference is
`strands-labs/strands-decider`, `examples/strands/_client.py` and
`examples/strands/tool_call_intervention.py`; the verbatim excerpts are in
`docs/context/03-strands-box-deciders-bidi.md` section 2.4 and 2.5. Mirror those names so a
scanner and a reader both recognise Decider usage.

## The System One request

`POST {DECIDER_URL}/v1/systemone`, JSON body:

```json
{
  "state": "<str | dict | list>",
  "model": "<model id>",
  "questions": {
    "<name>": {"type": "noul",   "instructions": "...", "criteria": {"true": "...", "false": "..."}},
    "<name>": {"type": "choice", "instructions": "...", "criteria": {"<option>": "<description>", ...}},
    "<name>": {"type": "score",  "instructions": "...", "criteria": ["lo", "mid", "hi"]}
  },
  "images": ["<base64 JPEG or data: URI>"]
}
```

Response: `{"model", "answers": {"<name>": ...}, "usage": {"input_tokens", "output_tokens"},
"latency_ms"}`. Answer shapes: `noul` -> `{"type": "noul", "noul": P(true)}`; `choice` ->
`{"type": "choice", "choice": "<option>", "probabilities": {...}, "confidence": c}`; `score` ->
`{"type": "score", "score": s, "legend": {...}, "probabilities": {...}, "confidence": c}`.
`images` needs `strands-decider serve --vision`; up to 4 per request. `GET /health` reports
`status`, `model`, `vision`, `device`.

## Question types

- `noul`: yes/no, returns P(true). Optional `criteria` with `true`/`false` descriptions.
- `choice`: one of N named options with a description each (at least 2). Threshold on the
  chosen option's own probability (`probabilities[choice]`), not on the normalised `confidence`.
- `score`: ordered rubric of 2 to 10 levels; returns the expected level. This project does not
  use `score` in the gate.

Many questions over one `state` are nearly free (the state is encoded once), so send related
questions in one request: the gate sends the person `noul` and the five-way `choice` over the
same frame in a single POST (`DeciderClient.ask_frame`), and never acts on one answer when it
asked for two.

## Names to keep

- `patterns/strands/_client.py`: `Decider` with static builders `Decider.noul(instructions,
  criteria)`, `Decider.choice(instructions, criteria)`, `Decider.score(instructions, levels)`,
  methods `.ask(state, questions)` and `.health()`, constants `NAME` and `MODEL_ID`
  (default `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, env-overridable), exception
  `ServerUnavailable`. Imports are `from _client import NAME, Decider, ServerUnavailable` with a
  package-relative fallback, as upstream does.
- `patterns/strands/tool_call_intervention.py`: a module-level `QUESTIONS` dict, a `YES`
  threshold constant (`YES = 0.65`, the policy knob, owned by the code, not the model), the
  `InterventionHandler` subclass `MotionGate` (vision variant: `FrameGate` in
  `frame_intervention.py`) whose `before_tool_call(self, event, **kwargs)` returns
  `Proceed()`, `Guide(feedback=...)`, `Confirm(...)` or `Deny(...)`, and an
  `Agent(model=..., tools=[...], interventions=[gate])` wiring example.
- Project gate: `DeciderGate`, `Verdict`, `Decision`, `Envelope`, `DeciderClient`,
  `DeciderUnavailable`; question strings `ENVELOPE_QUESTION`, `FRAME_QUESTION`,
  `PERSON_QUESTION`; `FRAME_CLASSES` exactly
  `("clear", "obstacle_near", "person_in_frame", "off_surface", "unclear")`.

## Proceed / Guide / Confirm / Deny mapping (the decision table)

Rows are checked in this order; the first matching row is the action (`docs/dev/CONTRACTS.md`
section 7; `gate.py` module docstring; `patterns/strands/README.md`). Thresholds: `YES = 0.65`,
`NO = 0.35` (text questions), `PERSON = 0.5`, `UNCLEAR = 0.65` (`UNCLEAR_THRESHOLD`, env
`DEEPRACER_UNCLEAR_THRESHOLD`), budget 1.5 s.

| # | Condition | Action | Reason string |
|---|---|---|---|
| 1 | decider unreachable, timeout (> 1.5 s), malformed answer (missing key, probability outside [0, 1] or NaN, unknown class) | `Deny` | "decider unavailable" (text request) / "vision unavailable" (frame request); on the car both say "vision unavailable" |
| 2 | no camera frame | `Deny` | "vision unavailable" |
| 3 | person >= 0.5, or frame class `person_in_frame` | `Deny` | "person in frame" |
| 4 | frame class `off_surface` | `Deny` | "off the surface" |
| 5 | frame class `unclear` with p >= 0.65 | `Deny` | "cannot see clearly" |
| 6 | intent `stop` with p >= 0.65 | `Deny` | "the user asked to stop" |
| 7 | deterministic envelope check fails (code, not the model) | drop-in: `Guide` "re-plan inside the envelope"; ON THE CAR: `Confirm` (the marshal's thumb: the operator may approve a bigger hop) | "outside envelope: <violations>" |
| 8 | `inside_envelope` < 0.35 | `Guide`: re-plan inside the envelope | "outside envelope per decider (p=...)" |
| 9 | `args_grounded` < 0.35 | `Guide`: ask the user for the values instead of inventing them | "arguments not grounded (p=...)" |
| 10 | intent `question` or `unrelated` with p >= 0.65 | `Guide`: answer the user instead of moving | "intent <x> (p=...)" |
| 11 | frame class `obstacle_near` | `Guide`: halve the speed and re-plan the hop | "obstacle_near (p=...)" |
| 12 | `inside_envelope` or `args_grounded` in [0.35, 0.65) | `Confirm`: ask the operator | "unclear: inside=... grounded=..." |
| 13 | otherwise | `Proceed` | "<class> (p=...)" / "inside envelope p=..., grounded p=..." |

Deterministic checks live in code next to the decider (`Envelope.violations`); a numeric
overshoot is never left to a classifier alone. Thresholds are calibrated, not guessed: re-run
`python -m deepracer_agent.calibrate_frames` before changing `FRAME_CLASS_DESCRIPTIONS`, any
question string or a threshold (`docs/results/decider-calibration-2026-10-14.md` records why).

## Never fail open

No decider means Deny. A timeout, an HTTP error, a non-JSON body, a missing or malformed
answer, a probability outside [0, 1], or a `choice` not in the criteria all raise
`DeciderUnavailable` and the gate returns `Deny`. The handler's `on_error` is `"deny"`. There
is no fallback that proceeds because the server was unreachable; an operator may switch the
gate to `advisory` or `off` on purpose, and that choice is logged as such. Physics stops the
car; the decider explains.

## Every decision is one request and one event

One drive command produces one envelope request and one frame request, each written to the
event log as a `verdict` with `request_id`, `stage`, `action`, `reason`, `class`,
`probability`, `latency_ms` and `frame_ref`. Tests for a pattern include a refusal table: one
parametrised test listing every input the gate refuses and the reason string it returns.
