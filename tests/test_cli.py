"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pisolar.cli import main, DEFAULT_CONFIG, DEFAULT_LOG_CONFIG


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_files(tmp_path):
    """Create temporary config files for testing."""
    config = tmp_path / "config.yaml"
    config.write_text("""
temperature:
  enabled: true
  sensors:
    - name: test_sensor
      address: "0000007c6850"
  schedule:
    cron: "*/5 * * * *"
    enabled: true

renogy:
  enabled: false
  mac_address: ""
  device_alias: "BT-2"
  schedule:
    cron: "*/5 * * * *"
    enabled: false

metrics:
  output_dir: /tmp/pisolar_test
""")

    log_config = tmp_path / "logging.yaml"
    log_config.write_text("""
version: 1
disable_existing_loggers: false
handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    stream: ext://sys.stdout
root:
  level: DEBUG
  handlers: [console]
""")

    return {"config": str(config), "log_config": str(log_config)}


class TestMainGroup:
    """Tests for main CLI group."""

    def test_main_help(self, runner):
        """Test main command shows help."""
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "piSolar" in result.output
        assert "--config" in result.output
        assert "--log-config" in result.output

    def test_main_shows_commands(self, runner):
        """Test main shows available commands."""
        result = runner.invoke(main, ["--help"])

        assert "run" in result.output
        assert "check" in result.output
        assert "read-once" in result.output
        assert "show-config" in result.output


class TestShowConfigCommand:
    """Tests for show-config command."""

    def test_show_config(self, runner, config_files):
        """Test show-config displays configuration."""
        result = runner.invoke(
            main,
            ["-c", config_files["config"], "-l", config_files["log_config"], "show-config"],
        )

        assert result.exit_code == 0
        assert "Current configuration:" in result.output
        assert "Temperature sensor:" in result.output
        assert "enabled: True" in result.output
        assert "test_sensor" in result.output
        assert "Renogy sensor:" in result.output


class TestCheckCommand:
    """Tests for check command."""

    @patch("pisolar.cli.TemperatureSensor")
    def test_check_with_temp_sensors(self, mock_temp_class, runner, config_files):
        """Test check command with temperature sensors."""
        mock_sensor = MagicMock()
        mock_sensor.read.return_value = [MagicMock()]
        mock_temp_class.return_value = mock_sensor

        result = runner.invoke(
            main,
            ["-c", config_files["config"], "-l", config_files["log_config"], "check"],
        )

        assert result.exit_code == 0
        assert "Checking sensors..." in result.output
        assert "Temperature sensors:" in result.output

    @patch("pisolar.cli.TemperatureSensor")
    def test_check_temp_sensor_error(self, mock_temp_class, runner, config_files):
        """Test check command when temperature sensor fails."""
        mock_sensor = MagicMock()
        mock_sensor.read.side_effect = Exception("Sensor error")
        mock_temp_class.return_value = mock_sensor

        result = runner.invoke(
            main,
            ["-c", config_files["config"], "-l", config_files["log_config"], "check"],
        )

        assert result.exit_code == 0
        assert "Temperature sensors: ✗" in result.output
        assert "Sensor error" in result.output


class TestReadOnceCommand:
    """Tests for read-once command."""

    @patch("pisolar.cli.TemperatureSensor")
    def test_read_once_with_temp_sensors(self, mock_temp_class, runner, config_files):
        """Test read-once command with temperature sensors."""
        mock_reading = MagicMock()
        mock_reading.name = "test_sensor"
        mock_reading.value = 22.5
        mock_reading.unit = "celsius"

        mock_sensor = MagicMock()
        mock_sensor.read.return_value = [mock_reading]
        mock_temp_class.return_value = mock_sensor

        result = runner.invoke(
            main,
            ["-c", config_files["config"], "-l", config_files["log_config"], "read-once"],
        )

        assert result.exit_code == 0
        assert "Reading sensors..." in result.output
        assert "[temp] test_sensor: 22.50 celsius" in result.output
        assert "Total: 1 readings" in result.output

    @patch("pisolar.cli.RenogySensor")
    def test_read_once_with_renogy_sensor(self, mock_renogy_class, runner, tmp_path):
        """Test read-once command with Renogy sensor uses to_dict()."""
        from pisolar.sensors.solar_reading import SolarReading
        from tests.fixtures import RENOGY_RAW_DATA

        # Create a real SolarReading to test to_dict() is called
        mock_reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=RENOGY_RAW_DATA,
        )

        mock_sensor = MagicMock()
        mock_sensor.read.return_value = [mock_reading]
        mock_renogy_class.return_value = mock_sensor

        # Config with Renogy enabled
        config = tmp_path / "config.yaml"
        config.write_text("""
temperature:
  enabled: false
  sensors: []
  schedule:
    cron: "*/5 * * * *"
    enabled: false

renogy:
  enabled: true
  mac_address: "CC:45:A5:AB:F1:0E"
  device_alias: "BT-TH-A5ABF10E"
  schedule:
    cron: "*/5 * * * *"
    enabled: false

metrics:
  output_dir: /tmp/pisolar_test
""")

        log_config = tmp_path / "logging.yaml"
        log_config.write_text("""
version: 1
disable_existing_loggers: false
handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    stream: ext://sys.stdout
root:
  level: DEBUG
  handlers: [console]
""")

        result = runner.invoke(
            main,
            ["-c", str(config), "-l", str(log_config), "read-once"],
        )

        assert result.exit_code == 0
        assert "Reading sensors..." in result.output
        assert "[solar] BT-TH-A5ABF10E:" in result.output
        assert "battery_voltage" in result.output
        assert "13.2" in result.output
        assert "Total: 1 readings" in result.output

    def test_read_once_no_sensors_enabled(self, runner, tmp_path):
        """Test read-once with no sensors enabled."""
        config = tmp_path / "config.yaml"
        config.write_text("""
temperature:
  enabled: false
  sensors: []
  schedule:
    cron: "*/5 * * * *"
    enabled: false

renogy:
  enabled: false
  mac_address: ""
  device_alias: "BT-2"
  schedule:
    cron: "*/5 * * * *"
    enabled: false

metrics:
  output_dir: /tmp/pisolar_test
""")

        log_config = tmp_path / "logging.yaml"
        log_config.write_text("""
version: 1
disable_existing_loggers: false
handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    stream: ext://sys.stdout
root:
  level: DEBUG
  handlers: [console]
""")

        result = runner.invoke(
            main,
            ["-c", str(config), "-l", str(log_config), "read-once"],
        )

        assert result.exit_code == 1
        assert "No readings available" in result.output


class TestRunCommand:
    """Tests for run command."""

    @patch("pisolar.cli.SchedulerService")
    @patch("pisolar.cli.MetricsService")
    @patch("pisolar.cli.LoggingConsumer")
    def test_run_starts_scheduler(
        self, mock_consumer, mock_metrics, mock_scheduler_class, runner, config_files
    ):
        """Test run command starts the scheduler."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        # Make scheduler.start() raise KeyboardInterrupt to exit
        mock_scheduler.start.side_effect = KeyboardInterrupt()

        result = runner.invoke(
            main,
            ["-c", config_files["config"], "-l", config_files["log_config"], "run"],
            catch_exceptions=False,
        )

        # Verify scheduler was created and started
        mock_scheduler_class.assert_called_once()
        mock_scheduler.start.assert_called_once()
