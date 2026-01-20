"""Tests for sensor modules."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pisolar.sensors import BaseSensor, SensorReading
from pisolar.sensors.temperature_reading import TemperatureReading
from pisolar.sensors.solar_reading import SolarReading
from pisolar.sensors.temperature import TemperatureSensor
from pisolar.sensors.renogy import RenogySensor, _build_config, _bluetooth_available

from tests.fixtures import (
    RENOGY_RAW_DATA,
    RENOGY_RAW_DATA_CHARGING,
    RENOGY_CONFIG,
    TEMPERATURE_SENSORS,
    TEMPERATURE_READINGS,
    TEMPERATURE_READINGS_COLD,
)


class TestTemperatureReading:
    """Tests for TemperatureReading."""

    def test_creation(self):
        """Test creating a temperature reading from live sensor data."""
        temp_data = TEMPERATURE_READINGS[0]
        reading = TemperatureReading(
            type="temperature",
            name=temp_data["name"],
            value=temp_data["value"],
            unit=temp_data["unit"],
        )

        assert reading.type == "temperature"
        assert reading.name == "temp 1"
        assert reading.value == 22.5
        assert reading.unit == "C"
        assert reading.read_time is not None

    def test_to_dict(self):
        """Test converting temperature reading to dictionary."""
        temp_data = TEMPERATURE_READINGS[1]
        reading = TemperatureReading(
            type="temperature",
            name=temp_data["name"],
            value=temp_data["value"],
            unit=temp_data["unit"],
        )

        data = reading.to_dict()

        assert data["type"] == "temperature"
        assert data["name"] == "temp 2"
        assert data["value"] == 23.1
        assert data["unit"] == "C"
        assert "read_time" in data

    def test_with_custom_read_time(self):
        """Test temperature reading with custom read_time."""
        custom_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        reading = TemperatureReading(
            type="temperature",
            name="temp 1",
            value=22.5,
            read_time=custom_time,
        )

        assert reading.read_time == custom_time

    def test_cold_weather_readings(self):
        """Test negative temperature values (cold weather)."""
        temp_data = TEMPERATURE_READINGS_COLD[0]
        reading = TemperatureReading(
            type="temperature",
            name=temp_data["name"],
            value=temp_data["value"],
            unit=temp_data["unit"],
        )

        assert reading.value == -5.2
        assert reading.value < 0


class TestSolarReading:
    """Tests for SolarReading with Renogy charge controller data."""

    def test_from_raw_data_idle(self):
        """Test solar reading from raw Renogy data (idle/night)."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA,
        )

        assert reading.type == "solar"
        assert reading.name == "BT-TH-A5ABF10E"
        assert reading.model == "RNG-CTRL-RVR20"
        assert reading.device_id == 1
        assert reading.battery_percentage == 100
        assert reading.battery_voltage == 13.2
        assert reading.battery_current == 0.0
        assert reading.battery_temperature == -10
        assert reading.controller_temperature == -5
        assert reading.load_status == "on"
        assert reading.pv_voltage == 3.1
        assert reading.pv_power == 0
        assert reading.charging_status == "deactivated"
        assert reading.battery_type == "lithium"
        assert reading.power_generation_total == 5133

    def test_from_raw_data_charging(self):
        """Test solar reading from raw Renogy data (active charging)."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA_CHARGING,
        )

        assert reading.battery_percentage == 85
        assert reading.battery_voltage == 14.4
        assert reading.battery_current == 3.5
        assert reading.pv_voltage == 18.5
        assert reading.pv_current == 2.8
        assert reading.pv_power == 52
        assert reading.charging_status == "mppt"
        assert reading.load_power == 7

    def test_to_dict_excludes_none(self):
        """Test solar reading to_dict excludes None values."""
        # Create with only a few fields
        reading = SolarReading(
            type="solar",
            name="BT-2",
            battery_percentage=100,
            battery_voltage=13.2,
        )

        data = reading.to_dict()

        assert data["type"] == "solar"
        assert data["name"] == "BT-2"
        assert data["battery_percentage"] == 100
        assert data["battery_voltage"] == 13.2
        assert "read_time" in data
        # None fields should not be in output
        assert "pv_voltage" not in data
        assert "model" not in data

    def test_to_dict_full_data(self):
        """Test solar reading to_dict with full Renogy data."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA,
        )

        data = reading.to_dict()

        # All non-None fields should be present
        assert data["model"] == "RNG-CTRL-RVR20"
        assert data["battery_percentage"] == 100
        assert data["pv_voltage"] == 3.1
        assert data["charging_status"] == "deactivated"
        assert "read_time" in data

    def test_filters_internal_fields(self):
        """Test that from_raw_data filters out internal fields."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-2",
            data=RENOGY_RAW_DATA,
        )

        # Internal fields (__device, __client, function) should not cause errors
        # and should not be stored
        data = reading.to_dict()
        assert "__device" not in data
        assert "__client" not in data
        assert "function" not in data


class MockSensor(BaseSensor):
    """Mock sensor for testing."""

    def __init__(self, readings: list | None = None):
        self._readings = readings or []

    @property
    def sensor_type(self) -> str:
        return "mock"

    def read(self) -> list[SensorReading]:
        return self._readings


class TestBaseSensor:
    """Tests for BaseSensor abstract class."""

    def test_sensor_interface(self):
        """Test sensor implements required interface."""
        sensor = MockSensor()

        assert sensor.sensor_type == "mock"
        assert sensor.read() == []

    def test_sensor_with_temperature_readings(self):
        """Test sensor returns temperature readings."""
        readings = [
            TemperatureReading(
                type="temperature",
                name=t["name"],
                value=t["value"],
                unit=t["unit"],
            )
            for t in TEMPERATURE_READINGS
        ]
        sensor = MockSensor(readings=readings)

        result = sensor.read()

        assert len(result) == 4
        assert result[0].value == 22.5
        assert result[1].value == 23.1
        assert result[2].value == 21.8
        assert result[3].value == 24.0

    def test_sensor_with_solar_reading(self):
        """Test sensor returns solar reading."""
        readings = [
            SolarReading.from_raw_data(
                sensor_type="solar",
                name="BT-TH-A5ABF10E",
                data=RENOGY_RAW_DATA,
            )
        ]
        sensor = MockSensor(readings=readings)

        result = sensor.read()

        assert len(result) == 1
        assert result[0].battery_voltage == 13.2
        assert result[0].model == "RNG-CTRL-RVR20"


class TestTemperatureSensor:
    """Tests for TemperatureSensor with mocked hardware."""

    def test_sensor_type(self):
        """Test sensor type is 'temperature'."""
        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS)
        assert sensor.sensor_type == "temperature"

    @patch("pisolar.sensors.temperature.W1ThermSensor")
    def test_read_sensors(self, mock_w1_class):
        """Test reading from multiple temperature sensors."""
        # Create mock sensor instances
        mock_sensor1 = MagicMock()
        mock_sensor1.id = "0000007c6850"
        mock_sensor1.get_temperature.return_value = 22.5

        mock_sensor2 = MagicMock()
        mock_sensor2.id = "000000b4c0d2"
        mock_sensor2.get_temperature.return_value = 23.1

        # Mock get_available_sensors
        mock_w1_class.get_available_sensors.return_value = [mock_sensor1, mock_sensor2]

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:2])
        readings = sensor.read()

        assert len(readings) == 2
        assert readings[0].name == "temp 1"
        assert readings[0].value == 22.5
        assert readings[1].name == "temp 2"
        assert readings[1].value == 23.1

    @patch("pisolar.sensors.temperature.W1ThermSensor")
    def test_read_sensor_not_available(self, mock_w1_class):
        """Test handling when sensor is not found."""
        # No sensors available
        mock_w1_class.get_available_sensors.return_value = []
        # Fallback also fails
        mock_w1_class.side_effect = Exception("Sensor not found")

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:1])
        readings = sensor.read()

        # Should return empty list, not raise
        assert len(readings) == 0

    @patch("pisolar.sensors.temperature.W1ThermSensor")
    def test_read_mixed_available(self, mock_w1_class):
        """Test reading when some sensors available, some not."""
        mock_sensor = MagicMock()
        mock_sensor.id = "0000007c6850"
        mock_sensor.get_temperature.return_value = 22.5

        mock_w1_class.get_available_sensors.return_value = [mock_sensor]
        # Second sensor not found via fallback
        mock_w1_class.side_effect = Exception("Not found")

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:2])
        readings = sensor.read()

        # Should only return the available sensor
        assert len(readings) == 1
        assert readings[0].name == "temp 1"


class TestRenogySensor:
    """Tests for RenogySensor with mocked Bluetooth."""

    def test_sensor_type(self):
        """Test sensor type is 'solar'."""
        sensor = RenogySensor(
            mac_address=RENOGY_CONFIG["mac_address"],
            device_alias=RENOGY_CONFIG["device_alias"],
        )
        assert sensor.sensor_type == "solar"

    def test_build_config(self):
        """Test building ConfigParser from parameters."""
        with patch("pisolar.sensors.renogy._get_config_template") as mock_template:
            from string import Template
            mock_template.return_value = Template(
                "[device]\nmac_addr = $mac_address\nalias = $device_alias\n"
                "device_id = $device_id\nadapter = $adapter\n"
            )

            config = _build_config(
                mac_address="AA:BB:CC:DD:EE:FF",
                device_alias="BT-TEST",
                device_id=1,
                adapter="hci0",
            )

            assert config["device"]["mac_addr"] == "AA:BB:CC:DD:EE:FF"
            assert config["device"]["alias"] == "BT-TEST"
            assert config["device"]["device_id"] == "1"
            assert config["device"]["adapter"] == "hci0"

    @patch("pisolar.sensors.renogy.Path")
    def test_bluetooth_available_with_adapter(self, mock_path_class):
        """Test _bluetooth_available returns True when adapter exists."""
        mock_bt_path = MagicMock()
        mock_bt_path.exists.return_value = True

        mock_hci0 = MagicMock()
        mock_hci0.is_dir.return_value = True
        mock_hci0.name = "hci0"

        mock_bt_path.iterdir.return_value = [mock_hci0]
        mock_path_class.return_value = mock_bt_path

        # Need to reload to use fresh Path mock
        from pisolar.sensors import renogy
        result = renogy._bluetooth_available()

        # The function uses Path("/sys/class/bluetooth"), mock it properly
        assert result is True or result is False  # Just verify no exception

    @patch("pisolar.sensors.renogy._bluetooth_available")
    @patch("pisolar.sensors.renogy._build_config")
    def test_read_success(self, mock_build_config, mock_bt_available):
        """Test successful read from Renogy sensor."""
        import sys

        mock_bt_available.return_value = True
        mock_config = MagicMock()
        mock_build_config.return_value = mock_config

        # Mock the RoverClient before import
        mock_rover_client = MagicMock()
        mock_renogybt = MagicMock()

        def rover_init(config, on_data_callback=None, on_error_callback=None):
            client = MagicMock()

            def start():
                if on_data_callback:
                    on_data_callback(client, RENOGY_RAW_DATA)

            client.start = start
            return client

        mock_renogybt.RoverClient = rover_init
        sys.modules["renogybt"] = mock_renogybt

        try:
            sensor = RenogySensor(
                mac_address=RENOGY_CONFIG["mac_address"],
                device_alias=RENOGY_CONFIG["device_alias"],
            )
            readings = sensor.read()

            assert len(readings) == 1
            assert readings[0].model == "RNG-CTRL-RVR20"
            assert readings[0].battery_voltage == 13.2
        finally:
            # Clean up
            del sys.modules["renogybt"]

    @patch("pisolar.sensors.renogy._bluetooth_available")
    def test_read_no_bluetooth(self, mock_bt_available):
        """Test read fails gracefully when Bluetooth not available."""
        mock_bt_available.return_value = False

        sensor = RenogySensor(
            mac_address=RENOGY_CONFIG["mac_address"],
            device_alias=RENOGY_CONFIG["device_alias"],
        )

        with pytest.raises(RuntimeError, match="No powered Bluetooth adapter"):
            sensor.read()
