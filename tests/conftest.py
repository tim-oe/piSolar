"""Pytest configuration and shared fixtures."""

import pytest

from pisolar.event_bus import reset_event_bus


@pytest.fixture(autouse=True)
def reset_event_bus_between_tests():
    """Give every test a clean EventBus so singleton state doesn't leak."""
    reset_event_bus()
    yield
    reset_event_bus()
