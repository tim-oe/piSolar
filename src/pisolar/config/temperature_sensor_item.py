"""Configuration for a single temperature sensor."""

from pydantic import BaseModel, Field


class TemperatureSensorItem(BaseModel):
    """Configuration for a single temperature sensor."""

    id: int = Field(
        ge=1,
        le=255,
        description="Sensor ID — stored as sensor_id in temperature_reading",
    )
    address: str = Field(description="1-Wire address of the sensor (no family prefix)")
    name: str | None = Field(
        default=None,
        description="Optional human-readable label for this sensor",
    )
