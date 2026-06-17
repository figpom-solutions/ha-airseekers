"""Entity behaviour tests (lawn mower, sensors, button, number, select)."""

from __future__ import annotations

from .conftest import async_setup_stub

MOWER = "lawn_mower.airseekers_tron_max"


async def test_lawn_mower_commands(hass) -> None:
    await async_setup_stub(hass)
    assert hass.states.get(MOWER).state in ("docked", "charging", "unknown")

    await hass.services.async_call(
        "lawn_mower", "start_mowing", {"entity_id": MOWER}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOWER).state == "mowing"

    await hass.services.async_call("lawn_mower", "pause", {"entity_id": MOWER}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(MOWER).state == "paused"

    await hass.services.async_call("lawn_mower", "dock", {"entity_id": MOWER}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(MOWER).state == "returning"


async def test_battery_sensor(hass) -> None:
    await async_setup_stub(hass)
    state = hass.states.get("sensor.airseekers_tron_max_battery")
    assert state is not None
    assert 0 <= int(float(state.state)) <= 100


async def test_start_button(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.airseekers_tron_max_start"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOWER).state == "mowing"


async def test_cutting_height_number(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.airseekers_tron_max_cutting_height", "value": 55},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert int(float(hass.states.get("number.airseekers_tron_max_cutting_height").state)) == 55


async def test_zone_select_options(hass) -> None:
    await async_setup_stub(hass)
    state = hass.states.get("select.airseekers_tron_max_zone")
    assert state is not None
    assert "Back lawn" in state.attributes["options"]
