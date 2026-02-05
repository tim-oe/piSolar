"""Renogy BT-2 sensor implementation using renogy-ble library."""

import asyncio
import time
from pathlib import Path
from typing import Any, Literal

from pisolar.config.renogy_config import DEFAULT_MAX_RETRIES, DEFAULT_SCAN_TIMEOUT
from pisolar.logging_config import get_logger
from pisolar.sensors.base_sensor import BaseSensor
from pisolar.sensors.renogy.reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading

logger = get_logger("sensors.renogy")

# Supported device types from renogy-ble
DeviceType = Literal["controller", "dcc"]

# Delay between retry attempts (not configurable, internal constant)
_RETRY_DELAY = 2.0  # seconds between retries


def _bluetooth_available() -> bool:
    """Return True if a Bluetooth adapter is present (Linux sysfs), or on non-Linux."""
    bt = Path("/sys/class/bluetooth")
    if not bt.exists():
        return True  # non-Linux or no sysfs; let the library handle it
    for adapter in bt.iterdir():
        if adapter.is_dir() and adapter.name.startswith("hci"):
            return True
    return False


class RenogySensor(BaseSensor):
    """Renogy BT-2 Bluetooth module sensor using renogy-ble library."""

    def __init__(
        self,
        mac_address: str,
        device_alias: str = "BT-2",
        device_type: DeviceType = "controller",
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """
        Initialize the Renogy sensor.

        Args:
            mac_address: Bluetooth MAC address of the BT-2 module
            device_alias: Friendly name for the device
            device_type: Device type - "controller" for solar charge controllers,
                        "dcc" for DC-DC chargers
            scan_timeout: Timeout in seconds for BLE scanning
            max_retries: Number of full scan+connect retry attempts
        """
        self._mac_address = mac_address.upper()
        self._device_alias = device_alias
        self._device_type: DeviceType = device_type
        self._scan_timeout = scan_timeout
        self._max_retries = max_retries

    @property
    def sensor_type(self) -> str:
        """Return the sensor type identifier."""
        return "solar"

    def read(self) -> list[SensorReading]:
        """Read data from the Renogy BT-2 module."""
        start_time = time.perf_counter()

        if not _bluetooth_available():
            raise RuntimeError(
                "No powered Bluetooth adapter found. Turn on Bluetooth and try again."
            )

        # Run the async read in a new event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        try:
            if loop is not None:
                # Already in an async context - use nest_asyncio or run in executor
                # For simplicity, create a new thread with its own event loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._read_sync)
                    return future.result(timeout=30.0)
            else:
                return asyncio.run(self._read_async())
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Total Renogy read time: %.1fms for %s",
                elapsed_ms,
                self._device_alias,
            )

    def _read_sync(self) -> list[SensorReading]:
        """Synchronous wrapper for async read."""
        return asyncio.run(self._read_async())

    async def _read_async(self) -> list[SensorReading]:
        """Async implementation of read using renogy-ble."""
        from bleak import BleakScanner
        from renogy_ble import RenogyBleClient, RenogyBLEDevice

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                result = await self._attempt_read(BleakScanner, RenogyBleClient, RenogyBLEDevice)
                return result
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                        attempt,
                        self._max_retries,
                        self._device_alias,
                        str(e),
                        _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    logger.error(
                        "All %d attempts failed for %s",
                        self._max_retries,
                        self._device_alias,
                    )

        raise RuntimeError(
            f"Failed to read from Renogy device after {self._max_retries} attempts: "
            f"{last_error}"
        )

    async def _attempt_read(
        self,
        scanner_class: type,
        client_class: type,
        device_class: type,
    ) -> list[SensorReading]:
        """Single attempt to scan and read from the device."""
        attempt_start = time.perf_counter()

        logger.debug(
            "Scanning for Renogy device %s (timeout: %.1fs)...",
            self._mac_address,
            self._scan_timeout,
        )

        # Use class method directly - more reliable than context manager
        # which can conflict with other scans in progress
        device = await scanner_class.find_device_by_address(
            self._mac_address,
            timeout=self._scan_timeout,
        )

        scan_elapsed_ms = (time.perf_counter() - attempt_start) * 1000

        if device is None:
            logger.debug("Scan completed in %.1fms - device not found", scan_elapsed_ms)
            raise RuntimeError(
                f"Could not find Renogy device with MAC address {self._mac_address}. "
                "Ensure the device is powered on and in range."
            )

        logger.debug("Found device: %s (scan: %.1fms)", device.name, scan_elapsed_ms)

        # Create renogy-ble device wrapper
        renogy_device = device_class(
            ble_device=device,
            advertisement_rssi=None,
            device_type=self._device_type,
        )

        # Create client and read - bleak-retry-connector handles connection retries
        connect_start = time.perf_counter()
        client = client_class(max_attempts=5)
        result = await client.read_device(renogy_device)
        connect_elapsed_ms = (time.perf_counter() - connect_start) * 1000

        # Total time for this attempt
        total_elapsed_ms = (time.perf_counter() - attempt_start) * 1000

        if not result.success:
            error_msg = str(result.error) if result.error else "Unknown error"
            raise RuntimeError(f"BLE read failed: {error_msg}")

        # Validate we got meaningful data
        if not result.parsed_data:
            raise RuntimeError(
                "Renogy device returned empty data. "
                "Check device connection and try again."
            )

        # Add device metadata
        data: dict[str, Any] = dict(result.parsed_data)
        data["__device"] = self._device_alias
        data["__client"] = "RenogyBleClient"

        reading = SolarReading.from_raw_data(
            sensor_type=self.sensor_type,
            name=self._device_alias,
            data=data,
            read_duration_ms=round(total_elapsed_ms, 1),
        )

        logger.info(
            "Read %d field(s) from %s (scan: %.1fms, connect+read: %.1fms, total: %.1fms)",
            len(result.parsed_data),
            self._device_alias,
            scan_elapsed_ms,
            connect_elapsed_ms,
            total_elapsed_ms,
        )

        return [reading]
