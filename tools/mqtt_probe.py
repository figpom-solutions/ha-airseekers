#!/usr/bin/env python3
"""
mqtt_probe.py — Detect presence of an MQTT broker on a target host.

Steps:
  1. TCP connect check on the configured ports (default 1883, 8883).
  2. Optionally (--connect flag): attempt a single anonymous MQTT CONNECT
     and report only whether the broker accepted or refused.

NEVER subscribes to topics.
NEVER publishes messages.
Uses paho-mqtt if available; falls back to a hand-crafted MQTT CONNECT
packet in pure stdlib so --connect works without any extra dependencies.
"""

# =============================================================================
# SECURITY / ETHICS NOTICE
# =============================================================================
# This script:
#   - Performs a TCP connect check (sends SYN packets) to the listed ports.
#   - With --connect: sends a single minimal MQTT CONNECT packet and reads
#     back the CONNACK only to determine broker acceptance.
#   - NEVER subscribes to any topic.
#   - NEVER publishes any message.
#   - NEVER stores, logs, or transmits credentials or Authorization headers.
#   - Does NOT perform brute-force credential guessing.
# Use only on brokers you own or have explicit permission to test.
# =============================================================================

import argparse
import datetime
from pathlib import Path
import random
import socket
import struct

DEFAULT_PORTS = "1883,8883"
REPORTS_DIR = Path(__file__).parent / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _random_client_id() -> str:
    suffix = "".join(f"{random.randint(0, 15):x}" for _ in range(4))
    return f"airseekers_probe_{suffix}"


# ---------------------------------------------------------------------------
# TCP connect check
# ---------------------------------------------------------------------------


def tcp_connect(host: str, port: int, timeout: float) -> tuple[bool, str]:
    """Return (is_open, message)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP port {port} is OPEN."
    except ConnectionRefusedError:
        return False, f"TCP port {port}: Connection refused."
    except TimeoutError:
        return False, f"TCP port {port}: Timed out."
    except OSError as exc:
        return False, f"TCP port {port}: {exc}"


# ---------------------------------------------------------------------------
# Pure-stdlib MQTT CONNECT packet builder
# ---------------------------------------------------------------------------


def _build_mqtt_connect_packet(client_id: str) -> bytes:
    """
    Build a minimal MQTT v3.1.1 CONNECT packet.

    Fixed header  : 0x10 (CONNECT), variable-length remaining length
    Variable header:
      Protocol Name  : "MQTT" (UTF-8 prefixed)
      Protocol Level : 4 (MQTT 3.1.1)
      Connect Flags  : 0x02 (clean session, no will, no username/password)
      Keep Alive     : 60 seconds
    Payload:
      Client Identifier: client_id (UTF-8 prefixed)
    """
    # Variable header (10 bytes for MQTT 3.1.1)
    protocol_name = b"\x00\x04MQTT"  # length-prefixed "MQTT"
    protocol_level = b"\x04"  # MQTT 3.1.1
    connect_flags = b"\x02"  # clean session
    keep_alive = struct.pack("!H", 60)  # 60 seconds big-endian

    variable_header = protocol_name + protocol_level + connect_flags + keep_alive

    # Payload: client identifier
    cid_bytes = client_id.encode("utf-8")
    payload = struct.pack("!H", len(cid_bytes)) + cid_bytes

    # Remaining length (variable-length encoding)
    remaining = variable_header + payload
    remaining_length = len(remaining)

    # Encode remaining length as MQTT variable-length integer
    encoded_length = bytearray()
    x = remaining_length
    while True:
        byte = x % 128
        x = x // 128
        if x > 0:
            byte |= 0x80
        encoded_length.append(byte)
        if x == 0:
            break

    # Fixed header
    fixed_header = bytes([0x10]) + bytes(encoded_length)
    return fixed_header + remaining


def _parse_connack(data: bytes) -> tuple[bool, str]:
    """
    Parse a CONNACK packet.
    Returns (accepted, description).
    """
    if len(data) < 4:
        return False, f"Truncated response ({len(data)} bytes)"
    if data[0] != 0x20:
        return False, f"Unexpected packet type: 0x{data[0]:02x} (not CONNACK)"
    if data[1] != 0x02:
        return False, f"Unexpected remaining length: {data[1]}"

    # Byte 3: session present flag (bit 0)
    # Byte 4: return code
    return_code = data[3]
    rc_descriptions = {
        0x00: "Connection Accepted",
        0x01: "Refused: unacceptable protocol version",
        0x02: "Refused: identifier rejected",
        0x03: "Refused: server unavailable",
        0x04: "Refused: bad username or password",
        0x05: "Refused: not authorized",
    }
    description = rc_descriptions.get(return_code, f"Unknown return code 0x{return_code:02x}")
    accepted = return_code == 0x00
    return accepted, description


# ---------------------------------------------------------------------------
# MQTT connect attempt — stdlib fallback
# ---------------------------------------------------------------------------


def mqtt_connect_stdlib(host: str, port: int, timeout: float) -> dict:
    """
    Attempt a single MQTT CONNECT via raw socket.
    Returns result dict with keys: accepted, description, client_id, method.
    """
    client_id = _random_client_id()
    packet = _build_mqtt_connect_packet(client_id)
    result = {
        "client_id": client_id,
        "method": "stdlib-raw",
        "accepted": False,
        "description": "No response",
    }
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(packet)
            sock.settimeout(timeout)
            response = sock.recv(64)
        accepted, description = _parse_connack(response)
        result["accepted"] = accepted
        result["description"] = description
    except ConnectionRefusedError:
        result["description"] = "Connection refused"
    except TimeoutError:
        result["description"] = "Timed out waiting for CONNACK"
    except OSError as exc:
        result["description"] = f"OSError: {exc}"
    return result


# ---------------------------------------------------------------------------
# MQTT connect attempt — paho-mqtt
# ---------------------------------------------------------------------------


def mqtt_connect_paho(host: str, port: int, timeout: float) -> dict | None:
    """
    Attempt a single MQTT CONNECT using paho-mqtt.
    Returns None if paho-mqtt is not installed.
    NEVER subscribes or publishes.
    """
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        print(
            "[MQTT] paho-mqtt not installed — using stdlib fallback.\n"
            "       To use paho-mqtt: pip install paho-mqtt"
        )
        return None

    client_id = _random_client_id()
    result = {
        "client_id": client_id,
        "method": "paho-mqtt",
        "accepted": False,
        "description": "No response",
    }

    import threading

    event = threading.Event()

    def on_connect(client, userdata, flags, rc):
        result["accepted"] = rc == 0
        rc_map = {
            0: "Connection Accepted",
            1: "Refused: unacceptable protocol version",
            2: "Refused: identifier rejected",
            3: "Refused: server unavailable",
            4: "Refused: bad username or password",
            5: "Refused: not authorized",
        }
        result["description"] = rc_map.get(rc, f"Unknown rc={rc}")
        event.set()

    client = mqtt.Client(client_id=client_id, clean_session=True)
    client.on_connect = on_connect

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
        event.wait(timeout=timeout)
        client.loop_stop()
        client.disconnect()
    except Exception as exc:
        result["description"] = f"Exception: {exc}"

    return result


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def write_report(
    report_path: Path,
    tcp_results: list[dict],
    connect_result: dict | None,
    args: argparse.Namespace,
) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# MQTT Probe Report",
        f"\n**Generated:** {ts}",
        f"**Target host:** `{args.host}`",
        f"**Ports tested:** {args.ports}",
        f"**Timeout:** {args.timeout}s",
        f"**Connect attempt:** {'yes' if args.connect else 'no'}",
        "",
        "> This probe NEVER subscribes to topics or publishes messages.",
        "",
        "## TCP Connectivity",
        "",
    ]

    for r in tcp_results:
        icon = "OPEN" if r["open"] else "CLOSED/FILTERED"
        lines.append(f"- Port **{r['port']}**: {icon} — {r['message']}")
    lines.append("")

    if connect_result:
        lines += ["## MQTT CONNECT Attempt", ""]
        accepted_str = (
            "YES — broker accepted anonymous connection" if connect_result["accepted"] else "NO"
        )
        lines.append(f"**Accepted:** {accepted_str}")
        lines.append(f"**Description:** {connect_result['description']}")
        lines.append(f"**Method:** {connect_result['method']}")
        lines.append(f"**Client ID used:** `{connect_result['client_id']}`")
        lines.append("")
        lines.append(
            "> The probe immediately disconnected after receiving CONNACK. "
            "No topics were subscribed. No messages were published."
        )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect MQTT broker presence. No publish, no subscribe."
    )
    parser.add_argument("--host", required=True, help="Target host IP or hostname")
    parser.add_argument(
        "--ports",
        default=DEFAULT_PORTS,
        help=f"Comma-separated MQTT ports (default: {DEFAULT_PORTS})",
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="Timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Attempt a single anonymous MQTT CONNECT (reports accept/refuse only)",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Override report output path",
    )
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]

    print(f"=== MQTT Probe: {args.host} ===")
    print(f"Ports: {ports} | Timeout: {args.timeout}s | Connect: {args.connect}")
    print()

    # Step 1: TCP check
    tcp_results: list[dict] = []
    for port in ports:
        is_open, msg = tcp_connect(args.host, port, args.timeout)
        tcp_results.append({"port": port, "open": is_open, "message": msg})
        status = "OPEN" if is_open else "CLOSED/FILTERED"
        print(f"  Port {port}: {status}")

    # Step 2: Optional MQTT CONNECT
    connect_result: dict | None = None
    if args.connect:
        # Pick first open port for connect attempt
        open_ports = [r["port"] for r in tcp_results if r["open"]]
        if not open_ports:
            print("\n  --connect requested but no open ports found. Skipping.")
        else:
            target_port = open_ports[0]
            print(f"\n  Attempting MQTT CONNECT on port {target_port}...")
            print(
                "  (This sends a single MQTT CONNECT packet and reads CONNACK only. "
                "No subscribe/publish.)"
            )
            # Try paho first, fall back to stdlib
            connect_result = mqtt_connect_paho(args.host, target_port, args.timeout)
            if connect_result is None:
                connect_result = mqtt_connect_stdlib(args.host, target_port, args.timeout)
            accepted_str = "ACCEPTED" if connect_result["accepted"] else "REFUSED"
            print(f"  Result: {accepted_str} — {connect_result['description']}")

    # Report
    _ensure_reports_dir()
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = REPORTS_DIR / f"mqtt_probe_{_timestamp()}.md"

    write_report(report_path, tcp_results, connect_result, args)
    print(f"\nReport written to: {report_path}")

    open_count = sum(1 for r in tcp_results if r["open"])
    print(f"\nSummary: {open_count}/{len(ports)} MQTT port(s) open.")
    if connect_result:
        verdict = "accepted" if connect_result["accepted"] else "refused"
        print(f"  CONNECT attempt: broker {verdict} the connection.")


if __name__ == "__main__":
    main()
