"""Covers: screens, shutters, awnings, gates, windows and pergola slats."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from aioteleco import Cover, Slats
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import MOVING_UPDATE_INTERVAL
from .coordinator import TelecoConfigEntry, TelecoCoordinator
from .entity import TelecoDeviceEntity

PARALLEL_UPDATES = 0

# idDevicemodel -> device class (pergola slats: see TelecoSlats)
DEVICE_CLASSES: dict[int, CoverDeviceClass] = {
    21: CoverDeviceClass.SHUTTER,
    22: CoverDeviceClass.GATE,
    23: CoverDeviceClass.GARAGE,
    24: CoverDeviceClass.AWNING,
    25: CoverDeviceClass.SHADE,
    31: CoverDeviceClass.BLIND,
    43: CoverDeviceClass.GARAGE,
    47: CoverDeviceClass.WINDOW,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TelecoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[CoverEntity] = []
    for device in entry.runtime_data.data.devices.values():
        if isinstance(device, Slats):
            entities.append(TelecoSlats(coordinator, device))
        elif isinstance(device, Cover):
            entities.append(TelecoCover(coordinator, device))
    async_add_entities(entities)


class TelecoCover(TelecoDeviceEntity[Cover], CoverEntity, RestoreEntity):
    """An open/stop/close device.

    With travel times (integration options) it also takes a position: the move is
    timed, then stopped, and the position is an estimate kept across restarts.
    """

    def __init__(self, coordinator: TelecoCoordinator, device: Cover) -> None:
        super().__init__(coordinator, device)
        self._attr_device_class = DEVICE_CLASSES.get(device.model, CoverDeviceClass.SHUTTER)
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        if device.travel_times is not None:
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features
        self._unsub_moving: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.device.travel_times is None:
            return
        last = await self.async_get_last_state()
        if last is not None and self.device.state not in ("OPEN", "CLOSE"):
            position = last.attributes.get(ATTR_CURRENT_POSITION)
            if isinstance(position, int | float):
                self.device.restore_position(position)

    async def async_will_remove_from_hass(self) -> None:
        self._stop_tracking()
        await super().async_will_remove_from_hass()

    @property
    def current_cover_position(self) -> int | None:
        return self.device.position

    @property
    def is_closed(self) -> bool | None:
        return self.device.is_closed

    @property
    def is_opening(self) -> bool:
        return self.device.direction > 0

    @property
    def is_closing(self) -> bool:
        return self.device.direction < 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.open())
        self._track_moving()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.close())
        self._track_moving()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.stop())
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        # A timed move lasts up to the full travel time: run it in the background so
        # the service call returns at once; open/close/stop cancel it.
        self.coordinator.config_entry.async_create_background_task(
            self.hass, self._travel(kwargs[ATTR_POSITION]), f"{self.entity_id} travel"
        )
        await self._wait_for_move()
        self._track_moving()

    async def _travel(self, position: int) -> None:
        try:
            await self._command(self.device.travel_to(position))
        finally:
            self._stop_tracking()
            self.async_write_ha_state()

    async def _wait_for_move(self) -> None:
        """Let the background move send its first command before reporting."""
        for _ in range(20):
            if self.device.direction:
                return
            await asyncio.sleep(0.05)

    @callback
    def _track_moving(self) -> None:
        """Update the estimated position every second while the cover moves."""
        self.async_write_ha_state()
        if self._unsub_moving is None and self.device.travel_times is not None:
            self._unsub_moving = async_track_time_interval(
                self.hass, self._moving_tick, MOVING_UPDATE_INTERVAL
            )

    @callback
    def _moving_tick(self, _now: datetime) -> None:
        self.async_write_ha_state()
        if not self.device.direction:
            self._stop_tracking()

    @callback
    def _stop_tracking(self) -> None:
        if self._unsub_moving is not None:
            self._unsub_moving()
            self._unsub_moving = None


class TelecoSlats(TelecoDeviceEntity[Slats], CoverEntity):
    """Pergola slats: open/close/stop and the app's steps (0/33/66/100 %)."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int | None:
        return self.device.position

    @property
    def is_closed(self) -> bool | None:
        position = self.device.position
        if position is not None:
            return position == 0
        return self.device.is_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.open())

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.close())

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._command(self.device.stop())

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Snap to the nearest step, like the app."""
        await self._command(self.device.set_position(kwargs[ATTR_POSITION]))
