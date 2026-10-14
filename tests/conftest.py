"""Fixtures for Raise3D tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.1.50"
BASE = f"http://{HOST}:8090"

# Shape of r3monitor /status while printing (see printer/r3monitor.py summarize()).
STATUS_PRINTING = {
    "state": "printing",
    "message": None,
    "filename": "support.gcode",
    "progress_pct": 37.5,
    "progress_source": "virtual_sdcard",
    "print_duration_s": 3600,
    "total_duration_s": 3700,
    "eta_s": 6000,
    "filament_used_mm": 1234.5,
    "heaters": {
        "extruder": {"temp": 214.6, "target": 215.0, "power": 0.42},
        "extruder1": {"temp": 25.1, "target": 0.0, "power": 0.0},
        "heater_bed": {"temp": 59.8, "target": 60.0, "power": 0.3},
    },
    "fan": 0.5,
    "filament_sensors": {
        "F0": {"detected": True, "enabled": True},
        "F1": {"detected": False, "enabled": True},
    },
    "idle_state": "Printing",
    "homed_axes": "xyz",
    "position": [100.0, 120.5, 3.2],
    "sysload": 0.85,
    "updated": 1792000000,
}

STATUS_UNREACHABLE = {
    "state": "klipper_unreachable",
    "error": "[Errno 2] No such file or directory",
    "updated": None,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def printer(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock r3monitor on a printer currently printing."""
    aioclient_mock.get(f"{BASE}/status", json=STATUS_PRINTING)
    aioclient_mock.get(f"{BASE}/raw", json={"print_stats": {"state": "printing"}})
    aioclient_mock.get(f"{BASE}/snapshot.jpg", content=b"\xff\xd8jpeg\xff\xd9")
    return aioclient_mock
