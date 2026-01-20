"""Logging configuration from external YAML file."""

import logging
import logging.config

from pyaml_env import parse_config


def setup_logging(config_path: str) -> None:
    """Configure logging from a YAML file with environment variable support."""
    config = parse_config(config_path)
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"pisolar.{name}")
