"""Device tracker platform for AIRSEEKERS — GPS/RTK position."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant

from .const import CAP_POSITION
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity, build_entity_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up the device tracker if the robot reports a position."""
    coordinator = entry.runtime_data.coordinator
    if coordinator.data.device.supports(CAP_POSITION):
        async_add_entities([AirseekersDeviceTracker(coordinator)])


class AirseekersDeviceTracker(AirseekersEntity, TrackerEntity):
    """Reports the robot's GPS/RTK position as device_tracker.tron."""

    _attr_name = None  # use the device name

    def __init__(self, coordinator: AirseekersDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_id}_position"
        self.entity_id = build_entity_id("device_tracker")  # device_tracker.tron

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._status.latitude

    @property
    def longitude(self) -> float | None:
        return self._status.longitude

    @property
    def location_accuracy(self) -> int:
        acc = self._status.gps_accuracy
        return int(round(acc)) if acc is not None else 0
