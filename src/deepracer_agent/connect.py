"""Find the car and make it reachable, whatever the network looks like today.

The order of preference, each step reported through ``on_step(step, status, detail)``:

1. **USB-C cable**: the stock image is a USB Ethernet adapter at 10.0.0.1 (``usb0``). About
   1 ms, no Wi-Fi, no router; the bench default.
2. **Direct IPv4**: the car found by its MAC in the ARP table, by mDNS, or by a sweep of the
   laptop's /24, with rosbridge (9090) answering. The travel router or a LAN.
3. **IPv6 with an SSH tunnel**: on an IPv6-only hotspot (a phone on a CG-NAT carrier gives the
   laptop no IPv4) the car is found by its MAC in the neighbour table; rosbridge only listens on
   IPv4 on the car, so an ``ssh -N -L`` tunnel carries rosbridge and the console over the
   IPv6 link. Round trip on a phone hotspot was 75-800 ms (2026-10-17): fine for the bench, not
   for the stage. The stage uses the travel router.

The result is written to the environment the rest of the stack reads (``DEEPRACER_HOST``,
``DEEPRACER_ROSBRIDGE_PORT``, ``DEEPRACER_CONSOLE_URL``, ``DEEPRACER_SSH_HOST``), so a runtime
built after ``connect()`` talks to the right place. Physics stops the car; the decider explains;
this module only finds the wire.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepracer_agent import discover

logger = logging.getLogger(__name__)

StepFn = Callable[[str, str, str], None]

TUNNEL_ROSBRIDGE_PORT = 9090
HANDSHAKE_TIMEOUT_S = 20.0  # a reconnecting factory may be mid-backoff after a tunnel change
TUNNEL_CONSOLE_PORT = 18443  # 8443 is often taken (Docker Desktop on this laptop)
ROSBRIDGE_PORT = 9090


@dataclass
class CarLink:
    """What ``connect`` found and how the stack should reach it."""

    host: str = ""  # address the rosbridge/console clients use (127.0.0.1 when tunnelled)
    ssh_host: str = ""  # address ssh/scp use (the car's own address)
    how: str = "none"  # usb | direct | tunnel | none
    found_by: str = ""  # usb | arp | mdns | mdns6 | ndp | sweep | configured
    rosbridge_port: int = ROSBRIDGE_PORT
    console_url: str = ""
    rtt_ms: float | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def connected(self) -> bool:
        return self.how != "none" and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "host": self.host,
            "ssh_host": self.ssh_host,
            "how": self.how,
            "found_by": self.found_by,
            "rosbridge_port": self.rosbridge_port,
            "console_url": self.console_url,
            "rtt_ms": self.rtt_ms,
            "error": self.error,
            "steps": list(self.steps),
        }

    def export(self) -> dict[str, str]:
        """The env the rest of the stack reads; applied to ``os.environ`` by :func:`apply_env`."""
        if not self.connected:
            return {}
        return {
            "DEEPRACER_HOST": self.host,
            "DEEPRACER_SSH_HOST": self.ssh_host,
            "DEEPRACER_ROSBRIDGE_PORT": str(self.rosbridge_port),
            "DEEPRACER_CONSOLE_URL": self.console_url,
            "DEEPRACER_BODY": "car",
        }


def apply_env(link: CarLink) -> None:
    for key, value in link.export().items():
        os.environ[key] = value
    discover._cache.clear()


# -- the SSH tunnel ---------------------------------------------------------------------------


class Tunnel:
    """``ssh -N -L`` from the laptop to the car, kept as a child process."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None
        self.target: str = ""
        self.console_target: str = "127.0.0.1"

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def open(
        self,
        ssh_host: str,
        *,
        user: str | None = None,
        key: str | None = None,
        console_target: str = "127.0.0.1",
        rosbridge_local: int = TUNNEL_ROSBRIDGE_PORT,
        console_local: int = TUNNEL_CONSOLE_PORT,
        wait_s: float = 8.0,
    ) -> bool:
        self.close()
        ssh = shutil.which("ssh")
        if ssh is None:
            raise RuntimeError("ssh not found on PATH")
        user = user or os.environ.get("DEEPRACER_SSH_USER", "deepracer")
        key = key or os.path.expanduser(os.environ.get("DEEPRACER_SSH_KEY", "~/.ssh/id_ed25519_deepracer"))
        cmd = [
            ssh,
            "-N",
            "-o", "ConnectTimeout=8",
            "-o", "BatchMode=yes",
            "-o", "ServerAliveInterval=10",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-i", key,
            "-L", f"127.0.0.1:{rosbridge_local}:127.0.0.1:{ROSBRIDGE_PORT}",
            "-L", f"127.0.0.1:{console_local}:{console_target}:443",
            f"{user}@{ssh_host}",
        ]  # fmt: skip
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.target = ssh_host
        self.console_target = console_target
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                err = (self.proc.stderr.read() if self.proc.stderr else b"").decode(errors="replace").strip()
                logger.warning("tunnel exited: %s", err)
                self.proc = None
                return False
            if discover.reachable("127.0.0.1", ports=(rosbridge_local,), timeout=0.5):
                return True
            time.sleep(0.25)
        self.close()
        return False

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.target = ""


_tunnel = Tunnel()


def tunnel() -> Tunnel:
    return _tunnel


# -- the workflow ----------------------------------------------------------------------------


def _step(on_step: StepFn | None, link: CarLink, step: str, status: str, detail: str = "") -> None:
    link.steps.append({"step": step, "status": status, "detail": detail, "ts": time.time()})
    if on_step is not None:
        try:
            on_step(step, status, detail)
        except Exception as exc:  # the report never stops the workflow
            logger.debug("on_step failed: %s", exc)


def _car_wifi_ipv4(ssh_host: str, user: str, key: str) -> str | None:
    """The car's own IPv4 on its Wi-Fi, read over SSH (the TLS console listens there, not on lo)."""
    try:
        out = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=8",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-i",
                key,
                f"{user}@{ssh_host}",
                "ip -4 -o addr show scope global",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] != "lo" and not parts[1].startswith("usb"):
            return parts[3].split("/")[0]
    return None


def connect(
    *,
    host: str | None = None,
    on_step: StepFn | None = None,
    probe: Callable[[str], bool] | None = None,
    allow_tunnel: bool = True,
) -> CarLink:
    """Find the car and choose the wire. Returns a :class:`CarLink`; never raises for a missing car."""
    link = CarLink()
    probe = probe or discover.reachable
    mac = os.environ.get("DEEPRACER_MAC", "")
    mdns = os.environ.get("DEEPRACER_MDNS", "")
    user = os.environ.get("DEEPRACER_SSH_USER", "deepracer")
    key = os.path.expanduser(os.environ.get("DEEPRACER_SSH_KEY", "~/.ssh/id_ed25519_deepracer"))
    configured = (host or os.environ.get("DEEPRACER_HOST", "")).strip()
    if configured in ("127.0.0.1", "localhost") and os.environ.get("DEEPRACER_SSH_HOST"):
        configured = os.environ["DEEPRACER_SSH_HOST"]  # a previous tunnel; look for the car itself

    if _tunnel.alive and _tunnel.target != (configured if configured != "auto" else _tunnel.target):
        _tunnel.close()  # a tunnel to some other car; a live one to this car is reused below

    # 1. USB-C cable
    _step(on_step, link, "usb", "running", "looking for the car on its USB-C link (10.0.0.1)")
    usb = discover.usb_otg_host(probe)
    if usb:
        _step(on_step, link, "usb", "ok", f"car answers at {usb}")
        found, how = usb, "usb"
    else:
        _step(on_step, link, "usb", "skip", "no USB link")
        found, how = None, ""

    # 2. a configured address that still answers
    if found is None and configured and configured != "auto":
        _step(on_step, link, "configured", "running", f"probing {configured}")
        if probe(configured):
            found, how = configured, "configured"
            _step(on_step, link, "configured", "ok", f"{configured} answers")
        else:
            _step(on_step, link, "configured", "fail", f"{configured} does not answer on 22/9090")

    # 3. discovery by MAC / mDNS / sweep / neighbour table
    if found is None:
        plan = f"MAC {mac or '?'}, mDNS {mdns or '?'}: ARP, mDNS, IPv6 neighbours, sweep"
        _step(on_step, link, "discover", "running", plan)
        res = discover.find_car(mac=mac or None, mdns=mdns or None, probe=probe)
        if res is None:
            _step(on_step, link, "discover", "fail", "car not found on this network")
            link.error = "car not found"
            return link
        found, how = res
        _step(on_step, link, "discover", "ok", f"car at {found} via {how}")

    link.ssh_host = found
    link.found_by = how
    v6 = discover.is_ipv6(found)

    # 4. rosbridge: direct when it answers on the found address, else a tunnel over SSH
    _step(on_step, link, "rosbridge", "running", f"probing rosbridge on {found}:{ROSBRIDGE_PORT}")
    if discover.reachable(found, ports=(ROSBRIDGE_PORT,), timeout=1.5):
        link.host = found
        link.how = "usb" if how == "usb" else "direct"
        link.rosbridge_port = ROSBRIDGE_PORT
        link.console_url = f"https://{discover.url_host(found)}"
        _step(on_step, link, "rosbridge", "ok", f"direct ws://{discover.url_host(found)}:{ROSBRIDGE_PORT}")
    elif allow_tunnel and discover.reachable(found, ports=(22,), timeout=1.5):
        why = "rosbridge listens on IPv4 only on the car" if v6 else "rosbridge not reachable directly"
        _step(on_step, link, "rosbridge", "skip", f"{why}; opening an SSH tunnel")
        via = f"ssh -N -L {TUNNEL_ROSBRIDGE_PORT},{TUNNEL_CONSOLE_PORT} {user}@{found}"
        _step(on_step, link, "tunnel", "running", via)
        reused = (
            _tunnel.alive
            and _tunnel.target == found
            and discover.reachable("127.0.0.1", ports=(TUNNEL_ROSBRIDGE_PORT,), timeout=0.5)
        )
        console_target = (
            _tunnel.console_target if reused else (_car_wifi_ipv4(found, user, key) or "127.0.0.1")
        )
        if reused:
            ok = True  # a live tunnel to the same car: keep it, and the shared rosbridge connection with it
        else:
            try:
                ok = _tunnel.open(found, user=user, key=key, console_target=console_target)
            except RuntimeError as exc:
                ok = False
                _step(on_step, link, "tunnel", "fail", str(exc))
        if not ok:
            _step(on_step, link, "tunnel", "fail", "tunnel did not come up (key login? host key?)")
            link.error = "tunnel failed"
            return link
        link.host = "127.0.0.1"
        link.how = "tunnel"
        link.rosbridge_port = TUNNEL_ROSBRIDGE_PORT
        link.console_url = f"https://127.0.0.1:{TUNNEL_CONSOLE_PORT}"
        done = f"rosbridge on 127.0.0.1:{TUNNEL_ROSBRIDGE_PORT}, console via {console_target}"
        _step(on_step, link, "tunnel", "ok", done + (" (reused)" if reused else ""))
    else:
        _step(on_step, link, "rosbridge", "fail", "neither rosbridge nor ssh answers")
        link.error = "no rosbridge"
        return link

    # 5. a real rosbridge handshake, timed
    _step(on_step, link, "handshake", "running", "roslibpy handshake")
    try:
        from deepracer_agent.transport import RosbridgeTransport, kick_reconnect

        apply_env(link)
        if kick_reconnect(link.host, link.rosbridge_port):
            _step(on_step, link, "handshake", "running", "re-dialing the process-wide rosbridge connection")
        t = RosbridgeTransport(host=link.host, port=link.rosbridge_port, timeout=HANDSHAKE_TIMEOUT_S)
        status = t.status()
        t.close()
        link.rtt_ms = status.get("rtt_ms") if isinstance(status, dict) else None
        if isinstance(status, dict) and status.get("connected"):
            _step(on_step, link, "handshake", "ok", f"connected, rtt {link.rtt_ms} ms")
        else:
            _step(on_step, link, "handshake", "fail", str(status)[:160])
            link.error = "rosbridge handshake failed"
            return link
    except Exception as exc:
        _step(on_step, link, "handshake", "fail", f"{type(exc).__name__}: {exc}")
        link.error = "rosbridge handshake failed"
        return link

    # 6. the console (camera)
    _step(on_step, link, "console", "running", f"login at {link.console_url}")
    try:
        from deepracer_agent.tools import ConsoleClient

        c = ConsoleClient(base_url=link.console_url)
        ok = c.login() or (time.sleep(1.0) or c.login())  # the console drops the first login after a restart
        # No frame-rate probe here: the runtime's shared camera stream owns the MJPEG route.
        fps = None
        c.close()
        if ok:
            _step(on_step, link, "console", "ok", f"camera {fps if fps is not None else '?'} fps")
        else:
            _step(on_step, link, "console", "fail", "login failed (password? TLS listener?)")
    except Exception as exc:
        _step(on_step, link, "console", "fail", f"{type(exc).__name__}: {exc}")

    apply_env(link)
    return link


def disconnect() -> None:
    _tunnel.close()
    for key in ("DEEPRACER_SSH_HOST",):
        os.environ.pop(key, None)


# -- the USB stick with the Wi-Fi credentials -----------------------------------------------------

WIFI_CREDS = "wifi-creds.txt"
DEVICE_STATUS = "device-status.txt"


def external_volumes() -> list[Path]:
    """Mounted removable volumes (macOS ``/Volumes/*`` that are not the system disk; Linux ``/media``)."""
    user = os.environ.get("USER", "")
    roots = [Path("/Volumes"), Path("/media") / user, Path("/run/media") / user]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            try:
                if p.is_symlink() or not p.is_dir() or p.name in ("Macintosh HD",):
                    continue
                if not os.access(p, os.W_OK):
                    continue
                out.append(p)
            except OSError:
                continue
    return out


def write_wifi_creds(ssid: str, password: str, volumes: list[Path] | None = None) -> list[Path]:
    """``wifi-creds.txt`` in the stock format on every writable removable volume; returns the paths."""
    if not ssid.strip():
        raise ValueError("ssid is required")
    text = f'ssid: "{ssid}"\npassword: "{password}"\n'
    written: list[Path] = []
    for vol in volumes if volumes is not None else external_volumes():
        try:
            target = vol / WIFI_CREDS
            target.write_text(text, encoding="utf-8")
            written.append(target)
        except OSError as exc:
            logger.warning("could not write %s: %s", vol, exc)
    return written


def read_device_status(volumes: list[Path] | None = None) -> dict[str, str]:
    """``device-status.txt`` from every removable volume that has one (the car's connection report)."""
    out: dict[str, str] = {}
    for vol in volumes if volumes is not None else external_volumes():
        p = vol / DEVICE_STATUS
        if p.is_file():
            try:
                out[str(vol)] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out
