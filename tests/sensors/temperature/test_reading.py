"""Tests for TemperatureReading."""

from datetime import datetime, timezone

from pisolar.sensors.temperature import TemperatureReading
from tests.fixtures import TEMPERATURE_READINGS, TEMPERATURE_READINGS_COLD


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
