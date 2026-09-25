"""Lights: on/off, dimmers, RGB and tunable-white lights, RGB with presets."""

from __future__ import annotations

import math
from typing import Any

from aioteleco import ColorLight, Dimmer, Heater, Light, PresetRgbLight
from aioteleco.devices import RGB_PRESETS
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode, LightEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import TelecoConfigEntry
from .entity import TelecoDeviceEntity

PARALLEL_UPDATES = 0

LEVEL_SCALE = (1, 100)
EFFECT_CYCLE = "cycle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TelecoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[LightEntity] = []
    for device in entry.runtime_data.data.devices.values():
        if isinstance(device, Heater):
            continue  # select platform
        if isinstance(device, Dimmer):
            entities.append(TelecoDimmer(coordinator, device))
        elif isinstance(device, ColorLight):
            entities.append(TelecoColorLight(coordinator, device))
        elif isinstance(device, PresetRgbLight):
            entities.append(TelecoPresetLight(coordinator, device))
        elif isinstance(device, Light):
            entities.append(TelecoLight(coordinator, device))
    async_add_entities(entities)


class TelecoLight[LightT: Light](TelecoDeviceEntity[LightT], LightEntity):
    """On/off light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        return self.device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._command(self.device.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._command(self.device.turn_off())


class TelecoDimmer(TelecoLight[Dimmer]):
    """Dimmer: a free level on slider dimmers, 4 steps (25 % each) on the others."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int | None:
        level = self.device.level
        if not level:
            return None
        return value_to_brightness(LEVEL_SCALE, level)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is None:
            await self._command(self.device.turn_on())
            return
        level = max(1, math.ceil(brightness_to_value(LEVEL_SCALE, brightness)))
        await self._command(self.device.set_level(level))


class TelecoColorLight(TelecoLight[ColorLight]):
    """RGB (color wheel) and tunable-white lights, driven by an RGB + brightness value."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        color = self.device.color
        return color[0] if color else None

    @property
    def brightness(self) -> int | None:
        color = self.device.color
        if not color or not color[1]:
            return None
        return value_to_brightness(LEVEL_SCALE, color[1])

    async def async_turn_on(self, **kwargs: Any) -> None:
        rgb = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if rgb is None and brightness is None:
            await self._command(self.device.turn_on())
            return
        current = self.device.color
        if rgb is None:
            rgb = current[0] if current else (255, 255, 255)
        if brightness is None:
            level = current[1] if current and current[1] else 100
        else:
            level = max(1, math.ceil(brightness_to_value(LEVEL_SCALE, brightness)))
        await self._command(self.device.set_color(tuple(rgb), level))


class TelecoPresetLight(TelecoLight[PresetRgbLight]):
    """RGB light with 8 preset colors and a color cycle, exposed as effects."""

    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = [*(preset.lower() for preset in RGB_PRESETS), EFFECT_CYCLE]

    @property
    def effect(self) -> str | None:
        preset = self.device.preset
        return preset.lower() if preset and preset in RGB_PRESETS else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        effect = kwargs.get(ATTR_EFFECT)
        if effect is None:
            await self._command(self.device.turn_on())
        elif effect == EFFECT_CYCLE:
            await self._command(self.device.cycle())
        else:
            await self._command(self.device.set_preset(effect.upper()))
