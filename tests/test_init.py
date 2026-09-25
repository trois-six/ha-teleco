"""Setup, unload and error handling of a config entry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aioteleco import TelecoAuthError, TelecoConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teleco.const import DOMAIN

from .conftest import FakeHub, make_entry


async def test_setup_and_unload(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    assert setup.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(er.async_get(hass), setup.entry_id)
    platforms = sorted({e.domain for e in entities})
    assert platforms == ["binary_sensor", "button", "cover", "fan", "light", "select", "sensor"]
    assert len(entities) == 11  # 8 devices + scenario + online + signal

    devices = dr.async_get(hass)
    box = devices.async_get_device_by_identifier((DOMAIN, "456_box"), setup.entry_id)
    assert box is not None
    assert box.sw_version == "1.4.0.2"
    screen = devices.async_get_device_by_identifier((DOMAIN, "456_2"), setup.entry_id)
    assert screen is not None
    assert screen.via_device_id == box.id
    assert screen.suggested_area == "Garden"

    assert await hass.config_entries.async_unload(setup.entry_id)
    assert setup.state is ConfigEntryState.NOT_LOADED
    hub.close.assert_awaited()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (TelecoAuthError("Wrong user name or password"), ConfigEntryState.SETUP_ERROR),
        (TelecoConnectionError("down"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant, hub: FakeHub, error: Exception, state: ConfigEntryState
) -> None:
    hub.connect = AsyncMock(side_effect=error)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is state
    if state is ConfigEntryState.SETUP_ERROR:
        flows = hass.config_entries.flow.async_progress()
        assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_offline_box_makes_devices_unavailable(
    hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub
) -> None:
    hub.online = False
    await setup.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("cover.garden_screen").state == "unavailable"
    assert hass.states.get("binary_sensor.home_cloud_connection").state == "off"
