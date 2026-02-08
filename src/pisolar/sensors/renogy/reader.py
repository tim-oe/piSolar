"""Abstract base class for Renogy device readers."""

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Union

from pisolar.logging_config import get_logger

if TYPE_CHECKING:
    from pisolar.config.renogy_bluetooth_sensor_config import (
        RenogyBluetoothSensorConfig,
    )
    from pisolar.config.renogy_serial_sensor_config import RenogySerialSensorConfig


class RenogyReader(ABC):
    """Abstract base class for reading data from Renogy devices.

    Implementations handle specific connection types (Bluetooth, Serial/Modbus).
    Provides common functionality like logging and retry logic.
    """

    # Class-level logger shared by all subclasses
    _logger = get_logger("sensors.renogy")

    def __init__(self, max_retries: int, retry_delay: float = 1.0) -> None:
        """Initialize the base reader.

        Args:
            max_retries: Number of retry attempts for connection failures
            retry_delay: Delay in seconds between retry attempts
        """
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    @staticmethod
    def create_reader(
        config: Union["RenogyBluetoothSensorConfig", "RenogySerialSensorConfig"]
    ) -> "RenogyReader":
        """Factory method to create appropriate reader based on configuration.

        Args:
            config: Either RenogyBluetoothSensorConfig or RenogySerialSensorConfig

        Returns:
            Appropriate RenogyReader subclass instance

        Raises:
            ValueError: If config type is not recognized
        """
        # Import here to avoid circular imports
        from pisolar.config.renogy_bluetooth_sensor_config import (
            RenogyBluetoothSensorConfig,
        )
        from pisolar.config.renogy_serial_sensor_config import RenogySerialSensorConfig
        from pisolar.sensors.renogy.bluetooth_reader import BluetoothReader
        from pisolar.sensors.renogy.modbus_reader import ModbusReader

        if isinstance(config, RenogyBluetoothSensorConfig):
            return BluetoothReader(
                mac_address=config.mac_address,
                device_alias=config.device_alias,
                device_type=config.device_type,
                scan_timeout=config.scan_timeout,
                max_retries=config.max_retries,
            )
        elif isinstance(config, RenogySerialSensorConfig):
            return ModbusReader(
                device_path=config.device_path,
                device_name=config.name,
                device_type=config.device_type,
                baud_rate=config.baud_rate,
                slave_address=config.slave_address,
                max_retries=config.max_retries,
            )
        else:
            raise ValueError(f"Unknown config type: {type(config)}")

    async def read(self) -> dict[str, Any]:
        """Read data from the Renogy device with automatic retry logic.

        Returns:
            Dictionary containing the raw data from the device.
            Keys should match SolarReading field names where possible.

        Raises:
            RuntimeError: If the read fails after retries.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._read_implementation()
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    self._logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                        attempt,
                        self._max_retries,
                        self.device_name,
                        str(e),
                        self._retry_delay,
                    )
                    await asyncio.sleep(self._retry_delay)
                else:
                    self._logger.error(
                        "All %d attempts failed for %s",
                        self._max_retries,
                        self.device_name,
                    )

        raise RuntimeError(
            f"Failed to read from Renogy device after {self._max_retries} attempts: "
            f"{last_error}"
        )

    @abstractmethod
    async def _read_implementation(self) -> dict[str, Any]:
        """Internal implementation of read logic (without retry).

        Subclasses should implement this method instead of read().

        Returns:
            Dictionary containing the raw data from the device.

        Raises:
            Exception: On read failure (will trigger retry in read())
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources held by the reader."""
        pass

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Return a friendly name for the device being read."""
        pass

    @property
    @abstractmethod
    def connection_type(self) -> str:
        """Return the connection type identifier (e.g., 'bluetooth', 'modbus')."""
        pass
