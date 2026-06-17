"""Persistent maintenance subsystem for AIRSEEKERS.

Owns the durable maintenance state (warranty, blade wear, cumulative counters, a maintenance log, and
alert-armed flags) in a Home Assistant ``Store`` — these are persistent counters, not transient
timers. It also computes warranty/blade state (reusing the pure helpers in ``api.py``) and raises
non-spam persistent-notification alerts that re-arm after reset, threshold change, or a new event.

This module defines the ``MaintenanceManager`` plus the maintenance entities (sensors, binary sensors,
buttons, numbers), exposed via ``build_maintenance_*`` helpers that the platform modules call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
import json
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .api import AirseekersBladeState, AirseekersWarrantyState
from .const import (
    BLADE_REPLACE,
    CONF_BLADE_LIFETIME_HOURS,
    CONF_BLADE_WARNING_PERCENT,
    CONF_WARRANTY_MONTHS,
    CONF_WARRANTY_WARNING_DAYS,
    DEFAULT_BLADE_LIFETIME_HOURS,
    DEFAULT_BLADE_WARNING_PERCENT,
    DEFAULT_WARRANTY_MONTHS,
    DEFAULT_WARRANTY_WARNING_DAYS,
    EVENT_BLADE_CHANGE,
    EVENT_MAINTENANCE_LOG,
    MAINTENANCE_DUE,
    MAINTENANCE_EVENT_TYPES,
    MAINTENANCE_OK,
    NOTIFICATION_ID_PREFIX,
    STORAGE_KEY_MAINTENANCE,
    STORAGE_VERSION,
    WARRANTY_EXPIRE_SOON,
    WARRANTY_EXPIRED,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity

_LOGGER = logging.getLogger(__name__)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class MaintenanceManager:
    """Holds and persists maintenance state for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirseekersConfigEntry,
        coordinator: AirseekersDataUpdateCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_MAINTENANCE}_{entry.entry_id}"
        )
        self._data: dict[str, Any] = {}
        self._listeners: set[Callable[[], None]] = set()

    # -- lifecycle --------------------------------------------------------
    async def async_initialize(self) -> None:
        stored = await self._store.async_load() or {}
        opts = self.entry.options
        self._data = {
            "purchase_date": stored.get("purchase_date"),
            "warranty_months": stored.get(
                "warranty_months", opts.get(CONF_WARRANTY_MONTHS, DEFAULT_WARRANTY_MONTHS)
            ),
            "warranty_warning_days": stored.get(
                "warranty_warning_days",
                opts.get(CONF_WARRANTY_WARNING_DAYS, DEFAULT_WARRANTY_WARNING_DAYS),
            ),
            "last_blade_change": stored.get("last_blade_change"),
            "blade_lifetime_hours": stored.get(
                "blade_lifetime_hours",
                opts.get(CONF_BLADE_LIFETIME_HOURS, DEFAULT_BLADE_LIFETIME_HOURS),
            ),
            "blade_warning_percent": stored.get(
                "blade_warning_percent",
                opts.get(CONF_BLADE_WARNING_PERCENT, DEFAULT_BLADE_WARNING_PERCENT),
            ),
            "blade_baseline_hours": stored.get("blade_baseline_hours", self._current_mowing_hours()),
            "log": stored.get("log", []),
            "notified": stored.get("notified", {}),
        }
        await self._save()

    async def _save(self) -> None:
        await self._store.async_save(self._data)

    @callback
    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(cb)

        def _remove() -> None:
            self._listeners.discard(cb)

        return _remove

    @callback
    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            cb()

    # -- inputs from the device -------------------------------------------
    def _current_mowing_hours(self) -> float:
        data = self.coordinator.data
        if data is None:
            return 0.0
        return float(data.status.total_mowing_time_hours)

    def _current_cycles(self) -> int:
        data = self.coordinator.data
        if data is None:
            return 0
        return int(data.status.total_cycles)

    def _has_active_error(self) -> bool:
        data = self.coordinator.data
        return bool(data and data.status.has_error)

    # -- config getters ---------------------------------------------------
    @property
    def purchase_date(self) -> date | None:
        return _parse_date(self._data.get("purchase_date"))

    @property
    def last_blade_change(self) -> date | None:
        return _parse_date(self._data.get("last_blade_change"))

    @property
    def warranty_months(self) -> int:
        return int(self._data.get("warranty_months", DEFAULT_WARRANTY_MONTHS))

    @property
    def warranty_warning_days(self) -> int:
        return int(self._data.get("warranty_warning_days", DEFAULT_WARRANTY_WARNING_DAYS))

    @property
    def blade_lifetime_hours(self) -> int:
        return int(self._data.get("blade_lifetime_hours", DEFAULT_BLADE_LIFETIME_HOURS))

    @property
    def blade_warning_percent(self) -> int:
        return int(self._data.get("blade_warning_percent", DEFAULT_BLADE_WARNING_PERCENT))

    @property
    def log(self) -> list[dict[str, Any]]:
        return list(self._data.get("log", []))

    # -- computed state ---------------------------------------------------
    def warranty_state(self) -> AirseekersWarrantyState:
        return AirseekersWarrantyState.compute(
            self.purchase_date, self.warranty_months, self.warranty_warning_days
        )

    @property
    def blade_runtime_hours(self) -> float:
        baseline = float(self._data.get("blade_baseline_hours", 0.0))
        return round(max(0.0, self._current_mowing_hours() - baseline), 2)

    def blade_state(self) -> AirseekersBladeState:
        return AirseekersBladeState.compute(
            self.blade_runtime_hours,
            self.blade_lifetime_hours,
            self.blade_warning_percent,
            self.last_blade_change,
        )

    @property
    def maintenance_required(self) -> bool:
        return self.blade_state().status == BLADE_REPLACE or self._has_active_error()

    @property
    def maintenance_status(self) -> str:
        return MAINTENANCE_DUE if self.maintenance_required else MAINTENANCE_OK

    def next_blade_change_estimate(self) -> date | None:
        runtime = self.blade_runtime_hours
        last = self.last_blade_change
        if not last or runtime <= 0:
            return None
        elapsed_days = (date.today() - last).days
        if elapsed_days <= 0:
            return None
        rate = runtime / elapsed_days  # hours per day
        if rate <= 0:
            return None
        remaining = max(0.0, self.blade_lifetime_hours - runtime)
        return date.today() + timedelta(days=round(remaining / rate))

    # -- mutations --------------------------------------------------------
    async def _add_log(self, event_type: str, comment: str | None) -> dict[str, Any]:
        entry = {
            "date": date.today().isoformat(),
            "type": event_type,
            "comment": comment or "",
            "mowing_hours": self._current_mowing_hours(),
            "cycles": self._current_cycles(),
        }
        self._data.setdefault("log", []).append(entry)
        self.hass.bus.async_fire(EVENT_MAINTENANCE_LOG, dict(entry))
        return entry

    async def async_mark_blades_changed(self, comment: str | None = None) -> None:
        self._data["blade_baseline_hours"] = self._current_mowing_hours()
        self._data["last_blade_change"] = date.today().isoformat()
        await self._add_log(EVENT_BLADE_CHANGE, comment or "Blades replaced")
        self._rearm("blades")
        await self._finish()

    async def async_reset_blade_timer(self) -> None:
        self._data["blade_baseline_hours"] = self._current_mowing_hours()
        self._data["last_blade_change"] = date.today().isoformat()
        self._rearm("blades")
        await self._finish()

    async def async_set_purchase_date(self, value: date) -> None:
        self._data["purchase_date"] = value.isoformat()
        self._rearm("warranty_soon")
        self._rearm("warranty_expired")
        await self._finish()

    async def async_set_warranty_duration(self, months: int) -> None:
        self._data["warranty_months"] = int(months)
        self._rearm("warranty_soon")
        self._rearm("warranty_expired")
        await self._finish()

    async def async_add_maintenance_event(self, event_type: str, comment: str | None) -> None:
        if event_type not in MAINTENANCE_EVENT_TYPES:
            raise ValueError(f"unknown maintenance event type: {event_type!r}")
        await self._add_log(event_type, comment)
        await self._finish()

    async def async_set_blade_lifetime_hours(self, hours: int) -> None:
        self._data["blade_lifetime_hours"] = int(hours)
        self._rearm("blades")
        await self._finish()

    async def async_set_warranty_warning_days(self, days: int) -> None:
        self._data["warranty_warning_days"] = int(days)
        self._rearm("warranty_soon")
        await self._finish()

    async def async_set_blade_warning_percent(self, percent: int) -> None:
        self._data["blade_warning_percent"] = int(percent)
        self._rearm("blades")
        await self._finish()

    async def async_reset_maintenance_counters(self) -> None:
        self._data["blade_baseline_hours"] = self._current_mowing_hours()
        self._data["last_blade_change"] = date.today().isoformat()
        for key in ("warranty_soon", "warranty_expired", "blades", "maintenance"):
            self._rearm(key)
        await self._finish()

    async def async_reset_alerts(self) -> None:
        for key in ("warranty_soon", "warranty_expired", "blades", "maintenance"):
            self._rearm(key)
        await self._save()
        self._notify_listeners()

    def async_export_log(self, fmt: str = "markdown") -> str:
        if fmt == "json":
            content = json.dumps(self.log, indent=2)
        else:
            lines = ["| Date | Type | Comment | Hours | Cycles |", "|---|---|---|---|---|"]
            for e in self.log:
                lines.append(
                    f"| {e.get('date')} | {e.get('type')} | {e.get('comment')} | "
                    f"{e.get('mowing_hours')} | {e.get('cycles')} |"
                )
            content = "\n".join(lines) if self.log else "_No maintenance events recorded._"
        persistent_notification.async_create(
            self.hass,
            content,
            title="AIRSEEKERS maintenance log",
            notification_id=f"{NOTIFICATION_ID_PREFIX}{self.entry.entry_id}_log_export",
        )
        return content

    async def async_export_log_to_notification(self, fmt: str = "markdown") -> str:
        """Async wrapper for the export button/service."""
        return self.async_export_log(fmt)

    # -- alerts -----------------------------------------------------------
    @callback
    def _rearm(self, key: str) -> None:
        """Allow an alert to fire again and dismiss any standing notification."""
        notified = self._data.setdefault("notified", {})
        if notified.get(key):
            persistent_notification.async_dismiss(
                self.hass, f"{NOTIFICATION_ID_PREFIX}{self.entry.entry_id}_{key}"
            )
        notified[key] = False

    @callback
    def _alert(self, key: str, active: bool, title: str, message: str) -> bool:
        notified = self._data.setdefault("notified", {})
        nid = f"{NOTIFICATION_ID_PREFIX}{self.entry.entry_id}_{key}"
        if active and not notified.get(key):
            persistent_notification.async_create(
                self.hass, message, title=f"AIRSEEKERS: {title}", notification_id=nid
            )
            notified[key] = True
            return True
        if not active and notified.get(key):
            persistent_notification.async_dismiss(self.hass, nid)
            notified[key] = False
            return True
        return False

    async def async_evaluate_alerts(self) -> None:
        warranty = self.warranty_state()
        blade = self.blade_state()
        changed = False
        changed |= self._alert(
            "warranty_soon",
            warranty.status == WARRANTY_EXPIRE_SOON,
            "Warranty expiring soon",
            f"The AIRSEEKERS warranty expires in {warranty.days_remaining} days "
            f"(on {warranty.end_date}). Check for any issues before it ends.",
        )
        changed |= self._alert(
            "warranty_expired",
            warranty.status == WARRANTY_EXPIRED,
            "Warranty expired",
            f"The AIRSEEKERS warranty expired on {warranty.end_date}.",
        )
        changed |= self._alert(
            "blades",
            blade.status == BLADE_REPLACE,
            "Blades need replacement",
            f"The AIRSEEKERS blades have reached {blade.runtime_hours} h of use. Plan a replacement.",
        )
        changed |= self._alert(
            "maintenance",
            self.maintenance_required,
            "Maintenance required",
            "The AIRSEEKERS robot needs maintenance attention.",
        )
        if changed:
            await self._save()
            self._notify_listeners()

    async def _finish(self) -> None:
        await self._save()
        self._notify_listeners()
        await self.async_evaluate_alerts()


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class _MaintenanceEntity(AirseekersEntity):
    """Maintenance entity: updates on coordinator ticks AND manager changes."""

    def __init__(
        self, coordinator: AirseekersDataUpdateCoordinator, manager: MaintenanceManager
    ) -> None:
        super().__init__(coordinator)
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))


@dataclass(frozen=True, kw_only=True)
class _MSensorDesc(SensorEntityDescription):
    value_fn: Callable[[MaintenanceManager], Any]


MAINTENANCE_SENSORS: tuple[_MSensorDesc, ...] = (
    _MSensorDesc(
        key="warranty_end_date",
        name="Warranty end date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda m: m.warranty_state().end_date,
    ),
    _MSensorDesc(
        key="warranty_days_remaining",
        name="Warranty days remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda m: m.warranty_state().days_remaining,
    ),
    _MSensorDesc(
        key="warranty_status",
        name="Warranty status",
        value_fn=lambda m: m.warranty_state().status,
    ),
    _MSensorDesc(
        key="blade_runtime_hours",
        name="Blade runtime",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: m.blade_runtime_hours,
    ),
    _MSensorDesc(
        key="blade_life_remaining_percent",
        name="Blade life remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: m.blade_state().life_remaining_percent,
    ),
    _MSensorDesc(
        key="blade_status",
        name="Blade status",
        value_fn=lambda m: m.blade_state().status,
    ),
    _MSensorDesc(
        key="last_blade_change",
        name="Last blade change",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda m: m.last_blade_change,
    ),
    _MSensorDesc(
        key="next_blade_change_estimate",
        name="Next blade change estimate",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda m: m.next_blade_change_estimate(),
    ),
    _MSensorDesc(
        key="maintenance_status",
        name="Maintenance status",
        value_fn=lambda m: m.maintenance_status,
    ),
)


class MaintenanceSensor(_MaintenanceEntity, SensorEntity):
    entity_description: _MSensorDesc

    def __init__(self, coordinator, manager, description: _MSensorDesc) -> None:
        super().__init__(coordinator, manager)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.manager)


@dataclass(frozen=True, kw_only=True)
class _MBinaryDesc(BinarySensorEntityDescription):
    value_fn: Callable[[MaintenanceManager], bool]


MAINTENANCE_BINARY_SENSORS: tuple[_MBinaryDesc, ...] = (
    _MBinaryDesc(
        key="warranty_expiring_soon",
        name="Warranty expiring soon",
        value_fn=lambda m: m.warranty_state().status == WARRANTY_EXPIRE_SOON,
    ),
    _MBinaryDesc(
        key="warranty_expired",
        name="Warranty expired",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda m: m.warranty_state().status == WARRANTY_EXPIRED,
    ),
    _MBinaryDesc(
        key="blades_need_replacement",
        name="Blades need replacement",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda m: m.blade_state().status == BLADE_REPLACE,
    ),
    _MBinaryDesc(
        key="maintenance_required",
        name="Maintenance required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda m: m.maintenance_required,
    ),
)


class MaintenanceBinarySensor(_MaintenanceEntity, BinarySensorEntity):
    entity_description: _MBinaryDesc

    def __init__(self, coordinator, manager, description: _MBinaryDesc) -> None:
        super().__init__(coordinator, manager)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.manager)


@dataclass(frozen=True, kw_only=True)
class _MButtonDesc(ButtonEntityDescription):
    press_fn: Callable[[MaintenanceManager], Any]


MAINTENANCE_BUTTONS: tuple[_MButtonDesc, ...] = (
    _MButtonDesc(
        key="reset_blade_timer",
        name="Reset blade timer",
        press_fn=lambda m: m.async_reset_blade_timer(),
    ),
    _MButtonDesc(
        key="mark_blades_changed",
        name="Mark blades changed",
        press_fn=lambda m: m.async_mark_blades_changed(),
    ),
    _MButtonDesc(
        key="reset_maintenance_alert",
        name="Reset maintenance alert",
        press_fn=lambda m: m.async_reset_alerts(),
    ),
    _MButtonDesc(
        key="export_maintenance_log",
        name="Export maintenance log",
        press_fn=lambda m: m.async_export_log_to_notification(),
    ),
)


class MaintenanceButton(_MaintenanceEntity, ButtonEntity):
    entity_description: _MButtonDesc
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, manager, description: _MButtonDesc) -> None:
        super().__init__(coordinator, manager)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_button_{description.key}"

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.manager)


@dataclass(frozen=True, kw_only=True)
class _MNumberDesc:
    key: str
    name: str
    native_min_value: float
    native_max_value: float
    native_step: float
    native_unit_of_measurement: str | None
    get_fn: Callable[[MaintenanceManager], float]
    set_fn: Callable[[MaintenanceManager, float], Any]


MAINTENANCE_NUMBERS: tuple[_MNumberDesc, ...] = (
    _MNumberDesc(
        key="blade_lifetime_hours",
        name="Blade lifetime",
        native_min_value=1,
        native_max_value=100000,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.HOURS,
        get_fn=lambda m: float(m.blade_lifetime_hours),
        set_fn=lambda m, v: m.async_set_blade_lifetime_hours(int(v)),
    ),
    _MNumberDesc(
        key="warranty_warning_days",
        name="Warranty warning days",
        native_min_value=0,
        native_max_value=3650,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
        get_fn=lambda m: float(m.warranty_warning_days),
        set_fn=lambda m, v: m.async_set_warranty_warning_days(int(v)),
    ),
    _MNumberDesc(
        key="blade_warning_percent",
        name="Blade warning percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        get_fn=lambda m: float(m.blade_warning_percent),
        set_fn=lambda m, v: m.async_set_blade_warning_percent(int(v)),
    ),
)


class MaintenanceNumber(_MaintenanceEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, manager, description: _MNumberDesc) -> None:
        super().__init__(coordinator, manager)
        self._desc = description
        self._attr_name = description.name
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> float:
        return self._desc.get_fn(self.manager)

    async def async_set_native_value(self, value: float) -> None:
        await self._desc.set_fn(self.manager, value)


# ---------------------------------------------------------------------------
# Builders used by the platform modules
# ---------------------------------------------------------------------------
def build_maintenance_sensors(coordinator, manager) -> list[SensorEntity]:
    return [MaintenanceSensor(coordinator, manager, d) for d in MAINTENANCE_SENSORS]


def build_maintenance_binary_sensors(coordinator, manager) -> list[BinarySensorEntity]:
    return [MaintenanceBinarySensor(coordinator, manager, d) for d in MAINTENANCE_BINARY_SENSORS]


def build_maintenance_buttons(coordinator, manager) -> list[ButtonEntity]:
    return [MaintenanceButton(coordinator, manager, d) for d in MAINTENANCE_BUTTONS]


def build_maintenance_numbers(coordinator, manager) -> list[NumberEntity]:
    return [MaintenanceNumber(coordinator, manager, d) for d in MAINTENANCE_NUMBERS]
