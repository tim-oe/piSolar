"""RabbitMQ consumer that publishes sensor readings to an AMQP exchange."""

import json

import pika
import pika.exceptions

from pisolar.config.rabbitmq_config import RabbitMQConfig
from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.services.metrics_service import SENSOR_READING_EVENT


class RabbitMQConsumer:
    """Consumer that publishes sensor readings to a RabbitMQ exchange.

    Maintains a single blocking connection and channel, re-establishing them
    transparently on publish failure so transient broker outages don't crash
    the monitoring service.
    """

    _logger = get_logger("services.rabbitmq")

    def __init__(self, config: RabbitMQConfig) -> None:
        self._config = config
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None

        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._logger.info(
            "RabbitMQ consumer initialized: url=%s exchange=%s routing_key=%s",
            self._config.url,
            self._config.exchange,
            self._config.routing_key,
        )

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open a new connection and declare the exchange."""
        params = pika.URLParameters(self._config.url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.exchange_declare(
            exchange=self._config.exchange,
            exchange_type=self._config.exchange_type,
            durable=self._config.durable,
        )
        self._logger.info(
            "Connected to RabbitMQ: exchange=%s type=%s durable=%s",
            self._config.exchange,
            self._config.exchange_type,
            self._config.durable,
        )

    def _ensure_connected(self) -> bool:
        """Return True if a usable channel is available, connecting if needed."""
        if self._connection is None or self._connection.is_closed:
            try:
                self._connect()
            except Exception:
                self._logger.exception("Failed to connect to RabbitMQ")
                return False
        return True

    def _close_quietly(self) -> None:
        """Close the connection without raising."""
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception:
            pass
        finally:
            self._connection = None
            self._channel = None

    # ------------------------------------------------------------------
    # Routing key
    # ------------------------------------------------------------------

    def _build_routing_key(self, reading: SensorReading) -> str:
        """Build the routing key for a reading.

        For *topic* exchanges the key is ``<base>.<type>.<name>`` so
        consumers can bind with patterns like ``sensor.reading.temperature.*``.
        For other exchange types the configured base key is used unchanged.
        """
        if self._config.exchange_type == "topic":
            safe_name = reading.name.replace(" ", "_")
            return f"{self._config.routing_key}.{reading.type}.{safe_name}"
        return self._config.routing_key

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _handle_reading(self, reading: SensorReading) -> None:
        """Publish a sensor reading to RabbitMQ."""
        if not self._ensure_connected():
            return

        payload = json.dumps(reading.to_dict()).encode()
        routing_key = self._build_routing_key(reading)

        try:
            assert self._channel is not None  # guaranteed by _ensure_connected
            self._channel.basic_publish(
                exchange=self._config.exchange,
                routing_key=routing_key,
                body=payload,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=pika.DeliveryMode.Persistent,
                ),
            )
            self._logger.debug(
                "Published reading: exchange=%s routing_key=%s sensor=%s/%s",
                self._config.exchange,
                routing_key,
                reading.type,
                reading.name,
            )
        except (pika.exceptions.AMQPError, Exception):
            self._logger.exception(
                "Failed to publish reading for %s/%s — dropping connection",
                reading.type,
                reading.name,
            )
            self._close_quietly()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Unsubscribe from the event bus and close the RabbitMQ connection."""
        self._event_bus.unsubscribe(SENSOR_READING_EVENT, self._handle_reading)
        self._close_quietly()
        self._logger.info("RabbitMQ consumer closed")
