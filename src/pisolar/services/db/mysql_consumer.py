"""MySQL consumer that persists solar and temperature sensor readings."""

from sqlalchemy.orm import Session

from pisolar.config.mysql_config import MySQLConfig
from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.db.base import create_db_engine
from pisolar.services.db.solar_model import SolarRecord
from pisolar.services.db.temperature_model import TemperatureRecord
from pisolar.services.metrics_service import SENSOR_READING_EVENT


class MySQLConsumer:
    """Consumer that persists sensor readings to a MySQL database.

    Subscribes to the :data:`~pisolar.services.metrics_service.SENSOR_READING_EVENT`
    event bus topic and writes one row per reading to the appropriate table:

    - :class:`~pisolar.sensors.renogy.solar_reading.SolarReading` → ``solar_reading``
    - :class:`~pisolar.sensors.temperature.temperature_reading.TemperatureReading`
      → ``temperature_reading``

    Schema management is handled externally (pyway).  This class does **not**
    call ``create_all()``; the tables must already exist before the service starts.

    Temperature sensor IDs are sourced directly from config and stored in
    :attr:`~pisolar.sensors.temperature.temperature_reading.TemperatureReading.sensor_id`.
    The ``temperature_sensor`` lookup table is managed by pyway migrations.
    """

    _logger = get_logger("services.mysql")

    def __init__(self, config: MySQLConfig) -> None:
        self._engine = create_db_engine(
            url=config.url,
            pool_size=config.pool_size,
            pool_recycle=config.pool_recycle,
        )

        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._logger.info("MySQL consumer initialized: url=%s", config.masked_url)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_reading(self, reading: SensorReading) -> None:
        try:
            with Session(self._engine) as session:
                if isinstance(reading, SolarReading):
                    session.add(SolarRecord.from_reading(reading))
                elif isinstance(reading, TemperatureReading):
                    session.add(
                        TemperatureRecord.from_reading(reading, reading.sensor_id)
                    )
                else:
                    self._logger.warning(
                        "Unhandled reading type %s for %s/%s — skipping",
                        type(reading).__name__,
                        reading.type,
                        reading.name,
                    )
                    return
                session.commit()
            self._logger.debug(
                "Persisted %s reading for %s", reading.type, reading.name
            )
        except Exception:
            self._logger.exception(
                "Failed to persist %s reading for %s", reading.type, reading.name
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Unsubscribe from the event bus and dispose the connection pool."""
        self._event_bus.unsubscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._engine.dispose()
        self._logger.info("MySQL consumer closed")
