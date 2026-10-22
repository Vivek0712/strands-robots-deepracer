"""Shared pytest fixtures: the fake garage on the contract ports, and the environment every test sees.

`sim_stack` starts the fake car, fake console and fake decider once per session (CONTRACTS §3
ports) and `fake_car`, `fake_console`, `fake_decider` hand out their control handles reset to a
known state. `run_dir` points `DEEPRACER_RUN_DIR` at a temporary run directory. The three
command surfaces (`/manual_drive`, `/vehicle_state`, `/enable_state`) are pre-granted for the
test process through `STRANDS_ROS2_COMMAND_ALLOW`, the documented headless pre-grant: tests
have no operator to answer the gate's prompt. When the run selects the real-car layers
(`-m wheels_off`, `-m pen`) the sim defaults are NOT applied: body `car`, rosbridge 9090 and the
console at `https://$DEEPRACER_HOST`. Physics stops the car; the decider explains.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from harness import CONSOLE_PORT, DECIDER_PORT, ROSBRIDGE_PORT
from harness.stack import SimStack, ports_from_env

#: Headless pre-grant for the test process (CONTRACTS §3 / §9): no operator answers prompts here.
COMMAND_ALLOW = "/manual_drive,/vehicle_state,/enable_state"

CONTRACT_ENV = {
    "DEEPRACER_BODY": "sim",
    "DEEPRACER_HOST": "127.0.0.1",
    "DEEPRACER_ROSBRIDGE_PORT": str(ROSBRIDGE_PORT),
    "DEEPRACER_CONSOLE_URL": f"http://127.0.0.1:{CONSOLE_PORT}",
    "DECIDER_URL": f"http://127.0.0.1:{DECIDER_PORT}",
    "STRANDS_ROS2_COMMAND_ALLOW": COMMAND_ALLOW,
}

_LAYER_MARKERS = {"sim": "sim", "car": "wheels_off", "pen": "pen"}


def _real_car_selected(config: pytest.Config) -> bool:
    """True when the run selects the car layers (``-m wheels_off`` / ``-m pen``), not deselects them."""
    expr = str(config.getoption("markexpr") or "")
    selected = expr.replace("not wheels_off", "").replace("not pen", "")
    return "wheels_off" in selected or "pen" in selected


def pytest_configure(config: pytest.Config) -> None:
    if _real_car_selected(config):
        # Layers 2 and 3 talk to the real car: DEEPRACER_HOST comes from ~/.config/deepracer/env
        # (sourced by the Makefile); the sim port/console defaults below would point the car tests at
        # ws://<car>:9091, which does not exist (that cost a 25 s x 3 retry per test on 2026-10-14).
        host = os.environ.get("DEEPRACER_HOST", "")
        os.environ.setdefault("DEEPRACER_BODY", "car")
        os.environ.setdefault("DEEPRACER_ROSBRIDGE_PORT", "9090")
        if host and host != "127.0.0.1":
            os.environ.setdefault("DEEPRACER_CONSOLE_URL", f"https://{host}")
        os.environ.setdefault("STRANDS_ROS2_COMMAND_ALLOW", COMMAND_ALLOW)
    else:
        for key, value in CONTRACT_ENV.items():
            os.environ.setdefault(key, value)
    # The portal is not part of the unit/sim/car layers; an unset PORTAL_URL means "do not POST".
    os.environ.pop("PORTAL_URL", None)
    # The operator's own ~/.config/deepracer/calibration.json (the portal's Throttle setting) must
    # not leak into tests: point the loader at a file that does not exist unless a test sets one.
    if not _real_car_selected(config):
        os.environ.setdefault("DEEPRACER_CALIBRATION_FILE", "")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark tests by the layer directory they live in (tests/sim -> sim, tests/car -> wheels_off)."""
    root = Path(str(config.rootpath)) / "tests"
    for item in items:
        try:
            layer = Path(str(item.fspath)).relative_to(root).parts[0]
        except ValueError:
            continue
        marker = _LAYER_MARKERS.get(layer)
        if marker and not item.get_closest_marker(marker):
            item.add_marker(getattr(pytest.mark, marker))


@pytest.fixture(scope="session")
def sim_stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SimStack]:
    shared = tmp_path_factory.mktemp("sim") / "shared.json"
    os.environ["DEEPRACER_SIM_SHARED"] = str(shared)
    # The four ports come from the same env the clients read (CONTRACTS section 3 override
    # columns), so `DECIDER_URL=http://127.0.0.1:8211 make unit` runs beside a live decider on 8111.
    with SimStack(shared_path=shared, **ports_from_env()) as stack:
        yield stack


@pytest.fixture
def fake_car(sim_stack: SimStack) -> Iterator[Any]:
    sim_stack.reset()
    yield sim_stack.car
    sim_stack.car.set_deadman(False)


@pytest.fixture
def fake_console(sim_stack: SimStack) -> Any:
    sim_stack.shared.set(label="clear")
    return sim_stack.console


@pytest.fixture
def fake_decider(sim_stack: SimStack) -> Any:
    sim_stack.decider.reset()
    sim_stack.shared.set(label="clear")
    return sim_stack.decider


@pytest.fixture
def run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "run"
    (directory / "frames").mkdir(parents=True)
    monkeypatch.setenv("DEEPRACER_RUN_DIR", str(directory))
    return directory


@pytest.fixture(scope="session")
def rosbridge() -> Callable[..., dict[str, Any]]:
    """`rosbridge_action` bound to the fake car with upstream's real command gate.

    Only the verbs that carry a command (`publish`, `service_call`) consult the gate; the
    pre-grant in `COMMAND_ALLOW` lets them through without an operator.
    """
    from strands_robots._command_gate import gate_command
    from strands_robots.rosbridge import GATE_TOOL, never_gated, rosbridge_action

    host = os.environ["DEEPRACER_HOST"]
    port = int(os.environ["DEEPRACER_ROSBRIDGE_PORT"])

    def gate(kind: str, target: str) -> str | None:
        return gate_command(kind, target, None, tool=GATE_TOOL)

    def call(action: str, **kw: Any) -> dict[str, Any]:
        chosen = gate if action in ("publish", "service_call") else never_gated
        return rosbridge_action(action, host=host, port=port, gate=chosen, **kw)

    return call


@pytest.fixture(autouse=True)
def _no_decider_cooldown():
    """The decider client's post-timeout cooldown is process-wide; tests must not inherit it."""
    try:
        from deepracer_agent import decider_client

        decider_client._cooldown_until.clear()
    except ImportError:
        pass
    yield
