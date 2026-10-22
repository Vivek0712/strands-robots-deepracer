"""connect: the wire-finding workflow with every network shape faked; the USB stick helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from deepracer_agent import connect, discover


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """``connect.apply_env`` writes the car's address into os.environ; keep it inside each test."""
    for key, value in (
        ("DEEPRACER_HOST", "auto"),
        ("DEEPRACER_SSH_HOST", ""),
        ("DEEPRACER_ROSBRIDGE_PORT", "9091"),
        ("DEEPRACER_CONSOLE_URL", "http://127.0.0.1:8090"),
        ("DEEPRACER_BODY", "sim"),
    ):
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(discover, "_cache", {})


NDP_MAC = """Neighbor                        Linklayer Address  Netif Expire    St Flgs Prbs
2001:db8:4a:fb72:1675:5306:9c62:a82c 02:00:00:ab:cd:ef   en0 23h59m51s S  R
fe80::541:706c:c9bd:5944%en0    02:00:00:ab:cd:ef   en0 23h59m51s S  R
fe80::c4f7:c1ff:fe8b:3364%en0   c6:f7:c1:8b:33:64   en0 23h59m51s S  R
fe80::1%lo0                     (incomplete)        lo0 permanent R
"""

IP_NEIGH = """2001:db8:4a:fb72::9 dev wlan0 lladdr 02:00:00:ab:cd:ef REACHABLE
fe80::541:706c:c9bd:5944 dev wlan0 lladdr 02:00:00:ab:cd:ef STALE
"""


def test_ndp_table_parses_macos_and_puts_global_addresses_first():
    table = discover.ndp_table(run=lambda cmd: NDP_MAC if cmd[0] == "ndp" else "")
    assert table["02:00:00:ab:cd:ef"] == [
        "2001:db8:4a:fb72:1675:5306:9c62:a82c",
        "fe80::541:706c:c9bd:5944%en0",
    ]
    assert "c6:f7:c1:8b:33:64" in table and len(table) == 2


def test_ndp_table_parses_linux_and_scopes_link_local():
    table = discover.ndp_table(run=lambda cmd: IP_NEIGH if cmd[0] == "ip" else "")
    assert table["02:00:00:ab:cd:ef"] == ["2001:db8:4a:fb72::9", "fe80::541:706c:c9bd:5944%wlan0"]


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("10.0.0.1", "10.0.0.1"),
        ("fe80::1%en0", "[fe80::1%25en0]"),
        ("2409::9", "[2409::9]"),
        ("[::1]", "[::1]"),
    ],
)
def test_url_host_brackets_ipv6(host, expected):
    assert discover.url_host(host) == expected


def test_find_car_prefers_usb_then_arp_then_ndp(monkeypatch):
    calls: list[str] = []

    def probe(host: str) -> bool:
        calls.append(host)
        return host in ("10.0.0.1",)

    assert discover.find_car(mac="02:00:00:ab:cd:ef", mdns=None, run=lambda c: "", probe=probe) == (
        "10.0.0.1",
        "usb",
    )

    def probe_v6(host: str) -> bool:
        return host.startswith("2001")

    found = discover.find_car(
        mac="02:00:00:AB:CD:EF",
        mdns=None,
        run=lambda cmd: NDP_MAC if cmd[0] == "ndp" else "",
        probe=probe_v6,
        mdns_resolver=lambda name: None,
        local_ip=lambda: None,
    )
    assert found == ("2001:db8:4a:fb72:1675:5306:9c62:a82c", "ndp")


class FakeTunnel:
    def __init__(self, ok: bool = True, target: str = "") -> None:
        self.ok = ok
        self.opened: list[str] = []
        self.closed = 0
        self.proc = None
        self.target = target
        self.console_target = "127.0.0.1"

    @property
    def alive(self) -> bool:
        return (bool(self.opened) or bool(self.target)) and self.ok

    def open(self, ssh_host: str, **kw) -> bool:
        self.opened.append(ssh_host)
        self.target = ssh_host
        self.console_target = kw.get("console_target", "127.0.0.1")
        return self.ok

    def close(self) -> None:
        self.closed += 1


def _patch_endpoints(monkeypatch, *, handshake=True, console=True):
    class T:
        def __init__(self, host=None, port=None, **kw):
            self.host, self.port = host, port

        def status(self):
            return {"connected": handshake, "rtt_ms": 12.0}

        def close(self):
            pass

    class C:
        def __init__(self, base_url=None, **kw):
            self.base_url = base_url

        def login(self):
            return console

        def frame_rate(self, s):
            return 20.0

        def close(self):
            pass

    import deepracer_agent.tools as tools
    import deepracer_agent.transport as transport

    monkeypatch.setattr(transport, "RosbridgeTransport", T)
    monkeypatch.setattr(tools, "ConsoleClient", C)


def test_connect_direct_ipv4(monkeypatch):
    monkeypatch.setenv("DEEPRACER_MAC", "02:00:00:ab:cd:ef")
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_SSH_HOST", raising=False)
    monkeypatch.setattr(connect, "_tunnel", FakeTunnel())
    monkeypatch.setattr(discover, "usb_otg_host", lambda probe: None)
    monkeypatch.setattr(discover, "find_car", lambda **kw: ("192.168.0.2", "arp"))
    monkeypatch.setattr(
        discover, "reachable", lambda host, ports=(22, 9090), timeout=1.0: host == "192.168.0.2"
    )
    _patch_endpoints(monkeypatch)
    steps: list[tuple[str, str]] = []
    link = connect.connect(on_step=lambda s, st, d: steps.append((s, st)), probe=lambda h: h == "192.168.0.2")
    assert link.connected and link.how == "direct" and link.host == "192.168.0.2" and link.found_by == "arp"
    assert link.console_url == "https://192.168.0.2" and link.rtt_ms == 12.0
    assert ("rosbridge", "ok") in steps and ("handshake", "ok") in steps and ("console", "ok") in steps
    assert (
        link.export()["DEEPRACER_HOST"] == "192.168.0.2"
        and link.export()["DEEPRACER_ROSBRIDGE_PORT"] == "9090"
    )


def test_connect_ipv6_opens_a_tunnel(monkeypatch):
    monkeypatch.setenv("DEEPRACER_MAC", "02:00:00:ab:cd:ef")
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_SSH_HOST", raising=False)
    tunnel = FakeTunnel()
    monkeypatch.setattr(connect, "_tunnel", tunnel)
    monkeypatch.setattr(discover, "usb_otg_host", lambda probe: None)
    v6 = "2001:db8:4a:fb72:1675:5306:9c62:a82c"
    monkeypatch.setattr(discover, "find_car", lambda **kw: (v6, "ndp"))
    # rosbridge (9090) does not answer on IPv6; ssh (22) does
    monkeypatch.setattr(
        discover, "reachable", lambda host, ports=(22, 9090), timeout=1.0: 22 in tuple(ports) and host == v6
    )
    monkeypatch.setattr(connect, "_car_wifi_ipv4", lambda host, user, key: "172.20.10.9")
    _patch_endpoints(monkeypatch)
    steps: list[tuple[str, str]] = []
    link = connect.connect(on_step=lambda s, st, d: steps.append((s, st)), probe=lambda h: h == v6)
    assert link.connected and link.how == "tunnel" and link.host == "127.0.0.1" and link.ssh_host == v6
    assert link.rosbridge_port == connect.TUNNEL_ROSBRIDGE_PORT
    assert link.console_url == f"https://127.0.0.1:{connect.TUNNEL_CONSOLE_PORT}"
    assert tunnel.opened == [v6] and ("tunnel", "ok") in steps
    assert link.export()["DEEPRACER_SSH_HOST"] == v6


def test_connect_reports_a_missing_car(monkeypatch):
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_SSH_HOST", raising=False)
    monkeypatch.setattr(connect, "_tunnel", FakeTunnel())
    monkeypatch.setattr(discover, "usb_otg_host", lambda probe: None)
    monkeypatch.setattr(discover, "find_car", lambda **kw: None)
    steps: list[tuple[str, str]] = []
    link = connect.connect(on_step=lambda s, st, d: steps.append((s, st)), probe=lambda h: False)
    assert not link.connected and link.error == "car not found" and link.export() == {}
    assert steps[-1] == ("discover", "fail")


def test_connect_tunnel_failure_is_reported(monkeypatch):
    monkeypatch.setenv("DEEPRACER_HOST", "auto")
    monkeypatch.delenv("DEEPRACER_SSH_HOST", raising=False)
    monkeypatch.setattr(connect, "_tunnel", FakeTunnel(ok=False))
    monkeypatch.setattr(discover, "usb_otg_host", lambda probe: None)
    v6 = "fe80::1%en0"
    monkeypatch.setattr(discover, "find_car", lambda **kw: (v6, "ndp"))
    monkeypatch.setattr(discover, "reachable", lambda host, ports=(22, 9090), timeout=1.0: 22 in tuple(ports))
    monkeypatch.setattr(connect, "_car_wifi_ipv4", lambda host, user, key: None)
    link = connect.connect(probe=lambda h: True)
    assert not link.connected and link.error == "tunnel failed"


def test_wifi_creds_written_in_the_stock_format_and_report_read(tmp_path: Path):
    vol = tmp_path / "STICK"
    vol.mkdir()
    written = connect.write_wifi_creds("Vivek", "secret", [vol])
    assert written == [vol / "wifi-creds.txt"]
    assert (vol / "wifi-creds.txt").read_text() == 'ssid: "Vivek"\npassword: "secret"\n'
    assert connect.read_device_status([vol]) == {}
    (vol / "device-status.txt").write_text("Hostname: amss-abcd\nNot connected to WiFi network.\n")
    assert "Not connected" in connect.read_device_status([vol])[str(vol)]
    with pytest.raises(ValueError):
        connect.write_wifi_creds("  ", "x", [vol])


def test_connect_reuses_a_live_tunnel_to_the_same_car(monkeypatch):
    v6 = "2001:db8:4a:fb72:1675:5306:9c62:a82c"
    monkeypatch.setenv("DEEPRACER_HOST", v6)
    tunnel = FakeTunnel(target=v6)
    tunnel.console_target = "172.20.10.9"
    monkeypatch.setattr(connect, "_tunnel", tunnel)
    monkeypatch.setattr(discover, "usb_otg_host", lambda probe: None)

    def reachable(host, ports=(22, 9090), timeout=1.0):
        if host == v6:
            return 22 in tuple(ports)
        return host == "127.0.0.1" and connect.TUNNEL_ROSBRIDGE_PORT in tuple(ports)

    monkeypatch.setattr(discover, "reachable", reachable)
    monkeypatch.setattr(
        connect, "_car_wifi_ipv4", lambda *a: pytest.fail("ssh must not run for a reused tunnel")
    )
    _patch_endpoints(monkeypatch)
    steps: list[tuple[str, str, str]] = []
    link = connect.connect(on_step=lambda s, st, d: steps.append((s, st, d)), probe=lambda h: h == v6)
    assert link.connected and link.how == "tunnel" and link.found_by == "configured"
    assert tunnel.opened == [] and tunnel.closed == 0
    assert any(s == "tunnel" and st == "ok" and "reused" in d for s, st, d in steps)
