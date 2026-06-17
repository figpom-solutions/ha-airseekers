"""Config, options, and reauth flows for the AIRSEEKERS integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AirseekersApiError,
    AirseekersAuthError,
    AirseekersClient,
    AirseekersConnectionError,
    AirseekersError,
    AirseekersUnsupportedFeature,
)
from .const import (
    BACKENDS,
    CAMERA_DISCOVERY_MODES,
    CONF_BACKEND,
    CONF_BLADE_LIFETIME_HOURS,
    CONF_BLADE_WARNING_PERCENT,
    CONF_CAMERA_DISCOVERY_MODE,
    CONF_CUTTING_HEIGHT_MAX,
    CONF_CUTTING_HEIGHT_MIN,
    CONF_DEVICE_NAME,
    CONF_DISABLE_CAMERAS_AT_NIGHT,
    CONF_DISABLE_CAMERAS_WHEN_DOCKED,
    CONF_ENABLE_ALL_CAMERAS,
    CONF_ENABLE_CAMERA_ENTITIES,
    CONF_ENABLE_MAINTENANCE_SENSORS,
    CONF_ENABLE_RAW_COMMAND,
    CONF_HOST,
    CONF_MODEL,
    CONF_POLL_ACTIVE,
    CONF_POLL_IDLE,
    CONF_PREFER_LOCAL,
    CONF_PRIVACY_MODE,
    CONF_WARRANTY_MONTHS,
    CONF_WARRANTY_WARNING_DAYS,
    DEFAULT_BACKEND,
    DEFAULT_BLADE_LIFETIME_HOURS,
    DEFAULT_BLADE_WARNING_PERCENT,
    DEFAULT_CAMERA_DISCOVERY_MODE,
    DEFAULT_CUTTING_HEIGHT_MAX,
    DEFAULT_CUTTING_HEIGHT_MIN,
    DEFAULT_DISABLE_CAMERAS_AT_NIGHT,
    DEFAULT_DISABLE_CAMERAS_WHEN_DOCKED,
    DEFAULT_ENABLE_ALL_CAMERAS,
    DEFAULT_ENABLE_CAMERA_ENTITIES,
    DEFAULT_ENABLE_MAINTENANCE_SENSORS,
    DEFAULT_ENABLE_RAW_COMMAND,
    DEFAULT_MODEL,
    DEFAULT_POLL_ACTIVE,
    DEFAULT_POLL_IDLE,
    DEFAULT_PRIVACY_MODE,
    DEFAULT_WARRANTY_MONTHS,
    DEFAULT_WARRANTY_WARNING_DAYS,
    DOMAIN,
    MODELS,
)

_LOGGER = logging.getLogger(__name__)


async def _async_validate(
    hass: Any,
    backend: str,
    *,
    host: str | None,
    username: str | None,
    password: str | None,
    device_name: str | None,
    model: str | None,
) -> str:
    """Validate a connection and return the device_id. Raises mapped AirseekersError subclasses."""
    session = None if backend == DEFAULT_BACKEND else async_get_clientsession(hass)
    client = AirseekersClient(
        backend,
        session=session,
        config={"host": host, "device_name": device_name, "model": model},
    )
    try:
        if username and password:
            await client.async_login(username, password)
        devices = await client.async_get_devices()
    finally:
        await client.async_close()
    if not devices:
        raise AirseekersApiError("no devices reported")
    return devices[0].device_id


def _errors_for(err: Exception) -> dict[str, str]:
    if isinstance(err, AirseekersAuthError):
        return {"base": "invalid_auth"}
    if isinstance(err, AirseekersUnsupportedFeature):
        return {"base": "backend_not_ready"}
    if isinstance(err, AirseekersConnectionError):
        return {"base": "cannot_connect"}
    if isinstance(err, AirseekersError):
        return {"base": "cannot_connect"}
    _LOGGER.exception("Unexpected error validating AIRSEEKERS config")
    return {"base": "unknown"}


def _default_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        CONF_BACKEND: user_input.get(CONF_BACKEND, DEFAULT_BACKEND),
        CONF_POLL_ACTIVE: DEFAULT_POLL_ACTIVE,
        CONF_POLL_IDLE: DEFAULT_POLL_IDLE,
        CONF_PREFER_LOCAL: user_input.get(CONF_PREFER_LOCAL, False),
        CONF_ENABLE_CAMERA_ENTITIES: user_input.get(
            CONF_ENABLE_CAMERA_ENTITIES, DEFAULT_ENABLE_CAMERA_ENTITIES
        ),
        CONF_ENABLE_ALL_CAMERAS: DEFAULT_ENABLE_ALL_CAMERAS,
        CONF_PRIVACY_MODE: DEFAULT_PRIVACY_MODE,
        CONF_DISABLE_CAMERAS_WHEN_DOCKED: DEFAULT_DISABLE_CAMERAS_WHEN_DOCKED,
        CONF_DISABLE_CAMERAS_AT_NIGHT: DEFAULT_DISABLE_CAMERAS_AT_NIGHT,
        CONF_CAMERA_DISCOVERY_MODE: DEFAULT_CAMERA_DISCOVERY_MODE,
        CONF_ENABLE_MAINTENANCE_SENSORS: user_input.get(
            CONF_ENABLE_MAINTENANCE_SENSORS, DEFAULT_ENABLE_MAINTENANCE_SENSORS
        ),
        CONF_WARRANTY_MONTHS: DEFAULT_WARRANTY_MONTHS,
        CONF_WARRANTY_WARNING_DAYS: DEFAULT_WARRANTY_WARNING_DAYS,
        CONF_BLADE_LIFETIME_HOURS: DEFAULT_BLADE_LIFETIME_HOURS,
        CONF_BLADE_WARNING_PERCENT: DEFAULT_BLADE_WARNING_PERCENT,
        CONF_CUTTING_HEIGHT_MIN: DEFAULT_CUTTING_HEIGHT_MIN,
        CONF_CUTTING_HEIGHT_MAX: DEFAULT_CUTTING_HEIGHT_MAX,
        CONF_ENABLE_RAW_COMMAND: DEFAULT_ENABLE_RAW_COMMAND,
    }


USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BACKEND, default=DEFAULT_BACKEND): vol.In(BACKENDS),
        vol.Required(CONF_MODEL, default=DEFAULT_MODEL): vol.In(MODELS),
        vol.Required(CONF_DEVICE_NAME, default="AIRSEEKERS TRON Max"): str,
        vol.Optional(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PREFER_LOCAL, default=False): bool,
        vol.Optional(
            CONF_ENABLE_CAMERA_ENTITIES, default=DEFAULT_ENABLE_CAMERA_ENTITIES
        ): bool,
        vol.Optional(
            CONF_ENABLE_MAINTENANCE_SENSORS, default=DEFAULT_ENABLE_MAINTENANCE_SENSORS
        ): bool,
    }
)


class AirseekersConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_id = await _async_validate(
                    self.hass,
                    user_input[CONF_BACKEND],
                    host=user_input.get(CONF_HOST),
                    username=user_input.get(CONF_USERNAME),
                    password=user_input.get(CONF_PASSWORD),
                    device_name=user_input.get(CONF_DEVICE_NAME),
                    model=user_input.get(CONF_MODEL),
                )
            except AirseekersError as err:
                errors = _errors_for(err)
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_DEVICE_NAME) or "AIRSEEKERS",
                    data=user_input,
                    options=_default_options(user_input),
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            backend = entry.options.get(CONF_BACKEND) or entry.data.get(
                CONF_BACKEND, DEFAULT_BACKEND
            )
            try:
                await _async_validate(
                    self.hass,
                    backend,
                    host=entry.data.get(CONF_HOST),
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    device_name=entry.data.get(CONF_DEVICE_NAME),
                    model=entry.data.get(CONF_MODEL),
                )
            except AirseekersError as err:
                errors = _errors_for(err)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        # Do NOT pass config_entry (read-only property since HA 2024.11).
        return AirseekersOptionsFlow()


class AirseekersOptionsFlow(OptionsFlow):
    """Handle the options flow. ``self.config_entry`` is provided by Home Assistant."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options

        def _d(key: str, fallback: Any) -> Any:
            return opts.get(key, fallback)

        schema = vol.Schema(
            {
                vol.Optional(CONF_BACKEND, default=_d(CONF_BACKEND, DEFAULT_BACKEND)): vol.In(
                    BACKENDS
                ),
                vol.Optional(
                    CONF_POLL_ACTIVE, default=_d(CONF_POLL_ACTIVE, DEFAULT_POLL_ACTIVE)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_POLL_IDLE, default=_d(CONF_POLL_IDLE, DEFAULT_POLL_IDLE)
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=86400)),
                vol.Optional(CONF_PREFER_LOCAL, default=_d(CONF_PREFER_LOCAL, False)): bool,
                vol.Optional(
                    CONF_ENABLE_CAMERA_ENTITIES,
                    default=_d(CONF_ENABLE_CAMERA_ENTITIES, DEFAULT_ENABLE_CAMERA_ENTITIES),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_ALL_CAMERAS,
                    default=_d(CONF_ENABLE_ALL_CAMERAS, DEFAULT_ENABLE_ALL_CAMERAS),
                ): bool,
                vol.Optional(
                    CONF_PRIVACY_MODE, default=_d(CONF_PRIVACY_MODE, DEFAULT_PRIVACY_MODE)
                ): bool,
                vol.Optional(
                    CONF_DISABLE_CAMERAS_WHEN_DOCKED,
                    default=_d(CONF_DISABLE_CAMERAS_WHEN_DOCKED, DEFAULT_DISABLE_CAMERAS_WHEN_DOCKED),
                ): bool,
                vol.Optional(
                    CONF_DISABLE_CAMERAS_AT_NIGHT,
                    default=_d(CONF_DISABLE_CAMERAS_AT_NIGHT, DEFAULT_DISABLE_CAMERAS_AT_NIGHT),
                ): bool,
                vol.Optional(
                    CONF_CAMERA_DISCOVERY_MODE,
                    default=_d(CONF_CAMERA_DISCOVERY_MODE, DEFAULT_CAMERA_DISCOVERY_MODE),
                ): vol.In(CAMERA_DISCOVERY_MODES),
                vol.Optional(
                    CONF_ENABLE_MAINTENANCE_SENSORS,
                    default=_d(CONF_ENABLE_MAINTENANCE_SENSORS, DEFAULT_ENABLE_MAINTENANCE_SENSORS),
                ): bool,
                vol.Optional(
                    CONF_WARRANTY_MONTHS, default=_d(CONF_WARRANTY_MONTHS, DEFAULT_WARRANTY_MONTHS)
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)),
                vol.Optional(
                    CONF_WARRANTY_WARNING_DAYS,
                    default=_d(CONF_WARRANTY_WARNING_DAYS, DEFAULT_WARRANTY_WARNING_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3650)),
                vol.Optional(
                    CONF_BLADE_LIFETIME_HOURS,
                    default=_d(CONF_BLADE_LIFETIME_HOURS, DEFAULT_BLADE_LIFETIME_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100000)),
                vol.Optional(
                    CONF_BLADE_WARNING_PERCENT,
                    default=_d(CONF_BLADE_WARNING_PERCENT, DEFAULT_BLADE_WARNING_PERCENT),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Optional(
                    CONF_CUTTING_HEIGHT_MIN,
                    default=_d(CONF_CUTTING_HEIGHT_MIN, DEFAULT_CUTTING_HEIGHT_MIN),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=500)),
                vol.Optional(
                    CONF_CUTTING_HEIGHT_MAX,
                    default=_d(CONF_CUTTING_HEIGHT_MAX, DEFAULT_CUTTING_HEIGHT_MAX),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=500)),
                vol.Optional(
                    CONF_ENABLE_RAW_COMMAND,
                    default=_d(CONF_ENABLE_RAW_COMMAND, DEFAULT_ENABLE_RAW_COMMAND),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
