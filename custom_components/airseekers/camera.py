"""Camera platform for AIRSEEKERS.

Placeholder — dynamic multi-camera entities (one per reported camera, role-named, snapshot/live/
composite, privacy-first) are added in Phase 5. Wired now so the integration loads cleanly.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import AirseekersConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """No camera entities yet (Phase 5)."""
    return
