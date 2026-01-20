"""Tests for services module."""

import pytest
from unittest.mock import MagicMock, patch

from pisolar.sensors.temperature_reading import TemperatureReading
from pisolar.sensors.solar_reading import SolarReading
from pisolar.services.metrics import MetricsService, SENSOR_READING_EVENT
from pisolar.services.consumers import LoggingConsumer
from pisolar.event_bus import EventBus

from tests.fixtures import RENOGY_RAW_DATA, TEMPERATURE_READINGS


class TestMetricsService:
    """Tests for MetricsService."""

    def test_create_metrics_service(self):
        """Test creating a metrics service."""
        service = MetricsService()
        assert service._event_bus is not None

    def test_record_publishes_events(self):
        """Test that record() publishes events for each reading."""
        with patch("pisolar.services.metrics.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            service = MetricsService()

            readings = [
                TemperatureReading(
                    type="temperature",
                    name="temp 1",
                    value=22.5,
                ),
                TemperatureReading(
                    type="temperature",
                    name="temp 2",
                    value=23.1,
                ),
            ]

            service.record(readings)

            # Should publish once for each reading
            assert mock_bus.publish.call_count == 2
            # Verify event type
            mock_bus.publish.assert_any_call(SENSOR_READING_EVENT, readings[0])
            mock_bus.publish.assert_any_call(SENSOR_READING_EVENT, readings[1])

    def test_record_solar_reading(self):
        """Test recording a solar reading."""
        with patch("pisolar.services.metrics.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            service = MetricsService()

            reading = SolarReading.from_raw_data(
                sensor_type="solar",
                name="BT-2",
                data=RENOGY_RAW_DATA,
            )

            service.record([reading])

            mock_bus.publish.assert_called_once_with(SENSOR_READING_EVENT, reading)

    def test_record_empty_list(self):
        """Test recording empty list of readings."""
        with patch("pisolar.services.metrics.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            service = MetricsService()
            service.record([])

            # Should not publish any events
            mock_bus.publish.assert_not_called()


class TestLoggingConsumer:
    """Tests for LoggingConsumer."""

    def test_create_logging_consumer(self):
        """Test creating a logging consumer subscribes to events."""
        with patch("pisolar.services.consumers.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            consumer = LoggingConsumer()

            # Should subscribe to sensor reading events
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

            # Call the handler directly
            with patch("pisolar.services.consumers.logger") as mock_logger:
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

            with patch("pisolar.services.consumers.logger") as mock_logger:
                consumer._handle_reading(reading)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args[0]
                assert call_args[1] == "solar"
                assert call_args[2] == "BT-TH-A5ABF10E"
