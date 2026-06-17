"""Number platform for AIRSEEKERS.

Phase 4 provides the cutting-height control. Maintenance threshold numbers (blade lifetime, warranty
warning days, blade warning percent) are added in Phase 6.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import AirseekersError, AirseekersUnsupportedFeature
from .const import (
    CAP_CUTTING_HEIGHT,
    CONF_CUTTING_HEIGHT_MAX,
    CONF_CUTTING_HEIGHT_MIN,
    CONF_ENABLE_MAINTENANCE_SENSORS,
    DEFAULT_CUTTING_HEIGHT_MAX,
    DEFAULT_CUTTING_HEIGHT_MIN,
    DEFAULT_ENABLE_MAINTENANCE_SENSORS,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity
from .maintenance import build_maintenance_numbers


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up the cutting-height number and maintenance threshold numbers."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.data.device
    entities: list[NumberEntity] = []
    if device.supports(CAP_CUTTING_HEIGHT):
        entities.append(AirseekersCuttingHeightNumber(coordinator, entry))
    maintenance = entry.runtime_data.maintenance
    if maintenance and entry.options.get(
        CONF_ENABLE_MAINTENANCE_SENSORS, DEFAULT_ENABLE_MAINTENANCE_SENSORS
    ):
        entities.extend(build_maintenance_numbers(coordinator, maintenance))
    async_add_entities(entities)


class AirseekersCuttingHeightNumber(AirseekersEntity, NumberEntity):
    """Cutting height in millimetres."""

    _attr_name = "Cutting height"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        entry: AirseekersConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_id}_cutting_height"
        device = coordinator.data.device
        # Options override device-reported bounds when present.
        self._attr_native_min_value = float(
            entry.options.get(CONF_CUTTING_HEIGHT_MIN, device.cutting_height_min)
            or DEFAULT_CUTTING_HEIGHT_MIN
        )
        self._attr_native_max_value = float(
            entry.options.get(CONF_CUTTING_HEIGHT_MAX, device.cutting_height_max)
            or DEFAULT_CUTTING_HEIGHT_MAX
        )

    @property
    def native_value(self) -> float | None:
        height = self._status.cutting_height_mm
        return float(height) if height is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.client.async_set_cutting_height(self._device_id, int(value))
        except AirseekersUnsupportedFeature as err:
            raise HomeAssistantError(f"AIRSEEKERS: not supported by this backend: {err}") from err
        except AirseekersError as err:
            raise HomeAssistantError(f"AIRSEEKERS could not set cutting height: {err}") from err
        await self.coordinator.async_request_refresh()
