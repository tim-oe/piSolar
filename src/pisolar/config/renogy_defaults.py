"""Shared constants and types for Renogy sensor configuration."""

from typing import Literal

# Supported device types
DeviceType = Literal["controller", "dcc", "rover", "wanderer"]

# Default connection settings
DEFAULT_SCAN_TIMEOUT = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BAUD_RATE = 9600
DEFAULT_SLAVE_ADDRESS = 1
