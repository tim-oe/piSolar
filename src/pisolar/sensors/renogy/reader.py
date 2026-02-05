"""Abstract base class for Renogy device readers."""

from abc import ABC, abstractmethod
from typing import Any


class RenogyReader(ABC):
    """Abstract base class for reading data from Renogy devices.

    Implementations handle specific connection types (Bluetooth, Serial/Modbus).
    """

    @abstractmethod
    async def read(self) -> dict[str, Any]:
        """Read data from the Renogy device.

        Returns:
            Dictionary containing the raw data from the device.
            Keys should match SolarReading field names where possible.

        Raises:
            RuntimeError: If the read fails after retries.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources held by the reader."""
        pass

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Return a friendly name for the device being read."""
        pass

    @property
    @abstractmethod
    def connection_type(self) -> str:
        """Return the connection type identifier (e.g., 'bluetooth', 'modbus')."""
        pass
