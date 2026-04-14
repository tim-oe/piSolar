"""Tests for RabbitMQConsumer."""

import json
from unittest.mock import MagicMock, call, patch

import pika
import pika.exceptions
import pytest

from pisolar.config.rabbitmq_config import RabbitMQConfig
from pisolar.event_bus import EventBus
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.metrics_service import SENSOR_READING_EVENT
from pisolar.services.rabbitmq_consumer import RabbitMQConsumer
from tests.fixtures import RENOGY_RAW_DATA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> RabbitMQConfig:
    defaults = dict(
        enabled=True,
        url="amqp://guest:guest@localhost:5672/",
        exchange="pisolar",
        exchange_type="topic",
        routing_key="sensor.reading",
        durable=True,
    )
    defaults.update(overrides)
    return RabbitMQConfig(**defaults)


def _temp_reading(name: str = "temp 1", value: float = 22.5) -> TemperatureReading:
    return TemperatureReading(type="temperature", name=name, value=value)


def _solar_reading(name: str = "rover") -> SolarReading:
    return SolarReading.from_raw_data(
        sensor_type="solar",
        name=name,
        data=RENOGY_RAW_DATA,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_bus():
    return MagicMock(spec=EventBus)


@pytest.fixture()
def mock_channel():
    return MagicMock()


@pytest.fixture()
def mock_connection(mock_channel):
    conn = MagicMock()
    conn.is_closed = False
    conn.channel.return_value = mock_channel
    return conn


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestRabbitMQConsumerInit:
    def test_subscribes_to_sensor_reading_event(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())

        mock_bus.subscribe.assert_called_once()
        event_type, handler = mock_bus.subscribe.call_args[0]
        assert event_type == SENSOR_READING_EVENT
        assert handler == consumer._handle_reading

    def test_connection_not_opened_at_init(self, mock_bus):
        """Connection should be lazy – opened only on first publish."""
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection") as mock_cls:
            RabbitMQConsumer(_make_config())

        mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# _connect
# ---------------------------------------------------------------------------

class TestConnect:
    def test_opens_connection_and_declares_exchange(self, mock_bus, mock_connection, mock_channel):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters") as mock_params:
            config = _make_config(exchange="myexchange", exchange_type="fanout", durable=False)
            consumer = RabbitMQConsumer(config)
            consumer._connect()

        mock_params.assert_called_once_with(config.url)
        mock_channel.exchange_declare.assert_called_once_with(
            exchange="myexchange",
            exchange_type="fanout",
            durable=False,
        )

    def test_stores_connection_and_channel(self, mock_bus, mock_connection, mock_channel):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())
            consumer._connect()

        assert consumer._connection is mock_connection
        assert consumer._channel is mock_channel


# ---------------------------------------------------------------------------
# _ensure_connected
# ---------------------------------------------------------------------------

class TestEnsureConnected:
    def test_returns_true_when_already_connected(self, mock_bus, mock_connection):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())
        consumer._connection = mock_connection  # inject open connection
        consumer._channel = MagicMock()

        result = consumer._ensure_connected()

        assert result is True

    def test_connects_when_connection_is_none(self, mock_bus, mock_connection, mock_channel):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())
            result = consumer._ensure_connected()

        assert result is True
        assert consumer._connection is mock_connection

    def test_connects_when_connection_is_closed(self, mock_bus, mock_connection, mock_channel):
        closed_conn = MagicMock()
        closed_conn.is_closed = True

        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())
            consumer._connection = closed_conn
            result = consumer._ensure_connected()

        assert result is True
        assert consumer._connection is mock_connection

    def test_returns_false_on_connection_error(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection",
                   side_effect=pika.exceptions.AMQPConnectionError("refused")), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())
            result = consumer._ensure_connected()

        assert result is False


# ---------------------------------------------------------------------------
# _close_quietly
# ---------------------------------------------------------------------------

class TestCloseQuietly:
    def test_closes_open_connection(self, mock_bus, mock_connection):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())
        consumer._connection = mock_connection
        consumer._channel = MagicMock()

        consumer._close_quietly()

        mock_connection.close.assert_called_once()
        assert consumer._connection is None
        assert consumer._channel is None

    def test_does_not_raise_when_close_fails(self, mock_bus, mock_connection):
        mock_connection.close.side_effect = Exception("bang")
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())
        consumer._connection = mock_connection

        consumer._close_quietly()  # should not raise

        assert consumer._connection is None

    def test_handles_none_connection(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())
        consumer._connection = None

        consumer._close_quietly()  # should not raise

        assert consumer._connection is None


# ---------------------------------------------------------------------------
# _build_routing_key
# ---------------------------------------------------------------------------

class TestBuildRoutingKey:
    def test_topic_exchange_includes_type_and_name(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config(exchange_type="topic", routing_key="sensor.reading"))

        reading = _temp_reading(name="temp 1")
        key = consumer._build_routing_key(reading)

        assert key == "sensor.reading.temperature.temp_1"

    def test_topic_exchange_replaces_spaces_in_name(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config(exchange_type="topic"))

        reading = _temp_reading(name="my sensor")
        key = consumer._build_routing_key(reading)

        assert " " not in key
        assert "my_sensor" in key

    def test_direct_exchange_returns_base_routing_key(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config(exchange_type="direct", routing_key="readings"))

        key = consumer._build_routing_key(_temp_reading())

        assert key == "readings"

    def test_fanout_exchange_returns_base_routing_key(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config(exchange_type="fanout", routing_key="sensor.reading"))

        key = consumer._build_routing_key(_temp_reading())

        assert key == "sensor.reading"

    def test_solar_reading_routing_key(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config(exchange_type="topic"))

        key = consumer._build_routing_key(_solar_reading(name="rover"))

        assert key == "sensor.reading.solar.rover"


# ---------------------------------------------------------------------------
# _handle_reading
# ---------------------------------------------------------------------------

class TestHandleReading:
    def _make_consumer(self, mock_bus, mock_connection, mock_channel, **cfg_overrides):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config(**cfg_overrides))
            consumer._ensure_connected()
        return consumer

    def test_publishes_temperature_reading(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        reading = _temp_reading()

        consumer._handle_reading(reading)

        mock_channel.basic_publish.assert_called_once()
        kwargs = mock_channel.basic_publish.call_args[1]
        assert kwargs["exchange"] == "pisolar"
        assert kwargs["routing_key"].startswith("sensor.reading.temperature")

    def test_publishes_json_payload(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        reading = _temp_reading(name="temp 1", value=22.5)

        consumer._handle_reading(reading)

        body = mock_channel.basic_publish.call_args[1]["body"]
        payload = json.loads(body)
        assert payload["name"] == "temp 1"
        assert payload["value"] == 22.5
        assert payload["type"] == "temperature"

    def test_publishes_solar_reading(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        reading = _solar_reading()

        consumer._handle_reading(reading)

        body = mock_channel.basic_publish.call_args[1]["body"]
        payload = json.loads(body)
        assert payload["battery_percentage"] == 100
        assert payload["battery_voltage"] == 13.2

    def test_message_properties_content_type(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)

        consumer._handle_reading(_temp_reading())

        props = mock_channel.basic_publish.call_args[1]["properties"]
        assert props.content_type == "application/json"

    def test_message_properties_persistent_delivery(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)

        consumer._handle_reading(_temp_reading())

        props = mock_channel.basic_publish.call_args[1]["properties"]
        # BasicProperties stores delivery_mode as the raw int value
        assert props.delivery_mode == pika.DeliveryMode.Persistent.value

    def test_skips_publish_when_connection_unavailable(self, mock_bus):
        """When _ensure_connected returns False the channel is never called."""
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection",
                   side_effect=Exception("no broker")), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())

        consumer._handle_reading(_temp_reading())  # should not raise

    def test_drops_connection_on_amqp_error(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        mock_channel.basic_publish.side_effect = pika.exceptions.AMQPError("broken pipe")

        consumer._handle_reading(_temp_reading())

        assert consumer._connection is None
        assert consumer._channel is None

    def test_drops_connection_on_generic_error(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        mock_channel.basic_publish.side_effect = OSError("socket error")

        consumer._handle_reading(_temp_reading())

        assert consumer._connection is None
        assert consumer._channel is None

    def test_reconnects_on_next_reading_after_error(self, mock_bus, mock_connection, mock_channel):
        consumer = self._make_consumer(mock_bus, mock_connection, mock_channel)
        mock_channel.basic_publish.side_effect = [
            pika.exceptions.AMQPError("first call fails"),
            None,  # second call succeeds
        ]

        # First reading drops the connection
        consumer._handle_reading(_temp_reading())
        assert consumer._connection is None

        # Patch a fresh connection for the second reading
        fresh_conn = MagicMock()
        fresh_conn.is_closed = False
        fresh_channel = MagicMock()
        fresh_conn.channel.return_value = fresh_channel

        with patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=fresh_conn), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer._handle_reading(_temp_reading())

        fresh_channel.basic_publish.assert_called_once()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

class TestClose:
    def test_unsubscribes_from_event_bus(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())

        consumer.close()

        mock_bus.unsubscribe.assert_called_once_with(
            SENSOR_READING_EVENT, consumer._handle_reading
        )

    def test_closes_open_connection(self, mock_bus, mock_connection, mock_channel):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus), \
             patch("pisolar.services.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection), \
             patch("pisolar.services.rabbitmq_consumer.pika.URLParameters"):
            consumer = RabbitMQConsumer(_make_config())
            consumer._ensure_connected()

        consumer.close()

        mock_connection.close.assert_called_once()
        assert consumer._connection is None

    def test_close_with_no_connection_does_not_raise(self, mock_bus):
        with patch("pisolar.services.rabbitmq_consumer.get_event_bus", return_value=mock_bus):
            consumer = RabbitMQConsumer(_make_config())

        consumer.close()  # _connection is None – should not raise
