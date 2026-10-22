"""Find the car on whatever network the laptop is on today.

DHCP hands the DeepRacer a new address on every network (hotel, venue, travel router), and
on 2026-10-14 a phone even took its old address at home. Nothing in this project should
carry an IP: ``DEEPRACER_HOST=auto`` (or a host that no longer answers) resolves through
three steps, cheapest first:

1. the laptop's ARP table, looking for the car's Wi-Fi MAC (``DEEPRACER_MAC``), which never
   changes (under a second, works on any shared subnet);
2. the car's mDNS name (``DEEPRACER_MDNS``, e.g. ``amss-abcd.local``), when the network
   passes multicast and the car's firewall lets avahi answer (a dead lookup costs 2 s, so
   it is not first);
3. a one-second ping sweep of the laptop's /24 to populate the ARP table, then step 1 again.

The result is written back to ``os.environ["DEEPRACER_HOST"]`` so every later reader
(rosbridge, console URL, SSH helpers) agrees. The shell twin is
``car/connect/find-car.sh``. Nothing here moves the car.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)

PROBE_PORTS = (22, 9090)
ARP_LINE = re.compile(r"\((?P<ip>\d+\.\d+\.\d+\.\d+)\)\s+at\s+(?P<mac>[0-9a-fA-F:]{11,17})")
ARP_LINE_LINUX = re.compile(r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+\S+\s+(?P<mac>[0-9a-fA-F:]{17})", re.M)

Runner = Callable[[list[str]], str]


def normalise_mac(mac: str) -> str:
    """``02:00:00:AB:CD:EF`` and macOS's zero-dropped ``2:8d:42:46:9c:7`` to one lower-case form."""
    parts = mac.strip().replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"not a MAC address: {mac!r}")
    return ":".join(f"{int(p, 16):02x}" for p in parts)


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def reachable(host: str, ports: Iterable[int] = PROBE_PORTS, timeout: float = 1.0) -> bool:
    """True when ``host`` accepts a TCP connection on any of ``ports``."""
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def resolve_mdns(name: str, timeout: float = 2.0) -> str | None:
    """IPv4 for an mDNS name, or None; bounded, because a dead resolver can hang for 5 s."""
    if not name:
        return None

    def lookup() -> str | None:
        try:
            infos = socket.getaddrinfo(name, None, socket.AF_INET)
        except OSError:
            return None
        return infos[0][4][0] if infos else None

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(lookup).result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return None  # the resolver thread is abandoned; a context manager would wait for it
    finally:
        pool.shutdown(wait=False)


def arp_table(run: Runner | None = None) -> dict[str, str]:
    """``{mac: ip}`` from ``arp -a`` (macOS/BSD) or ``ip neigh`` (Linux), MACs normalised."""
    run = run or _run
    table: dict[str, str] = {}
    text = run(["arp", "-a", "-n"]) or run(["arp", "-a"])
    for m in ARP_LINE.finditer(text):
        try:
            table[normalise_mac(m.group("mac"))] = m.group("ip")
        except ValueError:
            continue
    if not table and sys.platform.startswith("linux"):
        for m in ARP_LINE_LINUX.finditer(run(["ip", "neigh"])):
            table[normalise_mac(m.group("mac"))] = m.group("ip")
    return table


#: The stock image's USB-C OTG network: the car is a USB Ethernet adapter at this address.
USB_OTG_HOSTS: tuple[str, ...] = ("10.0.0.1", "10.0.1.1")


def is_ipv6(host: str) -> bool:
    return ":" in host and not host.startswith("[")


def url_host(host: str) -> str:
    """``host`` as it goes into a URL: IPv6 literals get brackets (scope ids are percent-encoded)."""
    if is_ipv6(host):
        return "[" + host.replace("%", "%25") + "]"
    return host


def ndp_table(run: Runner | None = None) -> dict[str, list[str]]:
    """MAC -> IPv6 addresses from the neighbour table (``ndp -an`` on macOS, ``ip -6 neigh`` on Linux).

    Global addresses come first, link-local (with its ``%iface`` scope) last, so a caller that
    takes the first entry gets the one that works in a URL without a scope id.
    """
    run = run or _run
    out: dict[str, list[str]] = {}
    text = run(["ndp", "-an"]) or run(["ip", "-6", "neigh"])
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        addr, mac = None, None
        if parts[0].lower().startswith(("neighbor", "neighbour")):
            continue
        if "lladdr" in parts:  # linux: <addr> dev <if> lladdr <mac> <state>
            addr = parts[0]
            mac = parts[parts.index("lladdr") + 1]
            dev = parts[parts.index("dev") + 1] if "dev" in parts else ""
            if addr.lower().startswith("fe80") and dev and "%" not in addr:
                addr = f"{addr}%{dev}"
        else:  # macOS: <addr> <mac> <if> <expire> <state> ...
            addr, mac = parts[0], parts[1]
        if not addr or not mac or ":" not in mac or "incomplete" in mac:
            continue
        try:
            key = normalise_mac(mac)
        except ValueError:
            continue
        out.setdefault(key, []).append(addr)
    for addrs in out.values():
        addrs.sort(key=lambda a: a.lower().startswith("fe80"))
    return out


def wake_ipv6_neighbours(run: Runner | None = None) -> None:
    """Ping the all-nodes multicast group on every Wi-Fi/Ethernet interface so the table fills."""
    run = run or _run
    for iface in _ipv6_interfaces(run):
        if sys.platform == "darwin":
            run(["ping6", "-c", "1", "-I", iface, f"ff02::1%{iface}"])
        else:
            run(["ping", "-6", "-c", "1", "-I", iface, "ff02::1"])


def _ipv6_interfaces(run: Runner | None = None) -> list[str]:
    run = run or _run
    text = run(["ifconfig"]) if sys.platform == "darwin" else run(["ip", "-6", "-br", "addr"])
    names: list[str] = []
    for line in text.splitlines():
        if sys.platform == "darwin":
            if line and not line.startswith((" ", "\t")) and line.startswith(("en", "eth", "wlan")):
                names.append(line.split(":")[0])
        elif line.startswith(("en", "eth", "wlan")) and "UP" in line:
            names.append(line.split()[0])
    return names


def resolve_mdns6(name: str, timeout: float = 2.0) -> str | None:
    """``name.local`` as an IPv6 address (the stock car's avahi announces IPv6 only on some links)."""
    if not name:
        return None

    def lookup() -> str | None:
        try:
            infos = socket.getaddrinfo(name, None, socket.AF_INET6, socket.SOCK_STREAM)
        except OSError:
            return None
        addrs = [str(i[4][0]) for i in infos]
        addrs.sort(key=lambda a: a.lower().startswith("fe80"))
        return addrs[0] if addrs else None

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(lookup).result(timeout=timeout)
    except Exception:
        return None
    finally:
        pool.shutdown(wait=False)


def usb_otg_host(probe: Callable[[str], bool] = reachable) -> str | None:
    """The car over its USB-C cable, if the laptop has that link up."""
    for host in USB_OTG_HOSTS:
        if probe(host):
            return host
    return None


def local_ipv4() -> str | None:
    """The laptop's address on its default route (no packet is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1: never routed, only picks the interface
            return s.getsockname()[0]
    except OSError:
        return None


def sweep(prefix: str, run: Runner | None = None, hosts: Iterable[int] = range(1, 255)) -> None:
    """Ping every address in ``prefix``.x once, in parallel, so the ARP table fills."""
    run = run or _run
    ping = ["ping", "-c", "1", "-W", "300"] if sys.platform == "darwin" else ["ping", "-c", "1", "-W", "1"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(lambda h: run([*ping, f"{prefix}.{h}"]), hosts))


def find_car(
    *,
    mac: str | None,
    mdns: str | None,
    run: Runner | None = None,
    probe: Callable[[str], bool] = reachable,
    mdns_resolver: Callable[[str], str | None] = resolve_mdns,
    local_ip: Callable[[], str | None] = local_ipv4,
) -> tuple[str, str] | None:
    """``(ip, how)`` for the car, or None. ``how`` is ``arp``, ``mdns`` or ``sweep``."""
    run = run or _run
    want = normalise_mac(mac) if mac else None
    usb = usb_otg_host(probe)
    if usb:
        return usb, "usb"
    if want is not None:
        ip = arp_table(run).get(want)
        if ip and probe(ip):
            return ip, "arp"
    if mdns:
        ip = mdns_resolver(mdns)
        if ip and probe(ip):
            return ip, "mdns"
        ip6 = resolve_mdns6(mdns)
        if ip6 and probe(ip6):
            return ip6, "mdns6"
    if want is not None:
        for attempt in range(2):
            for addr in ndp_table(run).get(want, []):
                if probe(addr):
                    return addr, "ndp"
            if attempt == 0:
                wake_ipv6_neighbours(run)
    if want is None:
        return None
    me = local_ip()
    if not me:
        return None
    prefix = me.rsplit(".", 1)[0]
    sweep(prefix, run)
    ip = arp_table(run).get(want)
    if ip and probe(ip):
        return ip, "sweep"
    return None


_cache: dict[str, str] = {}


def resolve_host(default: str = "127.0.0.1", *, probe: Callable[[str], bool] = reachable) -> str:
    """``DEEPRACER_HOST`` as a host that answers today.

    Sim (``DEEPRACER_BODY`` not ``car``) returns the variable untouched. On ``car``, a value of
    ``auto``, empty, or one that no longer answers on 22/9090 is replaced by :func:`find_car`
    using ``DEEPRACER_MAC`` / ``DEEPRACER_MDNS``; the answer is cached in the environment so
    the console URL and the SSH helpers see the same host. When nothing is found the
    configured value is returned and the connection error that follows names it.
    """
    configured = os.environ.get("DEEPRACER_HOST", "").strip()
    if os.environ.get("DEEPRACER_BODY", "sim") != "car":
        return configured or default
    if configured and configured != "auto":
        if configured in _cache.values() or probe(configured):
            return configured
        logger.warning("DEEPRACER_HOST=%s does not answer; looking for the car", configured)
    key = configured or "auto"
    if key in _cache:
        return _cache[key]
    found = find_car(mac=os.environ.get("DEEPRACER_MAC"), mdns=os.environ.get("DEEPRACER_MDNS"), probe=probe)
    if found is None:
        logger.error(
            "car not found (DEEPRACER_HOST=%s, DEEPRACER_MAC=%s, DEEPRACER_MDNS=%s)",
            configured,
            os.environ.get("DEEPRACER_MAC"),
            os.environ.get("DEEPRACER_MDNS"),
        )
        return configured or default
    ip, how = found
    logger.info("car found at %s via %s", ip, how)
    _cache[key] = ip
    os.environ["DEEPRACER_HOST"] = ip
    return ip


def main(argv: list[str] | None = None) -> int:
    """``python -m deepracer_agent.discover``: print the car's IP, exit 1 when not found."""
    import argparse

    parser = argparse.ArgumentParser(description="Find the DeepRacer on this network.")
    parser.add_argument("--mac", default=os.environ.get("DEEPRACER_MAC"))
    parser.add_argument("--mdns", default=os.environ.get("DEEPRACER_MDNS"))
    args = parser.parse_args(argv)
    found = find_car(mac=args.mac, mdns=args.mdns)
    if found is None:
        print("car not found", file=sys.stderr)
        return 1
    print(found[0])
    print(f"via {found[1]}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
