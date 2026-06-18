#!/usr/bin/env python3
"""
probe_camera_url.py — Test an owner-supplied URL and classify its stream type.

Dispatches based on URL scheme:
  rtsp://  → sends a single RTSP OPTIONS request (raw TCP socket, no credentials tested)
  http://
  https:// → sends a single GET request and classifies by Content-Type:
               multipart/x-mixed-replace → MJPEG stream
               image/jpeg / image/png    → snapshot
               application/vnd.apple.mpegurl or .m3u8 extension → HLS
               other                    → unknown (raw Content-Type shown)

Credentials embedded in the URL are redacted in all output and the report.

Usage:
    python probe_camera_url.py --url rtsp://192.168.1.50:554/live --report
    python probe_camera_url.py --url http://192.168.1.50:8080/snapshot.jpg
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This tool issues a single passive probe (RTSP OPTIONS or HTTP GET) only.
# It does NOT brute-force credentials, enumerate paths, or attempt exploits.
# Use exclusively on devices you own or have explicit written permission to test.
# If an RTSP server returns 401, the tool stops immediately.
# At most 4096 bytes of HTTP body are read — it will not buffer a full stream.
# Misuse may violate the Computer Fraud and Abuse Act (CFAA) and equivalent
# laws in your jurisdiction.
# =============================================================================

import argparse
import contextlib
from datetime import UTC, datetime
from pathlib import Path
import socket
import sys
import urllib.error
from urllib.parse import urlparse, urlunparse
import urllib.request

REPORTS_DIR = Path(__file__).parent / "reports"
MAX_BODY_BYTES = 4096


# ---------------------------------------------------------------------------
# URL helpers (shared)
# ---------------------------------------------------------------------------


def redact_url(raw_url: str) -> str:
    """Replace user:password in URL with ***:***."""
    parsed = urlparse(raw_url)
    if parsed.username or parsed.password:
        netloc = f"***:***@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


def strip_credentials(raw_url: str) -> str:
    """Return URL with credentials removed (safe for use in requests)."""
    parsed = urlparse(raw_url)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


# ---------------------------------------------------------------------------
# RTSP probe (inline — mirrors probe_rtsp.py logic)
# ---------------------------------------------------------------------------


def _rtsp_options(host: str, port: int, path: str, timeout: float) -> dict:
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
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 4096:
            chunk = sock.recv(512)
            if not chunk:
                break
            buf += chunk
    except (TimeoutError, OSError) as exc:
        result["error"] = f"Read error: {exc}"
        return result
    finally:
        sock.close()

    raw = buf.decode("ascii", errors="replace")
    lines = raw.split("\r\n")
    if not lines:
        result["error"] = "Empty response"
        return result

    result["status_line"] = lines[0]
    parts = lines[0].split(" ", 2)
    if len(parts) >= 2:
        with contextlib.suppress(ValueError):
            result["status_code"] = int(parts[1])

    for line in lines[1:]:
        if ": " in line:
            k, _, v = line.partition(": ")
            result["headers"][k.strip()] = v.strip()

    return result


def probe_rtsp(raw_url: str, timeout: float) -> dict:
    parsed = urlparse(raw_url)
    host = parsed.hostname or ""
    port = parsed.port or 554
    path = parsed.path or "/"
    probe = _rtsp_options(host, port, path, timeout)

    public = probe["headers"].get("Public", probe["headers"].get("public", ""))
    if probe["error"]:
        classification = f"Error — {probe['error']}"
    elif probe["status_code"] == 401:
        classification = "RTSP — 401 Unauthorized (auth required)"
    elif probe["status_code"] == 200:
        classification = "RTSP stream endpoint (OPTIONS 200 OK)"
    else:
        classification = f"RTSP — unexpected status {probe['status_code']}"

    return {
        "scheme": "rtsp",
        "status_code": probe["status_code"],
        "status_line": probe["status_line"],
        "content_type": "",
        "classification": classification,
        "extra": {"Public": public} if public else {},
        "headers": probe["headers"],
        "error": probe["error"],
    }


# ---------------------------------------------------------------------------
# HTTP(S) probe (inline — mirrors probe_mjpeg.py logic, extended for HLS)
# ---------------------------------------------------------------------------


def _classify_http(content_type: str, path: str) -> str:
    ct_lower = content_type.lower().split(";")[0].strip()
    path_lower = path.lower()

    if "multipart/x-mixed-replace" in ct_lower:
        return "MJPEG stream (multipart/x-mixed-replace)"
    if ct_lower in ("image/jpeg", "image/jpg"):
        return "JPEG snapshot"
    if ct_lower == "image/png":
        return "PNG snapshot"
    if ct_lower in ("application/vnd.apple.mpegurl", "application/x-mpegurl"):
        return "HLS stream (application/vnd.apple.mpegurl)"
    if path_lower.endswith(".m3u8") or ct_lower.endswith("mpegurl"):
        return "HLS stream (inferred from .m3u8 extension or content type)"
    if ct_lower:
        return f"Unknown stream type (Content-Type: {content_type.strip()})"
    return "Unknown stream type (no Content-Type header)"


def probe_http(raw_url: str, timeout: float) -> dict:
    clean_url = strip_credentials(raw_url)
    parsed = urlparse(raw_url)

    result: dict = {
        "scheme": parsed.scheme,
        "status_code": 0,
        "reason": "",
        "content_type": "",
        "classification": "",
        "extra": {},
        "headers": {},
        "body_preview_bytes": 0,
        "error": None,
    }

    req = urllib.request.Request(
        clean_url,
        headers={"User-Agent": "AirseekersProbe/0.1"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status_code"] = resp.status
            result["reason"] = resp.reason or ""
            result["headers"] = dict(resp.headers.items())
            ct = resp.headers.get("Content-Type", "")
            result["content_type"] = ct
            result["classification"] = _classify_http(ct, parsed.path)
            body = resp.read(MAX_BODY_BYTES)
            result["body_preview_bytes"] = len(body)
    except urllib.error.HTTPError as exc:
        result["status_code"] = exc.code
        result["reason"] = exc.reason or ""
        result["error"] = f"HTTP {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        result["error"] = f"URL error: {exc.reason}"
    except TimeoutError:
        result["error"] = "Request timed out"
    except OSError as exc:
        result["error"] = f"Connection error: {exc}"

    return result


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_report(redacted_url: str, scheme: str, timeout: float, probe: dict) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    if probe.get("error"):
        outcome = f"**Error:** {probe['error']}"
    elif scheme == "rtsp":
        if probe["status_code"] == 401:
            outcome = "**401 Unauthorized** — authentication required. No further attempts made."
        else:
            outcome = f"**{probe['status_line']}**"
    else:
        outcome = f"**HTTP {probe['status_code']} {probe.get('reason', '')}**"

    # Redact auth headers
    safe_headers = {
        k: (
            "***REDACTED***"
            if k.lower() in ("authorization", "www-authenticate", "proxy-authorization")
            else v
        )
        for k, v in probe.get("headers", {}).items()
    }
    headers_md = "\n".join(f"| `{k}` | `{v}` |" for k, v in safe_headers.items()) or "_no headers_"

    extra_lines = ""
    if probe.get("extra"):
        extra_lines = "\n".join(f"**{k}:** `{v}`" for k, v in probe["extra"].items())

    body_line = ""
    if scheme in ("http", "https"):
        body_line = (
            f"**Body bytes read (max {MAX_BODY_BYTES}):** {probe.get('body_preview_bytes', 0)}"
        )

    return f"""# Camera URL Probe Report

**URL (redacted):** `{redacted_url}`
**Scheme:** `{scheme}`
**Probe time:** {ts}
**Timeout:** {timeout}s

---

## Result

{outcome}

**Classification:** {probe.get("classification", "_n/a_")}
**Content-Type:** `{probe.get("content_type") or "(not applicable / not present)"}`
{extra_lines}
{body_line}

---

## Response Headers

| Header | Value |
| ------ | ----- |
{headers_md}

---

## Notes

- A single passive probe ({scheme.upper()} {"OPTIONS" if scheme == "rtsp" else "GET"}) was issued.
- No credentials were tested or brute-forced.
- If the server returned 401, this tool stopped immediately.
- Credentials embedded in the original URL have been **redacted** in this report.
- `Authorization` / `WWW-Authenticate` headers are also redacted above.

---

*Generated by probe_camera_url.py — single probe only.*
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test an owner-supplied camera URL and classify its stream type. "
            "Supports rtsp://, http://, and https:// URLs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="URL",
        help="Camera URL to probe (rtsp://, http://, or https://).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Probe timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write a markdown report to tools/reports/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    parsed = urlparse(args.url)
    scheme = parsed.scheme.lower()

    if scheme not in ("rtsp", "rtsps", "http", "https"):
        print(
            f"[!] Unsupported scheme: {scheme!r}. "
            "Expected rtsp://, rtsps://, http://, or https://.",
            file=sys.stderr,
        )
        sys.exit(1)

    redacted_url = redact_url(args.url)
    print(f"[*] Probing: {redacted_url}  (scheme={scheme}, timeout={args.timeout}s)")

    if scheme in ("rtsp", "rtsps"):
        probe = probe_rtsp(args.url, args.timeout)
    else:
        probe = probe_http(args.url, args.timeout)

    print()
    if probe.get("error"):
        print(f"[!] {probe['error']}")
    else:
        if scheme in ("rtsp", "rtsps"):
            print(f"[+] Status line    : {probe['status_line']}")
            public = probe.get("extra", {}).get("Public")
            if public:
                print(f"[+] Public methods : {public}")
        else:
            print(f"[+] HTTP {probe['status_code']} {probe.get('reason', '')}")
            print(f"[+] Content-Type   : {probe['content_type'] or '(not present)'}")
        print(f"[+] Classification : {probe['classification']}")

        if scheme in ("rtsp", "rtsps") and probe["status_code"] == 401:
            print()
            print("[!] 401 Unauthorized — authentication required. No further attempts made.")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"probe_camera_url_{ts_file}.md"
        report_path.write_text(
            build_report(redacted_url, scheme, args.timeout, probe),
            encoding="utf-8",
        )
        print(f"\n[+] Report written to: {report_path}")


if __name__ == "__main__":
    main()
