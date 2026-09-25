"""Diagnostics: the anonymised account dump of the SDK, plus the entry settings."""

from __future__ import annotations

from typing import Any

from aioteleco.diagnostics import collect
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_LOCAL_HOST
from .coordinator import TelecoConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, CONF_LOCAL_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TelecoConfigEntry
) -> dict[str, Any]:
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "account": await collect(entry.runtime_data.hub),
    }
