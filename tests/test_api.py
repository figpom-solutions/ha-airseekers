"""Phase 2 tests: the async client, the fully functional stub backend, and the pure compute helpers.

These tests do not require a running Home Assistant; they exercise the backend-agnostic API layer.
"""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.airseekers import const
from custom_components.airseekers.api import (
    ACTIVE_STATES,
    AirseekersApiError,
    AirseekersBladeState,
    AirseekersCameraUnavailable,
    AirseekersClient,
    AirseekersUnsupportedFeature,
    AirseekersWarrantyState,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _stub() -> AirseekersClient:
    return AirseekersClient(const.BACKEND_STUB)


async def _device_id(client: AirseekersClient) -> str:
    return (await client.async_get_devices())[0].device_id


async def test_stub_devices_advertise_capabilities() -> None:
    client = _stub()
    devices = await client.async_get_devices()
    assert len(devices) == 1
    dev = devices[0]
    assert dev.model == const.MODEL_TRON_MAX
    assert dev.supports(const.CAP_CAMERAS)
    assert dev.supports(const.CAP_ZONES)


async def test_stub_status_and_command_state_machine() -> None:
    client = _stub()
    dev_id = await _device_id(client)

    status = await client.async_get_status(dev_id)
    assert status.state in (const.STATE_DOCKED, const.STATE_CHARGING)
    assert status.battery_level is not None
    assert status.last_update is not None

    await client.async_start_mowing(dev_id)
    s = await client.async_get_status(dev_id)
    assert s.state == const.STATE_MOWING
    assert s.is_active is True
    assert s.state in ACTIVE_STATES
    assert s.blade_motor_on is True

    await client.async_pause(dev_id)
    assert (await client.async_get_status(dev_id)).state == const.STATE_PAUSED

    await client.async_dock(dev_id)
    assert (await client.async_get_status(dev_id)).state == const.STATE_RETURNING

    await client.async_stop(dev_id)
    assert (await client.async_get_status(dev_id)).state == const.STATE_IDLE


async def test_stub_zone_mowing() -> None:
    client = _stub()
    dev_id = await _device_id(client)
    zones = await client.async_get_zones(dev_id)
    assert len(zones) >= 2

    await client.async_start_mowing(dev_id, zone_id="zone-back")
    assert (await client.async_get_status(dev_id)).current_zone == "zone-back"

    with pytest.raises(AirseekersApiError):
        await client.async_start_mowing(dev_id, zone_id="does-not-exist")


async def test_stub_cutting_height_bounds() -> None:
    client = _stub()
    dev_id = await _device_id(client)
    with pytest.raises(AirseekersApiError):
        await client.async_set_cutting_height(dev_id, 5)
    await client.async_set_cutting_height(dev_id, 50)
    assert (await client.async_get_status(dev_id)).cutting_height_mm == 50


async def test_stub_cameras_dynamic_and_distinct_snapshots() -> None:
    client = _stub()
    dev_id = await _device_id(client)
    cams = await client.async_get_cameras(dev_id)
    assert len(cams) >= 5
    roles = {c.role for c in cams}
    assert const.ROLE_COMPOSITE_360 in roles
    assert any(c.is_composite for c in cams)
    assert all(c.is_privacy_sensitive for c in cams)

    front = await client.async_get_camera_snapshot(dev_id, "cam-front")
    left = await client.async_get_camera_snapshot(dev_id, "cam-left")
    assert front.startswith(PNG_MAGIC)
    assert left.startswith(PNG_MAGIC)
    assert front != left  # distinct image per role

    # Stub is snapshot-only; it never fabricates a stream URL.
    assert await client.async_get_camera_stream_url(dev_id, "cam-front") is None


async def test_stub_camera_disable_enable() -> None:
    client = _stub()
    dev_id = await _device_id(client)

    await client.async_disable_camera(dev_id, "cam-rear")
    cams = {c.camera_id for c in await client.async_get_cameras(dev_id)}
    assert "cam-rear" not in cams
    with pytest.raises(AirseekersCameraUnavailable):
        await client.async_get_camera_snapshot(dev_id, "cam-rear")

    await client.async_enable_camera(dev_id, "cam-rear")
    cams = {c.camera_id for c in await client.async_get_cameras(dev_id)}
    assert "cam-rear" in cams


async def test_unknown_camera_raises() -> None:
    client = _stub()
    dev_id = await _device_id(client)
    with pytest.raises(AirseekersCameraUnavailable):
        await client.async_get_camera_snapshot(dev_id, "cam-nope")


async def test_login_rejects_empty_credentials() -> None:
    client = _stub()
    await client.async_login("user@example.com", "secret")  # accepted, never stored
    from custom_components.airseekers.api import AirseekersAuthError

    with pytest.raises(AirseekersAuthError):
        await client.async_login("", "")


async def test_unsupported_backend_raises() -> None:
    for backend in (
        const.BACKEND_LOCAL_HTTP,
        const.BACKEND_CLOUD_HTTP,
        const.BACKEND_MQTT,
    ):
        client = AirseekersClient(backend)
        with pytest.raises(AirseekersUnsupportedFeature):
            await client.async_get_devices()


async def test_stub_locate_and_reset_error() -> None:
    client = _stub()
    dev_id = await _device_id(client)
    # locate is a no-op on the stub but must not raise.
    await client.async_locate(dev_id)
    # reset_error clears any fault and leaves an error state idle.
    await client.async_reset_error(dev_id)
    status = await client.async_get_status(dev_id)
    assert status.has_error is False


async def test_unknown_device_raises() -> None:
    client = _stub()
    with pytest.raises(AirseekersApiError):
        await client.async_get_status("not-a-real-device")


def test_unknown_backend_name_raises() -> None:
    with pytest.raises(AirseekersApiError):
        AirseekersClient("totally-made-up")


def test_warranty_compute_ok_soon_expired() -> None:
    today = date(2026, 6, 17)

    ok = AirseekersWarrantyState.compute(date(2025, 6, 17), 24, 60, today)
    assert ok.end_date == date(2027, 6, 17)
    assert ok.status == const.WARRANTY_OK
    assert ok.days_remaining == (date(2027, 6, 17) - today).days

    soon = AirseekersWarrantyState.compute(date(2024, 7, 1), 24, 60, today)
    assert soon.end_date == date(2026, 7, 1)
    assert soon.status == const.WARRANTY_EXPIRE_SOON
    assert 0 <= soon.days_remaining <= 60

    expired = AirseekersWarrantyState.compute(date(2023, 1, 1), 24, 60, today)
    assert expired.status == const.WARRANTY_EXPIRED
    assert expired.days_remaining < 0

    none = AirseekersWarrantyState.compute(None)
    assert none.end_date is None
    assert none.status == const.WARRANTY_OK


def test_warranty_compute_clamps_end_of_month() -> None:
    # Jan 31 + 1 month must clamp to Feb 28/29, not overflow.
    w = AirseekersWarrantyState.compute(date(2025, 1, 31), 1, 60, date(2025, 2, 1))
    assert w.end_date == date(2025, 2, 28)


def test_blade_compute_ok_soon_replace() -> None:
    ok = AirseekersBladeState.compute(0, 100, 20)
    assert ok.life_remaining_percent == 100.0
    assert ok.status == const.BLADE_OK

    soon = AirseekersBladeState.compute(85, 100, 20)
    assert soon.status == const.BLADE_SOON
    assert soon.life_remaining_percent == pytest.approx(15.0)

    replace = AirseekersBladeState.compute(100, 100, 20)
    assert replace.status == const.BLADE_REPLACE
    assert replace.life_remaining_percent == 0.0

    over = AirseekersBladeState.compute(150, 100, 20)
    assert over.life_remaining_percent == 0.0
    assert over.status == const.BLADE_REPLACE
