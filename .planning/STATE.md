# Project State: ha-airseekers

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-17)

**Core value:** Install via HACS → add the robot → fully working HA device on the stub backend, before the real protocol is mapped.
**Current focus:** Phase 8 — Tests, quality & documentation (final)

## Status

- **Phase:** Phases 1–7 done; Phase 8 next (of 8)
- **Mode:** YOLO + quality agents (research / plan-check / verifier on); model profile: quality
- **GSD management:** manual (parent dir is an active GSD project; `gsd-sdk` anchors to the outer worktree)
- **Backend in use:** `stub` (real backends UNVERIFIED)

## Recent Activity

- 2026-06-17 — Initialized standalone git repo for the HACS integration.
- 2026-06-17 — Created GSD planning docs (PROJECT, REQUIREMENTS, ROADMAP, STATE, config) manually.
- 2026-06-17 — Launched research agents for AIRSEEKERS protocol reality and HA integration API surface (→ docs/api_mapping.md, docs/camera_mapping.md, docs/architecture.md).
- 2026-06-17 — Phase 1 committed (skeleton + discovery tools). Added GitHub remote, pushed main to github.com/figpom-solutions/ha-airseekers.
- 2026-06-17 — Phase 2 committed: api.py (models, exceptions, AirseekersClient, fully functional stub backend + skeleton backends) and tests/test_api.py. Stub + warranty/blade math verified locally via HA shim.
- 2026-06-17 — Phase 3 committed: redact.py, coordinator.py (adaptive polling, config_entry=, reauth), entity.py, real __init__.py (setup/unload + options reload), config_flow.py (config+options+reauth), lawn_mower.py, diagnostics.py, platform stubs (sensor/binary_sensor/button/number/select/camera), strings.json + translations (en/fr). Redaction verified locally; HA-runtime modules compile and follow verified current HA APIs (full pytest pending in HA env).
- 2026-06-18 — Phase 4 committed: real sensor/binary_sensor/button/number/select platforms (capability-gated, description-driven). Added client async_locate/async_reset_error (+ stub). mowing_mode select deferred (no verified backend support); CAP_MOWING_MODE no longer advertised by stub. Stub logic re-verified via shim.
- 2026-06-18 — Phase 5 committed: real camera.py — dynamic one-entity-per-reported-camera, role-named, stable unique_id, snapshot/live/composite, attributes without URLs, privacy mode + disable-when-docked/at-night + enabled-roles/prefer-composite filtering. Compiles; entity behaviour to be exercised in HA/CI (camera tests in Phase 8).
- 2026-06-18 — Phase 6 committed: maintenance.py — Store-backed MaintenanceManager (warranty/blade/maintenance compute, blade-baseline runtime, next-change estimate, log, anti-spam re-arming notifications). Maintenance sensors/binary_sensors/buttons/numbers wired into the 4 platforms; manager created in __init__ and re-evaluates alerts on each coordinator tick. Compiles; HA-runtime tests in Phase 8.
- 2026-06-18 — Phase 7 committed: services.py + services.yaml (10 services: refresh, start_zone, set_cutting_height, send_command_raw [guarded], set_purchase_date, set_warranty_duration, mark_blades_changed, add_maintenance_event, reset_maintenance_counters, export_maintenance_log [response]). Services registered in __init__, removed on last unload. client.async_send_command_raw added (+ stub). Docs: dashboard.md (Lovelace + 7 automations), maintenance.md, security.md.

## Open Questions / Unknowns

- Does the robot expose a local API, or is it cloud-only? (UNVERIFIED — see docs/api_mapping.md)
- Camera count, roles, and streaming tech (RTSP/WebRTC/proprietary)? (UNVERIFIED — see docs/camera_mapping.md)
- Auth model and cloud domains? (UNVERIFIED)

## Next Step

`/gsd:discuss-phase 1` equivalent → continue Phase 1 build (skeleton + discovery tools), then Phase 2 (client + stub).

---
*Last updated: 2026-06-17*
