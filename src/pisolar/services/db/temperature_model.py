"""SQLAlchemy ORM model for temperature sensor readings.

DDL (MySQL):

    CREATE TABLE IF NOT EXISTS solar_temperature_reading (
        id               INT UNSIGNED     NOT NULL AUTO_INCREMENT,
        sensor_id        TINYINT UNSIGNED NOT NULL,
        read_time        DATETIME(6)      NOT NULL,
        value            FLOAT            NOT NULL,

        PRIMARY KEY (id, read_time),
        INDEX idx_solar_temp_read_time  (read_time),
        INDEX idx_solar_temp_sensor_id  (sensor_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

    -- No FK constraint: partitioned tables do not support foreign keys in MariaDB/MySQL.
    -- sensor_id logically references solar_temperature_sensor(id) but is not enforced by the DB.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.mysql import DATETIME, FLOAT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from pisolar.services.db.base import Base

if TYPE_CHECKING:
    from pisolar.sensors.temperature.temperature_reading import TemperatureReading


class TemperatureRecord(Base):
    """Persisted row for a single :class:`~pisolar.sensors.temperature.temperature_reading.TemperatureReading`."""

    __tablename__ = "solar_temperature_reading"

    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    sensor_id: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        index=True,
    )
    read_time: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, index=True)

    # Temperature value — signed (outdoor temps can be below 0°C)
    value: Mapped[float] = mapped_column(FLOAT, nullable=False)

    @classmethod
    def from_reading(cls, reading: TemperatureReading, sensor_id: int) -> TemperatureRecord:
        """Build a :class:`TemperatureRecord` from a reading.

        Args:
            reading: The temperature reading to persist.
            sensor_id: Sensor identifier from config; logically references
                ``solar_temperature_sensor(id)`` but not DB-enforced (partitioned table).

        The ``read_time`` timezone info is stripped before storage because
        MySQL ``DATETIME`` columns are not timezone-aware.
        """
        return cls(
            sensor_id=sensor_id,
            read_time=reading.read_time.replace(tzinfo=None),
            value=reading.value,
        )
