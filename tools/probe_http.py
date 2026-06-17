#!/usr/bin/env python3
"""
probe_http.py — Light HTTP/HTTPS probe for Airseekers robot host.

Sends a single GET / to each configured port and reports:
  - HTTP status code
  - Server, Content-Type headers
  - WWW-Authenticate header presence (value REDACTED)
  - Content preview (first 200 chars)

Set-Cookie and Authorization headers are NEVER logged.
No path enumeration, no brute force.
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This script sends exactly ONE HTTP GET / request per configured port.
# It does NOT:
#   - Enumerate paths or endpoints
#   - Perform brute-force authentication attempts
#   - Store or log Set-Cookie or Authorization header values
#   - Follow redirects beyond the initial response
# Use only on hosts you own or have explicit permission to probe.
# =============================================================================

import argparse
import datetime
import http.client
import ipaddress
import socket
import ssl
import sys
from pathlib import Path

DEFAULT_PORTS = "80,443,8080"
REPORTS_DIR = Path(__file__).parent / "reports"

# Headers whose values must NEVER appear in output
_REDACT_HEADERS = {"set-cookie", "authorization", "proxy-authorization"}
# Headers whose presence is noted but value is redacted
_PRESENCE_ONLY_HEADERS = {"www-authenticate", "proxy-authenticate"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_ssl_port(port: int) -> bool:
    return port == 443 or port == 8443


def _safe_header(name: str, value: str) -> str:
    """Return header value, or REDACTED/[present] depending on policy."""
    nl = name.lower()
    if nl in _REDACT_HEADERS:
        return "[REDACTED — not logged]"
    if nl in _PRESENCE_ONLY_HEADERS:
        return "[present — value redacted for security]"
    return value


# ---------------------------------------------------------------------------
# HTTP probe (stdlib http.client)
# ---------------------------------------------------------------------------

def probe_port_stdlib(host: str, port: int, timeout: float) -> dict:
    """Probe a single port with stdlib http.client. Returns result dict."""
    use_ssl = _is_ssl_port(port)
    result: dict = {
        "host": host,
        "port": port,
        "scheme": "https" if use_ssl else "http",
        "status": None,
        "reason": None,
        "headers": {},
        "content_preview": "",
        "error": None,
    }

    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    conn_cls = http.client.HTTPSConnection if use_ssl else http.client.HTTPConnection

    try:
        conn = conn_cls(host, port, timeout=timeout, context=ctx) if use_ssl else conn_cls(host, port, timeout=timeout)
        conn.request("GET", "/", headers={"User-Agent": "airseekers-probe/1.0", "Connection": "close"})
        resp = conn.getresponse()
        result["status"] = resp.status
        result["reason"] = resp.reason

        for hname, hval in resp.getheaders():
            safe_val = _safe_header(hname, hval)
            result["headers"][hname] = safe_val

        body = resp.read(512)
        try:
            preview = body.decode("utf-8", errors="replace")[:200]
        except Exception:
            preview = repr(body[:200])
        result["content_preview"] = preview
        conn.close()
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        result["error"] = f"Unexpected: {type(exc).__name__}: {exc}"

    return result


# ---------------------------------------------------------------------------
# Optional aiohttp probe (lazy import)
# ---------------------------------------------------------------------------

def probe_port_aiohttp(host: str, port: int, timeout: float) -> dict | None:
    """Try to use aiohttp for probing. Returns None if not available."""
    try:
        import asyncio
        import aiohttp  # type: ignore
    except ImportError:
        return None

    use_ssl = _is_ssl_port(port)
    scheme = "https" if use_ssl else "http"
    url = f"{scheme}://{host}:{port}/"

    async def _fetch() -> dict:
        result: dict = {
            "host": host,
            "port": port,
            "scheme": scheme,
            "status": None,
            "reason": None,
            "headers": {},
            "content_preview": "",
            "error": None,
        }
        connector = aiohttp.TCPConnector(ssl=False)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=False,
                    headers={"User-Agent": "airseekers-probe/1.0"},
                ) as resp:
                    result["status"] = resp.status
                    result["reason"] = resp.reason
                    for hname, hval in resp.headers.items():
                        result["headers"][hname] = _safe_header(hname, hval)
                    body = await resp.read()
                    preview = body.decode("utf-8", errors="replace")[:200]
                    result["content_preview"] = preview
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    try:
        import asyncio
        return asyncio.run(_fetch())
    except Exception as exc:
        return {"error": str(exc), "host": host, "port": port}


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(report_path: Path, results: list[dict], args: argparse.Namespace) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# HTTP Probe Report",
        f"\n**Generated:** {ts}",
        f"**Target host:** `{args.host}`",
        f"**Ports:** {args.ports}",
        f"**Timeout:** {args.timeout}s",
        "",
        "> Set-Cookie and Authorization header values are NEVER logged.",
        "",
    ]

    for r in results:
        scheme = r.get("scheme", "http")
        port = r["port"]
        lines.append(f"## {scheme.upper()} Port {port}")
        lines.append("")
        if r.get("error"):
            lines.append(f"**Error:** `{r['error']}`")
        else:
            lines.append(f"**Status:** {r.get('status')} {r.get('reason', '')}")
            headers = r.get("headers", {})
            for interesting in ["Server", "Content-Type", "WWW-Authenticate", "X-Powered-By"]:
                val = headers.get(interesting) or headers.get(interesting.lower())
                if val:
                    lines.append(f"**{interesting}:** `{val}`")
            lines.append("")
            preview = r.get("content_preview", "")
            if preview:
                lines.append("**Content preview (first 200 chars):**")
                lines.append("```")
                lines.append(preview)
                lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-GET HTTP/HTTPS probe. No path enumeration."
    )
    parser.add_argument("--host", required=True, help="Target host IP or hostname")
    parser.add_argument(
        "--ports",
        default=DEFAULT_PORTS,
        help=f"Comma-separated ports (default: {DEFAULT_PORTS})",
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="Request timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--report",
        default="",
        help="Override report output path",
    )
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]

    print(f"=== HTTP Probe: {args.host} ===")
    print(f"Ports: {ports} | Timeout: {args.timeout}s")
    print("Note: Set-Cookie / Authorization header values are NEVER logged.")
    print()

    results: list[dict] = []
    for port in ports:
        scheme = "https" if _is_ssl_port(port) else "http"
        print(f"  Probing {scheme}://{args.host}:{port}/ ...")
        r = probe_port_stdlib(args.host, port, args.timeout)
        if r.get("error"):
            print(f"    Error: {r['error']}")
        else:
            print(f"    Status: {r.get('status')} {r.get('reason', '')}")
            srv = r["headers"].get("Server") or r["headers"].get("server", "")
            if srv:
                print(f"    Server: {srv}")
        results.append(r)

    _ensure_reports_dir()
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = REPORTS_DIR / f"probe_http_{_timestamp()}.md"

    write_report(report_path, results, args)
    print(f"\nReport written to: {report_path}")

    # Stdout summary
    ok = [r for r in results if r.get("status") is not None]
    print(f"\nSummary: {len(ok)}/{len(ports)} ports responded.")


if __name__ == "__main__":
    main()
