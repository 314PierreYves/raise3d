"""The Raise3D integration (via r3monitor)."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Raise3DClient
from .const import DEFAULT_PORT
from .coordinator import Raise3DConfigEntry, Raise3DCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: Raise3DConfigEntry) -> bool:
    """Set up Raise3D from a config entry."""
    client = Raise3DClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = Raise3DCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Raise3DConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: Raise3DConfigEntry) -> None:
    """Reload when options change (scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
