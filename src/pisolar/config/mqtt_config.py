"""MQTT broker and topic configuration."""

from pydantic import BaseModel, Field, SecretStr


class MqttTopics(BaseModel):
    """MQTT topic paths for each sensor type."""

    solar: str = Field(
        default="pisolar/solar",
        description="Topic for solar charge controller readings",
    )
    temperature: str = Field(
        default="pisolar/temperature",
        description="Topic for temperature sensor readings",
    )


class MqttConfig(BaseModel):
    """MQTT connection and topic configuration."""

    enabled: bool = Field(default=False, description="Enable MQTT publishing")
    host: str = Field(default="localhost", description="MQTT broker hostname")
    port: int = Field(default=1883, description="MQTT broker port")
    client_id: str = Field(default="pisolar", description="MQTT client identifier")
    username: str | None = Field(default=None, description="MQTT broker username")
    password: SecretStr | None = Field(
        default=None, description="MQTT broker password"
    )
    keepalive: int = Field(
        default=60, description="Keepalive interval in seconds"
    )
    qos: int = Field(default=1, ge=0, le=2, description="MQTT QoS level (0, 1, or 2)")
    retain: bool = Field(
        default=False,
        description="Whether the broker should retain the last message per topic",
    )
    topics: MqttTopics = Field(default_factory=MqttTopics)
