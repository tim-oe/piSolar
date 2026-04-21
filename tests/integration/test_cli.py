"""Integration tests for the piSolar CLI against real hardware.

Uses ~/.config.yaml and config/logging.yaml to exercise the full
read-once and check commands end-to-end with live sensors.

Run with:
    poetry run pytest -m integration
"""

import pytest
from click.testing import CliRunner

from pisolar.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.integration
class TestReadOnceIntegration:
    """End-to-end read-once against live sensors from ~/.config.yaml."""

    def test_exits_successfully(self, runner, config_path, log_config_path):
        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "read-once"]
        )
        assert result.exit_code == 0, (
            f"read-once exited with {result.exit_code}:\n{result.output}"
        )

    def test_produces_readings(self, runner, config_path, log_config_path):
        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "read-once"]
        )
        assert "Total:" in result.output, (
            f"No 'Total:' line in output — sensors may have failed:\n{result.output}"
        )
        assert "No readings available" not in result.output

    def test_temperature_readings_displayed(
        self, runner, config_path, log_config_path, integration_settings
    ):
        if not integration_settings.temperature.enabled:
            pytest.skip("temperature.enabled is false in ~/.config.yaml")

        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "read-once"]
        )
        assert "[temp]" in result.output, (
            f"No temperature readings in output:\n{result.output}"
        )

    def test_renogy_readings_displayed(
        self, runner, config_path, log_config_path, integration_settings
    ):
        if not integration_settings.renogy.enabled:
            pytest.skip("renogy.enabled is false in ~/.config.yaml")

        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "read-once"]
        )
        assert "[solar/" in result.output, (
            f"No Renogy readings in output:\n{result.output}"
        )


@pytest.mark.integration
class TestCheckIntegration:
    """End-to-end check command against live sensors from ~/.config.yaml."""

    def test_check_exits_successfully(self, runner, config_path, log_config_path):
        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "check"]
        )
        assert result.exit_code == 0, (
            f"check exited with {result.exit_code}:\n{result.output}"
        )

    def test_check_reports_temperature(
        self, runner, config_path, log_config_path, integration_settings
    ):
        if not integration_settings.temperature.enabled:
            pytest.skip("temperature.enabled is false in ~/.config.yaml")

        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "check"]
        )
        assert "Temperature sensors: ✓" in result.output, (
            f"Temperature check failed:\n{result.output}"
        )


@pytest.mark.integration
class TestShowConfigIntegration:
    """Verify show-config parses ~/.config.yaml without errors."""

    def test_show_config_exits_successfully(self, runner, config_path, log_config_path):
        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "show-config"]
        )
        assert result.exit_code == 0, (
            f"show-config exited with {result.exit_code}:\n{result.output}"
        )

    def test_show_config_lists_sensors(
        self, runner, config_path, log_config_path, integration_settings
    ):
        result = runner.invoke(
            main, ["-c", config_path, "-l", log_config_path, "show-config"]
        )
        assert "Temperature sensor:" in result.output
        for s in integration_settings.temperature.sensors:
            label = s.name or str(s.id)
            assert label in result.output, (
                f"Sensor '{label}' not shown in show-config output"
            )
