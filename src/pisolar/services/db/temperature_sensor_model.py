"""SQLAlchemy ORM model for the temperature sensor lookup table.

DDL (MySQL):

    CREATE TABLE IF NOT EXISTS solar_temperature_sensor (
        id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
        name  VARCHAR(100)     NOT NULL,

        PRIMARY KEY (id),
        UNIQUE KEY uq_solar_temp_sensor_name (name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

from __future__ import annotations

from sqlalchemy.dialects.mysql import TINYINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from pisolar.services.db.base import Base


class TemperatureSensorRecord(Base):
    """Lookup table row mapping a sensor display name to a stable integer identity.

    Rows are inserted on first sight by
    :class:`~pisolar.services.db.mysql_consumer.MySQLConsumer`
    and cached in memory for the lifetime of the process.
    """

    __tablename__ = "solar_temperature_sensor"

    id: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False, unique=True)
