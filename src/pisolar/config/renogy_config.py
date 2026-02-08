"""Top-level configuration for Renogy sensors."""

from typing import Annotated, Union

from pydantic import BaseModel, Field

from pisolar.config.renogy_bluetooth_sensor_config import RenogyBluetoothSensorConfig
from pisolar.config.renogy_serial_sensor_config import RenogySerialSensorConfig
from pisolar.config.sensor_schedule import SensorSchedule

# Discriminated union based on read_type field
RenogySensorConfig = Annotated[
    Union[RenogyBluetoothSensorConfig, RenogySerialSensorConfig],
    Field(discriminator="read_type"),
]


class RenogyConfig(BaseModel):
    """Top-level configuration for all Renogy sensors."""

    enabled: bool = Field(default=False, description="Enable Renogy sensor reading")
    schedule: SensorSchedule = Field(default_factory=SensorSchedule)
    sensors: list[RenogySensorConfig] = Field(
        default_factory=list,
        description="List of Renogy sensor configurations",
    )
