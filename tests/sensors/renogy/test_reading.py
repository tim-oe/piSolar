"""Tests for SolarReading."""

from pisolar.sensors.renogy import SolarReading
from tests.fixtures import RENOGY_RAW_DATA, RENOGY_RAW_DATA_CHARGING


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
        assert reading.battery_percentage == 100
        assert reading.battery_voltage == 13.2
        assert reading.pv_power == 0
        assert reading.charging_status == "deactivated"

    def test_from_raw_data_charging(self):
        """Test solar reading from raw Renogy data (charging)."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA_CHARGING,
        )

        assert reading.battery_percentage == 85
        assert reading.battery_voltage == 14.4
        assert reading.pv_power == 52
        assert reading.charging_status == "mppt"

    def test_to_dict_excludes_none(self):
        """Test that to_dict excludes None values."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="test",
            data={"battery_voltage": 12.5},
        )

        data = reading.to_dict()

        assert "battery_voltage" in data
        assert "pv_voltage" not in data

    def test_to_dict_full_data(self):
        """Test to_dict with full data set."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="test",
            data=RENOGY_RAW_DATA,
        )

        data = reading.to_dict()

        assert data["type"] == "solar"
        assert data["name"] == "test"
        assert data["model"] == "RNG-CTRL-RVR20"
        assert "read_time" in data

    def test_filters_internal_fields(self):
        """Test that internal fields are filtered out."""
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="test",
            data=RENOGY_RAW_DATA,
        )

        data = reading.to_dict()
        assert "__device" not in data
        assert "__client" not in data
        assert "function" not in data
