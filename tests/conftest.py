"""Pytest configuration and shared fixtures."""

import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="Run integration tests that require real hardware",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --runintegration is passed."""
    if config.getoption("--runintegration"):
        # Don't skip integration tests
        return

    skip_integration = pytest.mark.skip(
        reason="Integration test - run with --runintegration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
