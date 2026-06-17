#!/usr/bin/env python3
"""
probe_rtsp.py — Send a single RTSP OPTIONS request to an owner-supplied URL.

Connects to the RTSP server over a raw TCP socket (pure stdlib), sends
OPTIONS, and reports the response status line and the Public header
(supported methods).  Credentials embedded in the URL are redacted in
all output and in the written report.

Usage:
    python probe_rtsp.py rtsp://192.168.1.50:554/live
    python probe_rtsp.py --url rtsp://192.168.1.50:554/live --report
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This tool sends a single passive RTSP OPTIONS request only.
# It does NOT brute-force credentials, enumerate paths, or replay sessions.
# Use exclusively on devices you own or have explicit written permission to test.
# If the server responds with 401 Unauthorized, the tool stops immediately
# and does NOT attempt any further authentication.
# Misuse may violate the Computer Fraud and Abuse Act (CFAA) and equivalent
# laws in your jurisdiction.
# =============================================================================

import argparse
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPORTS_DIR = Path(__file__).parent / "reports"

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def parse_rtsp_url(raw_url: str) -> tuple[str, int, str, str]:
    """
    Parse an RTSP URL and return (host, port, path, redacted_url).

    Credentials are stripped for network use and replaced with ***:*** in the
    redacted form shown in all output.
    """
    parsed = urlparse(raw_url)

    if parsed.scheme not in ("rtsp", "rtsps"):
        raise ValueError(f"Expected rtsp:// or rtsps:// scheme, got: {parsed.scheme!r}")

    host = parsed.hostname or ""
    port = parsed.port or 554
    path = parsed.path or "/"
    if not path:
        path = "/"

    # Build redacted URL (mask user:pass if present)
    if parsed.username or parsed.password:
        netloc_redacted = f"***:***@{host}:{port}"
    else:
        netloc_redacted = f"{host}:{port}"

    redacted_url = f"rtsp://{netloc_redacted}{path}"
    if parsed.query:
        redacted_url += f"?{parsed.query}"

    return host, port, path, redacted_url


# ---------------------------------------------------------------------------
# Raw RTSP OPTIONS
# ---------------------------------------------------------------------------

def rtsp_options(host: str, port: int, path: str, timeout: float) -> dict:
    """
    Send a single RTSP OPTIONS request and return a dict with:
      - status_line (str)
      - status_code (int)
      - headers (dict[str, str])
      - raw_response (str, first 2 KB max)
      - error (str or None)
    """
    request = (
        f"OPTIONS rtsp://{host}:{port}{path} RTSP/1.0\r\n"
        f"CSeq: 1\r\n"
        f"User-Agent: AirseekersProbe/0.1\r\n"
        f"\r\n"
    )

    result: dict = {
        "status_line": "",
        "status_code": 0,
        "headers": {},
        "raw_response": "",
        "error": None,
    }

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except (ConnectionRefusedError, TimeoutError, OSError) as exc:
        result["error"] = f"Connection failed: {exc}"
        return result

    try:
        sock.settimeout(timeout)
        sock.sendall(request.encode("ascii"))

        # Read until end of headers (\r\n\r\n) or up to 4 KB
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 4096:
            chunk = sock.recv(512)
            if not chunk:
                break
            buf += chunk
    except (socket.timeout, OSError) as exc:
        result["error"] = f"Read error: {exc}"
        return result
    finally:
        sock.close()

    raw = buf.decode("ascii", errors="replace")
    result["raw_response"] = raw[:2048]

    lines = raw.split("\r\n")
    if not lines:
        result["error"] = "Empty response"
        return result

    result["status_line"] = lines[0]
    # Parse status code from "RTSP/1.0 200 OK"
    parts = lines[0].split(" ", 2)
    if len(parts) >= 2:
        try:
            result["status_code"] = int(parts[1])
        except ValueError:
            pass

    # Parse headers
    for line in lines[1:]:
        if ": " in line:
            k, _, v = line.partition(": ")
            result["headers"][k.strip()] = v.strip()

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    redacted_url: str,
    host: str,
    port: int,
    timeout: float,
    probe: dict,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    public = probe["headers"].get("Public", probe["headers"].get("public", "_not present_"))

    if probe["error"]:
        outcome = f"**Error:** {probe['error']}"
    elif probe["status_code"] == 401:
        outcome = "**401 Unauthorized** — authentication required. No further attempts made."
    elif probe["status_code"] == 200:
        outcome = f"**200 OK** — server is responding."
    else:
        outcome = f"**Status:** {probe['status_line']}"

    headers_md = "\n".join(
        f"| `{k}` | `{v}` |" for k, v in probe["headers"].items()
    ) or "_no headers parsed_"

    return f"""# RTSP Probe Report

**URL (redacted):** `{redacted_url}`
**Host:** `{host}`
**Port:** `{port}`
**Probe time:** {ts}
**Timeout:** {timeout}s

---

## Result

{outcome}

**Status line:** `{probe['status_line'] or '(none)'}`
**Public (supported methods):** `{public}`

---

## All Response Headers

| Header | Value |
| ------ | ----- |
{headers_md}

---

## Notes

- Only a single OPTIONS request was sent. No credentials were tested.
- If the server returned 401, authentication details are required to proceed.
  Obtain credentials from the device documentation or the Airseekers app.
- Credentials embedded in the original URL have been **redacted** in this report.

---

*Generated by probe_rtsp.py — single OPTIONS request only.*
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a single RTSP OPTIONS request to an owner-supplied URL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "positional_url",
        nargs="?",
        metavar="url",
        help="RTSP URL (positional). Alternative to --url.",
    )
    parser.add_argument(
        "--url",
        metavar="RTSP_URL",
        help="RTSP URL (flag form). Alternative to positional argument.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Socket timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write a markdown report to tools/reports/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    raw_url = args.url or args.positional_url
    if not raw_url:
        print("[!] Error: provide an RTSP URL as a positional argument or via --url.", file=sys.stderr)
        sys.exit(1)

    try:
        host, port, path, redacted_url = parse_rtsp_url(raw_url)
    except ValueError as exc:
        print(f"[!] Invalid URL: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Probing (RTSP OPTIONS): {redacted_url}")
    print(f"    host={host}  port={port}  path={path}  timeout={args.timeout}s")

    probe = rtsp_options(host, port, path, args.timeout)

    print()
    if probe["error"]:
        print(f"[!] {probe['error']}")
    else:
        print(f"[+] Status line : {probe['status_line']}")
        public = probe["headers"].get("Public", probe["headers"].get("public"))
        if public:
            print(f"[+] Public      : {public}")
        else:
            print("[~] Public header not present in response.")

        if probe["status_code"] == 401:
            print()
            print("[!] 401 Unauthorized — authentication required. No further attempts made.")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"probe_rtsp_{ts_file}.md"
        report_path.write_text(
            build_report(redacted_url, host, port, args.timeout, probe),
            encoding="utf-8",
        )
        print(f"\n[+] Report written to: {report_path}")


if __name__ == "__main__":
    main()
