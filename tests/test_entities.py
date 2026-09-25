"""Entity states and the commands they send."""

from __future__ import annotations

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teleco.const import CONF_TRAVEL_TIMES

from .conftest import FakeHub, make_entry


async def call(hass: HomeAssistant, domain: str, service: str, entity: str, **data: object) -> None:
    await hass.services.async_call(domain, service, {ATTR_ENTITY_ID: entity, **data}, blocking=True)


async def test_cover_states(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    screen = hass.states.get("cover.garden_screen")
    assert screen.state == "closed"
    assert screen.attributes["current_position"] == 0  # closed wins over LEVEL 100
    assert screen.attributes["device_class"] == "shutter"
    features = screen.attributes[ATTR_SUPPORTED_FEATURES]
    assert not features & CoverEntityFeature.SET_POSITION  # no travel times
    slats = hass.states.get("cover.garden_slats")
    assert slats.state == "closed"
    assert slats.attributes[ATTR_SUPPORTED_FEATURES] & CoverEntityFeature.SET_POSITION


async def test_cover_commands(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    await call(hass, "cover", "open_cover", "cover.garden_screen")
    await call(hass, "cover", "stop_cover", "cover.garden_screen")
    await call(hass, "cover", "set_cover_position", "cover.garden_slats", position=40)
    await call(hass, "cover", "close_cover", "cover.garden_slats")
    assert hub.sent == [
        ("Screen", "OPEN_STOP_CLOSE", "OPEN"),
        ("Screen", "OPEN_STOP_CLOSE", "STOP"),
        ("Slats", "LEVEL", "LEV2"),  # nearest step (33 %)
        ("Slats", "OPEN_STOP_CLOSE", "CLOSE"),
    ]


async def test_timed_cover_position(hass: HomeAssistant, hub: FakeHub) -> None:
    entry = make_entry(**{CONF_TRAVEL_TIMES: {"2": {"open": 0.4, "close": 0.4}}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("cover.garden_screen")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & CoverEntityFeature.SET_POSITION

    await call(hass, "cover", "set_cover_position", "cover.garden_screen", position=50)
    assert hass.states.get("cover.garden_screen").state == "opening"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [p for name, _, p in hub.sent if name == "Screen"] == ["OPEN", "STOP"]
    state = hass.states.get("cover.garden_screen")
    assert state.attributes["current_position"] == pytest.approx(50, abs=10)
    assert state.state == "open"


async def test_dimmer(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    assert hass.states.get("light.garden_led").state == "off"
    await call(hass, "light", "turn_on", "light.garden_led", brightness=128)  # ~50 % -> step 2
    await call(hass, "light", "turn_on", "light.garden_led")
    await call(hass, "light", "turn_off", "light.garden_led")
    assert hub.sent == [
        ("Led", "POWER", "LEV2"),
        ("Led", "POWER", "ON"),
        ("Led", "POWER", "OFF"),
    ]


async def test_color_light(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    state = hass.states.get("light.garden_color")
    assert state.state == "on"
    assert state.attributes["rgb_color"] == (255, 128, 0)
    assert state.attributes["brightness"] == 204  # 80 %
    await call(hass, "light", "turn_on", "light.garden_color", rgb_color=[0, 0, 255])
    assert hub.sent == [("Color", "COLOR", "A080R000G000B255")]


async def test_preset_light(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    state = hass.states.get("light.garden_preset")
    assert "red" in state.attributes["effect_list"]
    await call(hass, "light", "turn_on", "light.garden_preset", effect="red")
    await call(hass, "light", "turn_on", "light.garden_preset", effect="cycle")
    assert hub.sent == [("Preset", "COLOR", "RED"), ("Preset", "CYCLE", "ON")]


async def test_on_off_light(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    assert hass.states.get("light.garden_lamp").state == "on"
    await call(hass, "light", "turn_off", "light.garden_lamp")
    assert hub.sent == [("Lamp", "POWER", "OFF")]


async def test_fan(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    assert hass.states.get("fan.garden_fan").state == "off"
    await call(hass, "fan", "set_percentage", "fan.garden_fan", percentage=60)
    await call(hass, "fan", "turn_off", "fan.garden_fan")
    assert hub.sent == [("Fan", "SPEED", "67"), ("Fan", "POWER", "OFF")]


async def test_heater(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    state = hass.states.get("select.garden_heater")
    assert state.state == "2"  # LEVEL 50
    await call(hass, "select", "select_option", "select.garden_heater", option="4")
    await call(hass, "select", "select_option", "select.garden_heater", option="off")
    assert hub.sent == [("Heater", "POWER", "LEV4"), ("Heater", "POWER", "OFF")]


async def test_scenario_button(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    await call(hass, "button", "press", "button.home_evening")
    assert hub.scenarios_run == [7001]


async def test_box_sensors(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    assert hass.states.get("binary_sensor.home_cloud_connection").state == "on"
    assert hass.states.get("sensor.home_wi_fi_signal").state == "72"
