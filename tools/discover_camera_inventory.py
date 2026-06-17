#!/usr/bin/env python3
"""
discover_camera_inventory.py — Airseekers camera inventory helper.

Runs lightweight TCP-connect checks against a given host to detect which
camera-related ports are open, then produces a markdown report that includes:
  1. Port scan summary table
  2. A TEMPLATE table for the owner to fill in after observing app traffic
  3. Guidance on what to do next

This script does NOT guess or invent camera endpoints.
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This tool performs passive TCP-connect checks only (no banner grabbing,
# no exploit attempts, no credential testing, no aggressive sweeps).
# It is intended exclusively for the owner of the Airseekers device under test.
# DO NOT run this tool against devices or networks you do not own or have
# explicit written permission to test.
# Misuse may violate the Computer Fraud and Abuse Act (CFAA), GDPR, and
# equivalent laws in your jurisdiction.
# =============================================================================

import argparse
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORTS = {
    80:   "HTTP",
    443:  "HTTPS",
    554:  "RTSP (standard)",
    8554: "RTSP (alternate)",
    8080: "HTTP alternate",
    8000: "HTTP alternate",
    8888: "HTTP alternate",
}

TEMPLATE_ROWS = [
    ("Front Camera",    "", "", "", ""),
    ("Rear Camera",     "", "", "", ""),
    ("Mapping Camera",  "", "", "", ""),
    ("Obstacle Camera", "", "", "", ""),
    ("Live View (generic)", "", "", "", ""),
]

REPORTS_DIR = Path(__file__).parent / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tcp_connect(host: str, port: int, timeout: float) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def scan_ports(host: str, timeout: float) -> dict[int, bool]:
    results: dict[int, bool] = {}
    for port in PORTS:
        results[port] = tcp_connect(host, port, timeout)
    return results


def md_port_table(results: dict[int, bool]) -> str:
    lines = [
        "| Port | Label | Status |",
        "| ---: | ----- | ------ |",
    ]
    for port, label in PORTS.items():
        status = "open" if results[port] else "closed"
        lines.append(f"| {port} | {label} | {status} |")
    return "\n".join(lines)


def md_template_table() -> str:
    header = (
        "| camera_role | url_or_path | stream_type | auth_required | notes |\n"
        "| ----------- | ----------- | ----------- | ------------- | ----- |"
    )
    rows = "\n".join(
        f"| {role} | {url} | {st} | {auth} | {notes} |"
        for role, url, st, auth, notes in TEMPLATE_ROWS
    )
    note = (
        "> **Note:** Fill in the URL/path after observing the mobile app traffic "
        "with mitmproxy. Do not guess endpoints."
    )
    return f"{header}\n{rows}\n\n{note}"


def build_report(host: str, timeout: float, results: dict[int, bool]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    open_count = sum(1 for v in results.values() if v)

    return f"""# Airseekers Camera Inventory Report

**Host:** `{host}`
**Scan time:** {ts}
**Timeout:** {timeout}s
**Open ports found:** {open_count} / {len(PORTS)}

---

## 1. Port Scan Summary

{md_port_table(results)}

---

## 2. Camera Inventory Template

The table below is a **template only**. No endpoints have been guessed.
Fill in each row after capturing the Airseekers mobile app traffic with
a proxy such as mitmproxy.

{md_template_table()}

---

## 3. Guidance — What To Do Next

### Step A — Capture mobile app traffic with mitmproxy

1. Install mitmproxy on your workstation:
   ```
   pip install mitmproxy
   ```
2. Start the proxy:
   ```
   mitmproxy --listen-port 8888
   ```
3. Configure your phone to use your workstation IP as its HTTP proxy (port 8888).
4. Install the mitmproxy CA certificate on the phone so HTTPS is decrypted.
5. Launch the Airseekers app and navigate to each camera view.
6. In mitmproxy, look for requests whose `Host` matches `{host}` (or a related
   cloud host). Note the full URL, HTTP method, and any auth headers.

### Step B — Probe discovered endpoints

Once you have identified a URL from Step A:

- **RTSP streams:** run `probe_rtsp.py <url>` to test OPTIONS.
- **HTTP MJPEG / snapshots:** run `probe_mjpeg.py --url <url>`.
- **Any URL (auto-classified):** run `probe_camera_url.py --url <url>`.

### Step C — Fill the template above

Edit the "Camera Inventory Template" table with the real URLs and stream types
you discovered, then save this report for reference.

---

*Generated by discover_camera_inventory.py — passive scan only.*
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise camera-related open ports and produce an inventory template.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--host",
        required=True,
        help="IP address or hostname of the Airseekers device (e.g. 192.168.1.50).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        metavar="SECONDS",
        help="TCP connect timeout per port (default: 3).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write a markdown report to tools/reports/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"[*] Scanning {args.host} — checking {len(PORTS)} ports (timeout={args.timeout}s) ...")
    results = scan_ports(args.host, args.timeout)

    # Short stdout summary
    print()
    print(f"{'PORT':<6}  {'LABEL':<22}  STATUS")
    print("-" * 42)
    for port, label in PORTS.items():
        status = "OPEN  " if results[port] else "closed"
        print(f"{port:<6}  {label:<22}  {status}")

    open_ports = [p for p, v in results.items() if v]
    print()
    if open_ports:
        print(f"[+] Open ports: {', '.join(str(p) for p in open_ports)}")
    else:
        print("[!] No camera-related ports appear open from this host.")
    print()
    print("[*] This tool does NOT invent or guess endpoints.")
    print("[*] Use the template table (in the report) after capturing app traffic.")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"discover_camera_inventory_{ts_file}.md"
        report_path.write_text(build_report(args.host, args.timeout, results), encoding="utf-8")
        print(f"\n[+] Report written to: {report_path}")


if __name__ == "__main__":
    main()
