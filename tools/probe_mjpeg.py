#!/usr/bin/env python3
"""
probe_mjpeg.py — Test an owner-supplied HTTP(S) MJPEG / snapshot URL.

Sends a single GET request, reads at most 4096 bytes of the response body,
and classifies the stream by Content-Type:
  - multipart/x-mixed-replace  → MJPEG stream
  - image/jpeg / image/png     → snapshot endpoint
  - anything else              → unknown (Content-Type shown)

Credentials embedded in the URL are redacted in all output and the report.

Usage:
    python probe_mjpeg.py --url http://192.168.1.50:8080/stream --report
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This tool sends a single passive HTTP GET request only.
# It does NOT brute-force credentials, enumerate paths, or attempt exploits.
# Use exclusively on devices you own or have explicit written permission to test.
# At most 4096 bytes of body are read — it will not buffer a full video stream.
# Misuse may violate the Computer Fraud and Abuse Act (CFAA) and equivalent
# laws in your jurisdiction.
# =============================================================================

import argparse
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

REPORTS_DIR = Path(__file__).parent / "reports"
MAX_BODY_BYTES = 4096


# ---------------------------------------------------------------------------
# URL helpers
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
    """Return URL with credentials removed (for use in actual requests)."""
    parsed = urlparse(raw_url)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_content_type(ct: str) -> str:
    ct_lower = ct.lower().split(";")[0].strip()
    if "multipart/x-mixed-replace" in ct_lower:
        return "MJPEG stream (multipart/x-mixed-replace)"
    if ct_lower in ("image/jpeg", "image/jpg"):
        return "JPEG snapshot"
    if ct_lower == "image/png":
        return "PNG snapshot"
    return f"Unknown ({ct.strip()})"


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

def probe_url(url: str, timeout: float) -> dict:
    """
    Perform a single GET to `url`.  Returns a result dict with:
      status_code, content_type, classification, body_preview (hex), error
    """
    result: dict = {
        "status_code": 0,
        "reason": "",
        "content_type": "",
        "classification": "",
        "headers": {},
        "body_preview_bytes": 0,
        "error": None,
    }

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AirseekersProbe/0.1"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status_code"] = resp.status
            result["reason"] = resp.reason or ""
            # Collect all headers
            result["headers"] = dict(resp.headers.items())
            ct = resp.headers.get("Content-Type", "")
            result["content_type"] = ct
            result["classification"] = classify_content_type(ct)
            # Read at most MAX_BODY_BYTES — do NOT buffer the full stream
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
# Report
# ---------------------------------------------------------------------------

def build_report(redacted_url: str, timeout: float, probe: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if probe["error"]:
        outcome = f"**Error:** {probe['error']}"
    else:
        outcome = (
            f"**HTTP {probe['status_code']} {probe['reason']}**\n\n"
            f"**Classification:** {probe['classification']}"
        )

    # Redact Authorization headers in the displayed headers table
    safe_headers = {
        k: ("***REDACTED***" if k.lower() in ("authorization", "www-authenticate", "proxy-authorization") else v)
        for k, v in probe["headers"].items()
    }
    headers_md = "\n".join(
        f"| `{k}` | `{v}` |" for k, v in safe_headers.items()
    ) or "_no headers_"

    return f"""# MJPEG / Snapshot Probe Report

**URL (redacted):** `{redacted_url}`
**Probe time:** {ts}
**Timeout:** {timeout}s
**Body read (max {MAX_BODY_BYTES} bytes):** {probe['body_preview_bytes']} bytes read

---

## Result

{outcome}

**Content-Type:** `{probe['content_type'] or '(not present)'}`
**Body preview bytes read:** {probe['body_preview_bytes']}

---

## Response Headers

| Header | Value |
| ------ | ----- |
{headers_md}

---

## Notes

- Only a single GET request was sent; at most {MAX_BODY_BYTES} bytes of body were read.
- No credentials were tested or brute-forced.
- Credentials embedded in the original URL have been **redacted** in this report.
- `Authorization` / `WWW-Authenticate` headers are also redacted above.

---

*Generated by probe_mjpeg.py — single GET request only.*
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test an owner-supplied HTTP(S) MJPEG or snapshot URL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="URL",
        help="HTTP or HTTPS URL to probe (owner-supplied).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Request timeout in seconds (default: 5).",
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
    if parsed.scheme not in ("http", "https"):
        print(f"[!] Error: expected http:// or https:// URL, got: {parsed.scheme!r}", file=sys.stderr)
        sys.exit(1)

    redacted_url = redact_url(args.url)
    clean_url = strip_credentials(args.url)

    print(f"[*] Probing (HTTP GET): {redacted_url}")
    print(f"    timeout={args.timeout}s  max_body={MAX_BODY_BYTES} bytes")

    probe = probe_url(clean_url, args.timeout)

    print()
    if probe["error"]:
        print(f"[!] {probe['error']}")
    else:
        print(f"[+] HTTP {probe['status_code']} {probe['reason']}")
        print(f"[+] Content-Type : {probe['content_type'] or '(not present)'}")
        print(f"[+] Classification: {probe['classification']}")
        print(f"[+] Body bytes read: {probe['body_preview_bytes']}")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"probe_mjpeg_{ts_file}.md"
        report_path.write_text(
            build_report(redacted_url, args.timeout, probe),
            encoding="utf-8",
        )
        print(f"\n[+] Report written to: {report_path}")


if __name__ == "__main__":
    main()
