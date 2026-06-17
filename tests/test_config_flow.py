"""Config, options, and reauth flow tests."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.airseekers.api import AirseekersAuthError
from custom_components.airseekers.const import (
    BACKEND_CLOUD_HTTP,
    BACKEND_STUB,
    CONF_BACKEND,
    CONF_DEVICE_NAME,
    CONF_MODEL,
    CONF_POLL_ACTIVE,
    DOMAIN,
    MODEL_TRON_MAX,
)

from .conftest import async_setup_stub

USER_INPUT = {
    CONF_BACKEND: BACKEND_STUB,
    CONF_MODEL: MODEL_TRON_MAX,
    CONF_DEVICE_NAME: "AIRSEEKERS TRON Max",
}


async def test_user_flow_stub_success(hass) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "stub-tron-max-001"
    assert result["data"][CONF_BACKEND] == BACKEND_STUB


async def test_user_flow_backend_not_ready(hass) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_BACKEND: BACKEND_CLOUD_HTTP}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "backend_not_ready"}


async def test_user_flow_invalid_auth(hass) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.airseekers.config_flow._async_validate",
        side_effect=AirseekersAuthError("bad"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_single_instance(hass) -> None:
    await async_setup_stub(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass) -> None:
    entry = await async_setup_stub(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={**entry.options, CONF_POLL_ACTIVE: 45}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_POLL_ACTIVE] == 45


async def test_reauth_flow(hass) -> None:
    entry = await async_setup_stub(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "user@example.com"
