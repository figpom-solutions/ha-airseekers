#!/usr/bin/env python3
"""
discover_camera_streams.py — Light TCP connectivity check for camera-related
ports on a target host.

Tests a curated list of camera-related ports using TCP connect only.
Reports which ports are open (TCP handshake succeeded).

This tool ONLY tests TCP connectivity.
It does NOT enumerate paths or send protocol-specific data beyond the TCP
handshake.
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This script sends TCP SYN packets to the listed ports on the target host.
# It does NOT:
#   - Send any application-layer data (no HTTP requests, no RTSP DESCRIBE, etc.)
#   - Enumerate URL paths or stream names
#   - Perform brute-force authentication
#   - Log, store, or transmit any credentials or Authorization headers
#   - Write or publish anything to the target device
# Use only on hosts you own or have explicit permission to test.
# =============================================================================

import argparse
import datetime
import socket
import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"

# Curated camera-related port list with labels
DEFAULT_CAMERA_PORTS: list[tuple[int, str]] = [
    (80, "HTTP"),
    (443, "HTTPS"),
    (554, "RTSP"),
    (8554, "RTSP-alt"),
    (8080, "HTTP-alt"),
    (8000, "HTTP-alt2"),
    (8888, "HTTP-alt3"),
]

DEFAULT_PORTS_STR = ",".join(str(p) for p, _ in DEFAULT_CAMERA_PORTS)

# Build lookup from port to label for the curated list
_PORT_LABELS: dict[int, str] = {p: lbl for p, lbl in DEFAULT_CAMERA_PORTS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# TCP connect check
# ---------------------------------------------------------------------------

def tcp_check(host: str, port: int, label: str, timeout: float) -> dict:
    """
    Attempt TCP connect to (host, port).
    Returns a result dict.
    """
    result = {
        "port": port,
        "label": label,
        "status": "closed/filtered",
        "error": None,
    }
    try:
        with socket.create_connection((host, port), timeout=timeout):
            result["status"] = "open"
    except ConnectionRefusedError:
        result["status"] = "closed (refused)"
    except socket.timeout:
        result["status"] = "filtered (timeout)"
    except OSError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    report_path: Path,
    results: list[dict],
    args: argparse.Namespace,
) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    open_ports = [r for r in results if r["status"] == "open"]

    lines = [
        "# Camera Stream Discovery Report",
        f"\n**Generated:** {ts}",
        f"**Target host:** `{args.host}`",
        f"**Ports tested:** {args.ports}",
        f"**Timeout:** {args.timeout}s",
        "",
        "> **Scope note:** This tool only tests TCP connectivity. It does NOT",
        "> enumerate paths or send protocol-specific data beyond the TCP handshake.",
        "",
        "## Results",
        "",
        f"**Open ports found: {len(open_ports)}/{len(results)}**",
        "",
        "| Port | Service Label | Status |",
        "|---|---|---|",
    ]

    for r in results:
        lines.append(f"| {r['port']} | {r['label']} | {r['status']} |")

    lines.append("")

    if open_ports:
        lines += ["## Open Ports Summary", ""]
        for r in open_ports:
            lines.append(f"- **{r['port']}** ({r['label']}): OPEN")
        lines.append("")
        lines.append(
            "> Next step: use a dedicated protocol tool (e.g. ffprobe for RTSP, "
            "probe_http.py for HTTP) to query open ports. This script does not do that."
        )
    else:
        lines.append("_No open ports detected._")

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "TCP connectivity check for camera-related ports. "
            "Does NOT send protocol data beyond the TCP handshake."
        )
    )
    parser.add_argument("--host", required=True, help="Target host IP or hostname")
    parser.add_argument(
        "--ports",
        default=DEFAULT_PORTS_STR,
        help=(
            f"Comma-separated port list (default: {DEFAULT_PORTS_STR}). "
            "Override replaces the full default list."
        ),
    )
    parser.add_argument(
        "--timeout", type=float, default=3.0, help="TCP connect timeout per port in seconds (default: 3)"
    )
    parser.add_argument(
        "--report",
        default="",
        help="Override report output path",
    )
    args = parser.parse_args()

    # Parse ports; look up labels from curated list or fall back to "unknown"
    raw_ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    port_pairs = [(p, _PORT_LABELS.get(p, "unknown")) for p in raw_ports]

    print(f"=== Camera Stream Discovery: {args.host} ===")
    print()
    print(
        "Note: This tool only tests TCP connectivity. "
        "It does NOT enumerate paths or send protocol-specific data "
        "beyond the TCP handshake."
    )
    print()

    results: list[dict] = []
    for port, label in port_pairs:
        r = tcp_check(args.host, port, label, args.timeout)
        status_str = r["status"].upper()
        print(f"  Port {port:5d} ({label:<12}): {status_str}")
        results.append(r)

    _ensure_reports_dir()
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = REPORTS_DIR / f"discover_camera_streams_{_timestamp()}.md"

    write_report(report_path, results, args)
    print(f"\nReport written to: {report_path}")

    open_ports = [r for r in results if r["status"] == "open"]
    print(
        f"\nSummary: {len(open_ports)}/{len(results)} port(s) open on {args.host}."
    )
    if open_ports:
        labels = ", ".join(f"{r['port']} ({r['label']})" for r in open_ports)
        print(f"  Open: {labels}")


if __name__ == "__main__":
    main()
