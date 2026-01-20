"""Temperature sensor implementation using w1thermsensor."""

from w1thermsensor import Sensor, W1ThermSensor

from pisolar.logging_config import get_logger
from pisolar.sensors.base_sensor import BaseSensor
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature_reading import TemperatureReading

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
        readings: list[SensorReading] = []

        available = {s.id: s for s in W1ThermSensor.get_available_sensors([Sensor.DS18B20])}

        for sensor_config in self._sensors:
            name = sensor_config["name"]
            address = sensor_config["address"]

            sensor = available.get(address)
            if sensor is None:
                try:
                    sensor = W1ThermSensor(sensor_type=Sensor.DS18B20, sensor_id=address)
                except Exception as e:
                    logger.warning("Sensor %s (%s) not found: %s", name, address, e)
                    continue

            temp_celsius = sensor.get_temperature()

            reading = TemperatureReading(
                type=self.sensor_type,
                name=name,
                value=temp_celsius,
                unit="celsius",
            )
            readings.append(reading)
            logger.debug(
                "Temperature reading: name=%s, address=%s, value=%.2f°C",
                name,
                address,
                temp_celsius,
            )

        logger.info("Read %d temperature sensor(s)", len(readings))
        return readings
