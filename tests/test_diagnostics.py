"""Diagnostics hide the credentials and the box address."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teleco.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    with patch(
        "custom_components.teleco.diagnostics.collect",
        AsyncMock(return_value={"installations": []}),
    ):
        result = await async_get_config_entry_diagnostics(hass, setup)
    assert result["entry"]["data"]["email"] == "**REDACTED**"
    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["account"] == {"installations": []}
