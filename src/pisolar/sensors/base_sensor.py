"""Abstract base class for all sensors."""

from abc import ABC, abstractmethod

from pisolar.sensors.sensor_reading import SensorReading


class BaseSensor(ABC):
    """Abstract base class for all sensors."""

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """Return the type identifier for this sensor."""

    @abstractmethod
    def read(self) -> list[SensorReading]:
        """Read current values from the sensor(s)."""
