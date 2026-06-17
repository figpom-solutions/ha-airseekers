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

## Backlog (next phases)
- Phase 3: `redact.py`, `coordinator.py`, real `__init__.py` (setup/unload), `config_flow.py`
  (config+options+reauth), `entity.py` base, `lawn_mower.py`, `diagnostics.py`.
  Remember verified API facts: coordinator needs `config_entry=`; OptionsFlow must not set
  `config_entry` in `__init__`; no native lawn-mower STOP feature.

*Move items to `.planning/STATE.md` recent-activity when a phase closes; reset this file to the new phase.*
