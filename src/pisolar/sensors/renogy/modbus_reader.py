"""Modbus/Serial reader for Renogy charge controllers.

Two transports are supported:
  - pymodbus (default, used for USB RS485 adapters)
  - raw pyserial RTU (used for GPIO UART adapters, e.g. DFRobot DFR0845)

pymodbus calls reset_input_buffer() between TX and RX which drops the first
bytes of the response on some Pi UART configurations. The raw pyserial
transport avoids this by transmitting, waiting for TX to complete, then
reading without any buffer flush.
"""

import asyncio
import time
from functools import partial
from typing import Any

import serial
from pymodbus.client import ModbusSerialClient

from pisolar.config.device_type import DeviceType
from pisolar.config.renogy_defaults import (
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SLAVE_ADDRESS,
)
from pisolar.sensors.renogy.renogy_reader import RenogyReader

# Delay between retry attempts
_RETRY_DELAY = 1.0  # seconds between retries


def _crc16(data: bytes) -> int:
    """Standard Modbus CRC16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _build_modbus_frame(slave: int, register: int, count: int) -> bytes:
    """Build a Modbus RTU FC03 read holding registers frame."""
    payload = bytes(
        [slave, 0x03, register >> 8, register & 0xFF, count >> 8, count & 0xFF]
    )
    crc = _crc16(payload)
    return payload + bytes([crc & 0xFF, crc >> 8])


def _read_registers_raw(
    port: serial.Serial,
    slave: int,
    register: int,
    count: int,
    timeout: float = 1.0,
) -> list[int]:
    """Read Modbus holding registers using raw pyserial.

    Does not flush the input buffer between TX and RX — required for
    GPIO UART adapters (e.g. DFRobot DFR0845) where the Pi UART delivers
    the response immediately after TX completes.

    Args:
        port:     Open pyserial Serial instance
        slave:    Modbus slave address
        register: Starting register address
        count:    Number of 16-bit registers to read
        timeout:  Read timeout in seconds

    Returns:
        List of count unsigned 16-bit integers

    Raises:
        RuntimeError: On timeout, short response, or CRC mismatch
    """
    frame = _build_modbus_frame(slave, register, count)
    expected = 3 + count * 2 + 2  # addr + fc + byte_count + data + CRC

    port.reset_input_buffer()
    port.write(frame)
    port.flush()

    buf = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = port.read(64)
        if chunk:
            buf += chunk
        if len(buf) >= expected:
            break

    if len(buf) < expected:
        raise RuntimeError(
            f"Modbus timeout on register 0x{register:04X}: "
            f"got {len(buf)}/{expected} bytes" + (f" raw={buf.hex()}" if buf else "")
        )

    computed = _crc16(bytes(buf[:-2]))
    received = buf[-2] | (buf[-1] << 8)
    if computed != received:
        raise RuntimeError(
            f"Modbus CRC mismatch on register 0x{register:04X}: "
            f"computed={computed:#06x} received={received:#06x}"
        )

    if buf[1] & 0x80:
        raise RuntimeError(
            f"Modbus exception on register 0x{register:04X}: code {buf[2]:#04x}"
        )

    return [(buf[3 + i * 2] << 8) | buf[4 + i * 2] for i in range(count)]


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
    """Modbus/Serial reader for Renogy charge controllers using pymodbus.

    Uses dependency injection for Modbus client to enable testing with mocks.
    """

    def __init__(
        self,
        device_path: str,
        device_name: str = "Renogy",
        device_type: DeviceType = DeviceType.CONTROLLER,
        baud_rate: int = DEFAULT_BAUD_RATE,
        slave_address: int = DEFAULT_SLAVE_ADDRESS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        serial_adapter: str = "usb",
        uart_tx_pin: int | None = None,
        uart_rx_pin: int | None = None,
    ) -> None:
        """Initialize the Modbus reader.

        Args:
            device_path: Serial port path (e.g., /dev/ttyUSB0)
            device_name: Friendly name for the device
            device_type: Device type - "controller", "rover", "wanderer", or "dcc"
            baud_rate: Serial baud rate (default 9600)
            slave_address: Modbus slave address (default 1)
            max_retries: Number of retry attempts for connection failures
            serial_adapter: Physical adapter type ("usb" or "uart")
            uart_tx_pin: Optional BCM GPIO TX pin (for diagnostics/docs)
            uart_rx_pin: Optional BCM GPIO RX pin (for diagnostics/docs)
        """
        super().__init__(max_retries=max_retries, retry_delay=_RETRY_DELAY)
        self._device_path = device_path
        self._device_name = device_name
        self._device_type: DeviceType = device_type
        self._baud_rate = baud_rate
        self._slave_address = slave_address
        self._serial_adapter = serial_adapter
        self._uart_tx_pin = uart_tx_pin
        self._uart_rx_pin = uart_rx_pin
        self._client = None

        # Dependency that can be overridden in tests by setting instance variable
        self._client_class = ModbusSerialClient

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

    async def _read_implementation(self) -> dict[str, Any]:
        """Read data from the Renogy controller via Modbus.

        Returns:
            Dictionary containing the raw data from the device.

        Raises:
            RuntimeError: If the read fails.
        """
        # Run synchronous Modbus operations in executor
        loop = asyncio.get_running_loop()
        # Type checker confused about bound method signatures - this is correct
        return await loop.run_in_executor(  # type: ignore[arg-type]
            None, partial(self._read_sync)
        )

    def _read_sync(self) -> dict[str, Any]:
        """Synchronous implementation of Modbus read.

        Uses raw pyserial transport for UART adapters (serial_adapter='uart')
        to avoid pymodbus reset_input_buffer() dropping response bytes on Pi
        GPIO UARTs. Falls back to pymodbus for USB adapters.
        """
        if self._serial_adapter == "uart":
            return self._read_sync_raw()
        return self._read_sync_pymodbus()

    def _read_sync_raw(self) -> dict[str, Any]:
        """Read using raw pyserial RTU — required for GPIO UART adapters."""
        start_time = time.perf_counter()

        try:
            port = serial.Serial(
                port=self._device_path,
                baudrate=self._baud_rate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.001,
            )
        except serial.SerialException as e:
            raise RuntimeError(f"Failed to open {self._device_path}: {e}") from e

        connect_elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._logger.debug(
            "Opened %s at %s via raw UART (%.1fms)%s",
            self._device_name,
            self._device_path,
            connect_elapsed_ms,
            (
                f" [TX GPIO{self._uart_tx_pin}, RX GPIO{self._uart_rx_pin}]"
                if self._uart_tx_pin is not None and self._uart_rx_pin is not None
                else ""
            ),
        )

        try:
            return self._read_registers(
                read_fn=lambda reg, count: _read_registers_raw(
                    port, self._slave_address, reg, count
                ),
                start_time=start_time,
                connect_elapsed_ms=connect_elapsed_ms,
                client_label="ModbusReader/raw",
            )
        finally:
            port.close()

    def _read_sync_pymodbus(self) -> dict[str, Any]:
        """Read using pymodbus — used for USB RS485 adapters."""
        start_time = time.perf_counter()

        client = self._client_class(
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
            self._logger.debug(
                "Connected to %s at %s via pymodbus (%.1fms)",
                self._device_name,
                self._device_path,
                connect_elapsed_ms,
            )

            def _pymodbus_read(reg: int, count: int) -> list[int]:
                result = client.read_holding_registers(
                    address=reg, count=count, device_id=self._slave_address
                )
                if result.isError():
                    raise RuntimeError(str(result))
                return list(result.registers)

            return self._read_registers(
                read_fn=_pymodbus_read,
                start_time=start_time,
                connect_elapsed_ms=connect_elapsed_ms,
                client_label="ModbusReader/pymodbus",
            )
        finally:
            client.close()

    def _read_registers(
        self,
        read_fn: Any,
        start_time: float,
        connect_elapsed_ms: float,
        client_label: str,
    ) -> dict[str, Any]:
        """Common register reading logic shared by both transports."""
        data: dict[str, Any] = {}
        read_errors = 0

        for reg_addr, field_name, scale_factor, _description in REGISTER_MAP:
            try:
                values = read_fn(reg_addr, 1)
                raw_value = values[0]
                value = raw_value * scale_factor
                if isinstance(scale_factor, float):
                    value = round(value, 2)
                data[field_name] = value
            except Exception as e:
                self._logger.debug(
                    "Error reading register 0x%04X (%s): %s",
                    reg_addr,
                    field_name,
                    e,
                )
                read_errors += 1

        # Combined temperature register
        try:
            values = read_fn(TEMPERATURE_REGISTER, 1)
            raw_temp = values[0]
            ctrl_temp, batt_temp = _parse_temperature_register(raw_temp)
            data["controller_temperature"] = ctrl_temp
            data["battery_temperature"] = batt_temp
            self._logger.debug(
                "Temperature register 0x%04X = 0x%04X -> ctrl=%d, batt=%d",
                TEMPERATURE_REGISTER,
                raw_temp,
                ctrl_temp,
                batt_temp,
            )
        except Exception as e:
            self._logger.debug("Exception reading temperature register: %s", e)
            read_errors += 1

        # Charging status register
        try:
            values = read_fn(STATUS_REGISTER, 1)
            status_code = values[0] & 0xFF
            data["charging_status"] = CHARGING_STATUS.get(
                status_code, f"unknown_{status_code}"
            )
        except Exception:
            pass

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000

        data["__device"] = self._device_name
        data["__client"] = client_label
        data["__serial_adapter"] = self._serial_adapter
        data["__connect_ms"] = round(connect_elapsed_ms, 1)
        data["__total_ms"] = round(total_elapsed_ms, 1)
        if self._uart_tx_pin is not None:
            data["__uart_tx_pin"] = self._uart_tx_pin
        if self._uart_rx_pin is not None:
            data["__uart_rx_pin"] = self._uart_rx_pin

        self._logger.info(
            "Read %d field(s) from %s via Modbus "
            "(connect: %.1fms, total: %.1fms, errors: %d)",
            len([k for k in data if not k.startswith("__")]),
            self._device_name,
            connect_elapsed_ms,
            total_elapsed_ms,
            read_errors,
        )

        if len(data) <= 4:
            raise RuntimeError(
                "Renogy device returned no readable data. "
                "Check device connection and Modbus address."
            )

        return data
