"""The race engineer's leash: the Cedar policy parses, reads pass, writes need a confirmed operator.

These tests never open SSH or call a model. They exercise the policy file with cedarpy exactly
as ``CedarAuthorization`` would, so a loosened policy fails here, not on the car.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

cedarpy = pytest.importorskip("cedarpy")

from ops import race_engineer  # noqa: E402

POLICY = race_engineer.POLICY_FILE.read_text()
PRINCIPAL = 'User::"engineer"'
RESOURCE = 'Resource::"car"'


def _decide(action: str, tool_input: dict, confirmed: bool) -> str:
    request = {
        "principal": PRINCIPAL,
        "action": f'Action::"{action}"',
        "resource": RESOURCE,
        "context": {"input": tool_input, "session": {"operator_confirmed": confirmed, "hour_utc": 12}},
    }
    result = cedarpy.is_authorized(request, POLICY, [])
    return str(result.decision)


def test_policy_parses() -> None:
    cedarpy.format_policies(POLICY)


@pytest.mark.parametrize(
    ("action", "tool_input", "confirmed", "expected"),
    [
        ("read", {"path": "/opt/aws/deepracer/calibration.json"}, False, "Allow"),
        ("web_fetch", {"url": "https://docs.aws.amazon.com/deepracer/"}, False, "Allow"),
        ("shell", {"command": "cat /opt/aws/deepracer/calibration.json"}, False, "Allow"),
        ("shell", {"command": "journalctl -u deepracer-core -n 50"}, False, "Allow"),
        ("shell", {"command": "ros2 topic pub /webserver_pkg/manual_drive ..."}, True, "Deny"),
        ("shell", {"command": "ros2 topic pub /cmd_vel ..."}, True, "Deny"),
        ("shell", {"command": "sudo systemctl restart deepracer-core"}, False, "Deny"),
        ("shell", {"command": "sudo systemctl restart deepracer-core"}, True, "Allow"),
        ("shell", {"command": "sudo apt-get install foo"}, False, "Deny"),
        ("shell", {"command": "sudo reboot"}, False, "Deny"),
        ("shell", {"command": "echo 1400000 > /sys/class/pwm/pwmchip0/pwm0/duty_cycle"}, False, "Deny"),
        ("write", {"path": "/opt/aws/deepracer/calibration.json", "content": "{}"}, False, "Deny"),
        ("write", {"path": "/opt/aws/deepracer/calibration.json", "content": "{}"}, True, "Allow"),
        ("edit", {"path": "/opt/aws/deepracer/launch/x.py"}, False, "Deny"),
    ],
)
def test_leash_table(action: str, tool_input: dict, confirmed: bool, expected: str) -> None:
    assert expected in _decide(action, tool_input, confirmed)


def test_env_loader_reads_file_and_never_prints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "env"
    env.write_text('DEEPRACER_HOST=192.168.0.7\n# comment\nDEEPRACER_SSH_PASSWORD="s3cret"\n')
    monkeypatch.setattr(race_engineer, "ENV_FILE", env)
    monkeypatch.delenv("DEEPRACER_HOST", raising=False)
    values = race_engineer._load_env()
    assert values["DEEPRACER_HOST"] == "192.168.0.7"
    assert values["DEEPRACER_SSH_PASSWORD"] == "s3cret"
    assert "s3cret" not in json.dumps({k: v for k, v in values.items() if k != "DEEPRACER_SSH_PASSWORD"})


def test_operator_confirmation_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPRACER_OPERATOR_CONFIRMED", raising=False)
    assert race_engineer.operator_confirmation({}) == {"operator_confirmed": False}
    monkeypatch.setenv("DEEPRACER_OPERATOR_CONFIRMED", "1")
    assert race_engineer.operator_confirmation({}) == {"operator_confirmed": True}


@pytest.mark.parametrize("action", ["search_memory", "retrieve_context", "todo_write"])
def test_notebook_tools_are_permitted_without_confirmation(action: str) -> None:
    """The engineer's memory and notes never touch the car: allowed whether or not the operator confirmed.

    Found on the stand 2026-10-14: with these missing, the first calibration review could not
    compare against what it remembered ("policy restrictions").
    """
    assert _decide(action, {"query": "steering calibration"}, confirmed=False).endswith("Allow")
