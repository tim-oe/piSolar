"""Application settings with YAML and environment variable support."""

from pyaml_env import parse_config
from pydantic import BaseModel, Field

from pisolar.config.metrics_config import MetricsConfig
from pisolar.config.mysql_config import MySQLConfig
from pisolar.config.rabbitmq_config import RabbitMQConfig
from pisolar.config.renogy_config import RenogyConfig
from pisolar.config.storage_config import StorageConfig
from pisolar.config.temperature_sensor_config import TemperatureSensorConfig


class Settings(BaseModel):
    """Application settings with YAML and environment variable support."""

    temperature: TemperatureSensorConfig = Field(
        default_factory=TemperatureSensorConfig
    )
    renogy: RenogyConfig = Field(default_factory=RenogyConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)

    @classmethod  # type: ignore[misc]
    def from_yaml(cls, config_path: str) -> "Settings":
        """Load settings from YAML file with environment variable substitution."""
        config = parse_config(config_path)
        if config is None:
            raise ValueError(f"Failed to parse config from {config_path}")
        if not isinstance(config, dict):
            raise TypeError(f"Expected dict config, got {type(config)}")
        return cls(**config)
