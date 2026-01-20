# Bluetooth and Renogy BT-2 Setup Guide

This guide covers setting up Bluetooth on Raspberry Pi and installing the renogy-bt library for communicating with Renogy BT-1/BT-2 Bluetooth modules.

## Prerequisites

- Raspberry Pi with built-in Bluetooth (Pi 3, 4, Zero W, etc.) or USB Bluetooth adapter
- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.10+
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

Note the **MAC address** (e.g., `CC:45:A5:AB:F1:0E`) and **device name** (e.g., `BT-TH-A5ABF10E`).

### 2.3 Stop Scanning

```bash
scan off
exit
```

## 3. Install renogy-bt Library

The renogy-bt library is not on PyPI, so it must be installed manually.

### 3.1 Clone the Repository

```bash
# Clone next to your piSolar project
cd ~/src
git clone https://github.com/cyrils/renogy-bt.git
```

### 3.2 Install Dependencies

Install the renogy-bt dependencies into your Poetry environment:

```bash
cd ~/src/piSolar
poetry run pip install -r ~/src/renogy-bt/requirements.txt
```

### 3.3 Verify Installation

```bash
# Should not raise ImportError
PYTHONPATH=~/src/renogy-bt poetry run python -c "from renogybt import RoverClient; print('OK')"
```

## 4. Configure piSolar

### 4.1 Update config.yaml

Edit your piSolar configuration with the device details from step 2:

```yaml
renogy:
  enabled: true
  name: "Solar Controller"
  mac_address: CC:45:A5:AB:F1:0E  # Your BT-2 MAC address
  device_alias: BT-TH-A5ABF10E     # Your BT-2 device name
  schedule:
    cron: "*/5 * * * *"  # Read every 5 minutes
    enabled: true
```

### 4.2 Copy Template File (if deploying to /etc)

```bash
sudo mkdir -p /etc/pisolar
sudo cp config/renogy_bt.ini.template /etc/pisolar/
```

## 5. Test the Connection

### 5.1 Run a Single Read

```bash
PYTHONPATH=~/src/renogy-bt poetry run pisolar \
  -c config/config.yaml \
  -l config/logging.yaml \
  read-once
```

Expected output:
```
Reading sensors...
  [solar] BT-TH-A5ABF10E: {'type': 'solar', 'name': 'BT-TH-A5ABF10E', 'battery_voltage': 13.2, ...}

Total: 1 readings
```

### 5.2 Check Command

```bash
PYTHONPATH=~/src/renogy-bt poetry run pisolar \
  -c config/config.yaml \
  -l config/logging.yaml \
  check
```

## 6. Running as a Service

### 6.1 Create Environment File

Create `/etc/pisolar/environment`:

```bash
PYTHONPATH=/home/pi/src/renogy-bt
```

### 6.2 Update systemd Service

Ensure the systemd service file includes the environment:

```ini
[Service]
EnvironmentFile=/etc/pisolar/environment
ExecStart=/home/pi/.local/bin/poetry run pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml run
```

### 6.3 Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable pisolar
sudo systemctl start pisolar
sudo systemctl status pisolar
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
2. Move closer to the BT-2 module
3. Try restarting the BT-2 by disconnecting and reconnecting power
4. Check that the MAC address in config matches exactly

### "Task exception was never retrieved" (EOFError)

This is a non-fatal error during BLE disconnect. The data was read successfully. piSolar suppresses this at debug level.

### Permission Denied for Bluetooth

Add your user to the bluetooth group:

```bash
sudo usermod -a -G bluetooth $USER
# Log out and back in for changes to take effect
```

### Bluetooth Works Manually but Not from Service

Ensure the systemd service runs as a user with Bluetooth permissions, or run as root:

```ini
[Service]
User=root
```

Or configure PolicyKit/D-Bus permissions for the service user.

## Reference

- [renogy-bt GitHub](https://github.com/cyrils/renogy-bt)
- [BlueZ Documentation](http://www.bluez.org/)
- [Raspberry Pi Bluetooth Setup](https://www.raspberrypi.com/documentation/computers/configuration.html#bluetooth)
