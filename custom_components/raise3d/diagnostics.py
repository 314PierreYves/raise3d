"""Diagnostics for Raise3D: r3monitor summary and raw Klipper objects."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .api import Raise3DError
from .coordinator import Raise3DConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Raise3DConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    try:
        raw: Any = await coordinator.client.get_raw()
    except Raise3DError as err:
        raw = {"error": str(err)}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "status": coordinator.data,
        "raw": raw,
    }
