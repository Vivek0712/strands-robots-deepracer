# Section C: Strands Agents and the Harness SDK (6 slides)

Fragment: `sections/03-agents-harness.html`. Assets: `assets/03/`. Written 2026-10-17; every number
below was read on that date.

## Sources used

| Source | What it confirmed |
|---|---|
| https://pypi.org/project/strands-agents/ | latest 1.61.1, released 15 Oct 2026; description "A model-driven approach to building AI agents in just a few lines of code"; Python >= 3.10; `pip install strands-agents` |
| https://pypi.org/project/strands-harness/ | latest 0.3.1, 15 Oct 2026; "a batteries-included agent in one call, built on the Strands Harness SDK"; Python >= 3.10; memory under `./.agent/memory`; `.cedar` needs `pip install 'strands-agents[cedar]'` |
| https://github.com/strands-agents/harness-sdk/releases | tags python/v1.61.1 and harness-python/v0.3.1 (15 Oct), typescript/v1.21.0, harness-typescript/v0.3.0, harness-cli/v0.2.1 (14 Oct), python/v1.60.0 (12 Oct) |
| https://api.github.com/repos/strands-agents/harness-sdk (review, 2026-10-17) | stargazers_count 8842, license Apache-2.0 |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/{python/v1.60.0,python/v1.61.1,main}/strands-py/src/strands/experimental/bidi/__init__.py (review, 2026-10-17) | the `strands.experimental.bidi` shim still exists at all three refs and still warns "deprecated and will be removed in v1.60.0"; the python/v1.60.0, v1.61.0 and v1.61.1 release notes list no removal; the installed 1.60.0 in `.venv` imports it with that same DeprecationWarning |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/main/strands-py/src/strands/sandbox/__init__.py (review) | `PosixShellSandbox` is exported from `strands.sandbox` as the abstract base to subclass; the two sandbox docs pages do not name it |
| https://strandsagents.com/docs/user-guide/sdk/sandbox/ (review) | "Omitting the sandbox parameter runs the agent's command and file tools directly on the host with the full permissions of the agent process" |
| https://github.com/strands-agents/harness-sdk (README) | "Strands Agents is an open-source SDK for building and running AI agents in Python and TypeScript"; packages strands-py, strands-ts, harness-py, harness-ts, strands-cli, strands-mcp, site, team; `pip install strands-agents strands-agents-tools`, `pip install strands-harness`, `npm install @strands-agents/sdk`; Apache-2.0; 8.8k stars |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/main/harness-py/README.md | definition paragraph ("gets you a capable, ready-to-work agent in one call ... what you get back is a plain `strands.Agent`"); the `create_harness(...)` interface with `interventions="ask" | "smart" | policy string | .cedar file`; "What you get by default" (tuned prompt: explore before changing, confirm before anything irreversible, verify before done; eight built-in tools); "Long-term memory" (`./.agent/memory`, `search_memory`, flush at shutdown); "Tracing" (`OTEL_TRACES_EXPORTER`, "touches telemetry not at all" when unset); "Requiring approval for tool calls" (subagent children inherit the policy, `programmatic_tool_caller` calls are gated too; environment plugin reads through the sandbox "whether the agent runs locally, in Docker, or over SSH") |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/main/harness-py/src/strands_harness/agent.py | `create_harness(..., interventions=..., **agent_kwargs)`; `sandbox` is forwarded to `Agent` through `agent_kwargs` and to subagent children; `_drop_sandbox_tools` because the built-ins already route through the sandbox |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/main/strands-cli/README.md | `npm install -g @strands-agents/cli`; `--interventions <policy>` ("ask, smart, a .cedar policy file, or a natural-language rule"); `--acp-server` |
| https://strandsagents.com/docs/user-guide/sdk/ | "An agent harness is the software around a model that turns it into an agent." / "The Strands Harness SDK is for building one yourself, end to end."; navigation URLs for every page below |
| https://strandsagents.com/docs/user-guide/sdk/agents/agent-loop/ | loop description (invoke model, check for tool request, execute, re-invoke until final response); diagram labels Request / Model decides next step / Tools execute tool calls / Response / "Every pass adds to the conversation history"; stop reasons; `agent.cancel()` |
| https://strandsagents.com/docs/user-guide/sdk/quickstart/python/ | `pip install strands-agents`; Bedrock default; Anthropic, OpenAI, Gemini, Ollama examples; the `letter_counter` `@tool` example and `Agent(tools=[letter_counter, file_editor])` |
| https://strandsagents.com/docs/user-guide/sdk/agents/interventions/ | definition ("composable control layer ... typed decisions"); action table (exact wording): Proceed "Allow the operation to continue unchanged", Deny "Block the operation. Short-circuits remaining handlers", Guide "Cancel and provide feedback for the model to retry with", Confirm "Pause for human approval", Transform "Modify event content in-place before execution continues"; lifecycle methods (`before_tool_call` etc.); Confirm only on `before_tool_call`; `on_error` throw/proceed/deny; `from strands.interventions import ...` |
| https://strandsagents.com/docs/user-guide/sdk/agents/interventions/cedar-authorization/ | "evaluates Cedar policies before each tool call"; default-deny, fail-closed; `pip install strands-agents[cedar]`; `from strands.vended_interventions.cedar import CedarAuthorization`; options `policies`, `entities`, `principal_resolver`, `context_enricher`, `on_error`; Action = tool name, `context.input` = tool arguments, `context.session` = `hour_utc`, `call_count`, enricher fields |
| https://strandsagents.com/docs/user-guide/sdk/agents/interventions/human-in-the-loop/ | `HumanInTheLoop` pauses before a tool runs; modes interrupt/resume, `ask="stdio"`, custom callback; negated tools always ask; trust |
| https://strandsagents.com/docs/user-guide/sdk/agents/hooks/ | hooks "add logging, validation, guardrails, or custom logic at any point in the agent loop"; events BeforeInvocationEvent, BeforeToolCallEvent, AfterToolCallEvent, BeforeModelCallEvent, AfterInvocationEvent; `agent.add_hook(callback)` |
| https://strandsagents.com/docs/user-guide/sdk/sandbox/available-sandboxes/ | DockerSandbox (docker exec into a running container) and SshSandbox (fresh ssh process per command, key-based auth, BatchMode, `host`, `working_dir`, `identity_file`, `port`, `allow_unknown_hosts`, `ssh_options` allowlist); both register sandbox shell and file-editor tools; `Agent(sandbox=sandbox)`; base class PosixShellSandbox; omitting sandbox runs tools on the host (from the sandbox overview via search result) |
| https://strandsagents.com/docs/user-guide/sdk/bidi/ | BidiAgent "holds a persistent connection to a realtime model for the whole conversation"; user can "talk over the agent (barge in)"; providers Nova Sonic, Gemini Live, OpenAI Realtime; Python only |
| https://strandsagents.com/docs/user-guide/sdk/bidi/events/ | `BidiBargeInEvent` "signals an interruption to model output"; "Clear buffered audio as soon as the event arrives so playback stops promptly"; `AudioIO.output()` does this automatically |
| https://strandsagents.com/docs/user-guide/sdk/bidi/quickstart/ | `pip install "strands-agents[bidi,bidi-io,bidi-pyaudio,bidi-aec]"`; Python 3.12 or later; model id `amazon.nova-2-5-sonic` |
| https://strandsagents.com/docs/user-guide/sdk/bidi/interrupts/ | note: this page is an "In development" stub (issue #3981); barge-in facts come from the overview and events pages instead |
| https://strandsagents.com/docs/user-guide/harness/ | "Strands harness is a state-of-the-art, fully assembled agent harness"; `pip install strands-harness`; what the default harness does (models, prompting, tools, context, memory and sessions, delegation, extensions); harness vs Harness SDK positioning |
| https://strandsagents.com/docs/user-guide/harness/quickstart/ | Python 3.10+; Bedrock default and credentials; `session={"id": ...}` under `./.agent/sessions` |
| https://strandsagents.com/docs/user-guide/harness/reference/configuration/ | full option table; default model `bedrock/global.anthropic.claude-opus-5`; built-in tools shell, read, write, edit, web_fetch, web_search, programmatic_tool_caller, subagent; built-in plugins todos, environment |
| https://strandsagents.com/docs/user-guide/harness/composing-with-sdk/ | factory resolves options into SDK objects and constructs a plain `Agent`; passthrough; `HumanInTheLoop()` example; when to use harness vs SDK |
| https://raw.githubusercontent.com/strands-agents/harness-sdk/main/site/src/styles/diagrams.css | the official diagram design system (dg-* classes) used to recolour the downloaded SVGs |
| Local: `docs/context/08-harness-sdk.md` | the project rule ("The harness is not the driving loop ... The harness is the race engineer"), the sandbox seam, interventions sugar, subagent inheritance |
| Local: `docs/context/03-strands-box-deciders-bidi.md` | bidi GA at 1.57.2 (2026-10-01); `strands.experimental.bidi` shim warning "will be removed in v1.60.0"; Nova Sonic Python 3.12+; BidiBargeInEvent and AudioIO behaviour |
| Local: `docs/context/01-strands-robots-code-deepdive.md` section 1.4 | `_command_gate`: one owner of operator approval for every transport; blocklist incl. `/cmd_vel`, `/manual_drive`, `/vehicle_state`, `/enable_state`; `tool_context.interrupt(...)`; `STRANDS_ROS2_COMMAND_ALLOW` |
| Local: `CLAUDE.md` | "The harness is the race-engineer agent (SSH sandbox to the car, Cedar/decider interventions), never the driving loop"; safety posture |
| Local: `ops/race_engineer.py`, `ops/pit_stop.cedar` | the `create_harness` call with `SshSandbox` and `CedarAuthorization(on_error="deny", context_enricher=operator_confirmation)`; the policy text quoted on slide 5 |
| Local: `docs/results/pit-stop-2026-10-14/README.md`, `02-refused-write.txt`, `03-calibration-review-with-memory.txt` | the run on the stand (wheels off), model `us.amazon.nova-pro-v1:0`; steering mid 1450000 read over SSH; `edit` refused by Cedar with operator not confirmed; file still 1450000; 1456000 is the staged premise; confirmed path left for the recording |

## Could not verify / caveats

- The releases page shows dates without years; the year 2026 is taken from PyPI (which shows full dates) and from the page order.
- The GitHub star count (8,842 on 2026-10-17) will drift; phrased as "8.8k stars (17 Oct 2026)" on slide 6, drop it if the deck is reused later.
- The bidi interrupts docs page is a stub, so the barge-in sentences cite the overview and stream-events pages. No provider list for barge-in detection is given there; the slide does not claim one.
- `strands-robots` on PyPI could not be fetched (PyPI returned an error page). The project venv has strands-robots 0.5.4.dev51 from the fork branch, strands-agents 1.60.0 and strands-harness 0.2.0 installed; slide 6 quotes the PyPI latest (1.61.1 / 0.3.1), not what is installed. Per speaker, unverified: whether the installed versions will be upgraded before the talk.
- Slide 1 code is condensed from the quickstart (docstring shortened to one line, `file_editor` removed); labelled "condensed" in the caption.
- Slide 3 code is `ops/race_engineer.py` trimmed (env loading and host discovery removed, `deepracer@<car>` placeholder); labelled "trimmed" in the caption.
- The pre-recorded confirmed path of Pit Stop (operator says yes, calibration written, car drives straight) had not been filmed as of the 2026-10-14 README; slide 5 only states what was run. Per speaker, unverified: whether the recording now exists.
- Slide 5's red transcript line ("The tool call to edit the calibration file was denied by the Cedar policy.") is the model's own `<thinking>` block in `02-refused-write.txt`, not a Cedar message; the slide marks it as `<thinking>`.
- The experimental bidi shim: its warning names v1.60.0 as the removal version, but the shim is still present at python/v1.61.1 and on main (checked 2026-10-17). Slide 6 therefore says only that it is deprecated and will go, not when.

## Assets (all real files, fetched with curl, HTTP 200)

| File | Bytes | Source |
|---|---|---|
| `assets/03/strands-agent-loop.svg` | 2459 | https://raw.githubusercontent.com/strands-agents/harness-sdk/main/site/src/assets/diagrams/agent-loop.svg (official docs diagram; kept for reference, not referenced by a slide) |
| `assets/03/strands-agent-loop.themed.svg` | 3943 | the same SVG with the official diagrams.css roles embedded as deck colours (not referenced by a slide; available for the merge) |
| `assets/03/strands-sandbox-execution-boundary.svg` | 2196 | .../diagrams/sandbox-execution-boundary.svg (official) |
| `assets/03/strands-sandbox-execution-boundary.themed.svg` | 3680 | themed copy, used on slide 3 |
| `assets/03/strands-human-in-the-loop-approval-flow.svg` | 2720 | .../diagrams/human-in-the-loop-approval-flow.svg (official; not referenced, spare for slide 2 if the merge prefers an image over the CSS gate) |
| `assets/03/strands-human-in-the-loop-approval-flow.themed.svg` | 4204 | themed copy |
| `assets/03/strands-bidi-how-it-works.svg` | 3186 | .../diagrams/bidi-how-it-works.svg (official; not referenced, spare for the voice section) |
| `assets/03/strands-logo-dark.svg` | 1720 | https://raw.githubusercontent.com/strands-agents/harness-sdk/main/site/src/assets/logo-dark.svg (official mark; not referenced) |
| `assets/03/strands-wordmark-dark.svg` | 2086 | https://strandsagents.com/latest/assets/wordmark-github-dark.svg (the wordmark the Strands READMEs embed for dark mode; used on slide 6) |

The official diagrams carry class names only and take their colours from the site's `diagrams.css`; as a
plain `<img>` they would render black on black. The `.themed.svg` copies embed those roles resolved to
the deck tokens (orange accent instead of the site's green). Geometry and text are untouched. The guide
puts logos under `assets/logos/`; this section was scoped to `assets/03/`, so the wordmark sits there
(move it at merge time if wanted).

## Speaker notes

### C1. Strands Agents: model-driven, one loop
Vocabulary slide, 60 seconds. The loop labels are the official diagram's. Stress "model-driven": the
model picks the next step, the SDK runs tools and feeds results back. Mention `agent.cancel()` as the
hook "Pull the Plug" uses later. Versions: Python 1.61.1 (15 Oct 2026), TypeScript 1.21.0 (14 Oct 2026).

### C2. Four things a robot needs, already in the SDK
Say the safety line first: physics stops the car; the decider explains. Interventions are typed
decisions; the four outcome boxes carry the docs table's own wording (Proceed green, Guide amber,
Confirm blue, Deny red; Transform exists too, it is not on the slide). Hooks observe or change at any lifecycle point. The command gate is
strands-robots' own: one owner of operator approval for every motion topic, interrupt for a human yes,
`STRANDS_ROS2_COMMAND_ALLOW` named explicitly for headless runs. Bidi: persistent connection, barge-in
clears playback.

### C3. "An agent harness is the software around a model that turns it into an agent."
Quote is the SDK overview's first sentence. Distinguish the Harness SDK (toolkit) from Strands harness
(`create_harness()`, returns a plain Agent). Sandboxes: Docker, SSH, custom; no sandbox means the host.
Policies: the string sugar and `CedarAuthorization`. Memory: sessions and `./.agent/memory`. The
harness loop is the agent loop with batteries. The code on the right is our race engineer, one call.

### C4. What create_harness() wires up
Walk the six cards, one line each; the detail per card is in the slide's hidden notes if asked. The
footer line lists the rest (tuned prompt, context management, caching, skills, CLI).

### C5. The harness is the race engineer, never the driving loop
Our rule (CLAUDE.md, report 08). Pit Stop is pre-recorded by council verdict. Tell the stand run
honestly: read over SSH, 1450000 found, 1456000 remembered (staged premise), offset reported without
changes; with the operator not confirmed the edit was refused by Cedar and the file stayed 1450000.
The confirmed write is an operator decision, filmed with the operator at the keyboard. Safety line.

### C6. Start here
Install lines verbatim from docs and READMEs; versions read on PyPI and GitHub on 2026-10-17. Point to
the SDK and harness docs roots and the monorepo. Write against `strands.bidi`; the experimental shim
is deprecated and still ships in 1.61.1 (its warning named v1.60.0 as the removal version, which has
passed without the removal; re-checked 2026-10-17).

## Review 2026-10-17

Re-verified against the live sources above: package versions and dates, the interventions action
names and descriptions, the bidi extras and the Nova Sonic model id, the sandbox classes and the
`create_harness` policy options, the Pit Stop numbers. Corrections: TypeScript 1.21.0 is 14 Oct, not
15; the four intervention descriptions now quote the docs table exactly; the bidi-shim line no longer
claims a removal version. Text trimmed for 10 m readability (one line per card on slide 4, both
`<pre>` blocks at 10 lines, at most six staged reveals per slide).
