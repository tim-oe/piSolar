"""Renogy device type enumeration."""

from enum import Enum


class DeviceType(str, Enum):
    """Supported Renogy device types."""

    CONTROLLER = "controller"
    DCC = "dcc"
    ROVER = "rover"
    WANDERER = "wanderer"
