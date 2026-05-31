"""Configuration for a Renogy sensor via Serial/Modbus (RS232/RS485)."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from pisolar.config.device_type import DeviceType
from pisolar.config.renogy_defaults import (
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SLAVE_ADDRESS,
)


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
    serial_adapter: Literal["usb", "uart"] = Field(
        default="usb",
        description="Serial adapter type: 'usb' (USB-RS485) or 'uart' (GPIO UART-RS485)",
    )
    uart_device_path: str | None = Field(
        default=None,
        description="UART serial path when serial_adapter='uart' (e.g., /dev/serial0)",
    )
    uart_tx_pin: int | None = Field(
        default=None,
        description="Optional BCM GPIO TX pin for UART overlays/documentation",
    )
    uart_rx_pin: int | None = Field(
        default=None,
        description="Optional BCM GPIO RX pin for UART overlays/documentation",
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

    @property
    def resolved_device_path(self) -> str:
        """Return the serial path to use for Modbus communication."""
        if self.serial_adapter == "uart" and self.uart_device_path:
            return self.uart_device_path
        return self.device_path

    @model_validator(mode="after")
    def validate_uart_fields(self) -> "RenogySerialSensorConfig":
        """Validate UART-specific fields when UART transport is selected."""
        if self.serial_adapter == "uart" and not self.uart_device_path:
            raise ValueError(
                "uart_device_path is required when serial_adapter is set to 'uart'"
            )
        return self
