# Project State: ha-airseekers

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-17)

**Core value:** Install via HACS → add the robot → fully working HA device on the stub backend, before the real protocol is mapped.
**Current focus:** Phase 3 — Home Assistant Core Integration (coordinator, flows, lawn_mower, diagnostics)

## Status

- **Phase:** Phases 1–2 done; Phase 3 next (of 8)
- **Mode:** YOLO + quality agents (research / plan-check / verifier on); model profile: quality
- **GSD management:** manual (parent dir is an active GSD project; `gsd-sdk` anchors to the outer worktree)
- **Backend in use:** `stub` (real backends UNVERIFIED)

## Recent Activity

- 2026-06-17 — Initialized standalone git repo for the HACS integration.
- 2026-06-17 — Created GSD planning docs (PROJECT, REQUIREMENTS, ROADMAP, STATE, config) manually.
- 2026-06-17 — Launched research agents for AIRSEEKERS protocol reality and HA integration API surface (→ docs/api_mapping.md, docs/camera_mapping.md, docs/architecture.md).
- 2026-06-17 — Phase 1 committed (skeleton + discovery tools). Added GitHub remote, pushed main to github.com/figpom-solutions/ha-airseekers.
- 2026-06-17 — Phase 2 committed: api.py (models, exceptions, AirseekersClient, fully functional stub backend + skeleton backends) and tests/test_api.py. Stub + warranty/blade math verified locally via HA shim.

## Open Questions / Unknowns

- Does the robot expose a local API, or is it cloud-only? (UNVERIFIED — see docs/api_mapping.md)
- Camera count, roles, and streaming tech (RTSP/WebRTC/proprietary)? (UNVERIFIED — see docs/camera_mapping.md)
- Auth model and cloud domains? (UNVERIFIED)

## Next Step

`/gsd:discuss-phase 1` equivalent → continue Phase 1 build (skeleton + discovery tools), then Phase 2 (client + stub).

---
*Last updated: 2026-06-17*
