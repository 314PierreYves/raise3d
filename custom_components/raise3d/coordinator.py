"""Data update coordinator for Raise3D."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Raise3DClient, Raise3DError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type Raise3DConfigEntry = ConfigEntry[Raise3DCoordinator]


class Raise3DCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll r3monitor /status at a fixed interval."""

    config_entry: Raise3DConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: Raise3DConfigEntry, client: Raise3DClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.get_status()
        except Raise3DError as err:
            raise UpdateFailed(str(err)) from err
