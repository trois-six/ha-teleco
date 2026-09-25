"""Polling of an installation's state, shared by all its entities."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aioteleco import BoxInfo, InstallationData, TelecoAuthError, TelecoError, TelecoHub
from aioteleco.models import Installation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, REFRESH_AFTER_COMMAND

_LOGGER = logging.getLogger(__name__)


@dataclass
class TelecoRuntimeData:
    """What a config entry keeps while it is loaded."""

    hub: TelecoHub
    installation: Installation
    data: InstallationData
    coordinator: TelecoCoordinator


type TelecoConfigEntry = ConfigEntry[TelecoRuntimeData]


class TelecoCoordinator(DataUpdateCoordinator[BoxInfo]):
    """Refreshes every device status and the box information of one installation."""

    config_entry: TelecoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TelecoConfigEntry,
        hub: TelecoHub,
        installation: Installation,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {installation.description}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.hub = hub
        self.installation = installation
        self._unsub_soon: Callable[[], None] | None = None
        self.box_device_id: str | None = None  # device registry id of the box

    async def _async_update_data(self) -> BoxInfo:
        try:
            await self.hub.refresh(self.installation)
            return await self.hub.box_info(self.installation)
        except TelecoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TelecoError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def async_refresh_soon(self) -> None:
        """Refresh shortly after a command, so the new state shows up quickly."""
        if self._unsub_soon is not None:
            self._unsub_soon()
        self._unsub_soon = async_call_later(
            self.hass, REFRESH_AFTER_COMMAND, self._async_refresh_soon
        )

    async def _async_refresh_soon(self, _now: datetime) -> None:
        self._unsub_soon = None
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        if self._unsub_soon is not None:
            self._unsub_soon()
            self._unsub_soon = None
        await super().async_shutdown()
