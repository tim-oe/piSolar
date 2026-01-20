"""Base abstract class for sensor readings."""

from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    """Base class for a sensor reading."""

    type: str
    name: str
    read_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert reading to dictionary."""
        ...
