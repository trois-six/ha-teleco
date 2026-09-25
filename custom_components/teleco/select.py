"""Heaters: off or one of their 4 power steps."""

from __future__ import annotations

from aioteleco import Heater
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TelecoConfigEntry
from .entity import TelecoDeviceEntity

PARALLEL_UPDATES = 0

OFF = "off"
STEPS = ["1", "2", "3", "4"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TelecoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TelecoHeaterSelect(coordinator, device)
        for device in entry.runtime_data.data.devices.values()
        if isinstance(device, Heater)
    )


class TelecoHeaterSelect(TelecoDeviceEntity[Heater], SelectEntity):
    _attr_translation_key = "heater_power"
    _attr_options = [OFF, *STEPS]

    @property
    def current_option(self) -> str | None:
        if self.device.is_on is False:
            return OFF
        level = self.device.level
        if level is None:
            return None
        return STEPS[min(3, max(0, round(level / 25) - 1))]

    async def async_select_option(self, option: str) -> None:
        if option == OFF:
            await self._command(self.device.turn_off())
        else:
            await self._command(self.device.set_step(int(option)))
