# Bluetooth and Renogy BT-1 and BT-2 Setup Guide

**✅ VERIFIED connectivity - BT-1 BT-2**

---

This guide covers setting up Bluetooth on Raspberry Pi and discovering Renogy BT-1/BT-2 Bluetooth modules.

For configuration details, see [CONFIGURATION.md](CONFIGURATION.md).  
For running as a service, see [SYSTEMD.md](SYSTEMD.md).

## Prerequisites

- Raspberry Pi with built-in Bluetooth (Pi 3, 4, Zero W, etc.) or USB Bluetooth adapter
- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.13+
- piSolar installed via Poetry

## 1. Enable and Configure Bluetooth

### 1.1 Install Bluetooth Packages

```bash
sudo apt update
sudo apt install -y bluetooth bluez bluez-tools
```

### 1.2 Enable Bluetooth Service

```bash
# Enable and start the Bluetooth service
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Check status
sudo systemctl status bluetooth
```

### 1.3 Unblock Bluetooth (if blocked)

Sometimes Bluetooth is software-blocked by rfkill:

```bash
# Check if Bluetooth is blocked
rfkill list

# If blocked, unblock it
sudo rfkill unblock bluetooth

# Restart service
sudo systemctl restart bluetooth
```

### 1.4 Power On Bluetooth Adapter

```bash
# Enter bluetoothctl
sudo bluetoothctl

# Inside bluetoothctl:
power on
agent on
default-agent

# Exit
exit
```

### 1.5 Verify Bluetooth is Working

```bash
# List Bluetooth adapters
hciconfig

# Scan for devices (should see nearby BT devices)
sudo bluetoothctl scan on
# Press Ctrl+C after a few seconds to stop scanning
```

## 2. Find Your Renogy BT-2 Device

### 2.1 Put BT-2 in Discovery Mode

The BT-2 module should be connected to your Renogy charge controller via RS232 cable and powered on.

### 2.2 Scan for the Device

```bash
sudo bluetoothctl
scan on
```

Look for devices with names starting with:
- `BT-TH-` (BT-2 module)
- `RNGRBP-` (Renogy Battery)
- `BTRIC-` (other Renogy devices)

Example output:
```
[NEW] Device CC:45:A5:AB:F1:0E BT-TH-A5ABF10E
```

Note the **MAC address** (e.g., `CC:45:A5:AB:F1:0E`) - you'll need this for configuration.

### 2.3 Stop Scanning

```bash
scan off
exit
```

## 3. Install Dependencies

The required libraries are automatically installed via Poetry:

```bash
cd ~/src/piSolar
poetry install
```

This installs:
- `renogy-ble` - Library for parsing Renogy BLE data
- `bleak` - Bluetooth Low Energy platform client

### 3.1 Verify Installation

```bash
# Should not raise ImportError
poetry run python -c "from renogy_ble import RenogyBleClient; print('OK')"
```

## 4. Test the Connection

### 4.1 Verify Adapter is Detected

```bash
poetry run python -c "
from pathlib import Path
bt = Path('/sys/class/bluetooth')
if bt.exists():
    adapters = [d.name for d in bt.iterdir() if d.is_dir() and d.name.startswith('hci')]
    print(f'Found adapters: {adapters}')
else:
    print('No bluetooth sysfs found')
"
```

### 4.2 Manual BLE Scan Test

```bash
poetry run python -c "
import asyncio
from bleak import BleakScanner

async def scan():
    print('Scanning for 15 seconds...')
    devices = await BleakScanner.discover(timeout=15.0)
    for d in devices:
        if 'BT-TH' in (d.name or '') or 'RNGR' in (d.name or ''):
            print(f'Found Renogy device: {d.name} - {d.address}')
    print(f'Total devices found: {len(devices)}')

asyncio.run(scan())
"
```

### 4.3 Test with piSolar

After configuring your device (see [CONFIGURATION.md](CONFIGURATION.md)):

```bash
poetry run pisolar -c config/config.yaml -l config/logging.yaml read-once
```

## Troubleshooting

### "No powered Bluetooth adapter found"

```bash
# Check adapter status
hciconfig

# If adapter shows "DOWN", bring it up
sudo hciconfig hci0 up

# Or restart Bluetooth service
sudo systemctl restart bluetooth
```

### "Failed to set power on: org.bluez.Error.Failed"

```bash
# Unblock and restart
sudo rfkill unblock bluetooth
sudo systemctl restart bluetooth
```

### Device Not Found During Scan

1. Ensure the BT-2 is powered on and connected to the charge controller
2. Move closer to the BT-2 module (BLE has limited range ~10m)
3. Try restarting the BT-2 by disconnecting and reconnecting power
4. Check that the charge controller is powered on
5. Increase `scan_timeout` in config if the default 15 seconds isn't enough
6. Ensure no other devices are connected to the BT-2 (only one connection at a time)

### "Could not find Renogy device with MAC address"

This means the BLE scan completed but didn't find your device:

```bash
# Scan and show ALL devices to verify Bluetooth is working
poetry run python -c "
import asyncio
from bleak import BleakScanner

async def scan():
    devices = await BleakScanner.discover(timeout=15.0)
    for d in devices:
        print(f'{d.address:20} {d.name}')
asyncio.run(scan())
"
```

If you see other devices but not your Renogy device:
- Verify the MAC address is correct
- Try power cycling the BT-2 module
- Make sure no smartphone app is connected to it

### Permission Denied for Bluetooth

Add your user to the bluetooth group:

```bash
sudo usermod -a -G bluetooth $USER
# Log out and back in for changes to take effect
```

### "bleak" or "renogy_ble" Module Not Found

Ensure you're using the Poetry environment:

```bash
# Check installed packages
poetry show | grep -E "(bleak|renogy-ble)"

# Should show:
# bleak                 2.1.1
# renogy-ble            1.2.0

# If missing, reinstall
poetry install
```

### BLE Scan Times Out

If scans consistently time out:

```bash
# Check BlueZ version (should be 5.50+)
bluetoothctl --version

# Restart Bluetooth daemon
sudo systemctl restart bluetooth

# Check for interference - disable WiFi temporarily
sudo rfkill block wifi
# Try scanning
# Re-enable WiFi
sudo rfkill unblock wifi
```

### Connection Drops or Intermittent

- Reduce distance to BT-2 module
- Check for 2.4GHz interference (WiFi, microwaves, etc.)
- Ensure good power supply to BT-2 and Raspberry Pi
- Increase `max_retries` in configuration

## Reference

- [renogy-ble on PyPI](https://pypi.org/project/renogy-ble/)
- [renogy-ble GitHub](https://github.com/cyrils/renogy-ble)
- [bleak GitHub](https://github.com/hbldh/bleak)
- [BlueZ Documentation](http://www.bluez.org/)
- [Raspberry Pi Bluetooth Setup](https://www.raspberrypi.com/documentation/computers/configuration.html#bluetooth)
