"""Tests for TemperatureSensorRecord ORM model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pisolar.services.db.temperature_sensor_model import TemperatureSensorRecord


class TestTemperatureSensorRecord:
    """Tests for TemperatureSensorRecord lookup table ORM model."""

    def test_table_name(self):
        assert TemperatureSensorRecord.__tablename__ == "solar_temperature_sensor"

    def test_insert_assigns_id(self, session):
        sensor = TemperatureSensorRecord(name="temp 1")
        session.add(sensor)
        session.commit()

        row = session.execute(select(TemperatureSensorRecord)).scalar_one()
        assert row.id is not None
        assert row.name == "temp 1"

    def test_multiple_sensors_get_distinct_ids(self, session):
        for i in range(1, 5):
            session.add(TemperatureSensorRecord(name=f"temp {i}"))
        session.commit()

        rows = session.execute(select(TemperatureSensorRecord)).scalars().all()
        ids = [r.id for r in rows]
        assert len(ids) == 4
        assert len(set(ids)) == 4

    def test_unique_name_constraint(self, session):
        session.add(TemperatureSensorRecord(name="temp 1"))
        session.commit()

        with pytest.raises(IntegrityError):
            session.add(TemperatureSensorRecord(name="temp 1"))
            session.commit()
