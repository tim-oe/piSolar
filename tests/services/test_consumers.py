"""Tests for LoggingConsumer."""

from unittest.mock import MagicMock, patch

from pisolar.event_bus import EventBus
from pisolar.sensors.renogy.reading import SolarReading
from pisolar.sensors.temperature.reading import TemperatureReading
from pisolar.services.consumers import LoggingConsumer
from pisolar.services.metrics import SENSOR_READING_EVENT
from tests.fixtures import RENOGY_RAW_DATA


class TestLoggingConsumer:
    """Tests for LoggingConsumer."""

    def test_create_logging_consumer(self):
        """Test creating a logging consumer subscribes to events."""
        with patch("pisolar.services.consumers.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            LoggingConsumer()  # Creates subscription as side effect

            mock_bus.subscribe.assert_called_once()
            call_args = mock_bus.subscribe.call_args
            assert call_args[0][0] == SENSOR_READING_EVENT

    def test_handle_reading_logs_data(self):
        """Test that handling a reading logs the data."""
        with patch("pisolar.services.consumers.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            consumer = LoggingConsumer()

            reading = TemperatureReading(
                type="temperature",
                name="temp 1",
                value=22.5,
            )

            with patch("pisolar.services.consumers.LoggingConsumer._logger") as mock_logger:
                consumer._handle_reading(reading)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args[0]
                assert "sensor.reading" in call_args[0]
                assert call_args[1] == "temperature"
                assert call_args[2] == "temp 1"

    def test_handle_solar_reading(self):
        """Test handling a solar reading."""
        with patch("pisolar.services.consumers.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            consumer = LoggingConsumer()

            reading = SolarReading.from_raw_data(
                sensor_type="solar",
                name="BT-TH-A5ABF10E",
                data=RENOGY_RAW_DATA,
            )

            with patch("pisolar.services.consumers.LoggingConsumer._logger") as mock_logger:
                consumer._handle_reading(reading)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args[0]
                assert call_args[1] == "solar"
                assert call_args[2] == "BT-TH-A5ABF10E"
