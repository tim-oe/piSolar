"""Temperature sensor implementation using w1thermsensor."""

import time

from w1thermsensor import Sensor, W1ThermSensor
from w1thermsensor.errors import (
    ResetValueError,
    SensorNotReadyError,
    W1ThermSensorError,
)

from pisolar.logging_config import get_logger
from pisolar.sensors.base_sensor import BaseSensor
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature.reading import TemperatureReading

logger = get_logger("sensors.temperature")


class TemperatureSensor(BaseSensor):
    """Temperature sensor using 1-Wire protocol via w1thermsensor."""

    def __init__(self, sensors: list[dict[str, str]]) -> None:
        """
        Initialize temperature sensor with configured sensors.

        Args:
            sensors: List of sensor configs with 'name' and 'address' keys
                     (address = sensor_id without family prefix, e.g. 0000007c6850)
        """
        self._sensors = sensors

    @property
    def sensor_type(self) -> str:
        """Return the sensor type identifier."""
        return "temperature"

    def read(self) -> list[SensorReading]:
        """Read temperature from configured 1-Wire sensors."""
        start_time = time.perf_counter()
        readings: list[SensorReading] = []

        available = {
            s.id: s for s in W1ThermSensor.get_available_sensors([Sensor.DS18B20])
        }

        for sensor_config in self._sensors:
            name = sensor_config["name"]
            address = sensor_config["address"]

            sensor = available.get(address)
            if sensor is None:
                try:
                    sensor = W1ThermSensor(
                        sensor_type=Sensor.DS18B20, sensor_id=address
                    )
                except Exception as e:
                    logger.warning("Sensor %s (%s) not found: %s", name, address, e)
                    continue

            sensor_start = time.perf_counter()
            try:
                temp_celsius = sensor.get_temperature()
            except ResetValueError:
                logger.warning(
                    "Sensor %s (%s) returned reset value (85°C). "
                    "Check power supply and wiring.",
                    name,
                    address,
                )
                continue
            except SensorNotReadyError:
                logger.warning(
                    "Sensor %s (%s) not ready. Skipping this read.",
                    name,
                    address,
                )
                continue
            except W1ThermSensorError as e:
                logger.warning(
                    "Sensor %s (%s) read error: %s",
                    name,
                    address,
                    e,
                )
                continue
            sensor_elapsed_ms = (time.perf_counter() - sensor_start) * 1000

            reading = TemperatureReading(
                type=self.sensor_type,
                name=name,
                value=temp_celsius,
                unit="celsius",
                read_duration_ms=round(sensor_elapsed_ms, 1),
            )
            readings.append(reading)
            logger.debug(
                "Temperature: %s (%s) = %.2fC in %.1fms",
                name,
                address,
                temp_celsius,
                sensor_elapsed_ms,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Read %d temperature sensor(s) in %.1fms (%.1fms/sensor)",
            len(readings),
            elapsed_ms,
            elapsed_ms / len(readings) if readings else 0,
        )
        return readings
