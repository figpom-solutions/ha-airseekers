"""Base entity for the AIRSEEKERS integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AirseekersStatus
from .const import DOMAIN, MANUFACTURER
from .coordinator import AirseekersData, AirseekersDataUpdateCoordinator


class AirseekersEntity(CoordinatorEntity[AirseekersDataUpdateCoordinator]):
    """Common base: ties an entity to the robot device and the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirseekersDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.data.device
        self._device_id = device.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=MANUFACTURER,
            model=device.model,
            name=device.name,
            sw_version=device.firmware,
        )

    @property
    def _data(self) -> AirseekersData:
        return self.coordinator.data

    @property
    def _status(self) -> AirseekersStatus:
        return self.coordinator.data.status

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.status.online
