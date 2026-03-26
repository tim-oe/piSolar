"""SQLite storage configuration."""

from pydantic import BaseModel, Field

from pisolar.config.sensor_schedule import SensorSchedule

DEFAULT_PRUNE_SCHEDULE = "0 3 * * *"


class StorageConfig(BaseModel):
    """SQLite storage configuration for persisting sensor readings."""

    enabled: bool = Field(default=False, description="Enable SQLite storage")
    db_path: str = Field(
        default="/var/lib/pisolar/readings.db",
        description="Path to the SQLite database file",
    )
    retention_days: int = Field(
        default=90,
        ge=1,
        description="Number of days to retain readings before pruning",
    )
    prune_schedule: SensorSchedule = Field(
        default_factory=lambda: SensorSchedule(
            cron=DEFAULT_PRUNE_SCHEDULE, enabled=True
        ),
        description="Schedule for pruning old readings",
    )
