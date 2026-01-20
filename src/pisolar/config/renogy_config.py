"""Configuration for Renogy BT-2 module."""

from pydantic import BaseModel, Field

from pisolar.config.sensor_schedule import SensorSchedule


class RenogyConfig(BaseModel):
    """Configuration for Renogy BT-2 module."""

    enabled: bool = Field(default=False)
    name: str = Field(default="", description="Friendly name for the device")
    mac_address: str = Field(default="", description="Bluetooth MAC address of BT-2")
    device_alias: str = Field(default="BT-2", description="Device alias")
    schedule: SensorSchedule = Field(default_factory=SensorSchedule)
