"""Configuration for a single temperature sensor."""

from pydantic import BaseModel, Field


class TemperatureSensorItem(BaseModel):
    """Configuration for a single temperature sensor."""

    name: str = Field(description="Friendly name for the sensor")
    address: str = Field(description="1-Wire address of the sensor")
