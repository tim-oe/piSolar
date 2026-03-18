"""Metrics collection and event publishing service."""

from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.sensor_reading import SensorReading

# Event type for sensor readings
SENSOR_READING_EVENT = "sensor.reading"


class MetricsService:
    """Service for collecting and publishing sensor metrics via event bus."""

    _logger = get_logger("services.metrics")

    def __init__(self) -> None:
        """Initialize the metrics service."""
        self._event_bus = get_event_bus()

    def record(self, readings: list[SensorReading]) -> None:
        """
        Publish sensor readings as events.

        Args:
            readings: List of sensor readings to publish
        """
        for reading in readings:
            self._event_bus.publish(SENSOR_READING_EVENT, reading)

        self._logger.info("Published %d sensor reading(s)", len(readings))
