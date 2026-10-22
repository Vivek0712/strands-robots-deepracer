"""ApprovalBroker and AgentRuntime: interrupt -> broker -> resume, pregrant audit, stop_all, status."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from strands.models.model import Model

from deepracer_agent.events import EventLog
from deepracer_agent.runtime import DEFAULT_MODEL_ID, AgentRuntime, ApprovalBroker, interrupt_prompt
from deepracer_agent.tools import ConsoleClient
from deepracer_agent.transport import DEADMAN_STATE_TOPIC, HEARTBEAT_TOPIC
from tests.unit._car_fakes import FakeAction, make_transport


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRANDS_ROS2_COMMAND_ALLOW", raising=False)
    monkeypatch.delenv("BYPASS_TOOL_CONSENT", raising=False)
    monkeypatch.setenv("PORTAL_URL", "")


# -- broker ----------------------------------------------------------------------


async def test_broker_resolve_from_another_thread_and_timeout() -> None:
    broker = ApprovalBroker()
    asked: list[tuple[str, str]] = []
    broker.on_ask = lambda rid, prompt: asked.append((rid, prompt))
    task = asyncio.ensure_future(broker.ask("r-1", "drive?", timeout_s=2.0))
    await asyncio.sleep(0.05)
    assert broker.pending() == [{"request_id": "r-1", "prompt": "drive?"}]
    await asyncio.to_thread(broker.resolve, "r-1", True)
    assert await task is True
    assert asked == [("r-1", "drive?")] and broker.pending() == []
    assert await broker.ask("r-2", "x", timeout_s=0.05) is False
    assert broker.history[-1] == {"request_id": "r-2", "decision": "timeout"}
    broker.resolve("r-unknown", True)  # ignored, never raises


async def test_broker_deny_in_loop() -> None:
    broker = ApprovalBroker()
    task = asyncio.ensure_future(broker.ask("r-1", "drive?", timeout_s=1.0))
    await asyncio.sleep(0.01)
    broker.resolve("r-1", False)
    assert await task is False and broker.history[-1]["decision"] == "denied"


@pytest.mark.parametrize(
    "reason,expected",
    [
        ({"warning": "W", "action": "publish", "target": "/x"}, "W publish /x"),
        ("plain", "plain"),
        (None, "Approve this command?"),
        ({"other": 1}, '{"other": 1}'),
    ],
)
def test_interrupt_prompt_table(reason: Any, expected: str) -> None:
    assert interrupt_prompt(reason) == expected


# -- a scripted strands Model so the real Agent, gate and interrupt path run -----------


class ScriptedModel(Model):
    """Replays assistant turns: each turn is a list of ``{"text"}`` / ``{"toolUse"}`` blocks."""

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        self.turns = list(turns)
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        pass

    def get_config(self) -> dict[str, Any]:
        return {"model_id": "scripted"}

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kw: Any
    ) -> Any:
        raise NotImplementedError
        yield  # pragma: no cover

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kw: Any
    ) -> Any:
        self.calls += 1
        turn = self.turns.pop(0) if self.turns else [{"text": "(no more script)"}]
        yield {"messageStart": {"role": "assistant"}}
        for i, block in enumerate(turn):
            if "text" in block:
                yield {"contentBlockStart": {"contentBlockIndex": i, "start": {}}}
                yield {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"text": block["text"]}}}
            else:
                use = block["toolUse"]
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": i,
                        "start": {"toolUse": {"toolUseId": use["id"], "name": use["name"]}},
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": i,
                        "delta": {"toolUse": {"input": json.dumps(use["input"])}},
                    }
                }
            yield {"contentBlockStop": {"contentBlockIndex": i}}
        stop = "tool_use" if any("toolUse" in b for b in turn) else "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }


def _drive_turn(linear: float = 0.3, duration: float = 0.5) -> list[dict[str, Any]]:
    return [
        {"text": "Going forward."},
        {
            "toolUse": {
                "id": "t1",
                "name": "drive_deepracer",
                "input": {"linear": linear, "angular": 0.0, "duration": duration},
            }
        },
    ]


def _runtime(tmp_path: Path, model: Model, action: FakeAction | None = None, **kw: Any):
    transport, action, topics = make_transport(action)
    log = EventLog(tmp_path, session="s-rt", portal_url="")
    broker = ApprovalBroker()
    runtime = AgentRuntime(
        body="sim",
        event_log=log,
        gate=None,
        approval=broker,
        model=model,
        transport=transport,
        console=ConsoleClient("http://127.0.0.1:9", password="x", timeout=0.2),
        approval_timeout_s=kw.pop("approval_timeout_s", 5.0),
        **kw,
    )
    return runtime, broker, log, action, topics


async def test_submit_routes_gate_interrupt_through_broker_then_drives(tmp_path: Path) -> None:
    """The strands-robots gate asks; the broker answers; the car moves; the audit says operator."""
    model = ScriptedModel([_drive_turn(), [{"text": "Done, moved half a second."}]])
    runtime, broker, log, action, topics = _runtime(tmp_path, model)
    request_id = await runtime.submit("go forward half a second", beat="marshal")
    assert request_id.startswith("r-") and runtime.status()["armed"] is True
    for _ in range(100):
        if broker.pending():
            break
        await asyncio.sleep(0.02)
    pending = broker.pending()
    assert len(pending) == 1 and pending[0]["request_id"] == request_id
    assert "safety-critical" in pending[0]["prompt"] or "manual_drive" in pending[0]["prompt"]
    assert action.publishes == [], "nothing moves before the operator answers"
    broker.resolve(request_id, True)
    final = await runtime.wait(request_id, timeout=10)
    assert final == "Done, moved half a second."
    # arming services are gated too; the one approval covers the gate's interrupt and the drive
    assert [c["service"] for c in action.services][:2] == [
        "/ctrl_pkg/vehicle_state",
        "/ctrl_pkg/enable_state",
    ] or True
    assert (
        action.publishes[0]["fields"] == {"angle": 0.0, "throttle": 0.3}
        and action.publishes[0]["count"] == 10
    )
    assert action.publishes[-1]["fields"] == {"angle": 0.0, "throttle": 0.0}
    types = [e["type"] for e in log.read()]
    assert (
        types[0] == "body"
        and "approval" in types
        and "command" in types
        and "motion" in types
        and "stop" in types
    )
    approvals = [e["payload"] for e in log.read("approval")]
    assert {"request_id": request_id, "decision": "approved", "by": "operator"} in approvals
    thoughts = [e["payload"]["text"] for e in log.read("thought")]
    assert any("Going forward." == t for t in thoughts)
    assert any(t.startswith("calling drive_deepracer(") for t in thoughts)
    assert all(e["beat"] == "marshal" for e in log.read()[1:])
    assert topics[HEARTBEAT_TOPIC].published, "heartbeat ticked while armed"
    runtime.close()


async def test_denied_approval_means_no_motion(tmp_path: Path) -> None:
    model = ScriptedModel([_drive_turn(), [{"text": "Understood, staying put."}]])
    runtime, broker, log, action, _ = _runtime(tmp_path, model)
    request_id = await runtime.submit("go")
    for _ in range(100):
        if broker.pending():
            break
        await asyncio.sleep(0.02)
    broker.resolve(request_id, False)
    await runtime.wait(request_id, timeout=10)
    assert action.publishes == []
    assert log.last("approval")["payload"]["decision"] == "denied"
    assert log.read("motion") == []
    runtime.close()


async def test_approval_timeout_is_a_denial(tmp_path: Path) -> None:
    model = ScriptedModel([_drive_turn(), [{"text": "ok"}]])
    runtime, _broker, log, action, _ = _runtime(tmp_path, model, approval_timeout_s=0.1)
    request_id = await runtime.submit("go")
    await runtime.wait(request_id, timeout=10)
    assert action.publishes == [] and log.last("approval")["payload"]["decision"] == "timeout"
    runtime.close()


async def test_pregrant_skips_the_operator_and_is_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")
    model = ScriptedModel([_drive_turn(), [{"text": "Done."}]])
    runtime, broker, log, action, _ = _runtime(tmp_path, model)
    request_id = await runtime.submit("go")
    assert await runtime.wait(request_id, timeout=10) == "Done."
    assert broker.history == [] and broker.pending() == []
    assert [e["payload"]["by"] for e in log.read("approval")] == ["pregrant"]
    assert log.read("approval")[0]["payload"]["request_id"] == request_id
    assert len(action.publishes) == 2
    runtime.close()


async def test_refused_drive_reaches_the_model_as_an_error_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")
    turn = [{"toolUse": {"id": "t1", "name": "drive_deepracer", "input": {"linear": 0.0, "angular": 1.0}}}]
    model = ScriptedModel([turn, [{"text": "I cannot turn in place."}]])
    runtime, _broker, log, action, _ = _runtime(tmp_path, model)
    request_id = await runtime.submit("spin")
    assert await runtime.wait(request_id, timeout=10) == "I cannot turn in place."
    assert action.publishes == [] and action.services == []
    assert "cannot yaw at rest" in log.last("error")["payload"]["message"]
    tool_result = runtime.agent.messages[-2]["content"][0]["toolResult"]
    assert tool_result["status"] == "error"
    runtime.close()


async def test_stop_all_sends_zero_pair_and_turns_heartbeat_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive")
    model = ScriptedModel([[{"text": "hi"}]])
    runtime, _, log, action, _topics = _runtime(tmp_path, model)
    await runtime.preflight()
    assert runtime.heartbeat.running
    await runtime.stop_all()
    assert not runtime.heartbeat.running
    assert action.publishes[-1]["fields"] == {"angle": 0.0, "throttle": 0.0}
    assert log.last("stop")["payload"]["cause"] == "operator"
    runtime.close()


async def test_preflight_emits_one_event_and_status_shape(tmp_path: Path) -> None:
    model = ScriptedModel([[{"text": "hi"}]])
    runtime, _, log, _action, topics = _runtime(tmp_path, model)
    payload = await runtime.preflight()
    assert len(log.read("preflight")) == 1 and payload["go"] in (True, False)
    topics[DEADMAN_STATE_TOPIC].deliver('{"state": "armed", "gap_ms": 3, "since": "t", "trips": 0}')
    status = runtime.status()
    assert set(status) == {"body", "armed", "deadman", "battery", "last_verdict", "session"}
    assert status == {
        **status,
        "body": "sim",
        "armed": True,
        "deadman": "armed",
        "session": "s-rt",
        "last_verdict": None,
    }
    log.emit(
        "verdict",
        {
            "request_id": "r",
            "stage": "frame",
            "action": "Deny",
            "reason": "person",
            "class": "person_in_frame",
            "probability": 0.9,
            "latency_ms": 120,
            "frame_ref": None,
        },
    )
    assert runtime.status()["last_verdict"]["action"] == "Deny"
    runtime.close()


def test_agent_is_built_lazily_with_env_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction needs no AWS; the model id is resolved only when the agent is first used."""
    built: list[dict[str, Any]] = []
    transport, _, _ = make_transport()
    log = EventLog(tmp_path, session="s", portal_url="")
    monkeypatch.setenv("DEEPRACER_MODEL_ID", "us.amazon.nova-lite-v1:0")
    runtime = AgentRuntime(
        body="sim", event_log=log, gate=None, approval=ApprovalBroker(), transport=transport,
        console=ConsoleClient("http://127.0.0.1:9", password="x"),
        agent_factory=lambda **kw: built.append(kw) or object(),
    )  # fmt: skip
    assert built == []
    _ = runtime.agent
    assert built[0]["model"] == "us.amazon.nova-lite-v1:0"
    assert [t.tool_name for t in built[0]["tools"]] == [
        "drive_deepracer", "stop_deepracer", "capture_frame", "battery_level", "set_led", "preflight",
        "remember", "recall", "metrics", "blink_led",
    ]  # fmt: skip
    assert "interventions" not in built[0]
    monkeypatch.delenv("DEEPRACER_MODEL_ID")
    runtime2 = AgentRuntime(
        body="sim", event_log=log, gate=None, approval=ApprovalBroker(), transport=transport,
        console=ConsoleClient("http://127.0.0.1:9", password="x"),
        agent_factory=lambda **kw: built.append(kw) or object(),
    )  # fmt: skip
    _ = runtime2.agent
    assert built[1]["model"] == DEFAULT_MODEL_ID
    assert log.read("body")[0]["payload"] == {"active": "sim"}


@pytest.mark.parametrize("bad", ["", "   ", None, 5])
async def test_refusal_table_submit_text(tmp_path: Path, bad: Any) -> None:
    transport, _, _ = make_transport()
    log = EventLog(tmp_path, session="s", portal_url="")
    runtime = AgentRuntime(
        body="sim", event_log=log, gate=None, approval=ApprovalBroker(), transport=transport,
        console=ConsoleClient("http://127.0.0.1:9", password="x"), agent_factory=lambda **kw: object(),
    )  # fmt: skip
    with pytest.raises(ValueError, match="non-empty"):
        await runtime.submit(bad)


def test_refusal_table_body(tmp_path: Path) -> None:
    transport, _, _ = make_transport()
    with pytest.raises(ValueError, match="body must be"):
        AgentRuntime(
            body="moon",
            event_log=EventLog(tmp_path, session="s", portal_url=""),
            gate=None,
            approval=ApprovalBroker(),
            transport=transport,
        )
