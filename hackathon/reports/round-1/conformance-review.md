# Conformance review: `patterns/strands/` vs the official strands-decider quickstart

Reviewer: `decider-pattern-conformance-reviewer` (read-only). Date: 2026-10-22.

## Sources compared

| Side | Source | Revision |
|---|---|---|
| Upstream (live) | `https://raw.githubusercontent.com/strands-labs/strands-decider/main/examples/strands/{_client.py,tool_call_intervention.py,README.md}` and `/main/README.md` | fetched 2026-10-22, all four HTTP 200 (6054 / 9451 / 3039 / 22260 bytes); scratch copies under `<scratch>/upstream-example/raw/` |
| Upstream (local) | `~/vision-decider/sd-upstream/examples/strands/` | fork commit `75c9fd3` (2026-10-03). `_client.py` byte-identical to live; `tool_call_intervention.py` differs from live only by black reformatting (lines 130-158); README differs only in the `serve` model id (`hobson-v19` local, `qwen3.5-v1-2610` live) |
| Ours | `patterns/strands/_client.py`, `tool_call_intervention.py`, `frame_intervention.py`, `README.md`; `patterns/README.md` | working tree at `8c320c4` |

WebFetch returned summaries, not verbatim text, so the files were pulled with `curl` and diffed against the local checkout; the local checkout is current except for the two cosmetic diffs above. `docs/context/03-strands-box-deciders-bidi.md` sections 2.4-2.5 agree with the live files.

## Findings

| Severity | File:line | Finding | Why it matters for the rubric | Suggested fix |
|---|---|---|---|---|
| Medium | `patterns/strands/_client.py:91,93,168` | Upstream exposes the server-reported latency as `Decider.last_latency_ms` (`_client.py:68,121` upstream). Ours renames it: `latency_ms` is client-measured, `server_latency_ms` is the server's. A user porting upstream code that reads `decider.last_latency_ms` gets `AttributeError`. | B2.3 "drop-in folder mirroring upstream names"; the README claims the clients are "interchangeable" (`patterns/README.md:7`). A renamed symbol that works is still a mismatch. | Add `@property def last_latency_ms(self): return self.server_latency_ms` (one-line alias), and say so in the module docstring's "Additions here" sentence (`_client.py:15-18`). |
| Medium | `patterns/strands/_client.py:37` ; `patterns/strands/README.md:87` ; `tool_call_intervention.py:379` | Upstream's endpoint override is `ENV_URL = "STRANDS_DECIDER_URL"` (`_client.py:31` upstream; README line 6; docstring line 37). Ours sets `ENV_URL = "DECIDER_URL"`. Code does honour `STRANDS_DECIDER_URL` as a fallback (`_client.py:45`), but neither the pattern README (`Env overrides: DECIDER_URL, DECIDER_MODEL, BEDROCK_MODEL_ID`) nor the `--url` help text mentions it. | A judge who sets `STRANDS_DECIDER_URL` as the upstream README tells them to will find it works but undocumented; a grep for the upstream env var finds it only in a docstring. | Document both in `patterns/strands/README.md:87` ("`DECIDER_URL` (or upstream's `STRANDS_DECIDER_URL`)") and in the `--url` help string. |
| Low | `patterns/strands/README.md`, `patterns/README.md` | Tag `#guardrails` appears (`patterns/README.md:14-15`, `patterns/strands/README.md:11`) but `#strands-decider-2b` appears in neither pattern README; it is only in the root `README.md:290`. The brief's checklist asks for both tags in the pattern README files. | A7 and the AI first-pass scorer key on `#strands-decider-2b`; the pattern folder is the file a judge opens first for A5. | Add one line to `patterns/strands/README.md` (after the title): "Tags: `#strands-decider-2b` `#guardrails`." |
| Low | `patterns/strands/README.md:80-87` | Upstream README has an explicit prerequisites paragraph (AWS credentials with Bedrock access, link to the Strands Bedrock provider docs) and an install line (`pip install -e . strands-agents`, lines 7-16). Ours shows `AWS_PROFILE=<profile> python ...` but never says how to install `strands-decider` or `strands-agents`. | B3.3 / A5 "a stranger can copy one folder": the stranger needs `pip install strands-decider strands-agents`. | Add two lines under "Run it against a real decider and Bedrock": `pip install strands-decider strands-agents` and "AWS credentials with Bedrock access must be in the environment". |
| Low | `patterns/strands/_client.py:43,52` ; README `:72,83` | Default port 8111 vs upstream 8099 (`_client.py:45` upstream; README line 5); `SERVE_HINT` adds `--vision`. Intentional (whole project stack is on 8111; vision is required by `FrameGate`) and consistently documented. | A judge following the upstream README's `--port 8099` and then running our file gets `ServerUnavailable` with the correct hint, so this self-corrects. | None required; optionally note "upstream uses 8099" in the README env line. |
| Low | `patterns/strands/frame_intervention.py:68` | The vision recipe's question set is `FRAME_QUESTIONS`, not `QUESTIONS`. `grep QUESTIONS` still hits (substring), and `tool_call_intervention.py:68` has the literal `QUESTIONS`. | A5 lists "a `QUESTIONS` dict". Satisfied by `tool_call_intervention.py`; a judge reading `frame_intervention.py` alone sees a different name. | Optional: `QUESTIONS = FRAME_QUESTIONS` alias after line 78, or rename. |
| Info | `patterns/strands/tool_call_intervention.py:190` | Upstream's message flattener is `_render` (`:98` upstream); ours is public `render`. | Nobody scans for this. | None. |
| Info | `patterns/strands/tool_call_intervention.py:155,166` | Handler class `MotionGate` / `name = f"{NAME}-motion-gate"` vs upstream `ToolCallReviewer` / `f"{NAME}-tool-call-reviewer"` (`:82,91` upstream). Renamed for the domain; the brief explicitly allows `MotionGate` and the scanner matches `class \w+\(.*InterventionHandler.*\)`. | None. | None. |
| Info | `patterns/strands/_client.py:48` | `MODEL_ID` is the real HF id `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` (env-overridable) where upstream still ships `MODEL_ID = "hobson-latest"` (`:41` upstream). Ours is the better token for the scanner: `scan_submission.py`'s `StrandsAgents/strands-decider-2B` marker does not fire on the upstream `.py` files but does on ours. | Positive for A1 / B2.3. | None. |
| Info | `patterns/strands/tool_call_intervention.py:53-60` | Import block matches the brief and the scanner: `from strands import Agent, tool`, `from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed`, `from strands.models import BedrockModel`, then `from _client import NAME, Decider, ServerUnavailable` (with a package-relative first attempt). Upstream puts `_client` first and imports only `Guide, InterventionHandler, Proceed`. The scanner regex `from\s+strands\.interventions\s+import\s+.*` matches both. | Ours imports all four actions, so the scanner's `intervention_handler` check is PASS for us where it is WARN for upstream itself. | None. |

## Conformance table

| Item | Upstream (file:line) | Ours (file:line) | Verdict | Fix |
|---|---|---|---|---|
| File `_client.py` | `examples/strands/_client.py` | `patterns/strands/_client.py` | present | |
| File `tool_call_intervention.py` | `examples/strands/tool_call_intervention.py` | `patterns/strands/tool_call_intervention.py` | present | |
| File `README.md` | `examples/strands/README.md` | `patterns/strands/README.md` | present | |
| File `frame_intervention.py` | (none upstream; brief's vision variant) | `patterns/strands/frame_intervention.py` | present | |
| File `patterns/README.md` | (none upstream) | `patterns/README.md` | present | |
| `NAME = "strands-decider"` | `_client.py:28` | `_client.py:34` | match | |
| `ENV_URL` | `"STRANDS_DECIDER_URL"` `_client.py:31` | `"DECIDER_URL"` `_client.py:37`; upstream name honoured as fallback `:45` | renamed, fallback kept, undocumented in README | document `STRANDS_DECIDER_URL` in README:87 and `--url` help |
| `ENV_MODEL` | (none) | `"DECIDER_MODEL"` `_client.py:40` | addition | |
| `MODEL_ID` | `"hobson-latest"` `_client.py:41` | `"StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"` (env-overridable) `_client.py:48` | changed, with reason (real id; scanner marker) | |
| `DEFAULT_PORT` / `DEFAULT_URL` | `8099` / `os.environ.get(ENV_URL, ...)` `_client.py:45-46` | `8111` / env chain `_client.py:43-46` | changed, with reason (project stack) | |
| `SERVE_HINT` | `"strands-decider serve <checkpoint> --port 8099"` `:34` | `f"{NAME} serve {MODEL_ID} --vision --port {DEFAULT_PORT}"` `:52` | changed (concrete, `--vision`) | |
| `class ServerUnavailable(RuntimeError)` | `_client.py:49` | `_client.py:59` | match | |
| `class Decider` | `_client.py:53` | `_client.py:72` | match | |
| `Decider.__init__(url=DEFAULT_URL, timeout=120.0)` | `:60` | `:85` | match | |
| `Decider.noul(instructions, criteria=None) -> {"type":"noul","instructions",["criteria"]}` | `:73-84` | `:97-108` | match | |
| `Decider.choice(instructions, criteria) -> {"type":"choice","instructions","criteria"}` | `:86-93` | `:109-118` (+ `ValueError` if < 2 options) | match (+ client-side check mirroring `harness/fake_decider.py:142`) | |
| `Decider.score(instructions, criteria) -> {"type":"score","instructions","criteria":[...]}` | `:95-98` | `:120-126` (+ `ValueError` outside 2..10) | match (+ check mirroring `fake_decider.py:145`) | |
| `ask(state, questions)` body `{"state","model","questions"}` | `:106-109` | `:133-148` (+ optional `"images"` `:150`) | match, extended | |
| POST `{url}/v1/systemone`, `content-type: application/json` | `:112` | `:152-154` | match | |
| `ask` returns `payload["answers"]` | `:122` | `:169` | match | |
| `usage.input_tokens` accumulated | `:120` | `:166-167` | match | |
| server `latency_ms` field | `self.last_latency_ms` `:68,121` | `self.server_latency_ms` `:93,168`; `self.latency_ms` is client-measured `:91,162` | renamed | add `last_latency_ms` alias |
| errors folded into `ServerUnavailable` | `URLError` only `:117,129` | `URLError, TimeoutError, ValueError, OSError` + body-without-`answers` `:160-164,176` | match, extended (fail-closed) | |
| `health()` GET `/health`, timeout 10 | `:124-130` | `:171-180` | match | |
| `banner()`, `__str__` | `:132-141` | `:182-190` | match (fields differ: `vision` vs `max_length`) | |
| stdlib only (`urllib`, `json`) | `:19-24` | `:23-30` (`base64`, `time` added) | match | |
| `from _client import NAME, Decider, ServerUnavailable` | `tool_call_intervention.py:45` | `:58,60` (relative then plain) | match | |
| `from strands import Agent, tool` | `:46` | `:53` | match | |
| `from strands.interventions import ...` | `Guide, InterventionHandler, Proceed` `:47` | `Confirm, Deny, Guide, InterventionHandler, Proceed` `:54` | match, extended | |
| `from strands.models import BedrockModel` | (none; passes a model-id string `:205`) | `:55` | addition (matches the brief's import list and the scanner's `BedrockModel` marker) | |
| module-level `QUESTIONS` dict from `Decider.noul/choice` | `:56-74` (2 noul) | `:68-98` (2 noul + 1 choice) | match | |
| `YES` float with "policy knob, owned by the code" comment | `YES = 0.45` `:73-76` | `YES = 0.65` `:95-100` (calibration cited) | match | |
| `class <Gate>(InterventionHandler)` with `name` | `ToolCallReviewer` `:82,91` | `MotionGate` `:155,166`; `FrameGate` `frame_intervention.py:97,109` | renamed (allowed by brief) | |
| `def before_tool_call(self, event, **kwargs)` | `:108` | `tool_call_intervention.py:212`; `frame_intervention.py:133` | match | |
| reads `event.tool_use["name"]`, `event.tool_use.get("input")`, `event.agent.messages` | `:109-114` | `:213-217` (`.get("name")`, `getattr(event.agent, "messages", [])`) | match | |
| returns `Proceed()` / `Guide(feedback=...)` | `:132-150` | `:216,234,255-284` (+ `Confirm(prompt=...)`, `Deny(reason=...)`) | match, extended; signatures verified against strands-agents 1.60.0 (`Guide(feedback, reason)`, `Deny(reason)`, `Confirm(prompt, reason, ...)`) | |
| `ServerUnavailable` handling | propagates (no try) | `Deny(reason=DECIDER_UNAVAILABLE)` `:231-234`; `on_error -> "deny"` `:184-187` | extended (brief requires Deny) | |
| `self.log` list of dict records | `:95,152` | `:179,235,245` (+ `latency_ms`) | match | |
| `Agent(model=..., tools=[...], interventions=[gate], system_prompt=..., callback_handler=None)` | `:204-210` | `:350-358` | match | |
| Bedrock model id in `main()` | `"us.anthropic.claude-haiku-4-5-20251001-v1:0"` `:205` | same, via `BedrockModel(model_id=os.environ.get("BEDROCK_MODEL_ID", ...), region_name="us-east-1")` `:351-354` | match | |
| `--url` flag | (none; env var only) | `:379` | addition | mention `STRANDS_DECIDER_URL` in help |
| `--offline` flag | (none) | `:378` | addition | |
| `images=[<base64>]` on `ask` | (none; root README documents `--vision`) | `_client.py:135,150`; `frame_intervention.py:157` | addition | |
| Question types exactly `noul`, `choice`, `score` | `_client.py:80,92,97` | `_client.py:104,118,126` | match | |
| Five frame classes `clear, obstacle_near, person_in_frame, off_surface, unclear` | (project contract) | `frame_intervention.py:60-66` | present | |
| README: run command | `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099` then `python examples/strands/tool_call_intervention.py` (README:16-18) | `make fake-decider` + `make pattern-demo` (`README.md:72-74`); `strands-decider serve ... --vision --port 8111` + `python patterns/strands/tool_call_intervention.py` (`:83-84`) | match | |
| README: install / prerequisites | `pip install -e . strands-agents`; AWS credentials paragraph (README:7-15) | not stated | missing | add install line + AWS prerequisite sentence |
| README: how to swap questions and tools | implied by "choose your own" caveat (README:49-51) | `patterns/README.md:21-47` "Drop-in procedure" steps 1-3; `patterns/strands/README.md:89-94` YES knob | present | |
| README: tags | (none) | `#guardrails` present (`patterns/README.md:14`, `patterns/strands/README.md:11`); `#strands-decider-2b` absent from both pattern READMEs (root `README.md:290` only) | partial | add tags line |
| README: safety line | (none) | `patterns/strands/README.md:124-130`; `patterns/README.md:59-60` | present | |
| README: typed questions printed as JSON | prose list (README:28-30) | ` ```json ` blocks `patterns/strands/README.md:17-52` | present (scanner `json_printed` = True) | |

## Scanner sanity check (does `hackathon/scan_submission.py` recognise the upstream example?)

A scratch repo was built at `<scratch>/upstream-example/repo/` with the three live upstream files under `patterns/strands/` and the upstream root README, then `.venv/bin/python -I hackathon/scan_submission.py --repo <scratch> --no-pytest` was run (JSON at `.../scratchpad/upstream-example/scan-upstream.json`). Decider-relevant results:

| Check | Upstream example | Note |
|---|---|---|
| Decider 2B usage (gate) | PASS | 5/7 markers: `/v1/systemone` (`_client.py:112`), `strands-decider` (10 hits), `"noul"`, `"choice"`, `"score"`. Not found: `strands_decider`, `StrandsAgents/strands-decider-2B` (upstream `MODEL_ID` is `"hobson-latest"`). |
| InterventionHandler wiring (gate) | WARN | subclass `tool_call_intervention.py:82`, hook `:108` found; only `Guide, Proceed` imported, so the "import 3+ actions" heuristic warns. Expected: upstream really does import two. |
| Amazon Bedrock pairing (gate) | PASS | `anthropic.claude`, `us.anthropic` at `:205`. |
| Reusable decision pattern folder (gate) | WARN | all three files present; README has no "how to use"/"drop" wording and no ```json block. |

Conclusion: the scanner keys on the right tokens. It passes the official example on the two name-based gates (Decider usage, Bedrock) and finds the handler; its two WARNs are places where our pattern deliberately exceeds upstream (four actions imported, JSON question blocks, drop-in section), not false negatives. The `StrandsAgents/strands-decider-2B` marker would miss any entry that copied upstream's `MODEL_ID = "hobson-latest"` verbatim; ours carries the real id, so it fires for us.

## Grep output (brief's required command)

```
$ grep -rn "v1/systemone\|InterventionHandler\|before_tool_call\|QUESTIONS\|^YES\|ServerUnavailable\|MODEL_ID" patterns/
patterns/README.md:4:wiring that puts it in the agent's path (a Strands `InterventionHandler`), and a note on
patterns/strands/tool_call_intervention.py:54:from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed
patterns/strands/tool_call_intervention.py:58:    from ._client import NAME, Decider, ServerUnavailable
patterns/strands/tool_call_intervention.py:60:    from _client import NAME, Decider, ServerUnavailable
patterns/strands/tool_call_intervention.py:68:QUESTIONS: dict[str, dict[str, Any]] = {
patterns/strands/tool_call_intervention.py:100:YES = 0.65
patterns/strands/tool_call_intervention.py:155:class MotionGate(InterventionHandler):
patterns/strands/tool_call_intervention.py:212:    def before_tool_call(self, event, **kwargs):
patterns/strands/tool_call_intervention.py:225:            answers = self._decider.ask(state, QUESTIONS)
patterns/strands/tool_call_intervention.py:231:        except (ServerUnavailable, KeyError, TypeError, ValueError) as exc:
patterns/strands/frame_intervention.py:50:from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed
patterns/strands/frame_intervention.py:68:FRAME_QUESTIONS: dict[str, dict[str, Any]] = {
patterns/strands/frame_intervention.py:97:class FrameGate(InterventionHandler):
patterns/strands/frame_intervention.py:133:    def before_tool_call(self, event, **kwargs):
patterns/strands/frame_intervention.py:157:            answers = self._decider.ask(state, FRAME_QUESTIONS, images=[frame])
patterns/strands/README.md:10:| `_client.py` | stdlib `Decider`: `noul`, `choice`, `score`, `ask(state, questions, images=None)`, `health()`, `latency_ms`, `ServerUnavailable` |
patterns/strands/_client.py:48:MODEL_ID = os.environ.get(ENV_MODEL, "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610")
patterns/strands/_client.py:59:class ServerUnavailable(RuntimeError):
patterns/strands/_client.py:131:        return ServerUnavailable(f"no {NAME} at {self.url} ({exc}). Start one with:\n    {SERVE_HINT}")
patterns/strands/_client.py:148:        request_body: dict[str, Any] = {"state": state, "model": MODEL_ID, "questions": dict(questions)}
patterns/strands/_client.py:152:            f"{self.url}/v1/systemone",
(further hits in docstrings and demo code omitted; full output identical to the run on 2026-10-22)
```

Import checks (no network): `import patterns.strands._client` -> `NAME=strands-decider`, `MODEL_ID=StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, `DEFAULT_URL=http://127.0.0.1:8111`, `ENV_URL=DECIDER_URL`; `tool_call_intervention` -> `YES=0.65`, `QUESTIONS` keys `args_grounded, inside_envelope, intent`, `MotionGate.name=strands-decider-motion-gate`; `frame_intervention` -> `FrameGate.name=strands-decider-frame-gate`, keys `frame, person`. `python patterns/strands/tool_call_intervention.py --help` prints `--offline` and `--url`. Installed `strands-agents` is 1.60.0; `strands.interventions` exports `Confirm, Deny, Guide, InterventionHandler, Proceed`, and `InterventionHandler` has `name`, `on_error`, `before_tool_call`.

## Scores (0-5)

| Area | Score | Reason |
|---|---|---|
| File-name conformance | 5 | `_client.py`, `tool_call_intervention.py`, `README.md` exactly as upstream, plus `frame_intervention.py` and `patterns/README.md` as the brief requires. |
| API-name conformance | 4 | Every scanned name matches (`Decider.noul/choice/score`, `ask`, `health`, `NAME`, `MODEL_ID`, `ServerUnavailable`, `QUESTIONS`, `YES`, `before_tool_call`). Two renames: `last_latency_ms` -> `latency_ms`/`server_latency_ms`, `ENV_URL` `STRANDS_DECIDER_URL` -> `DECIDER_URL` (fallback kept). |
| Request-shape conformance | 5 | `{"state","model","questions"[,"images"]}` to `/v1/systemone` with `content-type: application/json`; builders emit exactly the shapes `harness/fake_decider.py validate()` (lines 124-157) accepts, with the 2-option / 2..10-level rules mirrored client-side. |
| InterventionHandler contract | 5 | `name`, `before_tool_call(self, event, **kwargs)`, all four actions with the 1.60.0 keyword names, `on_error = "deny"`, `ServerUnavailable` -> `Deny`, `Agent(model=BedrockModel(...), tools=[...], interventions=[gate])`. |
| Documentation of use | 4 | Run commands (fake and real), JSON question blocks, decision tables, YES knob, drop-in procedure and safety line present. Missing: install line and AWS prerequisite sentence, `#strands-decider-2b` tag in the pattern READMEs, `STRANDS_DECIDER_URL` mention. |

## Mismatches ranked by how likely an automated judge is to notice

1. `#strands-decider-2b` is absent from `patterns/strands/README.md` and `patterns/README.md` (only `#guardrails` is there). A tag grep scoped to the pattern folder misses the hackathon tag. One-line fix.
2. `STRANDS_DECIDER_URL` (the upstream env var, named in the upstream README and docstring) is honoured in code (`_client.py:45`) but documented nowhere in our READMEs or `--url` help; a judge grepping for the upstream name finds only a docstring. One-line fix in `README.md:87` and `tool_call_intervention.py:379`.
3. `Decider.last_latency_ms` renamed to `latency_ms` / `server_latency_ms` (`_client.py:91,93,168`): the only attribute an upstream-based snippet would break on. Add an alias property.
4. No `pip install strands-decider strands-agents` line and no AWS-credentials prerequisite sentence in `patterns/strands/README.md`, where upstream's README has both.
5. `frame_intervention.py` names its dict `FRAME_QUESTIONS` rather than `QUESTIONS` (substring grep still hits; `tool_call_intervention.py:68` has the literal). Optional alias.
6. Default port 8111 and `SERVE_HINT` with `--vision` (upstream 8099, no `--vision`): intentional and self-correcting via the `ServerUnavailable` message; no action.

Nothing was found that a name-matching scanner would miss outright: every token the rubric lists (`/v1/systemone`, `noul`, `choice`, `score`, `before_tool_call`, `QUESTIONS`, `YES`, `InterventionHandler`, `BedrockModel`, `StrandsAgents/strands-decider-2B`) is present in `patterns/strands/*.py` at the lines cited above.
