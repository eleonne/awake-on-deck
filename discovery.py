"""Discover PCs on the local network.

Two methods are combined:

1. NetBIOS node status query (UDP 137): Windows PCs reply with their computer
   name and the MAC address of the adapter that answered.
2. TCP scan of the subnet on the poll port, with MAC addresses read from the
   OS ARP table and names from reverse DNS. Catches PCs that don't answer
   NetBIOS.

Only PCs that are switched on can be found. The local subnet is assumed to be
a /24, which covers virtually all home networks.
"""

from __future__ import annotations

import ipaddress
import logging
import random
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SUBNET_PREFIX = 24
NETBIOS_PORT = 137
NETBIOS_TIMEOUT_SECONDS = 2.0
SCAN_TIMEOUT_SECONDS = 1.0
SCAN_WORKERS = 128

# First-level encoded wildcard name "*" padded with NULs (RFC 1002 4.1)
_NBSTAT_NAME = b"\x20" + b"CK" + b"A" * 30 + b"\x00"
_NBSTAT_TYPE = 0x0021
_IN_CLASS = 0x0001
_NAME_ENTRY_SIZE = 18
_GROUP_NAME_FLAG = 0x8000

_ARP_A_LINE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\s"
)


class DiscoveryError(Exception):
    """Raised when network discovery cannot run at all."""


@dataclass(frozen=True)
class DiscoveredPC:
    ip: str
    name: str = ""
    mac: str = ""  # "AA-BB-CC-DD-EE-FF", or "" when unknown
    port_open: bool = False  # answered on the poll TCP port


# ── Subnet helpers ────────────────────────────────────────────────────────────


def local_ipv4() -> str:
    """Return this device's LAN IPv4 address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connecting a UDP socket sends nothing; it just selects the route
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
    except OSError as exc:
        raise DiscoveryError(f"Could not determine local IP address: {exc}") from exc

    if ip.startswith("127.") or ip == "0.0.0.0":
        raise DiscoveryError("Not connected to a network")
    return ip


def subnet_hosts(local_ip: str, prefix: int = SUBNET_PREFIX) -> List[str]:
    """All host addresses in the local subnet except this device."""
    network = ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False)
    return [str(h) for h in network.hosts() if str(h) != local_ip]


def broadcast_address(ip: str, prefix: int = SUBNET_PREFIX) -> str:
    """Broadcast address of the subnet containing `ip`."""
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False).broadcast_address)


# ── MAC helpers ───────────────────────────────────────────────────────────────


def format_mac(raw: bytes) -> str:
    """Format 6 raw bytes as AA-BB-CC-DD-EE-FF; "" for missing or all-zero."""
    if len(raw) != 6 or not any(raw):
        return ""
    return "-".join(f"{b:02X}" for b in raw)


def normalize_mac(text: str) -> str:
    """Normalize a ':' or '-' separated MAC to AA-BB-CC-DD-EE-FF.

    Returns "" for malformed, all-zero, broadcast and multicast addresses.
    """
    parts = re.split(r"[-:]", text.strip())
    if len(parts) != 6:
        return ""
    try:
        raw = bytes(int(p, 16) for p in parts)
    except ValueError:
        return ""
    if raw[0] & 0x01:  # multicast / broadcast bit
        return ""
    return format_mac(raw)


# ── Method 1: NetBIOS node status ─────────────────────────────────────────────


def build_nbstat_request(transaction_id: int) -> bytes:
    """NetBIOS node status request for the wildcard name."""
    header = struct.pack(">HHHHHH", transaction_id, 0x0000, 1, 0, 0, 0)
    return header + _NBSTAT_NAME + struct.pack(">HH", _NBSTAT_TYPE, _IN_CLASS)


def parse_nbstat_response(data: bytes, transaction_id: int) -> Optional[Tuple[str, str]]:
    """Parse a node status response into (computer name, MAC).

    Returns None if the packet is not a valid response to our request.
    """
    try:
        tid, flags, _qd, answers, _ns, _ar = struct.unpack_from(">HHHHHH", data, 0)
        if tid != transaction_id or not flags & 0x8000 or answers < 1:
            return None

        offset = 12
        if data[offset] & 0xC0 == 0xC0:  # compressed name pointer
            offset += 2
        else:
            while data[offset] != 0:
                offset += data[offset] + 1
            offset += 1

        rtype, _rclass, _ttl, _rdlength = struct.unpack_from(">HHIH", data, offset)
        offset += 10
        if rtype != _NBSTAT_TYPE:
            return None

        count = data[offset]
        offset += 1
        name = ""
        for _ in range(count):
            entry = data[offset:offset + _NAME_ENTRY_SIZE]
            if len(entry) < _NAME_ENTRY_SIZE:
                return None
            suffix = entry[15]
            (name_flags,) = struct.unpack_from(">H", entry, 16)
            # Suffix 0x00 unique name is the workstation (computer) name
            if not name and suffix == 0x00 and not name_flags & _GROUP_NAME_FLAG:
                name = entry[:15].decode("ascii", "replace").rstrip(" \x00")
            offset += _NAME_ENTRY_SIZE

        mac = format_mac(data[offset:offset + 6])
        return name, mac
    except (struct.error, IndexError):
        return None


def netbios_query(
    hosts: Sequence[str],
    cancel: threading.Event,
    timeout: float = NETBIOS_TIMEOUT_SECONDS,
) -> Dict[str, Tuple[str, str]]:
    """Send a node status request to every host; return {ip: (name, mac)}."""
    transaction_id = random.randint(1, 0xFFFF)
    packet = build_nbstat_request(transaction_id)
    wanted = set(hosts)
    results: Dict[str, Tuple[str, str]] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:
        raise DiscoveryError(f"Could not open UDP socket: {exc}") from exc

    with sock:
        for ip in hosts:
            if cancel.is_set():
                return results
            try:
                sock.sendto(packet, (ip, NETBIOS_PORT))
            except OSError as exc:
                logger.debug("NetBIOS send to %s failed: %s", ip, exc)

        deadline = time.monotonic() + timeout
        while not cancel.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(remaining, 0.2))
            try:
                data, (ip, _port) = sock.recvfrom(1024)
            except OSError:
                # Timeout, or on Windows an ICMP "port unreachable" from a host
                # without NetBIOS surfacing as a connection reset; keep listening
                continue
            if ip not in wanted:
                continue
            parsed = parse_nbstat_response(data, transaction_id)
            if parsed is not None:
                logger.debug("NetBIOS reply from %s: %s", ip, parsed)
                results[ip] = parsed

    logger.info("NetBIOS query found %d host(s)", len(results))
    return results


# ── Method 2: TCP scan + ARP table ────────────────────────────────────────────


def tcp_scan(
    hosts: Sequence[str],
    port: int,
    cancel: threading.Event,
    timeout: float = SCAN_TIMEOUT_SECONDS,
) -> List[str]:
    """Return the hosts that accept a TCP connection on `port`."""

    def probe(ip: str) -> Optional[str]:
        if cancel.is_set():
            return None
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return ip
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        found = [ip for ip in pool.map(probe, hosts) if ip is not None]

    logger.info("TCP scan on port %d found %d host(s)", port, len(found))
    return found


def parse_proc_net_arp(text: str) -> Dict[str, str]:
    """Parse Linux /proc/net/arp into {ip: mac}."""
    table: Dict[str, str] = {}
    for line in text.splitlines()[1:]:
        cols = line.split()
        if len(cols) < 4:
            continue
        try:
            complete = int(cols[2], 16) & 0x2
        except ValueError:
            continue
        mac = normalize_mac(cols[3])
        if complete and mac:
            table[cols[0]] = mac
    return table


def parse_arp_a(text: str) -> Dict[str, str]:
    """Parse Windows `arp -a` output into {ip: mac}."""
    table: Dict[str, str] = {}
    for line in text.splitlines():
        match = _ARP_A_LINE.match(line)
        if match:
            mac = normalize_mac(match.group(2))
            if mac:
                table[match.group(1)] = mac
    return table


def read_arp_table() -> Dict[str, str]:
    """Read the OS neighbour cache; {} if unavailable."""
    try:
        if sys.platform.startswith("linux"):
            return parse_proc_net_arp(Path("/proc/net/arp").read_text(encoding="ascii"))
        if sys.platform == "win32":
            out = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).stdout
            return parse_arp_a(out)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not read ARP table: %s", exc)
    return {}


def reverse_dns(ip: str) -> str:
    """Short hostname for `ip` via reverse DNS, or ""."""
    try:
        name = socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""
    return "" if name == ip else name.split(".")[0]


# ── Combined ──────────────────────────────────────────────────────────────────


def _sorted(pcs: Dict[str, DiscoveredPC]) -> List[DiscoveredPC]:
    # Named PCs first, then by address
    return sorted(pcs.values(), key=lambda pc: (pc.name == "", ipaddress.ip_address(pc.ip)))


def discover(
    port: int,
    cancel: threading.Event,
    on_update: Optional[Callable[[List[DiscoveredPC]], None]] = None,
) -> List[DiscoveredPC]:
    """Find PCs on the local network.

    `on_update` is called with the full result list after each method
    completes, so callers can show partial results. Returns early with what
    was found so far if `cancel` is set.

    Raises DiscoveryError if the network cannot be scanned at all.
    """
    local_ip = local_ipv4()
    hosts = subnet_hosts(local_ip)
    logger.info("Discovering PCs on %s/%d", local_ip, SUBNET_PREFIX)
    pcs: Dict[str, DiscoveredPC] = {}

    for ip, (name, mac) in netbios_query(hosts, cancel).items():
        pcs[ip] = DiscoveredPC(ip=ip, name=name, mac=mac)
    if cancel.is_set():
        return _sorted(pcs)
    if on_update is not None:
        on_update(_sorted(pcs))

    open_hosts = tcp_scan(hosts, port, cancel)
    if cancel.is_set():
        return _sorted(pcs)

    arp = read_arp_table()
    new_hosts = [ip for ip in open_hosts if ip not in pcs]
    with ThreadPoolExecutor(max_workers=16) as pool:
        names = dict(zip(new_hosts, pool.map(reverse_dns, new_hosts)))

    for ip in open_hosts:
        pc = pcs.get(ip) or DiscoveredPC(ip=ip, name=names.get(ip, ""))
        pcs[ip] = replace(pc, port_open=True)
    for ip, pc in pcs.items():
        if not pc.mac and ip in arp:
            pcs[ip] = replace(pc, mac=arp[ip])

    result = _sorted(pcs)
    if on_update is not None:
        on_update(result)
    return result
