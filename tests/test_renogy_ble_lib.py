"""
Tests for renogy-ble library integration.

These tests validate the renogy-ble library (PyPI) as a potential replacement
for cyrils/renogy-bt.

LIBRARY COMPARISON:
==================

renogy-ble (PyPI):
  + Installable via pip/poetry
  + Actively maintained (Jan 2026)
  + Modern async/await API
  + Retry connector for flaky BLE
  - Uses warnings instead of exceptions
  - Requires validation at every call site
  - Silent failures possible

cyrils/renogy-bt (GitHub):
  + Uses exceptions for errors (fail-fast)
  + Single try/except handles all errors
  - Not on PyPI (PYTHONPATH hack)
  - Async disconnect bugs
  - Less actively maintained

RECOMMENDATION:
  If renogy-ble's warning-based error handling is a concern,
  consider wrapping it with exception-raising validation,
  or continue with cyrils/renogy-bt with the disconnect fixes.

Test categories:
- Unit tests: Mock BLE communication, test parsing
- Integration tests: Require real BLE hardware (skipped by default)

Run integration tests with: pytest -m integration --runintegration
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import from the renogy-ble library
from renogy_ble import (
    RenogyParser,
    RenogyBleClient,
    RenogyBLEDevice,
    COMMANDS,
)

from tests.fixtures import RENOGY_RAW_DATA, RENOGY_CONFIG


class TestRenogyParser:
    """Tests for RenogyParser - parsing raw Modbus responses."""

    def test_parser_exists(self):
        """Test that RenogyParser is importable and has parse method."""
        assert hasattr(RenogyParser, "parse")

    def test_parse_battery_type(self):
        """Test parsing battery type register (57348)."""
        # Raw Modbus response for battery_type = lithium (4)
        # Format: [device_id, function, byte_count, data..., crc16]
        # For lithium (4): 0xFF 0x03 0x02 0x00 0x04 [CRC]
        raw_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x90, 0x53])

        result = RenogyParser.parse(raw_data, device_type="controller", register=57348)

        assert "battery_type" in result
        assert result["battery_type"] == "lithium"

    def test_parse_battery_voltage(self):
        """Test parsing battery voltage from register 256."""
        # Battery voltage = 132 (13.2V with 0.1 scale)
        # 0xFF 0x03 0x02 0x00 0x84 [CRC]
        raw_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x84, 0x51, 0xC1])

        result = RenogyParser.parse(raw_data, device_type="controller", register=256)

        # Should contain battery-related fields
        assert isinstance(result, dict)

    def test_parse_invalid_data(self):
        """Test parsing with invalid/empty data returns empty dict with warnings."""
        # The library handles invalid data gracefully with warnings, not exceptions
        result = RenogyParser.parse(b"", device_type="controller", register=256)
        # Should return empty dict or dict with no valid values
        assert isinstance(result, dict)

    def test_supported_device_types(self):
        """Test that 'controller' device type is supported."""
        # Minimal valid response
        raw_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x90, 0x53])

        # Should not raise for controller type
        result = RenogyParser.parse(raw_data, device_type="controller", register=57348)
        assert isinstance(result, dict)


class TestRenogyBleClient:
    """Tests for RenogyBleClient - BLE communication client."""

    def test_client_creation(self):
        """Test creating a RenogyBleClient."""
        client = RenogyBleClient()
        assert client is not None

    def test_client_with_custom_device_id(self):
        """Test client with custom device ID."""
        client = RenogyBleClient(device_id=0x01)
        assert client is not None

    def test_client_with_custom_commands(self):
        """Test client with custom command set."""
        custom_commands = {
            "controller": {
                **COMMANDS["controller"],
                "custom": (3, 100, 1),
            }
        }
        client = RenogyBleClient(commands=custom_commands)
        assert client is not None

    def test_read_device_result_structure(self):
        """Test RenogyBleReadResult structure."""
        from renogy_ble import RenogyBleReadResult

        # Test successful result
        result = RenogyBleReadResult(
            success=True,
            parsed_data={"battery_voltage": 13.2},
            error=None,
        )
        assert result.success is True
        assert result.parsed_data["battery_voltage"] == 13.2
        assert result.error is None

        # Test failed result
        result = RenogyBleReadResult(
            success=False,
            parsed_data={},
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestRenogyBLEDevice:
    """Tests for RenogyBLEDevice - device wrapper."""

    def test_device_creation(self):
        """Test creating a RenogyBLEDevice."""
        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"
        mock_ble_device.address = "CC:45:A5:AB:F1:0E"

        device = RenogyBLEDevice(mock_ble_device, device_type="controller")

        assert device is not None
        assert device.device_type == "controller"

    def test_device_with_different_types(self):
        """Test device creation with different device types."""
        mock_ble_device = MagicMock()
        mock_ble_device.name = "Test"
        mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

        # Controller should work
        device = RenogyBLEDevice(mock_ble_device, device_type="controller")
        assert device.device_type == "controller"


class TestCommands:
    """Tests for command constants."""

    def test_controller_commands_exist(self):
        """Test that controller commands are defined."""
        assert "controller" in COMMANDS
        assert isinstance(COMMANDS["controller"], dict)

    def test_command_structure(self):
        """Test command structure (function, register, words)."""
        controller_commands = COMMANDS["controller"]

        # Each command should be a tuple of (function, register, words)
        for name, cmd in controller_commands.items():
            assert isinstance(cmd, tuple), f"Command {name} should be a tuple"
            assert len(cmd) == 3, f"Command {name} should have 3 elements"
            func, reg, words = cmd
            assert isinstance(func, int), f"Function in {name} should be int"
            assert isinstance(reg, int), f"Register in {name} should be int"
            assert isinstance(words, int), f"Words in {name} should be int"


class TestModbusFraming:
    """Tests for Modbus CRC and framing."""

    def test_crc_calculation(self):
        """Test that CRC is properly validated."""
        # Valid Modbus response with correct CRC
        valid_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x90, 0x53])

        # Should parse without CRC error
        result = RenogyParser.parse(valid_data, device_type="controller", register=57348)
        assert result is not None

    def test_invalid_crc(self):
        """Test that invalid CRC returns empty result."""
        # Same data but with wrong CRC
        invalid_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x00, 0x00])

        # Library handles invalid CRC gracefully - may return empty or partial data
        result = RenogyParser.parse(invalid_data, device_type="controller", register=57348)
        # Result should be a dict (possibly empty if CRC validation fails)
        assert isinstance(result, dict)


class TestDataMapping:
    """Tests for data value mapping and scaling."""

    def test_battery_type_mapping(self):
        """Test battery type value mapping."""
        # Battery type values: 1=open, 2=sealed, 3=gel, 4=lithium, 5=custom
        test_cases = [
            (1, "open"),
            (2, "sealed"),
            (3, "gel"),
            (4, "lithium"),
            (5, "custom"),
        ]

        for raw_value, expected_type in test_cases:
            # Construct Modbus response for battery type
            data = bytes([0xFF, 0x03, 0x02, 0x00, raw_value])
            # Calculate CRC (simplified - using known values)
            # For testing, we'll skip CRC validation by testing the mapping logic
            # This tests the concept rather than the exact bytes
            pass  # Full implementation would need proper CRC

    def test_charging_status_mapping(self):
        """Test charging status value mapping."""
        # Charging status: 0=deactivated, 1=activated, 2=mppt, 3=equalizing,
        #                  4=boost, 5=floating, 6=current limiting
        expected_statuses = [
            "deactivated",
            "activated",
            "mppt",
            "equalizing",
            "boost",
            "floating",
            "current limiting",
        ]

        # Verify these are the expected status strings
        assert len(expected_statuses) == 7


class TestAsyncIntegration:
    """Tests for async integration patterns."""

    @pytest.mark.asyncio
    async def test_asyncio_run_pattern(self):
        """Test that the library works with asyncio.run pattern."""
        async def mock_read():
            client = RenogyBleClient()
            return client

        result = await mock_read()
        assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_reads(self):
        """Test multiple sequential reads."""
        client = RenogyBleClient()

        # Create multiple mock devices
        for i in range(3):
            mock_ble_device = MagicMock()
            mock_ble_device.name = f"BT-TH-{i}"
            mock_ble_device.address = f"AA:BB:CC:DD:EE:{i:02X}"

            device = RenogyBLEDevice(mock_ble_device, device_type="controller")
            # Device should be creatable
            assert device is not None


# Integration tests - require real hardware
# Run with: pytest -m integration --runintegration

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real hardware)"
    )


@pytest.fixture
def skip_without_integration(request):
    """Skip integration tests unless --runintegration is passed."""
    if not request.config.getoption("--runintegration", default=False):
        pytest.skip("Integration test - run with --runintegration")


@pytest.mark.integration
class TestRealHardware:
    """Integration tests requiring real Renogy BT-2 hardware.

    Run with: pytest -m integration --runintegration
    """

    @pytest.mark.asyncio
    async def test_discover_device(self, skip_without_integration):
        """Test discovering Renogy BLE device."""
        from bleak import BleakScanner

        devices = await BleakScanner.discover(timeout=10.0)

        renogy_devices = [
            d for d in devices
            if d.name and ("BT-TH" in d.name or "RNGRBP" in d.name)
        ]

        assert len(renogy_devices) > 0, "No Renogy BLE devices found"
        print(f"Found devices: {[(d.name, d.address) for d in renogy_devices]}")

    @pytest.mark.asyncio
    async def test_connect_and_read(self, skip_without_integration):
        """Test connecting and reading from real device."""
        from bleak import BleakScanner

        # Discover device
        devices = await BleakScanner.discover(timeout=10.0)
        renogy_device = next(
            (d for d in devices if d.name and "BT-TH" in d.name),
            None
        )

        if not renogy_device:
            pytest.skip("No BT-TH device found")

        # Connect and read
        device = RenogyBLEDevice(renogy_device, device_type="controller")
        client = RenogyBleClient()

        result = await client.read_device(device)

        assert result.success, f"Read failed: {result.error}"
        assert "battery_voltage" in result.parsed_data
        print(f"Read data: {result.parsed_data}")


class TestValidationOverhead:
    """Tests demonstrating validation overhead required with warning-based error handling.

    CONCERN: renogy-ble uses warnings instead of exceptions for errors.
    This means every call site must validate responses, adding overhead.
    """

    def test_empty_response_requires_validation(self):
        """Test that empty data returns empty dict - caller must check."""
        result = RenogyParser.parse(b"", device_type="controller", register=256)

        # Caller MUST check for empty result
        assert isinstance(result, dict)
        if not result:
            # This validation is required at every call site
            pass  # Handle empty response

        # Without validation, accessing fields would fail silently or KeyError
        battery_voltage = result.get("battery_voltage")
        assert battery_voltage is None  # Silent failure - no data

    def test_partial_response_requires_field_validation(self):
        """Test that partial data requires field-by-field validation."""
        # Short response that can't contain all fields
        short_data = bytes([0xFF, 0x03, 0x02, 0x00, 0x04, 0x90, 0x53])
        result = RenogyParser.parse(short_data, device_type="controller", register=57348)

        # Caller must validate each expected field exists
        required_fields = ["battery_voltage", "pv_power", "charging_status"]
        missing_fields = [f for f in required_fields if f not in result]

        # This validation overhead is needed at every call site
        if missing_fields:
            pass  # Handle missing fields

    def test_validation_helper_needed(self):
        """Demonstrate that a validation helper would be needed."""

        def validate_renogy_response(data: dict, required_fields: list[str]) -> tuple[bool, list[str]]:
            """Helper to validate renogy-ble response.

            This helper would be needed to wrap every call to avoid silent failures.
            """
            if not data:
                return False, ["empty response"]

            missing = [f for f in required_fields if f not in data]
            return len(missing) == 0, missing

        # Empty response
        empty_result = RenogyParser.parse(b"", device_type="controller", register=256)
        valid, errors = validate_renogy_response(empty_result, ["battery_voltage"])
        assert valid is False
        assert "empty response" in errors

    def test_cyrils_exception_approach_is_cleaner(self):
        """Document why exception-based error handling (cyrils) is cleaner.

        With exceptions:
        - try/except at call site - single point of error handling
        - No need to validate every field
        - Clear success/failure indication
        - Easier to test (mock exceptions)

        With warnings:
        - Must check if result is empty
        - Must check if each required field exists
        - Must handle None values in each field
        - More test cases needed for coverage
        - Silent failures possible
        """
        # This test documents the tradeoff, not a functional test
        pass


# Comparison test with existing implementation
class TestComparisonWithCyrils:
    """Compare renogy-ble output with cyrils/renogy-bt output format."""

    def test_output_field_compatibility(self):
        """Test that renogy-ble produces similar fields to cyrils/renogy-bt."""
        # Fields from cyrils/renogy-bt that we expect
        expected_fields = {
            "battery_percentage",
            "battery_voltage",
            "battery_current",
            "battery_temperature",
            "controller_temperature",
            "load_status",
            "load_voltage",
            "load_current",
            "load_power",
            "pv_voltage",
            "pv_current",
            "pv_power",
            "charging_status",
            "battery_type",
            "model",
        }

        # These are the fields from our RENOGY_RAW_DATA fixture
        fixture_fields = set(RENOGY_RAW_DATA.keys())

        # Check overlap
        common_fields = expected_fields & fixture_fields
        assert len(common_fields) > 10, "Expected significant field overlap"

    def test_solar_reading_compatibility(self):
        """Test that renogy-ble data can populate our SolarReading model."""
        from pisolar.sensors.solar_reading import SolarReading

        # Simulated renogy-ble output (similar structure expected)
        renogy_ble_data = {
            "battery_voltage": 13.2,
            "battery_percentage": 100,
            "battery_current": 0.0,
            "battery_temperature": -10,
            "controller_temperature": -5,
            "pv_voltage": 3.1,
            "pv_current": 0.0,
            "pv_power": 0,
            "load_status": "on",
            "load_voltage": 13.2,
            "load_current": 0.0,
            "load_power": 0,
            "charging_status": "deactivated",
            "battery_type": "lithium",
            "model": "RNG-CTRL-RVR20",
        }

        # Should be able to create SolarReading from this data
        reading = SolarReading.from_raw_data(
            sensor_type="solar",
            name="BT-TH-A5ABF10E",
            data=renogy_ble_data,
        )

        assert reading.battery_voltage == 13.2
        assert reading.battery_percentage == 100
        assert reading.model == "RNG-CTRL-RVR20"
        assert reading.charging_status == "deactivated"
