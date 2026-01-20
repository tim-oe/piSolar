"""Temperature sensor reading."""

from typing import Any

from pisolar.sensors.sensor_reading import SensorReading


class TemperatureReading(SensorReading):
    """Temperature sensor reading with value and unit."""

    value: float
    unit: str = "C"  # Celsius by default

    def to_dict(self) -> dict[str, Any]:
        """Convert reading to dictionary."""
        return {
            "type": self.type,
            "name": self.name,
            "read_time": self.read_time.isoformat(),
            "value": self.value,
            "unit": self.unit,
        }
