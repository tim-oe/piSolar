"""Renogy sensor implementation with pluggable readers (Bluetooth/Modbus)."""

import asyncio
import concurrent.futures
import time
from typing import Any, Union

from pisolar.config.renogy_config import (
    RenogyBluetoothSensorConfig,
    RenogySerialSensorConfig,
)
from pisolar.logging_config import get_logger
from pisolar.sensors.base_sensor import BaseSensor
from pisolar.sensors.renogy.reader import RenogyReader
from pisolar.sensors.renogy.reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading

# Type alias for sensor config union
RenogySensorConfig = Union[RenogyBluetoothSensorConfig, RenogySerialSensorConfig]


class RenogySensor(BaseSensor):
    """Renogy sensor with pluggable reader (Bluetooth or Modbus/Serial)."""

    _logger = get_logger("sensors.renogy")

    def __init__(self, config: RenogySensorConfig) -> None:
        """Initialize the Renogy sensor.

        Args:
            config: Sensor configuration (Bluetooth or Serial)
        """
        self._config = config
        self._reader = RenogyReader.create_reader(config)

    @property
    def sensor_type(self) -> str:
        """Return the sensor type identifier."""
        return "solar"

    @property
    def name(self) -> str:
        """Return the sensor name."""
        return self._config.name

    def read(self) -> list[SensorReading]:
        """Read data from the Renogy device.

        Returns:
            List containing a single SolarReading with device data.

        Raises:
            RuntimeError: If the read fails after retries.
        """
        start_time = time.perf_counter()

        try:
            # Run the async read
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                # Already in an async context - run in executor
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._read_sync)
                    return future.result(timeout=60.0)
            else:
                return asyncio.run(self._read_async())
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._logger.debug(
                "Total Renogy read time: %.1fms for %s (%s)",
                elapsed_ms,
                self._reader.device_name,
                self._reader.connection_type,
            )

    def _read_sync(self) -> list[SensorReading]:
        """Synchronous wrapper for async read."""
        return asyncio.run(self._read_async())

    async def _read_async(self) -> list[SensorReading]:
        """Async implementation of read using the configured reader."""
        start_time = time.perf_counter()

        try:
            data = await self._reader.read()
        except Exception as e:
            self._logger.error(
                "Failed to read from %s (%s): %s",
                self._reader.device_name,
                self._reader.connection_type,
                e,
            )
            raise

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Get timing from reader metadata if available
        read_duration = data.get("__total_ms", round(total_elapsed_ms, 1))

        reading = SolarReading.from_raw_data(
            sensor_type=self.sensor_type,
            name=self._reader.device_name,
            data=data,
            read_duration_ms=read_duration,
        )

        return [reading]

    def to_dict(self) -> dict[str, Any]:
        """Return sensor configuration as dictionary."""
        result = {
            "name": self._config.name,
            "type": self.sensor_type,
            "connection": self._reader.connection_type,
        }

        if self._config.read_type == "bt":
            result["mac_address"] = self._config.mac_address
        else:
            result["device_path"] = self._config.device_path

        return result

    def connect(self) -> bool:
        """Test connection to the device.

        Returns:
            True if connection succeeds.
        """
        # For Bluetooth, we don't maintain persistent connections
        # For Modbus, we could add a test read here
        return True

    def close(self) -> None:
        """Clean up reader resources."""
        if self._reader:
            self._reader.close()
