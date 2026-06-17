"""Pytest configuration and fixtures for ha-airseekers.

Ensures the repository root is importable so tests can ``import custom_components.airseekers...``,
enables custom integrations, and provides a helper to set up the integration on the stub backend.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components/ in every test (pytest-homeassistant-custom-component)."""
    yield


def _stub_options(**overrides):
    from custom_components.airseekers.config_flow import _default_options
    from custom_components.airseekers.const import BACKEND_STUB, CONF_BACKEND

    opts = _default_options({CONF_BACKEND: BACKEND_STUB})
    opts.update(overrides)
    return opts


async def async_setup_stub(hass, *, options=None):
    """Create and set up a stub-backed config entry, returning the entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.airseekers.const import (
        BACKEND_STUB,
        CONF_BACKEND,
        CONF_DEVICE_NAME,
        CONF_MODEL,
        DOMAIN,
        MODEL_TRON_MAX,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AIRSEEKERS TRON Max",
        data={
            CONF_BACKEND: BACKEND_STUB,
            CONF_MODEL: MODEL_TRON_MAX,
            CONF_DEVICE_NAME: "AIRSEEKERS TRON Max",
        },
        options=options or _stub_options(),
        unique_id="stub-tron-max-001",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def stub_entry(hass):
    """A fully set-up stub config entry."""
    return await async_setup_stub(hass)
