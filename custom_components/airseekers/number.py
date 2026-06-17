"""Number platform for AIRSEEKERS.

Placeholder — cutting height and maintenance thresholds are added in Phase 4 / Phase 6. Wired now so
the integration loads cleanly.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import AirseekersConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """No number entities yet (Phase 4 / Phase 6)."""
    return
