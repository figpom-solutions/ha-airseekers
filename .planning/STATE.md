# Project State: ha-airseekers

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-17)

**Core value:** Install via HACS → add the robot → fully working HA device on the stub backend, before the real protocol is mapped.
**Current focus:** Milestone v2 — real **cloud_http** backend. Protocol discovery in progress (REST host verified; defeating cert pinning to read payloads).

## Status

- **Milestone v1 (stub integration):** ✅ done (Phases 1–8) + Phase 9 (stable entity convention).
- **Live install:** ✅ installed in the owner's real HA (`homeassistant-ha-1`, HA stable/Py3.14), loads cleanly, all `tron_*` entities created, runs end-to-end on `stub`.
- **Milestone v2 (real cloud backend):** 🟡 in progress — protocol discovery.
- **Mode:** YOLO + quality agents; model profile: quality.
- **GSD management:** manual (parent dir is an active GSD project; `gsd-sdk` anchors to the outer worktree).
- **Backend in use:** `stub` (data is simulated by design). Real `cloud_http` pending payload capture.

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
- 2026-06-18 — Phase 8 committed: pytest suite (config_flow/options/reauth, init setup/unload, entities, camera snapshot/composite/privacy, diagnostics redaction, maintenance warranty/blade/log/no-spam). GitHub Actions CI (ruff + ruff format + pytest + hassfest + HACS). README dev/CI note. MILESTONE COMPLETE — all 8 phases done.

- 2026-06-18 — Phase 9 (stable entity convention): forced deterministic `tron_*` entity_ids for every entity (via explicit entity_id + helper `build_entity_id`), kept stable across versions by unique_id. Added device_tracker.tron (GPS/RTK), switch.tron_camera_privacy & switch.tron_night_mowing, safety binary_sensors (lifted/tilted/blade_blocked), sensor.tron_firmware & sensor.tron_area, button.tron_find, select.tron_mowing_mode (re-added; stub now supports modes + position + area + safety). New platforms DEVICE_TRACKER, SWITCH. Delivered lovelace/airseekers_tron_dashboard.yaml. Tests updated to tron_* ids; api/const smokes pass.

- 2026-06-18 — Live install in real HA: copied component to `/config/custom_components/airseekers`, validated all 19 modules import against HA stable (Py3.14) in the container, restarted HA. **Fixed a setup bug** (`fix(coordinator)`: read initial update_interval from `entry`, not `self.config_entry` — was raising AttributeError in async_setup_entry). After fix: entry sets up cleanly, ~60 `tron_*` entities created. Confirmed to owner that stub data is simulated by design.
- 2026-06-18 — Protocol discovery (owner's own account/network): ran `tools/discover_lan.py` (robot not found on the wired LAN segment). Set up mitmproxy (Docker, `airseekers-mitm` on 10.0.0.7) — first HTTP proxy (app ignores proxy), then SOCKS5 fed by **PCAPdroid** (VPN, no-root) which captured the app. App **pins certs** → payloads not decrypted yet, but SNIs **verified**: `cloud-eu.airseekers-robotics.com` (REST) and `a26yx9tpysif9b-ats.iot.eu-central-1.amazonaws.com` (AWS IoT, mutual TLS). Committed to docs/api_mapping.md.

## Next (post-milestone v1)
- Let CI run on GitHub; fix any ruff/test findings. Tag **v0.1.0** (stub validated live ✅).
- Deferred polish: entity-name translations (fr/en), runtime addition of new cameras.

## Milestone v2 — Real cloud backend (in progress)
- [x] Discovery: REST host `cloud-eu.airseekers-robotics.com` + AWS IoT host verified (live capture).
- [ ] Defeat REST pinning via `apk-mitm` (repackage APK) → re-capture → decrypt REST payloads.
- [ ] Fill `docs/api_mapping.md` endpoint table (login/refresh/devices/status/commands) — anonymised.
- [ ] Implement `CloudHttpBackend` (REST + JWT, `cloud_polling`) in api.py; backend selectable.
- [ ] Mind one-session-per-account caveat (long idle poll; document app logout risk).
- **Out of scope:** AWS IoT MQTT real-time (mutual TLS, per-device cert — not third-party reusable); WebRTC camera relay.

## Open Questions / Unknowns (updated)

- Local API? → effectively **no** (cloud-only; AWS IoT + REST). RESOLVED.
- Cloud domains/auth? → REST `cloud-eu.airseekers-robotics.com`, JWT; **VERIFIED** (payload shapes still pending de-pinned capture).
- Cameras streaming tech? → cloud/WebRTC via AWS IoT relay; not locally reusable. Likely snapshot-only at best for HA.

## Next Step

Owner provides the AIRSEEKERS APK in `/home/vinok/mitm/` → run `apk-mitm` → reinstall patched app → re-capture via PCAPdroid (SOCKS5 10.0.0.7:8080, Block QUIC) → decrypt REST → implement `CloudHttpBackend`.

---
*Last updated: 2026-06-18*
