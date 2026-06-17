# GSD Tasks — ha-airseekers

Atomic tasks for the **current** phase. Completed phases are summarised in `.planning/STATE.md`.

## Phase 1 — Foundation, Repo Skeleton & Discovery Tooling

### Skeleton
- [x] Standalone git repo + `.gitignore` (repo = git.figpom.io/figpom/airseekers)
- [x] GSD planning docs (`.planning/`, `docs/gsd/`)
- [x] `hacs.json` (minimal; `render_readme` removed — unsupported)
- [x] `custom_components/airseekers/manifest.json`
- [x] `custom_components/airseekers/const.py` (domain, platforms, capability keys, defaults, SENSITIVE_KEYS)
- [x] `pyproject.toml`, `requirements_test.txt`, `.env.example`
- [x] README (replaced GitLab template)
- [x] Package `__init__.py` placeholder (real setup in Phase 3)
- [x] `docs/architecture.md` (verified HA API reference), `docs/api_mapping.md`, `docs/camera_mapping.md`

### Discovery tooling (`tools/`) — all written & syntax-checked
- [x] `discover_lan.py` (mDNS/SSDP/ARP + light port detection → markdown report)
- [x] `probe_http.py`
- [x] `mqtt_probe.py`
- [x] `airseekers_cloud_probe.py` (aiohttp skeleton, `.env`, TODO endpoints, redact())
- [x] `discover_camera_streams.py`, `discover_camera_inventory.py`
- [x] `probe_rtsp.py`, `probe_mjpeg.py`, `probe_camera_url.py`
- [x] `README_DISCOVERY.md`, `analyze_app_camera_calls.md`, `extract_app_domains.md`

### Security seed
- [ ] Reusable redaction helper module (`redact.py`) — SENSITIVE_KEYS defined in const.py; helper lands with diagnostics in Phase 3

### Phase 1 limits / notes
- HACS custom-repo install needs a **GitHub** mirror (origin is self-hosted GitLab); manual install works now.
- `__init__.py` is a placeholder — the integration is not yet loadable in HA (Phase 3 delivers setup).

## Phase 2 — Async API Client & Working Stub Backend ✅ (committed)
- [x] `api.py`: exceptions (auth/connection/api/unsupported/camera) + typed models
  (Device/Status/Zone/Fault/CameraInfo/Warranty/Blade/Maintenance)
- [x] `AirseekersClient` full method surface dispatching to a backend
- [x] `StubBackend` fully functional (state machine, zones, ≥5 cameras incl composite_360,
  distinct PNG snapshots, cutting-height bounds, enable/disable cameras)
- [x] Skeleton backends (local_http/cloud_http/mqtt/rtsp) raise AirseekersUnsupportedFeature — no invented endpoints
- [x] Pure compute helpers: `AirseekersWarrantyState.compute`, `AirseekersBladeState.compute`
- [x] `tests/conftest.py` + `tests/test_api.py`; verified locally via HA const shim

## Phase 3 — Home Assistant Core Integration ✅ (committed)
- [x] `redact.py` reusable redaction (keys, Authorization, tokenised/signed URLs) — tested locally
- [x] `coordinator.py` adaptive polling (active/idle), `config_entry=`, reauth via ConfigEntryAuthFailed
- [x] `entity.py` base (CoordinatorEntity + DeviceInfo + availability)
- [x] real `__init__.py` (setup/unload, runtime_data, login, options-reload listener)
- [x] `config_flow.py` config + options + reauth (OptionsFlow w/o setting config_entry)
- [x] `lawn_mower.py` (START_MOWING|PAUSE|DOCK; activity map; stop is button/service later)
- [x] `diagnostics.py` (redacted; camera stream/snapshot URLs dropped)
- [x] platform stubs sensor/binary_sensor/button/number/select/camera (no-op setup, fill later)
- [x] strings.json + translations/en.json + fr.json
- [ ] Live load in a real HA instance — recommended before tagging v0.1.0 (not runnable on this box)

## Phase 4 — Entity platforms ✅ (committed)
- [x] `sensor.py` — battery, state, activity, current_zone, error_code/message, rtk_status,
  gps_signal, wifi_rssi, blade_motor_state, total_mowing_time, total_mowing_cycles, last_update (capability-gated)
- [x] `binary_sensor.py` — online, charging, docked, raining, error, obstacle_detected, camera_available
- [x] `button.py` — refresh, start, pause, dock, stop, locate, reset_error
- [x] `number.py` — cutting_height (options-overridable min/max)
- [x] `select.py` — zone (starts zone mow), backend, camera_mode  (mowing_mode deferred: no verified backend support)
- [x] client `async_locate` / `async_reset_error` (+ stub) for the locate/reset buttons
- [ ] entity-name translations (en/fr) — deferred to Phase 8 polish (names are English strings for now)

## Phase 5 — Dynamic multi-camera support ✅ (committed)
- [x] `camera.py`: one entity per reported camera (dynamic), role-named, `unique_id={device_id}_{camera_id}`
- [x] snapshot (`async_camera_image`) + live (`stream_source` + STREAM feature) + composite flag
- [x] attributes (camera_id/role/stream_type/supports_*/is_composite/source/last_frame_at/privacy_mode), NO URLs
- [x] options: enable entities, enabled roles, prefer composite (enabled-default), privacy mode,
  disable when docked / at night, discovery mode = disabled short-circuit
- [ ] camera entity tests (snapshot-only/live/composite/privacy) — Phase 8 (needs HA harness)
- [ ] runtime addition of NEW cameras appearing after setup — future enhancement (stub set is static)

## Phase 6 — Maintenance, warranty & blade wear ✅ (committed)
- [x] `maintenance.py` MaintenanceManager (Store persistence; blade baseline runtime; warranty/blade/maintenance compute; next-change estimate; log; anti-spam re-arming notifications)
- [x] maintenance sensors (warranty end/days/status, blade runtime/percent/status, last/next blade change, maintenance status)
- [x] maintenance binary sensors (warranty expiring soon/expired, blades need replacement, maintenance required)
- [x] maintenance buttons (reset blade timer, mark blades changed, reset alert, export log)
- [x] maintenance numbers (blade lifetime hours, warranty warning days, blade warning percent)
- [x] wired into __init__ (manager) + 4 platforms; alerts re-evaluated each coordinator tick
- [ ] maintenance tests (warranty math edge cases, restore, no-spam) — Phase 8 (HA harness)

## Phase 7 — Services & Lovelace dashboard ✅ (committed)
- [x] `services.py` + `services.yaml`: refresh, start_zone, set_cutting_height, send_command_raw
  (guarded by enable_raw_command), set_purchase_date, set_warranty_duration, mark_blades_changed,
  add_maintenance_event, reset_maintenance_counters, export_maintenance_log (SupportsResponse)
- [x] device/entity target resolution → config entry; register once; remove on last unload
- [x] `client.async_send_command_raw` (+ stub no-op, never logs payload)
- [x] `docs/dashboard.md` (Lovelace dashboard + 7 example automations), `docs/maintenance.md`, `docs/security.md`

## Backlog (next phase)
- Phase 8: full pytest suite (flows/coordinator/lawn_mower/platforms/cameras/diagnostics/maintenance/
  restore/no-spam), ruff/mypy clean, README/doc polish, entity-name translations, final quality gate.
  Then a live HA stub-mode smoke test → tag v0.1.0.

*Move items to `.planning/STATE.md` recent-activity when a phase closes; reset this file to the new phase.*
