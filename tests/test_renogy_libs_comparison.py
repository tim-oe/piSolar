"""
Comprehensive comparison tests for all Renogy Python libraries.

This file tests and compares 4 Renogy libraries to determine the best fit
for piSolar's BT-2 Bluetooth integration.

LIBRARIES TESTED:
================

1. renogy-ble (PyPI)
   - Protocol: BLE (Bluetooth Low Energy)
   - Best for: BT-1/BT-2 Bluetooth modules (OUR USE CASE)
   - Error handling: Warnings (requires validation)

2. py-renogy / renogyapi (PyPI)
   - Protocol: Cloud API (HTTPS)
   - Best for: Cloud-connected Renogy systems
   - Requires: Renogy account, API keys
   - NOT suitable for local-only BT-2

3. modbus-solar (PyPI)
   - Protocol: RS485/Modbus (Serial)
   - Best for: Wired serial connections
   - Requires: USB-RS485 adapter, /dev/ttyUSB0
   - NOT suitable for Bluetooth

4. renogy-modbus-lib-python (PyPI)
   - Protocol: RS485/Modbus (Serial)
   - Best for: Direct Modbus communication
   - Requires: Serial connection
   - NOT suitable for Bluetooth

CONCLUSION:
==========
Only renogy-ble supports BLE/Bluetooth communication.
The others are for different connection types (Cloud API, RS485).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.fixtures import RENOGY_RAW_DATA, RENOGY_CONFIG


# =============================================================================
# Library 1: renogy-ble (BLE/Bluetooth) - SUITABLE FOR BT-2
# =============================================================================

class TestRenogyBle:
    """Tests for renogy-ble library (BLE/Bluetooth)."""

    def test_import(self):
        """Test library can be imported."""
        from renogy_ble import RenogyParser, RenogyBleClient, RenogyBLEDevice
        assert RenogyParser is not None
        assert RenogyBleClient is not None
        assert RenogyBLEDevice is not None

    def test_protocol(self):
        """Document the protocol used."""
        protocol = "BLE (Bluetooth Low Energy)"
        connection_type = "Wireless Bluetooth via BT-1/BT-2 module"
        suitable_for_bt2 = True

        assert suitable_for_bt2 is True

    def test_dependencies(self):
        """Test library dependencies."""
        # renogy-ble depends on bleak (BLE library)
        import bleak
        assert bleak is not None

    def test_error_handling_approach(self):
        """Document error handling approach."""
        from renogy_ble import RenogyParser

        # Returns empty dict with warnings instead of raising
        result = RenogyParser.parse(b"", device_type="controller", register=256)
        assert isinstance(result, dict)

        error_handling = "warnings"  # Not exceptions
        requires_validation = True
        assert requires_validation is True

    def test_async_support(self):
        """Test async/await support."""
        from renogy_ble import RenogyBleClient
        import asyncio
        import inspect

        client = RenogyBleClient()
        # read_device should be async
        assert inspect.iscoroutinefunction(client.read_device)

    def test_output_format(self):
        """Test output data format."""
        from renogy_ble import RenogyParser

        # Parse a known battery type response
        raw_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x90, 0x53])
        result = RenogyParser.parse(raw_data, device_type="controller", register=57348)

        assert isinstance(result, dict)
        assert "battery_type" in result
        assert result["battery_type"] == "lithium"


# =============================================================================
# Library 2: py-renogy / renogyapi (Cloud API) - NOT SUITABLE
# =============================================================================

class TestPyRenogy:
    """Tests for py-renogy library (Cloud API)."""

    def test_import(self):
        """Test library can be imported."""
        from renogyapi import Renogy
        assert Renogy is not None

    def test_protocol(self):
        """Document the protocol used."""
        protocol = "HTTPS Cloud API"
        connection_type = "Internet to Renogy cloud servers"
        suitable_for_bt2 = False  # Requires cloud, not local BLE

        assert suitable_for_bt2 is False

    def test_requires_api_credentials(self):
        """Test that library requires API credentials."""
        from renogyapi import Renogy
        import inspect

        sig = inspect.signature(Renogy.__init__)
        params = list(sig.parameters.keys())

        # Requires secret_key and access_key
        assert "secret_key" in params
        assert "access_key" in params

    def test_is_async(self):
        """Test that library uses async."""
        from renogyapi import Renogy
        import inspect

        # Methods should be async (aiohttp based)
        client = Renogy(secret_key="test", access_key="test")
        assert inspect.iscoroutinefunction(client.get_devices)
        assert inspect.iscoroutinefunction(client.get_realtime_data)

    def test_exceptions_used(self):
        """Test that library uses exceptions for errors."""
        from renogyapi import NotAuthorized, RateLimit, NoDevices, UrlNotFound

        # Has proper exception classes - good error handling
        assert issubclass(NotAuthorized, Exception)
        assert issubclass(RateLimit, Exception)
        assert issubclass(NoDevices, Exception)

    def test_not_suitable_reason(self):
        """Document why this library is not suitable for BT-2."""
        reasons = [
            "Requires Renogy cloud account and API keys",
            "Communicates via internet, not local Bluetooth",
            "Device must be registered with Renogy cloud",
            "Depends on Renogy servers being available",
            "Cannot work offline/locally",
        ]
        assert len(reasons) > 0


# =============================================================================
# Library 3: modbus-solar (RS485/Modbus Serial) - NOT SUITABLE
# =============================================================================

class TestModbusSolar:
    """Tests for modbus-solar library (RS485/Modbus)."""

    def test_import(self):
        """Test library can be imported."""
        from modbus_solar.get import get_all
        assert get_all is not None

    def test_protocol(self):
        """Document the protocol used."""
        protocol = "Modbus RTU over RS485 serial"
        connection_type = "Wired USB-RS485 adapter"
        suitable_for_bt2 = False  # RS485, not Bluetooth

        assert suitable_for_bt2 is False

    def test_requires_serial_device(self):
        """Test that library requires serial device path."""
        from modbus_solar.get import get_all
        import inspect

        sig = inspect.signature(get_all)
        params = list(sig.parameters.keys())

        # Requires modbus_device (serial port path)
        assert "modbus_device" in params

        # Default is /dev/ttyUSB0
        defaults = {p: sig.parameters[p].default for p in params}
        assert defaults["modbus_device"] == "/dev/ttyUSB0"

    def test_uses_minimalmodbus(self):
        """Test that library uses minimalmodbus for serial communication."""
        import minimalmodbus
        assert minimalmodbus is not None

    def test_synchronous_api(self):
        """Test that library is synchronous (blocking)."""
        from modbus_solar.get import get_all
        import inspect

        # Not async - blocking serial communication
        assert not inspect.iscoroutinefunction(get_all)

    def test_not_suitable_reason(self):
        """Document why this library is not suitable for BT-2."""
        reasons = [
            "Uses RS485 serial connection, not Bluetooth",
            "Requires physical USB-RS485 adapter",
            "Direct wire connection to charge controller",
            "BT-2 uses Bluetooth, not RS485",
            "Different physical layer",
        ]
        assert len(reasons) > 0


# =============================================================================
# Library 4: renogy-modbus-lib-python (Official, RS485) - NOT SUITABLE
# =============================================================================

class TestRenogyModbusLibPython:
    """Tests for renogy-modbus-lib-python (Official Renogy library)."""

    def test_import(self):
        """Test library can be imported."""
        import renogy_lib_python
        from renogy_lib_python import EnhancedModbusClient
        assert EnhancedModbusClient is not None

    def test_protocol(self):
        """Document the protocol used."""
        protocol = "Modbus RTU over RS485 serial"
        connection_type = "Wired serial connection"
        suitable_for_bt2 = False  # RS485, not Bluetooth

        assert suitable_for_bt2 is False

    def test_modules_available(self):
        """Test available modules."""
        import renogy_lib_python

        # Check available modules
        assert hasattr(renogy_lib_python, "battery_protocol")
        assert hasattr(renogy_lib_python, "controller_protocol")
        assert hasattr(renogy_lib_python, "modbus_comm")
        assert hasattr(renogy_lib_python, "cal_tools")

    def test_version(self):
        """Test library version."""
        import renogy_lib_python
        assert hasattr(renogy_lib_python, "__version__")

    def test_not_suitable_reason(self):
        """Document why this library is not suitable for BT-2."""
        reasons = [
            "Designed for direct Modbus/RS485 serial connection",
            "No Bluetooth support",
            "Requires USB-serial adapter",
            "BT-2 uses BLE, not RS485",
            "Official but for different hardware setup",
        ]
        assert len(reasons) > 0


# =============================================================================
# Comparison Summary
# =============================================================================

class TestLibraryComparison:
    """Summary comparison of all libraries."""

    def test_protocol_comparison(self):
        """Compare protocols supported by each library."""
        libraries = {
            "renogy-ble": {
                "protocol": "BLE (Bluetooth Low Energy)",
                "suitable_for_bt2": True,
                "connection": "Wireless Bluetooth",
                "requires": "Bluetooth adapter",
            },
            "py-renogy": {
                "protocol": "HTTPS Cloud API",
                "suitable_for_bt2": False,
                "connection": "Internet",
                "requires": "Renogy cloud account, API keys",
            },
            "modbus-solar": {
                "protocol": "Modbus RTU/RS485",
                "suitable_for_bt2": False,
                "connection": "Wired serial",
                "requires": "USB-RS485 adapter",
            },
            "renogy-modbus-lib-python": {
                "protocol": "Modbus RTU/RS485",
                "suitable_for_bt2": False,
                "connection": "Wired serial",
                "requires": "USB-RS485 adapter",
            },
        }

        # Only renogy-ble supports BT-2 Bluetooth
        bt2_compatible = [name for name, info in libraries.items() if info["suitable_for_bt2"]]
        assert bt2_compatible == ["renogy-ble"]

    def test_error_handling_comparison(self):
        """Compare error handling approaches."""
        error_handling = {
            "renogy-ble": {
                "approach": "warnings",
                "requires_validation": True,
                "fail_fast": False,
            },
            "py-renogy": {
                "approach": "exceptions",
                "requires_validation": False,
                "fail_fast": True,
            },
            "modbus-solar": {
                "approach": "exceptions",  # minimalmodbus raises on errors
                "requires_validation": False,
                "fail_fast": True,
            },
            "renogy-modbus-lib-python": {
                "approach": "exceptions",
                "requires_validation": False,
                "fail_fast": True,
            },
        }

        # py-renogy has better error handling than renogy-ble
        exception_based = [
            name for name, info in error_handling.items()
            if info["approach"] == "exceptions"
        ]
        assert len(exception_based) == 3
        assert "renogy-ble" not in exception_based

    def test_installation_comparison(self):
        """Compare installation methods."""
        installation = {
            "renogy-ble": {"pypi": True, "pip_install": "pip install renogy-ble"},
            "py-renogy": {"pypi": True, "pip_install": "pip install py-renogy"},
            "modbus-solar": {"pypi": True, "pip_install": "pip install modbus-solar"},
            "renogy-modbus-lib-python": {"pypi": True, "pip_install": "pip install renogy-modbus-lib-python"},
            "cyrils/renogy-bt": {"pypi": False, "pip_install": None},  # For comparison
        }

        # All PyPI libraries are easier to install than cyrils/renogy-bt
        pypi_libs = [name for name, info in installation.items() if info["pypi"]]
        assert len(pypi_libs) == 4

    def test_final_recommendation(self):
        """Document final recommendation for BT-2 integration."""
        recommendation = {
            "for_bt2_bluetooth": "renogy-ble",
            "alternative": "cyrils/renogy-bt",
            "reason_for_alternative": "Exception-based error handling is cleaner",
            "not_suitable": [
                "py-renogy (Cloud API only)",
                "modbus-solar (RS485 only)",
                "renogy-modbus-lib-python (RS485 only)",
            ],
        }

        # For BT-2, only renogy-ble is suitable from PyPI libraries
        assert recommendation["for_bt2_bluetooth"] == "renogy-ble"

        # But cyrils/renogy-bt has better error handling
        tradeoff = """
        renogy-ble:
          + On PyPI, easy to install
          + Active maintenance
          + Modern async API
          - Warning-based errors require validation at every call

        cyrils/renogy-bt:
          + Exception-based errors (fail-fast)
          + Single try/except handles all errors
          - Not on PyPI (PYTHONPATH required)
          - Async disconnect bugs (we fixed these)
        """
        assert "renogy-ble" in tradeoff
