# AIRSEEKERS for Home Assistant (`ha-airseekers`)

A custom Home Assistant integration for the **AIRSEEKERS TRON / TRON Max** RTK robotic lawn mower —
control, telemetry, multi-camera viewing, and real-world maintenance tracking (warranty, blade wear,
mowing hours/cycles, maintenance log).

> **Status: early / stub-first.** The integration works **end-to-end today against a fully simulated
> `stub` backend** so you can install it, see every entity, and build dashboards before the robot's
> real protocol is mapped. The real backends (`local_http`, `cloud_http`, `mqtt`, RTSP camera) are
> deliberately **not invented** — they ship as clear stubs and are completed only from
> owner-verified protocol discovery. See [`docs/api_mapping.md`](docs/api_mapping.md).

## Project state

| Area | State |
|------|-------|
| Stub backend (full simulation) | ✅ functional |
| HACS install | ✅ supported (custom repository) |
| Local API | ❓ to discover ([`docs/api_mapping.md`](docs/api_mapping.md)) |
| Cloud API | ❓ to discover |
| MQTT | ❓ to confirm |
| Cameras | ❓ to map ([`docs/camera_mapping.md`](docs/camera_mapping.md)) |

Development is managed with GSD — see [`.planning/ROADMAP.md`](.planning/ROADMAP.md) and
[`docs/gsd/`](docs/gsd/).

## Install

### Via HACS (custom repository)
1. HACS → ⋮ → **Custom repositories**.
2. Add this repo's URL, category **Integration**.
3. Install **AIRSEEKERS**, then restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → AIRSEEKERS.**

> Update `documentation` / `issue_tracker` / `codeowners` in `manifest.json` to match your repo
> before publishing.

### Manual
Copy `custom_components/airseekers/` into your Home Assistant `config/custom_components/`, then restart.

## Configuration

The config flow asks for a **backend** (start with `stub`), **model** (`TRON` / `TRON Max`), a device
name, and optional host/credentials for real backends later. Everything else (polling intervals,
camera behaviour, maintenance settings) is editable from the integration's **Configure** (options).

### Use the stub backend
Pick `stub` when adding the integration. You immediately get a mower entity, sensors, ≥5 simulated
cameras (front/left/right/rear/360), and the full maintenance subsystem — no robot required. This is
the recommended way to validate Home Assistant and build your dashboard.

## What you get

- **Mower:** start / pause / dock (+ best-effort stop), activity & battery, zone mowing where reported.
- **Sensors / binary sensors:** battery, state, activity, zone, error, RTK/GPS, Wi-Fi RSSI, blade motor,
  totals; online/charging/docked/raining/error/obstacle/camera-available.
- **Controls:** refresh/dock/pause/start/stop/locate/reset-error buttons, cutting-height number, zone /
  mode / backend / camera-mode selects.
- **Cameras:** one entity per reported camera (dynamic), role-named, snapshot/live/composite, privacy-first.
- **Maintenance:** warranty countdown, blade wear %, mowing hours/cycles, maintenance log, non-spam alerts.
- **Services + a ready Lovelace dashboard** (see [`docs/dashboard.md`](docs/dashboard.md)).

## Multi-camera notes

The TRON family uses a multi-camera vision system. Not every physical camera is necessarily exposed to
the user, and a robot may present **composite** views (e.g. 300°/360°) rather than raw per-lens feeds.
The integration creates entities **only for cameras the backend actually reports**, classifies each by
**role** and **stream type** (snapshot / MJPEG / HLS / RTSP / WebRTC / cloud / proprietary), and treats
streams as privacy-sensitive by default. See [`docs/camera_mapping.md`](docs/camera_mapping.md).

## Completing the real integration (protocol discovery)

To move beyond the stub, capture how **your own** robot and the **AIRSEEKERS app on your own phone/
account** communicate, then map endpoints to entities. Tools live in [`tools/`](tools/) and are
**non-intrusive** (no brute force, nothing published without confirmation, secrets redacted):

```bash
# Find the robot IP from your router/DHCP, then:
python tools/discover_lan.py
python tools/discover_camera_streams.py --host <IP_ROBOT>
# nmap -sV <IP_ROBOT>   # your own device only
```

Full procedure (Wireshark / mitmproxy on your own phone, DNS observation, anonymising traces, and the
endpoint table to fill in): [`tools/README_DISCOVERY.md`](tools/README_DISCOVERY.md),
[`tools/analyze_app_camera_calls.md`](tools/analyze_app_camera_calls.md),
[`tools/extract_app_domains.md`](tools/extract_app_domains.md).

**What to record per call:** endpoint · method · payload · response · the matching HA entity.
Anonymise before sharing.

## Security & privacy

- No credentials, tokens, signed URLs, or camera stream URLs are ever logged or written to diagnostics.
- Diagnostics are redacted via a shared helper; cameras default to no recording / no external exposure.
- Discovery tools touch **only your own** network/devices/account. See [`docs/security.md`](docs/security.md).

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest
```

Python 3.12+, full async, typed. See [`docs/architecture.md`](docs/architecture.md).

## Roadmap

LAN discovery → cloud auth → mow commands → zones → map → MQTT → multi-camera → Lovelace dashboard →
optional Frigate integration. Tracked in [`.planning/ROADMAP.md`](.planning/ROADMAP.md).

## Disclaimer

Independent, unofficial project for interoperability with **your own** robot, network, and account.
Not affiliated with AIRSEEKERS. Use at your own risk.

## License

MIT.
