"""Sensors for Raise3D (r3monitor /status)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import HEATERS, STATE_PRINTING
from .coordinator import Raise3DConfigEntry, Raise3DCoordinator
from .entity import Raise3DEntity

Status = dict[str, Any]


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> float | None:
    """Convert a 0..1 ratio to a percentage."""
    number = _num(value)
    return None if number is None else round(number * 100, 1)


def _estimated_end(status: Status) -> datetime | None:
    eta = _num(status.get("eta_s"))
    if status.get("state") != STATE_PRINTING or eta is None:
        return None
    # Rounded to the minute so the state does not change on every poll.
    end = dt_util.utcnow() + timedelta(seconds=eta)
    return end.replace(second=0, microsecond=0)


def _updated(status: Status) -> datetime | None:
    ts = _num(status.get("updated"))
    return None if not ts else dt_util.utc_from_timestamp(ts)


@dataclass(frozen=True, kw_only=True)
class Raise3DSensorDescription(SensorEntityDescription):
    """Describe a Raise3D sensor."""

    value_fn: Callable[[Status], StateType | datetime]
    attrs_fn: Callable[[Status], dict[str, Any]] | None = None
    requires_klipper: bool = True


SENSORS: tuple[Raise3DSensorDescription, ...] = (
    Raise3DSensorDescription(
        key="state",
        translation_key="state",
        value_fn=lambda s: s.get("state"),
        attrs_fn=lambda s: {
            "error": s.get("error"),
            "homed_axes": s.get("homed_axes"),
            "position": s.get("position"),
        },
        requires_klipper=False,
    ),
    Raise3DSensorDescription(
        key="message",
        translation_key="message",
        value_fn=lambda s: s.get("message"),
    ),
    Raise3DSensorDescription(
        key="filename",
        translation_key="filename",
        value_fn=lambda s: s.get("filename"),
    ),
    Raise3DSensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.get("progress_pct")),
        attrs_fn=lambda s: {"source": s.get("progress_source")},
    ),
    Raise3DSensorDescription(
        key="print_duration",
        translation_key="print_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        value_fn=lambda s: _num(s.get("print_duration_s")),
    ),
    Raise3DSensorDescription(
        key="total_duration",
        translation_key="total_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        value_fn=lambda s: _num(s.get("total_duration_s")),
    ),
    Raise3DSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        value_fn=lambda s: _num(s.get("eta_s")),
    ),
    Raise3DSensorDescription(
        key="estimated_end",
        translation_key="estimated_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_estimated_end,
    ),
    Raise3DSensorDescription(
        key="filament_used",
        translation_key="filament_used",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: _num(s.get("filament_used_mm")),
    ),
    Raise3DSensorDescription(
        key="fan",
        translation_key="fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _pct(s.get("fan")),
    ),
    Raise3DSensorDescription(
        key="idle_state",
        translation_key="idle_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        # Klipper reports "Idle", "Printing", "Ready".
        value_fn=lambda s: (s.get("idle_state") or "").lower() or None,
    ),
    Raise3DSensorDescription(
        key="sysload",
        translation_key="sysload",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda s: _num(s.get("sysload")),
    ),
    Raise3DSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_updated,
        requires_klipper=False,
    ),
)


def _heater(status: Status, heater: str) -> dict[str, Any]:
    return (status.get("heaters") or {}).get(heater) or {}


def _heater_sensors(heater: str) -> tuple[Raise3DSensorDescription, ...]:
    prefix = HEATERS[heater]
    return (
        Raise3DSensorDescription(
            key=f"{heater}_temperature",
            translation_key=f"{prefix}_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda s: _num(_heater(s, heater).get("temp")),
        ),
        Raise3DSensorDescription(
            key=f"{heater}_target",
            translation_key=f"{prefix}_target",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda s: _num(_heater(s, heater).get("target")),
        ),
        Raise3DSensorDescription(
            key=f"{heater}_power",
            translation_key=f"{prefix}_power",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda s: _pct(_heater(s, heater).get("power")),
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Raise3DConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Raise3D sensors."""
    coordinator = entry.runtime_data
    async_add_entities(Raise3DSensor(coordinator, desc) for desc in SENSORS)

    # Heaters only appear once r3monitor has read Klipper: add them as they show up.
    known: set[str] = set()

    @callback
    def _add_heaters() -> None:
        present = (set(coordinator.data.get("heaters") or {}) & HEATERS.keys()) - known
        if not present:
            return
        known.update(present)
        async_add_entities(
            Raise3DSensor(coordinator, desc)
            for heater in sorted(present)
            for desc in _heater_sensors(heater)
        )

    _add_heaters()
    entry.async_on_unload(coordinator.async_add_listener(_add_heaters))


class Raise3DSensor(Raise3DEntity, SensorEntity):
    """A Raise3D sensor."""

    entity_description: Raise3DSensorDescription

    def __init__(
        self, coordinator: Raise3DCoordinator, description: Raise3DSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._requires_klipper = description.requires_klipper

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
