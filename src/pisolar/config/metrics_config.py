"""Metrics output configuration."""

from pydantic import BaseModel, Field


class MetricsConfig(BaseModel):
    """Metrics output configuration."""

    output_dir: str = Field(default="./metrics", description="Directory for metrics")
