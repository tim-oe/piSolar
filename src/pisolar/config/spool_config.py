"""Offline spool configuration for MySQL write buffering."""

from pydantic import BaseModel, Field

from pisolar.config.sensor_schedule import SensorSchedule

DEFAULT_FLUSH_CRON = "*/5 * * * *"


class SpoolConfig(BaseModel):
    """Local JSON-lines spool when MySQL is unreachable."""

    enabled: bool = Field(
        default=True,
        description="Buffer MySQL writes to local spool files on connection errors",
    )
    folder: str = Field(
        default="/var/lib/piSolar/spool",
        description="Root directory for spool segments (must be local disk, not NFS)",
    )
    min_free_pct: float = Field(
        default=14.0,
        ge=0,
        le=100,
        description="Minimum free disk space (percent) before evicting oldest segments",
    )
    warn_age_hours: int = Field(
        default=24,
        ge=1,
        description=(
            "Log a warning once per outage when the oldest segment exceeds this age"
        ),
    )
    flush_schedule: SensorSchedule = Field(
        default_factory=lambda: SensorSchedule(cron=DEFAULT_FLUSH_CRON, enabled=True),
        description="Scheduled replay of spooled rows to MySQL",
    )
