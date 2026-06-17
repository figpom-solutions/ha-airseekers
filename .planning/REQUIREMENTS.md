# Requirements: ha-airseekers

**Defined:** 2026-06-17
**Core Value:** Install via HACS → add the robot → get a fully working Home Assistant device (mower, sensors, cameras, maintenance) even before the real protocol is mapped, via a complete stub backend.

## v1 Requirements

### Setup & Distribution (SETUP)

- [ ] **SETUP-01**: Integration is HACS-valid and installable as a custom repository
- [ ] **SETUP-02**: Integration loads in Home Assistant with a valid `manifest.json` (config_flow, iot_class, version)
- [ ] **SETUP-03**: User adds the robot via a config flow (backend, model, name, optional IP/credentials)
- [ ] **SETUP-04**: User can change runtime settings via an options flow without re-adding the device
- [ ] **SETUP-05**: Integration supports a reauth flow when authentication expires/fails
- [ ] **SETUP-06**: Backend is selectable (stub / local_http / cloud_http / mqtt) at setup and in options

### API Client & Backends (API)

- [ ] **API-01**: Async `AirseekersClient` exposes a stable method surface used by all entities
- [ ] **API-02**: Typed model objects (device, status, zone, camera, maintenance, warranty, blade, error)
- [ ] **API-03**: Domain exceptions for auth / connection / api / unsupported-feature / camera-unavailable
- [ ] **API-04**: `stub` backend is fully functional and exercises every entity and capability
- [ ] **API-05**: `local_http`, `cloud_http`, `mqtt`, `rtsp` backends exist as clean stubs raising clear "unsupported until discovered" errors — never inventing endpoints
- [ ] **API-06**: Client never logs credentials, tokens, refresh tokens, signed URLs, or stream URLs

### Mower Control (MOWER)

- [ ] **MOWER-01**: `lawn_mower` entity supports start mowing, pause, and dock
- [ ] **MOWER-02**: Best-effort stop is exposed (button/service) given no native stop feature
- [ ] **MOWER-03**: Activity maps to mowing/paused/docked/returning/error and reported state
- [ ] **MOWER-04**: Zone mowing is supported when the backend reports zones
- [ ] **MOWER-05**: Battery, current state, activity, and active error surface on the device

### Sensors (SENSOR)

- [ ] **SENSOR-01**: Robot sensors created from capabilities (battery, state, activity, zone, error code/message, RTK status, GPS signal, Wi-Fi RSSI, blade motor state, total mowing time, total cycles, last update)
- [ ] **SENSOR-02**: Binary sensors created from capabilities (online, charging, docked, raining, error, obstacle detected, camera available)
- [ ] **SENSOR-03**: Only sensors backed by available capabilities are created

### Controls (CONTROL)

- [ ] **CONTROL-01**: Buttons for refresh/dock/pause/start/stop/locate/reset-error (per capability)
- [ ] **CONTROL-02**: Number entity for cutting height with configurable min/max when not API-provided
- [ ] **CONTROL-03**: Select entities for zone / mowing mode / backend mode / camera mode (per capability)

### Cameras (CAM)

- [ ] **CAM-01**: One `camera` entity is created per camera returned by the backend (dynamic 1..N)
- [ ] **CAM-02**: Camera entities are named/identified by role with stable `unique_id` `{device_id}_{camera_id}`
- [ ] **CAM-03**: Snapshot-only cameras implement image fetch; live cameras implement stream source
- [ ] **CAM-04**: Composite (300/360) cameras are supported and flagged in attributes
- [ ] **CAM-05**: Stub backend provides ≥5 simulated cameras (front/left/right/rear/composite_360) with distinct labelled images
- [ ] **CAM-06**: Camera behaviour is configurable (enable, enabled roles, prefer composite/local, refresh interval, disable when docked/at night, privacy mode)
- [ ] **CAM-07**: Stream URLs/tokens are never written to logs or diagnostics

### Maintenance, Warranty & Blades (MAINT)

- [ ] **MAINT-01**: Warranty tracked from purchase date + duration → end date, days remaining, status
- [ ] **MAINT-02**: Blade wear tracked: runtime hours, life-remaining %, status, last/next change estimate
- [ ] **MAINT-03**: Cumulative mowing time and cycle counts are tracked and persisted
- [ ] **MAINT-04**: Maintenance state persists across Home Assistant restarts (Store + RestoreEntity)
- [ ] **MAINT-05**: Binary sensors for warranty expiring soon / expired / blades need replacement / maintenance required
- [ ] **MAINT-06**: Buttons for reset-blade-timer / mark-blades-changed / reset-maintenance-alert / export-log
- [ ] **MAINT-07**: Numbers for blade lifetime hours / warranty warning days / blade warning percent (defaults 100h / 60d / 20%)
- [ ] **MAINT-08**: Maintenance log records dated events (type, comment, hours, cycles) with defined event types
- [ ] **MAINT-09**: Persistent-notification alerts fire without spam and re-arm after reset/threshold change/new event

### Services (SVC)

- [ ] **SVC-01**: `start_zone`, `set_cutting_height`, `refresh` control services
- [ ] **SVC-02**: `send_command_raw` debug service, disabled by default and clearly documented
- [ ] **SVC-03**: Maintenance services: set_purchase_date, set_warranty_duration, mark_blades_changed, add_maintenance_event, export_maintenance_log, reset_maintenance_counters

### Discovery Tooling (DISCO)

- [ ] **DISCO-01**: `discover_lan.py` performs non-intrusive mDNS/SSDP/ARP + light port detection → markdown report
- [ ] **DISCO-02**: `probe_http.py` inspects HTTP/HTTPS on a given host without brute force → report
- [ ] **DISCO-03**: `mqtt_probe.py` detects broker/ports only, publishes nothing without explicit confirmation
- [ ] **DISCO-04**: `airseekers_cloud_probe.py` aiohttp skeleton with TODO endpoints, `.env`-based, no secrets in code
- [ ] **DISCO-05**: Camera discovery tools (`discover_camera_streams.py`, `discover_camera_inventory.py`, `probe_rtsp.py`, `probe_mjpeg.py`, `probe_camera_url.py`) test only owner-supplied targets, no brute force
- [ ] **DISCO-06**: Discovery docs (`README_DISCOVERY.md`, `analyze_app_camera_calls.md`, `extract_app_domains.md`) explain owner-side capture & anonymisation

### Security & Diagnostics (SEC)

- [ ] **SEC-01**: `diagnostics.py` outputs backend, capabilities, entities, anonymised state, camera count/roles, maintenance/warranty state
- [ ] **SEC-02**: Reusable redaction masks sensitive keys, tokenised URLs, sensitive query params, Authorization headers
- [ ] **SEC-03**: Diagnostics never include username/password/token/refresh-token/signed URL/sensitive stream URL/public IP

### Dashboard (DASH)

- [ ] **DASH-01**: Ready-to-use Lovelace dashboard (status, controls, zone, cutting height, error, cameras, RTK/GPS/Wi-Fi/rain, maintenance)
- [ ] **DASH-02**: "Maintenance AIRSEEKERS" section (battery gauge, warranty days/date, blade state, hours remaining, blades-changed button, last event)
- [ ] **DASH-03**: Example automations (no mow when raining/night, return on error, blocked notification, warranty 60d notice, blade replacement notice, mow block on critical maintenance)

### Quality (QA)

- [ ] **QA-01**: pytest unit tests covering config/options/reauth, coordinator, stub backend, mower, sensors, controls, multi-camera (snapshot/live/composite/privacy), diagnostics redaction, warranty math, blade math, persistence/restore, maintenance log, no-spam notifications
- [ ] **QA-02**: ruff clean; mypy where practical; imports verified
- [ ] **QA-03**: Complete README + docs (architecture, api_mapping, camera_mapping, maintenance, security, dashboard) honestly stating limits and never documenting an invented API

## v2 Requirements

### Future Protocol & Vision (FUT)

- **FUT-01**: Real `local_http` / `cloud_http` / `mqtt` backends implemented from owner-verified discovery
- **FUT-02**: Live map / zone editing if the protocol exposes it
- **FUT-03**: WebRTC / HLS live camera once stream tech is confirmed
- **FUT-04**: Optional Frigate integration for camera AI

## Out of Scope

| Feature | Reason |
|---------|--------|
| Inventing AIRSEEKERS endpoints/URLs/ports/payloads | Honesty + safety; real backends only from verified discovery |
| Hardcoded credentials or "magic" URLs | Security; configured by the user at runtime |
| Breaking/bypassing encryption or auth | Legal/ethical constraint |
| Recording/re-exposing camera streams externally by default | Privacy-first design |
| Reverse-engineering third-party accounts | Interop limited to the owner's own robot/account/network |

## Traceability

Populated during roadmap creation — see `.planning/ROADMAP.md`. Coverage summary kept in sync there.

**Coverage:**
- v1 requirements: 53 total
- Mapped to phases: 53 (see ROADMAP traceability table)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-17*
*Last updated: 2026-06-17 after initialization*
