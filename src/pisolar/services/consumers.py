"""Event consumers for sensor readings."""

from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.services.metrics import SENSOR_READING_EVENT


class LoggingConsumer:
    """Consumer that logs sensor readings to console/logging."""

    _logger = get_logger("services.consumers")

    def __init__(self) -> None:
        """Initialize the logging consumer."""
        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)

    def _handle_reading(self, reading: SensorReading) -> None:
        """Handle a sensor reading event."""
        data = reading.to_dict()
        self._logger.info("sensor.reading %s %s %s", reading.type, reading.name, data)
