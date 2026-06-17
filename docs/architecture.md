# AIRSEEKERS Home Assistant Integration — Architecture & HA API Reference

This is the implementation reference for `custom_components/airseekers`. The HA API facts below were
verified against the current `home-assistant/core` `dev` branch (2025–2026). Where the AIRSEEKERS
protocol itself is concerned, see `api_mapping.md` / `camera_mapping.md` — nothing here assumes a real
endpoint.

## Module layout

```
custom_components/airseekers/
  __init__.py        # async_setup_entry / async_unload_entry, coordinator wiring, services
  const.py           # shared contract (no HA imports beyond Platform)
  api.py             # AirseekersClient + typed models + exceptions + backends (stub fully works)
  coordinator.py     # AirseekersDataUpdateCoordinator (adaptive polling)
  config_flow.py     # config + options + reauth flows
  diagnostics.py     # async_get_config_entry_diagnostics + redaction
  redact.py          # reusable redaction helper (shared by diagnostics + safe logging)
  entity.py          # AirseekersEntity base (CoordinatorEntity + DeviceInfo)
  lawn_mower.py      # LawnMowerEntity
  sensor.py binary_sensor.py button.py number.py select.py
  camera.py          # one entity per reported camera (dynamic)
  maintenance.py     # Store-backed maintenance/warranty/blade state + notifications
  services.yaml      # service schemas
```

The whole entity layer depends only on the `AirseekersClient` interface and the coordinator data, so
swapping the `stub` backend for a verified real backend never touches entities.

## Verified HA API surface

### Lawn mower
```python
from homeassistant.components.lawn_mower import (
    LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature,
)
```
- `LawnMowerActivity` (StrEnum): `ERROR, PAUSED, MOWING, DOCKED, RETURNING`.
- `LawnMowerEntityFeature` (IntFlag): `START_MOWING = 1, PAUSE = 2, DOCK = 4`. **There is no STOP feature.**
  Expose "stop" via a Button and/or an entity service, not via a feature flag.
- Implement `async_start_mowing`, `async_pause`, `async_dock`. `state` is `@final` and returns
  `self.activity` — so set `_attr_activity` (or override `activity`). Map our internal states:
  `charging`/`idle`/`offline`/`unknown` → choose closest activity (e.g. charging+docked → `DOCKED`,
  offline/unknown → leave `activity` `None` so the entity shows `unknown`).

### Coordinator
```python
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity, DataUpdateCoordinator, UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
```
- Pass `config_entry=` **explicitly** to `DataUpdateCoordinator.__init__` (omitting it breaks in 2026.8).
- `_async_update_data()` raises `UpdateFailed` on transient errors and `ConfigEntryAuthFailed` to
  trigger the reauth flow.
- `update_interval` is settable at runtime: assign a `timedelta` (fast when active, slow when idle);
  `None` stops polling. Recompute it after each update from the reported activity.
- Use `always_update=False` only if the coordinator data is `__eq__`-able (use a dataclass).

### Config / options / reauth
```python
type AirseekersConfigEntry = ConfigEntry[AirseekersRuntimeData]
```
- Store the client + coordinator in `entry.runtime_data` (typed), not `hass.data` ad-hoc.
- `async_setup_entry`: create client → first refresh → `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)`.
- `async_unload_entry`: `await hass.config_entries.async_unload_platforms(entry, PLATFORMS)` then close client.
- **OptionsFlow**: `config_entry` is now a read-only property — do **not** set it in `__init__`
  (raises `ValueError`) and do **not** pass it to `async_get_options_flow` (changed 2024.11, removed 2025.12).
- **Reauth**: `async_step_reauth` → `async_step_reauth_confirm`, finishing with
  `self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=...)`.

### Camera (dynamic, multi)
```python
from homeassistant.components.camera import Camera, CameraEntityFeature  # STREAM = 2
```
- `async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None`
- `stream_source(self) -> str | None`  (set `CameraEntityFeature.STREAM` when a live URL exists)
- All cameras for one robot share the device via identical `DeviceInfo.identifiers`; optionally use
  `via_device` if cameras are modelled as sub-devices.
- Create one entity per `AirseekersCameraInfo` returned by `client.async_get_cameras(device_id)`.
- Snapshot-only → implement `async_camera_image`; live → also implement `stream_source`.
- **Never** return/log a URL containing a token; redaction applies to diagnostics.

### Persistence (maintenance)
```python
from homeassistant.helpers.storage import Store
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import RestoreSensor  # async_get_last_sensor_data()
```
- Canonical maintenance state (purchase date, blade hours, cycles, last-change, log, alert-armed flags)
  lives in a `Store(hass, STORAGE_VERSION, STORAGE_KEY_MAINTENANCE)`. `async_delay_save` takes a callable.
- Cumulative sensors that must survive restart use `RestoreSensor`; read back with
  `await self.async_get_last_sensor_data()`.

### Diagnostics
```python
from homeassistant.components.diagnostics import async_redact_data
async def async_get_config_entry_diagnostics(hass, entry) -> dict: ...
```
- Redact via our `redact.py` (keys in `const.SENSITIVE_KEYS` + tokenised-URL/query/Authorization patterns).

### Misc verified facts
- `DeviceInfo` canonical import: `homeassistant.helpers.device_registry`.
- Entity services: `entity_platform.async_get_current_platform().async_register_entity_service(...)`.
- `async_extract_referenced_entity_ids` is deprecated (breaks 2026.8) → use `async_extract_entity_ids`.
- Persistent notifications: `homeassistant.components.persistent_notification.async_create/async_dismiss`.
- `manifest.json` HACS-required keys: `domain, name, version, codeowners, documentation, issue_tracker`.
- `hacs.json`: only `name` is required; `render_readme` is **no longer supported** (removed here).

## Coordinator polling strategy

| Robot activity | Interval | Source |
|----------------|----------|--------|
| mowing / returning / paused (active) | `poll_active_interval` (default 30s) | options |
| docked / charging / idle / offline | `poll_idle_interval` (default 300s) | options |

Recompute `update_interval` at the end of each successful `_async_update_data` from the new activity.
Never hammer a cloud backend — the idle interval floor protects shared cloud APIs.

## Backend abstraction

`AirseekersClient(backend=..., session=..., config=...)` dispatches to a backend implementing the same
async surface. `stub` is fully functional and default. `local_http`/`cloud_http`/`mqtt`/`rtsp` raise
`AirseekersUnsupportedFeature("... until the protocol is verified")` — never an invented call.

## Gotchas / recent API changes (watch list)

- Coordinator `config_entry=` now required (2026.8).
- OptionsFlow `config_entry` read-only; no `__init__` assignment, no arg to `async_get_options_flow`.
- No `STOP` lawn-mower feature — model stop separately.
- `async_extract_referenced_entity_ids` deprecated → `async_extract_entity_ids`.
- `hacs.json` `render_readme` unsupported.

*Verified against home-assistant/core dev branch, 2025–2026.*
