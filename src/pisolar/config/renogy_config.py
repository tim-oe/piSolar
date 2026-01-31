"""Configuration for Renogy BT-2 module."""

from typing import Literal

from pydantic import BaseModel, Field

from pisolar.config.sensor_schedule import SensorSchedule

# Supported device types from renogy-ble
DeviceType = Literal["controller", "dcc"]

# Default BLE connection settings
DEFAULT_SCAN_TIMEOUT = 15.0
DEFAULT_MAX_RETRIES = 3


class RenogyConfig(BaseModel):
    """Configuration for Renogy BT-2 module."""

    enabled: bool = Field(default=False)
    name: str = Field(default="", description="Friendly name for the device")
    mac_address: str = Field(default="", description="Bluetooth MAC address of BT-2")
    device_alias: str = Field(default="BT-2", description="Device alias")
    device_type: DeviceType = Field(
        default="controller",
        description="Device type: 'controller' for solar charge controllers, "
        "'dcc' for DC-DC chargers",
    )
    scan_timeout: float = Field(
        default=DEFAULT_SCAN_TIMEOUT,
        description="Timeout in seconds for BLE device scanning",
    )
    max_retries: int = Field(
        default=DEFAULT_MAX_RETRIES,
        description="Number of retry attempts for BLE connection failures",
    )
    schedule: SensorSchedule = Field(default_factory=SensorSchedule)
