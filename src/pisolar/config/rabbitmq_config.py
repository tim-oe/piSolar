"""RabbitMQ publisher configuration."""

from pydantic import BaseModel, Field


class RabbitMQConfig(BaseModel):
    """RabbitMQ connection and publishing configuration."""

    enabled: bool = Field(default=False, description="Enable RabbitMQ publishing")
    url: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        description="AMQP connection URL",
    )
    exchange: str = Field(
        default="pisolar",
        description="Exchange name to publish sensor readings to",
    )
    exchange_type: str = Field(
        default="topic",
        description="Exchange type: direct, fanout, or topic",
    )
    routing_key: str = Field(
        default="sensor.reading",
        description=(
            "Base routing key for published messages. "
            "Prefixed with sensor type when exchange_type is 'topic'."
        ),
    )
    durable: bool = Field(
        default=True,
        description="Declare the exchange as durable (survives broker restarts)",
    )
