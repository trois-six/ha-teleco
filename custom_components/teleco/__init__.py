"""The Teleco Automation integration (Daisy and the other Teleco brand apps)."""

from __future__ import annotations

from aioteleco import Cover, TelecoAuthError, TelecoError, TelecoHub, TravelTimes
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_INSTALLATION,
    CONF_LOCAL_HOST,
    CONF_TRANSPORT,
    CONF_TRAVEL_TIMES,
    DEFAULT_TRANSPORT,
)
from .coordinator import TelecoConfigEntry, TelecoCoordinator, TelecoRuntimeData
from .entity import box_device_info

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: TelecoConfigEntry) -> bool:
    """Log in, load the installation and set up its entities."""
    hub = TelecoHub(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        transport=entry.options.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
        local_host=entry.options.get(CONF_LOCAL_HOST) or None,
    )
    try:
        await hub.connect()
        installation = hub.installation(entry.data[CONF_INSTALLATION])
        data = await hub.load(installation)
    except TelecoAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except TelecoError as err:
        raise ConfigEntryNotReady(str(err)) from err

    travel = entry.options.get(CONF_TRAVEL_TIMES, {})
    for device in data.devices.values():
        if isinstance(device, Cover) and (times := travel.get(str(device.id))):
            device.travel_times = TravelTimes(open=times["open"], close=times["close"])

    coordinator = TelecoCoordinator(hass, entry, hub, installation)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = TelecoRuntimeData(hub, installation, data, coordinator)
    # The box is the parent (via_device) of every other device: register it first.
    box = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **box_device_info(coordinator)
    )
    coordinator.box_device_id = box.id
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TelecoConfigEntry) -> bool:
    """Unload the entities and close the cloud session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.hub.close()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: TelecoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
