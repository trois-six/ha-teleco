"""Fans (3 speeds)."""

from __future__ import annotations

from typing import Any

from aioteleco import Fan
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .coordinator import TelecoConfigEntry
from .entity import TelecoDeviceEntity

PARALLEL_UPDATES = 0

SPEEDS = [33, 67, 100]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TelecoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TelecoFan(coordinator, device)
        for device in entry.runtime_data.data.devices.values()
        if isinstance(device, Fan)
    )


class TelecoFan(TelecoDeviceEntity[Fan], FanEntity):
    _attr_speed_count = len(SPEEDS)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )

    @property
    def is_on(self) -> bool | None:
        return self.device.is_on

    @property
    def percentage(self) -> int | None:
        if not self.device.is_on:
            return 0
        speed = self.device.status.get("SPEED")
        if speed is None or not speed.isdigit() or int(speed) not in SPEEDS:
            return None
        return ordered_list_item_to_percentage(SPEEDS, int(speed))

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        if percentage:
            await self.async_set_percentage(percentage)
        else:
            await self._command(self.device.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._command(self.device.turn_off())

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._command(
            self.device.set_speed(percentage_to_ordered_list_item(SPEEDS, percentage))
        )
