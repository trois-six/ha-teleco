"""Constants of the Teleco Automation integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "teleco"
MANUFACTURER: Final = "Teleco Automation"

CONF_INSTALLATION: Final = "installation"
CONF_TRANSPORT: Final = "transport"
CONF_LOCAL_HOST: Final = "local_host"
CONF_TRAVEL_TIMES: Final = "travel_times"
CONF_OPEN_TIME: Final = "open_time"
CONF_CLOSE_TIME: Final = "close_time"
CONF_DEVICE: Final = "device"

TRANSPORTS: Final = ("auto", "local", "cloud")
DEFAULT_TRANSPORT: Final = "auto"
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
MIN_SCAN_INTERVAL: Final = 10

# After a command, refresh the state this soon (the box updates the cloud quickly).
REFRESH_AFTER_COMMAND: Final = timedelta(seconds=2)
# While a timed cover move is running, update its estimated position this often.
MOVING_UPDATE_INTERVAL: Final = timedelta(seconds=1)
