"""Camera for Raise3D: still frames from r3monitor /snapshot.jpg."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Raise3DError
from .coordinator import Raise3DConfigEntry, Raise3DCoordinator
from .entity import Raise3DEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Raise3DConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Raise3D camera."""
    async_add_entities([Raise3DCamera(entry.runtime_data)])


class Raise3DCamera(Raise3DEntity, Camera):
    """Printer camera (MXCCameraServer, proxied by r3monitor)."""

    _attr_translation_key = "camera"
    # The camera does not depend on Klipper.
    _requires_klipper = False

    def __init__(self, coordinator: Raise3DCoordinator) -> None:
        super().__init__(coordinator, "camera")
        Camera.__init__(self)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return await self.coordinator.client.get_snapshot()
        except Raise3DError as err:
            _LOGGER.debug("Snapshot unavailable: %s", err)
            return None
