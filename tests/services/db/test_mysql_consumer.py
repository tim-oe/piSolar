"""Tests for MySQLConsumer."""

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from pisolar.config.mysql_config import MySQLConfig
from pisolar.config.spool_config import SpoolConfig
from pisolar.event_bus import EventBus
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.db.mysql_consumer import MySQLConsumer
from pisolar.services.db.solar_model import SolarRecord
from pisolar.services.db.temperature_model import TemperatureRecord
from pisolar.services.db.temperature_sensor_model import TemperatureSensorRecord
from pisolar.services.metrics_service import SENSOR_READING_EVENT
from tests.fixtures import RENOGY_RAW_DATA, RENOGY_RAW_DATA_CHARGING


class UnknownReading(SensorReading):
    """Concrete SensorReading subclass not handled by the consumer."""

    def to_dict(self):
        return {}


@pytest.fixture
def mock_bus():
    return MagicMock(spec=EventBus)


@pytest.fixture
def spool_config(tmp_path):
    return SpoolConfig(enabled=True, folder=str(tmp_path / "spool"))


@pytest.fixture
def consumer(engine, mock_bus):
    with (
        patch("pisolar.services.db.mysql_consumer.get_event_bus") as mock_get_bus,
        patch(
            "pisolar.services.db.mysql_consumer.create_db_engine"
        ) as mock_create_engine,
    ):
        mock_get_bus.return_value = mock_bus
        mock_create_engine.return_value = engine
        yield MySQLConsumer(MySQLConfig())


@pytest.fixture
def consumer_with_spool(engine, mock_bus, spool_config):
    with (
        patch("pisolar.services.db.mysql_consumer.get_event_bus") as mock_get_bus,
        patch(
            "pisolar.services.db.mysql_consumer.create_db_engine"
        ) as mock_create_engine,
    ):
        mock_get_bus.return_value = mock_bus
        mock_create_engine.return_value = engine
        yield MySQLConsumer(MySQLConfig(), spool_config)


@pytest.fixture
def seeded_sensors(session):
    """Pre-insert temperature_sensor rows 1-4 to satisfy the FK constraint.

    Must commit (not just flush) so the rows are visible to the consumer's
    independent Session and InnoDB row locks are released before the consumer
    tries to insert into temperature_reading.
    """
    for i in range(1, 5):
        session.add(TemperatureSensorRecord(name=f"sensor-{i}"))
    session.commit()


class TestMySQLConsumerInit:
    """Tests for MySQLConsumer initialisation."""

    def test_subscribes_to_sensor_reading_event(self, engine, mock_bus):
        with (
            patch("pisolar.services.db.mysql_consumer.get_event_bus") as mock_get_bus,
            patch(
                "pisolar.services.db.mysql_consumer.create_db_engine"
            ) as mock_create_engine,
        ):
            mock_get_bus.return_value = mock_bus
            mock_create_engine.return_value = engine
            MySQLConsumer(MySQLConfig())

        mock_bus.subscribe.assert_called_once()
        assert mock_bus.subscribe.call_args[0][0] == SENSOR_READING_EVENT


class TestMySQLConsumerTemperatureReadings:
    """Tests for temperature reading persistence."""

    def test_handle_temperature_reading_persists_value(
        self, consumer, engine, seeded_sensors
    ):
        reading = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=1, value=22.5
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(TemperatureRecord)).scalar_one()
            assert row.value == pytest.approx(22.5)

    def test_handle_temperature_reading_links_sensor_id(
        self, consumer, engine, seeded_sensors
    ):
        reading = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=1, value=22.5
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(TemperatureRecord)).scalar_one()
            assert row.sensor_id == 1

    def test_handle_negative_temperature(self, consumer, engine, seeded_sensors):
        reading = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=1, value=-5.2
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(TemperatureRecord)).scalar_one()
            assert row.value == pytest.approx(-5.2)

    def test_multiple_readings_from_same_sensor(self, consumer, engine, seeded_sensors):
        for value in [20.0, 21.0, 22.0]:
            consumer._handle_reading(
                TemperatureReading(
                    type="temperature", name="0000007b409e", sensor_id=1, value=value
                )
            )

        with Session(engine) as session:
            readings = session.execute(select(TemperatureRecord)).scalars().all()
            assert len(readings) == 3
            assert all(r.sensor_id == 1 for r in readings)

    def test_multiple_sensors_each_get_own_sensor_id(
        self, consumer, engine, seeded_sensors
    ):
        for sensor_id in range(1, 5):
            consumer._handle_reading(
                TemperatureReading(
                    type="temperature",
                    name=f"addr-{sensor_id}",
                    sensor_id=sensor_id,
                    value=22.0,
                )
            )

        with Session(engine) as session:
            rows = session.execute(select(TemperatureRecord)).scalars().all()
            assert len(rows) == 4
            assert {r.sensor_id for r in rows} == {1, 2, 3, 4}


class TestMySQLConsumerSolarReadings:
    """Tests for solar reading persistence."""

    def test_handle_solar_reading_persists_sensor_name(self, consumer, engine):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(SolarRecord)).scalar_one()
            assert row.sensor_name == "rover-40"

    def test_handle_solar_reading_persists_battery_fields(self, consumer, engine):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(SolarRecord)).scalar_one()
            assert row.battery_percentage == 100
            assert row.battery_voltage == pytest.approx(13.2)
            assert row.battery_temperature == -10
            assert row.charging_status == "deactivated"

    def test_handle_solar_reading_charging_state(self, consumer, engine):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA_CHARGING
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            row = session.execute(select(SolarRecord)).scalar_one()
            assert row.battery_current == pytest.approx(3.5)
            assert row.pv_power == 52
            assert row.charging_status == "mppt"

    def test_solar_reading_does_not_create_sensor_record(self, consumer, engine):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        consumer._handle_reading(reading)

        with Session(engine) as session:
            sensors = session.execute(select(TemperatureSensorRecord)).scalars().all()
            assert len(sensors) == 0


class TestMySQLConsumerUnknownReading:
    """Tests for unrecognised reading types."""

    def test_unknown_reading_is_skipped(self, consumer, engine):
        consumer._handle_reading(UnknownReading(type="other", name="sensor 1"))

        with Session(engine) as session:
            assert len(session.execute(select(SolarRecord)).scalars().all()) == 0
            assert len(session.execute(select(TemperatureRecord)).scalars().all()) == 0

    def test_unknown_reading_logs_warning(self, consumer):
        with patch(
            "pisolar.services.db.mysql_consumer.MySQLConsumer._logger"
        ) as mock_logger:
            consumer._handle_reading(UnknownReading(type="other", name="sensor 1"))
            mock_logger.warning.assert_called_once()


class TestMySQLConsumerSpool:
    def test_connection_error_spools_and_marks_offline(
        self, consumer_with_spool, spool_config
    ):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        with patch.object(Session, "commit", side_effect=OperationalError("", "", "")):
            consumer_with_spool._handle_reading(reading)

        assert consumer_with_spool._db_state.is_offline()
        segments = list(
            (consumer_with_spool._spool.folder / "solar_reading").glob("*.jsonl")
        )
        assert len(segments) == 1
        envelope = json.loads(segments[0].read_text(encoding="utf-8").splitlines()[0])
        assert envelope["table"] == "solar_reading"
        assert envelope["data"]["sensor_name"] == "rover-40"

    def test_non_connection_error_does_not_spool(self, consumer_with_spool, engine):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        with patch.object(Session, "commit", side_effect=RuntimeError("logic bug")):
            consumer_with_spool._handle_reading(reading)

        assert not consumer_with_spool._db_state.is_offline()
        assert consumer_with_spool._spool.depth("solar_reading") == 0
        with Session(engine) as session:
            assert len(session.execute(select(SolarRecord)).scalars().all()) == 0

    def test_offline_short_circuit_skips_database(
        self, consumer_with_spool, spool_config
    ):
        consumer_with_spool._db_state.mark_offline()
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        with patch.object(Session, "commit") as mock_commit:
            consumer_with_spool._handle_reading(reading)
        mock_commit.assert_not_called()
        assert consumer_with_spool._spool.depth("solar_reading") == 1

    def test_online_transition_submits_flush(self, consumer_with_spool):
        reading = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        with patch.object(Session, "commit", side_effect=OperationalError("", "", "")):
            consumer_with_spool._handle_reading(reading)

        with (
            patch.object(
                consumer_with_spool._db_state, "is_offline", return_value=False
            ),
            patch.object(consumer_with_spool._flush_executor, "submit") as mock_submit,
        ):
            consumer_with_spool._handle_reading(reading)
        mock_submit.assert_called_once()

    def test_flush_drains_spool_into_database(
        self, consumer_with_spool, engine, seeded_sensors
    ):
        temp = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=1, value=12.3
        )
        solar = SolarReading.from_raw_data(
            sensor_type="solar", name="rover-40", data=RENOGY_RAW_DATA
        )
        with patch.object(Session, "commit", side_effect=OperationalError("", "", "")):
            consumer_with_spool._handle_reading(temp)
            consumer_with_spool._handle_reading(solar)

        consumer_with_spool.flush()

        with Session(engine) as session:
            assert len(session.execute(select(TemperatureRecord)).scalars().all()) == 1
            assert len(session.execute(select(SolarRecord)).scalars().all()) == 1
        assert consumer_with_spool._spool.depth("solar_reading") == 0
        assert consumer_with_spool._spool.depth("solar_temperature_reading") == 0

    @pytest.mark.parametrize(
        "bad_line", ["null", "[]", '{"table":"solar_reading","data":[]}']
    )
    def test_flush_quarantines_invalid_envelope(self, consumer_with_spool, bad_line):
        consumer_with_spool._spool.append("solar_reading", bad_line)

        consumer_with_spool.flush()

        rejected = (
            consumer_with_spool._spool.folder / "solar_reading" / "rejected.jsonl"
        )
        assert rejected.exists()
        assert consumer_with_spool._spool.depth("solar_reading") == 0

    def test_flush_isolates_bad_row_in_segment(self, consumer_with_spool, engine):
        valid = TemperatureRecord(
            sensor_id=1,
            read_time=TemperatureReading(
                type="temperature", name="valid", sensor_id=1, value=12.3
            ).read_time.replace(tzinfo=None),
            value=12.3,
        )
        invalid = TemperatureRecord(
            sensor_id=None,
            read_time=valid.read_time,
            value=9.0,
        )
        consumer_with_spool._spool_row(valid)
        consumer_with_spool._spool_row(invalid)

        consumer_with_spool.flush()

        with Session(engine) as session:
            rows = session.execute(select(TemperatureRecord)).scalars().all()
            assert len(rows) == 1
            assert rows[0].value == pytest.approx(12.3)
        rejected = (
            consumer_with_spool._spool.folder
            / "solar_temperature_reading"
            / "rejected.jsonl"
        )
        assert rejected.exists()
        assert consumer_with_spool._spool.depth("solar_temperature_reading") == 0

    def test_flush_leaves_draining_on_connection_error(
        self, consumer_with_spool, engine, seeded_sensors
    ):
        reading = TemperatureReading(
            type="temperature", name="0000007b409e", sensor_id=1, value=9.0
        )
        with patch.object(Session, "commit", side_effect=OperationalError("", "", "")):
            consumer_with_spool._handle_reading(reading)

        with (
            patch.object(
                consumer_with_spool,
                "_health_check",
                return_value=True,
            ),
            patch.object(Session, "commit", side_effect=OperationalError("", "", "")),
        ):
            consumer_with_spool.flush()

        assert (
            len(
                consumer_with_spool._spool.draining_segments(
                    "solar_temperature_reading"
                )
            )
            == 1
        )

    def test_flush_reentrancy_lock(self, consumer_with_spool):
        consumer_with_spool._flush_lock.acquire()
        try:
            with patch.object(consumer_with_spool, "_health_check") as mock_health:
                consumer_with_spool.flush()
                mock_health.assert_not_called()
        finally:
            consumer_with_spool._flush_lock.release()


class TestMySQLConsumerClose:
    """Tests for MySQLConsumer.close()."""

    def test_close_unsubscribes_from_event_bus(self, consumer, mock_bus):
        consumer.close()
        mock_bus.unsubscribe.assert_called_once_with(
            SENSOR_READING_EVENT, consumer._handle_reading
        )

    def test_close_is_idempotent(self, consumer, mock_bus):
        consumer.close()
        consumer.close()
        assert mock_bus.unsubscribe.call_count == 2
