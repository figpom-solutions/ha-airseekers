"""Home Assistant services for the AIRSEEKERS integration.

Services are registered once at the domain level and resolve their target (entity/device) to the
matching config entry. Control services act on the client; maintenance services act on the
``MaintenanceManager``. The raw debug service is disabled unless the entry opts in.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
import voluptuous as vol

from .api import AirseekersError
from .const import (
    CONF_ENABLE_RAW_COMMAND,
    DEFAULT_ENABLE_RAW_COMMAND,
    DOMAIN,
    MAINTENANCE_EVENT_TYPES,
    SERVICE_ADD_MAINTENANCE_EVENT,
    SERVICE_EXPORT_MAINTENANCE_LOG,
    SERVICE_MARK_BLADES_CHANGED,
    SERVICE_REFRESH,
    SERVICE_RESET_MAINTENANCE_COUNTERS,
    SERVICE_SEND_COMMAND_RAW,
    SERVICE_SET_CUTTING_HEIGHT,
    SERVICE_SET_PURCHASE_DATE,
    SERVICE_SET_WARRANTY_DURATION,
    SERVICE_START_ZONE,
)

_LOGGER = logging.getLogger(__name__)

# Target keys HA injects from a service `target:` selection.
_TARGET_SCHEMA = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("area_id"): vol.All(cv.ensure_list, [cv.string]),
}


def _schema(extra: dict | None = None) -> vol.Schema:
    fields: dict = dict(_TARGET_SCHEMA)
    if extra:
        fields.update(extra)
    return vol.Schema(fields)


@callback
def _entries_from_call(hass: HomeAssistant, call: ServiceCall) -> list[ConfigEntry]:
    """Resolve the config entries a service call targets."""
    entry_ids: set[str] = set()
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    for device_id in call.data.get(ATTR_DEVICE_ID, []) or []:
        device = dev_reg.async_get(device_id)
        if device:
            entry_ids.update(device.config_entries)
    for entity_id in call.data.get(ATTR_ENTITY_ID, []) or []:
        entity = ent_reg.async_get(entity_id)
        if entity and entity.config_entry_id:
            entry_ids.add(entity.config_entry_id)

    resolved: list[ConfigEntry] = []
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN and getattr(entry, "runtime_data", None) is not None:
            resolved.append(entry)

    if not resolved:
        # Fall back to all loaded entries (typical single-robot setup).
        resolved = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
    if not resolved:
        raise ServiceValidationError("No loaded AIRSEEKERS device matched this service call.")
    return resolved


def _maintenance(entry: ConfigEntry):
    manager = entry.runtime_data.maintenance
    if manager is None:
        raise ServiceValidationError("Maintenance subsystem is not enabled for this device.")
    return manager


def async_setup_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    def _wrap(fn):
        """Wrap a handler as a coroutine function HA will await.

        Registering ``lambda c: _coro(c)`` would hand HA a *sync* callable that merely returns an
        un-awaited coroutine; HA never awaits it and the service silently no-ops. Returning a real
        ``async def`` ensures the handler is detected as a coroutine function and awaited.
        """

        async def _handler(call: ServiceCall) -> None:
            try:
                await fn(call)
            except AirseekersError as err:
                raise HomeAssistantError(f"AIRSEEKERS service failed: {err}") from err

        return _handler

    async def handle_refresh(call: ServiceCall) -> None:
        for entry in _entries_from_call(hass, call):
            await entry.runtime_data.coordinator.async_request_refresh()

    async def handle_start_zone(call: ServiceCall) -> None:
        zone_id = call.data["zone_id"]
        for entry in _entries_from_call(hass, call):
            coord = entry.runtime_data.coordinator
            await coord.client.async_start_mowing(coord.device_id, zone_id)
            await coord.async_request_refresh()

    async def handle_set_cutting_height(call: ServiceCall) -> None:
        height = call.data["height_mm"]
        for entry in _entries_from_call(hass, call):
            coord = entry.runtime_data.coordinator
            await coord.client.async_set_cutting_height(coord.device_id, height)
            await coord.async_request_refresh()

    async def handle_send_command_raw(call: ServiceCall) -> None:
        command = call.data["command"]
        params = call.data.get("params") or {}
        ran = False
        for entry in _entries_from_call(hass, call):
            if not entry.options.get(CONF_ENABLE_RAW_COMMAND, DEFAULT_ENABLE_RAW_COMMAND):
                continue
            coord = entry.runtime_data.coordinator
            await coord.client.async_send_command_raw(coord.device_id, command, params)
            ran = True
        if not ran:
            raise ServiceValidationError(
                "Raw command is disabled. Enable 'raw debug command' in the integration options "
                "to use this service."
            )

    async def handle_set_purchase_date(call: ServiceCall) -> None:
        value = call.data["purchase_date"]
        for entry in _entries_from_call(hass, call):
            await _maintenance(entry).async_set_purchase_date(value)

    async def handle_set_warranty_duration(call: ServiceCall) -> None:
        months = call.data["months"]
        for entry in _entries_from_call(hass, call):
            await _maintenance(entry).async_set_warranty_duration(months)

    async def handle_mark_blades_changed(call: ServiceCall) -> None:
        comment = call.data.get("comment")
        for entry in _entries_from_call(hass, call):
            await _maintenance(entry).async_mark_blades_changed(comment)

    async def handle_add_maintenance_event(call: ServiceCall) -> None:
        event_type = call.data["event_type"]
        comment = call.data.get("comment")
        for entry in _entries_from_call(hass, call):
            await _maintenance(entry).async_add_maintenance_event(event_type, comment)

    async def handle_reset_maintenance_counters(call: ServiceCall) -> None:
        for entry in _entries_from_call(hass, call):
            await _maintenance(entry).async_reset_maintenance_counters()

    async def handle_export_maintenance_log(call: ServiceCall) -> ServiceResponse:
        fmt = call.data.get("format", "markdown")
        results: list[dict[str, Any]] = []
        for entry in _entries_from_call(hass, call):
            content = _maintenance(entry).async_export_log(fmt)
            results.append({"entry_id": entry.entry_id, "format": fmt, "content": content})
        return {"results": results}

    # Register --------------------------------------------------------------
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _wrap(handle_refresh), _schema())
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ZONE,
        _wrap(handle_start_zone),
        _schema({vol.Required("zone_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CUTTING_HEIGHT,
        _wrap(handle_set_cutting_height),
        _schema({vol.Required("height_mm"): vol.All(vol.Coerce(int), vol.Range(min=0, max=500))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND_RAW,
        _wrap(handle_send_command_raw),
        _schema(
            {
                vol.Required("command"): cv.string,
                vol.Optional("params"): dict,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PURCHASE_DATE,
        _wrap(handle_set_purchase_date),
        _schema({vol.Required("purchase_date"): cv.date}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_WARRANTY_DURATION,
        _wrap(handle_set_warranty_duration),
        _schema({vol.Required("months"): vol.All(vol.Coerce(int), vol.Range(min=0, max=240))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_BLADES_CHANGED,
        _wrap(handle_mark_blades_changed),
        _schema({vol.Optional("comment"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MAINTENANCE_EVENT,
        _wrap(handle_add_maintenance_event),
        _schema(
            {
                vol.Required("event_type"): vol.In(MAINTENANCE_EVENT_TYPES),
                vol.Optional("comment"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_MAINTENANCE_COUNTERS,
        _wrap(handle_reset_maintenance_counters),
        _schema(),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_MAINTENANCE_LOG,
        handle_export_maintenance_log,
        _schema({vol.Optional("format", default="markdown"): vol.In(["markdown", "json"])}),
        supports_response=SupportsResponse.OPTIONAL,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when the last entry unloads."""
    for service in (
        SERVICE_REFRESH,
        SERVICE_START_ZONE,
        SERVICE_SET_CUTTING_HEIGHT,
        SERVICE_SEND_COMMAND_RAW,
        SERVICE_SET_PURCHASE_DATE,
        SERVICE_SET_WARRANTY_DURATION,
        SERVICE_MARK_BLADES_CHANGED,
        SERVICE_ADD_MAINTENANCE_EVENT,
        SERVICE_RESET_MAINTENANCE_COUNTERS,
        SERVICE_EXPORT_MAINTENANCE_LOG,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
