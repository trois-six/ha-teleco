"""Config flow, re-authentication and options."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aioteleco import TelecoAuthError, TelecoConnectionError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teleco.const import (
    CONF_CLOSE_TIME,
    CONF_DEVICE,
    CONF_INSTALLATION,
    CONF_LOCAL_HOST,
    CONF_OPEN_TIME,
    CONF_TRANSPORT,
    CONF_TRAVEL_TIMES,
    DOMAIN,
)

from .conftest import EMAIL, ID_INSTALLATION, PASSWORD, FakeHub, installation, make_entry

CREDENTIALS = {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}


async def test_single_installation(hass: HomeAssistant, hub: FakeHub) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {**CREDENTIALS, CONF_INSTALLATION: ID_INSTALLATION}
    assert result["result"].unique_id == str(ID_INSTALLATION)
    hub.close.assert_awaited()


async def test_pick_an_installation(hass: HomeAssistant, hub: FakeHub) -> None:
    hub.installations = [installation(1, "Home"), installation(2, "Holidays")]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "installation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INSTALLATION: "2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Holidays"
    assert result["data"][CONF_INSTALLATION] == 2


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TelecoAuthError("Wrong user name or password"), "invalid_auth"),
        (TelecoConnectionError("down"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_login_errors_then_recover(
    hass: HomeAssistant, hub: FakeHub, error: Exception, reason: str
) -> None:
    hub.connect = AsyncMock(side_effect=error)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    hub.connect = AsyncMock(return_value=hub.installations)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_installation(hass: HomeAssistant, hub: FakeHub) -> None:
    hub.installations = []
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_installations"


async def test_already_configured(hass: HomeAssistant, hub: FakeHub) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, setup: MockConfigEntry, hub: FakeHub) -> None:
    result = await setup.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    hub.connect = AsyncMock(side_effect=TelecoAuthError("Wrong user name or password"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    hub.connect = AsyncMock(return_value=hub.installations)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert setup.data[CONF_PASSWORD] == "new-secret"


async def test_options_settings(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(setup.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: "cloud", CONF_LOCAL_HOST: "192.0.2.9", CONF_SCAN_INTERVAL: 60},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup.options == {
        CONF_TRANSPORT: "cloud",
        CONF_LOCAL_HOST: "192.0.2.9",
        CONF_SCAN_INTERVAL: 60,
    }


async def test_options_travel_times(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    async def travel(device: str, opening: float, closing: float) -> None:
        result = await hass.config_entries.options.async_init(setup.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "travel"}
        )
        assert result["step_id"] == "travel"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_DEVICE: device, CONF_OPEN_TIME: opening, CONF_CLOSE_TIME: closing},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    await travel("2", 33.9, 33.2)
    assert setup.options[CONF_TRAVEL_TIMES] == {"2": {"open": 33.9, "close": 33.2}}
    await travel("2", 0, 0)  # removes them
    assert setup.options[CONF_TRAVEL_TIMES] == {}
