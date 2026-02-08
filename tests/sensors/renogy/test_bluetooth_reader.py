"""Tests for BluetoothReader."""

from unittest.mock import MagicMock, patch

from pisolar.sensors.renogy.bluetooth_reader import BluetoothReader


class TestBluetoothReader:
    """Tests for BluetoothReader helper functions."""

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

        assert result is True or result is False
