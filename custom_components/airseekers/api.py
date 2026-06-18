"""Async API client for the AIRSEEKERS integration.

The integration talks to the robot exclusively through :class:`AirseekersClient`, which dispatches to
a pluggable *backend*. Only the ``stub`` backend is fully functional; it simulates a complete robot so
the whole integration can be exercised with no real API. The ``local_http`` / ``cloud_http`` / ``mqtt``
/ ``rtsp`` backends are deliberate skeletons that raise :class:`AirseekersUnsupportedFeature` until the
real protocol is verified by the owner — **no endpoint, URL, port, or payload is invented** here
(see ``docs/api_mapping.md``).

This module imports no Home Assistant runtime objects beyond the constants in :mod:`.const`, so it can
be unit-tested as a plain async library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
import logging
import struct
import time
import zlib

from .const import (
    BACKEND_CLOUD_HTTP,
    BACKEND_LOCAL_HTTP,
    BACKEND_MQTT,
    BACKEND_RTSP,
    BACKEND_STUB,
    BLADE_OK,
    BLADE_REPLACE,
    BLADE_SOON,
    CAP_AREA,
    CAP_BATTERY,
    CAP_BLADE_MOTOR,
    CAP_CAMERAS,
    CAP_CUTTING_HEIGHT,
    CAP_GPS,
    CAP_LOCATE,
    CAP_MOWING_MODE,
    CAP_OBSTACLE,
    CAP_POSITION,
    CAP_RAIN_SENSOR,
    CAP_RESET_ERROR,
    CAP_RTK,
    CAP_SAFETY,
    CAP_STOP,
    CAP_WIFI_RSSI,
    CAP_ZONES,
    DEFAULT_BLADE_LIFETIME_HOURS,
    DEFAULT_BLADE_WARNING_PERCENT,
    DEFAULT_CUTTING_HEIGHT_MAX,
    DEFAULT_CUTTING_HEIGHT_MIN,
    DEFAULT_MOWING_MODE,
    DEFAULT_WARRANTY_MONTHS,
    DEFAULT_WARRANTY_WARNING_DAYS,
    MAINTENANCE_OK,
    MODEL_TRON_MAX,
    MOWING_MODES,
    ROLE_COMPOSITE_360,
    ROLE_FRONT,
    ROLE_LEFT,
    ROLE_REAR,
    ROLE_RIGHT,
    STATE_CHARGING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_MOWING,
    STATE_PAUSED,
    STATE_RETURNING,
    STREAM_SNAPSHOT,
    WARRANTY_EXPIRE_SOON,
    WARRANTY_EXPIRED,
    WARRANTY_OK,
)

_LOGGER = logging.getLogger(__name__)

# States considered "active" for adaptive polling.
ACTIVE_STATES: frozenset[str] = frozenset({STATE_MOWING, STATE_RETURNING, STATE_PAUSED})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class AirseekersError(Exception):
    """Base class for all AIRSEEKERS client errors."""


class AirseekersAuthError(AirseekersError):
    """Authentication failed or the session expired."""


class AirseekersConnectionError(AirseekersError):
    """Could not reach the robot or its backend (network/timeout)."""


class AirseekersApiError(AirseekersError):
    """The backend returned an error or an invalid request was made."""


class AirseekersUnsupportedFeature(AirseekersError):
    """The selected backend does not (yet) support this operation."""


class AirseekersCameraUnavailable(AirseekersError):
    """A camera exists but its image/stream is currently unavailable."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class AirseekersFault:
    """An error/fault reported by the robot.

    Named ``AirseekersFault`` to avoid clashing with the ``AirseekersError`` exception base; the spec's
    ``AirseekersError`` model concept is represented by this dataclass.
    """

    code: str | None = None
    message: str | None = None
    occurred_at: datetime | None = None

    @property
    def active(self) -> bool:
        return bool(self.code) or bool(self.message)


@dataclass(slots=True)
class AirseekersZone:
    """A mowing zone."""

    zone_id: str
    name: str
    enabled: bool = True


@dataclass(slots=True)
class AirseekersCameraInfo:
    """Describes a single camera exposed by the backend."""

    camera_id: str
    name: str
    role: str
    stream_type: str
    stream_url: str | None = None
    snapshot_url: str | None = None
    supports_live: bool = False
    supports_snapshot: bool = True
    supports_ptz: bool = False
    is_composite: bool = False
    is_privacy_sensitive: bool = True
    source: str = "stub"


@dataclass(slots=True)
class AirseekersWarrantyState:
    """Computed warranty state. Pure helper reused by the maintenance subsystem (Phase 6)."""

    purchase_date: date | None = None
    warranty_months: int = DEFAULT_WARRANTY_MONTHS
    end_date: date | None = None
    days_remaining: int | None = None
    status: str = WARRANTY_OK

    @classmethod
    def compute(
        cls,
        purchase_date: date | None,
        warranty_months: int = DEFAULT_WARRANTY_MONTHS,
        warning_days: int = DEFAULT_WARRANTY_WARNING_DAYS,
        today: date | None = None,
    ) -> AirseekersWarrantyState:
        if purchase_date is None:
            return cls(purchase_date=None, warranty_months=warranty_months)
        today = today or date.today()
        # Add whole months without external deps.
        month_index = purchase_date.month - 1 + warranty_months
        year = purchase_date.year + month_index // 12
        month = month_index % 12 + 1
        # Clamp day to the last valid day of the target month.
        day = min(purchase_date.day, _days_in_month(year, month))
        end_date = date(year, month, day)
        days_remaining = (end_date - today).days
        if days_remaining < 0:
            status = WARRANTY_EXPIRED
        elif days_remaining <= warning_days:
            status = WARRANTY_EXPIRE_SOON
        else:
            status = WARRANTY_OK
        return cls(
            purchase_date=purchase_date,
            warranty_months=warranty_months,
            end_date=end_date,
            days_remaining=days_remaining,
            status=status,
        )


@dataclass(slots=True)
class AirseekersBladeState:
    """Computed blade-wear state. Pure helper reused by the maintenance subsystem (Phase 6)."""

    runtime_hours: float = 0.0
    lifetime_hours: float = DEFAULT_BLADE_LIFETIME_HOURS
    life_remaining_percent: float = 100.0
    status: str = BLADE_OK
    last_change: date | None = None
    next_change_estimate: date | None = None

    @classmethod
    def compute(
        cls,
        runtime_hours: float,
        lifetime_hours: float = DEFAULT_BLADE_LIFETIME_HOURS,
        warning_percent: float = DEFAULT_BLADE_WARNING_PERCENT,
        last_change: date | None = None,
    ) -> AirseekersBladeState:
        lifetime_hours = max(float(lifetime_hours), 0.0)
        runtime_hours = max(float(runtime_hours), 0.0)
        if lifetime_hours <= 0:
            remaining = 0.0
        else:
            remaining = max(0.0, 100.0 * (1.0 - runtime_hours / lifetime_hours))
        if remaining <= 0:
            status = BLADE_REPLACE
        elif remaining <= warning_percent:
            status = BLADE_SOON
        else:
            status = BLADE_OK
        return cls(
            runtime_hours=round(runtime_hours, 2),
            lifetime_hours=lifetime_hours,
            life_remaining_percent=round(remaining, 1),
            status=status,
            last_change=last_change,
        )


@dataclass(slots=True)
class AirseekersMaintenanceState:
    """Device-reported maintenance counters plus computed warranty/blade state."""

    total_mowing_time_hours: float = 0.0
    total_cycles: int = 0
    blade: AirseekersBladeState = field(default_factory=AirseekersBladeState)
    warranty: AirseekersWarrantyState = field(default_factory=AirseekersWarrantyState)
    status: str = MAINTENANCE_OK
    log: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class AirseekersDevice:
    """Static-ish description of a robot."""

    device_id: str
    name: str
    model: str = MODEL_TRON_MAX
    firmware: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    cutting_height_min: int = DEFAULT_CUTTING_HEIGHT_MIN
    cutting_height_max: int = DEFAULT_CUTTING_HEIGHT_MAX

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(slots=True)
class AirseekersStatus:
    """Live status snapshot used by the coordinator and all entities."""

    device_id: str
    state: str = STATE_DOCKED
    online: bool = True
    battery_level: int | None = None
    charging: bool = False
    docked: bool = True
    returning: bool = False
    raining: bool | None = None
    obstacle_detected: bool | None = None
    lifted: bool | None = None
    tilted: bool | None = None
    blade_blocked: bool | None = None
    blade_motor_on: bool | None = None
    current_zone: str | None = None
    mowing_mode: str | None = None
    rtk_status: str | None = None
    gps_signal: int | None = None
    wifi_rssi: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    gps_accuracy: float | None = None
    cutting_height_mm: int | None = None
    area_mowed_m2: float | None = None
    total_mowing_time_hours: float = 0.0
    total_cycles: int = 0
    fault: AirseekersFault = field(default_factory=AirseekersFault)
    last_update: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def has_error(self) -> bool:
        return self.state == STATE_ERROR or self.fault.active


def _days_in_month(year: int, month: int) -> int:
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


# ---------------------------------------------------------------------------
# Tiny dependency-free PNG writer (used by the stub for distinct camera snapshots).
# Phase 5 may overlay role text; Phase 2 only needs a valid, visually-distinct image per camera.
# ---------------------------------------------------------------------------
def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    row = bytes((r, g, b)) * width
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter type 0 (None) per scanline
        raw.extend(row)

    def _chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, truecolor RGB
    idat = zlib.compress(bytes(raw), 9)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


_ROLE_COLORS: dict[str, tuple[int, int, int]] = {
    ROLE_FRONT: (198, 40, 40),
    ROLE_LEFT: (46, 125, 50),
    ROLE_RIGHT: (21, 101, 192),
    ROLE_REAR: (249, 168, 37),
    ROLE_COMPOSITE_360: (106, 27, 154),
}


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------
class AirseekersBackend(ABC):
    """Common async surface every backend implements."""

    name: str = "abstract"

    # Whether this backend performs HTTP I/O and therefore needs an aiohttp ``ClientSession``.
    # Kept False for the stub and the not-yet-implemented skeletons so callers (e.g. the config
    # flow) don't allocate a real session — and its DNS resolver thread — for a backend that never
    # uses it. Flip to True on a backend once it makes real network calls.
    requires_session: bool = False

    async def async_login(self, username: str, password: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: login not supported")

    async def async_refresh_token(self) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: token refresh not supported")

    @abstractmethod
    async def async_get_devices(self) -> list[AirseekersDevice]: ...

    @abstractmethod
    async def async_get_status(self, device_id: str) -> AirseekersStatus: ...

    async def async_start_mowing(self, device_id: str, zone_id: str | None = None) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: start not supported")

    async def async_pause(self, device_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: pause not supported")

    async def async_dock(self, device_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: dock not supported")

    async def async_stop(self, device_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: stop not supported")

    async def async_set_cutting_height(self, device_id: str, height_mm: int) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: set cutting height not supported")

    async def async_set_schedule(self, device_id: str, schedule: object | None = None) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: set schedule not supported")

    async def async_set_mowing_mode(self, device_id: str, mode: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: set mowing mode not supported")

    async def async_locate(self, device_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: locate not supported")

    async def async_reset_error(self, device_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: reset error not supported")

    async def async_send_command_raw(
        self, device_id: str, command: str, params: dict | None = None
    ) -> object:
        raise AirseekersUnsupportedFeature(f"{self.name}: raw command not supported")

    async def async_get_zones(self, device_id: str) -> list[AirseekersZone]:
        return []

    async def async_get_cameras(self, device_id: str) -> list[AirseekersCameraInfo]:
        return []

    async def async_get_camera_snapshot(self, device_id: str, camera_id: str) -> bytes:
        raise AirseekersCameraUnavailable(f"{self.name}: snapshot not supported")

    async def async_get_camera_stream_url(self, device_id: str, camera_id: str) -> str | None:
        return None

    async def async_enable_camera(self, device_id: str, camera_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: enable camera not supported")

    async def async_disable_camera(self, device_id: str, camera_id: str) -> None:
        raise AirseekersUnsupportedFeature(f"{self.name}: disable camera not supported")

    async def async_close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Stub backend — fully functional simulation
# ---------------------------------------------------------------------------
class StubBackend(AirseekersBackend):
    """A complete in-memory simulation of a TRON Max so the integration works without a real API."""

    name = BACKEND_STUB

    DEVICE_ID = "stub-tron-max-001"

    def __init__(self, *, config: Mapping[str, object] | None = None) -> None:
        cfg = dict(config or {})
        self._device = AirseekersDevice(
            device_id=self.DEVICE_ID,
            name=str(cfg.get("device_name") or "AIRSEEKERS TRON Max"),
            model=str(cfg.get("model") or MODEL_TRON_MAX),
            firmware="stub-1.0.0",
            capabilities=frozenset(
                {
                    CAP_BATTERY,
                    CAP_ZONES,
                    CAP_CUTTING_HEIGHT,
                    CAP_MOWING_MODE,
                    CAP_RTK,
                    CAP_GPS,
                    CAP_POSITION,
                    CAP_AREA,
                    CAP_WIFI_RSSI,
                    CAP_BLADE_MOTOR,
                    CAP_RAIN_SENSOR,
                    CAP_OBSTACLE,
                    CAP_SAFETY,
                    CAP_CAMERAS,
                    CAP_LOCATE,
                    CAP_RESET_ERROR,
                    CAP_STOP,
                }
            ),
        )
        # Mutable simulation state.
        self._state = STATE_DOCKED
        self._battery = 100.0
        self._cutting_height = 45
        self._current_zone: str | None = None
        self._total_mowing_hours = 12.5
        self._total_cycles = 7
        self._blade_runtime_hours = 12.5
        self._mowing_mode = DEFAULT_MOWING_MODE
        self._area_mowed_m2 = 1240.0
        # A plausible starting position (offset deterministically while mowing).
        self._lat = 48.8566
        self._lon = 2.3522
        self._tick_count = 0
        self._fault = AirseekersFault()
        self._dock_eta: float = 0.0  # monotonic deadline for RETURNING -> DOCKED
        self._last_tick = time.monotonic()
        self._zones = [
            AirseekersZone("zone-front", "Front lawn"),
            AirseekersZone("zone-back", "Back lawn"),
            AirseekersZone("zone-side", "Side strip"),
        ]
        self._cameras = [
            AirseekersCameraInfo("cam-front", "Front", ROLE_FRONT, STREAM_SNAPSHOT),
            AirseekersCameraInfo("cam-left", "Left", ROLE_LEFT, STREAM_SNAPSHOT),
            AirseekersCameraInfo("cam-right", "Right", ROLE_RIGHT, STREAM_SNAPSHOT),
            AirseekersCameraInfo("cam-rear", "Rear", ROLE_REAR, STREAM_SNAPSHOT),
            AirseekersCameraInfo(
                "cam-360", "360 View", ROLE_COMPOSITE_360, STREAM_SNAPSHOT, is_composite=True
            ),
        ]
        self._disabled_cameras: set[str] = set()

    # -- helpers ----------------------------------------------------------
    def _check_device(self, device_id: str) -> None:
        if device_id != self.DEVICE_ID:
            raise AirseekersApiError(f"unknown device_id: {device_id!r}")

    def _advance(self) -> None:
        """Advance the simulation based on real elapsed time since the last call."""
        now = time.monotonic()
        elapsed = now - self._last_tick
        self._last_tick = now
        hours = elapsed / 3600.0

        if self._state == STATE_MOWING:
            self._battery = max(0.0, self._battery - elapsed * (8.0 / 3600.0) * 100 / 100)
            self._total_mowing_hours += hours
            self._blade_runtime_hours += hours
            # ~3 m²/min mowing rate, and a small deterministic wander in position.
            self._area_mowed_m2 += elapsed * (3.0 / 60.0)
            self._tick_count += 1
            self._lat += 0.00001 * ((self._tick_count % 5) - 2)
            self._lon += 0.00001 * ((self._tick_count % 3) - 1)
            if self._battery <= 15.0:
                self._state = STATE_RETURNING
                self._dock_eta = now + 20.0
        elif self._state == STATE_RETURNING:
            self._battery = max(0.0, self._battery - elapsed * (4.0 / 3600.0) * 100 / 100)
            if now >= self._dock_eta:
                self._state = STATE_DOCKED
                self._total_cycles += 1
                self._current_zone = None
        elif self._state in (STATE_DOCKED, STATE_CHARGING):
            if self._battery < 100.0:
                self._battery = min(100.0, self._battery + elapsed * (40.0 / 3600.0) * 100 / 100)
                self._state = STATE_CHARGING if self._battery < 100.0 else STATE_DOCKED
            else:
                self._state = STATE_DOCKED

    # -- API surface ------------------------------------------------------
    async def async_login(self, username: str, password: str) -> None:
        # The stub accepts any non-empty credentials and never stores or logs them.
        if not username or not password:
            raise AirseekersAuthError("stub: empty credentials")
        _LOGGER.debug("stub backend: login accepted (credentials not stored)")

    async def async_refresh_token(self) -> None:
        return None

    async def async_get_devices(self) -> list[AirseekersDevice]:
        return [replace(self._device)]

    async def async_get_status(self, device_id: str) -> AirseekersStatus:
        self._check_device(device_id)
        self._advance()
        battery = round(self._battery)
        docked = self._state in (STATE_DOCKED, STATE_CHARGING)
        return AirseekersStatus(
            device_id=device_id,
            state=self._state,
            online=True,
            battery_level=battery,
            charging=self._state == STATE_CHARGING,
            docked=docked,
            returning=self._state == STATE_RETURNING,
            raining=False,
            obstacle_detected=False,
            lifted=False,
            tilted=False,
            blade_blocked=False,
            blade_motor_on=self._state == STATE_MOWING,
            current_zone=self._current_zone,
            mowing_mode=self._mowing_mode,
            rtk_status="fixed",
            gps_signal=98,
            wifi_rssi=-54,
            latitude=round(self._lat, 6),
            longitude=round(self._lon, 6),
            gps_accuracy=0.02,
            cutting_height_mm=self._cutting_height,
            area_mowed_m2=round(self._area_mowed_m2, 1),
            total_mowing_time_hours=round(self._total_mowing_hours, 2),
            total_cycles=self._total_cycles,
            fault=replace(self._fault),
            last_update=datetime.now(UTC),
        )

    async def async_start_mowing(self, device_id: str, zone_id: str | None = None) -> None:
        self._check_device(device_id)
        if zone_id is not None and zone_id not in {z.zone_id for z in self._zones}:
            raise AirseekersApiError(f"unknown zone_id: {zone_id!r}")
        self._advance()
        self._fault = AirseekersFault()
        self._current_zone = zone_id
        self._state = STATE_MOWING

    async def async_pause(self, device_id: str) -> None:
        self._check_device(device_id)
        self._advance()
        if self._state in (STATE_MOWING, STATE_RETURNING):
            self._state = STATE_PAUSED

    async def async_dock(self, device_id: str) -> None:
        self._check_device(device_id)
        self._advance()
        self._state = STATE_RETURNING
        self._dock_eta = time.monotonic() + 20.0

    async def async_stop(self, device_id: str) -> None:
        self._check_device(device_id)
        self._advance()
        self._state = STATE_IDLE

    async def async_set_cutting_height(self, device_id: str, height_mm: int) -> None:
        self._check_device(device_id)
        if not (self._device.cutting_height_min <= height_mm <= self._device.cutting_height_max):
            raise AirseekersApiError(
                f"cutting height {height_mm} mm out of range "
                f"[{self._device.cutting_height_min}, {self._device.cutting_height_max}]"
            )
        self._cutting_height = int(height_mm)

    async def async_set_schedule(self, device_id: str, schedule: object | None = None) -> None:
        self._check_device(device_id)
        # The stub accepts and discards the schedule; persisted scheduling is a future feature.
        return None

    async def async_set_mowing_mode(self, device_id: str, mode: str) -> None:
        self._check_device(device_id)
        if mode not in MOWING_MODES:
            raise AirseekersApiError(f"unknown mowing mode: {mode!r}")
        self._mowing_mode = mode

    async def async_locate(self, device_id: str) -> None:
        self._check_device(device_id)
        _LOGGER.debug("stub backend: locate requested (simulated beep)")

    async def async_reset_error(self, device_id: str) -> None:
        self._check_device(device_id)
        self._advance()
        self._fault = AirseekersFault()
        if self._state == STATE_ERROR:
            self._state = STATE_IDLE

    async def async_send_command_raw(
        self, device_id: str, command: str, params: dict | None = None
    ) -> object:
        self._check_device(device_id)
        # Never log the payload; only acknowledge the command name length for debugging.
        _LOGGER.debug(
            "stub backend: raw command %r received (%d params)", command, len(params or {})
        )
        return {"ok": True, "command": command, "backend": self.name}

    async def async_get_zones(self, device_id: str) -> list[AirseekersZone]:
        self._check_device(device_id)
        return [replace(z) for z in self._zones]

    async def async_get_cameras(self, device_id: str) -> list[AirseekersCameraInfo]:
        self._check_device(device_id)
        return [replace(c) for c in self._cameras if c.camera_id not in self._disabled_cameras]

    async def async_get_camera_snapshot(self, device_id: str, camera_id: str) -> bytes:
        self._check_device(device_id)
        cam = next((c for c in self._cameras if c.camera_id == camera_id), None)
        if cam is None:
            raise AirseekersCameraUnavailable(f"unknown camera_id: {camera_id!r}")
        if camera_id in self._disabled_cameras:
            raise AirseekersCameraUnavailable(f"camera {camera_id} is disabled")
        color = _ROLE_COLORS.get(cam.role, (96, 96, 96))
        return _solid_png(320, 240, color)

    async def async_get_camera_stream_url(self, device_id: str, camera_id: str) -> str | None:
        self._check_device(device_id)
        # Stub cameras are snapshot-only — no live URL (and we never fabricate one).
        return None

    async def async_enable_camera(self, device_id: str, camera_id: str) -> None:
        self._check_device(device_id)
        self._disabled_cameras.discard(camera_id)

    async def async_disable_camera(self, device_id: str, camera_id: str) -> None:
        self._check_device(device_id)
        self._disabled_cameras.add(camera_id)


# ---------------------------------------------------------------------------
# Skeleton backends — intentionally not implemented (no invented protocol)
# ---------------------------------------------------------------------------
class _UnimplementedBackend(AirseekersBackend):
    """Shared base for backends awaiting verified protocol discovery."""

    _doc = "docs/api_mapping.md"

    def __init__(
        self, *, session: object | None = None, config: Mapping[str, object] | None = None
    ):
        self._session = session
        self._config = dict(config or {})

    def _fail(self) -> AirseekersUnsupportedFeature:
        return AirseekersUnsupportedFeature(
            f"The '{self.name}' backend is not implemented yet. Complete it only from owner-verified "
            f"protocol discovery — see {self._doc}. The integration ships a working 'stub' backend in "
            "the meantime."
        )

    async def async_get_devices(self) -> list[AirseekersDevice]:
        raise self._fail()

    async def async_get_status(self, device_id: str) -> AirseekersStatus:
        raise self._fail()


class LocalHttpBackend(_UnimplementedBackend):
    """Skeleton for a local HTTP/HTTPS API, if one is ever discovered (likely none)."""

    name = BACKEND_LOCAL_HTTP


class CloudHttpBackend(_UnimplementedBackend):
    """Skeleton for the AIRSEEKERS cloud REST API.

    Research indicates control is cloud REST with JWT auth and a single session per account (see
    docs/api_mapping.md). This class will host that client once request/response shapes are verified
    against the owner's own account. It holds an aiohttp session but defines NO endpoints.
    """

    name = BACKEND_CLOUD_HTTP


class MqttBackend(_UnimplementedBackend):
    """Skeleton for MQTT realtime. Research indicates a per-device TLS client cert locks this channel,
    so it is generally not reusable by third parties."""

    name = BACKEND_MQTT


class RtspBackend(_UnimplementedBackend):
    """Skeleton for camera streaming. Research indicates WebRTC-over-MQTT (cloud-relayed), not LAN RTSP."""

    name = BACKEND_RTSP


_BACKENDS: dict[str, type[AirseekersBackend]] = {
    BACKEND_LOCAL_HTTP: LocalHttpBackend,
    BACKEND_CLOUD_HTTP: CloudHttpBackend,
    BACKEND_MQTT: MqttBackend,
    BACKEND_RTSP: RtspBackend,
}


def _build_backend(
    backend: str,
    *,
    session: object | None = None,
    config: Mapping[str, object] | None = None,
) -> AirseekersBackend:
    if backend == BACKEND_STUB:
        return StubBackend(config=config)
    cls = _BACKENDS.get(backend)
    if cls is None:
        raise AirseekersApiError(f"unknown backend: {backend!r}")
    return cls(session=session, config=config)  # type: ignore[call-arg]


def backend_requires_session(backend: str) -> bool:
    """Return whether a backend performs HTTP I/O and needs an aiohttp ``ClientSession``."""
    if backend == BACKEND_STUB:
        return StubBackend.requires_session
    cls = _BACKENDS.get(backend)
    return bool(cls.requires_session) if cls is not None else False


# ---------------------------------------------------------------------------
# Public client
# ---------------------------------------------------------------------------
class AirseekersClient:
    """Backend-agnostic async client used by the whole integration.

    Parameters
    ----------
    backend:
        One of the ``BACKEND_*`` identifiers. ``stub`` is fully functional.
    session:
        Optional aiohttp ``ClientSession`` for HTTP backends (pass ``async_get_clientsession(hass)``).
    config:
        Backend configuration (host, model, device name, ...). Credentials are passed to
        :meth:`async_login`, never logged.
    """

    def __init__(
        self,
        backend: str = BACKEND_STUB,
        *,
        session: object | None = None,
        config: Mapping[str, object] | None = None,
    ) -> None:
        self.backend = backend
        self._impl = _build_backend(backend, session=session, config=config)

    async def async_login(self, username: str, password: str) -> None:
        await self._impl.async_login(username, password)

    async def async_refresh_token(self) -> None:
        await self._impl.async_refresh_token()

    async def async_get_devices(self) -> list[AirseekersDevice]:
        return await self._impl.async_get_devices()

    async def async_get_status(self, device_id: str) -> AirseekersStatus:
        return await self._impl.async_get_status(device_id)

    async def async_start_mowing(self, device_id: str, zone_id: str | None = None) -> None:
        await self._impl.async_start_mowing(device_id, zone_id)

    async def async_pause(self, device_id: str) -> None:
        await self._impl.async_pause(device_id)

    async def async_dock(self, device_id: str) -> None:
        await self._impl.async_dock(device_id)

    async def async_stop(self, device_id: str) -> None:
        await self._impl.async_stop(device_id)

    async def async_set_cutting_height(self, device_id: str, height_mm: int) -> None:
        await self._impl.async_set_cutting_height(device_id, height_mm)

    async def async_set_schedule(self, device_id: str, schedule: object | None = None) -> None:
        await self._impl.async_set_schedule(device_id, schedule)

    async def async_set_mowing_mode(self, device_id: str, mode: str) -> None:
        await self._impl.async_set_mowing_mode(device_id, mode)

    async def async_locate(self, device_id: str) -> None:
        await self._impl.async_locate(device_id)

    async def async_reset_error(self, device_id: str) -> None:
        await self._impl.async_reset_error(device_id)

    async def async_send_command_raw(
        self, device_id: str, command: str, params: dict | None = None
    ) -> object:
        return await self._impl.async_send_command_raw(device_id, command, params)

    async def async_get_zones(self, device_id: str) -> list[AirseekersZone]:
        return await self._impl.async_get_zones(device_id)

    async def async_get_cameras(self, device_id: str) -> list[AirseekersCameraInfo]:
        return await self._impl.async_get_cameras(device_id)

    async def async_get_camera_snapshot(self, device_id: str, camera_id: str) -> bytes:
        return await self._impl.async_get_camera_snapshot(device_id, camera_id)

    async def async_get_camera_stream_url(self, device_id: str, camera_id: str) -> str | None:
        return await self._impl.async_get_camera_stream_url(device_id, camera_id)

    async def async_enable_camera(self, device_id: str, camera_id: str) -> None:
        await self._impl.async_enable_camera(device_id, camera_id)

    async def async_disable_camera(self, device_id: str, camera_id: str) -> None:
        await self._impl.async_disable_camera(device_id, camera_id)

    async def async_close(self) -> None:
        await self._impl.async_close()
