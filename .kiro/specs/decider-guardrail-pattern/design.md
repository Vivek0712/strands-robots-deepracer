# Design: reusable Strands Decider 2B guardrail pattern

## Components

| Component | File | Role |
|---|---|---|
| `Decider` client (pattern) | `patterns/strands/_client.py` | stdlib `urllib` client for `POST /v1/systemone` and `GET /health`; static builders `Decider.noul`, `Decider.choice`, `Decider.score`; `ask(state, questions)` returns `payload["answers"]`; raises `ServerUnavailable`; constants `NAME`, `MODEL_ID` |
| Text guardrail (pattern) | `patterns/strands/tool_call_intervention.py` | `QUESTIONS` dict, `YES = 0.65`, `MotionGate(InterventionHandler)` with `before_tool_call`; renders `event.agent.messages` plus the proposed tool call into `state`; returns `Proceed` / `Guide` / `Confirm` / `Deny`; `Agent(model=..., tools=[...], interventions=[gate])` example in `main()` |
| Vision guardrail (pattern) | `patterns/strands/frame_intervention.py` | `FrameGate`, same contract with `images=[b64]`: a person `noul` and a five-way `choice` over one frame |
| Pattern docs | `patterns/strands/README.md`, `patterns/README.md` | how to run against `make fake-decider`, how to swap in your own questions and tools |
| Project gate | `src/deepracer_agent/gate.py` | `DeciderGate(InterventionHandler)`: `Envelope`, `envelope_context`, `ask_frame_questions`, `combine_frame_answers`, `Verdict`, `Decision`, `warm_gate`, `BargeInStop` |
| Project client | `src/deepracer_agent/decider_client.py` | `DeciderClient` (httpx, 1.5 s budget, one request in flight per process and across processes, cooldown after timeout), `DeciderUnavailable` |
| Fake decider | `harness/fake_decider.py` | same wire shape; answers from the shared frame label; `/control` knobs `latency_ms`, `fail`, `noul`, `label` |
| Event log | `src/deepracer_agent/events.py` (fallback `gate.LocalEventLog`) | one JSON object per line; `verdict`, `stop`, `approval`, `thought` events |
| Approval | `src/deepracer_agent/runtime.py` `ApprovalBroker` | resolves a `Confirm` from the portal's Approve/Deny or the terminal's `y` |

## Sequence of one gated tool call

```
Agent / BidiAgent                DeciderGate.before_tool_call          DeciderClient            strands-decider serve
      |                                     |                                |                          |
      | tool_use drive_deepracer(l,a,d)      |                                |                          |
      |------------------------------------>| name in GATED_TOOLS?           |                          |
      |                                     | no -> return Proceed()         |                          |
      |                                     | yes:                           |                          |
      |                                     | frame = grab_frame(source)     |                          |
      |                                     | None -> Deny("vision unavailable")                        |
      |                                     | violations = Envelope.violations(l,a,d)                   |
      |                                     | ask_noul(ENVELOPE_QUESTION, envelope_context) ----------->| POST /v1/systemone (noul)
      |                                     |                                |<-------------------------| {"answers": {"q": {"noul": p}}}
      |                                     | envelope_ok = yes and not violations                       |
      |                                     | ask_frame(PERSON_QUESTION, FRAME_QUESTION, classes, jpeg)->| POST /v1/systemone (noul+choice, images)
      |                                     |                                |<-------------------------| {"answers": {"person":..., "frame":...}}
      |                                     | combine_frame_answers -> (cls, p)                          |
      |                                     | ordered decision table (13 rows)                           |
      |                                     | emit verdict per stage (latency_ms)                        |
      |<------------------------------------| Proceed | Guide(feedback) | Confirm(prompt[,response]) | Deny(reason)
      | Deny -> emit stop; tool not run     |                                |                          |
      | Guide -> model re-plans at half linear                               |                          |
      | Confirm -> ApprovalBroker.ask -> operator                           |                          |
      | Proceed -> strands_robots command gate -> driver -> /manual_drive   |                          |
```

Any exception inside the gate is caught in `decide()` and becomes `Deny("vision unavailable")`;
the handler's `on_error` is `"deny"` so an exception Strands sees also denies.

## Data shapes

Request (`DeciderClient._ask_many`):

```json
{"state": {"command": {"tool": "drive_deepracer", "linear": 0.3, "angular": 0.0, "duration": 0.5},
           "envelope": "|linear| <= 0.3 m/s, |angular| <= 1 rad/s, duration <= 2 s, directions: forward or backward",
           "deterministic_check": "ok"},
 "model": "strands-decider-latest",
 "questions": {"q": {"type": "noul", "instructions": "Is this drive command inside the briefed envelope?"}}}
```

Frame request: `state` is `""`, `questions` are `person` (`noul`) and `frame` (`choice` with
`FRAME_CLASS_DESCRIPTIONS` as criteria), `images` is one base64 JPEG (480x360).

Client results: `ask_noul` -> `{"yes": bool, "probability": float, "latency_ms": int}`;
`ask_choice` -> `{"class": str, "probability": float, "latency_ms": int, "probabilities": {...}}`;
`ask_frame` -> `{"person": <noul shape>, "frame": <choice shape>, "latency_ms": int}`.

`Verdict(request_id, stage, action, reason, cls, probability, latency_ms, frame_ref)`;
`Decision(request_id, action, reason, verdicts, args, guided_linear, confirm_prompt)`.
`Decision.to_dict()` is what `AgentRuntime.status()["last_verdict"]` and the portal show.

Pattern library shapes follow the upstream client: `Decider.ask` returns the raw `answers`
dict; the intervention reads `answers["args_grounded"]["noul"]` and compares with `YES`.

## Error handling

| Failure | Where caught | Result |
|---|---|---|
| timeout (> `timeout_s`) | `DeciderClient._ask_many` | `DeciderUnavailable("decider timeout after 1.5s")`, cooldown 8 s, gate `Deny` |
| transport error, non-200 | `_ask_many` | `DeciderUnavailable("decider HTTP <code>: ...")`, gate `Deny` |
| non-JSON body, missing `answers`, missing named answer | `_ask_many` | `DeciderUnavailable`, gate `Deny` |
| `noul` not numeric or outside [0, 1] | `_parse_noul` | `DeciderUnavailable`, gate `Deny` |
| `choice` not in criteria or probabilities malformed | `_parse_choice` | `DeciderUnavailable`, gate `Deny` |
| frame source raises or returns `None`/empty | `grab_frame` | `Deny("vision unavailable")` |
| approval times out | `_ask_operator` | `Confirm(response=False)`, outcome `timeout` logged |
| any other exception in `decide` | `decide` | logged, `Deny("vision unavailable")` |
| MPS server concurrency | `_request_lock`, `_process_lock` | one request in flight per process and across processes; orphan settle 6 s |

Pattern-library equivalents: `ServerUnavailable` for every transport and shape error; the
intervention catches it and returns `Deny` (never `Proceed`).

## Testing strategy

- `tests/unit/test_decider_client.py`: `httpx.MockTransport`, every malformed response.
- `tests/unit/test_gate.py`: decision table rows, most-severe-wins, pinned question strings,
  advisory and off modes, approval paths, `on_error`.
- `tests/unit/test_fake_decider.py`: wire shape and `/control` knobs.
- `tests/unit/test_patterns.py`: pattern library names, `QUESTIONS`/`YES` presence, refusal
  table, offline run against an in-process fake decider.
- `tests/sim/`: fake stack end to end (`make sim`).

## Reference

Upstream names and verbatim excerpts: `docs/context/03-strands-box-deciders-bidi.md` sections
2.4, 2.5, 2.9. Measured latency and model choice: `docs/results/decider-benchmark-2026-10-14.md`.
Threshold calibration: `docs/results/decider-calibration-2026-10-14.md`. Contract:
`docs/dev/CONTRACTS.md` section 7.
