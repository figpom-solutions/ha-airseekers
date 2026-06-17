"""The AIRSEEKERS integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AirseekersAuthError,
    AirseekersClient,
    AirseekersConnectionError,
    AirseekersError,
)
from .const import (
    CONF_BACKEND,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_MODEL,
    DEFAULT_BACKEND,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    AirseekersConfigEntry,
    AirseekersDataUpdateCoordinator,
    AirseekersRuntimeData,
)
from .maintenance import MaintenanceManager

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN"]


def _build_client(hass: HomeAssistant, entry: AirseekersConfigEntry) -> AirseekersClient:
    # Backend/host may be overridden via options (the options flow can switch backend).
    backend = entry.options.get(CONF_BACKEND) or entry.data.get(CONF_BACKEND, DEFAULT_BACKEND)
    host = entry.options.get(CONF_HOST) or entry.data.get(CONF_HOST)
    session = None if backend == DEFAULT_BACKEND else async_get_clientsession(hass)
    config = {
        "device_name": entry.data.get(CONF_DEVICE_NAME),
        "model": entry.data.get(CONF_MODEL),
        "host": host,
    }
    return AirseekersClient(backend, session=session, config=config)


async def async_setup_entry(hass: HomeAssistant, entry: AirseekersConfigEntry) -> bool:
    """Set up AIRSEEKERS from a config entry."""
    client = _build_client(hass, entry)

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    if username and password:
        try:
            await client.async_login(username, password)
        except AirseekersAuthError as err:
            await client.async_close()
            raise ConfigEntryAuthFailed(str(err)) from err
        except (AirseekersConnectionError, AirseekersError) as err:
            await client.async_close()
            raise ConfigEntryNotReady(str(err)) from err

    coordinator = AirseekersDataUpdateCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        await client.async_close()
        raise

    maintenance = MaintenanceManager(hass, entry, coordinator)
    await maintenance.async_initialize()
    entry.runtime_data = AirseekersRuntimeData(
        client=client, coordinator=coordinator, maintenance=maintenance
    )

    # Re-evaluate maintenance alerts on every coordinator update (uses live mowing counters).
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(maintenance.async_evaluate_alerts())
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await maintenance.async_evaluate_alerts()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirseekersConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and (runtime := getattr(entry, "runtime_data", None)) is not None:
        await runtime.client.async_close()
    return unloaded


async def _async_reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
