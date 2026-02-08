"""Tests for BluetoothReader."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pisolar.config.renogy_device_type import DeviceType
from pisolar.sensors.renogy.bluetooth_reader import BluetoothReader


class TestBluetoothReader:
    """Tests for BluetoothReader with dependency injection."""

    @patch("pisolar.sensors.renogy.bluetooth_reader.Path")
    def test_bluetooth_available_with_adapter(self, mock_path_class):
        """Test _bluetooth_available returns True when adapter exists."""
        mock_bt_path = MagicMock()
        mock_bt_path.exists.return_value = True

        mock_hci0 = MagicMock()
        mock_hci0.is_dir.return_value = True
        mock_hci0.name = "hci0"

        mock_bt_path.iterdir.return_value = [mock_hci0]
        mock_path_class.return_value = mock_bt_path

        result = BluetoothReader._bluetooth_available()

        assert result is True

    @patch("pisolar.sensors.renogy.bluetooth_reader.Path")
    def test_bluetooth_available_no_adapter(self, mock_path_class):
        """Test _bluetooth_available returns False when no adapter exists."""
        mock_bt_path = MagicMock()
        mock_bt_path.exists.return_value = True
        mock_bt_path.iterdir.return_value = []
        mock_path_class.return_value = mock_bt_path

        result = BluetoothReader._bluetooth_available()

        assert result is False

    @patch("pisolar.sensors.renogy.bluetooth_reader.Path")
    def test_bluetooth_available_no_sysfs(self, mock_path_class):
        """Test _bluetooth_available returns True on non-Linux (no sysfs)."""
        mock_bt_path = MagicMock()
        mock_bt_path.exists.return_value = False
        mock_path_class.return_value = mock_bt_path

        result = BluetoothReader._bluetooth_available()

        assert result is True

    @pytest.mark.asyncio
    @patch("pisolar.sensors.renogy.bluetooth_reader.BluetoothReader._bluetooth_available")
    async def test_read_success_with_dependency_injection(self, mock_bt_available):
        """Test successful read using dependency injection after instance creation."""
        mock_bt_available.return_value = True

        # Create mock classes
        mock_scanner_class = MagicMock()
        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"
        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )

        mock_device_class = MagicMock()
        mock_renogy_device = MagicMock()
        mock_device_class.return_value = mock_renogy_device

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_result.parsed_data = {
            "model": "RNG-CTRL-RVR20",
            "battery_voltage": 13.2,
            "battery_current": 0.0,
        }

        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        # Create reader normally
        reader = BluetoothReader(
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            device_type=DeviceType.CONTROLLER,
            max_retries=1,
        )

        # Inject mocks after creation
        reader._scanner_class = mock_scanner_class
        reader._client_class = mock_client_class
        reader._device_class = mock_device_class

        # Perform read
        result = await reader._read_implementation()

        # Verify
        assert result["model"] == "RNG-CTRL-RVR20"
        assert result["battery_voltage"] == 13.2
        assert result["__device"] == "BT-TH-A5ABF10E"
        assert result["__client"] == "BluetoothReader"
        mock_scanner_class.find_device_by_address.assert_called_once()
        mock_client.read_device.assert_called_once_with(mock_renogy_device)

    @pytest.mark.asyncio
    @patch("pisolar.sensors.renogy.bluetooth_reader.BluetoothReader._bluetooth_available")
    async def test_read_device_not_found(self, mock_bt_available):
        """Test read fails when device not found during scan."""
        mock_bt_available.return_value = True

        mock_scanner_class = MagicMock()
        mock_scanner_class.find_device_by_address = AsyncMock(return_value=None)

        reader = BluetoothReader(
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        reader._scanner_class = mock_scanner_class

        with pytest.raises(RuntimeError, match="Could not find Renogy device"):
            await reader._read_implementation()

    @pytest.mark.asyncio
    @patch("pisolar.sensors.renogy.bluetooth_reader.BluetoothReader._bluetooth_available")
    async def test_read_ble_failure(self, mock_bt_available):
        """Test read fails when BLE read fails."""
        mock_bt_available.return_value = True

        mock_scanner_class = MagicMock()
        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"
        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )

        mock_device_class = MagicMock()
        mock_device_class.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = RuntimeError("Connection failed")
        mock_result.parsed_data = {}

        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        reader = BluetoothReader(
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        reader._scanner_class = mock_scanner_class
        reader._client_class = mock_client_class
        reader._device_class = mock_device_class

        with pytest.raises(RuntimeError, match="BLE read failed"):
            await reader._read_implementation()

    @pytest.mark.asyncio
    @patch("pisolar.sensors.renogy.bluetooth_reader.BluetoothReader._bluetooth_available")
    async def test_read_empty_data(self, mock_bt_available):
        """Test read fails when device returns empty data."""
        mock_bt_available.return_value = True

        mock_scanner_class = MagicMock()
        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"
        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )

        mock_device_class = MagicMock()
        mock_device_class.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_result.parsed_data = {}

        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        reader = BluetoothReader(
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        reader._scanner_class = mock_scanner_class
        reader._client_class = mock_client_class
        reader._device_class = mock_device_class

        with pytest.raises(RuntimeError, match="returned empty data"):
            await reader._read_implementation()

    @pytest.mark.asyncio
    @patch("pisolar.sensors.renogy.bluetooth_reader.BluetoothReader._bluetooth_available")
    async def test_read_no_bluetooth(self, mock_bt_available):
        """Test read fails when Bluetooth not available."""
        mock_bt_available.return_value = False

        reader = BluetoothReader(
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )

        with pytest.raises(RuntimeError, match="No powered Bluetooth adapter"):
            await reader._read_implementation()
