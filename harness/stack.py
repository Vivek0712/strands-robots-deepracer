"""The whole fake garage in one `with` block: car, console and decider on the contract ports.

`with SimStack() as s:` starts the fake car (`ws://127.0.0.1:9091`, control `:8092`), the fake
console (`:8090`) and the fake decider (`:8111`) in daemon threads, waits until each answers,
and hands back their control handles (`s.car`, `s.console`, `s.decider`, `s.shared`). The
agent, the gate, the portal and the voice loop then run end to end with no hardware in the
room, which is where every regression should be caught first. `python -m harness.stack` runs
the three in the foreground for a manual session (`make beat NAME=marshal BODY=sim` against
them). Physics stops the car; the decider explains.
"""

from __future__ import annotations

import logging
import os
import socket
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from harness import CONSOLE_PORT, CONTROL_PORT, DECIDER_PORT, ROSBRIDGE_PORT
from harness.fake_car import FakeCar
from harness.fake_console import FakeConsole
from harness.fake_decider import FakeDecider
from harness.shared import SharedState

logger = logging.getLogger("harness.stack")


def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


class SimStack:
    """Fake car + fake console + fake decider, started together and stopped together."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        rosbridge_port: int = ROSBRIDGE_PORT,
        control_port: int = CONTROL_PORT,
        console_port: int = CONSOLE_PORT,
        decider_port: int = DECIDER_PORT,
        shared_path: Path | str | None = None,
        deadman: bool = False,
        battery: int = 10,
        calibration: str = "calibrated",
        ready_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.shared = SharedState(shared_path)
        self.car = FakeCar(
            host,
            rosbridge_port,
            control_port,
            shared=self.shared,
            deadman=deadman,
            battery=battery,
            calibration=calibration,
        )
        self.console = FakeConsole(host, console_port, shared=self.shared)
        self.decider = FakeDecider(host, decider_port, shared=self.shared)
        self.ready_timeout = ready_timeout
        self._started = False

    def env(self) -> dict[str, str]:
        """The CONTRACTS §3 environment that points a laptop-side component at this stack."""
        return {
            "DEEPRACER_BODY": "sim",
            "DEEPRACER_HOST": self.host,
            "DEEPRACER_ROSBRIDGE_PORT": str(self.car.port),
            "DEEPRACER_CONSOLE_URL": self.console.url,
            "DECIDER_URL": self.decider.url,
            "DEEPRACER_SIM_SHARED": str(self.shared.path),
        }

    def start(self) -> SimStack:
        if self._started:
            return self
        self.shared.reset()
        self.car.start()
        self.console.start()
        self.decider.start()
        self._started = True
        self.wait_ready(self.ready_timeout)
        logger.info("sim stack ready: %s", self.env())
        return self

    def wait_ready(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        checks = {
            "fake car ws": lambda: _port_open(self.host, self.car.port),
            "fake car control": lambda: _http_ok(f"http://{self.host}:{self.car.control_port}/state"),
            "fake console": lambda: _http_ok(f"{self.console.url}/login"),
            "fake decider": lambda: _http_ok(f"{self.decider.url}/health"),
        }
        pending = dict(checks)
        while pending and time.monotonic() < deadline:
            for name, check in list(pending.items()):
                if check():
                    pending.pop(name)
            if pending:
                time.sleep(0.05)
        if pending:
            raise TimeoutError(f"sim stack not ready within {timeout}s: {', '.join(pending)}")

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        for name, part in (("decider", self.decider), ("console", self.console), ("car", self.car)):
            try:
                part.stop()
            except Exception:
                logger.exception("stopping fake %s failed", name)

    def reset(self) -> None:
        """Between tests: car to boot state, decider knobs cleared, label back to `clear`."""
        self.car.reset()
        self.decider.reset()
        self.shared.set(label="clear")

    def status(self) -> dict[str, Any]:
        return {
            "car": self.car.state(),
            "decider": self.decider.control(),
            "console": {"label": self.console.label()},
        }

    def __enter__(self) -> SimStack:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


def _port_of(url: str | None, default: int) -> int:
    """Port of ``http://host:port`` (or ``ws://``); ``default`` when unset or unparsable."""
    if not url:
        return default
    try:
        return urlparse(url).port or default
    except ValueError:
        return default


def ports_from_env() -> dict[str, int]:
    """CONTRACTS §3 override columns: the stack's four ports, read from the same env the clients use.

    ``DEEPRACER_ROSBRIDGE_PORT`` (fake car ws), ``DEEPRACER_SIM_CONTROL_URL`` (fake car control),
    ``DEEPRACER_CONSOLE_URL`` (fake console), ``DECIDER_URL`` (fake decider). Unset means the
    contract defaults (9091, 8092, 8090, 8111), so two stacks can share a laptop when one of them
    sets the overrides.
    """
    return {
        "rosbridge_port": int(os.environ.get("DEEPRACER_ROSBRIDGE_PORT") or ROSBRIDGE_PORT),
        "control_port": _port_of(os.environ.get("DEEPRACER_SIM_CONTROL_URL"), CONTROL_PORT),
        "console_port": _port_of(os.environ.get("DEEPRACER_CONSOLE_URL"), CONSOLE_PORT),
        "decider_port": _port_of(os.environ.get("DECIDER_URL"), DECIDER_PORT),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deadman", action="store_true", help="start with the on-car deadman emulation on")
    ap.add_argument("--battery", type=int, default=10)
    ap.add_argument("-v", "--verbose", action="store_true")
    ports = ports_from_env()
    for name, default in ports.items():
        ap.add_argument(f"--{name.replace('_', '-')}", type=int, default=default)
    ap.add_argument(
        "--shared",
        default=os.environ.get("DEEPRACER_SIM_SHARED") or None,
        help="shared.json path (default runs/sim/shared.json; DEEPRACER_SIM_SHARED overrides)",
    )
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(name)s %(message)s")
    with SimStack(
        deadman=a.deadman,
        battery=a.battery,
        rosbridge_port=a.rosbridge_port,
        control_port=a.control_port,
        console_port=a.console_port,
        decider_port=a.decider_port,
        shared_path=a.shared,
    ) as stack:
        print("sim stack up:")
        for k, v in stack.env().items():
            print(f"  export {k}={v}")
        print(f"  control: http://{stack.host}:{stack.car.control_port}/state   (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
