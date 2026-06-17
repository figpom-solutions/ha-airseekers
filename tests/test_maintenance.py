"""Maintenance subsystem tests (warranty, blades, log, anti-spam alerts)."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.airseekers.const import DOMAIN

from .conftest import async_setup_stub

MOWER = "lawn_mower.airseekers_tron_max"


async def test_warranty_expired(hass) -> None:
    await async_setup_stub(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_purchase_date",
        {"entity_id": MOWER, "purchase_date": "2020-01-01"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.airseekers_tron_max_warranty_status").state == "expired"
    assert hass.states.get("binary_sensor.airseekers_tron_max_warranty_expired").state == "on"


async def test_mark_blades_changed_resets_and_logs(hass) -> None:
    entry = await async_setup_stub(hass)
    await hass.services.async_call(
        DOMAIN,
        "mark_blades_changed",
        {"entity_id": MOWER, "comment": "test change"},
        blocking=True,
    )
    await hass.async_block_till_done()

    manager = entry.runtime_data.maintenance
    assert len(manager.log) == 1
    assert manager.log[0]["type"] == "blade_change"
    assert manager.log[0]["comment"] == "test change"
    # Runtime reset to ~0 right after a change.
    assert float(hass.states.get("sensor.airseekers_tron_max_blade_runtime").state) == 0.0


async def test_add_maintenance_event_fires_bus_event(hass) -> None:
    entry = await async_setup_stub(hass)
    events = []

    def _capture(event):
        events.append(event)

    hass.bus.async_listen("airseekers_maintenance_event", _capture)
    await hass.services.async_call(
        DOMAIN,
        "add_maintenance_event",
        {"entity_id": MOWER, "event_type": "cleaning", "comment": "rinsed deck"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert any(e.data["type"] == "cleaning" for e in events)
    assert entry.runtime_data.maintenance.log[-1]["type"] == "cleaning"


async def test_alerts_do_not_spam(hass) -> None:
    with patch(
        "custom_components.airseekers.maintenance.persistent_notification.async_create"
    ) as mock_create:
        entry = await async_setup_stub(hass)
        await hass.services.async_call(
            DOMAIN,
            "set_purchase_date",
            {"entity_id": MOWER, "purchase_date": "2020-01-01"},
            blocking=True,
        )
        await hass.async_block_till_done()
        manager = entry.runtime_data.maintenance
        count_after_first = mock_create.call_count
        assert count_after_first >= 1

        # Re-evaluating must not create duplicate notifications.
        await manager.async_evaluate_alerts()
        await manager.async_evaluate_alerts()
        assert mock_create.call_count == count_after_first


async def test_reset_alerts_rearms(hass) -> None:
    with patch(
        "custom_components.airseekers.maintenance.persistent_notification.async_create"
    ) as mock_create, patch(
        "custom_components.airseekers.maintenance.persistent_notification.async_dismiss"
    ):
        entry = await async_setup_stub(hass)
        await hass.services.async_call(
            DOMAIN, "set_purchase_date", {"entity_id": MOWER, "purchase_date": "2020-01-01"}, blocking=True
        )
        await hass.async_block_till_done()
        manager = entry.runtime_data.maintenance
        before = mock_create.call_count

        await manager.async_reset_alerts()
        await manager.async_evaluate_alerts()
        # After a reset the still-active condition re-fires.
        assert mock_create.call_count > before
