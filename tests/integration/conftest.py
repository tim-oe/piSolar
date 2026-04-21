"""Shared fixtures for integration tests.

Integration tests run against real hardware using ~/.config.yaml.
They are excluded from the default pytest run and must be invoked explicitly:

    poetry run pytest -m integration
"""

import os
from pathlib import Path

import pytest

from pisolar.config.settings import Settings

_CONFIG_PATH = os.path.expanduser("~/.config.yaml")
_LOG_CONFIG_PATH = str(Path(__file__).parents[2] / "config" / "logging.yaml")


def pytest_collection_modifyitems(config, items):
    """Skip all integration tests when ~/.config.yaml is absent."""
    if not os.path.exists(_CONFIG_PATH):
        skip = pytest.mark.skip(reason=f"Integration config not found: {_CONFIG_PATH}")
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Load settings from ~/.config.yaml once for the whole session."""
    if not os.path.exists(_CONFIG_PATH):
        pytest.skip(f"Integration config not found: {_CONFIG_PATH}")
    return Settings.from_yaml(_CONFIG_PATH)


@pytest.fixture(scope="session")
def config_path() -> str:
    return _CONFIG_PATH


@pytest.fixture(scope="session")
def log_config_path() -> str:
    return _LOG_CONFIG_PATH
