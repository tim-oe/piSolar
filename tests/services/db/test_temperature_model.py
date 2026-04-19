"""Tests for TemperatureRecord ORM model."""

import pytest
from sqlalchemy import select

from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.db.temperature_model import TemperatureRecord
from pisolar.services.db.temperature_sensor_model import TemperatureSensorRecord


@pytest.fixture
def sensor_id(session):
    """Insert a temperature_sensor row so FK constraint is satisfied; return its id.

    Must commit so the row is visible to any subsequent sessions and InnoDB
    locks are released before the test inserts into temperature_reading.
    """
    sensor = TemperatureSensorRecord(name="sensor-1")
    session.add(sensor)
    session.commit()
    return sensor.id


class TestTemperatureRecord:
    """Tests for TemperatureRecord ORM model."""

    def test_table_name(self):
        assert TemperatureRecord.__tablename__ == "solar_temperature_reading"

    def test_from_reading_maps_value(self, session, sensor_id):
        reading = TemperatureReading(type="temperature", name="0000007b409e", sensor_id=sensor_id, value=22.5)
        session.add(TemperatureRecord.from_reading(reading, sensor_id))
        session.commit()

        row = session.execute(select(TemperatureRecord)).scalar_one()
        assert row.value == pytest.approx(22.5)

    def test_from_reading_maps_sensor_id(self, session, sensor_id):
        reading = TemperatureReading(type="temperature", name="0000007b409e", sensor_id=sensor_id, value=22.5)
        session.add(TemperatureRecord.from_reading(reading, sensor_id))
        session.commit()

        row = session.execute(select(TemperatureRecord)).scalar_one()
        assert row.sensor_id == sensor_id

    def test_from_reading_strips_timezone(self, sensor_id):
        reading = TemperatureReading(type="temperature", name="0000007b409e", sensor_id=sensor_id, value=22.5)
        record = TemperatureRecord.from_reading(reading, sensor_id)
        assert record.read_time.tzinfo is None

    def test_from_reading_negative_temperature(self, session, sensor_id):
        reading = TemperatureReading(type="temperature", name="0000007b409e", sensor_id=sensor_id, value=-5.2)
        session.add(TemperatureRecord.from_reading(reading, sensor_id))
        session.commit()

        row = session.execute(select(TemperatureRecord)).scalar_one()
        assert row.value == pytest.approx(-5.2)

    def test_from_reading_preserves_read_time(self, session, sensor_id):
        reading = TemperatureReading(type="temperature", name="0000007b409e", sensor_id=sensor_id, value=22.5)
        record = TemperatureRecord.from_reading(reading, sensor_id)
        expected = reading.read_time.replace(tzinfo=None)

        assert record.read_time == expected
