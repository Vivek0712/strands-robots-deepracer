# strands-robots (strands-labs/robots) deep dive: DeepRacer, Ackermann, ROS/rosbridge transports

Source: read-only worktree of upstream `main @ d504fedd` (2026-10-12), tag `v0.5.3` (2026-10-07) + 50 commits
(`git describe` -> `v0.5.3-50-gd504fedd`). All paths are relative to the repo root; every cite is `file:line`
as read from that worktree. Quoted code is exact.

Scope: how the DeepRacer/Ackermann driver, the three ROS transports (rclpy, rosbridge WebSocket, raw RTPS),
the agent tools over them, the command gate, the mesh, the dashboard voice console and the contribution rules
fit together, so an "agentic DeepRacer" project can build on strands-robots without re-reading it.

---

## 1. ARCHITECTURE LAYERING, REFUSAL CONVENTIONS, GATES, HOUSE STYLE

### 1.1 The seven-layer import DAG

The layer map is NOT in AGENTS.md; it is declared once in `scripts/check_import_layers.py` and pinned by
`tests/test_import_layers_are_a_dag.py`. The script's docstring states the order:

```
core -> registry -> drivers|mesh -> sim|policies -> app -> tools -> dashboard
```
(`scripts/check_import_layers.py:7`)

The membership table (`scripts/check_import_layers.py:84-152`), relevant members only:

| layer (index) | members that matter for ROS/DeepRacer |
|---|---|
| `core` (0) | `_command_gate`, `_hitl_audit`, `_motion_grants`, `_pacing`, `audit`, `locomotion_envelope`, `refusal_codes`, `utils` (`:85-112`) |
| `registry` (1) | `assets`, `registry` (`:114`) |
| `drivers\|mesh` (2) | `device_connect`, `drivers`, `foxglove`, `mesh`, `ros`, `rosbridge`, `ros_telemetry`, `rtps`, `teleop`, `teleop_mixin`, `teleoperator` (`:115-129`) |
| `sim\|policies` (3) | `inference`, `policies`, `simulation`, `training` (`:130`) |
| `app` (4) | `doctor`, `hardware_observe`, `hardware_robot`, `hardware_ros_bridge`, `hardware_rtps_bridge`, `robot`, `verify_dataset` (`:131-142`) |
| `tools` (5) | `tools` (`:143`) |
| `dashboard` (6) | `__main__`, `dashboard` (`:144`) |

Consequences for a new project / contribution:

* The ROS **transports** (`strands_robots/ros.py`, `rosbridge.py`, `rtps/`) sit in `drivers|mesh`, *below* `tools`.
  A driver may import `strands_robots.ros.ros_action` but must never import `strands_robots.tools.use_ros`
  (that was the inversion fixed by #3873/#3871; see changelog.d/3873 in section 4.8).
* `_command_gate`, `_hitl_audit`, `_motion_grants`, `audit`, `refusal_codes` are `core` so *every* layer may use them.
* `KNOWN_UPWARD_EDGES` is empty (`scripts/check_import_layers.py:164`); the only tolerated deferred inversion is
  `("strands_robots.drivers.rollout", "strands_robots.policies")` (`:178-180`). Adding a new upward import
  (even inside a function) fails `tests/test_import_layers_are_a_dag.py` until it is written down there.
* No module may import the package root `strands_robots` (`tests/test_import_layers_are_a_dag.py:17-20`).
* Pin of the order: `tests/test_import_layers_are_a_dag.py:89-99`:
  ```python
  assert mod.LAYER_NAMES == ("core","registry","drivers|mesh","sim|policies","app","tools","dashboard")
  ```
* Typing-only imports (`if TYPE_CHECKING:`) are exempt from both cycle and direction grading; late imports are
  exempt from cycles but *graded for direction* (`tests/test_import_layers_are_a_dag.py:22-30`).
* Every top-level member must have a layer (`:101-103`), so a new top-level module (e.g. `strands_robots/deepracer.py`)
  must be added to `LAYERS` or the suite fails.

### 1.2 Lazy exports (`strands_robots/__init__.py`)

The package root is PEP 562 lazy. Light imports are only `MockPolicy, Policy, create_policy, list_providers,
register_policy` (`strands_robots/__init__.py:96-102`). Everything else is in `_LAZY_IMPORTS` (`:108-169`):

```python
"Robot": ("strands_robots.robot", "Robot"),                                   # :110
"HardwareRosBridge": ("strands_robots.hardware_ros_bridge", "HardwareRosBridge"),  # :111
"HardwareRtpsBridge": ("strands_robots.hardware_rtps_bridge", "HardwareRtpsBridge"),  # :112
...
"use_ros": ("strands_robots.tools.use_ros", "use_ros"),                       # :152
"use_rosbridge": ("strands_robots.tools.use_rosbridge", "use_rosbridge"),     # :153
"use_rtps": ("strands_robots.tools.use_rtps", "use_rtps"),                    # :154
"robot_mesh": ("strands_robots.tools.robot_mesh", "robot_mesh"),              # :156
```
`__getattr__` (`:277-299`) imports on first access, caches into `globals()`, and converts an `ImportError`
into a warning + `AttributeError`. NOTE: the mobile-base drivers (`AckermannRosRobot`, `RosBridgedRobot`,
`RosbridgeRobot`, `RtpsRobot`, `MobileBaseRobot`) are **not** root exports; import them from
`strands_robots.drivers.ros` (`strands_robots/drivers/ros/__init__.py:11-26`). The old `strands_robots.mesh.*`
spellings still resolve with a `DeprecationWarning` until 0.7 (`strands_robots/mesh/__init__.py:58-127`).

Module-import side effects at root: MuJoCo GL auto-config if `mujoco` is installed (`:247-261`) and the macOS
dyld shim for ffmpeg (`:269-274`).

### 1.3 Refusal-code convention (`strands_robots/refusal_codes.py`)

Only *continuable* refusals (an operator grant makes the identical request succeed) carry a code
(`refusal_codes.py:22-26`). Five codes (`:51-72`), closed vocabulary `REFUSAL_CODES` (`:75-81`) and the grant
variable per code `REFUSAL_GRANTS` (`:95-101`):

| code | subject | grant env var |
|---|---|---|
| `TRUST_REMOTE_CODE_REQUIRED` | provider name | `STRANDS_TRUST_REMOTE_CODE=1` |
| `HF_REPO_NOT_ALLOWED` | repo id | `STRANDS_MESH_HF_REPO_ALLOW` (append subject) |
| `POLICY_TYPE_NOT_ALLOWED` | type/provider | `STRANDS_MESH_POLICY_TYPE_ALLOW` (append) |
| `POLICY_HOST_NOT_ALLOWED` | host | `STRANDS_MESH_POLICY_HOST_ALLOW` (append) |
| `TELEOP_VALUE_OUT_OF_RANGE` | joint key | `STRANDS_MESH_INPUT_VALUE_ABS` (raise bound) |

Exceptions carry `exc.code` / `exc.subject` structurally (`:18-20`). A static scan checks every raise site spells
a declared code (`:34-43`). `docs/reference/refusal-codes.md` renders the table via the `{{refusals}}` mkdocs hook
(`docs/hooks/refusals.py:1-11`). The ROS gate refusals are **not** coded; they are plain error envelopes whose
text names the remedy (section 1.4).

The *other* refusal convention, pervasive in drivers: a verb never raises; it returns the tool envelope
`{"status": "error", "content": [{"text": reason}]}` via `strands_robots.drivers.base.refuse`
(`strands_robots/drivers/base.py:346-355`). Value-domain guards live in `strands_robots/utils.py` and are shared
(`positive_finite_number_error:707`, `finite_number_error:744`, `positive_whole_number_error:773`,
`positive_count_error:883`, `tcp_port_error:903`, `dial_host_error:953`, `dds_domain_id_error:1098`,
`boolean_flag_error:2251`, `partial_construction_repr:2272`, `require_optional:22`, `require_optionals:84`).
AGENTS.md rule 11 says a guard becomes shared only when it has a second caller (`AGENTS.md:95-104`).

### 1.4 The command gate (`strands_robots/_command_gate.py`)

One owner of the operator-approval decision for every transport (`_command_gate.py:1-17`). The blocklist is a
statement about physical surfaces, matched by final path segment:

```python
COMMAND_BLOCKLIST = frozenset({
    "/cmd_vel", "/cmd_vel_unstamped", "/manual_drive", "/joint_command", "/joint_trajectory",
    "/joint_trajectory_controller/joint_trajectory", "/emergency_stop", "/e_stop", "/motor_enable",
    "/enable_motor", "/disable_motor", "/vehicle_state", "/enable_state", "/navigate_to_pose", "/follow_path",
})                                                   # _command_gate.py:74-92
COMMAND_ALLOW_ENV = "STRANDS_ROS2_COMMAND_ALLOW"     # :94
BYPASS_CONSENT_ENV = "BYPASS_TOOL_CONSENT"           # :95
PHYSICAL_MOTION_ACTIONS = frozenset({"execute", "start", "teleop_receive", "reset", "step"})  # :108
```
The DeepRacer entries are explained in the comment: "`/manual_drive` covers the DeepRacer's
`/webserver_pkg/manual_drive`, and `/vehicle_state` and `/enable_state` cover the `/ctrl_pkg/...` services that
arm it" (`:67-70`).

* `canonical_command_name` (`:118-143`): adds a leading `/`, strips trailing `/`, preserves case; used for
  comparison only, never to redirect the command.
* `match_blocklist(name, blocked)` (`:146-167`): exact match or `"/" + last_segment == entry`. So `/cmd_vel`
  blocks `/robot1/cmd_vel`; `*` canonicalises to `/*` and matches nothing (`:274-278`).
* `gate_command(kind, name, tool_context, *, tool)` (`:177-212`): blocklist front; returns a refusal string or
  `None`.
* `gate_motion(tool, action, target, warning, tool_context, *, allow_env, allow_match=None)` (`:350-450`),
  decision order:
  1. `allow_env` names the target -> allow silently (`:407-412`).
  2. `BYPASS_TOOL_CONSENT=true` -> allow with a WARNING log (`:414-416`).
  3. `tool_context is None` -> refuse with `_no_operator_remedy` naming `STRANDS_ROS2_COMMAND_ALLOW=<value>` and
     `BYPASS_TOOL_CONSENT=true` (`:418-422`, `:252-303`).
  4. `tool_context.interrupt(f"{tool}-command-approval", reason={action,target,warning,how_to_answer})`
     (`:424-435`); `RuntimeError` from the host -> same remedy (`:436-442`).
  5. `approve_response` accepts only `y|yes|approve|approved` (`:110-115`); the reply is audited on BOTH outcomes
     via `log_operator_response(f"{tool}_tool", ...)` and never returned to the model (`:444-447`).
* Interrupt id for every ROS transport is `use_ros-command-approval` / `use_rosbridge-command-approval` /
  `use_rtps-command-approval` because each transport exposes `GATE_TOOL` (`ros.py:67`, `rosbridge.py:68`,
  `rtps/participant.py:53`) and the drivers reuse it.
* `how_to_answer` tells a script how to resume: `agent([{"interruptResponse": {"interruptId": <id>, "response": "y"}}])`
  (`:342-347`).

### 1.5 Motion grants (`strands_robots/_motion_grants.py`)

A browser "yes" from the dashboard's `MotionInterruptHook` is deposited here so the tool does not ask twice
(`_motion_grants.py:1-8`). Lives in `core` so `hardware_robot`, `pose_tool`, `serial_tool` spend it without
importing the dashboard (`:10-28`).

* TTL: `STRANDS_DASH_MOTION_GRANT_TTL_S`, default `900.0` s (`:80-81`), re-read on every spend (`:198-218`).
* Identity: `grant_key(tool_name, tool_input, *, calibration)` = `repr((tool, action, resolve_target(...),
  instruction|message, f"calibration={calibration_identity(...)}", *motion_fields))` (`:350-401`).
* `DETAIL_FIELDS` (`:127-156`) is the roster of motion-bearing fields read both for the operator line and the key
  (`calibration, robot_id, pose_name, motor_name, motor_id, positions, position, velocity, delta, steps,
  step_delay, smooth, data, hex_data, baudrate, duration, source_peer_id, device_name, policy_provider,
  policy_host, policy_port, policy_type, pretrained_name_or_path, model_path, embodiment, walk,
  target_velocity, policy_config`). A new gated tool parameter must be in `DETAIL_FIELDS`, a fixed key part, or
  `UNKEYED_FIELDS` (`:158-169`) or a structural test fails.
* `deposit_grant(tool_name, tool_input, *, actor)` (`:404-423`), `consume_grant(...)` true exactly once and only
  for the same `actor` (`:426-482`), `forget_grants_for_peer` (`:485-508`), `pending_grants` (`:511-528`).
* ROS mobile-base tools (`drive_<node>`, `stop_<node>`) do **not** consult grants; they go straight to
  `gate_command` via `tool_context.interrupt`. Grants matter only when a DeepRacer joins the dashboard agent as a
  mesh peer (section 9).

### 1.6 Locomotion envelope (`strands_robots/locomotion_envelope.py`)

Plausibility bound on a mesh `target_velocity` for legged policies, shared by `mesh.security` and `WBCPolicy`
(`:1-12`). `MAX_TARGET_LINEAR_VELOCITY_MPS = 2.0`, `MAX_TARGET_ANGULAR_VELOCITY_RPS = 2.0` (`:37-40`), overrides
`STRANDS_MAX_TARGET_LINEAR_VELOCITY_MPS` / `STRANDS_MAX_TARGET_ANGULAR_VELOCITY_RPS` (`:44-47`), re-read per call.
Index 0/1 linear, index 2 angular (`:24-28`); a command over the bound is **refused, not clamped** (`:17-21`,
`target_velocity_component_error:80-102`). This does NOT apply to the ROS mobile bases, which clamp to their own
`max_linear`/`max_angular`/`max_speed` (section 4). A DeepRacer that is driven over the mesh `execute` path with a
`target_velocity` would be held to it.

### 1.7 HITL audit (`strands_robots/_hitl_audit.py`)

Single owner of the operator-response audit row (`:1-10`). Four gates: `robot_mesh`, `use_ros` (publish /
service_call / action_send_goal onto a blocklisted surface), `lerobot_train` extra_flags, and the dashboard motion
hook (`:4-10`). `log_operator_response(source, action, target, *, approved, response)` (`:63-118`) writes
`audit.log_safety_event("llm_tool_action", source, {"action","target","success","detail": "operator approved|declined: <repr>"[:500]})`
and swallows failures at DEBUG (`:104-118`). The audit log is `~/.strands_robots/mesh_audit.jsonl`
(`STRANDS_MESH_AUDIT_DIR`), HMAC-signed with `STRANDS_MESH_AUDIT_PSK` (`docs/learn/agents.md:89-91`,
`docs/learn/security.md:51-55`).

### 1.8 House style and contribution rules (AGENTS.md + changelog.d/README.md)

AGENTS.md is capped at 30 KB (`AGENTS.md:296`). Key conventions, numbered as in the file (`AGENTS.md:66-255`):

1. Python 3.12+ (`:68`); `requires-python = ">=3.12"` (`pyproject.toml:13`).
2. Dependency bounds: `>=1.0` deps cap the major, `<1.0` deps cap the minor (`:69`).
3. `__init__.py` thin, exports only (`:70`).
4. Imports at file top unless lazy-loading heavy deps with a documented reason (`:71`).
5. Raise on fatal errors; never warn-and-continue (`:72`).
6. No silent defaults on error; zero-valued actions on failure are forbidden (`:73`).
7. `require_optional()` for optional deps; `ImportError.name` must carry the module (`:74-91`).
8. Integration tests required per policy (`:92`).
9. Test behaviour, not implementation (`:93`).
10. No dead code (`:94`).
11. A value-domain guard becomes shared only with a second caller (`:95-104`).
12. Security floors for transitive packages go in `[tool.uv] constraint-dependencies` with the GHSA id (`:106-118`).
13. Every `@tool` parameter needs its own `Args:` entry; `docstring_parser` derives the schema and substitutes
    `"Parameter <name>"` otherwise; pinned by `tests/tools/test_agent_tool_parameter_descriptions.py` (`:120-133`).
14. `__repr__` must not raise; wrap in `try/except AttributeError` and return `partial_construction_repr(self)`
    (`:134-145`). Every ROS driver does this (`ackermann_robot.py:514-521`, `rosbridge_robot.py:436-443`,
    `_mobile_base.py:671-678`, `rtps_robot.py:197-204`).
15. Recording tests name their own `root=tmp_path/...` (`:147-171`).
16. An example attests only the records it shows (`verify_audit_integrity(records)`) (`:173-190`).
17. A mesh transport delegates to `_*_directly` session helpers, never the router (`:192-210`).
18. **The rule a DeepRacer bridge lives under**: "A new bridge is un-gated until its surfaces are named, and refused
    until it forwards the context" (`:212-232`). Both halves ship together: add blocklist entries *spelled bare*
    (final-segment matching) AND thread `tool_context` through every `use_ros` call with `@tool(context=True)` on
    the command tools; state the pre-approval posture in the docs and the example because
    `STRANDS_ROS2_COMMAND_ALLOW` cannot be discovered from a refusal that has not happened. Pinned by
    `tests/mesh/test_ackermann_command_gate.py`, whose inventory of bridges is derived from the tree
    (`tests/mesh/test_ackermann_command_gate.py:332-363`). (The rule still cites
    `docs/reference/ros2-integration.md` and `docs/reference/security.md`, which were folded into
    `docs/learn/ros2.md` / `docs/learn/security.md` by the site rewrite; mkdocs redirects at `mkdocs.yml:239-248`.)
19. A backend may add a parameter but must never permute a shared one (`:233-255`).

PR workflow (`AGENTS.md:257-276`):
1. Branch on **your fork** (the base repo refuses new refs for every role).
2. Gate locally: `hatch run format && hatch run lint && hatch run test`, plus `hatch run whole-tree-check`
   when the run is narrowed with `-k`/paths.
3. Add `changelog.d/<pr-number>-<slug>.md`; never edit `## [Unreleased]` in `CHANGELOG.md`; enforced by
   `scripts/ci_guards.py` -> `scripts/check_changelog_fragment.py`.
4. Lint clean, tests pass. 5. Open PR from the fork; a push after approval needs a new approval. 6. Track follow-ups
   on the project board (`https://github.com/orgs/strands-labs/projects/2`, `AGENTS.md:9-14`). 7. Squash merge.
   8. Read PR state back (`mergeStateStatus`, `reviewDecision`), never infer.

Changelog fragment rules (`changelog.d/README.md:28-60`, enforced by `tests/test_changelog_fragments.py`):
* File `changelog.d/<number>-<slug>.md`; `0000` and `999x` are refused placeholders.
* Content: exactly one level-3 heading `### <Category>: <summary>` (Fixed/Added/Docs/Security/Changed...) then
  prose; no `## ` heading; nothing else may live in the directory.
* Validate: `python scripts/assemble_changelog.py --check` / `--print`; release folds with `--apply`.
* Real examples of the house voice: changelog.d/1035, 3541, 2705, 2839 quoted in section 4.8. The style is a
  measured narrative: what was observed (often with a literal before/after), why it was wrong, what changed,
  which test pins it.

Test conventions observed in the tree:
* Test module names are sentences describing the behaviour (`tests/mesh/test_drive_reports_a_refused_trailing_stop.py`,
  `tests/test_every_ros_transport_consults_the_command_gate.py`); a tracker number may not appear in the module
  name (`tests/test_test_module_names_do_not_spell_a_tracker_coordinate.py`).
* Every bridge test replaces the transport symbol with the shared `tests/mesh/_transport_stand_in.py` recorder,
  which binds against the real callable's signature so a forgotten `gate=` is refused
  (`_transport_stand_in.py:1-16, 49-76`). Use `stands_in_for(monkeypatch, module, "ros_action")`.
* "Refusal table" convention (the last ~20 commits, #4707-#4728, e.g. `d504fedd test: RL run size ... join the RL
  refusal table, not 182 cells`): a domain suite enumerates the probe values and the surfaces in module-level
  tables and asserts every facet of one refused value in one parametrised cell per surface, rather than
  `values x surfaces x facets` cells. `tests/mesh/test_drive_command_numeric_domains.py:63-125` is the ROS instance:
  `_TRANSPORTS` (one row per bridge with its constructor and expected wire fields), `UNUSABLE_VELOCITIES`,
  `UNUSABLE_DURATIONS`, `UNUSABLE_COUNTS`, `_COMMAND_DOMAINS` mapping each knob to the shared guard that words its
  refusal; parity is asserted on the *reason text*, not only on `status == "error"`.
* Inventories are derived from the tree, not hand-kept (every "a fifth bridge fails on arrival" sentence):
  `tests/mesh/test_ackermann_command_gate.py:343-358`, `tests/test_every_ros_transport_consults_the_command_gate.py:342-380`,
  `tests/mesh/test_drive_contract_fleet_scope.py:232`, `scripts/check_whole_tree_graders.py:26-40`.
* Hermetic gate tests delete `BYPASS_TOOL_CONSENT` and `STRANDS_ROS2_COMMAND_ALLOW` in an autouse fixture
  (`tests/mesh/test_ackermann_command_gate.py:111-118`).
* Package-wide contracts: ASCII-only tool text (`tests/tools/test_use_ros.py:15-21`), structured error dicts never
  raised (`:19-21`).

Docs hooks that a contribution must satisfy (`mkdocs.yml:80-94`; `docs/hooks/*.py`):
* `facts.py` `{{n:key}}` counts derived from the tree (`tools`, `native_drivers`, ...) (`docs/hooks/facts.py:1-30`).
* `tools_ref.py` `{{tools_ref}}` builds the tool catalog from every `@tool` and its `action` values
  (`docs/hooks/tools_ref.py:1-16`); `docs/reference/tools.md:24` is just `{{tools_ref}}`.
* `module_map.py` renders `LAYERS` from `scripts/check_import_layers.py` (`docs/hooks/module_map.py:1-16`).
* `refusals.py` renders `REFUSAL_CODES` (`docs/hooks/refusals.py:1-11`).
* `env_vars.py` derives every env var the package reads via AST (`docs/hooks/env_vars.py:1-25`).
* `word_budget.py`: every page <= 900 words (`docs/hooks/word_budget.py:1-18`,
  `tests/test_docs_pages_are_within_the_word_budget.py:125-126`); site ceiling `_SITE_BUDGET = 69_737` (`:104`).
* `check_fences.py` runs every bare ```python fence; `check_sketches.py` statically verifies
  ```python title="sketch"``` fences (imports, `Robot(...)` kwargs, `action=` values) (`docs/hooks/check_sketches.py:1-28`).

---

## 2. ROS TRANSPORTS

Three wire paths, one gate. The transports are library modules in the `drivers|mesh` layer; the agent tools in
section 3 are thin envelopes over them; the drivers in section 4 forward through them.

| module | protocol | needs on this machine | callers |
|---|---|---|---|
| `strands_robots/ros.py` | in-process `rclpy` + `rosidl_runtime_py` dynamic types | a sourced ROS 2 distro; `rclpy` is not on PyPI (`ros.py:18-26`) | `tools/use_ros.py`, `drivers/ros/ros_bridge.py`, `drivers/ros/ackermann_robot.py`, `drivers/yahboom_m3pro.py` |
| `strands_robots/rosbridge.py` | rosbridge JSON over WebSocket via `roslibpy` | `pip install "strands-robots[rosbridge]"` (`rosbridge.py:19-26`) | `tools/use_rosbridge.py`, `drivers/ros/rosbridge_robot.py`, `drivers/yahboom_m3pro.py` |
| `strands_robots/rtps/participant.py` | raw DDS/RTPS via `cyclonedds`, local IDL bundle | `pip install "strands-robots[ros2]"` (`rtps/__init__.py:1-6`) | `tools/use_rtps.py`, `drivers/ros/rtps_robot.py` |
| `strands_robots/ros_telemetry.py` + `hardware_ros_bridge.py` + `simulation/ros_bridge.py` | rclpy publisher/subscriber node for `/<robot>/joint_states`, `/<robot>/<cam>/image_raw`, `/<robot>/joint_command` | sourced distro | `hardware_robot.Robot(ros2_bridge=True)`, `SimEngine(ros2_bridge=True)` |
| `strands_robots/hardware_rtps_bridge.py` | same topics over cyclonedds | `[ros2]` extra | `Robot(ros2_bridge=True, ros2_transport="rtps")` |

### 2.1 `strands_robots/ros.py` - the rclpy transport (583 lines)

Public surface: `__all__ = ["CommandGate", "GATE_TOOL", "never_gated", "ros_action"]` (`ros.py:583`).

* `CommandGate = Callable[[str, str], str | None]` (`:59`) - called with `(verb, name)`, returns refusal text or None.
* `GATE_TOOL = "use_ros"` (`:67`) - every caller keys its interrupt id and audit source with it.
* `never_gated(kind, target) -> None` (`:83-101`) - the one permitted gate for read verbs.
* Validation regexes: `_NAME_RE = ^[A-Za-z0-9_/~{}]+\Z` and `_TYPE_RE = ^[A-Za-z0-9_]+/[A-Za-z0-9_]+/[A-Za-z0-9_]+\Z`
  (`:73-74`) - names are alnum/_/~/{} (so `/bad; rm -rf` is refused), types are `pkg/(msg|srv|action)/Name`.
* `_INSTALL_HINT` (`:76-80`): "rclpy is not importable - source a ROS 2 distro before launching the agent (e.g.
  'source /opt/ros/jazzy/setup.bash')...".
* `_RosBackend` (`:110-180`): process-wide singleton; `available()` probes `import rclpy; import
  rosidl_runtime_py.utilities` (`:127-139`); `_ensure_node()` does `rclpy.init()` if not `rclpy.ok()` and creates
  `Node("strands_robots_use_ros")` + `SingleThreadedExecutor` (`:141-154`); `spin_for(predicate, timeout)` spins
  `spin_once(timeout_sec=0.05)` on `time.monotonic()` (`:156-176`); an `RLock` serialises all access (`:119`).
  `_backend = _RosBackend()` (`:183`).
* Type resolution: `_get_message/_get_service/_get_action` via `rosidl_runtime_py.utilities.get_*` (`:186-201`);
  `_msg_to_dict` via `message_to_ordereddict` (`:204-207`). Fields are applied with `set_message_fields` (`:291-297`).
* Graph reads (each spins 0.2 s to let discovery settle): `_list_topics` (`:223-228`), `_list_nodes` (`:231-238`),
  `_list_services` (`:241-245`), `_resolve_topic_type` (`:248-254`), `_info` (publisher/subscriber counts) (`:257-268`),
  `_list_actions` via `rclpy.action.get_action_names_and_types` (`:352-358`).
* `_echo(topic, msg_type, timeout, count)` (`:276-287`): QoS depth **10** on the subscription (`:282`), destroyed in `finally`.
* `_publish(topic, msg_type, fields, count, rate)` (`:290-307`): publisher QoS depth **10** (`:295`), 0.3 s settle
  spin, then `count` publishes paced at `1/rate`, publisher destroyed in `finally`. There is no QoS profile
  knob (no reliability/durability choice) on this path.
* `_service_call` (`:310-328`): `wait_for_service(timeout)` then `call_async`; `TimeoutError` on either.
* `_action_send_goal` (`:361-430`): one monotonic deadline for discovery + acceptance + result; feedback capped at
  `_FEEDBACK_LIMIT = 5` keeping first 4 + latest (`:349`, `:385-392`); on a deadline past acceptance it sends
  `cancel_goal_async` and spins up to 2 s before raising (`:415-420`); returns
  `{"goal_status": "<SUCCEEDED|ABORTED|...>", "result": {...}, "feedback": [...]}` (`:424-428`,
  `_GOAL_STATUS_NAMES :336-344`).
* `ros_action(action, *, topic, service, action_name, type, fields, timeout=5.0, count=1, rate=10.0, gate)`
  (`:433-580`). Order: validate names/types (`:485-492`), `status` answers without a backend (`:494-497`), no backend
  -> `_err(_INSTALL_HINT)` (`:499-500`), **gate consulted after the probe and before the lock** for
  `("publish", topic)`, `("service_call", service)`, `("action_send_goal", action_name)` when both name and type
  are present (`:511-515`), then under `_backend.lock` dispatch (`:517-571`). Errors become
  `{"status":"error","content":[{"text":"use_ros: ..."}]}` (`_err :214-215`); `TimeoutError`, `ImportError`,
  `KeyError`, `AttributeError`, `ValueError`, `TypeError` are converted (`:572-580`).
* No reconnect logic: rclpy owns the DDS session; the node lives for the process.
* Tested by `tests/tools/test_use_ros.py` (fake `rclpy` node/rosidl injected into `strands_robots.ros`,
  `tests/tools/test_use_ros.py:1-21`, `:271-400`), `tests/test_use_ros_command_blocklist.py`,
  `tests/test_every_ros_transport_consults_the_command_gate.py:416-470` (the lock is free while the operator is asked),
  `tests/test_rclpy_refusal_cells_establish_the_absence.py`, `tests/tools/test_tool_wait_budgets_survive_a_clock_step.py`.

### 2.2 `strands_robots/rosbridge.py` - the WebSocket transport (528 lines)

`__all__ = ["CommandGate", "GATE_TOOL", "never_gated", "rosbridge_action"]` (`rosbridge.py:528`); `GATE_TOOL = "use_rosbridge"` (`:68`).

* Types are ROS1-style two-segment (`geometry_msgs/Twist`): `_TYPE_RE = ^[A-Za-z0-9_]+/[A-Za-z0-9_]+\Z`; names
  `_NAME_RE = ^[A-Za-z0-9_/~]+\Z` (`:86-87`). Host allowlist `_HOST_RE = ^[A-Za-z0-9._-]+\Z` applied after the
  shared `dial_host_error` (`:89-108`). Port: shared `tcp_port_error` then `_TRANSPORT_MAX_PORT = 65534` because
  autobahn's URL builder uses `range(0, 65535)` (`:110-159`); an `int` subclass port is normalised with `int(port)`
  (`:210-227`).
* `_ACTIONS = {"status","list_topics","list_services","echo","publish","service_call"}` (`:168`).
* `_RosbridgeBackend` (`:171-264`): one `roslibpy.Ros(host, port)` per `(host, port)` for the process lifetime, never
  terminated (terminating stops the non-restartable Twisted reactor) (`:194-206`); first connect `ros.run(timeout)`
  -> `TimeoutError("could not connect to rosbridge at ws://host:port within Ns - is rosbridge_server running?")`
  (`:231-245`); on a dropped socket it waits up to `timeout` for roslibpy's `ReconnectingClientFactory` to re-dial
  (`:246-260`). `RLock` serialises all access.
* Graph reads use `rosapi` services: `/rosapi/topics` (`rosapi/Topics`), `/rosapi/services`, `/rosapi/topic_type`
  (`:296-330`); `_list_topics` tolerates a short/absent `types` array and prints `TYPE_NOT_REPORTED` (`:271`, `:296-320`).
* `_echo` (`:333-350`): `roslibpy.Topic(ros, topic, msg_type).subscribe(cb)`, `threading.Event().wait(timeout)`,
  unsubscribe in `finally`. `_publish` (`:512-525`): `advertise()`, 0.2 s settle, `count` x `publish(roslibpy.Message(fields))`
  paced at `1/rate`, `unadvertise()`. rosbridge has no QoS knob; roslibpy defaults apply (latch false, queue
  default). `_service_call` = `_rosapi_call` (`:282-294`, `:353-354`).
* `rosbridge_action(action, *, host="localhost", port=9090, topic, service, type, fields, timeout=5.0, count=1,
  rate=10.0, gate)` (`:357-509`). Order: host/port/name/type domains (`:412-425`), unknown action (`:427-428`),
  **required names graded before the dial** (`:434-439`, #3682), `status` dials and reports
  `backend: roslibpy; connected to ws://host:port` or `not connected - ...` (`:441-449`), backend probe (`:451-452`),
  **gate for `("publish", topic)` and `("service_call", service)` before the dial/lock** (`:461-465`), then dispatch
  under the lock (`:467-509`). Error prefix is `use_rosbridge: ` (`:278-279`).
* Tested by `tests/tools/test_use_rosbridge.py`, `tests/tools/test_rosbridge_*` (host domain, port identity, port
  limit, required args before dial), `tests/mesh/test_rosbridge_robot_command_gate.py` (fakes `roslibpy.Ros/Topic`
  beneath the real gate, `:68-150`).

### 2.3 `strands_robots/rtps/` - the raw DDS participant

* `rtps/__init__.py` (42 lines): docstring states scope v1 = topics only (`advertise/publish/subscribe/echo/discovery`);
  services/actions deferred; publishing needs a local IDL type (`rtps/__init__.py:15-23`). Exports
  `MAX_DDS_TOPIC_LENGTH, ROS_TOPIC_RE, dds_topic_name, dds_type_name, ros_topic_error, ros_topic_name` (`:26-42`).
* `rtps/mangling.py` (248 lines): ROS topic `/turtle1/cmd_vel` -> DDS `rt/turtle1/cmd_vel` (`:8-15`); type
  `geometry_msgs/msg/Twist` -> `geometry_msgs::msg::dds_::Twist_` (`:30-37`); srv/action types are refused with an
  explanation (`:39-50`, `_ROS_SERVICE_TYPE_RE :88`). `ROS_TOPIC_RE = ^(?!.*__)(?:/(?![0-9])[A-Za-z0-9_]+)+\Z` (`:68`):
  absolute, no empty token, no digit-leading token, no double underscore. `MAX_DDS_TOPIC_LENGTH = 256` (`:74`).
  `ros_topic_error` names the clause broken (`:94-...`).
* `rtps/idl/__init__.py` (213 lines): `REGISTRY` of cyclonedds `IdlStruct` classes, filled only when cyclonedds
  imports (`:68-71`): `geometry_msgs/msg/{Vector3,Twist,Point,Quaternion,Pose,...}` (`:114-120`),
  `std_msgs/msg/Header`, `builtin_interfaces/msg/Time`, `sensor_msgs/msg/JointState`, `sensor_msgs/msg/Image`
  (`:183-188`). `get_type(ros_type)` raises `KeyError`-style listing known types (`:193-213`). **No LaserScan, no
  Odometry, no CompressedImage, no DeepRacer `ServoCtrlMsg` in the bundle.**
* `rtps/participant.py` (322 lines): `PublishGate = Callable[[str], str | None]` (`:46`), `GATE_TOOL = "use_rtps"` (`:53`),
  `never_gated(target)` (`:56-...`). `_RtpsBackend` (`:71-137`): one `DomainParticipant`, writers/readers cached per
  `(topic, type)`, `RLock`. `rtps_action(action, *, topic, type, fields, timeout=5.0, count=1, rate=10.0, gate)`
  (`:193-322`): validates with `ros_topic_error` and `dds_type_name` (`:237-243`), `status` (`:245-250`), `types`
  lists `REGISTRY` (`:259-260`), gate for `publish` after the probe and before the lock (`:262-273`), `advertise`
  creates the writer (`:276-281`), `publish` builds the sample with `_build_sample`, sleeps 0.3 s, writes `count`
  samples at `1/rate` (`:283-294`), `subscribe` creates a reader, `echo` polls `reader.take(N=...)` until `count` or
  monotonic deadline (`:296-312`). DDS QoS is cyclonedds default (the docs note `KEEP_LAST (1)` with no depth knob,
  `docs/learn/ros2.md:59`).
* Tested by `tests/tools/test_use_rtps.py`, `tests/rtps/test_mangling.py`, `tests/rtps/test_idl_bundle.py`,
  `tests/mesh/test_rtps_robot_command_gate.py` (fake writer + fake IDL bundle, `:58-166`); live proof under
  `examples/ros2/rtps_proof/` and the `rtps` pytest marker (`pyproject.toml:1361`, `RTPS_LIVE=1 pytest -m rtps`).

### 2.4 `strands_robots/ros_telemetry.py` - the telemetry wire contract (900 lines)

* `RosTelemetryBase` (`:237-680`): transport-agnostic topic names and inbound parsing.
  `joint_states_topic(robot) = f"/{safe(robot)}/joint_states"` (`:308-310`),
  `image_topic(robot, camera) = f"/{safe(robot)}/{safe(camera)}/image_raw"` (`:313-315`),
  `joint_command_topic(robot) = f"/{safe(robot)}/joint_command"` (`:318-320`). `_safe` sanitises to
  `[A-Za-z0-9_]`, collapses `_` runs (`:55-56`, `:255-296`). `_validate_joint_limits` (`:412`),
  `_validate_dds_security_config` (`:461`, required keys `identity_ca, certificate, private_key, governance,
  permissions`, optional `permissions_ca`, `:200-209`), `_require_secure_command_surface` (`:515-553`) refuses an
  inbound `joint_command` on an unsecured DDS graph unless `STRANDS_ROS2_BRIDGE_I_KNOW_THIS_IS_INSECURE=1|true|yes`
  (`ROS2_INSECURE_ENV :191`, `_insecure_opt_out :506-512`). `_command_action` (`:554-662`) zips `name`/`position`
  into `{"<motor>.pos": float}`, rejects length mismatch, non-numeric and out-of-limit whole (no partial
  application). `_drive_from_command` (`:663-681`) calls `robot.send_action` and logs, never raises.
* `MAX_QOS_HISTORY_DEPTH = 2**31 - 1` (`:85`); `_qos_history_depth_error` (`:88-141`) rejects `0`, bools,
  non-ints, `np.int64`, and values over the signed-32 ceiling because rclpy builds
  `QoSProfile(depth=value, history=KEEP_LAST)` lazily on the first publish.
* `_foreign_context_domain_error` (`:144-183`): a process already running an rclpy context on another domain cannot
  be moved by writing `ROS_DOMAIN_ID`; the bridge refuses rather than publish on the wrong domain.
* `ROS2_SYSTEM_INSTALL_HINT` (`:66-76`): "rclpy is not published on PyPI ... Source a distro ... The [ros2] extra
  installs only the cyclonedds RMW binding".
* `RosTelemetryBridge(RosTelemetryBase)` (`:683-900`): `__init__(domain_id=0, node_name=None, qos_depth=10)`
  (`:723`); validates domain (`dds_domain_id_error`, `[0, 232]`) and depth BEFORE writing `os.environ["ROS_DOMAIN_ID"]`
  (`:724-751`); `require_optional("rclpy", system_install=ROS2_SYSTEM_INSTALL_HINT, ...)` and
  `require_optional("sensor_msgs.msg", pip_install="ros-<distro>-sensor-msgs", ...)` (`:753-759`); owns the context
  only if it initialised it (`_owns_context :762-764`); refuses a foreign-domain context and rolls the env write back
  (`:765-777`); `create_node(node_name or default_node_name)` (`:778`, `default_node_name = "strands_robots"` `:721`).
  Publishers are cached **per topic** (`_joint_publisher :786-800`, `_image_publisher :802-819`) with
  `create_publisher(type, topic, qos_depth)`. `publish_joint_states(robot, names, positions)` drops a misaligned
  pair whole (`:821-836`); `publish_image(robot, camera, image)` requires `(H, W, 3)` and sends `rgb8`, `step=width*3`
  (`:838-858`). `shutdown()` destroys the node and shuts the context it owns (`:860-900`).

### 2.5 `strands_robots/hardware_ros_bridge.py` - full duplex rclpy bridge for a real robot (277 lines)

`HardwareRosBridge(RosTelemetryBridge)`, node name `strands_hardware` (`:130`). Constructor
`(robot=None, *, domain_id=0, node_name=None, qos_depth=10, enable_commands=True, command_robot_name=None,
spin_period=0.02, joint_limits=None)` (`:132-143`). All domain checks (`spin_period` positive finite,
`enable_commands` strict bool, `joint_limits`, `command_robot_name` str|None) run **before** `super().__init__`
so a refusal leaves `ROS_DOMAIN_ID` and the rclpy context untouched (`:144-189`). With a bound robot and
`enable_commands=True` it subscribes `/<robot>/joint_command` (`sensor_msgs/msg/JointState`) at `qos_depth`
(`:206-214`) and starts a daemon spin thread calling `rclpy.spin_once(node, timeout_sec=spin_period)` (`:233-265`).
`shutdown()` stops the thread (join 2 s) then the base (`:269-277`). Selected by
`Robot(..., ros2_bridge=True, ros2_transport="rclpy")` (`hardware_robot.py:556-561`, `:837-872`).

### 2.6 `strands_robots/hardware_rtps_bridge.py` - the cyclonedds twin (481 lines)

`HardwareRtpsBridge(RosTelemetryBase)` (`:107`). Constructor `(robot=None, *, domain_id=0, enable_commands=True,
command_robot_name=None, poll_period=0.02, joint_limits=None, dds_security_config=None)` (`:179-189`). Order:
domain, poll period, bool flag, namespace (`:190-223`), then `require_optional("cyclonedds", extra="ros2", ...)`
(`:226-230`), joint limits, DDS Security gate (`:247-259`), `DomainParticipant(domain_id, qos=...)` with
`dds.sec.*` properties when a config is given (`:261-269`, `_DDS_SECURITY_PROPERTY :82-89`,
`_DDS_SECURITY_PLUGINS :94-104`, `_build_security_qos :302-324`). Writers/readers per topic via
`Topic(participant, dds_topic_name(ros_topic), idl_cls)` (`:328-340`). Publishes `JointState` and `Image` from the
IDL bundle (`_JOINT_STATE_TYPE/_IMAGE_TYPE :73-74`) with a wall-clock `Header` (`:394-401`). Inbound: a poll
thread paced by `strands_robots._pacing.Ticker` takes up to 10 samples per tick (`:418-440`), `skip_empty=True`
for DDS dispose samples (`:405-416`). `shutdown()` drops references; cyclonedds has no explicit close (`:460-472`).
`__repr__` uses `partial_construction_repr` (`:474-481`). Known graph difference: a bare participant shows as
`_CREATED_BY_BARE_DDS_APP_` with an `INVALID` type hash (`:34-38`, `docs/learn/ros2.md:59`).

### 2.7 `strands_robots/simulation/ros_bridge.py` (52 lines)

`SimRosBridge(RosTelemetryBridge)`, node name `strands_sim` (`:46`); publish-only; skips the free overview camera
(`FREE_CAMERA_TOKENS`, `:48-52`, #4473). Enabled by `Simulation(ros2_bridge=True, ros2_domain=0)`
(`examples/ros2/sim_bridge_demo.py:31`).

### 2.8 How the transports are typed and tested, in one line each

* rclpy: real message classes from `rosidl_runtime_py` (`ros.py:28-32`); tests inject fake `rclpy` into the module.
* rosbridge: untyped JSON dicts, type string carried alongside (`rosbridge.py:28-30`); tests fake `roslibpy`.
* RTPS: `IdlStruct` dataclasses from `rtps/idl` built recursively by `_build_sample` (`participant.py:172-191`);
  tests fake the bundle and writer.
* All three return the Strands tool envelope `{"status": ..., "content": [{"text": ...}]}` and never raise.

---

## 3. TOOLS: `use_ros`, `use_rosbridge`, `use_rtps`, `_numeric_options`, `tools/__init__`

### 3.1 `strands_robots/tools/__init__.py`

Lazy table `_LAZY_IMPORTS` (`tools/__init__.py:14-34`) with `"use_ros": (".use_ros","use_ros")`,
`"use_rosbridge"`, `"use_rtps"`, `"robot_mesh"`, `"pose_tool"`, `"serial_tool"`, `"use_lerobot"`, `"run_policy"`,
`"train_policy"`, `"lerobot_*"`, episode-judge helpers, `harness_memory`, `download_assets`; `__all__` is the key
list; `__getattr__` imports on demand (`:39-46`).

### 3.2 `strands_robots/tools/_numeric_options.py` (81 lines)

One owner of the `timeout`/`count`/`rate` domains for all three ROS tools (`:1-19`).
`_OPTION_DOMAINS = (("timeout", positive_finite_number_error), ("count", positive_count_error),
("rate", positive_finite_number_error))` (`:33-37`). `numeric_option_error(action, options_by_action, *, timeout,
count, rate)` checks only the options the requested action consumes (`:40-81`): "A caller must never be refused
for a value the requested action never looks at" (`:56-59`). `count` must be a true `int` (bool refused),
`timeout`/`rate` positive finite reals.

### 3.3 `strands_robots/tools/use_ros.py` (182 lines) - full schema

Decorator: `@tool(context=True)` (`:92`). Signature (`:93-104`):

```python
def use_ros(action: str, tool_context: ToolContext | None = None, topic: str | None = None,
            service: str | None = None, action_name: str | None = None, type: str | None = None,
            fields: dict[str, Any] | None = None, timeout: float = 5.0, count: int = 1, rate: float = 10.0)
            -> dict[str, Any]
```

Actions (docstring `:36-50`, dispatch `:158-179`):

| action | required params | numeric options read (`_ACTION_NUMERIC_OPTIONS :84-89`) | gated? | returns (text) |
|---|---|---|---|---|
| `status` | - | - | no | `backend: rclpy (in-process)` or `backend: none - <hint>` |
| `list_topics` | - | - | no | `name [type, ...]` per line |
| `list_nodes` | - | - | no | `/ns/name` per line |
| `list_services` | - | - | no | `name [type]` per line |
| `list_actions` | - | - | no | `name [type]` per line |
| `info` | `topic` or `service` | - | no | type(s), publishers, subscribers |
| `echo` | `topic` (`type` auto-resolved) | `timeout`, `count` | no | `echo <topic> (<type>):\n<json list>` |
| `publish` | `topic`, `type` | `count`, `rate` | **yes** (blocklist) | `published N message(s) to <topic>` |
| `service_call` | `service`, `type` | `timeout` | **yes** | `response:\n<json>` |
| `action_send_goal` | `action_name`, `type` | `timeout` (end-to-end, cancels on expiry) | **yes** | `goal to <name> finished:\n{"goal_status","result","feedback"}` |

Return shape is always `{"status": "success"|"error", "content": [{"text": str}]}` (`:137-138`). The gate closure is
`gate_command(kind, target, tool_context=tool_context, tool=GATE_TOOL)` (`:155-156`); read verbs get `never_gated`.
Numeric options are checked before anything else (`:146-148`). Examples from the docstring (`:52-66`):

```python
use_ros(action="publish", topic="/turtle1/cmd_vel", type="geometry_msgs/msg/Twist",
        fields={"linear": {"x": 2.0}, "angular": {"z": 1.5}})
use_ros(action="service_call", service="/spawn", type="turtlesim/srv/Spawn", fields={"x": 3.0, "y": 3.0, "name": "t2"})
use_ros(action="action_send_goal", action_name="/navigate_to_pose", type="nav2_msgs/action/NavigateToPose",
        fields={"pose": {"header": {"frame_id": "map"}, "pose": {"position": {"x": 1.0, "y": 2.0}}}}, timeout=120.0)
```
How an agent uses it: `Agent(tools=[use_ros])` and a system prompt that spells the publish/echo calls
(`examples/ros2/use_ros/agent_drive.py:69-83`). A DeepRacer-specific call would be
`use_ros(action="publish", topic="/webserver_pkg/manual_drive", type="deepracer_interfaces_pkg/msg/ServoCtrlMsg",
fields={"angle": 0.0, "throttle": 0.3}, count=20, rate=20.0)` - gated because `/manual_drive` is blocklisted.

### 3.4 `strands_robots/tools/use_rosbridge.py` (168 lines)

`@tool(context=True)` (`:79`); signature (`:80-92`): `use_rosbridge(action, host="localhost", port=9090, topic,
service, type, fields, timeout=5.0, count=1, rate=10.0, tool_context=None)`. Actions (`:31-40`): `status`,
`list_topics`, `list_services`, `echo`, `publish`, `service_call`. Every action reads `timeout` because every one
dials (`_ACTION_NUMERIC_OPTIONS :69-76`: `status/list_topics/list_services/service_call: timeout`;
`echo: timeout,count`; `publish: timeout,count,rate`). `publish` and `service_call` are gated (`:141-160`). Type
strings are two-segment (`geometry_msgs/Twist`). Example (`:42-49`):
`use_rosbridge(action="publish", topic="/curiosity_mars_rover/ackermann_drive_controller/cmd_vel",
type="geometry_msgs/Twist", fields={"linear": {"x": 1.0}, "angular": {"z": 0.0}})`.

### 3.5 `strands_robots/tools/use_rtps.py` (144 lines)

`@tool(context=True)` (`:77`); signature (`:78-87`): `use_rtps(action, topic, type, fields, timeout=5.0, count=1,
rate=10.0, tool_context=None)`. `_ACTIONS = ("status","types","advertise","publish","subscribe","echo")` (`:65`),
graded first (`:112-113`). Numeric options: `publish: count, rate`; `echo: timeout, count` (`:71-74`). Only
`publish` is gated (`:127-136`); `advertise` is never gated because it writes no sample.

---

## 4. DRIVERS / MOBILE BASE / ACKERMANN

### 4.1 Package layout and hierarchy

`strands_robots/drivers/ros/__init__.py:1-26` exports `ActionCapable, MobileBaseRobot, ServiceCapable, Transport,
AckermannRosRobot, RosBridgedRobot, RosbridgeRobot, RtpsRobot`. The class hierarchy as the code actually has it:

```
MobileBaseRobot                       drivers/ros/_mobile_base.py:218   (shared drive contract; Transport seam)
  +-- RosBridgedRobot                 drivers/ros/ros_bridge.py:191     (rclpy; adds navigate_to / Nav2)
  +-- RtpsRobot                       drivers/ros/rtps_robot.py:111     (cyclonedds; adds advertise)
RosbridgeRobot  (standalone class)    drivers/ros/rosbridge_robot.py:55 (roslibpy; owns its own drive/stop)
AckermannRosRobot (standalone class)  drivers/ros/ackermann_robot.py:173 (rclpy via ros_action; owns its own drive/stop)
YahboomM3ProDriver (HardwareDriver)   drivers/yahboom_m3pro.py:238       (registry-registered native driver, 3 transports)
```

NB: although `_mobile_base.py:24-26` says "`_cmd_fields` ... a bicycle model for an Ackermann car", the shipped
`AckermannRosRobot` does **not** subclass `MobileBaseRobot`; it imports `failed_halt_error` from the base
(`ackermann_robot.py:71`), `_check_topic` and `_operator_gate` from `ros_bridge.py` (`:72`), and calls
`ros_action` directly (`:73`). The three drive-owning classes are `MobileBaseRobot`, `RosbridgeRobot`,
`AckermannRosRobot` (changelog.d/2839, `tests/mesh/test_drive_reports_a_refused_trailing_stop.py:257-287`).

None of the four ROS mobile bases is a `HardwareDriver` and none is in `_SHIPPED_DRIVERS`
(`strands_robots/drivers/__init__.py:53-73`); `Robot("deepracer", mode="real")` does not exist. They are used
directly: `car = AckermannRosRobot.from_deepracer(node_name="deepracer"); Agent(tools=car.tools)`.

### 4.2 `MobileBaseRobot` (`drivers/ros/_mobile_base.py`, 678 lines)

Safety contract stated once (`:28-58`): refuse non-finite; `duration` positive finite and within `max_duration`
(refused before any side effect, including before the `init_services` handshake); clamp to limits, `None` means
"no limit" not zero; every timed/multi-message non-zero command is followed by a single zero command from
`try/finally` and the zero's verdict is read; a bare single-shot `drive()` latches until `stop()`; `stop` is never
gated on the handshake or limits but IS subject to the transport's command gate; every command carries
`tool_context` down to the transport.

* `Transport` Protocol (`:75-130`): `twist_type: str`; `publish(*, topic, type, fields, count, rate, tool_context=None)`;
  `echo(*, topic, type, count, timeout)`. `ServiceCapable.service_call(*, service, type, fields, tool_context)`
  (`:133-157`), `ActionCapable.action_send_goal(*, action_name, type, fields, timeout, tool_context)` (`:160-179`).
* `positive_finite(label, value, context)` (`:182-194`) -> `ValueError` via the shared guard.
* `LATCHED_VELOCITY = "the robot may still be moving at the commanded velocity"` (`:200`).
* `failed_halt_error(result, halt, *, topic, subject)` (`:203-240`): returns
  `"drive: the command was published to {topic}, but the trailing stop failed - {subject}. Halt it with stop. Halt failure: {cause}"`
  when the hold succeeded and the stop did not; `None` when no stop was owed, the stop landed, or the hold itself failed.
* Constructor (`:259-337`): `(node_name, cmd_vel_topic, transport, *, odom_topic=None, scan_topic=None,
  cmd_vel_type=None, odom_type=None, scan_type=None, max_linear=None, max_angular=None, max_duration=None,
  publish_rate=10.0, init_services=None)`. Name grammar `_NAME_RE/_TOPIC_RE = ^[A-Za-z0-9_/~]+\Z` with per-seam hints
  (`:245-257`). `init_services` on a transport without `service_call` is refused (`:329-332`).
* `supports(capability)` (`:376-383`) detects optional transport methods.
* `_cmd_fields(linear, angular, lateral=0.0)` (`:387-408`): the kinematics seam; default identity onto a Twist
  `{"linear": {"x": v}, "angular": {"z": w}}`; `lateral` reserved for holonomic bases.
* `enable(tool_context)` (`:424-452`): runs `init_services` in order through `service_call`, stops at first failure
  without latching, idempotent on success.
* `drive(linear=0.0, angular=0.0, duration=None, count=1, tool_context=None)` (`:456-537`): guards in order
  `finite_number_error(linear)`, `finite_number_error(angular)`, `positive_finite_number_error(duration)` or
  `positive_whole_number_error(count)` (`:487-501`), `duration > max_duration` refusal (`:503-507`), handshake
  (`:510-513`), clamp (`:514-519`), `n = max(1, round(duration * publish_rate))` or `count` (`:520`), publish in
  `try`, trailing zero in `finally` when `(duration is not None or n > 1) and (v or w)` (`:525-532`), then
  `failed_halt_error` (`:536-537`).
* `stop(tool_context)` (`:539-553`), `get_pose(timeout=5.0)` (`:557-570`), `get_scan(timeout=5.0)` (`:572-580`).
* `tools` property (`:605-663`): `drive_<suffix>` and `stop_<suffix>` are `@tool(context=True)`; `get_pose_<suffix>`
  only with `odom_topic`; `get_scan_<suffix>` only with `scan_topic`; `_extra_tools()` appended. `tool_suffix =
  node_name.strip("/").replace("/", "_")` (`:585-588`). The drive description discloses the limits and the latch
  (`_drive_description :590-602`).

### 4.3 `RosBridgedRobot` (`drivers/ros/ros_bridge.py`, 416 lines)

* `_TWIST_TYPE = "geometry_msgs/msg/Twist"`, `_NAV_ACTION_TYPE = "nav2_msgs/action/NavigateToPose"` (`:84-85`);
  `_ROS2_GRAPH_NAME_RE = ^[A-Za-z0-9_/~]+\Z` (`:90`); module-level `_check_topic(label, value)` (`:93-102`) and
  `_operator_gate(tool_context) -> CommandGate` = `lambda kind, target: gate_command(kind, target,
  tool_context=tool_context, tool=GATE_TOOL)` (`:105-122`) - both reused by `AckermannRosRobot`.
* `_UseRosTransport` (`:125-188`): `publish/echo/service_call/action_send_goal` forwarding to `ros_action`, resolved
  through module globals so tests can patch `strands_robots.drivers.ros.ros_bridge.ros_action`.
* Constructor (`:225-260`): `(node_name, cmd_vel_topic, odom_topic, scan_topic=None, *, cmd_vel_type=_TWIST_TYPE,
  odom_type=None, scan_type=None, publish_rate=10.0, max_linear=None, max_angular=None, max_duration=None,
  nav_action=None, nav_action_type=_NAV_ACTION_TYPE)`; `odom_topic` is required here. `from_ros(...)` (`:262-277`).
* `navigate_to(x, y, yaw=0.0, frame_id="map", timeout=120.0, tool_context=None)` (`:279-371`): refuses non-finite
  pose/timeout, builds `{"pose": {"header": {"frame_id"}, "pose": {"position": {x,y}, "orientation": {z: sin(yaw/2), w: cos(yaw/2)}}}}`
  and sends an `action_send_goal` through the gate (`/navigate_to_pose` is blocklisted). `navigate_<suffix>` tool
  appears only with `nav_action` (`_extra_tools :373-397`).

### 4.4 `RtpsRobot` (`drivers/ros/rtps_robot.py`, 204 lines)

`_RtpsTransport` implements only `publish` (gated through `gate_command("publish", target, ..., tool=GATE_TOOL)`),
`echo`, `advertise` (`:60-108`); no services/actions, so `init_services` is refused by the base (`:28-34`). Topic
grammar is the strict `ROS_TOPIC_RE` from mangling (`:56`, `:137-147`). Constructor `(node_name, cmd_vel_topic, *,
cmd_vel_type="geometry_msgs/msg/Twist", publish_rate=10.0, max_linear=None, max_angular=None, max_duration=None)`
(`:149-169`); `from_rtps(...)` (`:171-185`); `advertise()` (`:187-195`).

### 4.5 `RosbridgeRobot` (`drivers/ros/rosbridge_robot.py`, 443 lines)

Standalone; `_TWIST_TYPE = "geometry_msgs/Twist"` (ROS1 spelling) (`:52`). Constructor (`:82-145`):
`(node_name, cmd_vel_topic, odom_topic, scan_topic=None, *, host="localhost", port=9090, cmd_vel_type=_TWIST_TYPE,
odom_type=None, scan_type=None, max_linear=2.0, max_angular=1.0, max_duration=30.0, publish_rate=10.0)`; host and
port graded by `dial_host_error`, `_HOST_RE`, `tcp_port_error`, `_transport_port_error` (`:109-120`); all four limits
positive finite (`:134-145`). `from_curiosity(node_name="curiosity", host="localhost", port=9090, **overrides)`
(`:147-173`) wires `/curiosity_mars_rover/ackermann_drive_controller/cmd_vel`, `/curiosity_mars_rover/odom`,
`max_linear 2.0`, `max_angular 1.0`, `max_duration 30.0`, `publish_rate 10.0`. `_publish_twist` (`:175-211`) sends
`{"linear": {"x": v}, "angular": {"z": w}}` with the gate closure; `drive` (`:213-323`) mirrors the base contract
(guards, ceiling, clamp, `n`, trailing zero in `finally`, `failed_halt_error`); `stop` (`:325-343`); `get_pose`
(`:345-363`); `get_scan` (`:365-383`); `tools` (`:385-434`): `drive_<s>`, `stop_<s>` context=True, `get_pose_<s>`,
`get_scan_<s>` if wired.

### 4.6 `AckermannRosRobot` (`drivers/ros/ackermann_robot.py`, 521 lines) - the DeepRacer bridge

Module docstring (`:1-60`): reference platform AWS DeepRacer; three differences absorbed: (1) commands are normalised
servo pairs `angle`/`throttle` in `[-1, 1]`, not Twist - `drive` keeps `(linear, angular)` and converts through a
bicycle model; (2) the vehicle must be armed by a two-step manual-mode service handshake (`init_services`) run once
before the first command; (3) no odometry on the stock platform, so no `get_pose`. All ROS I/O forwards through
`strands_robots.ros.ros_action`; the bridge owns no rclpy state (`:21-23`). Programmatic calls (no `tool_context`)
are refused unless `STRANDS_ROS2_COMMAND_ALLOW` names the surfaces or `BYPASS_TOOL_CONSENT=true` (`:34-38`).

Constants and conversion:

```python
_SERVO_TYPE = "deepracer_interfaces_pkg/msg/ServoCtrlMsg"      # :81
_REST_VELOCITY_EPS = 1e-3                                      # :86  (m/s)

def _twist_to_servo(linear, angular, *, wheelbase_m, max_speed, max_steering_rad) -> (angle_norm, throttle):
    v = float(linear)
    if abs(v) < _REST_VELOCITY_EPS: return (0.0, 0.0)
    delta = math.atan2(wheelbase_m * float(angular), abs(v))   # bicycle model, sign restored for reverse
    if v < 0: delta = -delta
    delta = max(-max_steering_rad, min(max_steering_rad, delta))
    throttle = max(-1.0, min(1.0, v / max_speed))
    return (delta / max_steering_rad, throttle)                 # :89-117
```
`_rest_command_error(linear, angular, context)` (`:120-170`): a yaw asked for at rest (`abs(linear) < 1e-3` and
`angular != 0`) is refused with "...an Ackermann platform steers its front wheels and cannot turn in place, so this
would go on the wire as the same zero servo pair a stop uses. Give the turn a linear speed to travel at, or call
stop()..."; a sub-threshold non-zero linear is refused with "...below the rest threshold 0.001 m/s..."; `(0, 0)`
is accepted as rest.

Constructor (`:209-251`):
```python
AckermannRosRobot(node_name, servo_topic, scan_topic=None, *, servo_type=_SERVO_TYPE, scan_type=None,
                  wheelbase_m=0.164, max_speed=1.5, max_steering_rad=0.5236, max_duration=10.0,
                  publish_rate=20.0, init_services=None)
```
Numeric domains: `wheelbase_m`, `max_speed`, `max_steering_rad`, `max_duration`, `publish_rate` each positive
finite (`:229-242`); names via `_check_topic` (`:224-226`); each `init_services` entry needs `service` (valid
graph name) and `type` (`:244-250`). `max_steering_rad = 0.5236` is 30 degrees; min turning radius
`wheelbase/tan(max_steering) = 0.164/tan(0.5236) ~= 0.284 m` (computed in `tools`, `:476`).

`from_deepracer(node_name, **overrides)` (`:253-282`) - the stock wiring:
```python
"servo_topic": "/webserver_pkg/manual_drive",
"scan_topic": "/rplidar_ros/scan",
"init_services": [
    {"service": "/ctrl_pkg/vehicle_state", "type": "deepracer_interfaces_pkg/srv/ActiveStateSrv", "fields": {"state": 1}},
    {"service": "/ctrl_pkg/enable_state", "type": "deepracer_interfaces_pkg/srv/EnableStateSrv", "fields": {"is_active": True}},
],
```
Any keyword may be overridden (`max_speed=0.8`, `scan_topic=None`, ...) (`tests/mesh/test_ackermann_robot.py:139-145`).

Methods:
* `enable(tool_context=None)` (`:284-313`): runs the handshake via `ros_action(action="service_call", ...,
  gate=_operator_gate(tool_context))`, stops at the first non-success, latches `_enabled` only on full success.
* `drive(linear=0.0, angular=0.0, duration=None, count=1, tool_context=None)` (`:315-413`), order: finite
  guards and duration/count domain (`:353-365`), `duration > max_duration` (`:368-372`), `_rest_command_error`
  (`:376-377`), handshake if not enabled (`:378-381`), clamp `v` to `+-max_speed` (`:382`), bicycle conversion
  (`:383-389`), `n = max(1, round(duration * publish_rate))` or `count` (`:390`), `_publish_servo(angle, throttle,
  count=n)` in `try`, trailing `_publish_servo(0.0, 0.0, count=1)` in `finally` when `(duration or n > 1) and
  (angle or throttle)` (`:398-403`), then `failed_halt_error(result, halt, topic=servo_topic, subject="the car may
  still be holding the commanded throttle")` (`:407-413`).
* `_publish_servo(angle, throttle, count, tool_context)` (`:415-430`): `ros_action(action="publish",
  topic=servo_topic, type=servo_type, fields={"angle": float, "throttle": float}, count=count, rate=publish_rate,
  gate=_operator_gate(tool_context))`.
* `stop(tool_context=None)` (`:432-439`): one zero servo message; does not require `enable`; still gated by surface.
* `get_scan(timeout=5.0)` (`:441-459`): `ros_action(action="echo", topic=scan_topic, type=scan_type, count=1,
  timeout, gate=never_gated)`; refuses when no `scan_topic`.
* `tools` (`:461-512`): `drive_<suffix>(linear, angular, duration, tool_context)` with description
  "Drive the <node> Ackermann robot (linear m/s, angular rad/s, optional duration s). Steering geometry: cannot
  turn in place; minimum turning radius ~0.28 m. A command with duration stops automatically afterwards; without
  duration the last command latches until stop." (`:478-495`); `stop_<suffix>` (`:497-503`); `get_scan_<suffix>`
  only when `scan_topic` (`:505-511`). For `node_name="deepracer"` the tool names are `drive_deepracer`,
  `stop_deepracer`, `get_scan_deepracer` (`tests/mesh/test_ackermann_command_gate.py:137`).

Gate behaviour pinned by tests (`tests/mesh/test_ackermann_command_gate.py:134-227`): a `drive_deepracer` call
prompts the operator three times in order `/ctrl_pkg/vehicle_state`, `/ctrl_pkg/enable_state`,
`/webserver_pkg/manual_drive` (`:134-148`); a decline at the servo publishes nothing (`:150-156`); a decline at the
first handshake call stops there (`:158-166`); `stop_deepracer` is gated and publishes `{"angle": 0.0,
"throttle": 0.0}` on approval (`:168-182`); `get_scan_deepracer` needs no context (`:184-187`); a programmatic
`drive` without context names both env vars (`:189-196`); both allowlist spellings
`"/manual_drive,/vehicle_state,/enable_state"` and the namespaced one work (`:198-218`); a timed drive gates the
hold and the trailing halt (`:220-227`).

### 4.7 Comparison: `YahboomM3ProDriver` (`drivers/yahboom_m3pro.py`, 1107 lines) - a registry-registered ROS driver

This is the one shipped `HardwareDriver` that drives a whole robot through its ROS 2 graph, and the closest
template for a registry-backed DeepRacer driver. Facts:
* `SUPPORTED_ROBOTS = ("yahboom_m3pro",)` (`:151`), registered via `_SHIPPED_DRIVERS`
  (`drivers/__init__.py:72`); registry entry `hardware.driver = "strands"` (`strands_robots/registry/robots.json`,
  printed in this study).
* `TRANSPORTS = ("rosbridge", "ros2", "twin")` (`:154`); default `"rosbridge"`, endpoint `host[:port]` through
  `port=`; `"ros2"` is in-process rclpy on the robot; `"twin"` steps the MuJoCo model answering the same topics
  (`:27-43`). `_call` forwards to `ros_action` or `rosbridge_action` with a gate (`:535-560`).
* Topics: `/cmd_vel` (`geometry_msgs/Twist`, mecanum `linear.x/y`, `angular.z`), `/arm6_joints`, `/arm_joint`,
  `/odom_raw`, `/imu/data_raw`, `/scan0`, `/scan1` (`:10-24`). `/cmd_vel` is on the blocklist; the arm topics are not
  (`:44-52`).
* Agent tool: one tool named after the robot with `action` enum `status, sensors, arm, gripper, home, move, stop`
  and per-action parameters (`tool_spec :377-455`); `move` requires `duration_s` because the firmware watchdog zeroes
  a stale twist, streams at `PUBLISH_RATE_HZ`, ends in an explicit stop (`:855-925`).
* `send_action` speaks the model's vocabulary (`arm1.pos..`, `gripper.pos` radians; base m/s) and converts at the
  wire (`:708-780`); `get_observation` returns `{}` on hardware because the board publishes no joint state (`:68-72`).
* Constructor contract for any native driver: `driver_cls(tool_name=<canonical>, cameras=<dict|None>,
  data_config=<str|None>, **declared kwargs)`; undeclared kwargs are refused by name; `reads_cameras = True` opts
  into a `cameras=` dict (`drivers/base.py:44-70`). Required members: `tool_name, tool_type, tool_spec, stream,
  send_action, start_task, run_policy, get_task_status, stop_task, cleanup` (`DRIVER_SURFACE`,
  `drivers/base.py:93-241`); registration refuses a class missing any (`drivers/registry.py:111-141`).
* `EarthRoverDriver` (`drivers/earthrover.py`) is the HTTP analogue: `POST /control` twist frames, `GET /data`
  telemetry, `GET /v2/front|rear` camera frames, `POST /speak`; verbs `sensors, status, camera, move, lamp, speak,
  stop`; `MAX_MOVE_DURATION_S = 30.0`, re-sends the twist to beat the SDK watchdog (`:1-100`).

### 4.8 The changelog.d fragments that define the Ackermann/ROS contract (quoted)

* `changelog.d/1035-ackermann-ros-robot.md` - "### Added: `AckermannRosRobot` - Ackermann ROS 2 cars (AWS DeepRacer)
  as strands robots": "keeps the same `drive(linear, angular, duration)` agent contract and converts through a
  bicycle model to normalized servo commands (`ServoCtrlMsg` on the DeepRacer), runs a declarative `init_services`
  handshake once before the first command (the DeepRacer's manual-mode two-step, preconfigured in
  `from_deepracer()`), clamps speed, rejects over-long holds loudly, and always trails timed commands with a zero
  servo message ... Conditional `get_scan` tool; no `get_pose` (the stock platform has no odometry)." It also
  records the four hardenings: shared numeric domains (`finite_number_error`, `positive_finite_number_error`,
  `positive_whole_number_error`), `__repr__` via `partial_construction_repr`, the failed-trailing-halt report, and
  "Its command surfaces now reach the `use_ros` operator-approval gate. Two halves were missing ... `/manual_drive`,
  `/vehicle_state` and `/enable_state` are now default blocklist entries, spelled bare ... `drive`, `stop` and
  `enable` now take a `tool_context` ... and the `drive_<node>`/`stop_<node>` tools are declared `@tool(context=True)`".
  History: Vivek Raja's branch (merge commit `b0f99c33 2026-07-28 Vivek Raja merge: bring branch up to main, move
  changelog entry to a news fragment` created this file) landed as squash `3a4c6078 (#2689, 2026-08-24)` with
  `Co-authored-by: Vivek Raja <vivekraja98@gmail.com>` in the body.
* `changelog.d/3541-ackermann-rest-command-refused.md` - "### Fixed: an Ackermann car refuses a yaw it cannot execute
  instead of sending a halt": "A `drive(linear=0.0, angular=1.0)` therefore left on the wire as `{"angle": 0.0,
  "throttle": 0.0}`, byte-identical to a halt, under `status="success"` ... `drive()` now refuses such a pair by name,
  quoting the threshold and what to send instead, ordered with the other domain refusals and ahead of the
  `init_services` handshake ... `drive(0, 0)` still means rest". That is what "ackermann rest command refused" means.
* `changelog.d/2700-drive-limit-scope-names-every-carrier.md` - "### Fixed: the drive-contract scope markers name
  every class that carries a limit": the velocity clamp and `max_duration` ceiling are carried by `RosbridgeRobot`
  AND `AckermannRosRobot` (`max_speed`, 10 s), not by `RosBridgedRobot`/`RtpsRobot`; "a reader ... carries the 30 s
  hold the page documents over to a DeepRacer and is refused by that car's 10 s ceiling"; the survey in
  `tests/mesh/test_drive_contract_fleet_scope.py` is derived from the package, three-way split "fleet-wide, carried by
  some, carried by this bridge alone".
* `changelog.d/4140-ros-mobile-bases-move-to-drivers.md` - "### Changed: the ROS 2 mobile bases move from
  `strands_robots.mesh` to `strands_robots.drivers.ros`": "they drive a robot; they do not network one ... The old
  names ... still resolve to the same objects with a `DeprecationWarning` and are removed in 0.7. The three private
  copies of the refusal envelope in those modules now use `strands_robots.drivers.base.refuse`."
* `changelog.d/3938-ros2-integration-split.md` - "### Docs: the ROS 2 integration guide is six pages, each under the
  word budget" (hub + `ros2/safety.md`, `ros2/ackermann.md`, `ros2/sim-bridge.md`, `ros2/hardware-bridge.md`,
  `ros2/mesh-bridge.md`; 1,500-word budget then). Those pages were since folded into `docs/learn/ros2.md` by
  #4112/#4676 and redirected (`mkdocs.yml:239-248`); the page budget is now 900 words.
* `changelog.d/3873-ros-transport-below-tools.md` - "### Changed: the in-process rclpy transport sits below both
  robots that publish through it": the rclpy mechanics "now live in `strands_robots.ros` ... `use_ros` keeps what an
  agent envelope owns (the numeric-option domains, the operator gate, the docstring a model reads). `ros_action`
  takes the operator gate as a required keyword-only argument, so no caller can command a blocklisted surface by
  forgetting one".
* `changelog.d/2705-rosbridge-command-operator-context.md` - "### Fixed: a `RosbridgeRobot` command can carry an
  operator's decision": measured `RtpsRobot.stop(tool_context=ctx) -> success` vs `RosbridgeRobot.stop() -> error,
  "No tool_context available for operator approval"`; docs had claimed `stop()` was never gated; now "the halt
  needs no prior state and no enable handshake, and it is not exempt from a gate that is keyed on the command
  surface rather than on the payload"; adds `tests/mesh/test_rosbridge_robot_command_gate.py`, the fourth gate suite.
* `changelog.d/2839-drive-reports-a-refused-trailing-stop.md` - "### Fixed: a timed drive whose trailing stop was
  refused reports it": "`drive(linear=1.0, duration=1.0)` answered `status="success"` ... two messages reached the
  wire, the last of them `linear.x = 1.0`, and no zero followed"; the rule now lives once as
  `_mobile_base.failed_halt_error`.
* `changelog.d/1110-rosbridge-transport.md` (Vivek, #1110) - "### Added: rosbridge transport - `use_rosbridge` tool +
  `RosbridgeRobot` (drive ROS1 robots, no ROS install)": "`RosbridgeRobot.from_curiosity()` preconfigures the NASA
  Curiosity Mars rover Gazebo simulation (ROS1 Noetic), with the hardened drive contract".

---

## 5. EXAMPLES (primary templates, printed in full)

Directory `examples/ros2/`: `deepracer_agent.py`, `turtlebot_demo.py`, `rtps_turtle_demo.py`, `sim_bridge_demo.py`,
`hardware_bridge_demo.py`, `hardware_bridge_rtps_demo.py`, `use_ros/` (agent_drive.py, showcase.py, README.md,
Dockerfile, docker-compose.yml, run_agent.sh, run_showcase.sh, sample outputs), `rtps_proof/` (drive_and_verify.py,
Dockerfile, docker-compose.yml, run_proof.sh, README.md). Directory `examples/rosbridge/`: `curiosity_agent.py`.
Every demo is graded by `tests/test_examples_never_report_a_refused_command.py` (a refused or paused command must
raise and name the remedy, never print a completed run) and `tests/test_use_ros_showcase_exercises_every_action.py`.

### 5.1 `examples/ros2/deepracer_agent.py` (49 lines)

```python
#!/usr/bin/env python3
"""Drive an AWS DeepRacer with natural language - Ackermann bridge demo.

Goal: Show AckermannRosRobot presenting a steering-geometry ROS 2 car as
strands agent tools. The bridge converts (linear, angular) commands through a
bicycle model to the DeepRacer's normalized servo interface, runs the car's
manual-mode service handshake automatically before the first command, and
always trails sustained commands with a zero so the car cannot be left
driving.

Dependencies:
  pip install strands-robots strands-agents
  A sourced ROS 2 environment (rclpy) on the same network/domain as the car,
  with the DeepRacer core stack running (ctrl_pkg, webserver_pkg, rplidar).

SAFETY: put the car on blocks or a clear track before running. The servo topic
and both mode services are gated command surfaces, so this agent prompts for
operator approval before each command it sends. For an unattended run,
pre-approve exactly those three surfaces instead (bare names cover the
namespaced DeepRacer spellings):

    export STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state

Expected output: the agent drives a short pattern and summarizes the lidar.
Runtime: ~20 seconds (depends on LLM latency).
"""

from strands import Agent

from strands_robots.drivers.ros import AckermannRosRobot

# Stock DeepRacer wiring: servo topic, lidar, and the two-step manual-mode
# handshake are preconfigured; override any keyword for a modified car.
car = AckermannRosRobot.from_deepracer(node_name="deepracer")

agent = Agent(tools=car.tools)

result = agent(
    "Drive forward at 0.3 m/s for two seconds, then arc gently left for two "
    "seconds, stop, and read the lidar to tell me the nearest obstacle."
)

# An unapproved gated command pauses the run rather than finishing it: nothing
# has moved, and the question carries both ways to answer it. Printing that as a
# completed run would report a drive the car never made.
if result.stop_reason == "interrupt":
    raise RuntimeError(f"paused at the command gate - the car did not move: {result.interrupts}")

print(f"Agent completed: {result}")
```

### 5.2 `examples/ros2/turtlebot_demo.py` (73 lines)

```python
#!/usr/bin/env python3
"""Drive a ROS 2 turtle (or any cmd_vel robot) through the mesh bridge.

Goal: Show that a remote ROS 2 robot becomes a first-class strands Robot. A
``RosBridgedRobot`` wraps the turtle's ``cmd_vel`` / pose topics; an agent then
drives it with natural language, using the same ``Agent(tools=[robot])`` pattern
as the simulated and hardware arms.

Dependencies:
  The bridge forwards to ``use_ros``, which runs in-process through ``rclpy``,
  so this script must run inside an interpreter where a ROS 2 distro is sourced
  (``rclpy`` importable). The easiest self-contained setup is to run everything
  inside a ROS 2 container:

    docker run -it --rm --net host ros:jazzy bash
    # then, inside the container:
    apt-get update && apt-get install -y ros-jazzy-turtlesim python3-pip
    pip install "strands-robots[ros2]" strands-agents --break-system-packages
    source /opt/ros/jazzy/setup.bash
    QT_QPA_PLATFORM=offscreen ros2 run turtlesim turtlesim_node &
    # /turtle1/cmd_vel is a gated command surface; the programmatic section
    # below has no operator to prompt, so pre-approve that one topic:
    export STRANDS_ROS2_COMMAND_ALLOW=/turtle1/cmd_vel
    python3 turtlebot_demo.py

  Already on a machine with ROS 2 sourced? Just ``source .../setup.bash`` and
  run the script directly - no container needed.

Expected output: the turtle's pose changes after the drive commands.
Runtime: ~10 seconds (plus LLM latency for the agent section).
"""

from strands_robots.drivers.ros import RosBridgedRobot


def _check(result: dict, what: str) -> dict:
    """Raise if a bridge call returned an error dict - never continue silently.

    ``drive`` / ``stop`` REPORT a refusal by returning
    ``{"status": "error", ...}`` rather than raising, and ``/turtle1/cmd_vel`` is
    a gated command surface a script has no operator to approve, so a discarded
    result prints an "after" pose identical to the "before" one as if that were
    the drive's outcome.
    """
    if isinstance(result, dict) and result.get("status") == "error":
        raise RuntimeError(f"{what} failed: " + "; ".join(c.get("text", "") for c in result.get("content", [])))
    return result


# 1. Wrap the remote ROS 2 robot. Nothing connects yet - the bridge is thin.
turtle = RosBridgedRobot.from_ros(
    node_name="turtlesim",
    cmd_vel_topic="/turtle1/cmd_vel",
    odom_topic="/turtle1/pose",
    odom_type="turtlesim/msg/Pose",
)

# 2. Direct, programmatic control. Needs STRANDS_ROS2_COMMAND_ALLOW to name
#    /turtle1/cmd_vel (see the header): a script has no operator context, so
#    use_ros's command gate has nobody to ask. The agent section below does
#    carry one - the bridge's drive/stop tools forward it, so the operator is
#    prompted per command instead.
print("before:", turtle.get_pose()["content"][0]["text"])
_check(turtle.drive(linear=2.0, angular=1.5, duration=1.5), "drive")
print("after: ", turtle.get_pose()["content"][0]["text"])
_check(turtle.stop(), "stop")

# 3. Hand the robot to an agent - its methods become named tools. Uncomment to
#    run (needs strands-agents + a model provider configured):
#
# from strands import Agent
# agent = Agent(tools=turtle.tools)
# agent("drive forward for two seconds while turning left, then report the pose")
```

### 5.3 `examples/rosbridge/curiosity_agent.py` (69 lines)

```python
#!/usr/bin/env python3
"""Drive the NASA Curiosity Mars rover in Gazebo with natural language.

Goal: Show RosbridgeRobot presenting a ROS1 robot as strands agent tools over
a rosbridge WebSocket - with NO ROS environment on this machine (pure pip).

Pipeline:
  NL -> Strands Agent -> RosbridgeRobot -> use_rosbridge -> rosbridge (ws://:9090)
     -> Curiosity rover (ROS1 Noetic + Gazebo)

Dependencies:
  pip install "strands-robots[rosbridge]" strands-agents
  AWS credentials for Bedrock (or any strands-agents model provider).
  Optional: MODEL=<bedrock model id> to override the default model.

The rover's cmd_vel is a gated command surface, so the agent prompts for
operator approval before each drive it sends. For an unattended run, pre-approve
exactly that surface instead:

    export STRANDS_ROS2_COMMAND_ALLOW=/curiosity_mars_rover/ackermann_drive_controller/cmd_vel

The simulation runs separately (it is NOT part of this package). One-time
standup with Docker, headless, from the community Curiosity workspace:

  docker run -d --name curiosity -p 9090:9090 <noetic-image> bash -lc '
    source /ws/devel/setup.bash &&
    roslaunch curiosity_mars_rover_gazebo main_mars_terrain.launch gui:=false rviz:=false &
    sleep 25 &&
    roslaunch rosbridge_server rosbridge_websocket.launch'

(or natively: ROS1 Noetic + https://github.com/mark-gl/curiosity_mars_rover_ws
 built with catkin_make, plus ros-noetic-rosbridge-suite. See
 docs/reference/ros2/rosbridge-robot.md for the full recipe.)

Expected output: the agent drives the rover across Mars terrain and reports
the odometry displacement. Runtime: ~30 seconds (LLM latency + 2 drive legs).
"""

import os

from strands import Agent

from strands_robots.drivers.ros import RosbridgeRobot

# Stock NASA-sim wiring: cmd_vel/odom topics and safety limits preconfigured;
# point host at wherever rosbridge runs (docker port-map, another machine...).
rover = RosbridgeRobot.from_curiosity(host=os.environ.get("ROS_HOST", "localhost"))

# MODEL env selects any strands-agents Bedrock model id (defaults to the
# strands default); e.g. MODEL=us.amazon.nova-pro-v1:0 for accounts without
# Anthropic model access.
agent = Agent(model=os.environ.get("MODEL"), tools=rover.tools)

result = agent(
    os.environ.get(
        "PROMPT",
        "Read the rover's current pose. Then drive forward at 1.0 m/s for 5 "
        "seconds, arc left gently for 3 seconds, and stop. Read the pose again "
        "and report how far the rover moved across the Martian terrain.",
    )
)

# An unapproved gated command pauses the run rather than finishing it: nothing
# has moved, and the question carries both ways to answer it. Printing that as a
# completed run would report a drive across Mars that never happened.
if result.stop_reason == "interrupt":
    raise RuntimeError(f"paused at the command gate - the rover did not move: {result.interrupts}")

print(f"Agent completed: {result}")
```

### 5.4 `examples/ros2/rtps_turtle_demo.py` (61 lines)

```python
#!/usr/bin/env python3
"""Drive a ROS 2 turtle over PURE RTPS - no rclpy, no sourced ROS 2 distro.

This is the "act as a robot" demo: a bare cyclonedds participant publishes
geometry_msgs/Twist on /turtle1/cmd_vel, and a real ROS 2 turtlesim moves. The
only dependency is the cyclonedds binding - this script runs on macOS / Jetson /
CI with NO ROS 2 installed in the Python environment.

Dependencies:
  pip install "strands-robots[ros2]"   # cyclonedds: a self-contained wheel on
                                       # macOS / Windows / Linux x86_64. Linux
                                       # aarch64 (Jetson) has no wheel and builds
                                       # against a Cyclone DDS C install - see
                                       # docs/reference/rtps-integration.md#linux-aarch64-jetson

A ROS 2 turtle on the same DDS domain (e.g. host networking):
  docker run -d --name turtle --net host ros:jazzy bash -lc \\
    "apt-get update && apt-get install -y ros-jazzy-turtlesim && \\
     source /opt/ros/jazzy/setup.bash && \\
     QT_QPA_PLATFORM=offscreen ros2 run turtlesim turtlesim_node"

``/turtle1/cmd_vel`` is a gated command surface and this script has no operator
to prompt, so pre-approve that one topic before running it:

  export STRANDS_ROS2_COMMAND_ALLOW=/turtle1/cmd_vel

Expected: the turtle drives forward and to the left for ~1.5 seconds.
Runtime: ~2 seconds.
"""

from strands_robots.drivers.ros import RtpsRobot


def _check(result: dict, what: str) -> dict:
    """Raise if a bridge call returned an error dict - never continue silently.

    ``drive`` / ``stop`` / ``advertise`` REPORT a refusal by returning
    ``{"status": "error", ...}`` rather than raising, and ``/turtle1/cmd_vel`` is
    a gated command surface a script has no operator to approve, so a discarded
    result prints this demo's closing line for a turtle that never moved.
    """
    if isinstance(result, dict) and result.get("status") == "error":
        raise RuntimeError(f"{what} failed: " + "; ".join(c.get("text", "") for c in result.get("content", [])))
    return result


# 1. Wrap the turtle as a pure-RTPS robot. No ROS 2 needed in this interpreter.
turtle = RtpsRobot.from_rtps(node_name="turtlesim", cmd_vel_topic="/turtle1/cmd_vel")

# 2. Appear on the ROS 2 graph as a cmd_vel publisher, then drive.
_check(turtle.advertise(), "advertise")
_check(turtle.drive(linear=2.0, angular=1.5, duration=1.5), "drive")  # publish Twist over RTPS
_check(turtle.stop(), "stop")
print("done - the turtle should have moved (check the turtlesim window)")

# 3. Or hand the robot to an agent. Its methods become named tools
#    (drive_turtlesim, stop_turtlesim). Uncomment to run with a model provider:
#
# from strands import Agent
# agent = Agent(tools=turtle.tools)
# agent("drive forward for two seconds while turning left, then stop")
```

### 5.5 `examples/ros2/sim_bridge_demo.py` (49 lines)

```python
#!/usr/bin/env python3
"""Expose a MuJoCo simulation on a ROS 2 domain (SimEngine ros2_bridge=True).

Goal: Show that the simulator can publish its live state on ROS 2 so external
ROS 2 nodes (or the agent's own use_ros calls) can subscribe to it. With
``ros2_bridge=True`` the sim advertises, per robot:

  /<robot>/joint_states            sensor_msgs/msg/JointState  (every step)
  /<robot>/<camera>/image_raw      sensor_msgs/msg/Image  (rgb8, per add_camera view)

Dependencies:
  pip install "strands-robots[sim-mujoco,ros2]"
  rclpy must be importable - it ships with a system ROS 2 install (apt /
  RoboStack) or the official docker images, not PyPI. Run this script in an
  environment where `python3 -c "import rclpy"` works (e.g. inside a
  `ros:jazzy` container with mujoco + strands-robots installed).

Verify from another shell on the same ROS 2 domain:
  ros2 topic list | grep so101
  ros2 topic echo /so101/joint_states

Runtime: runs until interrupted.
"""

import math
import time

from strands_robots.simulation import Simulation

# ros2_bridge=True spins up an internal rclpy node; ros2_domain picks the domain.
sim = Simulation(ros2_bridge=True, ros2_domain=0)
sim.create_world()
sim.add_robot("so101")

joints = sim.robot_joint_names("so101")
print(f"publishing /so101/joint_states for joints: {joints}")

try:
    i = 0
    while True:
        target = 0.6 * math.sin(i / 40.0)
        sim.send_action({j: target for j in joints}, robot_name="so101")
        sim.step(5)  # each step publishes joint_states (+ camera image_raw)
        time.sleep(0.05)
        i += 1
except KeyboardInterrupt:
    pass
finally:
    sim.destroy()  # tears down the ROS 2 node cleanly
```

### 5.6 `examples/ros2/hardware_bridge_demo.py` (77 lines)

```python
#!/usr/bin/env python3
"""Expose a real robot on a ROS 2 domain - full duplex (Robot ros2_bridge=True).

Goal: Show that a physical arm becomes a first-class ROS 2 participant in BOTH
directions when constructed with ``ros2_bridge=True``:

  * publish (outbound) - the live observation is advertised so external ROS 2
    nodes (rviz, nav2, or the agent's own use_ros calls) can subscribe to the
    hardware, per robot:

      /<robot>/joint_states            sensor_msgs/msg/JointState  (every control step)
      /<robot>/<camera>/image_raw      sensor_msgs/msg/Image  (rgb8, per camera)

  * subscribe (inbound) - the bridge listens on /<robot>/joint_command and
    forwards each JointState into Robot.send_action, so an external ROS 2 stack
    (a teleop node, MoveIt, a trajectory replayer) can DRIVE the real arm:

      /<robot>/joint_command           sensor_msgs/msg/JointState  (name+position -> send_action)

This is the symmetric counterpart of examples/ros2/sim_bridge_demo.py - the sim
and hardware telemetry bridges are thin subclasses of the same
RosTelemetryBridge, so a real arm and its digital twin publish identical topics.
The inbound command path lives only on the hardware bridge: a simulation is
driven by its physics engine; the real arm is the thing an external controller
can physically move.

Dependencies:
  pip install "strands-robots[ros2]"
  rclpy must be importable - it ships with a system ROS 2 install (apt /
  RoboStack) or the official docker images, not PyPI. Run this in an
  environment where `python3 -c "import rclpy"` works (e.g. inside a
  `ros:jazzy` container with strands-robots installed).

A physical SO-101 must be connected; pass its serial port. With no arm attached
this raises at connect() - the bridge itself is hardware-agnostic.

Verify telemetry from another shell on the same ROS 2 domain:
  ros2 topic list | grep so101
  ros2 topic echo /so101/joint_states

Drive the arm from another shell (inbound command path):
  ros2 topic pub --once /so101/joint_command sensor_msgs/msg/JointState \
    '{name: ["shoulder_pan.pos", "elbow.pos"], position: [0.1, -0.2]}'
"""

import time

from strands_robots import Robot

# ros2_bridge=True spins up an internal rclpy node; ros2_domain picks the domain.
# ros2_commands=True (the default) also subscribes to /so101/joint_command and
# drives the arm - full duplex. Set ros2_commands=False for a read-only bridge.
# Opt-in by design: ros2_bridge=False (the default) never touches ROS 2.
arm = Robot(
    "so101",
    mode="real",
    ros2_bridge=True,
    ros2_domain=0,
    ros2_commands=True,  # subscribe to joint_command and drive the arm
    cameras={"wrist": {"type": "opencv", "index_or_path": "/dev/video0", "fps": 30}},
)

print("publishing /so101/joint_states (+ /so101/wrist/image_raw) on domain 0")
print("listening on /so101/joint_command to drive the arm (full duplex)")

try:
    # Publish the live observation on demand, ~10 Hz. (Inside a running task the
    # control loop publishes automatically after each observation.) Meanwhile a
    # background spin thread services inbound joint_command messages and drives
    # the arm via send_action - both directions run concurrently.
    while True:
        arm.publish_ros_observation()
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    arm.cleanup()  # stops the command thread and tears down the ROS 2 node cleanly
```

### 5.7 `examples/ros2/hardware_bridge_rtps_demo.py` (62 lines)

```python
#!/usr/bin/env python3
"""Expose a real robot on ROS 2 over pure RTPS - no rclpy, no sourced distro.

This is the rclpy-free twin of examples/ros2/hardware_bridge_demo.py. Same
full-duplex behavior - publish /<robot>/joint_states (+ camera image_raw),
subscribe /<robot>/joint_command -> send_action - but the transport is pure
cyclonedds (a single pip wheel) instead of rclpy, so it runs with NO sourced
ROS 2 distro:

    pip install "strands-robots[ros2]"   # pulls cyclonedds; nothing else needed
                                         # on macOS / Windows / Linux x86_64.
                                         # Linux aarch64 (Jetson) has no
                                         # cyclonedds wheel and needs a Cyclone
                                         # DDS C install (CYCLONEDDS_HOME) - see
                                         # docs/reference/rtps-integration.md

The two transports emit the same topics with byte-identical payloads, so a real
ROS 2 node, rviz, or `ros2 topic echo` reads this exactly as it reads the rclpy
bridge or a real hardware node. The graph metadata differs - a bare participant
has no ROS 2 node name and no type hash, so `ros2 node list` does not list it and
`ros2 topic info -v` reports `_CREATED_BY_BARE_DDS_APP_` with an `INVALID` type
hash (docs/learn/ros2.md#what-a-ros-2-node-can-still-tell-apart):

    ros2 topic echo /so101/joint_states
    ros2 topic pub --once /so101/joint_command sensor_msgs/msg/JointState \
      '{name: ["shoulder_pan.pos"], position: [0.1]}'

Type coverage is bounded by the RTPS IDL bundle (strands_robots.rtps.idl):
joint_states + image_raw are in; anything outside the bundle needs the rclpy
backend (ros2_transport="rclpy", the default).

A physical SO-101 must be connected; with no arm attached this raises at
connect() - the bridge itself is hardware-agnostic.
"""

import time

from strands_robots import Robot

# ros2_transport="rtps" selects the cyclonedds backend (no rclpy). Everything
# else is identical to the rclpy hardware bridge demo.
arm = Robot(
    "so101",
    mode="real",
    ros2_bridge=True,
    ros2_transport="rtps",
    ros2_domain=0,
    ros2_commands=True,  # subscribe to joint_command and drive the arm
    cameras={"wrist": {"type": "opencv", "index_or_path": "/dev/video0", "fps": 30}},
)

print("publishing /so101/joint_states (+ /so101/wrist/image_raw) over RTPS, no rclpy")
print("listening on /so101/joint_command to drive the arm (full duplex)")

try:
    while True:
        arm.publish_ros_observation()
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    arm.cleanup()  # stops the poll thread and drops the cyclonedds participant
```

### 5.8 `examples/ros2/use_ros/agent_drive.py` (99 lines) - an agent holding the raw `use_ros` tool

```python
#!/usr/bin/env python3
"""A Strands agent driving a real ROS 2 turtlesim through the use_ros tool.

The natural-language end of the showcase: a Bedrock-backed agent is given the
use_ros tool and asked, in plain English, to drive a clean SQUARE using
closed-loop control - it echoes the pose after every move, computes the heading
error, and issues corrective turns until each corner is within tolerance. All
ROS 2 I/O is in-process through rclpy (no ros2 CLI).

The script resets the canvas and teleports the turtle to a known corner first
(both via use_ros service_call - note teleport_absolute is resolved dynamically
and is not even in any static registry), then hands control to the agent.

Requires (inside a sourced ROS 2 env with turtlesim running):
    pip install strands-agents
    export AWS_BEARER_TOKEN_BEDROCK=...        # or any boto3 credential chain
    export STRANDS_MODEL_ID=global.anthropic.claude-opus-4-8   # optional
    export AWS_REGION=us-east-1

Run:
    python3 agent_drive.py
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from strands_robots.tools.use_ros import use_ros as _use_ros_tool

# The @tool decorator returns a DecoratedFunctionTool instance whose
# __call__ static analysis (CodeQL) does not recognize. Bind it to a
# Callable-typed name so the call sites are seen as calling a function.
use_ros: Callable[..., dict[str, Any]] = _use_ros_tool


def pose() -> tuple[float, float, float] | None:
    r = use_ros(action="echo", topic="/turtle1/pose", type="turtlesim/msg/Pose", count=1, timeout=2.0)
    if r["status"] != "success":
        return None
    sample = json.loads(r["content"][0]["text"].split(":\n", 1)[1])[0]
    return round(sample["x"], 3), round(sample["y"], 3), round(sample["theta"], 3)


def main() -> None:
    # Clean canvas + known start corner facing east. teleport_absolute is resolved
    # dynamically by use_ros - it is not in any static type registry.
    use_ros(action="service_call", service="/reset", type="std_srvs/srv/Empty", fields={})
    time.sleep(0.5)
    use_ros(
        action="service_call",
        service="/turtle1/teleport_absolute",
        type="turtlesim/srv/TeleportAbsolute",
        fields={"x": 3.0, "y": 3.0, "theta": 0.0},
    )
    time.sleep(0.5)
    print("start pose:", pose())

    model = BedrockModel(
        model_id=os.getenv("STRANDS_MODEL_ID", "global.anthropic.claude-opus-4-8"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    agent = Agent(
        model=model,
        tools=[use_ros],
        system_prompt=(
            "You pilot a ROS 2 turtlesim turtle via the use_ros tool, using CLOSED-LOOP control. "
            "Drive: use_ros(action='publish', topic='/turtle1/cmd_vel', type='geometry_msgs/msg/Twist', "
            "fields={'linear':{'x':SPEED},'angular':{'z':TURN}}, count=N, rate=10.0). "
            "Sense: use_ros(action='echo', topic='/turtle1/pose', type='turtlesim/msg/Pose', count=1) "
            "returns x,y,theta (theta in radians, -pi..pi, 0=east, +=counterclockwise). "
            "ALWAYS echo the pose after each move and correct: if a turn overshoots or undershoots the "
            "target heading, issue a small corrective turn before driving forward. "
            "Forward speed x=1.5; for turns use small bursts (count=3-5 at z=1.5) then re-check heading. "
            "Be precise; verify each corner with an echo. Keep commentary to one short line per action."
        ),
    )
    task = (
        "Drive the turtle in a clean SQUARE with ~2.5 unit sides. Start heading east (theta=0). "
        "For each of 4 sides: drive forward ~2.5 units (check pose to confirm distance), then turn "
        "LEFT to the next cardinal heading (0 -> +1.571 -> +-3.142 -> -1.571 -> back to 0), using "
        "closed-loop echo+correct so each heading is within ~0.05 rad before driving the next side. "
        "After completing the square, stop (publish zero velocity) and echo the final pose."
    )
    print("\n=== AGENT DRIVING A CLOSED-LOOP SQUARE ===")
    result = agent(task)
    print("\n=== FINAL ===\n" + str(result)[:1000])
    time.sleep(1)
    print("\nfinal pose:", pose())


if __name__ == "__main__":
    main()
```

### 5.9 `examples/ros2/use_ros/showcase.py` (149 lines) - every `use_ros` action against a live turtlesim

```python
#!/usr/bin/env python3
"""Live showcase of every use_ros action against a real ROS 2 turtlesim.

Runs in-process through rclpy (no ros2 CLI, no code-generation) and exercises
the full action surface against a running turtlesim node:

    status / list_topics / list_nodes / list_services / list_actions /
    info / echo / publish / service_call / action_send_goal
    + the two error paths.

It captures real data - including a closed sense->act->sense loop: read the
pose, publish a Twist, read the pose again and confirm it changed; a goal sent
to turtlesim's /turtle1/rotate_absolute action server, whose terminal status and
feedback come back decoded; plus the two structured-error contracts (a
valid-shaped but non-installed type returns an error dict instead of crashing; a
metacharacter topic is rejected).

Run it inside a sourced ROS 2 environment with turtlesim running:

    # in a ros:jazzy container (or any machine with ROS 2 sourced):
    source /opt/ros/jazzy/setup.bash
    QT_QPA_PLATFORM=offscreen ros2 run turtlesim turtlesim_node &
    pip install strands-agents          # rclpy comes from the sourced distro
    # /turtle1/cmd_vel is a gated command surface and this script runs outside
    # an agent loop, so there is no operator to prompt - pre-approve it:
    STRANDS_ROS2_COMMAND_ALLOW=/turtle1/cmd_vel python3 showcase.py

See ./README.md for a one-command docker-compose runner.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from typing import Any

from strands_robots.tools.use_ros import use_ros as _use_ros_tool

# The @tool decorator returns a DecoratedFunctionTool instance whose
# __call__ static analysis (CodeQL) does not recognize. Bind it to a
# Callable-typed name so the call sites are seen as calling a function.
use_ros: Callable[..., dict[str, Any]] = _use_ros_tool

# The absolute heading the action goal asks turtlesim to rotate to. Read back
# from /turtle1/pose afterwards, so it is the goal and the assertion both.
_GOAL_HEADING = 1.5708


def run(**kw: object) -> dict:
    args = ", ".join(f"{k}={v!r}" for k, v in kw.items())
    print(f"\n### use_ros({args})")
    r = use_ros(**kw)  # type: ignore[arg-type]
    print(f"[{r['status']}] {r['content'][0]['text'][:600]}")
    return r


def _pose_xyt(result: dict) -> tuple[float, float, float] | None:
    txt = result["content"][0]["text"]
    if result["status"] != "success" or ":\n" not in txt:
        return None
    sample = json.loads(txt.split(":\n", 1)[1])[0]
    return sample["x"], sample["y"], sample["theta"]


def _goal_status(result: dict) -> str | None:
    txt = result["content"][0]["text"]
    if result["status"] != "success" or ":\n" not in txt:
        return None
    return str(json.loads(txt.split(":\n", 1)[1])["goal_status"])


def main() -> int:
    print("=" * 70)
    print("use_ros LIVE SHOWCASE - in-process rclpy against a real turtlesim")
    print("=" * 70)

    status = run(action="status")
    if "rclpy (in-process)" not in status["content"][0]["text"]:
        print("\nERROR: rclpy backend not available - source a ROS 2 distro first.", file=sys.stderr)
        return 2

    # Graph introspection.
    run(action="list_topics")
    run(action="list_nodes")
    run(action="list_services")
    run(action="info", topic="/turtle1/cmd_vel")

    # Closed sense -> act -> sense loop.
    before = run(action="echo", topic="/turtle1/pose", count=1, timeout=3.0)
    run(
        action="publish",
        topic="/turtle1/cmd_vel",
        type="geometry_msgs/msg/Twist",
        fields={"linear": {"x": 2.0}, "angular": {"z": 1.8}},
        count=20,
        rate=10.0,
    )
    time.sleep(0.4)
    after = run(action="echo", topic="/turtle1/pose", count=1, timeout=3.0)

    # Service call: spawn a second turtle, then confirm it joined the graph.
    run(
        action="service_call",
        service="/spawn",
        type="turtlesim/srv/Spawn",
        fields={"x": 2.0, "y": 2.0, "theta": 0.0, "name": "t2"},
    )
    time.sleep(0.5)
    run(action="list_topics")

    # Action client: the servers on the graph, then a goal to one of them.
    # This is the only verb whose reply is a terminal status rather than a
    # message - acceptance, streamed feedback and the result come back decoded,
    # and an expiring timeout cancels the goal rather than abandoning it.
    run(action="list_actions")
    goal = run(
        action="action_send_goal",
        action_name="/turtle1/rotate_absolute",
        type="turtlesim/action/RotateAbsolute",
        fields={"theta": _GOAL_HEADING},
        timeout=20.0,
    )
    turned = run(action="echo", topic="/turtle1/pose", count=1, timeout=3.0)

    # Structured-error contracts (never raise).
    run(action="echo", topic="/turtle1/pose", type="nonexistent_pkg/msg/Foo")
    run(action="echo", topic="/bad; rm -rf")

    b, a, t = _pose_xyt(before), _pose_xyt(after), _pose_xyt(turned)
    status_of_goal = _goal_status(goal)
    print("\n" + "=" * 70)
    print("PROOF: pose changed via use_ros publish (in-process rclpy, no CLI):")
    print(f"  before: {b}")
    print(f"  after:  {a}")
    print(f"  goal:   {status_of_goal} -> theta {t[2] if t else None} (asked {_GOAL_HEADING})")
    print("=" * 70)
    moved = bool(b and a and (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) > 0.1)
    rotated = status_of_goal == "SUCCEEDED" and t is not None and abs(t[2] - _GOAL_HEADING) < 0.2
    if moved and rotated:
        print("PASS: a real ROS 2 turtle was driven, turned and read back through use_ros.")
        return 0
    print(f"FAIL: moved={moved} rotated={rotated}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 5.10 `examples/ros2/rtps_proof/drive_and_verify.py` (84 lines)

```python
#!/usr/bin/env python3
"""Cross-process proof: drive a real ROS 2 turtlesim through use_rtps.

Runs INSIDE the proof container (see Dockerfile / docker-compose.yml). It:

1. reads turtlesim's pose before (via the ros2 CLI, the ground-truth observer),
2. drives /turtle1/cmd_vel using ``RtpsRobot`` -> ``use_rtps`` -> bare cyclonedds
   (NO rclpy on the publish side - only our ROS<->DDS mangling + IDL bundle),
3. reads the pose after and asserts the turtle moved.

A non-zero exit means the turtle did not move - the wire format is wrong.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time

from strands_robots.drivers.ros import RtpsRobot


def _ros_pose() -> tuple[float, float, float] | None:
    """Read turtlesim's (x, y, theta) via the ros2 CLI - the ground truth."""
    try:
        out = subprocess.run(
            ["bash", "-lc", "source /opt/ros/jazzy/setup.bash && " + "timeout 5 ros2 topic echo --once /turtle1/pose"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except subprocess.TimeoutExpired:
        return None

    def g(k: str) -> str | None:
        m = re.search(rf"{k}:\s*([-0-9.]+)", out)
        return m.group(1) if m else None

    x, y, th = g("x"), g("y"), g("theta")
    if None in (x, y, th):
        return None
    return float(x), float(y), float(th)


def main() -> int:
    print("== reading pose BEFORE ==")
    before = _ros_pose()
    print(f"   before: {before}")
    if before is None:
        print("ERROR: could not read turtlesim pose - is the node running?", file=sys.stderr)
        return 2

    print("== driving via RtpsRobot -> use_rtps -> bare cyclonedds (no rclpy) ==")
    turtle = RtpsRobot.from_rtps(node_name="turtlesim", cmd_vel_topic="/turtle1/cmd_vel")
    turtle.advertise()
    time.sleep(1.0)  # DDS discovery settle
    result = turtle.drive(linear=2.0, angular=2.0, duration=3.0)
    print(f"   drive result: {result['status']} - {result['content'][0]['text']}")
    turtle.stop()
    time.sleep(0.5)

    print("== reading pose AFTER ==")
    after = _ros_pose()
    print(f"   after:  {after}")
    if after is None:
        print("ERROR: could not read pose after driving", file=sys.stderr)
        return 2

    moved = abs(after[0] - before[0]) + abs(after[1] - before[1]) + abs(after[2] - before[2])
    print(f"== total pose delta: {moved:.4f} ==")
    if moved < 0.1:
        print("FAIL: turtle did not move - the RTPS wire format is wrong", file=sys.stderr)
        return 1

    print("\nPASS: a real ROS 2 turtlesim was driven by use_rtps over pure RTPS.")
    print(f"  x:     {before[0]:.3f} -> {after[0]:.3f}")
    print(f"  y:     {before[1]:.3f} -> {after[1]:.3f}")
    print(f"  theta: {before[2]:.3f} -> {after[2]:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`examples/ros2/use_ros/README.md` documents `docker compose run --build --rm showcase` (a `ros:jazzy` + turtlesim
image), the Bedrock agent run (`global.anthropic.claude-opus-4-8`, 43 `use_ros` calls to drive a closed-loop square,
GIF at `docs/assets/img/use_ros_agent_square.gif`), and a table of what each action proves.
`examples/ros2/rtps_proof/README.md` explains the cross-process proof (turtlesim with `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`
in one container, no host networking, arm64 builds cyclonedds from source).

### 5.11 Every other `examples/` directory, one line each (`ls examples`)

* `01_sim_hello_world.py` .. `19_judge_recorded_episodes.py` - numbered single-primitive walkthroughs (Robot+Simulation,
  create_policy, recording, mesh peer discovery, Agent+Robot tool, record+stream, post-tune, discover lerobot,
  terrain, benchmarks, domain randomisation, physics introspection, save/perturb, catalog, harness memory, pour task,
  SO-101 pick, episode judge) (`examples/README.md:34-57`).
* `fleet/` - multi-robot orchestration suite: skill dispatch, cross-zone transport, failover, emergency evacuation,
  work-order dispatch, `dashboard.py`, `capabilities.py`.
* `isaac_gs/`, `mujoco_gs/` - robot composited over 3D Gaussian Splatting backdrops (Isaac RTX / MuJoCo).
* `isaac_on_aws/` - provision/smoke/teardown an Isaac Sim GPU instance on AWS.
* `kimodo/` - Kimodo text-conditioned G1 motion diffusion.
* `lerobot/` - Hub-to-hardware companion, MolmoAct2 collect/train/run.
* `locomotion/` - G1 locomotion agent/keyboard/scripted and the VLA-on-G1 workflow.
* `mesh/` - Zenoh ACL JSON5 templates (`mesh_acl_example.json5`, `mesh_acl_strict_per_peer.json5`), AWS IoT direct RPC.
* `microduck/` - Microduck policy hot-swap, record, eval, render.
* `mjlab/` - mjlab RL train/deploy, sim2sim G1 velocity, vectorised eval.
* `notebooks/` - seven CPU-only Jupyter notebooks (getting started .. evaluate a policy).
* `registry/` - lerobot hardware catalog discovery.
* `robots/` - `neon.py` (the Unitree G1 "neon" showcase).
* `ros2/`, `rosbridge/` - as above.
* `so101_curobo/` - cuRobo motion planning + dataset capture for SO-101.
* `training/` - FastSAC / PPO reach trainers.
* `vla/` - Cosmos 3, FLUX 3 Action, MolmoAct2 rollouts.
* `wbc/` - GR00T-WBC (SONIC) G1 composite/gait/torque deploy.

---

## 6. DOCS

The ROS 2 reference pages named in AGENTS.md rule 18 and in older changelog fragments
(`docs/reference/ros2-integration.md`, `docs/reference/ros2/{ackermann,safety,sim-bridge,hardware-bridge,mesh-bridge,
rosbridge-robot,rtps-robot}.md`, `docs/reference/rosbridge-integration.md`, `docs/reference/rtps-integration.md`) **no
longer exist**: the site rewrite (#4092, #4112, #4676) folded them into `docs/learn/ros2.md` and installed
redirects (`mkdocs.yml:239-248`, `:283-292`). `docs/reference/api/mesh.md` and `docs/reference/api/tools.md` are
mkdocstrings stubs. **The word "DeepRacer" appears nowhere under `docs/`** (grep over docs, README, mkdocs.yml,
CHANGELOG.md, registry returned only `strands_robots/_command_gate.py`, `drivers/ros/_mobile_base.py`,
`drivers/ros/ackermann_robot.py`, `drivers/ros/ros_bridge.py`, three tests, `examples/ros2/deepracer_agent.py`
and three changelog fragments).

### 6.1 `docs/learn/ros2.md` (79 lines), section by section

* Front matter: "Three ROS 2 transports, when to use each, one operator gate, what a ROS 2 node can still tell apart" (`:1-3`).
* Opening sketch: `Agent(tools=[use_rtps])` then "List the topics on the graph, then echo /odom once." (`:9-15`).
* **Three transports** (`:17-31`): table of `use_ros` (in-process rclpy; sourced distro; services and actions;
  10 verbs), `use_rosbridge` (`[rosbridge]`, roslibpy, port 9090, ROS 1 and 2 with rosapi; 6 verbs), `use_rtps`
  (`[ros2]` cyclonedds; every distro; topics only; 6 verbs). Guidance: "Pick `use_ros` on the robot or a ROS
  workstation for services or actions; `use_rosbridge` from a laptop when the robot runs rosbridge; `use_rtps` with no
  ROS install near the agent, or when the agent must *be* a robot" (`:27`). Types: dynamic on `use_ros`, ROS 1
  two-segment on rosbridge, curated IDL bundle on RTPS (`:29`). "rosbridge is unauthenticated by default" (`:31`).
* **The gate is the same on all three** (`:33-39`): lists the full blocklist verbatim, "Reads are never gated, nor is
  `use_rtps`'s `advertise`", `STRANDS_ROS2_COMMAND_ALLOW` by base name ("a bare `/cmd_vel` lifts the gate on every
  namespaced `/cmd_vel`, so write `/robot_a/cmd_vel` to scope it (`*` matches nothing here on purpose)"),
  `BYPASS_TOOL_CONSENT=true` lifts with a warning, gate runs after probe and argument checks and before any lock/dial.
* **A real arm on the graph** (`:41-55`): `Robot("so101", mode="real", port=..., driver="lerobot", ros2_bridge=True,
  ros2_transport="rtps", ros2_domain=0, ros2_commands=True, dds_security_config={...})`; publishes
  `/<robot>/joint_states` and `/<robot>/<camera>/image_raw`, subscribes `/<robot>/joint_command`;
  `ros2_transport` is `"rclpy"` (`HardwareRosBridge`) or `"rtps"` (`HardwareRtpsBridge`); `ros2_commands=False`
  publish-only; `joint_limits=` clamps inbound; the RTPS command surface requires `dds_security_config` or
  `STRANDS_ROS2_BRIDGE_I_KNOW_THIS_IS_INSECURE=1`; a sim `Robot(..., ros2_bridge=True)` publishes over rclpy only.
* **What a ROS 2 node can still tell apart** (`:57-59`): RTPS bridge shows `Node name: _CREATED_BY_BARE_DDS_APP_`,
  `INVALID` type hash, `KEEP_LAST (1)` history; tooling that waits for a node or type hash wants rclpy.
* **Linux aarch64 (Jetson)** (`:61-75`): no cyclonedds aarch64 wheel; `sudo apt install ros-$ROS_DISTRO-cyclonedds;
  CYCLONEDDS_HOME=/opt/ros/$ROS_DISTRO pip install 'strands-robots[ros2]'` or build Cyclone DDS from source and
  export `CYCLONEDDS_HOME`; a stale `CYCLONEDDS_HOME` fails hard.
* **A ROS robot on the mesh** (`:77-79`): "`RosBridgedRobot` (rclpy), `RosbridgeRobot` (WebSocket) and `RtpsRobot`
  (DDS) in `strands_robots.mesh` wrap a mobile base that speaks `/cmd_vel` and `/odom` as a mesh peer answering
  `status`, `execute` and `stop` next to the arms; `AckermannRosRobot` does the same for a car-like base. The Yahboom
  M3 Pro driver is the shipped example of a whole robot driven through its ROS 2 graph." (Note: the module path in
  the prose is stale - they live in `strands_robots.drivers.ros` since #4140 - and the sentence about answering
  `status/execute/stop` as a mesh peer is aspirational: none of the four classes has a `Mesh`, `send_action` or
  `stop_task` member; see section 8.)
* No DeepRacer topics, no DeepRacer setup instructions anywhere on the page.

### 6.2 `docs/learn/mesh/bridges.md` (ROS-relevant facts)

* `pip install 'strands-robots[mesh-iot]'`; `bootstrap_account()`, `provision_robot("so101-arm-01")` yield
  `STRANDS_IOT_THING_NAME`, `STRANDS_IOT_ENDPOINT`, `STRANDS_IOT_CERT_DIR`, `STRANDS_MESH_BACKEND=iot` (`:9-21`).
* Three backends: `zenoh` (default, `ZenohTransport`), `iot` (`IotMqttTransport`, MQTT5 mTLS to AWS IoT Core),
  `bridge` (`BridgeTransport`, both; degrades rather than fails) (`:23-31`).
* What the bridge forwards to MQTT: `presence, health, cmd, response, broadcast, safety/event, safety/estop,
  safety/resume`; LAN-only: `state, pose, imu, odom, camera, input, hand, stream, lidar, map`;
  `STRANDS_MESH_BRIDGE_TOPICS` overrides (`:33-37`).
* IoT trust model: Thing name == peer_id == cert CN; `provision_robot(thing_name, region=, cert_dir=, attributes=,
  allow_estop_publish=False)`; env table (`:39-51`); shadow and camera offload mirrors (`:53`).
* Zenoh ACL: `STRANDS_MESH_ACL_FILE` JSON5 with `default_permission: "deny"`, roles `robot_peer`, `operator_peer`,
  `dashboard_peer`; `STRANDS_MESH_ACCEPT_PERMISSIVE_ACL=1` gate (`:57-67`).
* "ROS 2 as a peer" (`:69-71`): same stale sentence as ros2.md.

### 6.3 `docs/concepts/backends.md`

Hardware backends: `driver="lerobot"` wraps a lerobot class; `driver="strands"` picks a native driver
(`{{n:native_drivers}}` of them: "Feetech and Dynamixel serial buses, Franka, Robotiq, Unitree, ROS transports");
`driver="auto"` honours the registry `hardware.driver`; `"strands"` is refused by name when no native driver exists
(`:22-26`). "A hardware robot publishes a smaller tool: read (`status`, `get_state`, `list_cameras`, `render`), stop,
and the gated `execute` and `start`" (`:26`). Transports: "a ROS 2 graph or rosbridge for anything with a ROS stack"
(`:28-30`). The simulator is never gated (`:20`).

### 6.4 `docs/learn/agents.md`

* `Robot(...)` is an `AgentTool`; sim tool `<name>_sim` with 77 actions; real tool is the robot's name with
  `get_state, get_robot_state, list_cameras, render, execute, start, status, stop` (`:23-30`).
* Tool table: `use_ros, use_rosbridge, use_rtps` - "a ROS 2 graph, three transports" - gated on "blocklisted surfaces" (`:43`).
* The operator gate order (allowlist, bypass, no context -> refuse naming the value, interrupt
  `<tool>-command-approval`; `y|yes|approve|approved`; the model never sees the reply) (`:48-59`).
* Allowlist table (`:61-70`): `Robot(mode="real")`/mesh -> `STRANDS_ROBOT_COMMAND_ALLOW` (`execute`, `start`;
  mesh also `teleop_receive`, `reset`, `step`); `pose_tool` -> `STRANDS_POSE_COMMAND_ALLOW`; `serial_tool` ->
  `STRANDS_SERIAL_COMMAND_ALLOW`; `use_unitree` -> `STRANDS_UNITREE_COMMAND_ALLOW`; ROS tools ->
  `STRANDS_ROS2_COMMAND_ALLOW` "by base name"; `robot_mesh` -> `STRANDS_MESH_HITL_ACTIONS` selects the set.
  "`*` pre-approves every command where the tool honours it; `=1` or `=true` pre-approve nothing" (`:70`).
* A literal refusal (`:76-85`) and the dashboard's `MotionInterruptHook` consent card + grant (`:87`).
* Audit row shape (`:89-91`); posture: "There is no `dry_run` flag; the dry run is `mode="sim"`" (`:93-95`).

### 6.5 `docs/learn/security.md`

Layer table (`:11-23`): operator gate (`_command_gate.gate_motion`), motion grants (`_motion_grants`), command
validation (`mesh.security.validate_command`), wire auth (mTLS), ACL, transport caps (`STRANDS_MESH_MAX_*`,
`STRANDS_MESH_*_RATE_HZ`), safety envelopes, driver gates, bus access, path validation, audit log. "Reading is never
gated. Stopping is never gated." (`:27`, note: for the ROS bridges a *stop publish to a blocklisted topic is still
gated* - the sentence refers to the robot tool's `stop` verb). "the ROS blocklist is one set for three transports
because it describes a physical surface" (`:29`). Mesh allowlists and charset `^[a-z][a-z0-9_]*$` (`:33`); teleop
bounds `STRANDS_MESH_INPUT_VALUE_ABS` (720), `STRANDS_MESH_INPUT_MAX_HZ` (100) (`:35`); "The pure-RTPS ROS 2 bridge
refuses an inbound command surface without DDS Security unless `STRANDS_ROS2_BRIDGE_I_KNOW_THIS_IS_INSECURE=1`
... rosbridge is unauthenticated by design, for trusted networks" (`:39`); audit evidence and `verify_audit_integrity`
(`:53-55`).

### 6.6 `docs/reference/api/mesh.md` and `docs/reference/api/tools.md`

`api/mesh.md` renders `strands_robots.mesh.core` (`init_mesh`, `get_local_robots`, `mesh_disabled_by_env`,
`Mesh`), session helpers, `InputPublisher/InputReceiver`, and under "Bridged robots" the four drivers by their
**new** paths `strands_robots.drivers.ros.ros_bridge.RosBridgedRobot`, `...rosbridge_robot.RosbridgeRobot`,
`...rtps_robot.RtpsRobot`, `...ackermann_robot.AckermannRosRobot`, plus `HardwareRosBridge`, `HardwareRtpsBridge`,
`audit.log_safety_event`, device connect (`:51-100`). `api/tools.md` renders `use_ros`, `use_rosbridge`, `use_rtps`,
`robot_mesh` under "ROS and mesh" (`:65-85`). `docs/reference/tools.md` is `{{tools_ref}}` (`:24`).

### 6.7 Other doc facts relevant to a DeepRacer

* `docs/learn/hardware/drivers.md`: robots lerobot has no type for declare `hardware.driver = "strands"`
  (`unitree_go2, robotiq_2f85, reachy_mini, microduck, booster_t1, crazyflie, yahboom_m3pro`); `driver="strands"` on
  a robot with no native driver is refused by name; `port=` is polymorphic (serial path, IP, `radio://`, `host:port`)
  (`:28-30`); the contract table (`:40-52`).
* `docs/learn/dashboard.md`: Agent tab "a microphone opens voice"; Settings has "voice provider" (`:27-28`);
  `/ws/agent` protocol and consent card resume `{"type":"resume","id":...,"approve":true,"always":false}` (`:57`).
* `docs/reference/refusal-codes.md`: codes are the stable contract; the dashboard consent endpoint maps them to grant
  names (`:1-21`).
* `docs/reference/configuration.md:15`: boolean env vars accept `1|true|yes`; security-weakening variables
  (`BYPASS_TOOL_CONSENT`) are logged at WARNING once.

---

## 7. TESTS THAT DEFINE THE CONTRACT

### 7.1 Inventory (files touching ackermann / rosbridge / ros / rtps)

`tests/mesh/`: `test_ackermann_robot.py` (468), `test_ackermann_command_gate.py` (363), `test_ros_bridge.py` (201),
`test_ros_bridge_command_gate.py` (322), `test_rosbridge_robot.py` (185), `test_rosbridge_robot_command_gate.py`
(406), `test_rtps_robot.py` (105), `test_rtps_robot_command_gate.py` (369), `test_mobile_base.py` (724),
`test_mobile_base_hint_describes_its_own_seam.py`, `test_drive_command_guards.py`,
`test_drive_command_numeric_domains.py` (342), `test_drive_contract_fleet_scope.py` (450),
`test_drive_reports_a_refused_trailing_stop.py` (300), `test_bridge_stop_tool_parity.py` (284),
`test_bridge_read_timeout_domain.py`, `test_navigation_goal_guards.py`,
`test_a_bridge_forwards_what_its_transport_accepts.py`, `_transport_stand_in.py`.
`tests/drivers/`: `test_ros_mobile_bases_live_in_drivers.py` (58), `test_yahboom_m3pro_driver.py`,
`test_native_driver_named_when_lerobot_has_no_type.py`.
`tests/tools/`: `test_use_ros.py`, `test_use_rosbridge.py`, `test_use_rtps.py`, `test_rosbridge_host_domain.py`,
`test_rosbridge_port_type_identity.py`, `test_rosbridge_required_args_are_refused_before_the_dial.py`,
`test_rosbridge_transport_port_limit.py`, `test_transport_numeric_option_guards.py`,
`test_transport_refusal_names_its_parameter.py`, `test_tool_wait_budgets_survive_a_clock_step.py`,
`test_agent_tool_parameter_descriptions.py`, `test_tools_lazy_import.py`.
`tests/rtps/`: `test_mangling.py`, `test_idl_bundle.py`, `test_indistinguishability_claims_name_the_graph_metadata.py`.
`tests/` root: `test_every_ros_transport_consults_the_command_gate.py` (496),
`test_examples_never_report_a_refused_command.py` (215), `test_use_ros_command_blocklist.py` (890),
`test_use_ros_showcase_exercises_every_action.py`, `test_hardware_ros_bridge.py`, `test_hardware_rtps_bridge.py`,
`test_ros_telemetry_command_surface_security.py`, `test_ros_telemetry_topic_parity.py`,
`test_ros_telemetry_topics_are_names_ros2_allows.py`, `test_ros_qos_history_depth_domain.py`,
`test_ros2_command_surface_flag_domain.py`, `test_ros2_bridge_flag_is_graded_before_the_dependency_probe.py`,
`test_inbound_command_costs_one_message.py`, `test_inbound_command_refuses_a_non_finite_position.py`,
`test_dds_domain_id_domain.py`, `test_command_gate_headless_refusal_names_the_value.py`,
`test_command_gate_interrupt_carries_its_own_remedy.py`, `test_hitl_operator_response_audit.py`,
`test_rclpy_refusal_cells_establish_the_absence.py`, `test_docs_rtps_bridge_fences_start_without_a_security_config.py`,
`test_repr_survives_partial_construction.py`, `test_import_layers_are_a_dag.py`.
`tests/simulation/test_ros_sim_bridge.py`, `tests/foxglove/test_the_foxglove_bridge_publishes_and_stays_read_only.py`.

### 7.2 `tests/mesh/test_ackermann_robot.py` - behaviours asserted

Bicycle model (`:27-77`): straight full speed -> `(0.0, 1.0)`; rest and `5e-4` -> `(0.0, 0.0)`; left turn at
`(1.0, 2.0)` -> `angle = atan2(0.164*2, 1)/0.5236`, `throttle = 1/1.5`, positive = left; right turn negative;
steering clamps to `+-1.0`; throttle clamps at `+-1.0` past `max_speed`; reversing mirrors the angle.
Construction (`:105-145`): invalid names refused (`servo_topic`, `node_name`, `init_services service`); missing
`type` in an init service refused at construction; non-positive `wheelbase_m/max_speed/max_steering_rad/
max_duration/publish_rate` refused; `from_deepracer` wiring pinned exactly (servo `/webserver_pkg/manual_drive`,
type `deepracer_interfaces_pkg/msg/ServoCtrlMsg`, scan `/rplidar_ros/scan`, 0.164, 1.5, 0.5236, 20.0 Hz, the two
handshake calls); overrides respected. Enable (`:149-187`): in order, idempotent, failure surfaces without latching,
no services -> success. Stop/scan (`:190-219`): stop publishes zero without enable; scan errors without topic;
scan forwards an echo. Drive (`:222-436`): converts and publishes; runs enable first and once; aborts when enable
fails; rejects overlong duration (before enable); clamps linear to `max_speed`; duration publishes `n` then one
trailing zero; trailing zero is sent even when the publish errors; a failed trailing halt is reported instead of
the publish success; both failing reports the drive failure; single-shot success is not reinterpreted; a sustained
zero command has no trailing zero; non-finite inputs refused; non-positive duration refused; a short duration still
gets its trailing zero; the five `_REST_SUBSTITUTIONS` rows are refused ("cannot turn in place" /
"below the rest threshold") with no transport call; `drive(0,0)` and `drive(1,1)` still go out. Tools (`:438-466`):
names `drive_<s>`, `stop_<s>`, conditional `get_scan_<s>`; description states the turning radius; tools forward to
the instance; exported from `strands_robots.mesh` (deprecated alias).

### 7.3 `tests/mesh/test_ackermann_command_gate.py` - the gate contract (see 4.6 for the per-case list)

Four classes: `TestBridgeCommandsReachTheGate` (`:106-227`), `TestCommandToolsDeclareTheOperatorContext`
(`:230-306`: every command tool is `context=True` and forwards `tool_context`; read tools stay contextless; every
`ros_action(... gate=_operator_gate(tool_context))` call site builds its gate from the context; `tool_context` is
not in the input schema), `TestTheCommandedSurfacesAreBlocklisted` (`:308-330`: every shipped surface matches the
blocklist; the bare entries `/manual_drive`, `/vehicle_state`, `/enable_state` exist),
`TestEveryCommandingMeshBridgeHasAGateSuite` (`:332-363`: AST scan of `drivers/ros/*.py` for `ros_action(action=
"publish"|"service_call"|"action_send_goal")` must equal `_GATE_SUITES = {"ros_bridge.py": ..., "ackermann_robot.py": ...}`).
**A new DeepRacer module under `drivers/ros/` that calls `ros_action` with a command verb fails this test until it
is added to `_GATE_SUITES` with its own `tests/mesh/test_<name>_command_gate.py`.**

### 7.4 `tests/mesh/test_rosbridge_robot.py`

Invalid names/host/port refused; non-positive or nan limits refused; `from_curiosity` wiring pinned; drive forwards a
clamped Twist; rejects non-finite and bad durations; duration -> `n` then trailing zero; short duration still trails;
trailing zero even when publish errors; sustained zero has none; stop publishes zero; `get_pose` echoes odom;
`get_scan` conditional; tool names and conditionals; description discloses latch and limits; tools forward (`:33-185`).

### 7.5 `tests/mesh/test_drive_command_numeric_domains.py`

Over `_TRANSPORTS` (RosBridgedRobot, RtpsRobot, RosbridgeRobot, AckermannRosRobot): every bridge refuses each
unusable `linear/angular/duration/count` value **for the same reason text** as the shared guard (`:126-150`);
unusable limits are refused at construction (`:152-171`); a usable command publishes the expected wire fields -
Twist `{"linear":{"x":0.5},"angular":{"z":-0.25}}` or servo `{"angle": -0.15626, "throttle": 0.3333}` (`:173-190`);
a non-numeric value does not escape the bound agent tool (`:192-211`); a refused command leaves the trailing-stop
rule intact (`:213-281`); structural: the drive-owning bridges are the expected ones (`:283-300`), each calls the
shared domain helpers (`:302-312`), no bridge tests finiteness inline (`:314-327`), and the guard detects a hand-rolled
bridge (`:329-342`).

### 7.6 `tests/test_every_ros_transport_consults_the_command_gate.py`

`TestEveryTransportRefusesTheSameSurface` (`:111-186`): declined -> refused on every transport; a blocked publish is
refused without any context; `/robot_a/cmd_vel` is gated on every transport; headless fails closed naming both env
vars; the allowlist pre-approves on every transport; an unblocked surface is never gated.
`TestReadingIsNeverGated` (`:188-212`): reads never prompt; RTPS `advertise` not gated.
`TestTheGateRunsAfterArgumentValidation` (`:215-257`): a missing type is reported without asking.
`TestEveryCallerOfOneTransportAsksTheSameQuestion` (`:259-340`): the transport refuses to command without a `gate`
argument (TypeError); a robot and the tool prompt identically (same interrupt id and reason).
`TestEveryCommandingTransportConsultsTheGate` (`:342-410`): AST scan finds the three transports, each consults
`gate_command`, each commanding tool accepts `tool_context`, the gate has exactly one owner.
`TestNoOperatorIsAskedUnderTheTransportLock` (`:416-496`): the lock is free while the operator is asked; no gate
call sits inside a `with lock:` block.

### 7.7 `tests/test_examples_never_report_a_refused_command.py`

`DEMOS = [rtps_turtle_demo.py (RtpsRobot, "done - the turtle should have moved"), turtlebot_demo.py
(RosBridgedRobot, "after: ")]`; `AGENT_DEMOS = [rosbridge/curiosity_agent.py (RosbridgeRobot, "Agent completed"),
ros2/deepracer_agent.py (AckermannRosRobot, "Agent completed")]` (`:118-125`). Each script is run with `runpy`
against a stubbed bridge class / stubbed `strands.Agent`: a refused command raises and the claim is not printed
(`:165-175`); an accepted one still reports (`:177-186`); a paused agent run (`stop_reason == "interrupt"`) raises
carrying the remedy line (`:188-199`); a finished run still reports (`:201-210`); each demo documents the exact
`STRANDS_ROS2_COMMAND_ALLOW` value its own gate needs (`:212-215`). **A new DeepRacer example must follow this
pattern** (`if result.stop_reason == "interrupt": raise RuntimeError(...)`, and document the pre-approval line).

### 7.8 Other key suites, one line each

* `test_ros_bridge.py`: `from_ros` == constructor; invalid names; Twist mapping; duration -> count; stop; pose/scan;
  per-instance tool names; drive and stop always paired; `navigate_to` forwards a goal / errors without `nav_action`.
* `test_mobile_base.py` (724): the whole base contract on a fake transport, then re-run on the real shipped classes
  (`:503-...`): `positive_finite` is the shared domain; unset limits mean unbounded; `cmd_vel_type` defaults to the
  transport flavour; `supports`; `init_services` refused on a service-less transport; NaN/inf/duration/count refusals;
  numpy scalars accepted; clamp; `n`; handshake order/latch/abort; stop never gated on handshake; trailing zero rules;
  `_cmd_fields` is the single kinematics override point; `lateral` reserved; tools reflect wiring.
* `test_drive_contract_fleet_scope.py`: three-way scope split (fleet-wide / shared / bridge-only), measured over every
  drive-owning class; docstring must name every other carrier of a scoped guarantee.
* `test_bridge_stop_tool_parity.py`: every bridge exposing `drive_*` exposes `stop_*`; a drive without duration
  publishes one latching command.
* `test_use_ros_command_blocklist.py` (890): blocklist matching, canonical spellings, `gate_command` outcomes,
  every verb consults the gate, gate after argument validation, blocklist documented where operators look
  (`:458`), the documented exemptions are real (`:651-...`), the gate never receives the payload and a halt is refused
  exactly like a full-speed drive (`:713-...`).
* `test_ros_mobile_bases_live_in_drivers.py`: old `strands_robots.mesh.<stem>` resolves with a DeprecationWarning
  and keeps the driver module's spec.
* `test_hardware_ros_bridge.py`: symmetric with `SimRosBridge`; `publish_ros_observation`; no rclpy -> clear ImportError.

---

## 8. MESH / FLEET

### 8.1 What the mesh is (`strands_robots/mesh/__init__.py`, `docs/learn/mesh/*`)

`init_mesh(robot, peer_id=None, peer_type="robot", mesh=True) -> Mesh | None` (`mesh/core.py`, read in this study):
`STRANDS_MESH=false` is a hard kill switch; `peer_id` must match `^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,127}\Z` and not be
`broadcast`/`safety`; starts the `Mesh`, then best-effort IoT shadow/camera-offload enrichment. The `Mesh` publishes
presence at 2 Hz on `strands/<peer>/presence`, state at 10 Hz, answers RPC on `strands/<peer>/cmd` with replies on
`strands/<me>/response/<target>/<turn_id>` (`docs/learn/mesh/fleet.md:24-47`). Command vocabulary (`ALLOWED_ACTIONS`,
`mesh/security.py:487`; table at `fleet.md:32-41`): `status`, `state`, `features`, `execute`, `start`, `step`,
`reset`, `set_joints`, `call`, `describe_tool`, `stop`, `teleop_status`, `teleop_receive`, `teleop_stop`, `resume`.
`WIRE_MOTION_ACTIONS = PHYSICAL_MOTION_ACTIONS` (`mesh/core.py:128`) are gated on the receiving side
(`_dispatch :3234-3265`, `_wire_motion_refusal`). `Mesh.send(target, cmd, timeout=30.0)` (`core.py:4669`),
`tell`, `broadcast`, `emergency_stop`, `resume`. Caps: commands 20 Hz / 16 KiB, safety 2 Hz / 4 KiB, camera 1 MiB
(`docs/learn/mesh/index.md:78-80`).

### 8.2 How a DeepRacer would join a mesh today

There is no shipped path. `init_mesh(obj, peer_id=)` "attaches one to anything with `send_action` and `stop`"
(`docs/learn/mesh/index.md:56`), and the mesh reads joints through `bus_access.joint_read_source` (a `bus` with
`sync_read` or a `get_observation`) and sensors through `getattr(robot, "_pose"|"_imu"|"_battery"|"_lidar_state")`
(`drivers/base.py:14-33`). `AckermannRosRobot` has none of `send_action`, `stop_task`, `get_observation`, `_lidar_state`,
so it cannot be a mesh peer as-is; the docs sentence "answering `status`, `execute` and `stop` next to the arms"
(`docs/learn/ros2.md:79`) describes a `Robot(mode="real")` whose driver is ROS-backed (the Yahboom pattern), not the
mobile-base classes. Two viable routes:

1. Write a `HardwareDriver` (`DeepRacerDriver`) registered via `register_native_driver("deepracer", ...)`
   (`drivers/registry.py:111`) with a registry entry `hardware.driver = "strands"`; then `Robot("deepracer",
   mode="real", driver="strands", port=..., mesh=True, peer_id="deepracer-01")` publishes presence/state and answers
   `execute/stop` through the mesh (`Robot` factory, `strands_robots/robot.py:636-...`; `_build_native_driver :421`).
   The mesh publishes `lidar` if the driver exposes `_lidar_state`, `odom`/`pose` if `_pose`.
2. Wrap the `AckermannRosRobot` in a small object exposing `send_action({"linear.x":..,"angular.z":..})`,
   `stop()`, `get_observation()` and hand it to `init_mesh`.

Bridges: `STRANDS_MESH_BACKEND=bridge` puts `presence/cmd/response/safety/*` on AWS IoT Core while `odom/lidar/
camera/state` stay on the LAN (`docs/learn/mesh/bridges.md:33-37`). Audit: every operator verdict, e-stop, resume
and refusal is a JSONL row in `~/.strands_robots/mesh_audit.jsonl`, HMAC-signed with `STRANDS_MESH_AUDIT_PSK`;
`verify_audit_integrity(records)` (AGENTS.md rule 16). E-stop: `emergency_stop()` stops the local robot, broadcasts
`{"action": "stop"}`, publishes `strands/safety/estop` and locks the fleet until a signed `resume`
(`docs/learn/mesh/safety-and-estop.md:21-31`).

The agent-side tool for the fleet is `robot_mesh(action, target=, instruction=, command=, policy_provider=,
duration=, timeout=, name=, limit=, function=)` with actions `peers, status, tell, send, ping, rpc, broadcast, stop,
emergency_stop, subscribe, unsubscribe, watch, inbox`; six are HITL-gated by default (`STRANDS_MESH_HITL_ACTIONS`)
(`docs/learn/mesh/fleet.md:59-63`).

---

## 9. DASHBOARD + VOICE

### 9.1 Package shape

`strands_robots/dashboard/` is a FastAPI + uvicorn + WebAuthn app behind `require_optionals(["fastapi","uvicorn",
"webauthn","jwt"], extra="dashboard")` (`dashboard/__init__.py:35-40`). `server.create_app()` wires one router per
concern (`routes_auth, routes_mesh, fleet, routes_sim, routes_agent, routes_devices, routes_record, routes_train,
routes_config, routes_env, routes_consent, routes_voice`) (`dashboard/server.py:231-247`); the built React SPA ships
under `dashboard/static/` (`server.py:21-24`). The process joins the Zenoh mesh as a robot-less gateway through
`dashboard/mesh_bridge.py` (`MeshBridge :771`, `route_task_target :556`, `stop_outcome :634`).
CLI: `strands-robots dashboard --open` (port 8090) (`strands_robots/__main__.py:7`, `docs/learn/dashboard.md:9-13`).

### 9.2 `dashboard/agent_hitl.py` - the browser motion gate (255 lines)

`MotionInterruptHook(HookProvider)` (`:171-255`) registers on `BeforeToolCallEvent`/`AfterToolCallEvent` (`:194-197`).
`MOTION_ACTIONS = {"fleet": {"task"}, "pose_tool": {...}, "serial_tool": {...}}` (`:36-56`); `robot_mesh` and the
hardware `Robot` tool are deliberately absent because they raise their own interrupt / spend a grant.
`motion_intent(...)` (`:81-148`) returns the interrupt reason when the action is a motion verb, the target is physical
(`agent_motion.peer_is_physical`) and `STRANDS_DASH_AGENT_PHYSICAL_MOTION` is not granted. `_gate` raises
`event.interrupt("physical_motion", reason=...)`, audits via `log_operator_response("dashboard_agent_hitl", ...)`,
deposits a grant on yes (`deposit_grant(name, tool_input, actor=...)`) or sets `event.cancel_tool` to a flat
sentence on no (`:204-239`). `response_approves` accepts bool, `{"approve": ...}`, or `y|yes|approve|approved|1|true|on`
(`:151-159`). `dashboard/agent_motion.py`: `MOTION_ENV = "STRANDS_DASH_AGENT_PHYSICAL_MOTION"`, `GATED_ACTIONS =
PHYSICAL_MOTION_ACTIONS | {"task"}` (`:24-31`), `peer_is_physical` (`:68`), `agent_motion_allowed` (`:109`).

### 9.3 `dashboard/voice.py` - the speech-to-speech console (383 lines), read in full

* Module docstring: "browser mic <-> Strands bidi agent. PCM16 audio flows over /ws/voice (binary in, base64 JSON out)" (`:1-3`).
* `VOICE_PROMPT` (`:17-29`): the voice agent "control[s] real robots and simulations on a mesh via the fleet tool",
  keeps replies to one or two sentences, must confirm before actuating real hardware, and is told a refusal to start
  motion on a REAL robot is final ("A spoken yes cannot grant it - only their tap can"); stopping is never refused.
* `_DEFAULT_VOICES = {"openai": "marin", "nova_sonic": "tiffany"}` (`:31`);
  `_DEFAULT_MODEL_IDS = {"openai": "gpt-realtime", "nova_sonic": "amazon.nova-2-sonic-v1:0"}` (`:158`);
  `BROWSER_INPUT_RATE = 16000` (`:161`).
* Refusal listeners (`:34-51`) let the fleet tool's refusals be spoken once and turned into `needs_consent` frames.
* `make_fleet_tool(bridge)` (`:54-154`): the ONE tool the voice agent holds, `@tool fleet(action, target="",
  instruction="", policy_provider="mock", duration=15.0, robot_name="")` with actions `peers` (snapshot of live
  peers: type, hw_connected, cameras, joints, task), `task` (checks `agent_motion_allowed("task", peer, target)`
  and FAILS CLOSED for physical peers because "bidi cannot pause on an interrupt"; otherwise
  `bridge.send_cmd(target, {"action":"execute","instruction",...,"duration"}, timeout=duration+30, source="voice")`),
  `stop`, `stop_all` (fan-out `{"action":"stop"}` to every non-stale peer), `status`.
* `_build_bidi_model(provider, voice)` (`:164-194`): `nova_sonic|novasonic|nova` -> `strands.bidi.models.bedrock.
  BedrockNovaSonicModel(model_id=VOICE_MODEL or default, region=AWS_REGION or us-east-1, voice=...)`;
  `openai|openai_realtime` -> `strands.bidi.models.openai.OpenAIRealtimeModel(model_id, transcription_model_id=None,
  voice, api_key=OPENAI_API_KEY)`; Gemini Live is refused because google-genai caps websockets < 17 (`:192-194`).
* `_resample_pcm16(data, src_rate, dst_rate)` (`:197-207`): linear `np.interp` resample of mono int16.
* `stop_conversation` `@tool(context=True)` (`:210-219`): the console's own replacement for the SDK tool strands
  1.57.2 removed; calls `tool_context.agent.cancel()`.
* `build_voice_agent(provider=None, voice=None, *, bridge=None)` (`:222-252`): `BidiAgent(model=..., tools=[fleet,
  stop_conversation], system_prompt=DASHBOARD_VOICE_PROMPT or VOICE_PROMPT)`; provider from `VOICE_PROVIDER`
  (default `openai`), voice from `VOICE_NAME`. Deliberately NO `robot_mesh` and NO `os.environ` writes (an earlier
  version set `STRANDS_MESH_HITL_ACTIONS="none"` process-wide, disarming the chat agent's gate) (`:225-241`).
* `run_voice_session(ws, *, bridge=None)` (`:255-383`): the audio pipeline. Input `_BrowserInput` reads the model's
  `get_audio_config()["input"]["sample_rate"]`, pulls browser PCM16 frames from an `asyncio.Queue`, resamples
  16 kHz -> model rate and yields `AudioDelta(format="pcm", source={"bytes": ...})` (`:305-320`). Output
  `_BrowserOutput` sends `{"type":"voice_meta","rate": <output sample rate>}` on start, forwards events whose type
  starts with `bidi_audio` as `{"type":"audio","data": <base64>}` and `bidi_transcript` as
  `{"type":"transcript","role","text"}` (reads `delta` or legacy `text`) (`:322-342`). Tasks: `_reader` (binary ->
  queue; text `{"type":"stop"}` ends), `_drain_needs` (consent frames), and `agent.run(inputs=[_BrowserInput()],
  outputs=[_BrowserOutput()])`; everything is cancelled and the refusal listener unregistered in `finally`
  (`:354-383`). Event types are matched by string prefix because the bidi event vocabulary is experimental (`:263-275`).
* `routes_voice.py` (`:34-71`): `@router.websocket("/ws/voice")`; admission via `access.admit_socket`; probes
  `import strands.bidi` and refuses with code 4503 naming `strands-robots[voice] plus a voice provider key
  (OPENAI_API_KEY, or AWS credentials for nova_sonic)`; strangers closed with 4401; the credential is re-checked
  while the conversation runs.
* How it connects to a robot: only through the dashboard `MeshBridge` (`ws.app.state.bridge`, `routes_voice.py:54`) ->
  `bridge.send_cmd(peer_id, {"action": "execute"|"stop"|"status"})` over Zenoh/IoT. There is no direct robot or ROS
  handle in the voice path, and a physical peer can never be started by voice (fail-closed), only stopped.

### 9.4 The four voice-related fragments

* `changelog.d/4456-voice-console-on-strands-bidi.md` - "### Fixed: the dashboard voice console works on
  strands-agents 1.57.2": 1.57.2 moved the bidirectional agent from `strands.experimental.bidi` to `strands.bidi`
  and removed `stop_conversation`; the console now imports `strands.bidi`, ships its own `stop_conversation` via
  `BidiAgent.cancel()`, and the `strands-agents` floor (core, `[ollama]`, `[voice]`) is 1.57.2.
* `changelog.d/2988-g1-bidi-audio-dependencies-port.md` - adds read-only tools
  `strands_robots.tools.g1.g1_list_bidi_audio_dependencies` / `g1_bidi_audio_dependency_admits` snapshotting the
  three import names neon-the-g1's `g1_speak` probes: `pywebrtc_audio` (AEC front-end), `pyaudio` (PortAudio mic),
  `strands.experimental.bidi` (BidiAgent); roles `aec_frontend`, `mic_capture`, `bidi_agent`; refusal code `7404`.
* `changelog.d/2998-g1-speak-vad-envelope-port.md` - `g1_speak_vad_envelope`: `vad_threshold` clamp `[0.0, 1.0]`
  (neon default `0.7`), `silence_duration_ms >= 1` (default `700`); read-only.
* `changelog.d/2999-g1-bidi-audio-sample-rates-port.md` - `g1_bidi_audio_sample_rates`: `MIC_RATE = 16000`,
  `G1_RATE = 16000` (DDS chest speaker on `rt/audio_stream`), `OPENAI_RATE = 24000`; the BidiAgent upsamples to the
  endpoint rate and downsamples back.
  (These three are G1-specific lookups under `strands_robots/tools/g1/`, not used by the dashboard console.)

---

## 10. DEPENDENCIES AND INSTALL

### 10.1 `pyproject.toml` essentials

* Build: `hatchling<1.32` + `hatch-vcs`; version from git tags matching `v[0-9]*` (`pyproject.toml:1-6`, `:884-893`).
* `requires-python = ">=3.12"` (`:13`); classifiers 3.12 and 3.13.
* Core deps (`:40-86`): `strands-agents>=1.57.2,<2.0.0`, `numpy>=1.21.0,<3.0.0`, `opencv-python-headless>=4.5.0,<5.0.0`,
  `Pillow>=12.3.0,<13.0.0`. The strands floor comment (`:41-77`) explains it is a *capability* floor: `ToolContext`
  (1.5.0), `ToolResultEvent` (1.7.0), `BeforeToolCallEvent.interrupt` (1.13.0), and finally `strands.bidi.BidiAgent`,
  `strands.bidi.models.bedrock.BedrockNovaSonicModel`, `strands.bidi.models.openai.OpenAIRealtimeModel`,
  `strands.bidi.types.media.AudioDelta` first shipping in 1.57.2 - "which is what sets this floor"; measured by
  `tests/test_strands_agents_floor_ships_the_imported_api.py`.
* Extras relevant here (`:88-873`):
  * `ros2 = ["cyclonedds>=0.10.2,<12"]` (`:740`): pip-installable DDS binding only; `rclpy`/`rosidl_runtime_py` are
    NOT on PyPI and must come from a sourced distro (apt / RoboStack / conda) (`:719-739`); wheels exist for macOS,
    Windows, Linux x86_64; Linux aarch64 (Jetson, i.e. the DeepRacer's Intel Atom is x86_64 but a Jetson-based car is
    not) builds the sdist against `CYCLONEDDS_HOME`.
  * `rosbridge = ["roslibpy>=1.7.0,<2.0.0"]` (`:777`): pure pip, no ROS install.
  * `voice = ["strands-agents[bidi]>=1.57.2,<2.0.0"]` (`:825-826`): not in `[all]` because `[bidi]` pins `awscrt`
    differently from `[mesh-iot]`'s `awsiotsdk` (`:813-824`, `[tool.uv] conflicts :944-951`).
  * `dashboard = [fastapi>=0.110,<1.0, uvicorn[standard]>=0.27,<1.0, webauthn>=2.0,<4.0, python-multipart, PyJWT>=2.0,<3.0,
    strands-robots[serial], opencv-python-headless>=4.8, huggingface_hub>=1.5,<2.0.0]` (`:799-811`).
  * `mesh` (`:687`), `mesh-iot = [strands-robots[mesh], awsiotsdk>=1.21.0, awscrt>=0.20.0, boto3/botocore>=1.43.17]`,
    `device-connect`, `ollama = ["strands-agents[ollama]>=1.57.2,<2.0.0"]` (`:747`), `foxglove`, `inference`
    (`websockets>=17.1`), `sagemaker`, `serial` (`:365`), `earthrover`, `all` (`:828-858`, includes `rosbridge`,
    `mesh`, `mesh-iot`, `dashboard`, `ollama`; `voice` is excluded for the awscrt conflict and `ros2` is also NOT a member, so `pip install strands-robots[all]` does not install cyclonedds),
    `dev = [pytest, pytest-cov, ruff>=0.15.12,<0.16.0, mypy, pytest-timeout, pytest-xdist]` (`:860-871`).
  * `[tool.uv] constraint-dependencies` security floors include `twisted>=26.4.0` (under roslibpy), `cbor2`, `ujson`,
    `pyopenssl>=26.0.0`, `anyio>=4.14.2`, `gitpython`, with GHSA ids (`:971-1030`).
* `[project.scripts] strands-robots = "strands_robots.__main__:main"` (`:874-875`); commands `doctor`,
  `verify-dataset`, `dashboard`, `iot` (`strands_robots/__main__.py:7`).
* mypy ignores `rclpy.*`, `cyclonedds.*`, `roslibpy.*`, `rosidl_runtime_py.*`, `geometry_msgs.*` (`:1217`).
* pytest: `addopts = "-v --cov=strands_robots --cov-report=term-missing --cov-fail-under=80 --strict-markers --timeout=120"`,
  markers incl. `rtps: requires cyclonedds ([ros2] extra) + a live ROS 2 peer ... RTPS_LIVE=1 pytest -m rtps`,
  `hardware: ... STRANDS_HW_PORT=/dev/tty...` (`:1337-1363`).

### 10.2 Install recipes

```bash
# agent laptop, no ROS: rosbridge transport
pip install "strands-robots[rosbridge]" strands-agents
# agent laptop, no ROS: raw RTPS participant (x86_64/macOS wheel)
pip install "strands-robots[ros2]"
# on the car / a ROS workstation: rclpy transport
source /opt/ros/<distro>/setup.bash && pip install strands-robots strands-agents   # rclpy from the distro
# container recipe used by the examples
docker run -it --rm --net host ros:jazzy bash
apt-get update && apt-get install -y ros-jazzy-turtlesim python3-pip
pip install "strands-robots[ros2]" strands-agents --break-system-packages
source /opt/ros/jazzy/setup.bash                                              # examples/ros2/turtlebot_demo.py:15-24
# dashboard + voice (separate env from mesh-iot)
pip install "strands-robots[dashboard,voice]"; export VOICE_PROVIDER=nova_sonic AWS_REGION=us-east-1
```
The DeepRacer runs ROS 2 Foxy on Ubuntu 20.04 (Python 3.8) on the stock image; `requires-python>=3.12` means the
agent process cannot run inside the stock distro's Python - run the agent off-car over `use_rosbridge`/`RosbridgeRobot`
(after installing `rosbridge_server` + `rosapi` on the car), or over `use_rtps` (needs `ServoCtrlMsg` in the IDL
bundle, see section 12), or on-car in a separate Python 3.12 that can import the distro's `rclpy` (version-matched
build required).

### 10.3 Developer commands

* `pip install -e ".[all,dev]" hatch` (`AGENTS.md:51`); hatch uses uv (`installer = "uv"`, `pyproject.toml:899`).
* `hatch run test` -> `python scripts/select_tests.py -n logical --maxprocesses=2 --dist loadfile {args:tests}`
  (`pyproject.toml:1134`); on a PR it selects the test files that name the changed modules + the whole-tree graders
  (`scripts/select_tests.py:1-33`).
* `hatch run test-integ`, `hatch run lint` (ruff check, ruff format --check, mypy), `hatch run format`,
  `hatch run whole-tree-check` (`scripts/check_whole_tree_graders.py`, roster derived from the tree) (`:1135-1146`).
* Changelog: `python scripts/assemble_changelog.py --check|--print|--apply`.
* Docs: `mkdocs build --strict` with the hooks at `mkdocs.yml:80-94`; `python3 docs/hooks/check_fences.py`,
  `check_sketches.py`, `check_mermaid.py`, `word_budget.py` (900 words/page).

---

## 11. RECENT HISTORY

### 11.1 `git log --oneline -60` (main @ d504fedd)

The last ~25 commits (#4703-#4728, 2026-10-09..12) are the "refusal table" test consolidation series
("domain suites check every facet of one value in one cell, not in N cells"), plus CI selection (#4698), parse-once
graders (#4695-4703). Before them: `debdcbbf fix(sim): send_action names the vector entry that is not a number
(#4689)`, `c3135304 fix(drivers): pip install 'strands-robots[stretch]' installs the Stretch SDK (#4688)`,
`ec924220 docs: highlighted code, a layer map without line counts ... (#4676)`, `c8a9b837 fix(docs): the drivers page
pays for its not-connected sentence, so the site is back under its word ceiling (#4690)`, `c8aa4023 fix(mesh): a
peer's identity is the certificate that signed its message, and approvals name their actor (#4623)`,
`c0ce919f fix(core): import strands_robots survives a find_spec("mujoco") that raises (#4675)`, `e26d92a5
feat(simulation): run_multi_policy takes fast_mode (#4672)` = `v0.5.3` (2026-10-07).

### 11.2 ROS-path history (`git log --oneline -- strands_robots/drivers/ros strands_robots/rosbridge.py
strands_robots/ros.py strands_robots/tools/use_ros.py strands_robots/tools/use_rosbridge.py examples/ros2
examples/rosbridge strands_robots/mesh/{_mobile_base,ackermann_robot,rosbridge_robot}.py`), newest first

```
c2fa03cc fix(sim): the ROS 2 bridge publishes only the cameras a robot carries, not the overview view (#4473)
ee80304c refactor(drivers): the ROS 2 mobile bases move from mesh to strands_robots.drivers.ros (#4140)
75182436 docs: the site rewritten from the tree, with a MuJoCo viewer on every robot page (#4112)
2cf97614 docs(site): the nav carries the lane a reader browses, reference/ carries the contracts (#4092)
92a67e1a fix(examples): an agent demo raises the run the command gate paused (#4064)
8e790df0 fix(examples): the use_ros showcase drives the action-client verbs it claims (#4061)
58211bbf fix(examples): a cmd_vel demo raises the refusal the command gate returned (#4056)
c0bb37ef docs(rtps): the indistinguishability claim names the graph metadata a node sees (#4054)
c09bc32f docs(rosbridge): the rosbridge page keeps the tool, driving a robot gets its own (#4038)
2f2f8186 fix(ros): no operator is asked while the rclpy transport lock is held (#3883)
a128e625 refactor(ros): the rclpy transport lives below both robots that publish through it (#3873)
fbec1c7c refactor(rosbridge): the transport lives below both callers that dial through it (#3871)
cb839cd6 refactor(core): the operator gate lives below every caller that asks a human (#3854)
71060604 docs(ros2): the [ros2] extra names the Linux aarch64 route instead of promising a wheel (#3782)
1025ab94 fix(tools): use_rosbridge refuses a missing name before the dial (#3682)
0b93bc2a fix(tools/use_rosbridge): list_topics reports every topic rosapi named (#3651)
98837609 fix(mesh/ackermann): a yaw asked for at rest is refused, not sent as a halt (#3541)
8bee2206 fix(rosbridge): the host half of a dialled address is graded before a pattern is offered it (#3279)
60dd6d88 fix(validation): an allowlist anchors at the absolute end of the string (#3174)
664b2313 fix(mesh): report a timed drive whose trailing stop was refused (#2839)
22d3c4c7 fix(tools): name the parameter a rosbridge port refusal was given (#2764)
eb378603 fix(mesh): describe the grammar that refused a name, per seam (#2758)
1c05394e fix(mesh): let a RosbridgeRobot command carry an operator decision (#2705)
19d4588b refactor(mesh): MobileBaseRobot + Transport - one drive contract for every transport (#2696)
e3ff18dd fix(mesh): name every class that carries a scoped drive limit (#2700)
3a4c6078 feat(mesh): AckermannRosRobot - Ackermann ROS 2 cars (AWS DeepRacer) as strands robots (#2689)
c1efac8d security(tools): gate every ROS 2 transport's commands, not just use_ros (#2693)
22316477 fix(tools): record the operator's HITL reply at every gate, not only the mesh one (#2535)
c3b61d12 docs(use_ros): state the reach a command pre-approval actually has (#2522)
7f670342 fix(mesh): scope the drive guarantees each bridge actually keeps (#2445)
5ad45efe fix(tools): measure a published wait budget on a clock that cannot step (#2404)
efbc3dbd security(use_ros): gate every verb that can command a robot, not just publish (#2313)
e40c71d1 test(tools): drive the service-name and publish-argument refusals in use_rosbridge (#2214)
93f288c2 fix: __repr__ must not hide the constructor refusal that produced the object (#2130)
c1d8317d fix(tools): normalize a rosbridge port that is an int subclass (#1836)
de4ad991 fix(tools): refuse a rosbridge port the transport cannot address (closes #1822) (#1834)
9b1a62be fix(mesh): share the drive-command numeric domains across every bridge (#1817)
cd71f9f1 fix(tools): refuse a rosbridge numeric option that cannot be honored (#1816)
c038f9f9 feat: rosbridge transport (use_rosbridge + RosbridgeRobot) - NASA Curiosity Gazebo verified live (#1110)
4a3ed9db fix(tools): refuse a numeric transport option use_ros/use_rtps cannot honor (#1720)
735f3323 feat(tools): ROS 2 action support in use_ros + goal-level navigate_to on RosBridgedRobot (#995)
b18e4436 feat(hardware): publish a real robot on a ROS 2 domain (Robot ros2_bridge flag) (#755)
ff06b03f docs(ros2): use_ros showcase example + README/docs ROS 2 overview (#748)
fc5b72b3 feat(sim): publish simulation telemetry on a ROS 2 domain (ros2_bridge flag) (#747)
10af42c9 feat(rtps): use_rtps + RtpsRobot - act as a ROS 2 robot over pure RTPS (no rclpy) (#744)
4a4b8639 feat(mesh): RosBridgedRobot - present a ROS 2 robot as a first-class strands Robot (#742)
```

Other ROS-adjacent commits from the grep (`--grep ackermann|deepracer|rosbridge -i`): `2a4707a1 2026-09-22
feat(drivers): drive the real Yahboom ROSMASTER M3 Pro over its ROS 2 graph (#3941)`, `31b8bedb 2026-09-23
feat(drivers): twin transport - the hardware driver with the model at the far end (Feetech) (#3944)`,
`45b8e8c5 2026-09-22 docs(ros2): split the 5,241-word ROS 2 integration page into six pages (#3938)`,
`fea91fae 2026-09-24 fix(ros_telemetry): a bridge refuses a domain its process cannot be moved to (#3994)`,
`a00962c3 2026-09-14 fix(hardware_ros_bridge): joint_limits is answered before the node exists (#3628)`,
`e059fc5c 2026-08-11 fix(mesh): expose a stop tool on the ROS 2 bridge (#2142)`,
`6c6e4ab3 2026-09-16 fix(tools/_command_gate): a gated command with no operator to ask names the value to set (#3759)`.

### 11.3 Commits authored or co-authored by Vivek (the user)

`git log --author=Vivek` (author field):
```
f7d8a017 2026-09-29 feat(simulation): ManipulationOptional mixin for backends without manipulation (#4270)
d01d382d 2026-09-29 feat(simulation): SimEngine.capabilities() names what a backend supports (#4177)
8773b9fc 2026-09-29 feat(registry): register_robot accepts a robot with no simulation asset (#4232)
b43d96e8 2026-09-28 fix(packaging): ship a py.typed marker so type checkers read the annotations (#4175)
4ae4af4c 2026-09-28 fix(registry): refuse a user-overlay robot key that no lookup can reach (#4176)
5b13bc6a 2026-09-17 feat(dashboard): mesh_bridge slice of #2848 - the signed rail honours the kill switch ... (#2977) (#3205)
9bc17510 2026-09-05 feat(training): FastTD3 - Twin Delayed DDPG as a native off-policy RL provider (#862, #2720) (#3206)
c038f9f9 2026-07-31 feat: rosbridge transport (use_rosbridge + RosbridgeRobot) - NASA Curiosity Gazebo verified live (#1110)
735f3323 2026-07-03 feat(tools): ROS 2 action support in use_ros + goal-level navigate_to on RosBridgedRobot (#995)
```
Plus, for the Ackermann/DeepRacer bridge: PR **#1035** was Vivek's branch (the merge commit `b0f99c33 2026-07-28
Vivek Raja merge: bring branch up to main, move changelog entry to a news fragment` created
`changelog.d/1035-ackermann-ros-robot.md`, and `185c123a 2026-07-31 strands-robots fix(mesh): route AckermannRosRobot
through the shared drive-command domains` landed on it); it was squash-merged by the maintainer as
`3a4c6078 (#2689, 2026-08-24)` with `Co-authored-by: Vivek Raja <vivekraja98@gmail.com>` in the body and the
fragment kept its `1035` number. So Vivek is the origin of: `use_ros` actions + `navigate_to` (#995), the
rosbridge transport + `RosbridgeRobot` (#1110), and the `AckermannRosRobot`/DeepRacer bridge (#1035 -> #2689).

---

## 12. GAPS AND OPPORTUNITIES FOR AN AGENTIC DEEPRACER

What strands-robots gives today: `AckermannRosRobot.from_deepracer()` over rclpy (servo publish on
`/webserver_pkg/manual_drive`, the two-step `/ctrl_pkg/vehicle_state` + `/ctrl_pkg/enable_state` arming handshake,
`/rplidar_ros/scan` read, the operator gate, the trailing-zero contract, three agent tools), the three generic
transports, and a dashboard/voice stack that only speaks to mesh peers. What is missing, where it would plug in,
and which rules bind it:

1. **No rosbridge or RTPS variant of the Ackermann bridge.** `AckermannRosRobot` hard-wires `ros_action`
   (`ackermann_robot.py:73, 300, 422, 452`), so the agent must run where `rclpy` imports - i.e. on the car's
   Python (3.8 on the stock Foxy image, below `requires-python>=3.12`) or a version-matched workstation. The clean
   fix is to make the Ackermann class a `MobileBaseRobot` subclass that overrides `_cmd_fields` with the bicycle model
   (exactly what `_mobile_base.py:24-26, 387-397` reserves the seam for) and takes any `Transport`
   (`_UseRosTransport`, a rosbridge transport, `_RtpsTransport`). Then `AckermannRosRobot.from_deepracer(
   transport="rosbridge", host=<car ip>)` works from a laptop with only `[rosbridge]` installed. Rules: keep the
   rest-command refusal (`_rest_command_error`), the shared numeric domains
   (`tests/mesh/test_drive_command_numeric_domains.py`), `failed_halt_error`, `partial_construction_repr`; add the new
   module to `_GATE_SUITES` with its own gate suite (`tests/mesh/test_ackermann_command_gate.py:48-51`); a rosbridge
   variant needs the ROS1-style two-segment type spelling `deepracer_interfaces_pkg/ServoCtrlMsg` and `ActiveStateSrv`
   / `EnableStateSrv` services (rosbridge_action gates `service_call` too, `rosbridge.py:461-465`).
2. **No DeepRacer messages in the RTPS IDL bundle.** `strands_robots/rtps/idl/__init__.py` carries only
   `geometry_msgs`, `std_msgs/Header`, `builtin_interfaces/Time`, `sensor_msgs/{JointState,Image}`. An RTPS path needs
   `deepracer_interfaces_pkg/msg/ServoCtrlMsg` (`float32 angle, float32 throttle`), and reads need
   `sensor_msgs/msg/LaserScan`, `sensor_msgs/msg/CompressedImage`/`Image` and `deepracer_interfaces_pkg/msg/
   CameraMsg`/`InferResultsArray`. Services (`ActiveStateSrv`, `EnableStateSrv`) are out of RTPS scope v1
   (`rtps/__init__.py:15-17`), so arming over RTPS is impossible until request/reply-over-DDS lands. Rule: register
   in `REGISTRY` under the ROS type string; `tests/rtps/test_idl_bundle.py` and `tests/mesh/test_rtps_robot_command_gate.py:356`
   grade the bundle.
3. **No camera / inference / sensor surface on the Ackermann bridge.** Only `get_scan` exists (`ackermann_robot.py:441`).
   A DeepRacer agent needs `/camera_pkg/video_mjpeg` or `/camera_pkg/display_mjpeg` (`sensor_msgs/Image`),
   `/sensor_fusion_pkg/sensor_msg`, `/inference_pkg/rl_results` (`InferResultsArray`), `/camera_pkg/camera_msg`,
   battery/`/i2c_pkg/battery_level` (`BatteryLevelSrv`), LED `/servo_pkg/set_led_state` / `/led_pkg/...`,
   `/model_optimizer_pkg/model_optimizer`, `/ctrl_pkg/model_state`, `/ctrl_pkg/get_car_cal` / `set_car_cal`
   (calibration), `/ctrl_pkg/get_ctrl_modes`, `/ctrl_pkg/is_model_loading`. Plug-in points: new read methods +
   `_extra_tools()` on the Ackermann class (`_mobile_base.py:604`), each read `never_gated`; image reads should
   return `{"image": base64}` content blocks the way `EarthRoverDriver.capture_frame` does (`earthrover.py:974`),
   not a JSON dump of a `uint8[]`. Any *writing* service (set_led, set_car_cal, model load, `/ctrl_pkg/model_state`)
   must be added bare to `COMMAND_BLOCKLIST` (`_command_gate.py:74-92`) and documented on `docs/learn/ros2.md` (the
   blocklist prose is graded by `tests/test_use_ros_command_blocklist.py:458`).
4. **No DeepRacer webserver HTTP control.** The stock car exposes `https://<car>/api/...` (login, `manual_drive`,
   `start_stop`, `max_nav_throttle`, `models`, `isModelLoading`, `get_battery_level`, `set_led_color`, `calibration`).
   An HTTP driver in the shape of `EarthRoverDriver` (`drivers/earthrover.py`: `requests`, `POST /control`, watchdog
   re-send, best-effort zero on cleanup) would let a laptop drive the car with no ROS at all. It would be a native
   `HardwareDriver` (`drivers/base.py:93-241`), registered through `_SHIPPED_DRIVERS` (`drivers/__init__.py:53-73`)
   with `SUPPORTED_ROBOTS = ("deepracer",)`, gated through `gate_motion(tool="deepracer", action="manual_drive",
   target=<base url>, ..., allow_env="STRANDS_DEEPRACER_COMMAND_ALLOW")` (`_command_gate.py:350`) because its surface is
   not a graph name; its tool parameters need `Args:` entries (AGENTS.md rule 13) and its motion fields must be in
   `DETAIL_FIELDS` if the dashboard hook is to gate it (`_motion_grants.py:127-156`).
5. **No registry entry / native driver, so no `Robot("deepracer", mode="real")`, no mesh peer, no dashboard card,
   no voice control.** `strands_robots/registry/robots.json` has no `deepracer` (76 robots; `earthrover` and
   `yahboom_m3pro` are the mobile precedents). Adding `{"deepracer": {"category": "mobile", "hardware": {"driver":
   "strands"}, "aliases": ["aws_deepracer", "deepracer_evo"]}}` plus a `DeepRacerDriver` (`send_action({"linear.x",
   "angular.z"})`, `stop_task`, `get_observation`, `_lidar_state`, `_battery`, `tool_spec` with an `action` enum like
   Yahboom's `status, sensors, camera, move, stop, led, calibrate`) is what makes `Robot("deepracer", mode="real",
   driver="strands", port="rosbridge-host:9090", mesh=True)` join the mesh, appear in the dashboard Fleet tab, be
   e-stoppable by `emergency_stop()`, and be stoppable by the voice console (`fleet(action="stop")`). Rules: registry
   integrity test (`tests/registry/test_integrity.py`, AGENTS.md:286-291 - an entry with no `asset` block needs no
   auto-download declaration, cf. `earthrover`), driver contract tests (`tests/drivers/test_driver_verbs_accept_the_
   contract_parameter_names.py`, `test_a_native_driver_refuses_a_keyword_it_does_not_read.py`), `reads_cameras = True`
   if it opens cameras, a docs robot page under `docs/robots/` (hooks `robot_pages.py`), and a `docs/learn/hardware/
   deepracer.md` under 900 words.
6. **No odometry / pose on the stock platform, so no `navigate_to`.** `RosBridgedRobot.navigate_to` needs a Nav2
   action server (`ros_bridge.py:279`). A DeepRacer with the community Nav2/SLAM stack (`/odom` from wheel/IMU fusion,
   `/navigate_to_pose`) could use `RosBridgedRobot.from_ros(cmd_vel_topic=..., nav_action="/navigate_to_pose")` only if
   a `cmd_vel -> ServoCtrlMsg` node runs on the car; alternatively give the Ackermann class an optional `odom_topic`
   and `nav_action` (the base already models `odom_topic=None`, `_mobile_base.py:236-239`).
7. **No calibration surface.** The DeepRacer's steering/throttle PWM calibration (`/ctrl_pkg/get_car_cal`,
   `set_car_cal`, `CalibrationMsg`) and `max_speed`/`max_steering_rad` are unrelated today; the bicycle model assumes
   `throttle = v/max_speed` is linear and symmetric. A `calibrate`/`get_calibration` read tool and a `set_calibration`
   gated write (blocklist `/set_car_cal`) belong beside `enable`; the dashboard has a `calibration.py`/`calibration_run.py`
   rail for arms that a car would not reuse.
8. **No mesh bridge example for a ROS car.** `examples/fleet/` and `examples/mesh/` have no ROS robot. An
   `examples/ros2/deepracer_mesh_peer.py` (init_mesh over the driver from item 5, `STRANDS_MESH_LOCAL_DEV=true`,
   `robot_mesh` agent) would be the first; it must follow `tests/test_examples_never_report_a_refused_command.py`
   (raise on `stop_reason == "interrupt"`, document the pre-approval) and AGENTS.md rule 16 for audit attestation.
9. **No decider / vision-in-the-loop integration.** `grep -ri decider` finds nothing in the tree. A perception
   step (camera frame -> VLM/decider -> drive) would be a strands tool beside `drive_deepracer`, or a `Policy` provider
   (`strands_robots/policies`, `create_policy`) consumed by a `DeepRacerDriver.run_policy`; the episode-judge tools
   (`tools/episode_judge.py`) and `harness_memory` are the closest shipped patterns. A policy provider must obey the
   mesh allowlists (`STRANDS_MESH_POLICY_TYPE_ALLOW`, `registry/policies.json`).
10. **Voice teleop cannot start a real robot.** `dashboard/voice.py:54-60` fails closed on physical peers by design
    ("bidi cannot pause on an interrupt"); only `stop`/`stop_all`/`status`/`peers` reach metal. A voice-driven
    DeepRacer would need either a sim twin peer (`robot_type: "sim"`) or a new operator affordance (a pre-granted
    `STRANDS_DASH_AGENT_PHYSICAL_MOTION=1` on the dashboard process, `agent_motion.py:24`) - the latter is a posture
    change the docs must state. Direct ROS tools are not in the voice agent at all.
11. **No DeepRacer sim/twin.** `yahboom_m3pro` has a MuJoCo `twin` transport (`drivers/yahboom_m3pro_twin.py`); there is
    no DeepRacer MJCF in the registry, so the "dry run is `mode="sim"`" posture (`docs/learn/agents.md:93-95`) has no
    car to run against. A registry `asset` (GitHub source, `AGENTS.md:286-291`) plus a twin graph answering
    `/webserver_pkg/manual_drive` would give the agent a rehearsal path.
12. **Docs gap.** DeepRacer is absent from `docs/`; the only operator-facing statement of the pre-approval posture is
    the example docstring (`examples/ros2/deepracer_agent.py:16-22`) and the class docstring. AGENTS.md rule 18 asks
    the posture to be stated in the docs; a `docs/learn/hardware/deepracer.md` (<=900 words, `{{n:...}}` facts, a
    `python title="sketch"` fence that `check_sketches.py` can resolve) is owed with any of the above.
13. **Smaller polish**: `docs/learn/ros2.md:79` and `docs/learn/mesh/bridges.md:71` still say the mobile bases are "in
    `strands_robots.mesh`" (moved in #4140); AGENTS.md rule 18 cites the removed `docs/reference/ros2-integration.md`;
    the RTPS graph shows a bare participant (`ros2 node list` omits it) which matters if DeepRacer tooling waits for a
    node; `MobileBaseRobot._cmd_fields` docstring promises an Ackermann override that no shipped class uses.

Top-5 by leverage for an agentic DeepRacer: (1) transport-agnostic Ackermann bridge (rosbridge from a laptop), (3)
camera/inference/battery/LED read tools, (5) registry entry + `DeepRacerDriver` so the car is a `Robot`, a mesh peer
and a dashboard card, (2) `ServoCtrlMsg`/`LaserScan` in the IDL bundle for a no-ROS laptop path, (11)/(9) a sim
twin and a perception-decider step so the agent can rehearse and see.
