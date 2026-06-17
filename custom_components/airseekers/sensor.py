"""Sensor platform for AIRSEEKERS.

Placeholder — robot and maintenance sensors are added in Phase 4 / Phase 6. The platform is wired now
so the integration loads cleanly with no orphan entities.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import AirseekersConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """No sensor entities yet (Phase 4 / Phase 6)."""
    return
