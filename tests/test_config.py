"""Tests for configuration module."""

from pathlib import Path

import pytest

from pisolar.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_from_yaml_file(self, tmp_path: Path):
        """Test loading settings from YAML file."""
        config_content = """
temperature:
  enabled: false
metrics:
  output_dir: /custom/path
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        settings = Settings.from_yaml(str(config_file))

        assert settings.temperature.enabled is False
        assert settings.metrics.output_dir == "/custom/path"

    def test_from_yaml_missing_file_raises(self, tmp_path: Path):
        """Test that missing config file raises an error."""
        with pytest.raises(FileNotFoundError):
            Settings.from_yaml(str(tmp_path / "nonexistent.yaml"))

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test environment variable substitution via !ENV tag."""
        monkeypatch.setenv("TEST_TEMP_ENABLED", "false")

        config_content = """
temperature:
  enabled: !ENV ${TEST_TEMP_ENABLED:true}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        settings = Settings.from_yaml(str(config_file))

        assert settings.temperature.enabled is False

    def test_env_default_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test !ENV tag uses default when env var not set."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        config_content = """
temperature:
  enabled: !ENV ${NONEXISTENT_VAR:true}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        settings = Settings.from_yaml(str(config_file))

        assert settings.temperature.enabled is True

    def test_cron_schedule_default(self, tmp_path: Path):
        """Test default cron schedule."""
        config_content = "{}"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        settings = Settings.from_yaml(str(config_file))

        assert settings.temperature.schedule.cron == "*/5 * * * *"
        assert settings.temperature.schedule.enabled is True

    def test_renogy_config(self, tmp_path: Path):
        """Test Renogy configuration."""
        config_content = """
renogy:
  enabled: true
  mac_address: "AA:BB:CC:DD:EE:FF"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        settings = Settings.from_yaml(str(config_file))

        assert settings.renogy.enabled is True
        assert settings.renogy.mac_address == "AA:BB:CC:DD:EE:FF"
        assert settings.renogy.device_alias == "BT-2"
