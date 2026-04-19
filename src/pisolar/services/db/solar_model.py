"""SQLAlchemy ORM model for solar charge controller readings.

DDL (MySQL):

    CREATE TABLE IF NOT EXISTS solar_reading (
        id                            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
        sensor_name                   VARCHAR(100)    NOT NULL,
        read_time                     DATETIME(6)     NOT NULL,

        -- Device info
        model                         VARCHAR(64),
        device_id                     TINYINT UNSIGNED,

        -- Battery status
        battery_percentage            TINYINT UNSIGNED,
        battery_voltage               FLOAT UNSIGNED,
        battery_current               FLOAT UNSIGNED,
        battery_temperature           TINYINT,
        battery_type                  VARCHAR(32),

        -- Controller status
        controller_temperature        TINYINT,
        charging_status               VARCHAR(32),

        -- Load output (street light)
        load_status                   VARCHAR(8),
        load_voltage                  FLOAT UNSIGNED,
        load_current                  FLOAT UNSIGNED,
        load_power                    SMALLINT UNSIGNED,

        -- PV (solar panel) input
        pv_voltage                    FLOAT UNSIGNED,
        pv_current                    FLOAT UNSIGNED,
        pv_power                      SMALLINT UNSIGNED,

        -- Daily statistics
        battery_min_voltage_today     FLOAT UNSIGNED,
        battery_max_voltage_today     FLOAT UNSIGNED,
        max_charging_current_today    FLOAT UNSIGNED,
        max_discharging_current_today FLOAT UNSIGNED,
        max_charging_power_today      SMALLINT UNSIGNED,
        max_discharging_power_today   SMALLINT UNSIGNED,
        charging_amp_hours_today      SMALLINT UNSIGNED,
        discharging_amp_hours_today   SMALLINT UNSIGNED,
        power_generation_today        FLOAT UNSIGNED,
        power_consumption_today       FLOAT UNSIGNED,

        -- Lifetime statistics
        power_generation_total        INT UNSIGNED,

        PRIMARY KEY (id),
        INDEX idx_solar_read_time   (read_time),
        INDEX idx_solar_sensor_name (sensor_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy.dialects.mysql import (
    DATETIME,
    FLOAT,
    INTEGER,
    SMALLINT,
    TINYINT,
    VARCHAR,
)
from sqlalchemy.orm import Mapped, mapped_column

from pisolar.services.db.base import Base

if TYPE_CHECKING:
    from pisolar.sensors.renogy.solar_reading import SolarReading


class SolarRecord(Base):
    """Persisted row for a single :class:`~pisolar.sensors.renogy.solar_reading.SolarReading`."""

    __tablename__ = "solar_reading"

    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    sensor_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    read_time: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, index=True)

    # Device info
    model: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    device_id: Mapped[Optional[int]] = mapped_column(TINYINT(unsigned=True))

    # Battery status
    battery_percentage: Mapped[Optional[int]] = mapped_column(TINYINT(unsigned=True))
    battery_voltage: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    battery_current: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    battery_temperature: Mapped[Optional[int]] = mapped_column(TINYINT())
    battery_type: Mapped[Optional[str]] = mapped_column(VARCHAR(32))

    # Controller status
    controller_temperature: Mapped[Optional[int]] = mapped_column(TINYINT())
    charging_status: Mapped[Optional[str]] = mapped_column(VARCHAR(32))

    # Load output (street light)
    load_status: Mapped[Optional[str]] = mapped_column(VARCHAR(8))
    load_voltage: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    load_current: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    load_power: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))

    # PV (solar panel) input
    pv_voltage: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    pv_current: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    pv_power: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))

    # Daily statistics
    battery_min_voltage_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    battery_max_voltage_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    max_charging_current_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    max_discharging_current_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    max_charging_power_today: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))
    max_discharging_power_today: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))
    charging_amp_hours_today: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))
    discharging_amp_hours_today: Mapped[Optional[int]] = mapped_column(SMALLINT(unsigned=True))
    power_generation_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))
    power_consumption_today: Mapped[Optional[float]] = mapped_column(FLOAT(unsigned=True))

    # Lifetime statistics
    power_generation_total: Mapped[Optional[int]] = mapped_column(INTEGER(unsigned=True))

    @classmethod
    def from_reading(cls, reading: SolarReading) -> SolarRecord:
        """Build a :class:`SolarRecord` from a :class:`~pisolar.sensors.renogy.solar_reading.SolarReading`.

        The ``read_time`` timezone info is stripped before storage because
        MySQL ``DATETIME`` columns are not timezone-aware.
        """
        return cls(
            sensor_name=reading.name,
            read_time=reading.read_time.replace(tzinfo=None),
            model=reading.model,
            device_id=reading.device_id,
            battery_percentage=reading.battery_percentage,
            battery_voltage=reading.battery_voltage,
            battery_current=reading.battery_current,
            battery_temperature=reading.battery_temperature,
            battery_type=reading.battery_type,
            controller_temperature=reading.controller_temperature,
            charging_status=reading.charging_status,
            load_status=reading.load_status,
            load_voltage=reading.load_voltage,
            load_current=reading.load_current,
            load_power=reading.load_power,
            pv_voltage=reading.pv_voltage,
            pv_current=reading.pv_current,
            pv_power=reading.pv_power,
            battery_min_voltage_today=reading.battery_min_voltage_today,
            battery_max_voltage_today=reading.battery_max_voltage_today,
            max_charging_current_today=reading.max_charging_current_today,
            max_discharging_current_today=reading.max_discharging_current_today,
            max_charging_power_today=reading.max_charging_power_today,
            max_discharging_power_today=reading.max_discharging_power_today,
            charging_amp_hours_today=reading.charging_amp_hours_today,
            discharging_amp_hours_today=reading.discharging_amp_hours_today,
            power_generation_today=reading.power_generation_today,
            power_consumption_today=reading.power_consumption_today,
            power_generation_total=reading.power_generation_total,
        )
