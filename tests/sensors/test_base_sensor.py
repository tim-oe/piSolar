"""Tests for BaseSensor abstract class."""

from pisolar.sensors import BaseSensor
from pisolar.sensors.renogy import SolarReading
from pisolar.sensors.temperature import TemperatureReading
from tests.fixtures import RENOGY_RAW_DATA


class TestBaseSensor:
    """Tests for BaseSensor abstract class."""

    def test_sensor_interface(self):
        """Test that BaseSensor defines the expected interface."""

        class DummySensor(BaseSensor):
            sensor_type = "dummy"

            def read(self):
                return []

        sensor = DummySensor()
        assert sensor.sensor_type == "dummy"
        assert sensor.read() == []

    def test_sensor_with_temperature_readings(self):
        """Test sensor that returns temperature readings."""

        class TempDummySensor(BaseSensor):
            sensor_type = "temperature"

            def read(self):
                return [
                    TemperatureReading(
                        type="temperature",
                        name="test",
                        value=22.5,
                        unit="C",
                    )
                ]

        sensor = TempDummySensor()
        readings = sensor.read()
        assert len(readings) == 1
        assert readings[0].value == 22.5

    def test_sensor_with_solar_reading(self):
        """Test sensor that returns solar reading."""

        class SolarDummySensor(BaseSensor):
            sensor_type = "solar"

            def read(self):
                return [
                    SolarReading.from_raw_data(
                        sensor_type="solar",
                        name="test",
                        data=RENOGY_RAW_DATA,
                    )
                ]

        sensor = SolarDummySensor()
        readings = sensor.read()
        assert len(readings) == 1
        assert readings[0].battery_voltage == 13.2
