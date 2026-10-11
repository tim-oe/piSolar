"""Tests for spool record codec."""

import pytest

from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.db.solar_model import SolarRecord
from pisolar.services.db.temperature_model import TemperatureRecord
from pisolar.services.spool.record_codec import RecordCodec, decode_value
from tests.fixtures import RENOGY_RAW_DATA


class TestRecordCodec:
    def test_solar_record_round_trip(self):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        original = SolarRecord.from_reading(reading)
        encoded = RecordCodec.encode(original)
        assert "id" not in encoded
        restored = RecordCodec.decode(SolarRecord, encoded)
        for column in SolarRecord.__table__.columns:
            if column.name == "id":
                continue
            assert getattr(restored, column.name) == getattr(
                original, column.name
            )

    def test_temperature_record_round_trip(self):
        reading = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=2, value=19.5
        )
        original = TemperatureRecord.from_reading(reading, reading.sensor_id)
        encoded = RecordCodec.encode(original)
        restored = RecordCodec.decode(TemperatureRecord, encoded)
        assert restored.sensor_id == 2
        assert restored.value == pytest.approx(19.5)
        assert restored.read_time == original.read_time

    def test_datetime_rejects_offset(self):
        column = SolarRecord.__table__.columns.read_time
        with pytest.raises(ValueError):
            decode_value(column.type, "2026-03-04T05:06:07+00:00")
        with pytest.raises(ValueError):
            decode_value(column.type, "2026-03-04T05:06:07-05:00")
