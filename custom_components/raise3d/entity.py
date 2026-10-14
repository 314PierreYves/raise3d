"""Base entity for Raise3D."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, STATE_KLIPPER_UNREACHABLE, STATE_STARTING
from .coordinator import Raise3DCoordinator


class Raise3DEntity(CoordinatorEntity[Raise3DCoordinator]):
    """Entity attached to the printer device."""

    _attr_has_entity_name = True
    # Most values only make sense when r3monitor can read Klipper.
    _requires_klipper = True

    def __init__(self, coordinator: Raise3DCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Pro2 (Klipper)",
            name=entry.title,
            configuration_url=f"{coordinator.client.base_url}/",
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self._requires_klipper:
            return True
        return self.coordinator.data.get("state") not in (
            STATE_KLIPPER_UNREACHABLE,
            STATE_STARTING,
        )
