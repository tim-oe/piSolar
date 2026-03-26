"""MQTT consumer that publishes sensor readings to an MQTT broker."""

import json

import paho.mqtt.client as mqtt

from pisolar.config.mqtt_config import MqttConfig
from pisolar.event_bus import get_event_bus
from pisolar.logging_config import get_logger
from pisolar.sensors.renogy.solar_reading import SolarReading
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.services.metrics_service import SENSOR_READING_EVENT


class MqttConsumer:
    """Consumer that publishes sensor readings to an MQTT broker.

    Subscribes to the event bus and forwards readings as JSON to
    configured MQTT topics based on reading type.
    """

    _logger = get_logger("services.mqtt")

    def __init__(self, config: MqttConfig) -> None:
        self._config = config
        self._client = mqtt.Client(
            client_id=config.client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        if config.username is not None:
            password = (
                config.password.get_secret_value()
                if config.password is not None
                else None
            )
            self._client.username_pw_set(config.username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.enable_logger(self._logger)

        self._connect()

        self._event_bus = get_event_bus()
        self._event_bus.subscribe(SENSOR_READING_EVENT, self._handle_reading)

    def _connect(self) -> None:
        """Connect to the MQTT broker and start the network loop."""
        try:
            self._client.connect(
                self._config.host,
                self._config.port,
                keepalive=self._config.keepalive,
            )
            self._client.loop_start()
        except Exception:
            self._logger.exception(
                "Failed to connect to MQTT broker at %s:%d",
                self._config.host,
                self._config.port,
            )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        rc: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        if rc == mqtt.ReasonCode(mqtt.CONNACK_ACCEPTED):
            self._logger.info(
                "Connected to MQTT broker at %s:%d",
                self._config.host,
                self._config.port,
            )
        else:
            self._logger.error("MQTT connection refused: %s", rc)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        rc: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        if rc.value != 0:
            self._logger.warning("Unexpected MQTT disconnect: %s", rc)

    def _resolve_topic(self, reading: SensorReading) -> str | None:
        """Map a reading type to its configured MQTT topic."""
        if isinstance(reading, SolarReading):
            return self._config.topics.solar
        if isinstance(reading, TemperatureReading):
            return self._config.topics.temperature
        return None

    def _handle_reading(self, reading: SensorReading) -> None:
        """Serialize a sensor reading and publish it to the broker."""
        topic = self._resolve_topic(reading)
        if topic is None:
            self._logger.debug("No MQTT topic for reading type: %s", reading.type)
            return

        payload = json.dumps(reading.to_dict())
        result = self._client.publish(
            topic, payload, qos=self._config.qos, retain=self._config.retain
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self._logger.error(
                "Failed to publish to %s: %s", topic, mqtt.error_string(result.rc)
            )
        else:
            self._logger.debug("Published to %s (%d bytes)", topic, len(payload))

    def stop(self) -> None:
        """Disconnect from the broker and stop the network loop."""
        self._client.loop_stop()
        self._client.disconnect()
        self._logger.info("MQTT consumer stopped")
