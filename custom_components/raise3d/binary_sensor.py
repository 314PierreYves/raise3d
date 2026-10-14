"""Binary sensors for Raise3D (r3monitor /status)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STATE_KLIPPER_UNREACHABLE, STATE_PRINTING
from .coordinator import Raise3DConfigEntry, Raise3DCoordinator
from .entity import Raise3DEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Raise3DConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Raise3D binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities([Raise3DPrintingSensor(coordinator), Raise3DKlipperSensor(coordinator)])

    # Filament sensors (F0, F1...) only appear once r3monitor has read Klipper.
    known: set[str] = set()

    @callback
    def _add_filament_sensors() -> None:
        present = set(coordinator.data.get("filament_sensors") or {}) - known
        if not present:
            return
        known.update(present)
        async_add_entities(Raise3DFilamentSensor(coordinator, name) for name in sorted(present))

    _add_filament_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_filament_sensors))


class Raise3DPrintingSensor(Raise3DEntity, BinarySensorEntity):
    """On while the printer is printing."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "printing"

    def __init__(self, coordinator: Raise3DCoordinator) -> None:
        super().__init__(coordinator, "printing")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("state") == STATE_PRINTING


class Raise3DKlipperSensor(Raise3DEntity, BinarySensorEntity):
    """On while r3monitor can read Klipper."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "klipper"
    _requires_klipper = False

    def __init__(self, coordinator: Raise3DCoordinator) -> None:
        super().__init__(coordinator, "klipper")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("state") != STATE_KLIPPER_UNREACHABLE


class Raise3DFilamentSensor(Raise3DEntity, BinarySensorEntity):
    """On when filament is detected by a Klipper filament_switch_sensor."""

    _attr_translation_key = "filament"

    def __init__(self, coordinator: Raise3DCoordinator, name: str) -> None:
        super().__init__(coordinator, f"filament_{name}")
        self._name = name
        self._attr_translation_placeholders = {"name": name}

    @property
    def _sensor(self) -> dict[str, Any]:
        return (self.coordinator.data.get("filament_sensors") or {}).get(self._name) or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._sensor)

    @property
    def is_on(self) -> bool | None:
        detected = self._sensor.get("detected")
        return None if detected is None else bool(detected)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"enabled": self._sensor.get("enabled")}
