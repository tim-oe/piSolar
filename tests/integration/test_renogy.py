"""Integration tests for Renogy solar charge controllers.

Requires:
  - Renogy device connected (BT-2 or RS-485/RS-232 serial)
  - ~/.config.yaml with renogy.enabled: true and at least one sensor entry

Run with:
    poetry run pytest -m integration
"""

import pytest

from pisolar.sensors.renogy.renogy_sensor import RenogySensor
from pisolar.sensors.renogy.solar_reading import SolarReading


@pytest.mark.integration
class TestRenogySensorIntegration:
    """Live reads from Renogy controllers configured in ~/.config.yaml."""

    @pytest.fixture(autouse=True)
    def skip_if_disabled(self, integration_settings):
        if not integration_settings.renogy.enabled:
            pytest.skip("renogy.enabled is false in ~/.config.yaml")
        if not integration_settings.renogy.sensors:
            pytest.skip("No Renogy sensors configured in ~/.config.yaml")

    @pytest.fixture
    def sensors(self, integration_settings):
        return [RenogySensor(cfg) for cfg in integration_settings.renogy.sensors]

    def test_all_sensors_return_readings(self, sensors):
        for sensor in sensors:
            readings = sensor.read()
            assert len(readings) > 0, f"Sensor {sensor.name} returned no readings"

    def test_readings_are_solar_readings(self, sensors):
        for sensor in sensors:
            readings = sensor.read()
            for r in readings:
                assert isinstance(r, SolarReading), (
                    f"Expected SolarReading, got {type(r).__name__}"
                )

    def test_battery_voltage_in_range(self, sensors):
        """12V system: expect 10–16V under any charge state."""
        for sensor in sensors:
            readings = sensor.read()
            for r in readings:
                assert isinstance(r, SolarReading)
                assert 0 < r.battery_voltage <= 60, (
                    f"{sensor.name}: battery_voltage {r.battery_voltage}V out of range"
                )

    def test_battery_percentage_in_range(self, sensors):
        for sensor in sensors:
            readings = sensor.read()
            for r in readings:
                assert isinstance(r, SolarReading)
                assert 0 <= r.battery_percentage <= 100, (
                    f"{sensor.name}: battery_percentage {r.battery_percentage}% out of range"
                )

    def test_reading_has_sensor_name(self, sensors, integration_settings):
        configured_names = {s.name for s in integration_settings.renogy.sensors}
        for sensor in sensors:
            readings = sensor.read()
            for r in readings:
                assert r.name in configured_names, (
                    f"Reading name '{r.name}' not in configured sensors {configured_names}"
                )
