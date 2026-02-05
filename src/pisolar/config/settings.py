"""Application settings with YAML and environment variable support."""

from pyaml_env import parse_config
from pydantic import BaseModel, Field

from pisolar.config.metrics_config import MetricsConfig
from pisolar.config.renogy_config import RenogyConfig
from pisolar.config.temperature_sensor_config import TemperatureSensorConfig


class Settings(BaseModel):
    """Application settings with YAML and environment variable support."""

    temperature: TemperatureSensorConfig = Field(
        default_factory=TemperatureSensorConfig
    )
    renogy: RenogyConfig = Field(default_factory=RenogyConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @classmethod
    def from_yaml(cls, config_path: str) -> "Settings":
        """Load settings from YAML file with environment variable substitution."""
        config = parse_config(config_path)
        return cls(**config)
