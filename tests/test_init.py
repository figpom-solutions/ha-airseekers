"""Setup / unload tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState

from custom_components.airseekers.const import DOMAIN

from .conftest import async_setup_stub


async def test_setup_creates_entities_and_services(hass) -> None:
    entry = await async_setup_stub(hass)
    assert entry.state is ConfigEntryState.LOADED

    # Primary mower entity + a couple of sensors exist (stable tron_* IDs).
    assert hass.states.get("lawn_mower.tron") is not None
    assert hass.states.get("device_tracker.tron") is not None
    assert hass.states.get("sensor.tron_battery") is not None
    assert hass.states.get("binary_sensor.tron_online") is not None

    # Domain services were registered.
    assert hass.services.has_service(DOMAIN, "refresh")
    assert hass.services.has_service(DOMAIN, "mark_blades_changed")


async def test_unload(hass) -> None:
    entry = await async_setup_stub(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services removed once the last entry is gone.
    assert not hass.services.has_service(DOMAIN, "refresh")
