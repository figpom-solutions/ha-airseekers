"""Switch platform for AIRSEEKERS — camera privacy and night-mowing preferences.

These are integration-side preferences stored on the config entry options (consumed by the camera
platform and by user automations respectively). Toggling reloads the entry so the new value applies.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import (
    CAP_CAMERAS,
    CONF_NIGHT_MOWING,
    CONF_PRIVACY_MODE,
    DEFAULT_NIGHT_MOWING,
    DEFAULT_PRIVACY_MODE,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity, build_entity_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up preference switches."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = [
        AirseekersOptionSwitch(
            coordinator,
            entry,
            suffix="night_mowing",
            name="Night mowing",
            option_key=CONF_NIGHT_MOWING,
            default=DEFAULT_NIGHT_MOWING,
            icon="mdi:weather-night",
        )
    ]
    if coordinator.data.device.supports(CAP_CAMERAS):
        entities.append(
            AirseekersOptionSwitch(
                coordinator,
                entry,
                suffix="camera_privacy",
                name="Camera privacy",
                option_key=CONF_PRIVACY_MODE,
                default=DEFAULT_PRIVACY_MODE,
                icon="mdi:eye-off",
            )
        )
    async_add_entities(entities)


class AirseekersOptionSwitch(AirseekersEntity, SwitchEntity):
    """A boolean preference backed by a config-entry option."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        entry: AirseekersConfigEntry,
        *,
        suffix: str,
        name: str,
        option_key: str,
        default: bool,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._default = default
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_id}_{suffix}"
        self.entity_id = build_entity_id("switch", suffix)

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(self._option_key, self._default))

    async def _set(self, value: bool) -> None:
        if value == self.is_on:
            return
        new_options = {**self._entry.options, self._option_key: value}
        # Triggers the options-update listener, which reloads the entry.
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
