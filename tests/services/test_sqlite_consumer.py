"""Tests for SqliteConsumer."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pisolar.event_bus import EventBus
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.metrics_service import SENSOR_READING_EVENT
from pisolar.services.sqlite_consumer import SqliteConsumer
from tests.fixtures import RENOGY_RAW_DATA


class TestSqliteConsumer:
    """Tests for SqliteConsumer."""

    def test_create_consumer_subscribes_to_events(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            SqliteConsumer(db_path=db_path)

            mock_bus.subscribe.assert_called_once()
            call_args = mock_bus.subscribe.call_args
            assert call_args[0][0] == SENSOR_READING_EVENT

    def test_creates_database_and_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            SqliteConsumer(db_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_parent_directories(self, tmp_path):
        db_path = str(tmp_path / "nested" / "dir" / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            SqliteConsumer(db_path=db_path)

        assert (tmp_path / "nested" / "dir").is_dir()

    def test_handle_temperature_reading(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path)

        reading = TemperatureReading(
            type="temperature",
            name="temp 1",
            value=22.5,
        )
        consumer._handle_reading(reading)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT sensor_type, sensor_name, data FROM sensor_readings"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "temperature"
        assert row[1] == "temp 1"

        data = json.loads(row[2])
        assert data["value"] == 22.5
        assert data["type"] == "temperature"
        assert data["name"] == "temp 1"

    def test_handle_solar_reading(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path)

        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA,
        )
        consumer._handle_reading(reading)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT sensor_type, sensor_name, data FROM sensor_readings"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "solar"
        assert row[1] == "BT-TH-A5ABF10E"

        data = json.loads(row[2])
        assert data["battery_percentage"] == 100
        assert data["battery_voltage"] == 13.2

    def test_stores_read_time(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path)

        reading = TemperatureReading(
            type="temperature",
            name="temp 1",
            value=22.5,
        )
        consumer._handle_reading(reading)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT read_time FROM sensor_readings")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        read_time = datetime.fromisoformat(row[0])
        assert read_time.date() == datetime.now(timezone.utc).date()

    def test_multiple_readings_stored(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path)

        for i in range(5):
            reading = TemperatureReading(
                type="temperature",
                name=f"temp {i}",
                value=20.0 + i,
            )
            consumer._handle_reading(reading)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5

    def test_prune_removes_old_readings(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path, retention_days=30)

        conn = sqlite3.connect(db_path)
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        recent_time = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT INTO sensor_readings (sensor_type, sensor_name, read_time, data) VALUES (?, ?, ?, ?)",
            ("temperature", "temp 1", old_time, '{"value": 22.5}'),
        )
        conn.execute(
            "INSERT INTO sensor_readings (sensor_type, sensor_name, read_time, data) VALUES (?, ?, ?, ?)",
            ("temperature", "temp 2", recent_time, '{"value": 23.0}'),
        )
        conn.commit()
        conn.close()

        deleted = consumer.prune()

        assert deleted == 1

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM sensor_readings")
        remaining = cursor.fetchone()[0]
        conn.close()

        assert remaining == 1

    def test_prune_with_override_days(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path, retention_days=365)

        conn = sqlite3.connect(db_path)
        age_10_days = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        conn.execute(
            "INSERT INTO sensor_readings (sensor_type, sensor_name, read_time, data) VALUES (?, ?, ?, ?)",
            ("temperature", "temp 1", age_10_days, '{"value": 22.5}'),
        )
        conn.commit()
        conn.close()

        deleted = consumer.prune(retention_days=5)
        assert deleted == 1

    def test_prune_no_old_data_returns_zero(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_get_bus.return_value = MagicMock(spec=EventBus)
            consumer = SqliteConsumer(db_path=db_path, retention_days=30)

        reading = TemperatureReading(
            type="temperature",
            name="temp 1",
            value=22.5,
        )
        consumer._handle_reading(reading)

        deleted = consumer.prune()
        assert deleted == 0

    def test_close_unsubscribes(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        with patch("pisolar.services.sqlite_consumer.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus
            consumer = SqliteConsumer(db_path=db_path)

        consumer.close()

        mock_bus.unsubscribe.assert_called_once_with(
            SENSOR_READING_EVENT, consumer._handle_reading
        )
