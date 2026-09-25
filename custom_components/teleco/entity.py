"""Base entities: one Home Assistant device per Teleco device, under the box."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from aioteleco import Device, TelecoError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TelecoCoordinator


def box_identifier(coordinator: TelecoCoordinator) -> tuple[str, str]:
    return (DOMAIN, f"{coordinator.installation.id_installation}_box")


def box_device_info(coordinator: TelecoCoordinator) -> DeviceInfo:
    installation = coordinator.installation
    return DeviceInfo(
        identifiers={box_identifier(coordinator)},
        name=installation.description or "Teleco box",
        manufacturer=MANUFACTURER,
        model="Box",
        sw_version=installation.firmware_version or None,
        hw_version=installation.hardware_version or None,
    )


class TelecoEntity(CoordinatorEntity[TelecoCoordinator]):
    """Base class for the entities of the installation itself."""

    _attr_has_entity_name = True

    async def _command(self, action: Awaitable[Any]) -> None:
        """Run a command, turn SDK errors into HA errors, then refresh soon."""
        try:
            await action
        except TelecoError as err:
            raise HomeAssistantError(f"{self.entity_id}: {err}") from err
        finally:
            self.coordinator.async_refresh_soon()


class TelecoDeviceEntity[DeviceT: Device](TelecoEntity):
    """Base class for the entities of one Teleco device (named after the device)."""

    _attr_name = None

    def __init__(self, coordinator: TelecoCoordinator, device: DeviceT) -> None:
        super().__init__(coordinator)
        self.device = device
        installation = coordinator.installation
        key = f"{installation.id_installation}_{device.id}"
        self._attr_unique_id = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model_name,
            model_id=str(device.model),
            suggested_area=device.room.description or None,
        )
        if coordinator.box_device_id is not None:
            self._attr_device_info["via_device_id"] = coordinator.box_device_id

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data and self.coordinator.data.online)
