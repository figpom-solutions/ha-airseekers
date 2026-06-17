# Technical Context — ha-airseekers

## Runtime & layout

- Target: Home Assistant Core on Python 3.12+. Dev box here is Python 3.10 (authoring only; HA libs
  are not installed locally, so `homeassistant.*` imports can't be executed here — verify in HA/CI).
- Standalone repo at `airseekers/` with its own `.git`, nested inside (but isolated from) the parent
  Home Assistant Docker infra repo.
- Integration package: `custom_components/airseekers/`.

## Backend abstraction

`AirseekersClient` hides backend differences behind one async method surface. Backends:

| Backend | State | Notes |
|---------|-------|-------|
| `stub` | ✅ fully functional | Default; simulates status, zones, ≥5 cameras, maintenance |
| `local_http` | 🚧 stub | Raises `AirseekersUnsupportedFeature` until a local API is verified |
| `cloud_http` | 🚧 stub | aiohttp skeleton; `.env`-driven; no endpoints invented |
| `mqtt` | 🚧 stub | Only if a broker/protocol is confirmed |
| `rtsp`/camera | 🚧 stub | Stream handling once camera tech is confirmed |

## Polling strategy

- Coordinator update interval is adaptive: ~30s when the robot is active (mowing/returning), ~2–5 min
  when docked/idle. Configurable via options. Never spam a cloud API.

## Security posture

- Reusable redaction helper masks: credentials, tokens, refresh tokens, `Authorization` headers,
  tokenised/signed URLs, sensitive query params, stream URLs, public IPs.
- Discovery tools are read-only/non-intrusive: mDNS/SSDP/ARP, light port checks, owner-supplied probe
  targets only. No brute force, no credential lists, nothing published without explicit confirmation.

## Owner inputs needed to complete real backends

Captured from the owner's OWN phone/account (see `docs/api_mapping.md` + `tools/`):
- App name/developer; cloud domains; whether traffic is local or cloud.
- Endpoint table: endpoint · method · payload · response · HA mapping (anonymised before sharing).
- Camera stream type(s) and how the app requests each view.

## Open unknowns

See `.planning/STATE.md` → "Open Questions". The stub backend means these do not block any phase.
