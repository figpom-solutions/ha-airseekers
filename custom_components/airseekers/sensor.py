"""Sensor platform for AIRSEEKERS (robot telemetry).

Capability-gated: a sensor is created only when the device advertises the backing capability.
Maintenance sensors (warranty/blade) are added in Phase 6.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from .const import (
    CAP_BATTERY,
    CAP_BLADE_MOTOR,
    CAP_GPS,
    CAP_RTK,
    CAP_WIFI_RSSI,
    CAP_ZONES,
)
from .coordinator import AirseekersConfigEntry, AirseekersData, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity


@dataclass(frozen=True, kw_only=True)
class AirseekersSensorEntityDescription(SensorEntityDescription):
    """Sensor description with a value extractor and an optional capability gate."""

    value_fn: Callable[[AirseekersData], StateType | datetime]
    capability: str | None = None


SENSORS: tuple[AirseekersSensorEntityDescription, ...] = (
    AirseekersSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        capability=CAP_BATTERY,
        value_fn=lambda d: d.status.battery_level,
    ),
    AirseekersSensorEntityDescription(
        key="state",
        name="State",
        value_fn=lambda d: d.status.state,
    ),
    AirseekersSensorEntityDescription(
        key="activity",
        name="Activity",
        value_fn=lambda d: d.status.state,
    ),
    AirseekersSensorEntityDescription(
        key="current_zone",
        name="Current zone",
        capability=CAP_ZONES,
        value_fn=lambda d: d.status.current_zone,
    ),
    AirseekersSensorEntityDescription(
        key="error_code",
        name="Error code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.fault.code,
    ),
    AirseekersSensorEntityDescription(
        key="error_message",
        name="Error message",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.fault.message,
    ),
    AirseekersSensorEntityDescription(
        key="rtk_status",
        name="RTK status",
        entity_category=EntityCategory.DIAGNOSTIC,
        capability=CAP_RTK,
        value_fn=lambda d: d.status.rtk_status,
    ),
    AirseekersSensorEntityDescription(
        key="gps_signal",
        name="GPS signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        capability=CAP_GPS,
        value_fn=lambda d: d.status.gps_signal,
    ),
    AirseekersSensorEntityDescription(
        key="wifi_rssi",
        name="Wi-Fi RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        capability=CAP_WIFI_RSSI,
        value_fn=lambda d: d.status.wifi_rssi,
    ),
    AirseekersSensorEntityDescription(
        key="blade_motor_state",
        name="Blade motor",
        capability=CAP_BLADE_MOTOR,
        value_fn=lambda d: "on" if d.status.blade_motor_on else "off",
    ),
    AirseekersSensorEntityDescription(
        key="total_mowing_time",
        name="Total mowing time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.status.total_mowing_time_hours,
    ),
    AirseekersSensorEntityDescription(
        key="total_mowing_cycles",
        name="Total mowing cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.status.total_cycles,
    ),
    AirseekersSensorEntityDescription(
        key="last_update",
        name="Last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status.last_update,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up robot sensors for the supported capabilities."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.data.device
    async_add_entities(
        AirseekersSensor(coordinator, description)
        for description in SENSORS
        if description.capability is None or device.supports(description.capability)
    )


class AirseekersSensor(AirseekersEntity, SensorEntity):
    """A single robot telemetry sensor."""

    entity_description: AirseekersSensorEntityDescription

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        description: AirseekersSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)
