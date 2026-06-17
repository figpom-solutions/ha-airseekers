"""Entity behaviour tests (lawn mower, sensors, button, number, select)."""

from __future__ import annotations

from .conftest import async_setup_stub

MOWER = "lawn_mower.tron"


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
    state = hass.states.get("sensor.tron_battery")
    assert state is not None
    assert 0 <= int(float(state.state)) <= 100


async def test_start_button(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.tron_start"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(MOWER).state == "mowing"


async def test_cutting_height_number(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.tron_cutting_height", "value": 55},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert int(float(hass.states.get("number.tron_cutting_height").state)) == 55


async def test_zone_select_options(hass) -> None:
    await async_setup_stub(hass)
    state = hass.states.get("select.tron_zone")
    assert state is not None
    assert "Back lawn" in state.attributes["options"]


async def test_mowing_mode_select(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.tron_mowing_mode", "option": "edge"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("select.tron_mowing_mode").state == "edge"


async def test_device_tracker_and_switches_present(hass) -> None:
    await async_setup_stub(hass)
    assert hass.states.get("device_tracker.tron") is not None
    assert hass.states.get("switch.tron_night_mowing") is not None
    assert hass.states.get("switch.tron_camera_privacy") is not None


async def test_safety_binary_sensors(hass) -> None:
    await async_setup_stub(hass)
    for key in ("lifted", "tilted", "blade_blocked"):
        assert hass.states.get(f"binary_sensor.tron_{key}") is not None
