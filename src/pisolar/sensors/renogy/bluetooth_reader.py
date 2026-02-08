"""Bluetooth reader for Renogy BT-1/BT-2 modules using renogy-ble library."""

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pisolar.config.renogy_config import DEFAULT_MAX_RETRIES, DEFAULT_SCAN_TIMEOUT
from pisolar.config.renogy_device_type import DeviceType
from pisolar.sensors.renogy.reader import RenogyReader

if TYPE_CHECKING:
    from bleak import BleakScanner
    from renogy_ble import RenogyBleClient, RenogyBLEDevice

# Delay between retry attempts
_RETRY_DELAY = 2.0  # seconds between retries


class BluetoothReader(RenogyReader):
    """Bluetooth reader for Renogy BT-1/BT-2 modules using renogy-ble library."""

    def __init__(
        self,
        mac_address: str,
        device_alias: str = "BT-2",
        device_type: DeviceType = DeviceType.CONTROLLER,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialize the Bluetooth reader.

        Args:
            mac_address: Bluetooth MAC address of the BT-1/BT-2 module
            device_alias: Friendly name for the device
            device_type: Device type - "controller", "rover", "wanderer", or "dcc"
            scan_timeout: Timeout in seconds for BLE scanning
            max_retries: Number of full scan+connect retry attempts
        """
        super().__init__(max_retries=max_retries, retry_delay=_RETRY_DELAY)
        self._mac_address = mac_address.upper()
        self._device_alias = device_alias
        self._device_type: DeviceType = device_type
        self._scan_timeout = scan_timeout

    @property
    def device_name(self) -> str:
        """Return the device alias."""
        return self._device_alias

    @property
    def connection_type(self) -> str:
        """Return the connection type identifier."""
        return "bluetooth"

    def close(self) -> None:
        """Clean up resources (no persistent connection for BLE)."""
        pass

    @staticmethod
    def _bluetooth_available() -> bool:
        """Return True if a Bluetooth adapter is present (Linux sysfs), or on non-Linux."""
        bt = Path("/sys/class/bluetooth")
        if not bt.exists():
            return True  # non-Linux or no sysfs; let the library handle it
        for adapter in bt.iterdir():
            if adapter.is_dir() and adapter.name.startswith("hci"):
                return True
        return False

    async def _read_implementation(self) -> dict[str, Any]:
        """Read data from the Renogy BT module via Bluetooth.

        Returns:
            Dictionary containing the raw data from the device.

        Raises:
            RuntimeError: If Bluetooth is not available or read fails.
        """
        if not self._bluetooth_available():
            raise RuntimeError(
                "No powered Bluetooth adapter found. Turn on Bluetooth and try again."
            )

        # Import at runtime to allow mocking in tests
        from bleak import BleakScanner
        from renogy_ble import RenogyBleClient, RenogyBLEDevice

        return await self._attempt_read(BleakScanner, RenogyBleClient, RenogyBLEDevice)

    async def _attempt_read(
        self,
        scanner_class: "type[BleakScanner]",
        client_class: "type[RenogyBleClient]",
        device_class: "type[RenogyBLEDevice]",
    ) -> dict[str, Any]:
        """Single attempt to scan and read from the device."""
        attempt_start = time.perf_counter()

        self._logger.debug(
            "Scanning for Renogy device %s (timeout: %.1fs)...",
            self._mac_address,
            self._scan_timeout,
        )

        # Use class method directly - more reliable than context manager
        device = await scanner_class.find_device_by_address(
            self._mac_address,
            timeout=self._scan_timeout,
        )

        scan_elapsed_ms = (time.perf_counter() - attempt_start) * 1000

        if device is None:
            self._logger.debug("Scan completed in %.1fms - device not found", scan_elapsed_ms)
            raise RuntimeError(
                f"Could not find Renogy device with MAC address {self._mac_address}. "
                "Ensure the device is powered on and in range."
            )

        self._logger.debug("Found device: %s (scan: %.1fms)", device.name, scan_elapsed_ms)

        # Map device_type to renogy-ble expected format
        ble_device_type = self._device_type.value
        if ble_device_type in ("rover", "wanderer"):
            ble_device_type = "controller"

        # Create renogy-ble device wrapper
        renogy_device = device_class(
            ble_device=device,
            advertisement_rssi=None,
            device_type=ble_device_type,
        )

        # Create client and read
        connect_start = time.perf_counter()
        client = client_class(max_attempts=5)
        result = await client.read_device(renogy_device)
        connect_elapsed_ms = (time.perf_counter() - connect_start) * 1000

        total_elapsed_ms = (time.perf_counter() - attempt_start) * 1000

        if not result.success:
            error_msg = str(result.error) if result.error else "Unknown error"
            raise RuntimeError(f"BLE read failed: {error_msg}")

        if not result.parsed_data:
            raise RuntimeError(
                "Renogy device returned empty data. "
                "Check device connection and try again."
            )

        # Build result dictionary
        data: dict[str, Any] = dict(result.parsed_data)
        data["__device"] = self._device_alias
        data["__client"] = "BluetoothReader"
        data["__scan_ms"] = round(scan_elapsed_ms, 1)
        data["__connect_ms"] = round(connect_elapsed_ms, 1)
        data["__total_ms"] = round(total_elapsed_ms, 1)

        # Log all fields received for debugging
        self._logger.debug(
            "Raw data fields from %s: %s",
            self._device_alias,
            list(result.parsed_data.keys()),
        )

        self._logger.info(
            "Read %d field(s) from %s via Bluetooth "
            "(scan: %.1fms, connect+read: %.1fms, total: %.1fms)",
            len(result.parsed_data),
            self._device_alias,
            scan_elapsed_ms,
            connect_elapsed_ms,
            total_elapsed_ms,
        )

        return data
