"""Tests for RenogySensor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pisolar.config.renogy_config import RenogyBluetoothSensorConfig
from pisolar.sensors.renogy import RenogySensor
from tests.fixtures import RENOGY_BT_CONFIG, RENOGY_SERIAL_CONFIG


class TestRenogySensor:
    """Tests for RenogySensor with mocked readers."""

    def test_sensor_type(self):
        """Test sensor type is 'solar'."""
        sensor = RenogySensor(config=RENOGY_BT_CONFIG)
        assert sensor.sensor_type == "solar"

    def test_sensor_name(self):
        """Test sensor name from config."""
        sensor = RenogySensor(config=RENOGY_BT_CONFIG)
        assert sensor.name == "rover"

    def test_serial_sensor(self):
        """Test creating sensor with serial config."""
        sensor = RenogySensor(config=RENOGY_SERIAL_CONFIG)
        assert sensor.name == "wanderer"
        assert sensor._reader.connection_type == "modbus"

    def test_bluetooth_sensor(self):
        """Test creating sensor with Bluetooth config."""
        sensor = RenogySensor(config=RENOGY_BT_CONFIG)
        assert sensor._reader.connection_type == "bluetooth"

    @patch("pisolar.sensors.renogy.bluetooth_reader._bluetooth_available")
    @patch("bleak.BleakScanner")
    @patch("renogy_ble.RenogyBLEDevice")
    @patch("renogy_ble.RenogyBleClient")
    def test_read_success(
        self,
        mock_client_class,
        mock_device_class,
        mock_scanner_class,
        mock_bt_available,
    ):
        """Test successful read from Renogy sensor using Bluetooth."""
        mock_bt_available.return_value = True

        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"

        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )

        mock_renogy_device = MagicMock()
        mock_device_class.return_value = mock_renogy_device

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_result.parsed_data = {
            "model": "RNG-CTRL-RVR20",
            "device_id": 1,
            "battery_percentage": 100,
            "battery_voltage": 13.2,
            "battery_current": 0.0,
            "battery_temperature": -10,
            "controller_temperature": -5,
            "load_status": "on",
            "pv_voltage": 3.1,
            "pv_power": 0,
            "charging_status": "deactivated",
            "battery_type": "lithium",
        }

        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        config = RenogyBluetoothSensorConfig(
            name="test",
            read_type="bt",
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        sensor = RenogySensor(config=config)
        readings = sensor.read()

        assert len(readings) == 1
        assert readings[0].model == "RNG-CTRL-RVR20"
        assert readings[0].battery_voltage == 13.2

    @patch("pisolar.sensors.renogy.bluetooth_reader._bluetooth_available")
    def test_read_no_bluetooth(self, mock_bt_available):
        """Test read fails gracefully when Bluetooth not available."""
        mock_bt_available.return_value = False

        sensor = RenogySensor(config=RENOGY_BT_CONFIG)

        with pytest.raises(RuntimeError, match="No powered Bluetooth adapter"):
            sensor.read()

    @patch("pisolar.sensors.renogy.bluetooth_reader._bluetooth_available")
    @patch("bleak.BleakScanner")
    def test_read_device_not_found(self, mock_scanner_class, mock_bt_available):
        """Test read fails when device not found during scan."""
        mock_bt_available.return_value = True

        mock_scanner_class.find_device_by_address = AsyncMock(return_value=None)

        config = RenogyBluetoothSensorConfig(
            name="test",
            read_type="bt",
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        sensor = RenogySensor(config=config)

        with pytest.raises(RuntimeError, match="Could not find Renogy device"):
            sensor.read()

    @patch("pisolar.sensors.renogy.bluetooth_reader._bluetooth_available")
    @patch("bleak.BleakScanner")
    @patch("renogy_ble.RenogyBLEDevice")
    @patch("renogy_ble.RenogyBleClient")
    def test_read_ble_failure(
        self,
        mock_client_class,
        mock_device_class,
        mock_scanner_class,
        mock_bt_available,
    ):
        """Test read fails when BLE read fails."""
        mock_bt_available.return_value = True

        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"

        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )
        mock_device_class.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = RuntimeError("Connection failed")
        mock_result.parsed_data = {}

        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        config = RenogyBluetoothSensorConfig(
            name="test",
            read_type="bt",
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        sensor = RenogySensor(config=config)

        with pytest.raises(RuntimeError, match="Failed to read from Renogy device"):
            sensor.read()

    @patch("pisolar.sensors.renogy.bluetooth_reader._bluetooth_available")
    @patch("bleak.BleakScanner")
    @patch("renogy_ble.RenogyBLEDevice")
    @patch("renogy_ble.RenogyBleClient")
    def test_read_empty_data(
        self,
        mock_client_class,
        mock_device_class,
        mock_scanner_class,
        mock_bt_available,
    ):
        """Test read fails when device returns empty data."""
        mock_bt_available.return_value = True

        mock_ble_device = MagicMock()
        mock_ble_device.name = "BT-TH-A5ABF10E"

        mock_scanner_class.find_device_by_address = AsyncMock(
            return_value=mock_ble_device
        )
        mock_device_class.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_result.parsed_data = {}

        mock_client = MagicMock()
        mock_client.read_device = AsyncMock(return_value=mock_result)
        mock_client_class.return_value = mock_client

        config = RenogyBluetoothSensorConfig(
            name="test",
            read_type="bt",
            mac_address="CC:45:A5:AB:F1:0E",
            device_alias="BT-TH-A5ABF10E",
            max_retries=1,
        )
        sensor = RenogySensor(config=config)

        with pytest.raises(RuntimeError, match="returned empty data"):
            sensor.read()
