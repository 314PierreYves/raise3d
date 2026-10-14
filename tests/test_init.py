"""Tests for setup and entities."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.raise3d.const import DOMAIN

from .conftest import BASE, HOST, STATUS_PRINTING, STATUS_UNREACHABLE


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pro2",
        unique_id=f"{HOST}:8090",
        data={CONF_HOST: HOST, CONF_PORT: 8090},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state.state


async def test_entities_while_printing(hass: HomeAssistant, printer) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert _state(hass, "sensor.pro2_status") == "printing"
    assert _state(hass, "sensor.pro2_file") == "support.gcode"
    assert _state(hass, "sensor.pro2_progress") == "37.5"
    assert _state(hass, "sensor.pro2_left_nozzle_temperature") == "214.6"
    assert _state(hass, "sensor.pro2_right_nozzle_target") == "0.0"
    assert _state(hass, "sensor.pro2_bed_temperature") == "59.8"
    assert _state(hass, "sensor.pro2_fan_speed") == "50.0"
    assert _state(hass, "sensor.pro2_activity") == "printing"
    assert float(_state(hass, "sensor.pro2_filament_used")) == 1.2345
    assert round(float(_state(hass, "sensor.pro2_remaining_time")), 6) == round(6000 / 3600, 6)
    assert _state(hass, "sensor.pro2_estimated_end") != "unknown"
    assert _state(hass, "binary_sensor.pro2_printing") == "on"
    assert _state(hass, "binary_sensor.pro2_klipper") == "on"
    assert _state(hass, "binary_sensor.pro2_filament_f0") == "on"
    assert _state(hass, "binary_sensor.pro2_filament_f1") == "off"

    image = await async_get_image(hass, "camera.pro2_camera")
    assert image.content == b"\xff\xd8jpeg\xff\xd9"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_klipper_unreachable_then_back(
    hass: HomeAssistant, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    aioclient_mock.get(f"{BASE}/status", json=STATUS_UNREACHABLE)
    await _setup(hass)

    assert _state(hass, "sensor.pro2_status") == "klipper_unreachable"
    assert _state(hass, "binary_sensor.pro2_klipper") == "off"
    assert _state(hass, "sensor.pro2_progress") == STATE_UNAVAILABLE
    # Heaters and filament sensors are unknown until Klipper is read.
    assert hass.states.get("sensor.pro2_bed_temperature") is None

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/status", json=STATUS_PRINTING)
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _state(hass, "binary_sensor.pro2_klipper") == "on"
    assert _state(hass, "sensor.pro2_progress") == "37.5"
    assert _state(hass, "sensor.pro2_bed_temperature") == "59.8"
    assert _state(hass, "binary_sensor.pro2_filament_f0") == "on"


async def test_r3monitor_down(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/status", exc=TimeoutError)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"{HOST}:8090", data={CONF_HOST: HOST, CONF_PORT: 8090}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
