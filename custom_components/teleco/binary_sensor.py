"""Is the box reachable by the Teleco cloud."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TelecoConfigEntry, TelecoCoordinator
from .entity import TelecoEntity, box_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TelecoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TelecoBoxOnline(entry.runtime_data.coordinator)])


class TelecoBoxOnline(TelecoEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, coordinator: TelecoCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.installation.id_installation}_online"
        self._attr_device_info = box_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.online if self.coordinator.data else None
