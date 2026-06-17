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

## Backlog (next phases)
- Phase 2: `api.py` (models, exceptions, client, backends incl. working stub) + client tests.
- Phase 3: `__init__.py`, `coordinator.py`, `config_flow.py`, `lawn_mower.py`, `diagnostics.py`.

*Move items to `.planning/STATE.md` recent-activity when a phase closes; reset this file to the new phase.*
