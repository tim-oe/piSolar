"""Tests for TemperatureSensor."""

from unittest.mock import MagicMock, patch

from pisolar.sensors.temperature import TemperatureSensor
from tests.fixtures import TEMPERATURE_SENSORS


class TestTemperatureSensor:
    """Tests for TemperatureSensor with mocked 1-Wire interface."""

    def test_sensor_type(self):
        """Test sensor type is 'temperature'."""
        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS)
        assert sensor.sensor_type == "temperature"

    @patch("pisolar.sensors.temperature.sensor.W1ThermSensor")
    def test_read_sensors(self, mock_w1_class):
        """Test reading from temperature sensors."""
        # Mock sensor instances
        mock_sensor1 = MagicMock()
        mock_sensor1.id = "0000007c6850"
        mock_sensor1.get_temperature.return_value = 22.5

        mock_sensor2 = MagicMock()
        mock_sensor2.id = "000000b4c0d2"
        mock_sensor2.get_temperature.return_value = 23.1

        mock_w1_class.get_available_sensors.return_value = [mock_sensor1, mock_sensor2]

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:2])
        readings = sensor.read()

        assert len(readings) == 2
        assert readings[0].name == "temp 1"
        assert readings[0].value == 22.5

    @patch("pisolar.sensors.temperature.sensor.W1ThermSensor")
    def test_read_sensor_not_available(self, mock_w1_class):
        """Test handling when sensor is not found."""
        mock_w1_class.get_available_sensors.return_value = []
        mock_w1_class.side_effect = Exception("Sensor not found")

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:1])
        readings = sensor.read()

        # Should return empty list, not raise
        assert len(readings) == 0

    @patch("pisolar.sensors.temperature.sensor.W1ThermSensor")
    def test_read_reset_value_error(self, mock_w1_class):
        """Test handling when sensor returns reset value (85°C power issue)."""
        from w1thermsensor.errors import ResetValueError

        mock_sensor = MagicMock()
        mock_sensor.id = "0000007c6850"
        mock_sensor.get_temperature.side_effect = ResetValueError("0000007c6850")

        mock_w1_class.get_available_sensors.return_value = [mock_sensor]

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:1])
        readings = sensor.read()

        # Should return empty list, not raise
        assert len(readings) == 0

    @patch("pisolar.sensors.temperature.sensor.W1ThermSensor")
    def test_read_mixed_available(self, mock_w1_class):
        """Test reading when some sensors available, some not."""
        mock_sensor = MagicMock()
        mock_sensor.id = "0000007c6850"
        mock_sensor.get_temperature.return_value = 22.5

        mock_w1_class.get_available_sensors.return_value = [mock_sensor]
        mock_w1_class.side_effect = Exception("Not found")

        sensor = TemperatureSensor(sensors=TEMPERATURE_SENSORS[:2])
        readings = sensor.read()

        # Should only return the available sensor
        assert len(readings) == 1
        assert readings[0].name == "temp 1"
