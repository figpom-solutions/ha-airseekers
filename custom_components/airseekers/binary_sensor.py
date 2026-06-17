"""Binary sensor platform for AIRSEEKERS.

Placeholder — added in Phase 4 / Phase 6. Wired now so the integration loads cleanly.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import AirseekersConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """No binary sensor entities yet (Phase 4 / Phase 6)."""
    return
