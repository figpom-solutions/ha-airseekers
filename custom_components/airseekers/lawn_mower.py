"""Lawn mower platform for the AIRSEEKERS integration."""

from __future__ import annotations

import logging

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import (
    AirseekersError,
    AirseekersUnsupportedFeature,
)
from .const import (
    STATE_CHARGING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_MOWING,
    STATE_PAUSED,
    STATE_RETURNING,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity, build_entity_id

_LOGGER = logging.getLogger(__name__)

# Internal state -> HA LawnMowerActivity. States with no clean mapping (idle/offline/unknown)
# resolve to None, which Home Assistant renders as "unknown".
_ACTIVITY_MAP: dict[str, LawnMowerActivity] = {
    STATE_MOWING: LawnMowerActivity.MOWING,
    STATE_PAUSED: LawnMowerActivity.PAUSED,
    STATE_RETURNING: LawnMowerActivity.RETURNING,
    STATE_DOCKED: LawnMowerActivity.DOCKED,
    STATE_CHARGING: LawnMowerActivity.DOCKED,
    STATE_ERROR: LawnMowerActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up the lawn mower entity."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AirseekersLawnMower(coordinator)])


class AirseekersLawnMower(AirseekersEntity, LawnMowerEntity):
    """The robot mower itself (the device's primary entity)."""

    _attr_name = None  # use the device name
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: AirseekersDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_id}_lawn_mower"
        self.entity_id = build_entity_id("lawn_mower")  # lawn_mower.tron

    @property
    def activity(self) -> LawnMowerActivity | None:
        return _ACTIVITY_MAP.get(self._status.state)

    async def _run(self, coro) -> None:
        try:
            await coro
        except AirseekersUnsupportedFeature as err:
            raise HomeAssistantError(f"AIRSEEKERS: operation not supported by this backend: {err}") from err
        except AirseekersError as err:
            raise HomeAssistantError(f"AIRSEEKERS command failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_start_mowing(self) -> None:
        await self._run(self.coordinator.client.async_start_mowing(self._device_id))

    async def async_pause(self) -> None:
        await self._run(self.coordinator.client.async_pause(self._device_id))

    async def async_dock(self) -> None:
        await self._run(self.coordinator.client.async_dock(self._device_id))
