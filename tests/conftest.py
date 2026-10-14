"""Pytest configuration and shared fixtures."""

import os

import pytest

from pisolar.event_bus import reset_event_bus

# w1thermsensor modprobes w1-gpio and w1-therm on import. The unit tests mock
# that library, and GitHub-hosted runners cannot load those kernel modules.
os.environ.setdefault("W1THERMSENSOR_NO_KERNEL_MODULE", "1")


@pytest.fixture(autouse=True)
def reset_event_bus_between_tests():
    """Give every test a clean EventBus so singleton state doesn't leak."""
    reset_event_bus()
    yield
    reset_event_bus()
