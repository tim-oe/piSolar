"""Tests for MySQLConsumer."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pisolar.config.mysql_config import MySQLConfig
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
