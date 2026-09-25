"""Config flow: account, installation, re-authentication and options."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from aioteleco import Cover, Slats, TelecoAuthError, TelecoError, TelecoHub
from aioteleco.models import Installation
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CLOSE_TIME,
    CONF_DEVICE,
    CONF_INSTALLATION,
    CONF_LOCAL_HOST,
    CONF_OPEN_TIME,
    CONF_TRANSPORT,
    CONF_TRAVEL_TIMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRANSPORT,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    TRANSPORTS,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)
PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        )
    }
)
SECONDS = NumberSelector(
    NumberSelectorConfig(
        min=0, max=600, step=0.1, unit_of_measurement="s", mode=NumberSelectorMode.BOX
    )
)


async def _async_login(hass: HomeAssistant, email: str, password: str) -> list[Installation]:
    """Check the credentials and list the installations of the account."""
    hub = TelecoHub(
        async_get_clientsession(hass), email, password, transport="cloud", discover_local_ip=False
    )
    try:
        return await hub.connect()
    finally:
        await hub.close()


def _label(installation: Installation) -> str:
    return installation.description or f"Installation {installation.id_installation}"


class TelecoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in with the brand app account, then pick the installation (box)."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._installations: list[Installation] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            try:
                installations = await _async_login(self.hass, email, user_input[CONF_PASSWORD])
            except TelecoAuthError:
                errors["base"] = "invalid_auth"
            except TelecoError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while logging in")
                errors["base"] = "unknown"
            else:
                if not installations:
                    return self.async_abort(reason="no_installations")
                self._credentials = {CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                self._installations = installations
                if len(installations) == 1:
                    return await self._async_create(installations[0])
                return await self.async_step_installation()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            chosen = next(
                i
                for i in self._installations
                if str(i.id_installation) == user_input[CONF_INSTALLATION]
            )
            return await self._async_create(chosen)
        options = [
            SelectOptionDict(value=str(i.id_installation), label=_label(i))
            for i in self._installations
        ]
        return self.async_show_form(
            step_id="installation",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATION): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def _async_create(self, installation: Installation) -> ConfigFlowResult:
        await self.async_set_unique_id(str(installation.id_installation))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_label(installation),
            data={**self._credentials, CONF_INSTALLATION: installation.id_installation},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _async_login(self.hass, entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            except TelecoAuthError:
                errors["base"] = "invalid_auth"
            except TelecoError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while logging in")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=PASSWORD_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TelecoOptionsFlow:
        return TelecoOptionsFlow()


class TelecoOptionsFlow(OptionsFlow):
    """Transport, polling and the travel times of the covers."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["settings", "travel"])

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRANSPORT, default=options.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(TRANSPORTS),
                        translation_key=CONF_TRANSPORT,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_LOCAL_HOST,
                    description={"suggested_value": options.get(CONF_LOCAL_HOST, "")},
                ): TextSelector(),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_travel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Full opening / closing durations of one cover (0 removes them)."""
        entry = self.config_entry
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        covers = [
            device
            for device in entry.runtime_data.data.devices.values()
            if isinstance(device, Cover) and not isinstance(device, Slats)
        ]
        if not covers:
            return self.async_abort(reason="no_covers")
        if user_input is not None:
            travel = dict(entry.options.get(CONF_TRAVEL_TIMES, {}))
            opening, closing = user_input[CONF_OPEN_TIME], user_input[CONF_CLOSE_TIME]
            if opening and closing:
                travel[user_input[CONF_DEVICE]] = {"open": opening, "close": closing}
            else:
                travel.pop(user_input[CONF_DEVICE], None)
            return self.async_create_entry(data={**entry.options, CONF_TRAVEL_TIMES: travel})
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=str(d.id), label=d.name) for d in covers],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_OPEN_TIME, default=0): SECONDS,
                vol.Required(CONF_CLOSE_TIME, default=0): SECONDS,
            }
        )
        return self.async_show_form(step_id="travel", data_schema=schema)
