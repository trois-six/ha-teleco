"""Box diagnostics: Wi-Fi signal."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
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
    async_add_entities([TelecoSignal(entry.runtime_data.coordinator)])


class TelecoSignal(TelecoEntity, SensorEntity):
    """Wi-Fi signal quality reported by the box (0-100)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "signal"

    def __init__(self, coordinator: TelecoCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.installation.id_installation}_signal"
        self._attr_device_info = box_device_info(coordinator)

    @property
    def native_value(self) -> int | None:
        signal = self.coordinator.data.signal if self.coordinator.data else None
        return int(signal) if signal and signal.isdigit() else None
