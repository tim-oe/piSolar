"""MySQL consumer that persists solar and temperature sensor readings."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy import text
from sqlalchemy.orm import Session

from pisolar.config.mysql_config import MySQLConfig
from pisolar.config.spool_config import SpoolConfig
from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.db.base import Base, create_db_engine
from pisolar.services.db.connection import is_connection_error
from pisolar.services.db.db_state import DbState
from pisolar.services.db.solar_model import SolarRecord
from pisolar.services.db.temperature_model import TemperatureRecord
from pisolar.services.metrics_service import SENSOR_READING_EVENT
from pisolar.services.spool.record_codec import RecordCodec
from pisolar.services.spool.spool_store import SpoolStore


class MySQLConsumer:
    """Consumer that persists sensor readings to a MySQL database.

    Subscribes to the :data:`~pisolar.services.metrics_service.SENSOR_READING_EVENT`
    event bus topic and writes one row per reading to the appropriate table:

    - :class:`~pisolar.sensors.renogy.solar_reading.SolarReading` → ``solar_reading``
    - :class:`~pisolar.sensors.temperature.temperature_reading.TemperatureReading`
      → ``solar_temperature_reading``

    Schema management is handled externally (pyway).  This class does **not**
    call ``create_all()``; the tables must already exist before the service starts.

    Temperature sensor IDs are sourced directly from config and stored in
    :attr:`~pisolar.sensors.temperature.temperature_reading.TemperatureReading.sensor_id`.
    The ``temperature_sensor`` lookup table is managed by pyway migrations.
    """

    _logger = get_logger("services.mysql")

    def __init__(
        self,
        config: MySQLConfig,
        spool: SpoolConfig | None = None,
    ) -> None:
        spool_config = spool or SpoolConfig(enabled=False)
        self._spool_config = spool_config
        self._engine = create_db_engine(
            url=config.url,
            pool_size=config.pool_size,
            pool_recycle=config.pool_recycle,
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            write_timeout=config.write_timeout,
        )
        self._db_state = DbState(config.offline_retry_seconds)
        self._spool = SpoolStore(spool_config) if spool_config.enabled else None
        self._flush_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mysql-flush"
        )
        self._flush_lock = Lock()

        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._logger.info("MySQL consumer initialized: url=%s", config.masked_url)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_reading(self, reading: SensorReading) -> None:
        record = self._to_record(reading)
        if record is None:
            return
        self._persist(record)

    def _to_record(self, reading: SensorReading):
        if isinstance(reading, SolarReading):
            return SolarRecord.from_reading(reading)
        if isinstance(reading, TemperatureReading):
            return TemperatureRecord.from_reading(reading, reading.sensor_id)
        self._logger.warning(
            "Unhandled reading type %s for %s/%s — skipping",
            type(reading).__name__,
            reading.type,
            reading.name,
        )
        return None

    def _persist(self, record) -> None:
        if self._spool and self._db_state.is_offline():
            self._spool_row(record)
            return
        try:
            with Session(self._engine) as session:
                session.add(record)
                session.commit()
        except Exception as exc:
            if self._spool and is_connection_error(exc):
                if self._db_state.mark_offline():
                    self._logger.warning(
                        "database unavailable, spooling writes: %s", exc
                    )
                self._spool_row(record)
                return
            self._logger.exception("Failed to persist %s row", type(record).__name__)
            return

        if self._db_state.mark_online():
            self._submit_flush()
        self._logger.debug("Persisted %s row", type(record).__name__)

    def _spool_row(self, record) -> None:
        if not self._spool:
            return
        table = type(record).__tablename__
        envelope = {
            "table": table,
            "spooled_at": datetime.now(timezone.utc).isoformat(),
            "data": RecordCodec.encode(record),
        }
        self._spool.append(table, json.dumps(envelope, separators=(",", ":")))

    def _submit_flush(self) -> None:
        self._flush_executor.submit(self.flush)

    # ------------------------------------------------------------------
    # Spool replay
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Replay spooled rows to MySQL when the database is reachable."""
        if not self._spool:
            return
        if not self._flush_lock.acquire(blocking=False):
            self._logger.info("mysql flush already running")
            return
        try:
            self._drain_spool()
        finally:
            self._flush_lock.release()

    def _drain_spool(self) -> None:
        if not self._health_check():
            return
        self._db_state.mark_online()

        totals: dict[str, dict[str, int]] = {}
        for table in self._spool.tables():
            replayed, rejected, failed = self._drain_table(table)
            totals[table] = {
                "replayed": replayed,
                "rejected": rejected,
                "failed": int(failed),
            }
            if failed:
                break

        for table, counts in totals.items():
            remaining = self._spool.depth(table)
            self._logger.info(
                "mysql flush table=%s replayed=%s rejected=%s failed=%s remaining=%s",
                table,
                counts["replayed"],
                counts["rejected"],
                counts["failed"],
                remaining,
            )
        self._spool.reset_alerts_if_empty()

    def _drain_table(self, table: str) -> tuple[int, int, bool]:
        model = self._model_for_table(table)
        if model is None:
            self._quarantine_unknown_table(table)
            return 0, 0, False

        replayed = 0
        rejected = 0
        while True:
            path = self._spool.claim_oldest(table)
            if path is None:
                return replayed, rejected, False
            lines = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            entries: list[tuple[str, object]] = []
            for line in lines:
                try:
                    envelope = json.loads(line)
                except json.JSONDecodeError:
                    self._spool.quarantine(table, line, "invalid json")
                    rejected += 1
                    continue
                if not isinstance(envelope, dict):
                    self._spool.quarantine(table, line, "envelope must be an object")
                    rejected += 1
                    continue
                if envelope.get("table") != table:
                    self._spool.quarantine(table, line, "table mismatch")
                    rejected += 1
                    continue
                data = envelope.get("data")
                if not isinstance(data, dict):
                    self._spool.quarantine(table, line, "data must be an object")
                    rejected += 1
                    continue
                try:
                    entries.append((line, RecordCodec.decode(model, data)))
                except (ValueError, TypeError, KeyError) as exc:
                    self._spool.quarantine(table, line, str(exc))
                    rejected += 1

            if not entries:
                self._spool.complete(path)
                continue

            if len(entries) != len(lines):
                self._spool.rewrite_remainder(path, [line for line, _record in entries])

            try:
                with Session(self._engine) as session:
                    session.add_all(record for _line, record in entries)
                    session.commit()
            except Exception as exc:
                if is_connection_error(exc):
                    if self._db_state.mark_offline():
                        self._logger.warning(
                            "mysql flush stopped; database unavailable: %s", exc
                        )
                    return replayed, rejected, True
                self._logger.warning(
                    "mysql flush batch failed for table %s; retrying rows "
                    "individually: %s",
                    table,
                    exc,
                )
                row_replayed, row_rejected, failed = self._replay_individually(
                    table, entries
                )
                replayed += row_replayed
                rejected += row_rejected
                if failed:
                    return replayed, rejected, True
                self._spool.complete(path)
                continue

            replayed += len(entries)
            self._spool.complete(path)

    def _replay_individually(
        self, table: str, entries: list[tuple[str, object]]
    ) -> tuple[int, int, bool]:
        replayed = 0
        rejected = 0
        for line, record in entries:
            try:
                with Session(self._engine) as session:
                    session.add(record)
                    session.commit()
            except Exception as exc:
                if is_connection_error(exc):
                    if self._db_state.mark_offline():
                        self._logger.warning(
                            "mysql flush stopped; database unavailable: %s", exc
                        )
                    return replayed, rejected, True
                self._spool.quarantine(table, line, str(exc))
                rejected += 1
                continue
            replayed += 1
        return replayed, rejected, False

    def _quarantine_unknown_table(self, table: str) -> None:
        directory = self._spool.folder / table
        if not directory.is_dir():
            return
        for path in sorted(directory.iterdir()):
            if path.name == "rejected.jsonl":
                continue
            if path.suffix == ".jsonl" or path.name.endswith(".jsonl.draining"):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        self._spool.quarantine(
                            table, line, "unknown table for ORM registry"
                        )
                path.unlink(missing_ok=True)

    @staticmethod
    def _model_for_table(table: str):
        for mapper in Base.registry.mappers:
            if mapper.class_.__tablename__ == table:
                return mapper.class_
        return None

    def _health_check(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Unsubscribe from the event bus and dispose the connection pool."""
        self._event_bus.unsubscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._flush_executor.shutdown(wait=True)
        self._engine.dispose()
        self._logger.info("MySQL consumer closed")
