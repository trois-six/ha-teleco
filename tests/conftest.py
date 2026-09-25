"""Fixtures: a fake TelecoHub built from real SDK device objects."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioteleco import BoxInfo, Channel, InstallationData, SendResult
from aioteleco.devices import Device, device_class
from aioteleco.models import DeviceInfo, Installation, Room, Scenario, StatusItem
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teleco.const import CONF_INSTALLATION, DOMAIN

EMAIL = "user@example.com"
PASSWORD = "secret"
ID_INSTALLATION = 456


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


def installation(id_installation: int = ID_INSTALLATION, name: str = "Home") -> Installation:
    return Installation.from_json(
        {
            "idInstallation": id_installation,
            "idInstallationDevice": 789,
            "instCode": f"CODE{id_installation}",
            "instDescription": name,
            "firmwareVersion": "1.4.0.2",
            "activetimer": "S",
            "workdays": "1.0.0",
        }
    )


def _commands(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "idInstallationDeviceCommand": 100 + i,
            "commandAction": action,
            "commandParam": param,
            "lowlevelCommand": "CH1",
            "idDevicetypeCommandModel": 1,
        }
        for i, (action, param) in enumerate(pairs)
    ]


OSC = (("OPEN_STOP_CLOSE", "OPEN"), ("OPEN_STOP_CLOSE", "STOP"), ("OPEN_STOP_CLOSE", "CLOSE"))
STEPS = tuple(("LEVEL", f"LEV{i}") for i in range(1, 5))
POWER = (("POWER", "ON"), ("POWER", "OFF"))

# (id, model, label, commands, status)
DEVICES: list[tuple[int, int, str, tuple[tuple[str, str], ...], dict[str, str]]] = [
    (1, 27, "Slats", OSC + STEPS[1:], {"OPEN_CLOSE": "CLOSE", "LEVEL": "0"}),
    (2, 21, "Screen", OSC, {"OPEN_CLOSE": "CLOSE", "LEVEL": "100"}),
    (3, 17, "Led", (*POWER, *STEPS, ("LEVEL", "0")), {"POWER": "OFF", "LEVEL": "0"}),
    (4, 32, "Color", (*POWER, ("COLOR", "0")), {"POWER": "ON", "COLOR": "A080R255G128B000"}),
    (5, 26, "Preset", (*POWER, ("COLOR", "RED"), ("CYCLE", "ON")), {"POWER": "OFF"}),
    (6, 16, "Lamp", POWER, {"POWER": "ON"}),
    (7, 19, "Fan", (*POWER, ("SPEED", "33"), ("SPEED", "67"), ("SPEED", "100")), {"POWER": "OFF"}),
    (8, 18, "Heater", (*POWER, *STEPS), {"POWER": "ON", "LEVEL": "50"}),
]


class FakeHub:
    """Stands for TelecoHub: real device objects, commands recorded."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args, self.kwargs = args, kwargs
        self.installations = [installation()]
        self.sent: list[tuple[str, str, str]] = []  # (device name, action, param)
        self.scenarios_run: list[int] = []
        self.data: dict[int, InstallationData] = {}
        self.connect = AsyncMock(side_effect=self._connect)
        self.close = AsyncMock()
        self.online = True
        self.api = MagicMock()
        self.api.device_status = AsyncMock(return_value=[])
        self.api.node_active = AsyncMock(return_value=True)
        self.sender = MagicMock()
        self.sender.local_host = MagicMock(return_value="192.0.2.5")

    async def _connect(self) -> list[Installation]:
        return self.installations

    def installation(self, key: int | str | None = None) -> Installation:
        return next(i for i in self.installations if key in (None, i.id_installation))

    async def load(self, inst: Installation) -> InstallationData:
        room = Room.from_json({"idInstallationRoom": 1, "roomDescription": "Garden"})
        devices: dict[int, Device] = {}
        for id_device, model, label, commands, status in DEVICES:
            info_json = {
                "idInstallationDevice": id_device,
                "idDevicemodel": model,
                "deviceIndex": id_device,
                "label": label,
                "deviceCommandList": _commands(*commands),
            }
            info = DeviceInfo.from_json(info_json)
            device = device_class(info)(self, inst, room, info)  # type: ignore[arg-type]
            device.update_status(
                [
                    StatusItem.from_json({"statusItem": k, "statusValue": v})
                    for k, v in status.items()
                ]
            )
            devices[id_device] = device
        scenario = Scenario.from_json(
            {"idInstallationScenario": 7001, "scenarioDescription": "Evening", "commandList": []}
        )
        data = InstallationData(inst, [room], devices, [scenario])
        self.data[inst.id_installation] = data
        return data

    async def refresh(self, inst: Installation) -> None:
        """Statuses are set by the tests."""

    async def box_info(self, inst: Installation) -> BoxInfo:
        return BoxInfo(
            online=self.online,
            net=None,
            signal="72",
            current_time="12:00",
            firmware_version=inst.firmware_version,
        )

    async def send_command(self, device: Device, action: str, param: str) -> SendResult:
        self.sent.append((device.name, action, param))
        return SendResult(Channel.LOCAL, "ACK")

    async def run_scenario(self, inst: Installation, scenario: Scenario) -> SendResult:
        self.scenarios_run.append(scenario.id_installation_scenario)
        return SendResult(Channel.LOCAL, "ACK")


@pytest.fixture
def hub() -> Generator[FakeHub]:
    fake = FakeHub()
    with (
        patch("custom_components.teleco.TelecoHub", return_value=fake),
        patch("custom_components.teleco.config_flow.TelecoHub", return_value=fake),
    ):
        yield fake


def make_entry(**options: Any) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=str(ID_INSTALLATION),
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, CONF_INSTALLATION: ID_INSTALLATION},
        options=options,
    )


@pytest.fixture
async def setup(hass: HomeAssistant, hub: FakeHub) -> MockConfigEntry:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
