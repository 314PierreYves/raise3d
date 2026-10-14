"""Constants for the Raise3D integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "raise3d"
MANUFACTURER: Final = "Raise3D"

DEFAULT_NAME: Final = "Raise3D Pro2"
DEFAULT_PORT: Final = 8090  # r3monitor HTTP port
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds
MIN_SCAN_INTERVAL: Final = 2
MAX_SCAN_INTERVAL: Final = 300

CONF_SCAN_INTERVAL: Final = "scan_interval"

# print_stats.state from Klipper: standby, printing, paused, complete, cancelled, error.
# r3monitor adds "starting" (no read yet) and "klipper_unreachable".
STATE_PRINTING: Final = "printing"
STATE_KLIPPER_UNREACHABLE: Final = "klipper_unreachable"
STATE_STARTING: Final = "starting"

# Heaters reported by r3monitor, mapped to a translation prefix.
HEATERS: Final = {
    "extruder": "left_nozzle",
    "extruder1": "right_nozzle",
    "heater_bed": "bed",
}
