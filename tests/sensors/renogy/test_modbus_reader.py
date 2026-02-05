"""Tests for ModbusReader."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from pisolar.sensors.renogy.modbus_reader import (
    ModbusReader,
    _parse_temperature_register,
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

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_success(self, mock_client_class):
        """Test successful Modbus read."""
        mock_client = MagicMock()
        mock_client.connect.return_value = True

        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [100]

        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        assert "battery_percentage" in data
        assert data["battery_percentage"] == 100
        mock_client.connect.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_with_sample_data(self, mock_client_class):
        """Test reading with realistic sample data and verify all parsed values."""
        mock_client = self._create_mock_client(SAMPLE_MODBUS_DATA)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="wanderer",
            max_retries=1,
        )

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
        assert data["__client"] == "ModbusReader"

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_with_negative_temperatures(self, mock_client_class):
        """Test reading with negative temperatures (cold weather).

        Using sign+magnitude format per Renogy protocol:
        0x8A = -10°C (sign bit set + magnitude 10)
        """
        cold_weather_data = SAMPLE_MODBUS_DATA.copy()
        # 0x8A8A = controller=-10°C, battery=-10°C (sign+magnitude)
        cold_weather_data[0x0103] = 0x8A8A

        mock_client = self._create_mock_client(cold_weather_data)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        assert data["controller_temperature"] == -10
        assert data["battery_temperature"] == -10

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_user_reported_value(self, mock_client_class):
        """Test parsing the exact value the user reported (6400 = 0x1900)."""
        user_data = SAMPLE_MODBUS_DATA.copy()
        # User reported 6400 which is 0x1900 = controller=25°C, battery=0°C
        user_data[0x0103] = 6400  # 0x1900 in decimal

        mock_client = self._create_mock_client(user_data)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="wanderer",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        # 6400 = 0x1900: high byte=0x19=25, low byte=0x00=0
        assert data["controller_temperature"] == 25
        assert data["battery_temperature"] == 0

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_connection_failure(self, mock_client_class):
        """Test read fails when Modbus connection fails."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        with pytest.raises(RuntimeError, match="Failed to connect"):
            asyncio.run(reader.read())

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_min_values(self, mock_client_class):
        """Test reading with all minimum values (zeros)."""
        mock_client = self._create_mock_client(SAMPLE_MIN_VALUES)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

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

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_max_realistic_values(self, mock_client_class):
        """Test reading with maximum realistic operating values."""
        mock_client = self._create_mock_client(SAMPLE_MAX_VALUES)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

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

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_16bit_max_values(self, mock_client_class):
        """Test reading with 16-bit maximum values (0xFFFF = 65535).

        Verifies unsigned integer overflow handling for all voltage,
        current, and power fields.
        """
        mock_client = self._create_mock_client(SAMPLE_16BIT_MAX)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

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

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_extreme_cold_temperatures(self, mock_client_class):
        """Test reading with extreme cold temperatures (-127°C).

        Sign+magnitude format: 0xFF = 0x80 (sign) + 0x7F (127) = -127°C
        """
        mock_client = self._create_mock_client(SAMPLE_EXTREME_COLD)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        # Minimum possible temperatures
        assert data["controller_temperature"] == -127
        assert data["battery_temperature"] == -127

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_extreme_hot_temperatures(self, mock_client_class):
        """Test reading with extreme hot temperatures (+127°C)."""
        mock_client = self._create_mock_client(SAMPLE_EXTREME_HOT)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        # Maximum possible temperatures
        assert data["controller_temperature"] == 127
        assert data["battery_temperature"] == 127

    @patch("pymodbus.client.ModbusSerialClient")
    def test_read_mixed_extreme_temperatures(self, mock_client_class):
        """Test reading with mixed extreme temps (hot controller, cold battery)."""
        mock_client = self._create_mock_client(SAMPLE_MIXED_EXTREME_TEMPS)
        mock_client_class.return_value = mock_client

        reader = ModbusReader(
            device_path="/dev/ttyUSB0",
            device_name="test",
            max_retries=1,
        )

        data = asyncio.run(reader.read())

        # Controller at max positive, battery at max negative
        assert data["controller_temperature"] == 127
        assert data["battery_temperature"] == -127
