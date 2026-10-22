# Research C: Strands Box, Strands Deciders, Strands Bidi voice agents (as of 2026-10-12)

Scope: three Strands Agents ecosystem releases, plus the current SDK release train, researched from the web (official docs, GitHub, PyPI, AWS blogs) and from local files (the author's local decider checkouts, listed in 2.6, and the installed `strands-agents` 1.38.0 in `/opt/miniconda3/lib/python3.13/site-packages/strands`). Every code block marked "verbatim" is copied character for character from the named source (newlines restored where the docs site renders one `<div>` per line).

Key dates: strands-decider 0.1.0 and Decider 2B blog 2026-10-01; strands-agents 1.57.2 (bidi graduated) 2026-10-01; Bidi GA blog 2026-10-05; Strands Box v0.1.0 2026-10-07; strands-agents 1.59.0 2026-10-08; Gemma 4 deciders released 2026-10-09.

---

## 1. Strands Box

### 1.1 What it is (and what it is not)

**Strands Box exists and is official.** It lives in the **`strands-agents`** GitHub org (not `strands-labs`): https://github.com/strands-agents/box. It is **an open-source sandbox engine for AI agents**: OS-level isolation (macOS Seatbelt today) plus a default-deny semantic policy layer written in **Dogwood** (AWS's Cedar-compatible policy language, https://dogwood-policy.github.io/dogwood/). It is written in **Rust**, licensed **Apache-2.0**, and is **developer preview / pre-release 0.1.x**.

It is **not**:
- a hardware box, edge compute kit or anything robot-specific (no mention of robots, strands-robots or DeepRacer anywhere in the repo, docs, or the two launch posts; Marc Brooker's "Big Picture" post does not mention robots);
- a dev container or Docker image (the AWS post explicitly argues "why not containers or microVMs");
- a Python library (there is **no pip package**; it is a CLI binary `box` downloaded by a shell script or built with `cargo`).

Searches run: `"Strands Box" strands-agents`; `github strands-agents box OR strands-labs box "Strands" sandbox agent box release 2026`; `"strands" "box" AWS agents announcement robot OR sandbox OR "dev container" site:aws.amazon.com OR site:strandsagents.com OR site:github.com`. All three converge on the same single product. There is no other "Box" in either org.

Relationship to `strands-labs`: The New Stack reported AWS launched **Strands Labs** as the org where Amazon teams publish frontier projects not ready for the production SDK (https://thenewstack.io/aws-strands-labs-launch/). `strands-decider` and `robots` are in `strands-labs`; `box`, `harness-sdk` (the SDK monorepo) and `tools` are in `strands-agents`.

### 1.2 Release facts

| Item | Value |
|---|---|
| Repo | https://github.com/strands-agents/box |
| First tagged release | **v0.1.0, published 2026-10-07T17:24:27Z**, https://github.com/strands-agents/box/releases/tag/v0.1.0 |
| Announcement (AWS Open Source Blog) | "Introducing Strands Box: AI agent sandboxes powered by Dogwood", Fernando Dingler, 2026-10-07, https://aws.amazon.com/blogs/opensource/introducing-strands-box-ai-agent-sandboxes-powered-by-dogwood/ |
| Companion post | "Strands Box: The Big Picture", Marc Brooker, 2026-10-07, https://strandsagents.com/blog/strands-box-the-big-picture/ |
| Docs home | https://strandsagents.com/docs/user-guide/box/ |
| Getting started | https://strandsagents.com/docs/user-guide/box/getting-started/ (source: https://raw.githubusercontent.com/strands-agents/box/main/docs/user/getting-started.md) |
| Reference pages | box.toml: /docs/user-guide/box/reference/configuration/ ; CLI: /docs/user-guide/box/reference/cli/ ; Policy actions: /docs/user-guide/box/reference/policy-actions/ ; Strands Shell: /docs/user-guide/box/reference/shell/ ; Python (Monty): /docs/user-guide/box/reference/python/ ; Security model: /docs/user-guide/box/security/ |
| Install | `curl -fsSL https://raw.githubusercontent.com/strands-agents/box/main/download.sh \| sh` (unpacks to `./box-core/box`); or `cargo build --release -p strands-box -p strands-box-containment` |
| Pip name | none (no Python package) |
| Platform | macOS 15+ on Apple silicon only; Linux "planned"; Windows unsupported |
| Policy-authoring agent skill | https://raw.githubusercontent.com/strands-agents/box/main/.agents/skills/authoring-box-policy/SKILL.md |
| Press | The Register 2026-10-07 https://www.theregister.com/ai-and-ml/2026/10/07/aws-launches-open-source-ai-agent-sandbox-to-prevent-yolo-mode-disasters/5301687 ; Help Net Security 2026-10-12 https://www.helpnetsecurity.com/2026/10/12/aws-strands-box-open-source-ai-agent-sandbox/ ; DeepWiki https://deepwiki.com/strands-agents/box |
| Related community post | "Strands Box on AWS Lambda MicroVMs ... microvm-ctl" (Builder Center) https://builder.aws.com/content/3KNzMek3U1WL6S49viNEhHeFZmC/strands-box-on-aws-lambda-microvms-a-kernel-per-agent-a-policy-per-command-and-a-fleet-to-run-them-with-microvm-ctl |

### 1.3 Architecture and "API surface"

Box has no Python/TS API. Its surface is: the **`box` CLI** (`box run --config box.toml [-- <args to agent>]`, `box --version`), two config files, and a decision log.

- **`box.toml`**: `name`, `box_dir`, `policy`; `[agent]` (`command`, `workspace`, `env` or `[agent.env]`); `[agent.filesystem]` grants (`read`, `read_file`, `write`, `list`, `exec`, `metadata`) enforced by the OS (Seatbelt) with no per-op policy decision; `[tool.<name>]` sandboxed external programs; `[egress.<name>]` with `destinations` and `secret.ref` (`env://VAR`, `aws://profile`) and `secret.inject`.
- **`policy.dw`**: Dogwood `permit`/`forbid` rules with `@id`, `@description`, `when { context.input.* }` and `when temporal { ... }` clauses. Action vocabulary seen: `Box::Action::"net:connect"`, `"http:request"`, `"shell:exec"`, `"shell:spawn"`, `"fs:read"`, `"fs:write"`, `"fs:delete"`, MCP tool calls. Default deny; `forbid` overrides `permit`.
- **Enforcement points** (all in a trusted process outside the agent sandbox): **Strands Shell** (shell interpreter), **Monty** (Pydantic's Python interpreter), **egress gateway** (TLS termination, credential substitution, SigV4 signing), **MCP broker**, all feeding the embedded **Dogwood Local Engine** with a shared event history (so a rule can say "deny upload after a customer file was read" or "max 3 Slack posts per 10 minutes").
- **Decision records**: OTLP JSON at `<box_dir>/private/telemetry/records.jsonl`.
- Caveat from README: agent built-in file tools bypass policy; docs recommend giving the agent a shell as its only file tool.

Repo tree of interest: `examples/strands-box/strands-sdk-agent/{agent.py,box.toml,policy.dw,setup.sh}`, `examples/strands-cli/`, `examples/claude-code/`, `examples/codex-cli/`, `examples/pi/`; `docs/user/*.md`, `docs/design/*.md` (architecture, containment, egress, mcp, monty, shell, telemetry, limitations).

### 1.4 Relationship to strands-robots and AgentCore

- **strands-robots**: none stated. Box is "harness-agnostic" and its examples are coding agents (Strands CLI, Strands Python SDK agent, Claude Code, Codex CLI, pi). For a DeepRacer agent it would only matter as a way to sandbox an agent process on a Mac dev box; it does not run on the car (Ubuntu/Linux), since Linux is unsupported in 0.1.x.
- **AgentCore**: Brooker's post positions **AgentCore Runtime** as the cloud sandbox (dedicated per-session MicroVM) and says running Box *inside* an AgentCore agent is the suggested path for multi-tenant use, with **AgentCore Policy** handling tool-call policy. The AWS post's "What's next" lists packaging Boxes for deployed agents (AgentCore, ECS, Kubernetes), Linux, a config-generating CLI, and Dogwood liveness rules.
- **Strands SDK / Harness**: not required; Box works with any agent framework, but the getting-started uses the Strands CLI (`@strands-agents/cli`) and there is a Strands Python SDK example.

### 1.5 Verbatim code samples

**Sample A: the on-call agent box from the AWS launch post** (verbatim, https://aws.amazon.com/blogs/opensource/introducing-strands-box-ai-agent-sandboxes-powered-by-dogwood/)

`box.toml`:
```toml
name    = "oncall"
box_dir = "/Users/me/.box/oncall"
policy  = "policy.dw"

[agent]
command = ["strands", "--builtin-tools", "shell"]
workspace = "/Users/me/oncall"

[agent.filesystem]
read  = ["/Users/me/oncall"]
write = ["/Users/me/oncall"]

[tool.aws]
command = ["/usr/local/bin/aws"]

[tool.aws.env]
AWS_REGION = "us-west-2"

[egress.aws]
destinations = ["*.us-west-2.amazonaws.com"]
secret.ref   = "aws://oncall"

[egress.model]
destinations = ["api.anthropic.com"]
secret.ref   = "env://ANTHROPIC_API_KEY"

[egress.slack]
destinations = ["slack.com"]
secret.ref   = "env://SLACK_BOT_TOKEN"
secret.inject = "always"
```

`policy.dw`:
```
@id("allow_aws_cli")
permit (principal, action == Box::Action::"shell:spawn", resource)
when { context.input.program_path == "/usr/local/bin/aws" };

@id("allow_https_to_aws")
permit (principal, action == Box::Action::"http:request", resource)
when {
  context.input.host like "*.us-west-2.amazonaws.com" &&
  context.input.port == 443
};

@id("allow_model_api")
permit (principal, action == Box::Action::"http:request", resource)
when {
  context.input.host == "api.anthropic.com" &&
  context.input.port == 443
};
```

Run: `box run --config box.toml`

Temporal rule (the "three Slack posts per ten minutes" example):
```
@id("allow_slack_post")
permit (principal, action == Box::Action::"http:request", resource)
when {
  context.input.host == "slack.com" &&
  context.input.port == 443 &&
  context.input.method == "POST" &&
  context.input.path == "/api/chat.postMessage"
};

@id("rate_limit_slack_posts")
@description("Slack posts are capped at three every 10 minutes. Wait before you post again.")
forbid (principal, action == Box::Action::"http:request", resource)
when {
  context.input.host == "slack.com" &&
  context.input.port == 443 &&
  context.input.method == "POST" &&
  context.input.path == "/api/chat.postMessage"
}
when temporal {
  (count for (t: Timepoint). where (
      formerly within 10m (
          Box::Action::"http:request"::response{
              input.host: "slack.com",
              input.port: 443,
              input.method: "POST",
              input.path: "/api/chat.postMessage",
              output.status: 200
          } && tp(t)
      )
  )) >= 3
};
```

**Sample B: a Strands Python SDK agent in a box** (verbatim from https://github.com/strands-agents/box/tree/main/examples/strands-box/strands-sdk-agent)

`agent.py`:
```python
"""A Strands Agents SDK agent that works on a project from inside a box.

The box starts this file and passes the task on the command line, after `--`. Each tool runs a
command through the box's shell, so the policy decides every file the command touches.
"""

import os
import shlex
import subprocess
import sys

from strands import Agent, tool
from strands.models import BedrockModel

SYSTEM_PROMPT = """You work on the project in the current directory, with the tools you are given.
Keep answers to a few sentences. When a tool reports that the policy denied an operation, quote the
denial, say what it stopped, and end your turn. Do not look for another way to do it."""


def shell(command: str) -> str:
    """Run one command in the box's shell, show it on stderr, and return what it printed."""
    done = subprocess.run(["zsh", "-c", command], capture_output=True, text=True)
    print(f"[tool] {command} (exit {done.returncode})", file=sys.stderr)
    if done.stderr:
        print(done.stderr.rstrip(), file=sys.stderr)
    if done.returncode == 0:
        return done.stdout or "(no output)"
    return f"exit {done.returncode}\n{done.stderr}"


@tool
def list_project() -> str:
    """List the files in the project."""
    return shell("ls -a")


@tool
def read_file(path: str) -> str:
    """Read one file in the project, by its path relative to the project."""
    return shell(f"cat {shlex.quote(path)}")


@tool
def run_command(command: str) -> str:
    """Run a shell command in the project and return its output."""
    return shell(command)


def main() -> int:
    # Keep the model's words in order with the tool lines when the output goes to a file.
    sys.stdout.reconfigure(line_buffering=True)
    task = " ".join(sys.argv[1:])
    if not task:
        print("usage: box run --config box.toml -- <task>", file=sys.stderr)
        return 2
    missing = [name for name in ("MODEL_ID", "AWS_REGION") if name not in os.environ]
    if missing:
        print(f"set {' and '.join(missing)} in [agent] env in box.toml", file=sys.stderr)
        return 2
    agent = Agent(
        model=BedrockModel(model_id=os.environ["MODEL_ID"], region_name=os.environ["AWS_REGION"]),
        system_prompt=SYSTEM_PROMPT,
        tools=[list_project, read_file, run_command],
    )
    agent(task)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`box.toml`:
```toml
# To author or change the policy next to this file, point your coding agent at the skill:
#   https://raw.githubusercontent.com/strands-agents/box/main/.agents/skills/authoring-box-policy/SKILL.md

# The box's name, and where it keeps its own state. The agent can't reach box_dir.
name = "strands-sdk"
box_dir = "<HOME>/box-tutorial/strands-agent/state"
# The policy file, next to this one.
policy = "policy.dw"

[agent]
# The program the box starts: the Python in the example's virtual environment, running agent.py.
# The task comes from the command line, after `--`.
command = [
  "<HOME>/box-tutorial/strands-agent/runtime/.venv/bin/python3",
  "<HOME>/box-tutorial/strands-agent/agent.py",
]
# The directory the agent starts in. This alone grants nothing.
workspace = "<HOME>/box-tutorial/my-project"
# The agent gets these variables, plus the ones the box adds. Nothing comes from your shell. The
# SDK reads the region and skips the EC2 metadata service; agent.py reads the model.
env = { AWS_REGION = "us-west-2", AWS_EC2_METADATA_DISABLED = "true", MODEL_ID = "global.anthropic.claude-opus-5", PATH = "/usr/bin:/bin", TMPDIR = "<HOME>/box-tutorial/strands-agent/tmp" }

# What the agent's own process can touch without asking the policy.
[agent.filesystem]
# Python loads the SDK from the virtual environment, and its standard library and the libraries it
# links from Homebrew's kegs.
read = [
  "~/box-tutorial/strands-agent/runtime/.venv",
  "/opt/homebrew/Cellar/python@3.14",
  "/opt/homebrew/Cellar/openssl@3",
  "/opt/homebrew/Cellar/sqlite",
]
# Homebrew's opt directory holds the links that Python and its libraries follow into the kegs.
metadata = ["/opt/homebrew/opt"]
# Python runs agent.py.
read_file = ["~/box-tutorial/strands-agent/agent.py"]
# Homebrew's python3 starts the interpreter inside its own framework.
exec = ["/opt/homebrew/Cellar/python@3.14"]
# Python's temporary files.
write = ["~/box-tutorial/strands-agent/tmp"]
# The agent lists the names in its working directory. It can't open the files itself.
list = ["~/box-tutorial/my-project"]

# The box adds your Bedrock API key to each request to Bedrock. The agent gets a stand-in value.
[egress.model]
destinations = ["bedrock-runtime.us-west-2.amazonaws.com"]
secret.ref = "env://AWS_BEARER_TOKEN_BEDROCK"
```

`policy.dw`:
```
// Connect to Bedrock, and send it requests.
@id("model_connect")
permit (principal, action == Box::Action::"net:connect", resource)
when { context.input.host == "bedrock-runtime.us-west-2.amazonaws.com" && context.input.port == 443 };

@id("model_request")
permit (principal, action == Box::Action::"http:request", resource)
when { context.input.host == "bedrock-runtime.us-west-2.amazonaws.com" };

// Run any command in the box's shell. Each file a command touches is still its own decision.
@id("shell_commands")
permit (principal, action == Box::Action::"shell:exec", resource);

// Read anything in the project. A path under your home starts with "~" here.
@id("project_read")
permit (principal, action == Box::Action::"fs:read", resource)
when {
  context.input.path == "~/box-tutorial/my-project" ||
  context.input.path like "~/box-tutorial/my-project/*"
};

// Use /dev/null, which agents redirect output to all the time.
@id("dev_null")
permit (principal, action in [Box::Action::"fs:read", Box::Action::"fs:write"], resource)
when { context.input.path == "/dev/null" };

// One file inside the project stays unread, whatever the permit above says.
@id("no_env")
@description("The .env file holds credentials the agent must not read.")
forbid (principal, action == Box::Action::"fs:read", resource)
when { context.input.path == "~/box-tutorial/my-project/.env" };

// Nothing gets deleted, whatever another rule permits.
@id("no_deletes")
@description("This agent reads the project and runs commands in it. It deletes nothing.")
forbid (principal, action == Box::Action::"fs:delete", resource);

@id("metadata_hosts")
@description("Refuse the cloud metadata services by name, before resolution.")
forbid (principal, action == Box::Action::"net:connect", resource)
when {
  context.input.host == "metadata.google.internal" ||
  context.input.host == "metadata.azure.internal"
};

@id("metadata_addresses")
@description("Refuse link-local and cloud metadata addresses, on the address resolution pinned.")
forbid (principal, action == Box::Action::"net:connect", resource)
when {
  context.input has ip && (
    context.input.ip like "169.254.*" ||
    context.input.ip == "fd00:ec2::254" ||
    context.input.ip like "fe8*" || context.input.ip like "fe9*" ||
    context.input.ip like "fea*" || context.input.ip like "feb*")
};
```

Run (from the example README, verbatim):
```sh
[ -d box-src ] || git clone --depth 1 https://github.com/strands-agents/box.git box-src
cp -R box-src/examples/strands-box/strands-sdk-agent strands-agent
sed -i '' "s|<HOME>|$HOME|g" strands-agent/box.toml
./strands-agent/setup.sh
./box-core/box run --config strands-agent/box.toml -- "Summarize README.md in one sentence."
```

**Sample C: decision log query from the getting-started guide** (verbatim)
```sh
jq -r '.resourceLogs[]?.scopeLogs[].logRecords[]
  | (.attributes | map({(.key): .value}) | add) as $a
  | select($a["strands.box.policy.verdict"])
  | [$a["strands.box.policy.verdict"].stringValue, $a["strands.box.policy.action"].stringValue,
     ($a["file.path"].stringValue // $a["server.address"].stringValue
      // ($a["process.command_args"].arrayValue.values | map(.stringValue) | join(" ")))]
  | @tsv' my-box/state/private/telemetry/records.jsonl
```
Example output shown in the guide:
```
deny    net:connect   telemetry.strandsagents.com
deny    shell:spawn   /usr/bin/uname -s
permit  shell:exec    pwd
permit  net:connect   bedrock-runtime.us-west-2.amazonaws.com
permit  http:request  bedrock-runtime.us-west-2.amazonaws.com
permit  shell:exec    cat /Users/you/box-tutorial/my-project/README.md
permit  fs:read       ~/box-tutorial/my-project/README.md
...
deny    fs:write      ~/box-tutorial/my-project/README.md
```

---

## 2. Strands Deciders

### 2.1 What a Decider is

A **decision model ("system one" model)**: a pretrained decoder LLM torso with its language-modelling head **removed** and replaced by a ~1M-parameter **pointer head** that scores each option by comparing the hidden state at the `<answer>` token with the hidden state at each option's last token. One forward pass, no generation. The torso is adapted with a rank-16 LoRA; head runs in fp32. Three question types from one masked softmax:
- **`noul`** (yes/no): returns P(true);
- **`choice`** (one of N): argmax plus confidence `(N p_max - 1)/(N - 1)`;
- **`score`** (ordered rubric): expected level plus confidence `1 - sigma/sigma_max`.

Every answer carries a calibrated probability, so code can act when confident and defer otherwise. Many questions over one state are nearly free (state encoded once, KV/recurrent cache forked per question). It is **not** limited to yes/no: it is a general runtime-labelled classifier/scorer. Use cases from the README: model routing, tool selection, argument checking, triage, guardrails, evaluations, hybrid agents.

Source: https://github.com/strands-labs/strands-decider README and `docs/architecture.md`; blog "Introducing Strands Decider 2B" (Marc Brooker, Mike Chambers, Fabio Nonato de Paula, 2026-10-01) https://strandsagents.com/blog/introducing-strands-decider/.

### 2.2 Models, sizes, HF IDs

Hugging Face org: **https://huggingface.co/StrandsAgents** (7 repos, all tagged Text Classification). The five v1 models are mirrored under the `amazon` org with the same names (README commit 0ac22a9, 2026-10-09).

| HF model ID | Base | Params | JevBench v1 public (/231) | Brier | Notes |
|---|---|---|---|---|---|
| `StrandsAgents/strands-decider-2B-hobson-v19` | Qwen3.5-2B-Base | 1.9B | 167 (0.723) | 0.342 | launch model 2026-10-01; 115 ms median RTX 3090, 153 ms M3 Pro |
| `StrandsAgents/strands-decider-2B-hobson-v21` | Qwen3.5-2B-Base | 1.9B | 176 (0.762) | | released ~2026-10-05 |
| `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | Qwen3.5-2B-Base | 1.9B | **180 (0.779)** | 0.280 | **current reference model**, released 2026-10-09 (README #61); `--vision` works with it |
| `StrandsAgents/strands-decider-E2B-gemma4-v1-2610` | Gemma 4 E2B | ~2B eff. | 180 | 0.313 | ~9 GB bf16, 102 ms |
| `StrandsAgents/strands-decider-E4B-gemma4-v1-2610` | Gemma 4 E4B | ~4B eff. | 187 | 0.243 | ~15 GB, 139 ms |
| `StrandsAgents/strands-decider-12B-gemma4-v1-2610` | Gemma 4 12B | 12B | 200 | 0.173 | ~23 GB, 136 ms |
| `StrandsAgents/strands-decider-26B-A4B-gemma4-v1-2610` | Gemma 4 26B-A4B MoE | 26B (4B active) | 207 | 0.162 | ~51 GB, 245 ms |

Gemma 4 models released 2026-10-09 (README commit 468e653 "docs: release strands-decider-{E2B,E4B,12B,26B-A4B}-gemma4-v1-2610 (#63)"; code commit de3ded2 "feat(gemma4): support the Gemma 4 E2B, E4B, 12B and 26B-A4B torsos (#57)" 2026-10-08). Naming scheme (`docs/naming.md`): `strands-decider-<size>-<base>-v<N>-<YYMM>`.

### 2.3 Versions and releases

- **PyPI `strands-decider`**: only **0.1.0**, uploaded **2026-10-01 16:05 UTC**; `requires_python >=3.10`; summary "An experimental typed classifier: calibrated yes/no, choice and score answers from an LLM torso with a pointer readout." https://pypi.org/project/strands-decider/
- **GitHub releases/tags**: none (the releases API returns `[]`, tags `[]`); `pyproject.toml` `version = "0.1.0"`; builds take version "from v<number> tags only" (commit cdb4478). So the PyPI 0.1.0 predates Gemma 4, MLX, soup and vision changes. **Gemma 4 support and the `mlx` extra are `main`-only**: `pip install "strands-decider @ git+https://github.com/strands-labs/strands-decider"`.
- Repo stats seen 2026-10-12: 584 stars, 21 open issues, 18 open PRs; latest commits 2026-10-09.
- Extras: `[cuda]`, `[mps]`, `[cpu]`, `[mlx]`, `[vision]` (transformers >= 5.18), `[train]`.
- Changelog: no CHANGELOG in upstream main; the research record is `research/README.md`, `research/history.md`, `research/preregistrations/`. Recent "what changed": v19 -> v21 (more data, 123,339 rows) -> qwen3.5-v1-2610 (135,602 rows incl. 12,263 code rows, Qwen3.5-4B / gemma-4-31B-it teachers); Gemma 4 torsos; `strands-decider soup` (seed souping, #58); MLX serving (#7); image input `--vision` (#10, by the user).

### 2.4 API surface

**CLI** (`strands-decider` entry point, src/strands_decider/cli.py): `ask <model> --state ... [--choice "q=a,b,c"] [--noul "q"] [--score "q=lo,mid,hi"] [--image file] [--device cuda|mps|cpu|mlx]`; `serve <model> --port N [--vision] [--audio (PR #67)] [--device ...]`; `train`, `calibrate`, `soup`, `evaluate`.

**HTTP** (`POST /v1/systemone`, `GET /health`): the "System One" request/response contract shared with JevBench's `typesafe` adapter:
```json
{
  "state": "Help! My payouts have been failing for 3 days!",
  "questions": {
    "is_urgent": {"type": "noul", "instructions": "Does this convey urgency?"}
  }
}
```
Response:
```json
{
  "model": "strands-decider-2B-hobson-v19",
  "answers": {"is_urgent": {"type": "noul", "noul": 0.8277}},
  "usage": {"input_tokens": 86, "output_tokens": 1},
  "latency_ms": 140.03
}
```
`choice` questions take `"criteria": {"option": "description", ...}` and return `choice`, `probabilities`, `confidence`; `score` takes `"criteria": ["lo", "mid", "hi"]` and returns `score` (expected level), `legend`, `probabilities`, `confidence`. With `--vision` the request may carry `"images": ["<base64>"]` (up to 4 per request).

**Python**: there is no `Decider` class in the `strands_decider` package itself; the `Decider` class with `Decider.noul()`, `Decider.choice()`, `Decider.score()`, `.ask(state, questions)`, `.health()` lives in the example client `examples/strands/_client.py` (urllib, stdlib only). The agent seam is the Strands **intervention system**: `strands.interventions.InterventionHandler` with `before_tool_call(self, event, **kwargs)` returning `Proceed()`, `Guide(feedback=...)`, `Deny`, or `Confirm`. (The older `BeforeToolCallEvent` hook also works; `strands-decider-agentcore` example 02 uses a `BeforeToolCallEvent` hook that cancels the call when P(irreversible harm) >= 0.5.)

### 2.5 Verbatim: CLI and the Strands Agent integration

From the upstream README (verbatim from the strands-labs/strands-decider README; main now uses `strands-decider-2B-qwen3.5-v1-2610` in the same commands):
```bash
pip install strands-decider
```
```bash
strands-decider ask StrandsAgents/strands-decider-2B-hobson-v19 \
  --state "Help! My payouts have been failing for 3 days! " \
  --choice "Which team should handle this?=billing,sales,retail" \
  --noul "Does this convey urgency?" \
  --score "How frustrated is the writer?=calm,frustrated,depressed"
```
```bash
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8000
```
```bash
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -d '{
    "state": "Help! My payouts have been failing for 3 days!",
    "questions": {
      "is_urgent": {"type": "noul", "instructions": "Does this convey urgency?"}
    }
  }'
```
Images:
```bash
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --vision --port 8000
strands-decider ask StrandsAgents/strands-decider-2B-hobson-v19 --state "" --image page.png \
  --noul "Is the signature block filled in?"
```

From `examples/strands/README.md` (verbatim):
```bash
git clone https://github.com/strands-labs/strands-decider && cd strands-decider
pip install -e . strands-agents
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099

python examples/strands/tool_call_intervention.py
```

`examples/strands/tool_call_intervention.py`, the gate itself (verbatim excerpt; full file at that path in strands-labs/strands-decider):
```python
from _client import NAME, Decider, ServerUnavailable
from strands import Agent, tool
from strands.interventions import Guide, InterventionHandler, Proceed

QUESTIONS = {
    "args_grounded": Decider.noul(
        "Are the tool's argument values grounded in facts the user actually provided?",
        {
            "true": "every argument value traces back to something the user said",
            "false": "an argument value was guessed or invented, not stated by the user",
        },
    ),
    "premature": Decider.noul(
        "Is it premature to call this tool now, before clarifying with the user?",
        {
            "true": "the assistant should ask a clarifying question before calling the tool",
            "false": "there is nothing left to clarify; calling now is appropriate",
        },
    ),
}

# A strands-decider probability at or above this reads as a confident "yes". This is the
# policy knob, owned by the code, not the model. Raise it to block less, lower it to block
# more. 0.45 is illustrative -- pick a value that suits your own traffic.
YES = 0.45


class ToolCallReviewer(InterventionHandler):
    name = f"{NAME}-tool-call-reviewer"

    def __init__(self, decider: Decider) -> None:
        self._decider = decider
        self.log: list[dict[str, object]] = []

    @staticmethod
    def _render(messages: list[dict]) -> str:
        """Flatten Strands' message list to plain text: only the human-readable blocks."""
        lines: list[str] = []
        for message in messages:
            role = message.get("role", "unknown")
            for block in message.get("content", []):
                if isinstance(block, dict) and "text" in block:
                    lines.append(f"{role}: {block['text']}")
        return "\n".join(lines) if lines else "(no conversation yet)"

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        arguments = event.tool_use.get("input") or {}
        state = (
            "A conversation between a user and an AI assistant is below, followed by a "
            "tool call the assistant now wants to make.\n\n"
            f"--- CONVERSATION ---\n{self._render(event.agent.messages)}\n\n"
            f"--- PROPOSED TOOL CALL ---\ntool: {name}\n"
            f"arguments: {json.dumps(arguments)}"
        )

        answers = self._decider.ask(state, QUESTIONS)
        args_grounded = answers["args_grounded"]["noul"]
        premature = answers["premature"]["noul"]

        if args_grounded < YES:
            verdict, action = "guided", Guide(
                feedback=(
                    "The arguments are not grounded in anything the user said -- they look "
                    "guessed. Ask the user to confirm the values instead of inventing them."
                )
            )
        elif premature >= YES:
            verdict, action = "guided", Guide(
                feedback=(
                    "It is too early to call this tool. Clarify with the user first, then "
                    "try again."
                )
            )
        else:
            verdict, action = "proceeded", Proceed()
        ...
        return action


@tool
def get_weather(location: str) -> str:
    """Get the current weather for a specific city.

    Args:
        location: The city to look up, e.g. "Seattle" or "Paris".
    """
    return f"It's 21C and sunny in {location}."


def main() -> int:
    decider = Decider()
    gate = ToolCallReviewer(decider)
    agent = Agent(
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        tools=[get_weather],
        interventions=[gate],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,  # the gate's own log is the interesting output
    )
    result = agent(USER_REQUEST)
```

The `Decider` client's `ask` (from `examples/strands/_client.py`, verbatim):
```python
    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        """Evaluate `state` against `questions`; answers come back under the same keys."""
        body = json.dumps(
            {"state": state, "model": MODEL_ID, "questions": dict(questions)}
        ).encode()
        request = urllib.request.Request(
            f"{self.url}/v1/systemone", data=body, headers={"content-type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
        ...
        return payload["answers"]
```

### 2.6 The user's vision/multimodal decider work (the author's local decider checkouts)

Local layout of the author's decider checkouts: `sd-upstream` (clone, origin = Vivek0712/strands-decider fork, upstream = strands-labs), `strands-decider-fork` (vision-eval branch, tag `vision-eval-2026-10-03-3-gab88cac`), `sd-e4b-mm` (Gemma 4 image+audio work, latest commits 2026-10-12), a standalone `vision_decider` package, `decider-lab`, `strands-decider-agentcore`, `decider-playground`, `robots-decider`, `weights-pkg`, `checkpoints/`, `blog/`, `blog-robots/`, plus `VISION_DECIDER_RESEARCH.md` (33 KB, 2026-10-01) and `LINEAGE.md` (2026-10-04).

Upstream contributions (status checked via `gh api` 2026-10-12):
| # | Type | Title | State |
|---|---|---|---|
| strands-decider **#10** | PR | feat(vision): image input for Strands Decider (v19), vision tower kept, no retraining | **merged 2026-10-03** (upstream commit 75c9fd3; this is what `--vision` is) |
| strands-decider **#23** | PR | Strands Decider candidates ... code to train, evaluate and reproduce (v20/v21 recipe: multi-base torsos, `continue_from`, soups, teacher targets, grafted encoders) | closed 2026-10-04 (not merged) |
| strands-decider **#24** | issue | Four trained candidates (hobson-v20, v20-balanced, 2.5B-minicpm-v21, v21-vl) please review | open |
| strands-decider **#45** | issue | [FEATURE] decider-lab companion harness | open (2026-10-06) |
| strands-decider **#67** | PR | feat(gemma4): image and audio input for Gemma 4 E2B / E4B, encoders kept, no retraining (`--audio`) | **open, opened 2026-10-12**, mergeable_state blocked |
| strands-labs/robots **#4572 / #4573** | issue / PR | Strands Decider as an episode-judge backend that defers what it is unsure of (`DeciderJudge(url)`) | issue closed completed; PR closed, not merged |

Key findings from `VISION_DECIDER_RESEARCH.md`: Qwen3.5-2B-Base is natively multimodal (early fusion ViT + merger + decoder); upstream `_load_torso` deliberately drops the vision tower; "Option A" (keep the tower, image tokens inside `<state>`, pointer head unchanged) was chosen and became PR #10. Measured in `LINEAGE.md`: v19 with images, no retraining: NaturalBench 0.787, POPE 0.858; v20 image fine-tune: NB 0.805, POPE 0.874. The multimodal Gemma 4 blog draft (`blog/strands-decider-multimodal.md` in the author's local checkout, the basis of strands-labs/strands-decider PR #67) reports on the unchanged E4B: text bit-identical on all 231 JevBench tasks (187/231), Speech Commands 10-way 0.930, POPE 0.835 (ECE 0.051), NaturalBench 0.750, ESC-50 5-way 0.490, latency 117 ms text / ~400 ms with an image or 5 s clip on one L4.

Recorded unofficial checkpoints (LINEAGE.md): `strands-decider-2B-hobson-v20`, `-v20-balanced`, `strands-decider-2.5B-minicpm-v21`, `-v21-vl` (SigLIP2 graft), with SHA-256s in `weights-pkg/`.

### 2.7 strands-decider-agentcore (GitHub Vivek0712/strands-decider-agentcore)

Deploys official deciders on **Amazon Bedrock AgentCore Runtime** via the AgentCore CLI (`npm install -g @aws/agentcore`): one `runtime/` container, model/commit/precision as env vars; `deciderctl add <name> --model v21|v19`, `agentcore deploy -y`; int8 CPU build fits the 2 vCPU / 8 GB microVM (4.2 GB resident, 6.6 GB peak); weights downloaded from HF at session start. Invocation payload is the System One request; `{"batch": [...]}` and `{"action": "health"}` also accepted. Client: `client/decider_client.py` with `DeciderClient(arn=...)`, `noul()`, `choice()`, `score()`, `.decide(state, questions)`, session pools (`pool=N`). Measured (us-east-1, Graviton2, v21 int8): cold start 45 to 90 s; **about 7 s per question warm** (compute-bound; not for tight loops). Example 02 is a Strands agent with a `BeforeToolCallEvent` hook that blocks tool calls when P(irreversible harm) >= 0.5. Also contains `usecases/model-routing` (decider as difficulty judge: ROC AUC 1.00 vs 0.88 for Claude Sonnet 4.6) and the live playground https://d3jcg138x8aln8.cloudfront.net. Newer commit f9691ee adds `DECIDER_DEVICE=cuda`, Lambda (Web Adapter) and SageMaker GPU images with baked weights.

Verbatim client usage (README):
```python
from client.decider_client import DeciderClient, noul, choice, score

decider = DeciderClient(arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/StrandsDeciders_triage-AbCdEf")
r = decider.decide("Order #4411 arrived broken, I want a refund.", {
    "escalate": noul("Should a human agent handle this?"),
    "queue": choice("Which team?", {"returns": "refunds and returns", "billing": "payments"}),
})
if r["answers"]["escalate"]["noul"] >= 0.75:
    assign_to_agent(...)
```

### 2.8 decider-lab (GitHub https://github.com/Vivek0712/decider-lab, Apache-2.0, public 2026-10-06)

Evaluate / calibrate / compare / fine-tune harness driven by one `lab.yaml`; `decider-lab run lab.yaml --on local|ssh|aws|vast`; models: `{serve: <hf/s3/url/dir>}`, `{url: ...}` (any System One server), `{bedrock: ...}`, `{strands: ...}`, `{chat: ...}` (OpenAI-compatible), `{python: "mod:fn"}`, `{baseline: majority}`; suites: `smoke`, `synthetic`, `heldout`, `{file: ...}`, `jevbench` (231 public tasks, v1.5 rules as local proxy); paired bootstrap 95% CIs; temperature calibration; fine-tune via strands-decider's own trainer with leak check; Studio web UI (`decider-lab ui`). Install: `pip install "decider-lab @ git+https://github.com/Vivek0712/decider-lab"`. Proposed upstream as issue #45.

Verbatim `lab.yaml` from the README:
```yaml
name: first-lab
models:
  v19:      {serve: StrandsAgents/strands-decider-2B-hobson-v19}   # started, warmed up, verified, stopped
  mine:     {url: "http://10.0.0.5:8000"}                          # any System One server
  nova:     {bedrock: us.amazon.nova-pro-v1:0, region: us-east-1}   # Amazon Bedrock (or strands:, chat:)
  my_code:  {python: "my_model:Heuristic"}                          # your own function
  majority: {baseline: majority}                                    # the floor every model must beat
suites:
  - smoke                          # 90 rows, seconds
  - synthetic: {per_kind: 100}     # labels computed by programs, dev/test splits
  - heldout                        # public families Strands Decider never trains on
  - file: data/my_eval.jsonl       # yours
calibrate: true                    # temperatures fitted on dev, scored on test
baseline: majority                 # paired comparison, row by row, 95% CI
jevbench: [v19]                    # JevBench's 231 public tasks, v1.5 rules
```

### 2.9 How a decider could gate a DeepRacer agent

Two patterns, both already demonstrated in the user's work:

1. **Safety decider on motion commands** (text, `noul`/`score`): same seam as `tool_call_intervention.py`. Register an `InterventionHandler.before_tool_call` (or a `BeforeToolCallEvent` hook) on the DeepRacer agent; serialize the conversation plus the proposed `drive(throttle, steering)` / `set_speed` call into the `state`; ask e.g. `noul("Does this command exceed the allowed speed or steering envelope for the current context?")`, `score("How risky is this motion?", ["safe","caution","unsafe"])`; return `Proceed()` when confident-safe, `Guide(feedback=...)` or `Deny` otherwise. Local 2B decider answers in ~115 to 150 ms (GPU/Apple silicon) which fits a command-rate gate; AgentCore-hosted deciders (~7 s/question on CPU) do not fit a real-time loop and should be used for episode review or offline labelling. The strands-labs/robots doctrine the user worked within (robots-decider PLAN.md): a decider may **triage/advise** but must **never auto-approve**; the human command/motion gate stays the only approval. Deterministic envelope checks belong in code next to the decider (the agentcore README notes the guard did not flag a 10x refund).

2. **Vision decider on camera frames** (`--vision` server with `strands-decider-2B-qwen3.5-v1-2610`, or `--audio`/image on Gemma 4 E2B/E4B via PR #67): send `images: [<base64 frame>]` (up to 4 frames per request) with typed questions such as `choice("What is ahead?", {"clear_track": ..., "obstacle": ..., "off_track": ...})`, `noul("Is a person in the camera view?")`, `score("How centred is the car in the lane?", ["off","edge","centred"])`. Calibrated abstention (`DeciderJudge` pattern: defer when P in [0.2, 0.8] or choice confidence <= 0.6) lets the agent fall back to a VLM or stop. Measured image latency ~200 to 400 ms per request, so this is a per-second supervisory classifier, not a per-frame controller. The user's `robots-decider/bench_decider_judge.py` and the robot judge blog draft (`blog-robots/strands-decider-robot-judge.md`) show the exact three-question episode-labelling request and the deferral logic; the honest finding there was that off-the-shelf v19/v21 were at chance on MuJoCo footage and correctly deferred all 12 episodes, so a DeepRacer-specific fine-tune (decider-lab `finetune:` block, labels from telemetry/off-track events) is the step that turns deferrals into labels.

---

## 3. Strands bidirectional (Bidi) voice agents

### 3.1 Releases and announcements

| Item | Value |
|---|---|
| Graduation out of experimental | **strands-agents python/v1.57.2, 2026-10-01T18:54:51Z**, release note "feat(bidi): graduate bidirectional streaming API (#4707) (8dbc128ea)". https://github.com/strands-agents/harness-sdk/releases/tag/python/v1.57.2 ; changelog page https://strandsagents.com/changelog/sdk/python-v1.57.2/ |
| GA blog | **"Bidi Agents now GA"**, Albert Zhao, Morgan Willis, Rachit Mehta, Patrick Gray, **2026-10-05**, https://strandsagents.com/blog/bidi-agents-now-ga/ |
| Precursors | 1.57.1 (2026-09-25): snapshot capture/restore, explicit model IDs required; 1.57.0 (2026-09-22): retired Nova Sonic 1 removed, audio buffering/processing modules; 1.58.0 (2026-10-06): BidiAgent in SnapshotSessionManager; 1.58.1 (2026-10-06): bidi GA blog polish; 1.59.0 (2026-10-08) |
| Deprecation | `strands.experimental.bidi` is a shim that warns: "strands.experimental.bidi is deprecated and will be removed in v1.60.0. Import from strands.bidi instead." |
| Docs | Overview https://strandsagents.com/docs/user-guide/sdk/bidi/ ; Quickstart https://strandsagents.com/docs/user-guide/sdk/bidi/quickstart/ ; BidiAgent https://strandsagents.com/docs/user-guide/sdk/bidi/agent/ ; Models https://strandsagents.com/docs/user-guide/sdk/bidi/models/ ; I/O Streams https://strandsagents.com/docs/user-guide/sdk/bidi/io/ ; Stream Events https://strandsagents.com/docs/user-guide/sdk/bidi/events/ ; Tools https://strandsagents.com/docs/user-guide/sdk/bidi/tools/ ; API ref https://strandsagents.com/docs/api/python/strands.bidi.agent/ |
| AWS blog (AgentCore) | "Bi-directional streaming for real-time agent interactions now available in Amazon Bedrock AgentCore Runtime", Lana Zhang, Evandro Franco, Phelipe Fabres, 2025-12-18, https://aws.amazon.com/blogs/machine-learning/bi-directional-streaming-for-real-time-agent-interactions-now-available-in-amazon-bedrock-agentcore-runtime/ |
| Nova docs | https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-integrations.html |
| Language | **Python only** ("This feature is only supported in python"); Nova Sonic provider requires **Python 3.12+** |

### 3.2 Public API in the GA version (read from the python/v1.59.0 source tree, `strands-py/src/strands/bidi/`)

Package layout (1.59.0): `strands/bidi/{__init__,agent/{agent,loop,_blocks,_restart_timer},hooks/events,io/{audio,console/,configs},models/{bedrock,google,openai,model,configs},types/{agent,content,events,io,media},_audio/{buffer,processor},_telemetry}.py`.

`strands/bidi/__init__.py` (verbatim):
```python
"""Bidirectional streaming APIs."""

from . import agent, hooks, io, models, types
from .agent import BidiAgent as BidiAgent

__all__ = ["BidiAgent", "agent", "hooks", "io", "models", "types"]
```

**`BidiAgent(LocalAgent)` constructor** (`strands/bidi/agent/agent.py`, verbatim signature):
```python
class BidiAgent(LocalAgent):
    def __init__(
        self,
        model: BidiModel | str | None = None,
        tools: list[str | AgentTool | ToolProvider] | None = None,
        system_prompt: str | list[SystemContentBlock] | None = None,
        messages: Messages | None = None,
        record_direct_tool_call: bool = True,
        agent_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        hooks: list[HookProvider] | None = None,
        state: AgentState | dict | None = None,
        session_manager: "SessionManager[LocalAgent] | None" = None,
        storage: Storage | None = None,
    ):
```
Default model when `model=None`: Bedrock Nova Sonic.

**Methods / properties**: `async start(invocation_state=None)`, `async send(input_data: BidiAgentInput)`, `async receive() -> AsyncGenerator[BidiOutputEvent]`, `async stop()`, `async run(inputs: list[InputStream], outputs: list[OutputStream], invocation_state=None)`, `async with BidiAgent(...) as agent` (`__aenter__`/`__aexit__`), `cancel()` + `cancel_signal` (tool-initiated end, honoured at the end of the tool group), `take_snapshot(preset=..., include=..., exclude=..., app_data=...)` / `load_snapshot(snapshot)`, `add_hook(...)`, `tool` (direct tool caller), `tool_names`, `messages`, `system_prompt`, `session_id`, `storage`, `sandbox`, `context_manager`, `event_loop_metrics`.

`send()` accepted input (`BidiAgentInput`, `types/agent.py`): `str` | `TextBlock` | `ImageBlock` | `{"text": ...}` | `{"image": ...}` | `AudioDelta` | `{"audio_delta": {...}}` | a non-empty list of text/image blocks (one grouped user message). Docstring examples (verbatim):
```python
await agent.send("Hello")
await agent.send(AudioDelta(format="pcm", source={"bytes": audio_bytes}))
await agent.send({"audio_delta": {"format": "pcm", "source": {"bytes": audio_bytes}}})
await agent.send([TextBlock("Use these details."), TextBlock("Order number: 123.")])
```

**Audio input type** `strands/bidi/types/media.py` (verbatim):
```python
@dataclass
class AudioDelta:
    """Audio samples to append to the live input stream.

    Sending a delta does not explicitly end the user's turn.

    Attributes:
        format: Audio format.
        source: Source containing the audio samples.
    """

    format: AudioFormat
    source: AudioSource

    def to_dict(self) -> _AudioDeltaData:
        """Return the dictionary form of this delta."""
        return {"audio_delta": {"format": self.format, "source": self.source}}
```
(`AudioFormat`/`AudioSource` come from `strands.types.media`; raw PCM, mono.)

**Output events** (`strands/bidi/types/events.py`, `BidiOutputEvent` union, verbatim):
```python
BidiOutputEvent = (
    BidiConnectionStartEvent
    | BidiConnectionRestartEvent
    | BidiConnectionWarningEvent
    | BidiResponseStartEvent
    | BidiAudioStartEvent
    | BidiAudioDeltaEvent
    | BidiAudioStopEvent
    | BidiTextStartEvent
    | BidiTextDeltaEvent
    | BidiTextStopEvent
    | BidiTextBlockEvent
    | BidiReasoningStartEvent
    | BidiReasoningDeltaEvent
    | BidiReasoningStopEvent
    | BidiReasoningBlockEvent
    | BidiTranscriptStartEvent
    | BidiTranscriptDeltaEvent
    | BidiTranscriptStopEvent
    | BidiTranscriptBlockEvent
    | BidiBargeInEvent
    | BidiResponseStopEvent
    | BidiUsageEvent
    | BidiConnectionStopEvent
    | BidiToolUseBlocksEvent
)
```
Wire `"type"` strings: `bidi_connection_start|restart|warning|stop`, `bidi_response_start|stop`, `bidi_audio_start|delta|stop`, `bidi_text_start|delta|stop|block`, `bidi_reasoning_*`, `bidi_transcript_start|delta|stop|block`, `bidi_barge_in`, `bidi_usage`, `bidi_tool_use_blocks`. Audio output arrives as `BidiAudioDeltaEvent` (`bidi_audio_delta`). **Barge-in** (interruption) is the `BidiBargeInEvent`; AudioIO clears its playback buffer on it; also a hook `strands.bidi.hooks.events.BidiBargeInEvent`.

**Hooks** (`strands/bidi/hooks/events.py`): `BidiAgentStopEvent`, `BidiResponseStopEvent`, `BidiBargeInEvent`, `BidiBeforeConnectionRestartEvent`, `BidiAfterConnectionRestartEvent` (plus the shared `BeforeToolCallEvent`/`AfterToolCallEvent`, `MessageAddedEvent`, `AgentInitializedEvent` from the regular agent since `BidiAgent` is a `LocalAgent`).

**I/O streams** (`strands/bidi/types/io.py`): protocols `InputStream` (`async start(agent)`, `async stop()`, `__call__() -> Awaitable[BidiAgentInput]`) and `OutputStream` (`__call__(event) -> Awaitable[None]`). Any async callable works (the docs use `websocket.receive_text` directly as an input). Built-ins in `strands.bidi.io`: **`AudioIO(**AudioIOConfig)`** with `.input()`, `.output()`; config keys `audio_processor: bool | AudioProcessorConfig` (WebRTC echo cancellation + noise suppression + AGC, needs `strands-agents[bidi-aec]`), `console: ConsoleIO`, `input_device_index`, `output_device_index`, `input_buffer_size`, `output_buffer_size`, `input_frames_per_buffer` (512), `output_frames_per_buffer` (512); **`ConsoleIO(placeholder=..., show_text, show_reasoning, show_transcript, show_tools)`** for typing/speaking in one terminal. Sample rates are taken from the model via `AudioCapable.get_audio_config()`.

**Model providers** (`strands.bidi.models`; concrete classes lazy-loaded; also importable from `strands.bidi.models.bedrock`, `.openai`, `.google`):

| Provider | Class | Constructor (verbatim kwargs) | Audio | Connection limit / default restart |
|---|---|---|---|---|
| Amazon Bedrock Nova Sonic | `BedrockNovaSonicModel(BidiModel, AudioCapable)` | `(*, boto_session=None, region=None, audio: BedrockNovaSonicAudioConfig=None, voice="matthew", **model_config: ModelConfig)` with `model_id` required (e.g. `"amazon.nova-2-5-sonic"`; v1 `amazon.nova-sonic-v1:0` retired), `params`, `connection` | mono PCM; input/output sample_rate each in **8000 / 16000 / 24000**, default **16000** both | 8 min; `restart_after_s` default **420**; history replay on restart; Python 3.12+ |
| OpenAI Realtime | `OpenAIRealtimeModel` | `(*, transcription_model_id: str | None, api_key=None, organization=None, project=None, timeout_s=3000, voice="alloy", **model_config)` with `model_id` (e.g. `"gpt-realtime-2.1"`) | mono PCM **24000** only; `server_vad` turn detection default (threshold 0.5, prefix 300 ms, silence 500 ms) | 60 min (client timeout 50 min); `params={"output_modalities": ["text"]}` for text-only |
| Google Gemini Live | `GoogleGeminiLiveModel` | `(*, client_args=None, audio: GoogleGeminiLiveAudioConfig=None, voice=None, **model_config)` with `model_id` (e.g. `"gemini-3.8-live"`) | input default **16000**, output **24000** mono PCM; accepts images | ~10 min; session resumption (falls back to replay) |

Shared `ModelConfig` TypedDict: `model_id: Required[str]`, `params: dict | None`, `connection: ConnectionConfig{restart_after_s: int, auto_restart: bool}`. `update_config()` applies on the next connection. Custom providers subclass `BidiModel` (`start/stop/send/receive`), optionally `AudioCapable`, `Restartable`.

Install extras (from quickstart/GA blog): `pip install "strands-agents[bidi,bidi-io,bidi-pyaudio,bidi-aec]"` (Nova Sonic + local audio + echo cancellation), `[bidi-google]`, `[bidi-openai]`, `[bidi-all,bidi-pyaudio]`. PortAudio system lib needed (`brew install portaudio` / `apt-get install portaudio19-dev`).

### 3.3 Verbatim code samples (GA docs)

**Sample 1: minimal mic+speaker voice agent with tools** (quickstart https://strandsagents.com/docs/user-guide/sdk/bidi/quickstart/, verbatim):
```python
import asyncio
from datetime import datetime

from strands import ToolContext, tool
from strands.bidi import BidiAgent
from strands.bidi.io import AudioIO
from strands.bidi.models import BedrockNovaSonicModel


@tool
def get_current_time() -> str:
    """Get the current date and time in the computer's local time zone."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@tool(context=True)
def end_conversation(tool_context: ToolContext[BidiAgent]) -> str:
    """End the conversation when the user says goodbye or asks to stop."""
    tool_context.agent.cancel()
    return "Ending the conversation."


async def main() -> None:
    agent = BidiAgent(
        model=BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic"),
        tools=[get_current_time, end_conversation],
        system_prompt="You are a friendly voice assistant. Keep replies short.",
    )
    # One AudioIO drives both the microphone and the speakers
    audio_io = AudioIO()
    await agent.run(inputs=[audio_io.input()], outputs=[audio_io.output()])


asyncio.run(main())
```
Setup lines from the same page: `pip install "strands-agents[bidi,bidi-io,bidi-pyaudio,bidi-aec]"`, `export AWS_DEFAULT_REGION=us-east-1`, `python voice_agent.py`; echo on open speakers: `audio_io = AudioIO(audio_processor=True)`. Provider swaps: `GoogleGeminiLiveModel(model_id="gemini-3.8-live")`; `OpenAIRealtimeModel(model_id="gpt-realtime-2.1", transcription_model_id="gpt-transcribe")`.

**Sample 2: GA blog voice agent with echo cancellation, plus a research sub-agent tool** (https://strandsagents.com/blog/bidi-agents-now-ga/, verbatim):
```python
import asyncio

from strands.bidi.agent import BidiAgent
from strands.bidi.io import AudioIO
from strands.bidi.models import BedrockNovaSonicModel


async def main():
    model = BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic")

    agent = BidiAgent(
        model=model,
        system_prompt=(
            "You are a helpful voice assistant. "
            "Keep responses concise and conversational."
        ),
    )

    audio = AudioIO(audio_processor=True)

    # Runs until you press Ctrl+C.
    await agent.run(
        inputs=[audio.input()],
        outputs=[audio.output()],
    )


asyncio.run(main())
```
```python
from strands_harness import create_harness

researcher = create_harness(
    instructions=(
        "Research the user's question. "
        "Return a concise answer with sources."
    ),
)

research_tool = researcher.as_tool(
    name="research",
    description="Research questions that need detailed investigation.",
    preserve_context=True,
)

agent = BidiAgent(
    model=model,
    system_prompt=(
        "You are a helpful voice assistant. "
        "Use research when a question needs investigation, "
        "then explain the result conversationally."
    ),
    tools=[research_tool],
)
```

**Sample 3: manual send/receive event loop** (Stream Events page, verbatim):
```python
import asyncio

from strands.bidi.agent import BidiAgent
from strands.bidi.types import (
    BidiResponseStopEvent,
    BidiTranscriptBlockEvent,
)


async def main() -> None:
    async with BidiAgent() as agent:
        await agent.send("Say hello in one sentence.")

        async for event in agent.receive():
            if isinstance(event, BidiTranscriptBlockEvent):
                print(f"{event.role}: {event.transcript}")
            elif isinstance(event, BidiResponseStopEvent):
                break


asyncio.run(main())
```

**Sample 4: custom I/O over a FastAPI WebSocket (browser/robot bridge pattern)** (I/O Streams page, verbatim):
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from strands.bidi.agent import BidiAgent
from strands.bidi.models import OpenAIRealtimeModel
from strands.bidi.types import BidiOutputEvent, BidiTextBlockEvent

app = FastAPI()


@app.websocket("/conversation")
async def conversation(websocket: WebSocket) -> None:
    await websocket.accept()
    model = OpenAIRealtimeModel(
        model_id="gpt-realtime-2.1",
        transcription_model_id=None,
        params={"output_modalities": ["text"]},
    )
    agent = BidiAgent(model=model)

    async def send_text(event: BidiOutputEvent) -> None:
        if isinstance(event, BidiTextBlockEvent):
            await websocket.send_text(event.text)

    try:
        await agent.run(
            inputs=[websocket.receive_text],
            outputs=[send_text],
        )
    except WebSocketDisconnect:
        pass
```

**Sample 5: type-or-speak console, and connection restart tuning** (verbatim):
```python
import asyncio

from strands.bidi.agent import BidiAgent
from strands.bidi.io import AudioIO, ConsoleIO


async def main() -> None:
    agent = BidiAgent()
    console_io = ConsoleIO(placeholder="Type or speak…")
    audio_io = AudioIO(console=console_io)

    try:
        await asyncio.wait_for(
            agent.run(
                inputs=[console_io.input(), audio_io.input()],
                outputs=[audio_io.output()],
            ),
            timeout=30,
        )
    except asyncio.TimeoutError:
        pass


asyncio.run(main())
```
```python
from strands.bidi.models import BedrockNovaSonicModel

model = BedrockNovaSonicModel(
    model_id="amazon.nova-2-5-sonic",
    connection={"restart_after_s": 360},
)
```

### 3.4 Interruption, VAD, lifecycle

- **Barge-in**: provider-detected (Nova Sonic signals via `stopReason: INTERRUPTED` / `{ "interrupted" : true }`; OpenAI via server VAD; Gemini natively). Surfaces as `BidiBargeInEvent` on `receive()` and as a hook; `AudioIO` output clears queued playback and (with `audio_processor=True`) the echo-cancellation far-end buffer. 1.57.2 fix: "defer OpenAI responses during user speech".
- **VAD / turn detection**: OpenAI `server_vad` defaults in `DEFAULT_SESSION_CONFIG`; Nova Sonic v2 `turn_detection.endpointingSensitivity: HIGH|MEDIUM|LOW` via `params`; Gemini uses the Live API's native detection. Microphone-side **WebRTC AEC + noise suppression + AGC** via `AudioIO(audio_processor=True)` / `AudioProcessorConfig(echo_cancellation=..., stream_delay_ms=...)`.
- **Session lifecycle**: `start()` opens the provider connection (system prompt, tools, `messages` history sent at startup); the loop proactively **restarts** before the provider limit (`ConnectionConfig.restart_after_s`, Nova default 420 s of an 8-minute limit), aligning to a turn boundary, replaying history (Nova, OpenAI) or using session resumption (Gemini); `BidiConnectionRestartEvent` carries `reason` and `turn_interrupted`; tool results finishing across a restart are still delivered (1.57.2 fix). `stop()` cancels background tasks and closes the connection; `cancel()` from a `@tool(context=True)` ends the conversation after the tool group finishes. Persistence: `session_manager` (SnapshotSessionManager support from 1.58.0) and `take_snapshot()/load_snapshot()`; `storage` for agent-level file storage (1.57.2).
- **Observability**: OTEL spans for session, model response (time to first audio chunk), tool calls, connection establishment and restarts; `StrandsTelemetry().setup_console_exporter()`; redaction via `OTEL_SEMCONV_STABILITY_OPT_IN="gen_ai_unredacted_attributes="`.
- **Tools mid-conversation**: same `@tool` decorator as `Agent`; async tools run concurrently while audio continues; `ToolContext[BidiAgent]` gives tools the agent; `invocation_state` is shared with tools and hooks across restarts.

### 3.5 Locally installed version vs latest (the delta)

Local environment (`pip3 show strands-agents`): **strands-agents 1.38.0** (released 2026-04-30) at `/opt/miniconda3/lib/python3.13/site-packages/strands` (Python 3.13). `strands.__version__` does not exist (AttributeError). **`strands.bidi` does not exist** in 1.38.0 (`ModuleNotFoundError`). What exists is **`strands.experimental.bidi`** with these modules:

```
strands.experimental.bidi.agent.agent, .agent.loop, .io.audio, .io.text,
strands.experimental.bidi.models.{model, nova_sonic, openai_realtime, gemini_live},
strands.experimental.bidi.tools.stop_conversation,
strands.experimental.bidi.types.{agent, events, io, model}
```

Installed 1.38.0 experimental API (read from source):
- `BidiAgent(model: BidiModel | str | None, tools, system_prompt: str | None, messages, record_direct_tool_call, load_tools_from_directory, agent_id, name, description, hooks, state, session_manager, tool_executor, **kwargs)`; methods `start()`, `send()`, `receive()`, `stop()`, `run(inputs: list[BidiInput], outputs: list[BidiOutput], invocation_state)`, async context manager. No `cancel()`, no `storage`, no snapshots, no `LocalAgent` base.
- Models: `BidiNovaSonicModel(model_id="amazon.nova-2-sonic-v1:0", provider_config={"audio": {...}, "inference": {...}, "turn_detection": {...}}, client_config={...})`, `BidiOpenAIRealtimeModel(model_id="gpt-realtime", provider_config, client_config)`, `BidiGeminiLiveModel(model_id="gemini-2.5-flash-native-audio-preview-09-2025", ...)`. Audio defaults: Nova 16 kHz in/out, OpenAI 24 kHz, Gemini 16 k in / 24 k out. `BidiModelTimeoutError` drives restart.
- IO: `BidiAudioIO(**config)` (PyAudio, no echo cancellation), `BidiTextIO(**config)` (prompt_toolkit). Protocols `BidiInput` / `BidiOutput`.
- Events: input `BidiTextInputEvent(text, role)`, `BidiAudioInputEvent(audio: base64 str, format, sample_rate: 16000|24000|48000, channels)`, `BidiImageInputEvent(image, mime_type)`; output `BidiConnectionStartEvent`, `BidiConnectionRestartEvent`, `BidiResponseStartEvent`, `BidiAudioStreamEvent`, `BidiTranscriptStreamEvent`, `BidiInterruptionEvent(reason="user_speech"|"error")`, `BidiResponseCompleteEvent(stop_reason)`, `BidiUsageEvent`, `BidiConnectionCloseEvent`, `BidiErrorEvent`, plus `ToolUseStreamEvent`.
- Hooks: `BidiAgentInitializedEvent`, `BidiMessageAddedEvent`, `BidiBeforeInvocationEvent`, `BidiAfterInvocationEvent`, `BidiBefore/AfterConnectionRestartEvent`, `BidiInterruptionEvent` (hook).
- Deprecated tool `stop_conversation`.

Rename map 1.38.0 experimental -> 1.57.2+/1.59.0 GA:

| 1.38.0 `strands.experimental.bidi` | 1.59.0 `strands.bidi` |
|---|---|
| `BidiNovaSonicModel(model_id=..., provider_config=, client_config=)` | `models.BedrockNovaSonicModel(model_id=..., voice=, audio=, params=, connection=, boto_session=, region=)` |
| `BidiOpenAIRealtimeModel` | `models.OpenAIRealtimeModel(model_id=..., transcription_model_id=...)` |
| `BidiGeminiLiveModel` | `models.GoogleGeminiLiveModel` |
| `BidiAudioIO` / `BidiTextIO` | `io.AudioIO(audio_processor=..., console=...)` / `io.ConsoleIO(...)` |
| `BidiInput` / `BidiOutput` protocols | `types.InputStream` / `types.OutputStream` |
| `BidiAudioInputEvent(audio=b64, format, sample_rate, channels)` | `types.media.AudioDelta(format, source={"bytes": ...})` or `{"audio_delta": ...}` |
| `BidiTextInputEvent` / `BidiImageInputEvent` | plain `str` / `TextBlock` / `ImageBlock` / dict / list |
| `BidiAudioStreamEvent` | `BidiAudioStartEvent` / `BidiAudioDeltaEvent` / `BidiAudioStopEvent` |
| `BidiTranscriptStreamEvent(is_final)` | `BidiTranscriptStart/Delta/Stop/BlockEvent` |
| `BidiInterruptionEvent` | `BidiBargeInEvent` |
| `BidiResponseCompleteEvent` | `BidiResponseStopEvent` |
| `BidiConnectionCloseEvent` / `BidiErrorEvent` | `BidiConnectionStopEvent` / `BidiConnectionWarningEvent` (errors propagate from `receive()`/`run()`) |
| (none) | `BidiTextBlockEvent`, `BidiReasoning*Event`, `BidiToolUseBlocksEvent`, `cancel()`, `storage`, snapshots, `connection={"restart_after_s": ...}` |
| `stop_conversation` tool | `@tool(context=True)` calling `tool_context.agent.cancel()` |
| default Nova model id `amazon.nova-2-sonic-v1:0` (implicit) | `model_id` **required**, docs use `amazon.nova-2-5-sonic` |

Practical consequence: the DeepRacer project should `pip install -U "strands-agents[bidi,bidi-io,bidi-pyaudio,bidi-aec]"` (>= 1.57.2, ideally 1.59.0) and write against `strands.bidi`; the 1.38.0 experimental code paths will stop working at 1.60.0. Nova Sonic needs Python 3.12+ (the car's Ubuntu image must satisfy that; the user's Macs have python3.12 at `/opt/homebrew/bin/python3.12`).

---

## 4. SDK release train and related packages (brief)

**strands-agents (Python SDK).** Latest on PyPI: **1.59.0, uploaded 2026-10-08T13:40:22Z** (https://pypi.org/project/strands-agents/). The SDK now lives in the monorepo https://github.com/strands-agents/harness-sdk (tags `python/v1.59.0`, `typescript/v1.20.0`, `harness-python/v0.2.0`, `harness-cli/v0.2.0`, `mcp/v0.3.0`; the old `sdk-python` URL redirects); changelog at https://strandsagents.com/changelog/sdk/. Cadence is roughly weekly: 1.55.0 (09-08), 1.56.0 (09-15), 1.57.0 (09-22), 1.57.1 (09-25), 1.57.2 (10-01), 1.58.0 (10-06), 1.58.1 (10-06), 1.59.0 (10-08). `requires_python >=3.10`. The locally installed 1.38.0 is 21 minor releases and five months behind; notable things it lacks besides bidi GA: `LocalAgent` parity, interventions API (`strands.interventions`, used by the decider example), `strands.vended_tools`, snapshot session manager, agent `storage`, context manager stash.

**strands-agents-tools.** Latest **0.8.9, uploaded 2026-09-15T22:36:25Z** (https://pypi.org/project/strands-agents-tools/, repo https://github.com/strands-agents/tools). Locally installed: **0.2.2** (very old; the 0.3 to 0.8 line adds many tools and the `strands_tools.stop` tool the bidi docs reference). `requires_python >=3.10`.

**strands-amazon-nova.** PyPI latest **1.0.2, uploaded 2025-12-02**, "Amazon Nova API model provider for Strands Agents SDK", homepage https://github.com/amazon-nova-api/strands-nova; provides `NovaAPIModel` (httpx, SSE streaming, tool calling) for the Nova API (Nova Pro, Premier, reasoning models). Locally installed 1.0.2 (requires httpx, pydantic, python-dotenv, strands-agents). Note this is a community/Nova-API-key provider, separate from the built-in `strands.models.BedrockModel` (Nova on Bedrock) and from Nova Sonic bidi (`strands.bidi.models.BedrockNovaSonicModel`). The AWS Nova docs list Strands as a Nova Sonic integration: https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-integrations.html.

**Bedrock AgentCore Runtime relevance for a robot agent.** AgentCore Runtime gives each session its own dedicated MicroVM (the cloud counterpart of Strands Box, per Brooker's post) and since 2025-12-18 supports **bidirectional WebSocket streaming**: the container exposes `/ws` (and `/ping`) on port 8080, clients connect to `wss://bedrock-agentcore.<region>.amazonaws.com/runtimes/<agentRuntimeArn>/ws` with SigV4 or OAuth 2.0, and one container can serve both `InvokeAgentRuntime` and `InvokeAgentRuntimeWithWebsocketStream`; the blog shows a Strands `BidiAgent` + Nova Sonic server in ~20 lines versus ~150 native (https://aws.amazon.com/blogs/machine-learning/bi-directional-streaming-for-real-time-agent-interactions-now-available-in-amazon-bedrock-agentcore-runtime/). For a DeepRacer agent this is the natural place to host the *voice/reasoning* agent (bidi over WebSocket to the car or a phone), with the car running a thin ROS 2 bridge; the user's `strands-decider-agentcore` repo and memory notes show the constraints: 2 vCPU / 8 GB Graviton microVMs, `runtimeSessionId` >= 33 chars, cold starts of 45 to 90 s, 30-minute idle timeout, and CPU-bound inference (so decider gating belongs on-device or on GPU, not in the AgentCore microVM, unless latency of seconds is acceptable). Deployment tooling: AgentCore CLI (`npm install -g @aws/agentcore`, `agentcore deploy -y`, CodeBuild arm64 images), `bedrock-agentcore` SDK 1.18.0 and `bedrock-agentcore-starter-toolkit` 0.3.10 are installed locally.

---

## 5. Source index

Strands Box: https://github.com/strands-agents/box ; https://github.com/strands-agents/box/releases/tag/v0.1.0 ; https://aws.amazon.com/blogs/opensource/introducing-strands-box-ai-agent-sandboxes-powered-by-dogwood/ ; https://strandsagents.com/blog/strands-box-the-big-picture/ ; https://strandsagents.com/docs/user-guide/box/ ; https://strandsagents.com/docs/user-guide/box/getting-started/ ; https://dogwood-policy.github.io/dogwood/ ; https://thenewstack.io/aws-strands-labs-launch/ ; https://www.theregister.com/ai-and-ml/2026/10/07/aws-launches-open-source-ai-agent-sandbox-to-prevent-yolo-mode-disasters/5301687 ; https://www.helpnetsecurity.com/2026/10/12/aws-strands-box-open-source-ai-agent-sandbox/

Deciders: https://github.com/strands-labs/strands-decider ; https://strandsagents.com/blog/introducing-strands-decider/ ; https://pypi.org/project/strands-decider/ ; https://huggingface.co/StrandsAgents ; https://github.com/strands-labs/strands-decider/issues/45 ; https://github.com/strands-labs/strands-decider/pull/10 ; https://github.com/strands-labs/strands-decider/pull/67 ; https://github.com/Vivek0712/decider-lab ; https://github.com/Vivek0712/strands-decider-agentcore ; https://github.com/strands-labs/robots/pull/4573 ; local (the author's decider checkouts): VISION_DECIDER_RESEARCH.md, LINEAGE.md, the strands-decider README and examples/strands/, the decider-lab and strands-decider-agentcore READMEs, robots-decider/, blog/strands-decider-multimodal.md

Bidi: https://strandsagents.com/blog/bidi-agents-now-ga/ ; https://strandsagents.com/docs/user-guide/sdk/bidi/ (+ quickstart/, agent/, models/, io/, events/, tools/) ; https://strandsagents.com/changelog/sdk/python-v1.57.2/ ; https://github.com/strands-agents/harness-sdk/releases/tag/python/v1.57.2 ; https://github.com/strands-agents/harness-sdk/tree/python/v1.59.0/strands-py/src/strands/bidi ; https://aws.amazon.com/blogs/machine-learning/bi-directional-streaming-for-real-time-agent-interactions-now-available-in-amazon-bedrock-agentcore-runtime/ ; local: /opt/miniconda3/lib/python3.13/site-packages/strands/experimental/bidi/

Release train: https://pypi.org/project/strands-agents/ ; https://pypi.org/project/strands-agents-tools/ ; https://pypi.org/project/strands-amazon-nova/ ; https://github.com/amazon-nova-api/strands-nova ; https://github.com/strands-agents/harness-sdk/releases
