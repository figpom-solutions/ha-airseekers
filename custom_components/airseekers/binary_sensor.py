"""Binary sensor platform for AIRSEEKERS.

Capability-gated. Maintenance binary sensors (warranty/blade) are added in Phase 6.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import (
    CAP_BATTERY,
    CAP_CAMERAS,
    CAP_OBSTACLE,
    CAP_RAIN_SENSOR,
    CAP_SAFETY,
    CONF_ENABLE_MAINTENANCE_SENSORS,
    DEFAULT_ENABLE_MAINTENANCE_SENSORS,
)
from .coordinator import AirseekersConfigEntry, AirseekersData, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity, build_entity_id
from .maintenance import build_maintenance_binary_sensors


@dataclass(frozen=True, kw_only=True)
class AirseekersBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value extractor and optional capability gate."""

    value_fn: Callable[[AirseekersData], bool | None]
    capability: str | None = None


BINARY_SENSORS: tuple[AirseekersBinarySensorEntityDescription, ...] = (
    AirseekersBinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.online,
    ),
    AirseekersBinarySensorEntityDescription(
        key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        capability=CAP_BATTERY,
        value_fn=lambda d: d.status.charging,
    ),
    AirseekersBinarySensorEntityDescription(
        key="docked",
        name="Docked",
        value_fn=lambda d: d.status.docked,
    ),
    AirseekersBinarySensorEntityDescription(
        key="rain_detected",
        name="Rain detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
        capability=CAP_RAIN_SENSOR,
        value_fn=lambda d: d.status.raining,
    ),
    AirseekersBinarySensorEntityDescription(
        key="error",
        name="Error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.status.has_error,
    ),
    AirseekersBinarySensorEntityDescription(
        key="obstacle_detected",
        name="Obstacle detected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        capability=CAP_OBSTACLE,
        value_fn=lambda d: d.status.obstacle_detected,
    ),
    AirseekersBinarySensorEntityDescription(
        key="lifted",
        name="Lifted",
        device_class=BinarySensorDeviceClass.SAFETY,
        capability=CAP_SAFETY,
        value_fn=lambda d: d.status.lifted,
    ),
    AirseekersBinarySensorEntityDescription(
        key="tilted",
        name="Tilted",
        device_class=BinarySensorDeviceClass.SAFETY,
        capability=CAP_SAFETY,
        value_fn=lambda d: d.status.tilted,
    ),
    AirseekersBinarySensorEntityDescription(
        key="blade_blocked",
        name="Blade blocked",
        device_class=BinarySensorDeviceClass.PROBLEM,
        capability=CAP_SAFETY,
        value_fn=lambda d: d.status.blade_blocked,
    ),
    AirseekersBinarySensorEntityDescription(
        key="camera_available",
        name="Camera available",
        entity_category=EntityCategory.DIAGNOSTIC,
        capability=CAP_CAMERAS,
        value_fn=lambda d: len(d.cameras) > 0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up binary sensors for the supported capabilities."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.data.device
    entities: list[BinarySensorEntity] = [
        AirseekersBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.capability is None or device.supports(description.capability)
    ]
    maintenance = entry.runtime_data.maintenance
    if maintenance and entry.options.get(
        CONF_ENABLE_MAINTENANCE_SENSORS, DEFAULT_ENABLE_MAINTENANCE_SENSORS
    ):
        entities.extend(build_maintenance_binary_sensors(coordinator, maintenance))
    async_add_entities(entities)


class AirseekersBinarySensor(AirseekersEntity, BinarySensorEntity):
    """A single robot binary sensor."""

    entity_description: AirseekersBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        description: AirseekersBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self.entity_id = build_entity_id("binary_sensor", description.key)

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
