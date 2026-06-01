"""Tests for ModbusReader."""

import asyncio
import itertools
from unittest.mock import MagicMock, patch

import pytest

from pisolar.sensors.renogy.modbus_reader import (
    ModbusReader,
    _build_modbus_frame,
    _crc16,
    _parse_temperature_register,
    _read_registers_raw,
    _to_signed_8bit,
)


class TestTemperatureParsing:
    """Tests for temperature register parsing."""

    def test_to_signed_8bit_positive(self):
        """Test positive values remain positive."""
        assert _to_signed_8bit(0) == 0
        assert _to_signed_8bit(25) == 25
        assert _to_signed_8bit(0x28) == 40  # 40°C from doc example
        assert _to_signed_8bit(127) == 127

    def test_to_signed_8bit_negative(self):
        """Test sign+magnitude format per Renogy protocol.

        Per docs/rover_modbus.pdf section 3.7:
        b7 = sign bit (1 = negative)
        b0-b6 = magnitude

        Example from doc: 0x8B = -11°C (sign bit + magnitude 11)
        """
        assert _to_signed_8bit(0x8B) == -11  # -11°C from doc example
        assert _to_signed_8bit(0x8A) == -10  # -10°C
        assert _to_signed_8bit(0x81) == -1
        assert _to_signed_8bit(0x80) == 0  # -0°C (sign bit, zero magnitude)

    def test_to_signed_8bit_boundary_values(self):
        """Test boundary values for sign+magnitude format."""
        # Maximum positive value (0x7F = 127)
        assert _to_signed_8bit(0x7F) == 127

        # Maximum negative value (0xFF = sign bit + 127 = -127)
        assert _to_signed_8bit(0xFF) == -127

        # Minimum positive (excluding zero)
        assert _to_signed_8bit(0x01) == 1

        # Minimum negative (sign bit + 1 = -1)
        assert _to_signed_8bit(0x81) == -1

        # Negative zero (0x80 = sign bit + 0)
        assert _to_signed_8bit(0x80) == 0

    def test_parse_temperature_register_positive_temps(self):
        """Test parsing combined register with positive temperatures."""
        # 0x1900 = controller=25°C, battery=0°C (the user's actual value)
        ctrl, batt = _parse_temperature_register(0x1900)
        assert ctrl == 25
        assert batt == 0

        # 0x1E14 = controller=30°C, battery=20°C
        ctrl, batt = _parse_temperature_register(0x1E14)
        assert ctrl == 30
        assert batt == 20

    def test_parse_temperature_register_negative_temps(self):
        """Test parsing combined register with negative temperatures.

        Using sign+magnitude format: 0x8A = -10°C (sign bit + magnitude 10)
        """
        # 0x8A8A = controller=-10°C, battery=-10°C
        ctrl, batt = _parse_temperature_register(0x8A8A)
        assert ctrl == -10
        assert batt == -10

        # 0x8586 = controller=-5°C, battery=-6°C
        ctrl, batt = _parse_temperature_register(0x8586)
        assert ctrl == -5
        assert batt == -6

    def test_parse_temperature_register_mixed_temps(self):
        """Test parsing with one positive and one negative temperature."""
        # 0x198A = controller=25°C, battery=-10°C (sign+magnitude)
        ctrl, batt = _parse_temperature_register(0x198A)
        assert ctrl == 25
        assert batt == -10

        # 0x8A19 = controller=-10°C, battery=25°C
        ctrl, batt = _parse_temperature_register(0x8A19)
        assert ctrl == -10
        assert batt == 25


# =============================================================================
# Sample Modbus register test data sets
# Format: {register_address: raw_value}
# Register addresses verified against docs/rover_modbus.pdf
# =============================================================================

# Typical operating values from a Renogy Wanderer controller
SAMPLE_MODBUS_DATA = {
    0x0100: 85,  # battery_percentage: 85%
    0x0101: 132,  # battery_voltage: 13.2V (raw * 0.1)
    0x0102: 350,  # battery_current: 3.5A (raw * 0.01)
    0x0103: 0x1914,  # temperature: controller=25°C, battery=20°C
    # Load data per official doc (0x0104-0x0106)
    0x0104: 132,  # load_voltage: 13.2V (raw * 0.1)
    0x0105: 50,  # load_current: 0.5A (raw * 0.01)
    0x0106: 7,  # load_power: 7W
    # Solar panel data (0x0107-0x0109)
    0x0107: 185,  # pv_voltage: 18.5V (raw * 0.1)
    0x0108: 280,  # pv_current: 2.8A (raw * 0.01)
    0x0109: 52,  # pv_power: 52W
    # Daily statistics (0x010B-0x0114)
    0x010B: 125,  # battery_min_voltage_today: 12.5V (raw * 0.1)
    0x010C: 145,  # battery_max_voltage_today: 14.5V (raw * 0.1)
    0x010D: 450,  # max_charging_current_today: 4.5A (raw * 0.01)
    0x010E: 100,  # max_discharging_current_today: 1.0A (raw * 0.01)
    0x010F: 55,  # max_charging_power_today: 55W
    0x0110: 1,  # max_discharging_power_today: 1W
    0x0111: 12,  # charging_amp_hours_today: 12Ah
    0x0112: 2,  # discharging_amp_hours_today: 2Ah
    0x0113: 1800,  # power_generation_today: 180Wh (raw * 0.1 per doc)
    0x0114: 250,  # power_consumption_today: 25Wh (raw * 0.1 per doc)
    0x0120: 2,  # charging_status: mppt
}

# Minimum values - empty battery, no solar, no load, cold temps
SAMPLE_MIN_VALUES = {
    0x0100: 0,  # battery_percentage: 0% (empty)
    0x0101: 0,  # battery_voltage: 0V
    0x0102: 0,  # battery_current: 0A
    0x0103: 0x0000,  # temperature: controller=0°C, battery=0°C
    0x0104: 0,  # load_voltage: 0V
    0x0105: 0,  # load_current: 0A
    0x0106: 0,  # load_power: 0W
    0x0107: 0,  # pv_voltage: 0V (night)
    0x0108: 0,  # pv_current: 0A
    0x0109: 0,  # pv_power: 0W
    0x010B: 0,  # battery_min_voltage_today: 0V
    0x010C: 0,  # battery_max_voltage_today: 0V
    0x010D: 0,  # max_charging_current_today: 0A
    0x010E: 0,  # max_discharging_current_today: 0A
    0x010F: 0,  # max_charging_power_today: 0W
    0x0110: 0,  # max_discharging_power_today: 0W
    0x0111: 0,  # charging_amp_hours_today: 0Ah
    0x0112: 0,  # discharging_amp_hours_today: 0Ah
    0x0113: 0,  # power_generation_today: 0Wh
    0x0114: 0,  # power_consumption_today: 0Wh
    0x0120: 0,  # charging_status: deactivated
}

# Maximum realistic values - full battery, high solar output, max temps
# Uses 16-bit max (0xFFFF = 65535) where applicable
SAMPLE_MAX_VALUES = {
    0x0100: 100,  # battery_percentage: 100% (full, not 0xFFFF - capped at 100)
    0x0101: 600,  # battery_voltage: 60.0V (48V system max realistic)
    0x0102: 6000,  # battery_current: 60.0A (60A controller max)
    0x0103: 0x7F7F,  # temperature: controller=127°C, battery=127°C (max positive)
    0x0104: 600,  # load_voltage: 60.0V
    0x0105: 6000,  # load_current: 60.0A
    0x0106: 3600,  # load_power: 3600W
    0x0107: 1500,  # pv_voltage: 150.0V (high Voc solar array)
    0x0108: 4000,  # pv_current: 40.0A
    0x0109: 6000,  # pv_power: 6000W
    0x010B: 600,  # battery_min_voltage_today: 60.0V
    0x010C: 600,  # battery_max_voltage_today: 60.0V
    0x010D: 6000,  # max_charging_current_today: 60.0A
    0x010E: 6000,  # max_discharging_current_today: 60.0A
    0x010F: 6000,  # max_charging_power_today: 6000W
    0x0110: 6000,  # max_discharging_power_today: 6000W
    0x0111: 9999,  # charging_amp_hours_today: 9999Ah
    0x0112: 9999,  # discharging_amp_hours_today: 9999Ah
    0x0113: 65535,  # power_generation_today: 6553.5Wh (16-bit max * 0.1)
    0x0114: 65535,  # power_consumption_today: 6553.5Wh
    0x0120: 5,  # charging_status: floating
}

# Extreme cold temperatures - sign+magnitude format
# 0xFF = sign bit (0x80) + magnitude 127 = -127°C
SAMPLE_EXTREME_COLD = {
    **SAMPLE_MODBUS_DATA,
    0x0103: 0xFFFF,  # controller=-127°C, battery=-127°C (min possible)
}

# Extreme hot temperatures
SAMPLE_EXTREME_HOT = {
    **SAMPLE_MODBUS_DATA,
    0x0103: 0x7F7F,  # controller=+127°C, battery=+127°C (max possible)
}

# Mixed extreme temperatures - hot controller, cold battery
SAMPLE_MIXED_EXTREME_TEMPS = {
    **SAMPLE_MODBUS_DATA,
    0x0103: 0x7FFF,  # controller=+127°C, battery=-127°C
}

# 16-bit unsigned maximum for voltage/current fields (overflow test)
SAMPLE_16BIT_MAX = {
    0x0100: 100,  # battery_percentage: capped at 100
    0x0101: 0xFFFF,  # battery_voltage: 6553.5V (raw * 0.1)
    0x0102: 0xFFFF,  # battery_current: 655.35A (raw * 0.01)
    0x0103: 0x0000,  # temperature: 0°C, 0°C
    0x0104: 0xFFFF,  # load_voltage: 6553.5V
    0x0105: 0xFFFF,  # load_current: 655.35A
    0x0106: 0xFFFF,  # load_power: 65535W
    0x0107: 0xFFFF,  # pv_voltage: 6553.5V
    0x0108: 0xFFFF,  # pv_current: 655.35A
    0x0109: 0xFFFF,  # pv_power: 65535W
    0x010B: 0xFFFF,  # battery_min_voltage_today: 6553.5V
    0x010C: 0xFFFF,  # battery_max_voltage_today: 6553.5V
    0x010D: 0xFFFF,  # max_charging_current_today: 655.35A
    0x010E: 0xFFFF,  # max_discharging_current_today: 655.35A
    0x010F: 0xFFFF,  # max_charging_power_today: 65535W
    0x0110: 0xFFFF,  # max_discharging_power_today: 65535W
    0x0111: 0xFFFF,  # charging_amp_hours_today: 65535Ah
    0x0112: 0xFFFF,  # discharging_amp_hours_today: 65535Ah
    0x0113: 0xFFFF,  # power_generation_today: 6553.5Wh
    0x0114: 0xFFFF,  # power_consumption_today: 6553.5Wh
    0x0120: 6,  # charging_status: current_limiting
}


class TestModbusReader:
    """Tests for ModbusReader."""

    def _create_mock_client(self, register_data: dict[int, int]):
        """Create a mock Modbus client that returns data based on register address."""
        mock_client = MagicMock()
        mock_client.connect.return_value = True

        def mock_read_registers(address, count, device_id):
            result = MagicMock()
            if address in register_data:
                result.isError.return_value = False
                result.registers = [register_data[address]]
            else:
                result.isError.return_value = True
            return result

        mock_client.read_holding_registers.side_effect = mock_read_registers
        return mock_client

    def test_read_success(self):
        """Test successful Modbus read."""
        mock_client = MagicMock()
        mock_client.connect.return_value = True

        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [100]

        mock_client.read_holding_registers.return_value = mock_result

        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        assert "battery_percentage" in data
        assert data["battery_percentage"] == 100
        mock_client.connect.assert_called_once()
        mock_client.close.assert_called_once()

    def test_read_with_sample_data(self):
        """Test reading with realistic sample data and verify all parsed values."""
        mock_client = self._create_mock_client(SAMPLE_MODBUS_DATA)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="wanderer",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Verify battery data
        assert data["battery_percentage"] == 85
        assert data["battery_voltage"] == 13.2
        assert data["battery_current"] == 3.5

        # Verify temperature parsing (combined register)
        assert data["controller_temperature"] == 25
        assert data["battery_temperature"] == 20

        # Verify solar panel data
        assert data["pv_voltage"] == 18.5
        assert data["pv_current"] == 2.8
        assert data["pv_power"] == 52

        # Verify load data (registers 0x0104-0x0106 per official doc)
        assert data["load_voltage"] == 13.2
        assert data["load_current"] == 0.5
        assert data["load_power"] == 7

        # Verify daily statistics
        assert data["battery_min_voltage_today"] == 12.5
        assert data["battery_max_voltage_today"] == 14.5
        assert data["max_charging_current_today"] == 4.5
        assert data["max_discharging_current_today"] == 1.0
        assert data["max_charging_power_today"] == 55
        assert data["max_discharging_power_today"] == 1
        assert data["charging_amp_hours_today"] == 12
        assert data["discharging_amp_hours_today"] == 2
        # Power in kWh/10000 per doc, so raw * 0.1 = Wh
        assert data["power_generation_today"] == 180.0
        assert data["power_consumption_today"] == 25.0

        # Verify charging status
        assert data["charging_status"] == "mppt"

        # Verify metadata
        assert data["__device"] == "wanderer"
        assert data["__client"] == "ModbusReader/pymodbus"

    def test_read_with_negative_temperatures(self):
        """Test reading with negative temperatures (cold weather).

        Using sign+magnitude format per Renogy protocol:
        0x8A = -10°C (sign bit set + magnitude 10)
        """
        cold_weather_data = SAMPLE_MODBUS_DATA.copy()
        # 0x8A8A = controller=-10°C, battery=-10°C (sign+magnitude)
        cold_weather_data[0x0103] = 0x8A8A

        mock_client = self._create_mock_client(cold_weather_data)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        assert data["controller_temperature"] == -10
        assert data["battery_temperature"] == -10

    def test_read_user_reported_value(self):
        """Test parsing the exact value the user reported (6400 = 0x1900)."""
        user_data = SAMPLE_MODBUS_DATA.copy()
        # User reported 6400 which is 0x1900 = controller=25°C, battery=0°C
        user_data[0x0103] = 6400  # 0x1900 in decimal

        mock_client = self._create_mock_client(user_data)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="wanderer",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # 6400 = 0x1900: high byte=0x19=25, low byte=0x00=0
        assert data["controller_temperature"] == 25
        assert data["battery_temperature"] == 0

    def test_read_connection_failure(self):
        """Test read fails when Modbus connection fails."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        with pytest.raises(RuntimeError, match="Failed to connect"):
            asyncio.run(reader.read())

    def test_read_min_values(self):
        """Test reading with all minimum values (zeros)."""
        mock_client = self._create_mock_client(SAMPLE_MIN_VALUES)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # All zeros
        assert data["battery_percentage"] == 0
        assert data["battery_voltage"] == 0.0
        assert data["battery_current"] == 0.0
        assert data["controller_temperature"] == 0
        assert data["battery_temperature"] == 0
        assert data["load_voltage"] == 0.0
        assert data["load_current"] == 0.0
        assert data["load_power"] == 0
        assert data["pv_voltage"] == 0.0
        assert data["pv_current"] == 0.0
        assert data["pv_power"] == 0
        assert data["power_generation_today"] == 0.0
        assert data["power_consumption_today"] == 0.0
        assert data["charging_status"] == "deactivated"

    def test_read_max_realistic_values(self):
        """Test reading with maximum realistic operating values."""
        mock_client = self._create_mock_client(SAMPLE_MAX_VALUES)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Battery at 100%
        assert data["battery_percentage"] == 100

        # 48V system max voltage
        assert data["battery_voltage"] == 60.0
        assert data["battery_current"] == 60.0

        # Maximum positive temperatures (+127°C)
        assert data["controller_temperature"] == 127
        assert data["battery_temperature"] == 127

        # High solar output
        assert data["pv_voltage"] == 150.0
        assert data["pv_current"] == 40.0
        assert data["pv_power"] == 6000

        # Charging status floating
        assert data["charging_status"] == "floating"

    def test_read_16bit_max_values(self):
        """Test reading with 16-bit maximum values (0xFFFF = 65535).

        Verifies unsigned integer overflow handling for all voltage,
        current, and power fields.
        """
        mock_client = self._create_mock_client(SAMPLE_16BIT_MAX)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Voltage fields: 0xFFFF * 0.1 = 6553.5V
        assert data["battery_voltage"] == 6553.5
        assert data["load_voltage"] == 6553.5
        assert data["pv_voltage"] == 6553.5
        assert data["battery_min_voltage_today"] == 6553.5
        assert data["battery_max_voltage_today"] == 6553.5

        # Current fields: 0xFFFF * 0.01 = 655.35A
        assert data["battery_current"] == 655.35
        assert data["load_current"] == 655.35
        assert data["pv_current"] == 655.35
        assert data["max_charging_current_today"] == 655.35
        assert data["max_discharging_current_today"] == 655.35

        # Power fields: 0xFFFF = 65535W
        assert data["load_power"] == 65535
        assert data["pv_power"] == 65535
        assert data["max_charging_power_today"] == 65535
        assert data["max_discharging_power_today"] == 65535

        # Daily stats: 0xFFFF * 0.1 = 6553.5Wh for power
        assert data["power_generation_today"] == 6553.5
        assert data["power_consumption_today"] == 6553.5

        # Amp-hours: 0xFFFF = 65535Ah
        assert data["charging_amp_hours_today"] == 65535
        assert data["discharging_amp_hours_today"] == 65535

    def test_read_extreme_cold_temperatures(self):
        """Test reading with extreme cold temperatures (-127°C).

        Sign+magnitude format: 0xFF = 0x80 (sign) + 0x7F (127) = -127°C
        """
        mock_client = self._create_mock_client(SAMPLE_EXTREME_COLD)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Minimum possible temperatures
        assert data["controller_temperature"] == -127
        assert data["battery_temperature"] == -127

    def test_read_extreme_hot_temperatures(self):
        """Test reading with extreme hot temperatures (+127°C)."""
        mock_client = self._create_mock_client(SAMPLE_EXTREME_HOT)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Maximum possible temperatures
        assert data["controller_temperature"] == 127
        assert data["battery_temperature"] == 127

    def test_read_mixed_extreme_temperatures(self):
        """Test reading with mixed extreme temps (hot controller, cold battery)."""
        mock_client = self._create_mock_client(SAMPLE_MIXED_EXTREME_TEMPS)
        mock_client_class = MagicMock(return_value=mock_client)

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )
        reader._client_class = mock_client_class

        data = asyncio.run(reader.read())

        # Controller at max positive, battery at max negative
        assert data["controller_temperature"] == 127
        assert data["battery_temperature"] == -127


# =============================================================================
# Raw pyserial transport helpers
# =============================================================================


class TestCrc16:
    """Tests for Modbus CRC16 implementation."""

    def test_known_frame_crc(self):
        """CRC for a known FC03 request frame (slave=3, reg=0x0000, count=1)."""
        # Frame: 03 03 00 00 00 01 + CRC
        # CRC integer = 0xE885; stored little-endian → low byte=0x85, high byte=0xE8
        payload = bytes([0x03, 0x03, 0x00, 0x00, 0x00, 0x01])
        crc = _crc16(payload)
        assert crc == 0xE885
        assert crc & 0xFF == 0x85   # frame[-2] (low byte)
        assert crc >> 8 == 0xE8     # frame[-1] (high byte)

    def test_crc_empty(self):
        """CRC of empty data is 0xFFFF (initial value)."""
        assert _crc16(b"") == 0xFFFF

    def test_crc_single_byte(self):
        """CRC is deterministic for a single byte."""
        crc1 = _crc16(bytes([0x03]))
        crc2 = _crc16(bytes([0x03]))
        assert crc1 == crc2

    def test_crc_different_data_differs(self):
        """Different payloads produce different CRCs."""
        assert _crc16(bytes([0x01])) != _crc16(bytes([0x02]))


class TestBuildModbusFrame:
    """Tests for Modbus RTU FC03 frame builder."""

    def test_frame_length(self):
        """FC03 request is always 8 bytes (6 payload + 2 CRC)."""
        frame = _build_modbus_frame(slave=1, register=0x0100, count=1)
        assert len(frame) == 8

    def test_frame_slave_address(self):
        """First byte is the slave address."""
        frame = _build_modbus_frame(slave=16, register=0x0100, count=1)
        assert frame[0] == 16

    def test_frame_function_code(self):
        """Second byte is FC03 (0x03)."""
        frame = _build_modbus_frame(slave=1, register=0x0100, count=1)
        assert frame[1] == 0x03

    def test_frame_register_high_low(self):
        """Register address split into bytes 2-3."""
        frame = _build_modbus_frame(slave=1, register=0x0107, count=1)
        assert frame[2] == 0x01
        assert frame[3] == 0x07

    def test_frame_count(self):
        """Register count split into bytes 4-5."""
        frame = _build_modbus_frame(slave=1, register=0x0100, count=3)
        assert frame[4] == 0x00
        assert frame[5] == 0x03

    def test_frame_crc_valid(self):
        """CRC appended to frame is valid for the payload."""
        frame = _build_modbus_frame(slave=3, register=0x0000, count=1)
        payload = bytes(frame[:-2])
        crc = _crc16(payload)
        assert frame[-2] == crc & 0xFF
        assert frame[-1] == crc >> 8

    def test_known_wind_speed_frame(self):
        """Exact frame verified against live SEN0483 sensor response."""
        frame = _build_modbus_frame(slave=3, register=0x0000, count=1)
        assert frame == bytes([0x03, 0x03, 0x00, 0x00, 0x00, 0x01, 0x85, 0xE8])


def _make_raw_response(slave: int, register_values: list[int]) -> bytes:
    """Build a valid Modbus FC03 response frame for given register values."""
    count = len(register_values)
    byte_count = count * 2
    payload = bytes([slave, 0x03, byte_count])
    for v in register_values:
        payload += bytes([v >> 8, v & 0xFF])
    crc = _crc16(payload)
    return payload + bytes([crc & 0xFF, crc >> 8])


def _make_mock_port(response: bytes) -> MagicMock:
    """Create a mock pyserial Serial port that returns response bytes on read()."""
    port = MagicMock()
    # Return the full response on the first call, then endless empty bytes so
    # the read loop never exhausts the side_effect iterator regardless of timeout.
    port.read.side_effect = itertools.chain([response], itertools.repeat(b""))
    port.baudrate = 9600
    return port


class TestReadRegistersRaw:
    """Tests for _read_registers_raw() pyserial transport."""

    def test_single_register_success(self):
        """Reads a single register value from a valid response frame."""
        response = _make_raw_response(slave=1, register_values=[85])
        port = _make_mock_port(response)

        values = _read_registers_raw(port, slave=1, register=0x0100, count=1)

        assert values == [85]
        port.reset_input_buffer.assert_called_once()
        port.write.assert_called_once()
        port.flush.assert_called_once()

    def test_multiple_registers_success(self):
        """Reads multiple register values from a valid response frame."""
        response = _make_raw_response(slave=1, register_values=[132, 350])
        port = _make_mock_port(response)

        values = _read_registers_raw(port, slave=1, register=0x0101, count=2)

        assert values == [132, 350]

    def test_zero_value_register(self):
        """Correctly reads a register value of zero."""
        response = _make_raw_response(slave=3, register_values=[0])
        port = _make_mock_port(response)

        values = _read_registers_raw(port, slave=3, register=0x0000, count=1)

        assert values == [0]

    def test_max_uint16_value(self):
        """Correctly reads a register value of 0xFFFF."""
        response = _make_raw_response(slave=1, register_values=[0xFFFF])
        port = _make_mock_port(response)

        values = _read_registers_raw(port, slave=1, register=0x0100, count=1)

        assert values == [0xFFFF]

    def test_timeout_raises(self):
        """Raises RuntimeError when no response received within timeout."""
        port = MagicMock()
        port.read.return_value = b""
        port.baudrate = 9600

        with pytest.raises(RuntimeError, match="Modbus timeout"):
            _read_registers_raw(port, slave=1, register=0x0100, count=1, timeout=0.01)

    def test_short_response_raises(self):
        """Raises RuntimeError when response is shorter than expected."""
        port = MagicMock()
        port.read.side_effect = itertools.chain(
            [bytes([0x01, 0x03])], itertools.repeat(b"")
        )
        port.baudrate = 9600

        with pytest.raises(RuntimeError, match="Modbus timeout"):
            _read_registers_raw(port, slave=1, register=0x0100, count=1, timeout=0.01)

    def test_crc_mismatch_raises(self):
        """Raises RuntimeError when CRC does not match."""
        response = bytearray(_make_raw_response(slave=1, register_values=[85]))
        response[-1] ^= 0xFF  # corrupt last CRC byte
        port = _make_mock_port(bytes(response))

        with pytest.raises(RuntimeError, match="CRC mismatch"):
            _read_registers_raw(port, slave=1, register=0x0100, count=1)

    def test_modbus_exception_raises(self):
        """Raises RuntimeError when device returns a Modbus exception response.

        For count=1 the reader expects exactly 7 bytes.  Build a 7-byte frame
        with FC=0x83 (error bit set) so the exception check is reached after
        the length and CRC checks pass.
        """
        # 7-byte frame: slave + FC|0x80 + error_code + 2 padding bytes + CRC
        exc_payload = bytes([0x01, 0x83, 0x02, 0x00, 0x00])
        crc = _crc16(exc_payload)
        response = exc_payload + bytes([crc & 0xFF, crc >> 8])
        port = _make_mock_port(response)

        with pytest.raises(RuntimeError, match="Modbus exception"):
            _read_registers_raw(port, slave=1, register=0x0100, count=1)

    def test_chunked_response(self):
        """Handles response arriving in multiple read() chunks."""
        response = _make_raw_response(slave=1, register_values=[85])
        # Split into two chunks
        port = MagicMock()
        port.read.side_effect = [response[:3], response[3:], b"", b""]
        port.baudrate = 9600

        values = _read_registers_raw(port, slave=1, register=0x0100, count=1)

        assert values == [85]


class TestModbusReaderRawTransport:
    """Tests for ModbusReader using raw pyserial transport (serial_adapter='uart').

    Avoids the busy-wait timeout in _read_registers_raw by testing at the right
    layer for each concern:

    * Routing tests  — mock _read_sync_raw / _read_sync_pymodbus directly.
    * Parsing tests  — call _read_registers() with a plain dict-backed lambda.
    * Port-open test — patch serial.Serial and mock _read_registers immediately.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dict_read_fn(register_data: dict[int, int]):
        """Return a read_fn that looks up values from a dict (no serial I/O)."""
        def read_fn(reg: int, count: int) -> list[int]:
            if reg in register_data:
                return [register_data[reg]]
            raise RuntimeError(f"No data for register 0x{reg:04X}")
        return read_fn

    @staticmethod
    def _uart_reader(**kwargs) -> ModbusReader:
        return ModbusReader(
            device_path="/dev/ttyAMA5",
            device_name="rover-test",
            serial_adapter="uart",
            slave_address=16,
            max_retries=1,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Transport routing
    # ------------------------------------------------------------------

    def test_uart_adapter_routes_to_raw_transport(self):
        """serial_adapter='uart' calls _read_sync_raw, not _read_sync_pymodbus."""
        reader = self._uart_reader()
        fake_result = {"__client": "ModbusReader/raw", "__serial_adapter": "uart"}

        with patch.object(reader, "_read_sync_raw", return_value=fake_result) as mock_raw, \
             patch.object(reader, "_read_sync_pymodbus") as mock_pymodbus:
            result = reader._read_sync()

        mock_raw.assert_called_once()
        mock_pymodbus.assert_not_called()
        assert result["__client"] == "ModbusReader/raw"

    def test_usb_adapter_routes_to_pymodbus(self):
        """serial_adapter='usb' calls _read_sync_pymodbus, not _read_sync_raw."""
        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            serial_adapter="usb",
            max_retries=1,
        )
        fake_result = {"__client": "ModbusReader/pymodbus", "__serial_adapter": "usb"}

        with patch.object(reader, "_read_sync_pymodbus", return_value=fake_result) as mock_pymodbus, \
             patch.object(reader, "_read_sync_raw") as mock_raw:
            result = reader._read_sync()

        mock_pymodbus.assert_called_once()
        mock_raw.assert_not_called()
        assert result["__client"] == "ModbusReader/pymodbus"

    # ------------------------------------------------------------------
    # Register parsing via _read_registers (no serial I/O)
    # ------------------------------------------------------------------

    def test_parses_battery_data(self):
        """_read_registers correctly parses battery SOC, voltage, and current."""
        import time
        reader = self._uart_reader()
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=0.0,
            client_label="ModbusReader/raw",
        )
        assert data["battery_percentage"] == 85
        assert data["battery_voltage"] == 13.2
        assert data["battery_current"] == 3.5

    def test_parses_temperature(self):
        """_read_registers correctly decodes the combined temperature register."""
        import time
        reader = self._uart_reader()
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=0.0,
            client_label="ModbusReader/raw",
        )
        assert data["controller_temperature"] == 25
        assert data["battery_temperature"] == 20

    def test_parses_solar_data(self):
        """_read_registers correctly parses PV voltage, current, and power."""
        import time
        reader = self._uart_reader()
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=0.0,
            client_label="ModbusReader/raw",
        )
        assert data["pv_voltage"] == 18.5
        assert data["pv_current"] == 2.8
        assert data["pv_power"] == 52

    def test_metadata_fields(self):
        """_read_registers stamps __client and __serial_adapter into the result."""
        import time
        reader = self._uart_reader()
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=1.5,
            client_label="ModbusReader/raw",
        )
        assert data["__client"] == "ModbusReader/raw"
        assert data["__serial_adapter"] == "uart"
        assert data["__device"] == "rover-test"

    def test_metadata_includes_pins_when_configured(self):
        """TX/RX GPIO pin numbers appear in metadata when set on the reader."""
        import time
        reader = self._uart_reader(uart_tx_pin=12, uart_rx_pin=13)
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=0.0,
            client_label="ModbusReader/raw",
        )
        assert data["__uart_tx_pin"] == 12
        assert data["__uart_rx_pin"] == 13

    def test_metadata_excludes_pins_when_not_set(self):
        """Pin metadata keys are absent when no pins are configured."""
        import time
        reader = self._uart_reader()
        data = reader._read_registers(
            read_fn=self._dict_read_fn(SAMPLE_MODBUS_DATA),
            start_time=time.perf_counter(),
            connect_elapsed_ms=0.0,
            client_label="ModbusReader/raw",
        )
        assert "__uart_tx_pin" not in data
        assert "__uart_rx_pin" not in data

    # ------------------------------------------------------------------
    # Serial port interaction
    # ------------------------------------------------------------------

    def test_serial_port_opened_with_correct_params(self):
        """_read_sync_raw opens serial.Serial with the expected parameters."""
        import time
        reader = self._uart_reader()
        fake_data = {"__client": "ModbusReader/raw", "__serial_adapter": "uart",
                     "battery_percentage": 85, "__device": "rover-test",
                     "__connect_ms": 0.0, "__total_ms": 0.0}

        port_mock = MagicMock()
        serial_cls = MagicMock(return_value=port_mock)

        with patch("pisolar.sensors.renogy.modbus_reader.serial.Serial", serial_cls), \
             patch.object(reader, "_read_registers", return_value=fake_data):
            reader._read_sync_raw()

        serial_cls.assert_called_once_with(
            port="/dev/ttyAMA5",
            baudrate=9600,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.001,
        )
        port_mock.close.assert_called_once()

    def test_serial_port_open_failure_raises(self):
        """RuntimeError wraps SerialException when the port cannot be opened."""
        import serial as pyserial
        reader = self._uart_reader()

        with patch(
            "pisolar.sensors.renogy.modbus_reader.serial.Serial",
            side_effect=pyserial.SerialException("Port not found"),
        ):
            with pytest.raises(RuntimeError, match="Failed to open"):
                reader._read_sync_raw()
