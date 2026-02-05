"""Test fixtures with realistic data from live sensors."""

from pisolar.config.renogy_config import (
    RenogyBluetoothSensorConfig,
    RenogySerialSensorConfig,
)

# Raw Renogy BT-2 sensor output (from RNG-CTRL-RVR20 charge controller)
# Captured during low-light conditions (night/early morning)
RENOGY_RAW_DATA = {
    "function": "READ",
    "model": "RNG-CTRL-RVR20",
    "device_id": 1,
    "battery_percentage": 100,
    "battery_voltage": 13.2,
    "battery_current": 0.0,
    "battery_temperature": -10,
    "controller_temperature": -5,
    "load_status": "on",
    "load_voltage": 13.2,
    "load_current": 0.0,
    "load_power": 0,
    "pv_voltage": 3.1,
    "pv_current": 0.0,
    "pv_power": 0,
    "max_charging_power_today": 55,
    "max_discharging_power_today": 1,
    "charging_amp_hours_today": 5,
    "discharging_amp_hours_today": 0,
    "power_generation_today": 71,
    "power_consumption_today": 0,
    "power_generation_total": 5133,
    "charging_status": "deactivated",
    "battery_type": "lithium",
    "__device": "BT-TH-A5ABF10E",
    "__client": "RoverClient",
}

# Renogy data during active charging (simulated midday)
RENOGY_RAW_DATA_CHARGING = {
    "function": "READ",
    "model": "RNG-CTRL-RVR20",
    "device_id": 1,
    "battery_percentage": 85,
    "battery_voltage": 14.4,
    "battery_current": 3.5,
    "battery_temperature": 25,
    "controller_temperature": 35,
    "load_status": "on",
    "load_voltage": 14.4,
    "load_current": 0.5,
    "load_power": 7,
    "pv_voltage": 18.5,
    "pv_current": 2.8,
    "pv_power": 52,
    "max_charging_power_today": 55,
    "max_discharging_power_today": 1,
    "charging_amp_hours_today": 12,
    "discharging_amp_hours_today": 2,
    "power_generation_today": 180,
    "power_consumption_today": 25,
    "power_generation_total": 5200,
    "charging_status": "mppt",
    "battery_type": "lithium",
    "__device": "BT-TH-A5ABF10E",
    "__client": "RoverClient",
}

# Renogy Bluetooth sensor configuration
RENOGY_BT_CONFIG = RenogyBluetoothSensorConfig(
    name="rover",
    read_type="bt",
    mac_address="CC:45:A5:AB:F1:0E",
    device_alias="BT-TH-A5ABF10E",
    device_type="rover",
    scan_timeout=15.0,
    max_retries=3,
)

# Renogy Serial/Modbus sensor configuration
RENOGY_SERIAL_CONFIG = RenogySerialSensorConfig(
    name="wanderer",
    read_type="serial",
    device_path="/dev/ttyUSB0",
    baud_rate=9600,
    slave_address=1,
    device_type="wanderer",
    max_retries=3,
)

# Legacy config dict for backwards compatibility
RENOGY_CONFIG = RENOGY_BT_CONFIG

# Temperature sensor addresses (DS18B20 1-Wire sensors)
TEMPERATURE_SENSORS = [
    {"name": "temp 1", "address": "0000007c6850"},
    {"name": "temp 2", "address": "000000b4c0d2"},
    {"name": "temp 3", "address": "0000007b409e"},
    {"name": "temp 4", "address": "0000007ba79d"},
]

# Simulated temperature readings (Celsius)
TEMPERATURE_READINGS = [
    {"name": "temp 1", "value": 22.5, "unit": "C"},
    {"name": "temp 2", "value": 23.1, "unit": "C"},
    {"name": "temp 3", "value": 21.8, "unit": "C"},
    {"name": "temp 4", "value": 24.0, "unit": "C"},
]

# Cold weather temperature readings
TEMPERATURE_READINGS_COLD = [
    {"name": "temp 1", "value": -5.2, "unit": "C"},
    {"name": "temp 2", "value": -4.8, "unit": "C"},
    {"name": "temp 3", "value": -6.1, "unit": "C"},
    {"name": "temp 4", "value": -3.5, "unit": "C"},
]
