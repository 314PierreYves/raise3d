"""Tests for the Raise3D config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.raise3d.const import CONF_SCAN_INTERVAL, DOMAIN

from .conftest import BASE, HOST

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: 8090, CONF_NAME: "Pro2 Atelier"}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, printer) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pro2 Atelier"
    assert result["result"].unique_id == f"{HOST}:8090"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: 8090}
    await hass.async_block_till_done()

    # Same printer twice is refused.
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_accepts_klipper_unreachable(hass: HomeAssistant, aioclient_mock) -> None:
    """r3monitor answers even while Klipper restarts: setup must still be possible."""
    aioclient_mock.get(f"{BASE}/status", json={"state": "klipper_unreachable", "error": "x"})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/status", exc=TimeoutError)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_not_r3monitor(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/status", json={"hello": "world"})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_r3monitor"}


async def test_options_flow(hass: HomeAssistant, printer) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 30}
