"""Finding the car when DHCP moved it: mDNS, ARP by MAC, sweep; sim is never touched."""

from __future__ import annotations

from typing import Any

import pytest

from deepracer_agent import discover

ARP_MAC = """? (192.168.0.1) at 30:68:93:32:49:45 on en0 ifscope [ethernet]
? (192.168.0.2) at 02:00:00:ab:cd:ef on en0 ifscope [ethernet]
? (192.168.0.6) at 2:8d:42:46:9c:7 on en0 ifscope permanent [ethernet]
? (169.254.169.254) at (incomplete) on en0 [ethernet]
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("02:00:00:AB:CD:EF", "02:00:00:ab:cd:ef"),
        ("2:8d:42:46:9c:7", "02:8d:42:46:9c:07"),
        ("02-00-00-ab-cd-ef", "02:00:00:ab:cd:ef"),
    ],
)
def test_normalise_mac(raw: str, expected: str) -> None:
    assert discover.normalise_mac(raw) == expected


@pytest.mark.parametrize("bad", ["", "02:00:00", "not a mac", "02:00:00:ab:cd:ef:00"])
def test_refusal_table_normalise_mac(bad: str) -> None:
    with pytest.raises(ValueError):
        discover.normalise_mac(bad)


def test_arp_table_normalises_macos_zero_dropped_octets() -> None:
    table = discover.arp_table(lambda cmd: ARP_MAC)
    assert table["02:00:00:ab:cd:ef"] == "192.168.0.2"
    assert table["02:8d:42:46:9c:07"] == "192.168.0.6"
    assert len(table) == 3  # the incomplete entry is skipped


def test_find_car_takes_the_arp_table_first() -> None:
    """A dead mDNS lookup costs 2 s; the ARP table is sub-second, so it goes first."""
    found = discover.find_car(
        mac="02:00:00:AB:CD:EF",
        mdns="amss-abcd.local",
        run=lambda cmd: ARP_MAC,
        probe=lambda ip: ip == "192.168.0.2",
        mdns_resolver=lambda name: pytest.fail("mDNS must not be asked when ARP answers"),
        local_ip=lambda: "192.168.0.6",
    )
    assert found == ("192.168.0.2", "arp")


def test_find_car_uses_mdns_when_the_arp_table_is_cold() -> None:
    found = discover.find_car(
        mac="02:00:00:ab:cd:ef",
        mdns="amss-abcd.local",
        run=lambda cmd: "",  # cold ARP table, no sweep needed
        probe=lambda ip: ip == "192.168.0.9",
        mdns_resolver=lambda name: "192.168.0.9",
        local_ip=lambda: "192.168.0.6",
    )
    assert found == ("192.168.0.9", "mdns")


def test_find_car_mdns_only_without_a_mac() -> None:
    found = discover.find_car(
        mac=None,
        mdns="amss-abcd.local",
        probe=lambda ip: ip.startswith("192.168."),
        mdns_resolver=lambda name: "192.168.0.9",
    )
    assert found == ("192.168.0.9", "mdns")


def test_find_car_sweeps_then_reads_arp_again() -> None:
    calls: list[list[str]] = []
    state = {"swept": False}

    def run(cmd: list[str]) -> str:
        calls.append(cmd)
        if cmd[0] == "ping":
            state["swept"] = True
            return ""
        return ARP_MAC if state["swept"] else ""

    found = discover.find_car(
        mac="02:00:00:ab:cd:ef",
        mdns=None,
        run=run,
        probe=lambda ip: ip.startswith("192.168."),
        mdns_resolver=lambda name: None,
        local_ip=lambda: "10.42.0.7",
    )
    assert found == ("192.168.0.2", "sweep")
    pings = [c for c in calls if c[0] == "ping"]
    assert len(pings) == 254 and all(c[-1].startswith("10.42.0.") for c in pings)


def test_find_car_without_mac_or_mdns_is_none() -> None:
    assert discover.find_car(mac=None, mdns=None, run=lambda cmd: ARP_MAC) is None


def test_resolve_host_leaves_sim_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPRACER_BODY", "sim")
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    assert discover.resolve_host("127.0.0.1", probe=lambda h: pytest.fail("sim must not probe")) == "auto"
    monkeypatch.delenv("DEEPRACER_HOST")
    assert discover.resolve_host("127.0.0.1") == "127.0.0.1"


def test_resolve_host_keeps_a_configured_host_that_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPRACER_BODY", "car")
    monkeypatch.setenv("DEEPRACER_HOST", "192.168.0.7")
    monkeypatch.setattr(discover, "_cache", {})
    assert discover.resolve_host(probe=lambda h: h == "192.168.0.7") == "192.168.0.7"


def test_resolve_host_replaces_a_stale_host_and_writes_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPRACER_BODY", "car")
    monkeypatch.setenv("DEEPRACER_HOST", "192.168.0.7")
    monkeypatch.setenv("DEEPRACER_MAC", "02:00:00:ab:cd:ef")
    monkeypatch.delenv("DEEPRACER_MDNS", raising=False)
    monkeypatch.setattr(discover, "_cache", {})
    monkeypatch.setattr(discover, "_run", lambda cmd: ARP_MAC)
    monkeypatch.setattr(discover, "local_ipv4", lambda: "192.168.0.6")
    probes: list[str] = []

    def probe(h: str) -> bool:
        probes.append(h)
        return h == "192.168.0.2"

    assert discover.resolve_host(probe=probe) == "192.168.0.2"
    assert probes[0] == "192.168.0.7"
    assert discover.resolve_host(probe=probe) == "192.168.0.2"  # cached: no second search
    import os

    assert os.environ["DEEPRACER_HOST"] == "192.168.0.2"


def test_resolve_host_returns_configured_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPRACER_BODY", "car")
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_MAC", raising=False)
    monkeypatch.delenv("DEEPRACER_MDNS", raising=False)
    monkeypatch.setattr(discover, "_cache", {})
    assert discover.resolve_host("127.0.0.1", probe=lambda h: False) == "auto"


def test_env_host_and_console_url_follow_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    from deepracer_agent.tools import env_console_url
    from deepracer_agent.transport import env_host

    monkeypatch.setenv("DEEPRACER_BODY", "car")
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_CONSOLE_URL", raising=False)
    monkeypatch.setattr(discover, "_cache", {"auto": "192.168.0.2"})
    assert env_host() == "192.168.0.2"
    assert env_console_url() == "https://192.168.0.2"
    monkeypatch.setenv("DEEPRACER_CONSOLE_URL", "https://car.example/")
    assert env_console_url() == "https://car.example"


def test_main_prints_ip(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(discover, "find_car", lambda **kw: ("192.168.0.2", "arp"))
    assert discover.main(["--mac", "02:00:00:ab:cd:ef"]) == 0
    assert capsys.readouterr().out.strip() == "192.168.0.2"
    monkeypatch.setattr(discover, "find_car", lambda **kw: None)
    assert discover.main([]) == 1
