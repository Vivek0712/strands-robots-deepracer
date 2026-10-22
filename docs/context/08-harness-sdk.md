# Strands Harness SDK (studied 2026-10-12)

Repo: https://github.com/strands-agents/harness-sdk (Apache-2.0, strands-agents org). This
monorepo now holds the whole Strands stack; the old `sdk-python` URL redirects here.

| Package | Path | Latest tag | What it is |
|---|---|---|---|
| strands-agents (Python SDK) | `strands-py/` | python/v1.59.0 (2026-10-08) | `Agent`, tools, hooks, interventions, sessions, memory, plugins, `strands.bidi` |
| @strands-agents/sdk (TypeScript SDK) | `strands-ts/` | typescript/v1.20.0 | TS twin of the SDK |
| strands-harness (Python) | `harness-py/` | harness-python/v0.2.0 | `create_harness()`: a batteries-included agent in one call |
| @strands-agents/harness (TypeScript) | `harness-ts/` | | TS twin of the harness |
| @strands-agents/cli | `strands-cli/` | harness-cli/v0.2.0 | `strands` terminal chat over the harness; ACP server mode |
| strands-mcp | `strands-mcp/` | mcp/v0.3.0 | MCP server/client helpers |
| site | `site/` | | strandsagents.com docs (Astro) |
| team | `team/` | | API bar-raising, compatibility, complexity, feature lifecycle, PR rules |

## What "harness" means here

`strands_harness.create_harness(...)` returns a plain `strands.Agent` preconfigured with:
built-in tools `shell, read, write, edit, web_fetch, web_search, programmatic_tool_caller,
subagent`; built-in plugins `todos, environment` (injects platform, date, cwd, `AGENTS.md`
before each turn); prompt caching; a context manager (`auto` or `agentic`); resumable
sessions; long-term memory as markdown under `./.agent/memory` with a `search_memory` tool;
Agent Skills from `./.agent/skills`; OpenTelemetry when `OTEL_TRACES_EXPORTER` is set; and
optional interventions. Default model is Bedrock Opus 5; `model="provider/name"` or a
bare Bedrock id switches it; `effort` maps reasoning levels per provider.

Requires `strands-agents[otel]>=1.57.2`, `pydantic-monty==0.0.23` (the sandbox that
`programmatic_tool_caller` runs model-written Python in: no filesystem, network or
process access, only the other tools). Python >= 3.10.

Signature (harness-py/src/strands_harness/agent.py):

```python
create_harness(*, model=None, effort="auto", instructions=None, tools=None, plugins=None,
    mcp_servers=None, builtin_tools=None, background_tasks=None, caching="auto",
    context_manager="auto", session=True, skills=True, memory=True, builtin_plugins=None,
    interventions=None, **agent_kwargs) -> Agent
```

Key behaviours relevant to a robot project:

- **Sandbox seam.** `shell`, `read`, `write`, `edit` and the environment plugin all run
  through the agent's `sandbox`, which can be local, Docker or SSH. An SSH sandbox pointed
  at the DeepRacer lets the harness run `ros2 topic hz`, read `calibration.json`, tail
  logs and edit launch files on the car while the model runs on the laptop.
- **Interventions sugar.** `interventions="ask"` approves every tool call, `"smart"` adds
  an LLM risk classifier, any other string is a natural-language rubric for that
  classifier, a `.cedar` path loads `CedarAuthorization`, and an `InterventionHandler`
  instance passes through. The gate reaches `subagent` children and
  `programmatic_tool_caller` calls, so delegation cannot bypass it. A decider-backed
  `InterventionHandler` (report 03) slots in here unchanged.
- **Subagent delegation.** `make_subagent(builder, presets, instructions, tools, model,
  context, max_depth=2)` derives the tool schema from authority modes (`Fixed`,
  `Inherit`, `Open`, `Choice`). Presets define roles (e.g. `telemetry_analyst`,
  `calibration_tuner`); children inherit tools, plugins, skills and interventions and may
  only narrow tools. `subagent` always runs as a background task; the parent continues
  when the result arrives.
- **`Agent.as_tool(name, description, preserve_context=True)`** wraps any agent (a
  harness, a bidi agent's helper, a robot agent) as a tool for another agent. Report 03
  shows a bidi voice agent calling a harness `research` tool this way.
- **Memory and sessions.** Long-term memory distils facts across conversations (the
  car's sign convention, calibration values, which Wi-Fi it is on) and folds them back
  in; sessions resume by id. `await agent.memory_manager.flush()` before a short run ends.
- **Strands CLI.** `npm install -g @strands-agents/cli`; `strands --agent ./ops/agent.py`
  loads a Python agent definition; `--interventions`, `--model`, `--effort`,
  `--builtin-tools`, `--mcp-config`; `--acp-server` serves the agent over ACP for editors;
  `/export` writes the agent as a Python or TypeScript project. Prefix `!` runs a shell
  command through the agent's sandbox. This is a ready-made operator console.

## Where it fits in this project

The harness is not the driving loop. Driving stays on strands-robots' gated `drive_*`
tools with the car's safety envelope. The harness is the **race engineer**: an agent with
shell access to the car over SSH, file tools for calibration and launch configs, web
tools for the DeepRacer docs and community images, subagents for analysis, memory for the
car's quirks, and a Cedar or decider intervention policy that says which commands may
touch the car. The robot agent can be exposed to it with `as_tool`, and the bidi voice
agent can expose the harness as a `research`/`diagnose` tool the same way.

Reference snippets saved under the scratchpad `research/dl/harness/` (READMEs,
`agent.py`, `interventions.py`, `plugins/environment.py`, `docs/subagent.md`).
