"""Scenarios, as buttons of the box device."""

from __future__ import annotations

from aioteleco import Scenario
from homeassistant.components.button import ButtonEntity
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
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TelecoScenarioButton(coordinator, scenario)
        for scenario in entry.runtime_data.data.scenarios
    )


class TelecoScenarioButton(TelecoEntity, ButtonEntity):
    """Runs a scenario of the installation."""

    def __init__(self, coordinator: TelecoCoordinator, scenario: Scenario) -> None:
        super().__init__(coordinator)
        self.scenario = scenario
        installation = coordinator.installation
        self._attr_unique_id = (
            f"{installation.id_installation}_scenario_{scenario.id_installation_scenario}"
        )
        self._attr_name = scenario.description
        self._attr_device_info = box_device_info(coordinator)

    async def async_press(self) -> None:
        await self._command(
            self.coordinator.hub.run_scenario(self.coordinator.installation, self.scenario)
        )
