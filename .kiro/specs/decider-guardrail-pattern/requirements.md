# Requirements: reusable Strands Decider 2B guardrail pattern

Spec folder: `.kiro/specs/decider-guardrail-pattern/`. Declared hackathon pattern:
Guardrails ("before a tool call, verify the arguments are grounded in what the user actually
said"). Acceptance criteria use EARS notation as Kiro documents it: "WHEN [condition/event]
THE SYSTEM SHALL [expected behavior]".

## Glossary

- Decider: a Strands Decider 2B server answering `POST /v1/systemone` (`noul`, `choice`,
  `score` questions; `images` with `--vision`).
- Gate: an `strands.interventions.InterventionHandler` whose `before_tool_call` asks the
  decider and returns `Proceed`, `Guide`, `Confirm` or `Deny`.
- Pattern library: `patterns/strands/` (`_client.py`, `tool_call_intervention.py`,
  `frame_intervention.py`, `README.md`) plus the index `patterns/README.md`.
- Project gate: `src/deepracer_agent/gate.py` (`DeciderGate`) with
  `src/deepracer_agent/decider_client.py` (`DeciderClient`).

## Requirement 1: typed questions

User story: As a builder adding a guardrail to my own Strands agent, I want the questions the
decider is asked to be typed (`noul`, `choice`, `score`) and declared in one place, so that I
can read, test and recalibrate them without touching the wiring.

Acceptance criteria:

1. WHEN a developer opens `patterns/strands/tool_call_intervention.py` THE SYSTEM SHALL
   expose a module-level `QUESTIONS` dict whose values are built with `Decider.noul(...)`,
   `Decider.choice(...)` or `Decider.score(...)`.
2. WHEN a question is built with `Decider.choice` THE SYSTEM SHALL require at least two
   options, each with a description string, and reject fewer with a `ValueError`.
3. WHEN a question is built with `Decider.noul` with criteria THE SYSTEM SHALL accept only the
   keys `true` and `false`.
4. WHEN the gate asks about a camera frame THE SYSTEM SHALL use exactly the five classes
   `clear`, `obstacle_near`, `person_in_frame`, `off_surface`, `unclear`.

## Requirement 2: one request per decision

User story: As an operator watching the latency on the Pit Wall, I want every gated tool call
to cost one decider round trip per stage, so that the number on screen is the decision's true
cost and related questions share one encoded state.

Acceptance criteria:

1. WHEN the gate evaluates one tool call THE SYSTEM SHALL send the envelope question in one
   `POST /v1/systemone` and the frame questions (person `noul` plus five-way `choice`) in one
   further `POST` carrying the same image.
2. WHEN a request carries several questions THE SYSTEM SHALL require every named answer in
   the response and treat a missing answer as the whole request failing.
3. WHEN a decision is made THE SYSTEM SHALL record one `verdict` event per stage with
   `request_id`, `stage`, `action`, `reason`, `class`, `probability`, `latency_ms` and
   `frame_ref`.

## Requirement 3: calibrated thresholds

User story: As the person tuning the gate, I want thresholds to be named constants with a
recorded calibration, so that a change is a measured decision and not a feel.

Acceptance criteria:

1. WHEN a developer reads the pattern THE SYSTEM SHALL expose the yes threshold as a single
   module constant named `YES` (pattern library) and `deny_threshold` / `UNCLEAR_THRESHOLD`
   (project gate), with a comment stating that the knob is owned by the code, not the model.
2. WHEN a `choice` answer is thresholded THE SYSTEM SHALL compare the chosen option's own
   probability (`probabilities[choice]`), not the normalised `confidence`.
3. WHEN the person `noul` says yes at or above the deny threshold THE SYSTEM SHALL set the
   class to `person_in_frame` at that probability regardless of the five-way answer, and
   SHALL never lower a five-way answer (monotone toward Deny).
4. WHEN a question string, a class description or a threshold changes THE SYSTEM SHALL have a
   re-run of `python -m deepracer_agent.calibrate_frames` recorded under `docs/results/`.

## Requirement 4: intervention mapping

User story: As a Strands user, I want the decider's probabilities mapped onto the four
interventions the SDK understands, so that the gate composes with any `Agent` or `BidiAgent`
through `interventions=[gate]`.

Acceptance criteria:

1. WHEN the gate's `before_tool_call(self, event, **kwargs)` runs THE SYSTEM SHALL return one
   of `Proceed()`, `Guide(feedback=...)`, `Confirm(prompt=...)` or `Deny(reason=...)` from
   `strands.interventions`.
2. WHEN a tool call is not in the gated set THE SYSTEM SHALL return `Proceed()` without
   calling the decider.
3. WHEN more than one stage produces an action THE SYSTEM SHALL return the first matching row of the ordered
   13-row table (Deny rows, then Guide, then Confirm, then Proceed), never a less severe action.
4. WHEN the deterministic envelope check (`Envelope.violations`) fails THE SYSTEM SHALL return
   at least `Confirm`, whatever the decider said.
5. WHEN an `ApprovalBroker` is attached THE SYSTEM SHALL resolve a `Confirm` inline and hand
   Strands the operator's answer as the response; WHEN none is attached THE SYSTEM SHALL
   return a bare `Confirm` so a plain `Agent` pauses with `stop_reason == "interrupt"`.

## Requirement 5: never fail open

User story: As the marshal, I want a missing or broken decider to refuse motion rather than
allow it, so that the explanation layer never silently disappears.

Acceptance criteria:

1. WHEN the decider times out (default 1.5 s), returns a non-200 status, returns a non-JSON
   body, omits an answer, returns a probability outside [0, 1] or a `choice` not in the
   criteria THE SYSTEM SHALL raise `DeciderUnavailable` (`ServerUnavailable` in the pattern
   library) and the gate SHALL return `Deny` with the reason `vision unavailable`.
2. WHEN no frame is available or the frame is older than 2 s THE SYSTEM SHALL return `Deny`.
3. WHEN the handler itself raises THE SYSTEM SHALL report `on_error == "deny"`.
4. WHEN the operator switches the gate to `advisory` or `off` THE SYSTEM SHALL log that
   choice in every verdict (`advisory: true`, or the `GATE_OFF` reason) and the upstream
   command gate and the on-car deadman SHALL remain in force.

## Requirement 6: offline demo

User story: As a judge or a new contributor without a GPU or a car, I want to run the pattern
end to end on my laptop, so that I can see every verdict without the real model.

Acceptance criteria:

1. WHEN `make fake-decider` is running on port 8111 THE SYSTEM SHALL answer the pattern's
   requests with the same field names as the real server and derive answers from the fake
   console's frame label.
2. WHEN `python -m patterns.strands.tool_call_intervention` (or the documented run command)
   is executed against the fake decider THE SYSTEM SHALL print one verdict per tool call with
   its latency and exit 0.
3. WHEN `/control?fail=1` or `/control?latency_ms=3000` is set on the fake decider THE SYSTEM
   SHALL demonstrate a `Deny` for `vision unavailable`.
4. WHEN the notebook under `notebooks/` is run top to bottom with only the fake services THE
   SYSTEM SHALL complete with outputs saved and no credentials required.

## Requirement 7: test refusal table

User story: As a reviewer, I want one table that lists every input the gate refuses and the
reason it gives, so that the fail-closed behaviour is provable from the tests alone.

Acceptance criteria:

1. WHEN `tests/unit/test_patterns.py` runs THE SYSTEM SHALL include one parametrised test
   listing every refused input (timeout, HTTP 500, non-JSON, missing answer, out-of-range
   probability, unknown choice, no frame) with the exact reason string returned.
2. WHEN `tests/unit/test_gate.py` runs THE SYSTEM SHALL pin the question strings
   `ENVELOPE_QUESTION`, `FRAME_QUESTION`, `PERSON_QUESTION` and the class list, so a change
   fails a test until the calibration is re-run.
3. WHEN `.venv/bin/python -m pytest tests/unit -q` runs THE SYSTEM SHALL pass with no network
   and no real decider.

## Requirement 8: recognisable by the hackathon scanner

User story: As the submitter, I want the pattern to be machine-recognisable as Strands Decider
2B usage, so that the automated first gate reads it correctly.

Acceptance criteria:

1. WHEN the scanner reads `patterns/strands/` THE SYSTEM SHALL find the file names
   `_client.py`, `tool_call_intervention.py`, `README.md`, the names `Decider`, `NAME`,
   `MODEL_ID`, `ServerUnavailable`, `QUESTIONS`, `YES`, `InterventionHandler`,
   `before_tool_call`, and the model id `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`.
2. WHEN the scanner reads the article THE SYSTEM SHALL find the tags `#strands-decider-2b`
   and `#guardrails`, a Bedrock model id, and a clearly marked demo video placeholder.
3. WHEN `hackathon/scan_submission.py --repo . --article docs/article/article.md` runs THE
   SYSTEM SHALL report zero FAIL rows.
