"""Configuration for a Renogy sensor via Serial/Modbus (RS232/RS485)."""

from typing import Literal

from pydantic import BaseModel, Field

from pisolar.config.renogy_defaults import (
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SLAVE_ADDRESS,
)
from pisolar.config.renogy_device_type import DeviceType


class RenogySerialSensorConfig(BaseModel):
    """Configuration for a Renogy sensor via Serial/Modbus (RS232/RS485)."""

    name: str = Field(description="Friendly name for the device")
    read_type: Literal["serial"] = Field(
        default="serial",
        description="Connection type: 'serial' for RS232/RS485 Modbus",
    )
    device_path: str = Field(
        default="/dev/ttyUSB0",
        description="Serial port path (e.g., /dev/ttyUSB0)",
    )
    baud_rate: int = Field(
        default=DEFAULT_BAUD_RATE,
        description="Serial baud rate (typically 9600 for Renogy)",
    )
    slave_address: int = Field(
        default=DEFAULT_SLAVE_ADDRESS,
        description="Modbus slave address (typically 1 for Renogy)",
    )
    device_type: DeviceType = Field(
        default=DeviceType.CONTROLLER,
        description="Device type: 'controller', 'rover', 'wanderer', or 'dcc'",
    )
    max_retries: int = Field(
        default=DEFAULT_MAX_RETRIES,
        description="Number of retry attempts for connection failures",
    )
