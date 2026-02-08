"""Configuration for a Renogy sensor via Bluetooth (BT-1/BT-2 module)."""

from typing import Literal

from pydantic import BaseModel, Field

from pisolar.config.renogy_defaults import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_SCAN_TIMEOUT,
)
from pisolar.config.renogy_device_type import DeviceType


class RenogyBluetoothSensorConfig(BaseModel):
    """Configuration for a Renogy sensor via Bluetooth (BT-1/BT-2 module)."""

    name: str = Field(description="Friendly name for the device")
    read_type: Literal["bt"] = Field(
        default="bt",
        description="Connection type: 'bt' for Bluetooth",
    )
    mac_address: str = Field(description="Bluetooth MAC address of BT-1/BT-2 module")
    device_alias: str = Field(default="BT-2", description="Device alias for logging")
    device_type: DeviceType = Field(
        default=DeviceType.CONTROLLER,
        description="Device type: 'controller', 'rover', 'wanderer', or 'dcc'",
    )
    scan_timeout: float = Field(
        default=DEFAULT_SCAN_TIMEOUT,
        description="Timeout in seconds for BLE device scanning",
    )
    max_retries: int = Field(
        default=DEFAULT_MAX_RETRIES,
        description="Number of retry attempts for connection failures",
    )
