"""Tests for SolarRecord ORM model."""

import pytest
from sqlalchemy import select

from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.services.db.solar_model import SolarRecord
from tests.fixtures import RENOGY_RAW_DATA, RENOGY_RAW_DATA_CHARGING


class TestSolarRecord:
    """Tests for SolarRecord ORM model."""

    def test_table_name(self):
        assert SolarRecord.__tablename__ == "solar_reading"

    def test_from_reading_maps_sensor_name(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.sensor_name == "rover-40"

    def test_from_reading_maps_battery_fields(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.battery_percentage == 100
        assert row.battery_voltage == pytest.approx(13.2)
        assert row.battery_current == pytest.approx(0.0)
        assert row.battery_temperature == -10
        assert row.battery_type == "lithium"

    def test_from_reading_maps_controller_fields(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.controller_temperature == -5
        assert row.charging_status == "deactivated"

    def test_from_reading_maps_load_fields(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.load_status == "on"
        assert row.load_voltage == pytest.approx(13.2)
        assert row.load_current == pytest.approx(0.0)
        assert row.load_power == 0

    def test_from_reading_maps_pv_fields(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.pv_voltage == pytest.approx(3.1)
        assert row.pv_current == pytest.approx(0.0)
        assert row.pv_power == 0

    def test_from_reading_maps_daily_stats(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.max_charging_power_today == 55
        assert row.charging_amp_hours_today == 5
        assert row.power_generation_today == pytest.approx(71)
        assert row.power_generation_total == 5133

    def test_from_reading_strips_timezone(self):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        record = SolarRecord.from_reading(reading)
        assert record.read_time.tzinfo is None

    def test_from_reading_null_optional_fields(self, session):
        reading = SolarReading(type="solar", name="rover-40")
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.model is None
        assert row.battery_percentage is None
        assert row.pv_voltage is None
        assert row.power_generation_total is None

    def test_from_reading_charging_data(self, session):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA_CHARGING
        )
        session.add(SolarRecord.from_reading(reading))
        session.commit()

        row = session.execute(select(SolarRecord)).scalar_one()
        assert row.battery_current == pytest.approx(3.5)
        assert row.pv_power == 52
        assert row.charging_status == "mppt"
        assert row.battery_temperature == 25
        assert row.controller_temperature == 35
