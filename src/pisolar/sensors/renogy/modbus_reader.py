"""Modbus/Serial reader for Renogy charge controllers using pymodbus."""

import asyncio
import time
from typing import Any, Literal

from pisolar.config.renogy_config import (
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SLAVE_ADDRESS,
)
from pisolar.logging_config import get_logger
from pisolar.sensors.renogy.reader import RenogyReader

logger = get_logger("sensors.renogy.modbus")

# Delay between retry attempts
_RETRY_DELAY = 1.0  # seconds between retries

# Renogy Modbus Register Map (from docs/rover_modbus.docx)
# Format: (register_address, field_name, scale_factor, description)
# Note: Temperature register 0x0103 is special - see _parse_temperature_register()
#
# IMPORTANT: Register layout verified against official Renogy Rover Modbus Protocol.
# Some community implementations use different addresses - this follows the doc.
REGISTER_MAP = [
    # Battery data (0x0100 - 0x0102)
    (0x0100, "battery_percentage", 1, "Battery SOC %"),
    (0x0101, "battery_voltage", 0.1, "Battery voltage V"),
    (0x0102, "battery_current", 0.01, "Charging current A"),
    # 0x0103 handled separately - combined temp register (high=controller, low=battery)
    # Load/Street light data (0x0104 - 0x0106) per official doc
    (0x0104, "load_voltage", 0.1, "Street light (load) voltage V"),
    (0x0105, "load_current", 0.01, "Street light (load) current A"),
    (0x0106, "load_power", 1, "Street light (load) power W"),
    # Solar panel data (0x0107 - 0x0109)
    (0x0107, "pv_voltage", 0.1, "Solar panel voltage V"),
    (0x0108, "pv_current", 0.01, "Solar panel current A"),
    (0x0109, "pv_power", 1, "Charging power W"),
    # Daily statistics (0x010B - 0x0114)
    (0x010B, "battery_min_voltage_today", 0.1, "Battery min voltage today V"),
    (0x010C, "battery_max_voltage_today", 0.1, "Battery max voltage today V"),
    (0x010D, "max_charging_current_today", 0.01, "Max charging current today A"),
    (0x010E, "max_discharging_current_today", 0.01, "Max discharging current today A"),
    (0x010F, "max_charging_power_today", 1, "Max charging power today W"),
    (0x0110, "max_discharging_power_today", 1, "Max discharging power today W"),
    (0x0111, "charging_amp_hours_today", 1, "Charging Ah today"),
    (0x0112, "discharging_amp_hours_today", 1, "Discharging Ah today"),
    # Power in kWh/10000 per doc - scale 0.0001 gives kWh, 0.1 gives Wh
    (0x0113, "power_generation_today", 0.1, "Power generation today Wh"),
    (0x0114, "power_consumption_today", 0.1, "Power consumption today Wh"),
]

# Temperature register - stores both controller and battery temp in one register
TEMPERATURE_REGISTER = 0x0103

# Status register for charging state
STATUS_REGISTER = 0x0120

# Charging status codes
CHARGING_STATUS = {
    0: "deactivated",
    1: "activated",
    2: "mppt",
    3: "equalizing",
    4: "boost",
    5: "floating",
    6: "current_limiting",
}

DeviceType = Literal["controller", "dcc", "rover", "wanderer"]


def _to_signed_8bit(value: int) -> int:
    """Convert 8-bit sign+magnitude value to signed integer.

    Per Renogy Modbus Protocol (docs/rover_modbus.pdf section 3.7):
    b7 = sign bit (1 = negative)
    b0-b6 = temperature magnitude (0-127)

    Examples from the official doc:
    - 0x28 (40) = +40°C
    - 0x8B = -11°C (sign bit + magnitude 11)
    """
    if value & 0x80:  # Sign bit set (negative)
        return -(value & 0x7F)
    return value


def _parse_temperature_register(raw_value: int) -> tuple[int, int]:
    """Parse combined temperature register into controller and battery temps.

    Renogy stores both temperatures in a single 16-bit register:
    - High byte (bits 15-8): Controller temperature (signed °C)
    - Low byte (bits 7-0): Battery temperature (signed °C)

    Args:
        raw_value: Raw 16-bit register value

    Returns:
        Tuple of (controller_temperature, battery_temperature) in Celsius
    """
    controller_temp = _to_signed_8bit((raw_value >> 8) & 0xFF)
    battery_temp = _to_signed_8bit(raw_value & 0xFF)
    return controller_temp, battery_temp


class ModbusReader(RenogyReader):
    """Modbus/Serial reader for Renogy charge controllers using pymodbus."""

    def __init__(
        self,
        device_path: str,
        device_name: str = "Renogy",
        device_type: DeviceType = "controller",
        baud_rate: int = DEFAULT_BAUD_RATE,
        slave_address: int = DEFAULT_SLAVE_ADDRESS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialize the Modbus reader.

        Args:
            device_path: Serial port path (e.g., /dev/ttyUSB0)
            device_name: Friendly name for the device
            device_type: Device type - "controller", "rover", "wanderer", or "dcc"
            baud_rate: Serial baud rate (default 9600)
            slave_address: Modbus slave address (default 1)
            max_retries: Number of retry attempts for connection failures
        """
        self._device_path = device_path
        self._device_name = device_name
        self._device_type: DeviceType = device_type
        self._baud_rate = baud_rate
        self._slave_address = slave_address
        self._max_retries = max_retries
        self._client = None

    @property
    def device_name(self) -> str:
        """Return the device name."""
        return self._device_name

    @property
    def connection_type(self) -> str:
        """Return the connection type identifier."""
        return "modbus"

    def close(self) -> None:
        """Close the Modbus connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    async def read(self) -> dict[str, Any]:
        """Read data from the Renogy controller via Modbus.

        Returns:
            Dictionary containing the raw data from the device.

        Raises:
            RuntimeError: If the read fails after retries.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                # Run synchronous Modbus operations in executor
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._read_sync)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                        attempt,
                        self._max_retries,
                        self._device_name,
                        str(e),
                        _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    logger.error(
                        "All %d attempts failed for %s",
                        self._max_retries,
                        self._device_name,
                    )

        raise RuntimeError(
            f"Failed to read from Renogy device after {self._max_retries} attempts: "
            f"{last_error}"
        )

    def _read_sync(self) -> dict[str, Any]:
        """Synchronous implementation of Modbus read."""
        from pymodbus.client import ModbusSerialClient

        start_time = time.perf_counter()

        # Create client if not exists
        client = ModbusSerialClient(
            port=self._device_path,
            baudrate=self._baud_rate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=3,
        )

        try:
            if not client.connect():
                raise RuntimeError(
                    f"Failed to connect to Modbus device at {self._device_path}"
                )

            connect_elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "Connected to %s at %s (%.1fms)",
                self._device_name,
                self._device_path,
                connect_elapsed_ms,
            )

            data: dict[str, Any] = {}
            read_errors = 0

            # Read each register
            for reg_addr, field_name, scale_factor, _description in REGISTER_MAP:
                try:
                    result = client.read_holding_registers(
                        address=reg_addr,
                        count=1,
                        device_id=self._slave_address,
                    )

                    if result.isError():
                        logger.debug(
                            "Error reading register 0x%04X (%s): %s",
                            reg_addr,
                            field_name,
                            result,
                        )
                        read_errors += 1
                        continue

                    raw_value = result.registers[0]

                    # Apply scale factor
                    value = raw_value * scale_factor

                    # Round floats for cleaner output
                    if isinstance(scale_factor, float):
                        value = round(value, 2)

                    data[field_name] = value

                except Exception as e:
                    logger.debug(
                        "Exception reading register 0x%04X (%s): %s",
                        reg_addr,
                        field_name,
                        e,
                    )
                    read_errors += 1

            # Read combined temperature register (0x0103)
            # High byte = controller temp, Low byte = battery temp (both signed)
            try:
                result = client.read_holding_registers(
                    address=TEMPERATURE_REGISTER,
                    count=1,
                    device_id=self._slave_address,
                )
                if not result.isError():
                    raw_temp = result.registers[0]
                    ctrl_temp, batt_temp = _parse_temperature_register(raw_temp)
                    data["controller_temperature"] = ctrl_temp
                    data["battery_temperature"] = batt_temp
                    logger.debug(
                        "Temperature register 0x%04X = 0x%04X -> ctrl=%d, batt=%d",
                        TEMPERATURE_REGISTER,
                        raw_temp,
                        ctrl_temp,
                        batt_temp,
                    )
                else:
                    read_errors += 1
            except Exception as e:
                logger.debug("Exception reading temperature register: %s", e)
                read_errors += 1

            # Try to read charging status
            try:
                result = client.read_holding_registers(
                    address=STATUS_REGISTER,
                    count=1,
                    device_id=self._slave_address,
                )
                if not result.isError():
                    status_code = result.registers[0] & 0xFF
                    data["charging_status"] = CHARGING_STATUS.get(
                        status_code, f"unknown_{status_code}"
                    )
            except Exception:
                pass  # Status register may not be available on all models

            total_elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Add metadata
            data["__device"] = self._device_name
            data["__client"] = "ModbusReader"
            data["__connect_ms"] = round(connect_elapsed_ms, 1)
            data["__total_ms"] = round(total_elapsed_ms, 1)

            logger.info(
                "Read %d field(s) from %s via Modbus "
                "(connect: %.1fms, total: %.1fms, errors: %d)",
                len(data) - 4,  # Exclude metadata fields
                self._device_name,
                connect_elapsed_ms,
                total_elapsed_ms,
                read_errors,
            )

            if len(data) <= 4:  # Only metadata, no actual data
                raise RuntimeError(
                    "Renogy device returned no readable data. "
                    "Check device connection and Modbus address."
                )

            return data

        finally:
            client.close()
