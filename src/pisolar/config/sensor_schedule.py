"""Schedule configuration for a sensor."""

from pydantic import BaseModel, Field


class SensorSchedule(BaseModel):
    """Schedule configuration for a sensor."""

    cron: str = Field(
        default="*/5 * * * *", description="Cron expression for scheduling"
    )
    enabled: bool = Field(default=True, description="Whether this schedule is enabled")
