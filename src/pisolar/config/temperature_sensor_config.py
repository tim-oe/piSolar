"""Configuration for temperature sensors."""

from pydantic import BaseModel, Field

from pisolar.config.sensor_schedule import SensorSchedule
from pisolar.config.temperature_sensor_item import TemperatureSensorItem


class TemperatureSensorConfig(BaseModel):
    """Configuration for temperature sensors."""

    enabled: bool = Field(default=True)
    sensors: list[TemperatureSensorItem] = Field(
        default_factory=list, description="List of configured temperature sensors"
    )
    schedule: SensorSchedule = Field(default_factory=SensorSchedule)
