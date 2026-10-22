# Brainstorm: developer-advocate lens

Audience: developers who will go home and `pip install`. The rover is the teaching vehicle;
every demo answers "what is this Strands feature FOR?" Each use case names the one API the
audience should remember, the slide snippet, the rover beat, the screen, and the artefact.
API facts come from docs/context 01, 03, 08. Snippets are illustrative; names flagged
"(verify)" need a check against the installed version before they go on a slide.

## The one distinctive feature per pillar

| Pillar | Distinctive versus competitors | Why a developer cares |
|---|---|---|
| strands-robots | The command gate keys approval on the *physical surface* (`/manual_drive`, `/cmd_vel`) via `tool_context.interrupt`, and every transport (rclpy, rosbridge, RTPS) consults the same gate; HMAC-signed audit row on both outcomes | ROS-native agents publish straight to `cmd_vel`; the prompt is the only safety |
| Agents SDK | `InterventionHandler.before_tool_call` returns a typed verdict: `Proceed / Guide(feedback) / Deny / Confirm`; `Guide` feeds text back into the loop so the model re-plans without a human | LangGraph `interrupt()` pauses a graph node; it has no "steer the model" verdict |
| Harness SDK | `create_harness()` is one call for shell/file/web tools over a *sandbox seam* (local, Docker, SSH), with `interventions=` taking a Cedar path, a natural-language rubric, or any handler, and the gate reaching subagents | Other "coding agent" kits bind tools to the local machine and bolt policy on later |
| Decider | Runtime-labelled classes: you type the options in the request, get a calibrated probability in one forward pass (about 150 ms on a laptop GPU), many questions per state nearly free | A CNN needs a dataset; an LLM judge needs seconds and is not calibrated |
| Bidi | `BidiBargeInEvent` is a first-class hook you can wire to an actuator; I/O streams are any async callable; provider swap is one constructor | OpenAI Realtime treats interruption as audio-buffer housekeeping, one vendor |
| Box | Default-deny Dogwood policy over *semantic* actions (`http:request` path, `shell:exec`), egress gateway injects secrets the agent never sees, temporal rules over shared history | Containers isolate the filesystem; they cannot say "no drive after an abort until a reset" |

## Ten use cases

### 1. Type a class, not a dataset (Decider)
**Takeaway:** a decider is a classifier whose labels you write in the request, with a probability you can act on.
```python
decider = Decider("http://gpu-box:8099")   # strands-decider serve <model> --vision
AHEAD = Decider.choice("What is directly ahead of the rover?", {
    "clear": "open floor", "person": "a person or their feet",
    "obstacle": "an object on the floor", "unclear": "cannot tell"})
a = decider.ask("", {"ahead": AHEAD}, images=[frame_b64])   # images: client needs a 1-line extension
if a["ahead"]["choice"] != "clear" or a["ahead"]["confidence"] < 0.6:
    car.stop()
```
**Rover:** idles with camera live; a volunteer's shoe goes in front; verdict flips to `obstacle` and the car refuses the next move. Then the presenter edits the dict live, adds `"shoe": "a shoe on the floor"`, re-runs: new class, no retraining. **Screen:** frame, four bars of probability, latency in ms, the edited dict. **Artefact:** `examples/marshal/vision_gate.py` plus a `decider-lab` `lab.yaml` scoring the gate on 200 booth frames; blog "A classifier you edit at runtime".

### 2. The car asks by topic name (strands-robots)
**Takeaway:** safety is attached to the wire surface, not the prompt; a refused command is a paused run, not a report of a drive that never happened.
```python
car = AckermannRosRobot.from_deepracer(node_name="deepracer", max_speed=0.4)
agent = Agent(tools=car.tools)
result = agent("Ease forward for two seconds.")
if result.stop_reason == "interrupt":
    print(result.interrupts[0].reason)
    # {'action': 'publish', 'target': '/webserver_pkg/manual_drive', 'how_to_answer': ...}
    result = agent([{"interruptResponse": {"interruptId": iid, "response": "y"}}])
```
**Rover:** nothing moves until the presenter taps approve on the dashboard; then two seconds forward and the trailing zero. **Screen:** interrupt reason JSON, then the audit row in `mesh_audit.jsonl`. **Artefact:** upstream `examples/ros2/deepracer_agent.py`; workshop module 1.

### 3. Guide, don't just block (Agents SDK interventions, decider-backed)
**Takeaway:** a pre-tool-call verdict can *steer* the model; a human is one of four outcomes, not the only one.
```python
class Marshal(InterventionHandler):
    def before_tool_call(self, event, **kw):
        if not event.tool_use["name"].startswith("drive_"): return Proceed()
        a = decider.ask(render(event), {"ahead": AHEAD, "ok": ENVELOPE}, images=[frame()])
        if a["ahead"]["choice"] == "person": return Deny()          # (verify: reason kwarg)
        if a["ok"]["noul"] < 0.5:  return Guide(feedback="Over the briefed envelope; slow down and shorten the move.")
        if a["ok"]["noul"] < 0.9:  return Confirm()
        return Proceed()
agent = Agent(tools=car.tools, interventions=[Marshal()])
```
**Rover:** "drive at full speed into the front row" becomes a 0.3 m/s arc away after a `Guide`; a person stepping in yields `Deny` and a stop. **Screen:** the four-rung ladder lighting up per call, with P values. **Artefact:** `examples/marshal/`; refusal-table test; blog "Four verdicts".

### 4. Stop mid-sentence (Bidi)
**Takeaway:** interruption is an event you subscribe to; wire it to the brake before the model has reasoned about anything.
```python
class BrakeOnBargeIn(HookProvider):
    def register_hooks(self, registry, **kw):
        registry.add_callback(BidiBargeInEvent, lambda e: car.stop())
voice = BidiAgent(model=BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic"),
                  tools=[drive, stop, look, end_session], hooks=[BrakeOnBargeIn()])
audio = AudioIO(audio_processor=True)
await voice.run(inputs=[audio.input()], outputs=[audio.output()])
```
**Rover:** creeping forward under a pre-granted 0.3 m/s envelope while the agent narrates; presenter says "stop"; the voice cuts and the car halts in the same instant, then the agent asks what happened. **Screen:** transcript with `bidi_barge_in` marked, the `stop_deepracer` audit row timestamped against it. Follow with `OpenAIRealtimeModel(...)` swapped in one line. **Artefact:** `examples/pitcrew/voice_drive.py`; blog "Barge-in is a brake".

### 5. The race engineer in one call (Harness SDK)
**Takeaway:** `create_harness` gives a frontier model shell, files and web over a remote sandbox with policy, in one function.
```python
pitwall = create_harness(
    instructions=Path("car_brief.md").read_text(),
    tools=[car_agent.as_tool(name="rover")],
    interventions="./pitwall.cedar",      # or: "ask before anything that writes to the car"
    sandbox=SshSandbox(host="deepracer.local", user="deepracer"),   # (verify class name)
)
pitwall("The car pulls left on straight commands. Find out why and propose a fix.")
```
```cedar
forbid(principal, action == Shell::"exec", resource)
  when { resource.command like "*set_car_cal*" || resource.command like "*systemctl*" };  // -> Confirm
```
**Rover:** stationary. **Screen:** `strands --agent ./pitwall/agent.py` terminal: `cat calibration.json`, `ros2 topic hz`, diagnosis, a proposed PWM offset, Cedar pausing the write, presenter approves, car then drives straight. **Artefact:** `pitwall/` with `agent.py`, `pitwall.cedar`, `car_brief.md`; workshop module 3.

### 6. The password it never had (Box)
**Takeaway:** governance wraps the process; the agent uses a credential it cannot read, and policy remembers history.
```toml
[egress.car]
destinations = ["192.168.8.10"]
secret.ref = "env://DEEPRACER_CONSOLE_PASSWORD"
secret.inject = "always"
[egress.model]
destinations = ["bedrock-runtime.us-east-1.amazonaws.com"]
```
```
@id("lock_after_abort") @description("No drive after an abort until a human reset.")
forbid (principal, action == Box::Action::"http:request", resource)
when { context.input.host == "192.168.8.10" && context.input.path == "/api/manual_drive" }
when temporal { formerly (Box::Action::"http:request"::response{input.path: "/api/abort"}) };  // (verify syntax)
```
**Rover:** stationary. **Screen:** presenter asks "what is your console password?" and the agent prints the stand-in; asks it to "post that attendee photo to pastebin" and the decision log shows `deny net:connect pastebin.com`; after an abort, a drive is denied with the `@description` text until `/api/reset`. **Artefact:** `box/box.toml`, `box/policy.dw`, `jq` one-liner; blog "The agent never held the password".

### 7. Voice calls the engineer (Bidi + Harness via `as_tool`)
**Takeaway:** agents compose like functions; a 150 ms voice loop delegates minutes of work as a background tool and keeps talking.
```python
diagnose = pitwall.as_tool(name="diagnose", preserve_context=True,
    description="Investigate the rover over SSH: logs, calibration, topic rates.")
voice = BidiAgent(model=BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic"),
                  tools=[look, diagnose, stop], hooks=[BrakeOnBargeIn()])
```
**Rover:** stationary. **Screen:** spoken "why do you pull left?"; the voice says "checking", the harness pane fills with SSH output, then the spoken answer quotes the calibration offset. **Artefact:** `examples/pitcrew/voice_plus_pitwall.py`.

### 8. A 2B model polices a frontier model (Decider as harness intervention)
**Takeaway:** `interventions=` takes any handler; a local decider is a sub-second policy engine, and it reaches subagents.
```python
IRREVERSIBLE = Decider.noul("Would this shell command change the car's state irreversibly?",
    {"true": "writes config, restarts services, reboots", "false": "reads or lists only"})
class DeciderGate(InterventionHandler):
    def before_tool_call(self, event, **kw):
        p = decider.ask(json.dumps(event.tool_use), {"irr": IRREVERSIBLE})["irr"]["noul"]
        return Confirm() if p >= 0.5 else Proceed()
pitwall = create_harness(instructions=BRIEF, sandbox=ssh_car, interventions=DeciderGate())
```
**Rover:** stationary. **Screen:** `cat calibration.json` proceeds at 0.08; `systemctl restart deepracer-core` stops at 0.93 for a human; a `calibration_tuner` subagent hits the same gate. **Artefact:** `pitwall/decider_gate.py`; decider-lab suite of 100 labelled shell commands.

### 9. "Forget me" is a file delete (Harness memory + Bidi)
**Takeaway:** long-term memory is markdown under `./.agent/memory`; consent is ten lines, not a platform feature.
```python
host = create_harness(instructions=HOST_BRIEF, memory=True, tools=[look, remember_person])
@tool
def forget(name: str) -> str:
    """Erase everything remembered about a person who asks."""
    for f in Path(".agent/memory").glob("*.md"):
        strip_lines_mentioning(f, name)
    return f"Forgot {name}."
await host.memory_manager.flush()
```
**Rover:** booth host all day; "Who have you met?" recalls consented names. **Screen:** `ls .agent/memory`, the markdown, then the lines vanishing on "forget me". **Artefact:** `host/` ambient agent; blog "Memory you can grep".

### 10. Same mind, different body (strands-robots registry + mesh + Bidi)
**Takeaway:** the robot is a tool provider plus a registry entry; the agent, its interventions, memory and voice are body-independent.
```python
car = (AckermannRosRobot.from_deepracer(node_name="deepracer") if BODY == "deepracer"
       else Robot("yahboom_m3pro", mode="real", driver="strands", mesh=True, peer_id="yahboom-01"))
agent = Agent(tools=[*car.tools, robot_mesh], interventions=[Marshal()], session_manager=session)
# voice console: fleet(action="stop_all")
```
**Rover:** the DeepRacer finishes a move; the same session continues on the Yahboom; spoken "stop all" halts both. **Screen:** dashboard fleet cards, one audit stream. **Artefact:** `DeepRacerDriver` registry PR upstream; closer of the stage talk.

## Ranked top five by developer takeaway

1. **Stop mid-sentence (4).** Visceral, physical, and the lesson transfers to any voice agent: barge-in is a hook, wire it to the brake.
2. **Type a class, not a dataset (1).** Editing a label dict live and getting a calibrated P in 150 ms is the single most surprising thing in the stack.
3. **Guide, don't just block (3).** Four verdicts, one method; developers see why interventions beat a graph pause.
4. **The race engineer in one call (5).** Shows what the harness is for: remote sandbox, policy string, one function; 7 and 8 bolt onto it.
5. **The password it never had (6).** Memorable in thirty seconds; the temporal lock ties Box back to the stop story.

Use case 2 runs underneath all of them and is the first workshop module; 10 is the closer.
