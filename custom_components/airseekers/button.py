"""Button platform for AIRSEEKERS (control actions).

Capability-gated. Maintenance buttons (mark blades changed, reset alert, export log) are added in
Phase 6 once the persistent maintenance store exists.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import AirseekersError, AirseekersUnsupportedFeature
from .const import CAP_LOCATE, CAP_RESET_ERROR, CAP_STOP
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity


@dataclass(frozen=True, kw_only=True)
class AirseekersButtonEntityDescription(ButtonEntityDescription):
    """Button description with a press action and an optional capability gate."""

    press_fn: Callable[[AirseekersDataUpdateCoordinator], Awaitable[None]]
    capability: str | None = None
    refresh_after: bool = True


BUTTONS: tuple[AirseekersButtonEntityDescription, ...] = (
    AirseekersButtonEntityDescription(
        key="refresh",
        name="Refresh",
        entity_category=EntityCategory.CONFIG,
        refresh_after=False,
        press_fn=lambda c: c.async_request_refresh(),
    ),
    AirseekersButtonEntityDescription(
        key="start",
        name="Start mowing",
        press_fn=lambda c: c.client.async_start_mowing(c.device_id),
    ),
    AirseekersButtonEntityDescription(
        key="pause",
        name="Pause",
        press_fn=lambda c: c.client.async_pause(c.device_id),
    ),
    AirseekersButtonEntityDescription(
        key="dock",
        name="Dock",
        press_fn=lambda c: c.client.async_dock(c.device_id),
    ),
    AirseekersButtonEntityDescription(
        key="stop",
        name="Stop",
        capability=CAP_STOP,
        press_fn=lambda c: c.client.async_stop(c.device_id),
    ),
    AirseekersButtonEntityDescription(
        key="locate",
        name="Locate",
        device_class=ButtonDeviceClass.IDENTIFY,
        capability=CAP_LOCATE,
        press_fn=lambda c: c.client.async_locate(c.device_id),
    ),
    AirseekersButtonEntityDescription(
        key="reset_error",
        name="Reset error",
        entity_category=EntityCategory.CONFIG,
        capability=CAP_RESET_ERROR,
        press_fn=lambda c: c.client.async_reset_error(c.device_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up control buttons for the supported capabilities."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.data.device
    async_add_entities(
        AirseekersButton(coordinator, description)
        for description in BUTTONS
        if description.capability is None or device.supports(description.capability)
    )


class AirseekersButton(AirseekersEntity, ButtonEntity):
    """A single control button."""

    entity_description: AirseekersButtonEntityDescription

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        description: AirseekersButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_button_{description.key}"

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator)
        except AirseekersUnsupportedFeature as err:
            raise HomeAssistantError(f"AIRSEEKERS: not supported by this backend: {err}") from err
        except AirseekersError as err:
            raise HomeAssistantError(f"AIRSEEKERS command failed: {err}") from err
        if self.entity_description.refresh_after:
            await self.coordinator.async_request_refresh()
