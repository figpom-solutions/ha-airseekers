"""Camera platform tests (dynamic creation, snapshot, composite, privacy)."""

from __future__ import annotations

from homeassistant.components.camera import async_get_image
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.airseekers.const import CONF_ENABLE_ALL_CAMERAS, CONF_PRIVACY_MODE

from .conftest import _stub_options, async_setup_stub

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
FRONT = "camera.tron_front"
COMPOSITE = "camera.tron_panoramic"


async def test_all_cameras_created(hass) -> None:
    await async_setup_stub(hass, options=_stub_options(**{CONF_ENABLE_ALL_CAMERAS: True}))
    cams = [e for e in hass.states.async_entity_ids("camera") if e.startswith("camera.tron_")]
    assert len(cams) == 5
    assert FRONT in cams
    assert COMPOSITE in cams


async def test_snapshot_returns_png(hass) -> None:
    await async_setup_stub(hass, options=_stub_options(**{CONF_ENABLE_ALL_CAMERAS: True}))
    image = await async_get_image(hass, FRONT)
    assert image.content.startswith(PNG_MAGIC)


async def test_composite_flagged(hass) -> None:
    await async_setup_stub(hass, options=_stub_options(**{CONF_ENABLE_ALL_CAMERAS: True}))
    state = hass.states.get(COMPOSITE)
    assert state.attributes["is_composite"] is True
    # Stream/snapshot URLs must never be exposed in attributes.
    assert "stream_url" not in state.attributes
    assert "snapshot_url" not in state.attributes


async def test_privacy_mode_blocks_image(hass) -> None:
    await async_setup_stub(
        hass,
        options=_stub_options(**{CONF_ENABLE_ALL_CAMERAS: True, CONF_PRIVACY_MODE: True}),
    )
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, FRONT)
