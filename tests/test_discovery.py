"""Tests for discovery.py."""

import socket
import struct
import threading

import pytest

import discovery
from discovery import (
    DiscoveredPC,
    DiscoveryError,
    broadcast_address,
    build_nbstat_request,
    discover,
    format_mac,
    netbios_query,
    normalize_mac,
    parse_arp_a,
    parse_nbstat_response,
    parse_proc_net_arp,
    subnet_hosts,
    tcp_scan,
)

TID = 0x1234
MAC = bytes.fromhex("aabbcc112233")


def nbstat_response(
    tid: int = TID,
    names: tuple = ((b"GAMING-PC", 0x00, 0x0400), (b"WORKGROUP", 0x00, 0x8400)),
    mac: bytes = MAC,
    compressed_name: bool = False,
) -> bytes:
    header = struct.pack(">HHHHHH", tid, 0x8400, 0, 1, 0, 0)
    rr_name = b"\xc0\x0c" if compressed_name else b"\x20" + b"CK" + b"A" * 30 + b"\x00"
    body = bytes([len(names)])
    for name, suffix, flags in names:
        body += name.ljust(15, b" ") + bytes([suffix]) + struct.pack(">H", flags)
    body += mac + b"\x00" * 40  # rest of the statistics block
    return header + rr_name + struct.pack(">HHIH", 0x21, 1, 0, len(body)) + body


class TestSubnet:
    def test_hosts_exclude_self(self):
        hosts = subnet_hosts("192.168.1.50")
        assert len(hosts) == 253
        assert "192.168.1.50" not in hosts
        assert hosts[0] == "192.168.1.1" and hosts[-1] == "192.168.1.254"

    def test_broadcast(self):
        assert broadcast_address("192.168.1.100") == "192.168.1.255"
        assert broadcast_address("10.0.5.9") == "10.0.5.255"


class TestLocalIpv4:
    def test_raises_typed_error_on_socket_failure(self, mocker):
        mocker.patch("discovery.socket.socket", side_effect=OSError("no network"))
        with pytest.raises(DiscoveryError):
            discovery.local_ipv4()

    def test_raises_on_loopback(self, mocker):
        sock = mocker.MagicMock()
        sock.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 0)
        mocker.patch("discovery.socket.socket", return_value=sock)
        with pytest.raises(DiscoveryError):
            discovery.local_ipv4()


class TestMac:
    def test_format(self):
        assert format_mac(MAC) == "AA-BB-CC-11-22-33"

    def test_format_zero_or_short_is_empty(self):
        assert format_mac(b"\x00" * 6) == ""
        assert format_mac(b"\x01\x02") == ""

    def test_normalize(self):
        assert normalize_mac("aa:bb:cc:11:22:33") == "AA-BB-CC-11-22-33"
        assert normalize_mac("aa-bb-cc-11-22-33") == "AA-BB-CC-11-22-33"

    def test_normalize_rejects_bad_broadcast_multicast(self):
        assert normalize_mac("nonsense") == ""
        assert normalize_mac("ff-ff-ff-ff-ff-ff") == ""
        assert normalize_mac("01-00-5e-00-00-fb") == ""
        assert normalize_mac("00:00:00:00:00:00") == ""


class TestNbstat:
    def test_request_layout(self):
        pkt = build_nbstat_request(TID)
        assert pkt[:2] == b"\x12\x34"
        assert pkt[12] == 0x20 and pkt[13:15] == b"CK"
        assert pkt[-4:] == b"\x00\x21\x00\x01"
        assert len(pkt) == 12 + 34 + 4

    def test_parse_name_and_mac(self):
        assert parse_nbstat_response(nbstat_response(), TID) == ("GAMING-PC", "AA-BB-CC-11-22-33")

    def test_parse_compressed_rr_name(self):
        data = nbstat_response(compressed_name=True)
        assert parse_nbstat_response(data, TID) == ("GAMING-PC", "AA-BB-CC-11-22-33")

    def test_skips_group_names(self):
        data = nbstat_response(names=((b"WORKGROUP", 0x00, 0x8400), (b"DESKTOP", 0x00, 0x0400)))
        assert parse_nbstat_response(data, TID)[0] == "DESKTOP"

    def test_zero_mac_is_unknown(self):
        assert parse_nbstat_response(nbstat_response(mac=b"\x00" * 6), TID) == ("GAMING-PC", "")

    def test_wrong_transaction_id(self):
        assert parse_nbstat_response(nbstat_response(tid=1), TID) is None

    def test_truncated(self):
        assert parse_nbstat_response(nbstat_response()[:60], TID) is None
        assert parse_nbstat_response(b"\x12", TID) is None


class TestNetbiosQuery:
    def _socket(self, mocker, replies):
        sock = mocker.MagicMock()
        sock.__enter__.return_value = sock
        pending = list(replies)

        def recvfrom(_size):
            item = pending.pop(0) if pending else socket.timeout()
            if isinstance(item, BaseException):
                raise item
            return item

        sock.recvfrom.side_effect = recvfrom
        mocker.patch("discovery.socket.socket", return_value=sock)
        mocker.patch("discovery.random.randint", return_value=TID)
        return sock

    def test_collects_replies_and_ignores_errors(self, mocker):
        sock = self._socket(mocker, [
            ConnectionResetError(),  # Windows ICMP unreachable
            (nbstat_response(), ("192.168.1.10", 137)),
            (nbstat_response(), ("8.8.8.8", 137)),  # not one of our hosts
            (b"garbage", ("192.168.1.11", 137)),
        ])
        result = netbios_query(["192.168.1.10", "192.168.1.11"], threading.Event(), timeout=0.3)
        assert result == {"192.168.1.10": ("GAMING-PC", "AA-BB-CC-11-22-33")}
        assert sock.sendto.call_count == 2

    def test_send_failure_is_not_fatal(self, mocker):
        sock = self._socket(mocker, [])
        sock.sendto.side_effect = OSError("unreachable")
        assert netbios_query(["192.168.1.10"], threading.Event(), timeout=0.1) == {}

    def test_socket_failure_raises_typed_error(self, mocker):
        mocker.patch("discovery.socket.socket", side_effect=OSError("denied"))
        with pytest.raises(DiscoveryError):
            netbios_query(["192.168.1.10"], threading.Event())

    def test_cancel_stops_sending(self, mocker):
        sock = self._socket(mocker, [])
        cancel = threading.Event()
        cancel.set()
        assert netbios_query(["192.168.1.10"], cancel) == {}
        sock.sendto.assert_not_called()


class TestTcpScan:
    def test_returns_hosts_that_accept(self, mocker):
        def fake_connect(addr, timeout):
            if addr[0] == "192.168.1.20":
                return mocker.MagicMock()
            raise OSError("refused")

        mocker.patch("discovery.socket.create_connection", side_effect=fake_connect)
        hosts = ["192.168.1.10", "192.168.1.20", "192.168.1.30"]
        assert tcp_scan(hosts, 445, threading.Event()) == ["192.168.1.20"]

    def test_cancelled_scan_probes_nothing(self, mocker):
        connect = mocker.patch("discovery.socket.create_connection")
        cancel = threading.Event()
        cancel.set()
        assert tcp_scan(["192.168.1.10"], 445, cancel) == []
        connect.assert_not_called()


class TestArpParsing:
    def test_proc_net_arp(self):
        text = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.1.100    0x1         0x2         aa:bb:cc:11:22:33     *        wlan0\n"
            "192.168.1.30     0x1         0x0         00:00:00:00:00:00     *        wlan0\n"
        )
        assert parse_proc_net_arp(text) == {"192.168.1.100": "AA-BB-CC-11-22-33"}

    def test_arp_a(self):
        text = (
            "\nInterface: 192.168.1.50 --- 0x5\n"
            "  Internet Address      Physical Address      Type\n"
            "  192.168.1.1           aa-bb-cc-dd-ee-01     dynamic\n"
            "  192.168.1.100         aa-bb-cc-11-22-33     dinâmico\n"
            "  192.168.1.255         ff-ff-ff-ff-ff-ff     static\n"
            "  224.0.0.22            01-00-5e-00-00-16     static\n"
        )
        assert parse_arp_a(text) == {
            "192.168.1.1": "AA-BB-CC-DD-EE-01",
            "192.168.1.100": "AA-BB-CC-11-22-33",
        }


class TestDiscover:
    @pytest.fixture
    def network(self, mocker):
        mocker.patch("discovery.local_ipv4", return_value="192.168.1.50")
        mocker.patch("discovery.netbios_query", return_value={
            "192.168.1.100": ("GAMING-PC", "AA-BB-CC-11-22-33"),
            "192.168.1.40": ("NAS", ""),
        })
        mocker.patch("discovery.tcp_scan", return_value=["192.168.1.100", "192.168.1.40", "192.168.1.7"])
        mocker.patch("discovery.read_arp_table", return_value={
            "192.168.1.40": "AA-AA-AA-AA-AA-40",
            "192.168.1.7": "AA-AA-AA-AA-AA-07",
        })
        mocker.patch("discovery.reverse_dns", side_effect=lambda ip: "")

    def test_merges_both_methods(self, network):
        updates = []
        result = discover(445, threading.Event(), on_update=updates.append)
        assert result == [
            DiscoveredPC("192.168.1.40", "NAS", "AA-AA-AA-AA-AA-40", True),
            DiscoveredPC("192.168.1.100", "GAMING-PC", "AA-BB-CC-11-22-33", True),
            DiscoveredPC("192.168.1.7", "", "AA-AA-AA-AA-AA-07", True),
        ]
        assert len(updates) == 2
        assert {pc.ip for pc in updates[0]} == {"192.168.1.100", "192.168.1.40"}
        assert updates[1] == result

    def test_netbios_only_pc_marked_port_closed(self, network, mocker):
        mocker.patch("discovery.tcp_scan", return_value=[])
        result = discover(445, threading.Event())
        assert all(not pc.port_open for pc in result)

    def test_cancel_after_netbios_skips_scan(self, network, mocker):
        cancel = threading.Event()
        scan = mocker.patch("discovery.tcp_scan")
        discovery.netbios_query.side_effect = lambda *a, **k: (cancel.set(), {})[1]
        assert discover(445, cancel) == []
        scan.assert_not_called()
