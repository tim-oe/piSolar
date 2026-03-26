"""SQLite consumer for persisting sensor readings as JSON."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.services.metrics_service import SENSOR_READING_EVENT

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_type TEXT NOT NULL,
    sensor_name TEXT NOT NULL,
    read_time TEXT NOT NULL,
    data JSON NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
)
"""

CREATE_INDEX_READ_TIME_SQL = """
CREATE INDEX IF NOT EXISTS idx_sensor_readings_read_time
ON sensor_readings (read_time)
"""

CREATE_INDEX_TYPE_SQL = """
CREATE INDEX IF NOT EXISTS idx_sensor_readings_type
ON sensor_readings (sensor_type)
"""

INSERT_SQL = """
INSERT INTO sensor_readings (sensor_type, sensor_name, read_time, data)
VALUES (?, ?, ?, ?)
"""

PRUNE_SQL = """
DELETE FROM sensor_readings WHERE read_time < ?
"""

COUNT_SQL = """
SELECT COUNT(*) FROM sensor_readings WHERE read_time < ?
"""


class SqliteConsumer:
    """Consumer that persists sensor readings to SQLite as JSON."""

    _logger = get_logger("services.sqlite")

    def __init__(self, db_path: str, retention_days: int = 90) -> None:
        self._db_path = db_path
        self._retention_days = retention_days
        self._ensure_db_directory()
        self._init_db()

        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._logger.info(
            "SQLite consumer initialized: db=%s, retention=%d days",
            self._db_path,
            self._retention_days,
        )

    def _ensure_db_directory(self) -> None:
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.execute(CREATE_INDEX_READ_TIME_SQL)
            conn.execute(CREATE_INDEX_TYPE_SQL)

    def _handle_reading(self, reading: SensorReading) -> None:
        data = reading.to_dict()
        read_time = data.get("read_time", datetime.now(timezone.utc).isoformat())
        data_json = json.dumps(data)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    INSERT_SQL,
                    (reading.type, reading.name, read_time, data_json),
                )
            self._logger.debug(
                "Stored reading: %s/%s at %s", reading.type, reading.name, read_time
            )
        except sqlite3.Error:
            self._logger.exception(
                "Failed to store reading for %s/%s", reading.type, reading.name
            )

    def prune(self, retention_days: int | None = None) -> int:
        """Delete readings older than retention_days.

        Args:
            retention_days: Override the configured retention period.
                            Uses the instance default when not supplied.

        Returns:
            Number of rows deleted.
        """
        days = retention_days if retention_days is not None else self._retention_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(COUNT_SQL, (cutoff,))
                count = cursor.fetchone()[0]

                if count > 0:
                    conn.execute(PRUNE_SQL, (cutoff,))
                    self._logger.info(
                        "Pruned %d readings older than %d days (cutoff: %s)",
                        count,
                        days,
                        cutoff,
                    )
                else:
                    self._logger.debug("No readings to prune (cutoff: %s)", cutoff)

                return count
        except sqlite3.Error:
            self._logger.exception("Failed to prune readings")
            return 0

    def close(self) -> None:
        """Unsubscribe from the event bus."""
        self._event_bus.unsubscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._logger.info("SQLite consumer closed")
