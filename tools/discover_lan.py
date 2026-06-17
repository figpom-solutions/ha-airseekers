#!/usr/bin/env python3
"""
discover_lan.py — Non-intrusive LAN host discovery for Airseekers robot.

Tries three passive/semi-passive methods in order:
  1. mDNS via zeroconf (lazy import)
  2. SSDP via UDP multicast (stdlib)
  3. ARP table read (parse `ip neigh` / `arp -a`, read-only)

Optionally performs a light TCP-connect check against a curated port list
when --host is provided or a host is discovered, but ONLY with explicit user
awareness (a warning is printed before any TCP SYN packets are sent).
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This script is intentionally non-intrusive:
#   - It reads the local ARP/neighbour table (no packets sent for this step).
#   - It sends a single standard SSDP M-SEARCH multicast (normal LAN traffic).
#   - mDNS browsing listens passively on the multicast group.
#   - TCP port scanning ONLY occurs when the user explicitly passes --host
#     or acknowledges a discovered IP.  A clear warning is printed first.
#   - NO brute-force, NO credential guessing, NO aggressive sweeps.
#   - NO writes to any device.
#   - Authorization / secret headers are never logged.
# Use only on networks and devices you own or have explicit permission to test.
# =============================================================================

import argparse
import datetime
import ipaddress
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 3  # seconds to wait for SSDP responses

DEFAULT_PORTS = "80,443,1883,8883,8080,8554,554,8888"
PORT_LABELS: dict[int, str] = {
    80: "HTTP",
    443: "HTTPS",
    1883: "MQTT",
    8883: "MQTT-TLS",
    8080: "HTTP-alt",
    8554: "RTSP-alt",
    554: "RTSP",
    8888: "HTTP-alt2",
}

REPORTS_DIR = Path(__file__).parent / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _redact(value: str) -> str:
    """Redact secrets: keep first 3 chars, replace the rest with ***."""
    if not value:
        return value
    if len(value) <= 3:
        return "***"
    return value[:3] + "***"


# ---------------------------------------------------------------------------
# 1. mDNS discovery (lazy zeroconf import)
# ---------------------------------------------------------------------------

def discover_mdns(timeout: float) -> list[dict]:
    """Browse mDNS for common service types; return list of host dicts."""
    try:
        from zeroconf import ServiceBrowser, Zeroconf  # type: ignore
        from zeroconf._utils.ipaddress import get_ip_address_object  # type: ignore
    except ImportError:
        print(
            "[mDNS] zeroconf not installed — skipping.\n"
            "       To enable: pip install zeroconf"
        )
        return []

    results: list[dict] = []
    service_types = [
        "_http._tcp.local.",
        "_https._tcp.local.",
        "_mqtt._tcp.local.",
        "_rtsp._tcp.local.",
    ]

    class Listener:
        def add_service(self, zc: "Zeroconf", type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name, timeout=int(timeout * 1000))
            if info:
                addresses = [
                    str(ipaddress.ip_address(a)) for a in info.parsed_addresses()
                ]
                results.append(
                    {
                        "source": "mDNS",
                        "name": name,
                        "type": type_,
                        "addresses": addresses,
                        "port": info.port,
                        "server": info.server,
                    }
                )

        def remove_service(self, *_) -> None:
            pass

        def update_service(self, *_) -> None:
            pass

    zc = Zeroconf()
    listener = Listener()
    browsers = [ServiceBrowser(zc, st, listener) for st in service_types]  # noqa: F841
    time.sleep(timeout)
    zc.close()
    return results


# ---------------------------------------------------------------------------
# 2. SSDP discovery (stdlib only)
# ---------------------------------------------------------------------------

def discover_ssdp(timeout: float) -> list[dict]:
    """Send a single SSDP M-SEARCH and collect responses."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"MX: {SSDP_MX}\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    ).encode()

    results: list[dict] = []
    seen: set[str] = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)
    try:
        sock.sendto(msg, (SSDP_ADDR, SSDP_PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                ip = addr[0]
                if ip in seen:
                    continue
                seen.add(ip)
                text = data.decode(errors="replace")
                location = ""
                server_hdr = ""
                for line in text.splitlines():
                    ll = line.lower()
                    if ll.startswith("location:"):
                        location = line.split(":", 1)[1].strip()
                    if ll.startswith("server:"):
                        server_hdr = line.split(":", 1)[1].strip()
                results.append(
                    {
                        "source": "SSDP",
                        "ip": ip,
                        "location": location,
                        "server": server_hdr,
                    }
                )
            except socket.timeout:
                break
    finally:
        sock.close()

    return results


# ---------------------------------------------------------------------------
# 3. ARP table read (read-only, no packets)
# ---------------------------------------------------------------------------

def read_arp_table() -> list[dict]:
    """Read local ARP/neighbour table; no packets sent."""
    results: list[dict] = []

    # Try `ip neigh` first (Linux)
    try:
        out = subprocess.check_output(
            ["ip", "neigh"], stderr=subprocess.DEVNULL, text=True
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1] == "dev":
                state = parts[-1] if parts else "UNKNOWN"
                ip = parts[0]
                mac = parts[4] if len(parts) > 4 else ""
                results.append(
                    {"source": "ARP/ip-neigh", "ip": ip, "mac": mac, "state": state}
                )
        return results
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback: `arp -a` (macOS / older Linux)
    try:
        out = subprocess.check_output(
            ["arp", "-a"], stderr=subprocess.DEVNULL, text=True
        )
        for line in out.splitlines():
            # Format: hostname (ip) at mac [ether] on iface
            parts = line.split()
            ip = ""
            mac = ""
            hostname = ""
            for i, p in enumerate(parts):
                if p.startswith("(") and p.endswith(")"):
                    ip = p.strip("()")
                    hostname = parts[i - 1] if i > 0 else ""
                if p == "at" and i + 1 < len(parts):
                    mac = parts[i + 1]
            if ip:
                results.append(
                    {
                        "source": "ARP/arp-a",
                        "ip": ip,
                        "hostname": hostname,
                        "mac": mac,
                    }
                )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return results


# ---------------------------------------------------------------------------
# 4. Light TCP-connect check (only on explicit --host or user-confirmed IP)
# ---------------------------------------------------------------------------

def tcp_connect_check(host: str, ports: list[int], timeout: float) -> list[dict]:
    """
    Attempt TCP connect to each port on host.

    WARNING: This sends real TCP SYN packets to the target host.
    Only call after printing the warning to the user.
    """
    results: list[dict] = []
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                results.append(
                    {
                        "port": port,
                        "label": PORT_LABELS.get(port, "unknown"),
                        "status": "open",
                    }
                )
        except (ConnectionRefusedError, socket.timeout, OSError):
            results.append(
                {
                    "port": port,
                    "label": PORT_LABELS.get(port, "unknown"),
                    "status": "closed/filtered",
                }
            )
    return results


# ---------------------------------------------------------------------------
# Reverse-DNS helper
# ---------------------------------------------------------------------------

def reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    report_path: Path,
    mdns_results: list[dict],
    ssdp_results: list[dict],
    arp_results: list[dict],
    tcp_results: dict[str, list[dict]],
    args: argparse.Namespace,
) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# LAN Discovery Report",
        f"\n**Generated:** {ts}",
        f"**Timeout:** {args.timeout}s",
        f"**Explicit host:** {args.host or '(none)'}",
        "",
    ]

    # mDNS
    lines += ["## mDNS Results", ""]
    if mdns_results:
        for r in mdns_results:
            lines.append(
                f"- **{r.get('name', '')}** ({r.get('type', '')}) "
                f"— addresses: {', '.join(r.get('addresses', []))} "
                f"port {r.get('port', '')} server: `{r.get('server', '')}`"
            )
    else:
        lines.append("_No mDNS results._")
    lines.append("")

    # SSDP
    lines += ["## SSDP Results", ""]
    if ssdp_results:
        for r in ssdp_results:
            lines.append(
                f"- **{r['ip']}** — server: `{r.get('server', '')}` "
                f"location: `{r.get('location', '')}`"
            )
    else:
        lines.append("_No SSDP results._")
    lines.append("")

    # ARP
    lines += ["## ARP Table", ""]
    if arp_results:
        lines.append("| IP | MAC | Hostname | State | Source |")
        lines.append("|---|---|---|---|---|")
        for r in arp_results:
            ip = r.get("ip", "")
            mac = r.get("mac", "")
            hostname = r.get("hostname", "") or reverse_dns(ip)
            state = r.get("state", "")
            src = r.get("source", "")
            lines.append(f"| {ip} | {mac} | {hostname} | {state} | {src} |")
    else:
        lines.append("_ARP table empty or unavailable._")
    lines.append("")

    # TCP
    if tcp_results:
        lines += ["## TCP Port Check", ""]
        lines.append(
            "> **Note:** TCP SYN packets were sent to the hosts below. "
            "Only ports in the curated list were tested."
        )
        lines.append("")
        for host, checks in tcp_results.items():
            lines.append(f"### Host: `{host}`")
            lines.append("")
            lines.append("| Port | Service | Status |")
            lines.append("|---|---|---|")
            for c in checks:
                lines.append(f"| {c['port']} | {c['label']} | {c['status']} |")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover robot host on the LAN (non-intrusive)."
    )
    parser.add_argument(
        "--timeout", type=float, default=3.0, help="Discovery timeout in seconds (default: 3)"
    )
    parser.add_argument(
        "--host",
        default="",
        help="Optional explicit host IP/name; enables TCP port check with warning.",
    )
    parser.add_argument(
        "--ports",
        default=DEFAULT_PORTS,
        help=f"Comma-separated port list for TCP check (default: {DEFAULT_PORTS})",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Override report output path (default: tools/reports/discover_lan_<timestamp>.md)",
    )
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]

    print("=== Airseekers LAN Discovery ===")
    print(f"Timeout: {args.timeout}s | Ports: {ports}")
    print()

    # --- mDNS ---
    print("[1/3] mDNS browsing...")
    mdns_results = discover_mdns(args.timeout)
    print(f"      Found {len(mdns_results)} mDNS service(s).")

    # --- SSDP ---
    print("[2/3] SSDP M-SEARCH multicast...")
    ssdp_results = discover_ssdp(args.timeout)
    print(f"      Found {len(ssdp_results)} SSDP device(s).")

    # --- ARP ---
    print("[3/3] Reading ARP/neighbour table (read-only)...")
    arp_results = read_arp_table()
    print(f"      Found {len(arp_results)} ARP entr(y/ies).")

    # --- TCP check ---
    tcp_results: dict[str, list[dict]] = {}
    candidate_hosts: list[str] = []
    if args.host:
        candidate_hosts = [args.host]
    # Optionally, a future enhancement could ask user to confirm discovered IPs.

    if candidate_hosts:
        print()
        print(
            "*** WARNING: TCP port check is about to send TCP SYN packets to the "
            "following host(s): " + ", ".join(candidate_hosts)
        )
        print(
            "    This is a light connectivity check, NOT a full scan. "
            "Only the curated port list is tested."
        )
        for h in candidate_hosts:
            print(f"    Checking {h}...")
            tcp_results[h] = tcp_connect_check(h, ports, args.timeout)
            open_ports = [c for c in tcp_results[h] if c["status"] == "open"]
            print(
                f"    {h}: {len(open_ports)} open port(s) out of {len(ports)} checked."
            )

    # --- Report ---
    _ensure_reports_dir()
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = REPORTS_DIR / f"discover_lan_{_timestamp()}.md"

    write_report(report_path, mdns_results, ssdp_results, arp_results, tcp_results, args)

    print()
    print(f"Report written to: {report_path}")

    # Short stdout summary
    total = len(mdns_results) + len(ssdp_results) + len(arp_results)
    print(
        f"\nSummary: {len(mdns_results)} mDNS, {len(ssdp_results)} SSDP, "
        f"{len(arp_results)} ARP entries — {total} total hosts/services discovered."
    )
    if tcp_results:
        for h, checks in tcp_results.items():
            open_p = [str(c["port"]) for c in checks if c["status"] == "open"]
            print(f"  TCP {h}: open ports = {', '.join(open_p) or 'none'}")


if __name__ == "__main__":
    main()
