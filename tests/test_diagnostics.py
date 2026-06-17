"""Diagnostics redaction tests."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airseekers.const import (
    BACKEND_STUB,
    CONF_BACKEND,
    CONF_DEVICE_NAME,
    CONF_MODEL,
    DOMAIN,
    MODEL_TRON_MAX,
)
from custom_components.airseekers.diagnostics import async_get_config_entry_diagnostics
from custom_components.airseekers.redact import REDACTED

from .conftest import _stub_options


async def test_diagnostics_redacts_and_omits_urls(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AIRSEEKERS TRON Max",
        data={
            CONF_BACKEND: BACKEND_STUB,
            CONF_MODEL: MODEL_TRON_MAX,
            CONF_DEVICE_NAME: "AIRSEEKERS TRON Max",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "supersecret",
        },
        options=_stub_options(),
        unique_id="stub-tron-max-001",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # Credentials redacted.
    assert diag["entry"]["data"][CONF_PASSWORD] == REDACTED
    assert diag["entry"]["data"][CONF_USERNAME] == REDACTED

    # Camera items expose flags but never URLs.
    for cam in diag["cameras"]["items"]:
        assert "stream_url" not in cam
        assert "snapshot_url" not in cam
        assert "has_stream_url" in cam

    assert diag["status"]["state"] is not None
    assert diag["cameras"]["count"] == 5
