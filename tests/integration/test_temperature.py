"""Integration tests for the DS18B20 1-Wire temperature sensor.

Requires:
  - Real DS18B20 sensor wired to the Pi
  - ~/.config.yaml with temperature.enabled: true and at least one sensor entry
  - w1-gpio overlay loaded (dtoverlay=w1-gpio,gpiopin=<N> in /boot/config.txt)

Run with:
    poetry run pytest -m integration
"""

import pytest

from pisolar.sensors.temperature.temperature_sensor import TemperatureSensor


@pytest.mark.integration
class TestTemperatureSensorIntegration:
    """Live reads from DS18B20 sensors configured in ~/.config.yaml."""

    @pytest.fixture(autouse=True)
    def skip_if_disabled(self, integration_settings):
        if not integration_settings.temperature.enabled:
            pytest.skip("temperature.enabled is false in ~/.config.yaml")
        if not integration_settings.temperature.sensors:
            pytest.skip("No temperature sensors configured in ~/.config.yaml")

    @pytest.fixture
    def sensor(self, integration_settings):
        sensor_configs = [
            {"id": s.id, "address": s.address, "name": s.name}
            for s in integration_settings.temperature.sensors
        ]
        return TemperatureSensor(sensor_configs)

    def test_reads_at_least_one_sensor(self, sensor):
        readings = sensor.read()
        assert len(readings) > 0, "No temperature readings returned — check wiring and address in config"

    def test_reading_values_in_valid_range(self, sensor):
        """DS18B20 operating range: -55°C to +125°C."""
        readings = sensor.read()
        for r in readings:
            assert -55 <= r.value <= 125, f"Sensor {r.name}: value {r.value}°C out of DS18B20 range"

    def test_reading_unit_is_celsius(self, sensor):
        readings = sensor.read()
        for r in readings:
            assert r.unit == "celsius", f"Expected unit 'celsius', got '{r.unit}'"

    def test_reading_has_sensor_id(self, sensor, integration_settings):
        readings = sensor.read()
        configured_ids = {s.id for s in integration_settings.temperature.sensors}
        for r in readings:
            assert r.sensor_id in configured_ids, (
                f"Reading sensor_id {r.sensor_id} not in configured ids {configured_ids}"
            )

    def test_reading_name_matches_config(self, sensor, integration_settings):
        """reading.name should be the configured name (or address if name is None)."""
        readings = sensor.read()
        config_by_id = {s.id: s for s in integration_settings.temperature.sensors}
        for r in readings:
            cfg = config_by_id.get(r.sensor_id)
            if cfg and cfg.name:
                assert r.name == cfg.name, f"Expected name '{cfg.name}', got '{r.name}'"

    def test_all_configured_sensors_respond(self, sensor, integration_settings):
        """Warn (not fail) for each configured sensor that didn't return a reading."""
        readings = sensor.read()
        returned_ids = {r.sensor_id for r in readings}
        for s in integration_settings.temperature.sensors:
            assert s.id in returned_ids, (
                f"Sensor id={s.id} address={s.address} did not return a reading — "
                "check address and wiring"
            )

    def test_no_reset_value_85c(self, sensor):
        """85°C is the DS18B20 power-on reset value — indicates a wiring/power problem."""
        readings = sensor.read()
        for r in readings:
            assert r.value != 85.0, (
                f"Sensor {r.name} returned 85°C reset value — check VDD and pull-up resistor"
            )
