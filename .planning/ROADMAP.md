# Roadmap: ha-airseekers

**Created:** 2026-06-17
**Granularity:** standard (8 phases) — groups the owner's 14-section spec into validatable slices
**Mode:** layered, but Phase 2 delivers an early end-to-end "it loads and works on stub" slice

> Each phase ends with: files created/modified, tests run, remaining limits, next tasks, and an
> atomic git commit. The `stub` backend is the spine — it keeps every phase shippable while real
> backends stay UNVERIFIED.

---

### Phase 1: Foundation, Repo Skeleton & Discovery Tooling
**Goal:** A HACS-valid, well-structured repository skeleton plus the non-intrusive discovery tools and docs the owner needs to map the real protocol later.
**Requirements:** SETUP-01, SETUP-02, DISCO-01..06, SEC-02 (redaction helper seed)
**Success Criteria:**
1. Repo has the full directory layout, `hacs.json`, `manifest.json`, `pyproject.toml`, `.gitignore`, `.env.example`, README scaffold.
2. `custom_components/airseekers/` imports as a package; `const.py` defines the domain and capability keys.
3. `tools/` discovery scripts run and emit markdown reports without brute force and without leaking host secrets.
4. Discovery docs explain owner-side capture (mitmproxy on own phone) and anonymisation.

### Phase 2: Async API Client & Working Stub Backend
**Goal:** A typed async client with a backend abstraction whose `stub` backend is fully functional, so the integration can be exercised end-to-end with no real API.
**Requirements:** API-01..06
**Success Criteria:**
1. `api.py` defines typed models, domain exceptions, and `AirseekersClient` with the full method surface.
2. `stub` backend returns coherent, evolving simulated data (status, zones, cameras, maintenance).
3. `local_http`/`cloud_http`/`mqtt`/`rtsp` backends exist and raise clear "unsupported until discovered" errors — no invented endpoints.
4. Client unit tests pass against the stub; no secret is ever logged.

### Phase 3: Home Assistant Core Integration
**Goal:** The integration sets up in HA: coordinator, config/options/reauth flows, the lawn_mower entity, device info, and redacting diagnostics.
**Requirements:** SETUP-03..06, MOWER-01..05, SEC-01, SEC-03
**Success Criteria:**
1. Config flow adds a device on the stub backend; options flow edits polling/backend/camera/maintenance settings; reauth flow exists.
2. `DataUpdateCoordinator` polls with adaptive interval (fast active / slow idle), configurable.
3. `lawn_mower` entity starts/pauses/docks (+ best-effort stop) and maps activity states.
4. Diagnostics export anonymised state with all secrets redacted.

### Phase 4: Entity Platforms (sensors, binary sensors, buttons, numbers, selects)
**Goal:** Capability-driven entity platforms covering robot telemetry and controls.
**Requirements:** SENSOR-01..03, CONTROL-01..03
**Success Criteria:**
1. Sensors and binary sensors are created only for available capabilities and update via the coordinator.
2. Buttons trigger the matching client actions; cutting-height number respects configurable min/max.
3. Selects (zone/mowing mode/backend/camera mode) reflect and set state where supported.
4. Platform unit tests pass on the stub.

### Phase 5: Dynamic Multi-Camera Support
**Goal:** One camera entity per backend-reported camera, with roles, snapshot/live/composite handling, and privacy-first options.
**Requirements:** CAM-01..07
**Success Criteria:**
1. Cameras are created dynamically (1..N) with role-based names and stable unique IDs.
2. Stub provides ≥5 cameras (front/left/right/rear/composite_360) with distinct labelled images.
3. Snapshot-only vs live vs composite paths each work; camera options (enable/roles/privacy/schedule) apply.
4. No stream URL or token appears in logs or diagnostics; camera tests pass.

### Phase 6: Maintenance, Warranty & Blade Wear
**Goal:** Persistent maintenance subsystem: warranty countdown, blade wear, mowing hours/cycles, maintenance log, and non-spam alerts.
**Requirements:** MAINT-01..09
**Success Criteria:**
1. Warranty end/days/status and blade hours/percent/status compute correctly and survive restarts.
2. Maintenance sensors, binary sensors, buttons, and numbers behave per spec defaults (100h/60d/20%).
3. Maintenance log stores dated events; export works; counters reset safely.
4. Persistent notifications fire once, re-arm after reset/threshold change/new event; tests cover no-spam.

### Phase 7: Services & Lovelace Dashboard
**Goal:** Registered HA services (control + maintenance + guarded raw debug) and a ready-to-use dashboard with example automations.
**Requirements:** SVC-01..03, DASH-01..03
**Success Criteria:**
1. `services.yaml` and handlers expose all control and maintenance services; `send_command_raw` is disabled by default and documented.
2. Lovelace dashboard renders status, controls, cameras, RTK/GPS/Wi-Fi/rain, and a Maintenance section.
3. Example automations cover rain/night blocks, return-on-error, blocked/maintenance/warranty/blade notifications.

### Phase 8: Tests, Quality & Documentation
**Goal:** Comprehensive tests, clean linting/typing, and honest, complete documentation.
**Requirements:** QA-01..03
**Success Criteria:**
1. pytest suite covers flows, coordinator, stub, mower, platforms, multi-camera (snapshot/live/composite/privacy), redaction, warranty/blade math, persistence/restore, log, no-spam alerts.
2. ruff clean; mypy where practical; manifest/HACS validated; stub mode verified end-to-end.
3. README and docs are complete and clearly state limits; no invented API is documented anywhere.

---

## Traceability

| Requirement(s) | Phase |
|----------------|-------|
| SETUP-01, SETUP-02 | 1 |
| DISCO-01..06 | 1 |
| SEC-02 (seed) | 1 |
| API-01..06 | 2 |
| SETUP-03..06 | 3 |
| MOWER-01..05 | 3 |
| SEC-01, SEC-03 | 3 |
| SENSOR-01..03 | 4 |
| CONTROL-01..03 | 4 |
| CAM-01..07 | 5 |
| MAINT-01..09 | 6 |
| SVC-01..03 | 7 |
| DASH-01..03 | 7 |
| QA-01..03 | 8 |

**Coverage:** 53 v1 requirements, all mapped, 0 unmapped ✓

---
*Last updated: 2026-06-17 after initialization*
