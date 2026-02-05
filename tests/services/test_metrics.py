"""Tests for MetricsService."""

from unittest.mock import MagicMock, patch

from pisolar.event_bus import EventBus
from pisolar.sensors.renogy import SolarReading
from pisolar.sensors.temperature import TemperatureReading
from pisolar.services.metrics import SENSOR_READING_EVENT, MetricsService
from tests.fixtures import RENOGY_RAW_DATA


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

            assert mock_bus.publish.call_count == 2
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

            mock_bus.publish.assert_not_called()
