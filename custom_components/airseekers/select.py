"""Select platform for AIRSEEKERS.

Placeholder — zone / mowing-mode / backend / camera-mode selects are added in Phase 4. Wired now so
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
    """No select entities yet (Phase 4)."""
    return
