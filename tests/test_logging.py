"""Tests for logging configuration module."""

import logging
from pathlib import Path

import pytest

from pisolar.logging_config import get_logger, setup_logging


class TestLoggingConfig:
    """Tests for logging configuration."""

    def test_get_logger(self):
        """Test getting a child logger."""
        logger = get_logger("test_module")

        assert logger.name == "pisolar.test_module"

    def test_setup_logging(self, tmp_path: Path):
        """Test setting up logging from YAML file."""
        config_content = """
version: 1
disable_existing_loggers: no
formatters:
    simple:
        format: "%(levelname)s - %(message)s"
handlers:
    console:
        class: logging.StreamHandler
        level: DEBUG
        formatter: simple
        stream: ext://sys.stdout
loggers:
    pisolar:
        level: DEBUG
        handlers: [console]
        propagate: no
"""
        config_file = tmp_path / "logging.yaml"
        config_file.write_text(config_content)

        setup_logging(config_file)
        logger = logging.getLogger("pisolar")

        assert logger.name == "pisolar"

    def test_setup_logging_missing_file_raises(self, tmp_path: Path):
        """Test that missing config file raises an error."""
        with pytest.raises(FileNotFoundError):
            setup_logging(tmp_path / "nonexistent.yaml")

    def test_env_variable_substitution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test !ENV tag substitutes environment variables."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "WARNING")

        config_content = """
version: 1
disable_existing_loggers: no
handlers:
    console:
        class: logging.StreamHandler
        level: !ENV ${TEST_LOG_LEVEL:DEBUG}
        stream: ext://sys.stdout
loggers:
    pisolar:
        level: !ENV ${TEST_LOG_LEVEL:DEBUG}
        handlers: [console]
        propagate: no
"""
        config_file = tmp_path / "logging.yaml"
        config_file.write_text(config_content)

        setup_logging(config_file)
        logger = logging.getLogger("pisolar")

        assert logger.level == logging.WARNING
