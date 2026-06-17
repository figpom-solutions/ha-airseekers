"""Data update coordinator for the AIRSEEKERS integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AirseekersAuthError,
    AirseekersCameraInfo,
    AirseekersClient,
    AirseekersConnectionError,
    AirseekersDevice,
    AirseekersError,
    AirseekersStatus,
    AirseekersZone,
)
from .const import (
    CONF_POLL_ACTIVE,
    CONF_POLL_IDLE,
    DEFAULT_POLL_ACTIVE,
    DEFAULT_POLL_IDLE,
    DOMAIN,
)

if TYPE_CHECKING:
    from .maintenance import MaintenanceManager

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AirseekersData:
    """Snapshot held by the coordinator and consumed by every entity."""

    device: AirseekersDevice
    status: AirseekersStatus
    zones: list[AirseekersZone]
    cameras: list[AirseekersCameraInfo]


@dataclass(slots=True)
class AirseekersRuntimeData:
    """Stored on ``config_entry.runtime_data``."""

    client: AirseekersClient
    coordinator: AirseekersDataUpdateCoordinator
    maintenance: MaintenanceManager | None = None


# Typed config entry alias (HA 2024.11+ pattern). Plain assignment (not PEP 695 `type`) keeps the
# module importable on Python 3.10 tooling while behaving identically on HA's 3.12+ runtime.
AirseekersConfigEntry = ConfigEntry[AirseekersRuntimeData]


class AirseekersDataUpdateCoordinator(DataUpdateCoordinator[AirseekersData]):
    """Polls the robot via the selected backend with an adaptive interval."""

    config_entry: AirseekersConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirseekersConfigEntry,
        client: AirseekersClient,
    ) -> None:
        self.client = client
        self._device: AirseekersDevice | None = None
        # Read the initial interval from `entry` directly: self.config_entry is only set by
        # super().__init__(), so the _active_interval property is not usable yet here.
        initial_interval = int(entry.options.get(CONF_POLL_ACTIVE, DEFAULT_POLL_ACTIVE))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,  # required (HA 2026.8+)
            update_interval=timedelta(seconds=initial_interval),
        )

    @property
    def _active_interval(self) -> int:
        return int(self.config_entry.options.get(CONF_POLL_ACTIVE, DEFAULT_POLL_ACTIVE))

    @property
    def _idle_interval(self) -> int:
        return int(self.config_entry.options.get(CONF_POLL_IDLE, DEFAULT_POLL_IDLE))

    @property
    def device_id(self) -> str:
        assert self._device is not None  # set in _async_setup before first update
        return self._device.device_id

    async def _async_setup(self) -> None:
        """One-time setup: resolve the device this entry manages."""
        try:
            devices = await self.client.async_get_devices()
        except AirseekersAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (AirseekersConnectionError, AirseekersError) as err:
            raise UpdateFailed(f"Could not list devices: {err}") from err
        if not devices:
            raise UpdateFailed("No AIRSEEKERS device reported by the backend")
        self._device = devices[0]

    async def _async_update_data(self) -> AirseekersData:
        assert self._device is not None
        device_id = self._device.device_id
        try:
            status = await self.client.async_get_status(device_id)
            zones = await self.client.async_get_zones(device_id)
            cameras = await self.client.async_get_cameras(device_id)
        except AirseekersAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (AirseekersConnectionError, AirseekersError) as err:
            raise UpdateFailed(f"Update failed: {err}") from err

        # Adaptive polling: fast while active, slow (cloud-friendly) while docked/idle.
        interval = self._active_interval if status.is_active else self._idle_interval
        self.update_interval = timedelta(seconds=interval)

        return AirseekersData(device=self._device, status=status, zones=zones, cameras=cameras)
