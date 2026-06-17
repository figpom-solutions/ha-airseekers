"""Select platform for AIRSEEKERS.

Provides:
- Zone select (capability-gated): selecting a zone starts mowing it.
- Backend select: switches the active backend (updates options → reload).
- Camera discovery-mode select (capability-gated): sets how cameras are discovered.

A mowing-mode select is intentionally omitted until a verified backend exposes mowing modes — the
project does not fabricate robot features.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import AirseekersError, AirseekersUnsupportedFeature
from .const import (
    BACKENDS,
    CAMERA_DISCOVERY_MODES,
    CAP_CAMERAS,
    CAP_ZONES,
    CONF_BACKEND,
    CONF_CAMERA_DISCOVERY_MODE,
    DEFAULT_BACKEND,
    DEFAULT_CAMERA_DISCOVERY_MODE,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.data.device
    entities: list[SelectEntity] = [AirseekersBackendSelect(coordinator, entry)]
    if device.supports(CAP_ZONES):
        entities.append(AirseekersZoneSelect(coordinator))
    if device.supports(CAP_CAMERAS):
        entities.append(AirseekersCameraModeSelect(coordinator, entry))
    async_add_entities(entities)


class AirseekersZoneSelect(AirseekersEntity, SelectEntity):
    """Select a mowing zone (selecting it starts mowing that zone)."""

    _attr_name = "Zone"

    def __init__(self, coordinator: AirseekersDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_id}_zone"

    def _zone_by_name(self) -> dict[str, str]:
        return {z.name: z.zone_id for z in self.coordinator.data.zones}

    @property
    def options(self) -> list[str]:
        return [z.name for z in self.coordinator.data.zones]

    @property
    def current_option(self) -> str | None:
        current = self._status.current_zone
        if current is None:
            return None
        return next(
            (z.name for z in self.coordinator.data.zones if z.zone_id == current), None
        )

    async def async_select_option(self, option: str) -> None:
        zone_id = self._zone_by_name().get(option)
        if zone_id is None:
            raise HomeAssistantError(f"AIRSEEKERS: unknown zone {option!r}")
        try:
            await self.coordinator.client.async_start_mowing(self._device_id, zone_id)
        except AirseekersUnsupportedFeature as err:
            raise HomeAssistantError(f"AIRSEEKERS: not supported by this backend: {err}") from err
        except AirseekersError as err:
            raise HomeAssistantError(f"AIRSEEKERS could not start zone: {err}") from err
        await self.coordinator.async_request_refresh()


class AirseekersBackendSelect(AirseekersEntity, SelectEntity):
    """Switch the active backend. Changing this reloads the integration."""

    _attr_name = "Backend"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(BACKENDS)

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        entry: AirseekersConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{self._device_id}_backend_mode"

    @property
    def current_option(self) -> str | None:
        return self._entry.options.get(CONF_BACKEND) or self._entry.data.get(
            CONF_BACKEND, DEFAULT_BACKEND
        )

    async def async_select_option(self, option: str) -> None:
        if option == self.current_option:
            return
        new_options = {**self._entry.options, CONF_BACKEND: option}
        # Triggers the options-update listener, which reloads the entry.
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)


class AirseekersCameraModeSelect(AirseekersEntity, SelectEntity):
    """Select the camera discovery mode (auto / manual / disabled)."""

    _attr_name = "Camera mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(CAMERA_DISCOVERY_MODES)

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        entry: AirseekersConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{self._device_id}_camera_mode"

    @property
    def current_option(self) -> str | None:
        return self._entry.options.get(CONF_CAMERA_DISCOVERY_MODE, DEFAULT_CAMERA_DISCOVERY_MODE)

    async def async_select_option(self, option: str) -> None:
        if option == self.current_option:
            return
        new_options = {**self._entry.options, CONF_CAMERA_DISCOVERY_MODE: option}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
