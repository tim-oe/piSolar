# Systemd Service Setup

This guide covers running piSolar as a systemd service for automatic startup and management.

## Prerequisites

- piSolar installed and tested manually
- Configuration files ready (`config.yaml`, `logging.yaml`)
- Root access for systemd configuration

## Installation

### 1. Create Service User and Directories

```bash
# Create dedicated service user (no login shell)
sudo useradd -r -s /bin/false pisolar

# Create required directories
sudo mkdir -p /opt/pisolar /var/log/pisolar /var/lib/pisolar /etc/pisolar

# Set ownership for data directories
sudo chown pisolar:pisolar /var/log/pisolar /var/lib/pisolar
```

### 2. Install Configuration Files

```bash
sudo cp config/config.yaml /etc/pisolar/
sudo cp config/logging.yaml /etc/pisolar/

# Edit configuration as needed
sudo nano /etc/pisolar/config.yaml
```

### 3. Install the Application

```bash
cd /opt/pisolar
sudo python -m venv .venv
sudo .venv/bin/pip install /path/to/piSolar

# Dependencies including Bluetooth are installed automatically
```

### 4. Install and Enable Service

```bash
sudo cp systemd/pisolar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pisolar
sudo systemctl start pisolar
```

## Service Commands

```bash
sudo systemctl status pisolar   # Check status
sudo systemctl start pisolar    # Start service
sudo systemctl stop pisolar     # Stop service
sudo systemctl restart pisolar  # Restart service
sudo systemctl enable pisolar   # Enable auto-start on boot
sudo systemctl disable pisolar  # Disable auto-start
```

## Viewing Logs

```bash
# Follow logs in real-time
sudo journalctl -u pisolar -f

# View recent logs
sudo journalctl -u pisolar -n 100

# View logs since last boot
sudo journalctl -u pisolar -b

# View logs from specific time
sudo journalctl -u pisolar --since "2024-01-01 00:00:00"
```

Application logs are also written to the file specified in `logging.yaml` (default: `/var/log/pisolar/pisolar.log`).

## Service File

The service file is located at `systemd/pisolar.service`. Key settings:

```ini
[Unit]
Description=piSolar Monitoring Service
After=network.target bluetooth.target

[Service]
Type=simple
User=pisolar
Group=pisolar
ExecStart=/opt/pisolar/.venv/bin/pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Permissions

### Bluetooth Access

For Bluetooth support, the pisolar user needs access to the Bluetooth adapter:

```bash
sudo usermod -a -G bluetooth pisolar
```

### Serial Port Access

For RS232/RS485 Modbus, the pisolar user needs access to serial devices:

```bash
sudo usermod -a -G dialout pisolar
```

### 1-Wire Access

For temperature sensors, ensure the 1-Wire interface is enabled and accessible:

```bash
# Add to /boot/config.txt
dtoverlay=w1-gpio
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status and recent logs
sudo systemctl status pisolar
sudo journalctl -u pisolar -n 50

# Test configuration manually
sudo -u pisolar /opt/pisolar/.venv/bin/pisolar \
  -c /etc/pisolar/config.yaml \
  -l /etc/pisolar/logging.yaml \
  show-config
```

### Permission Denied Errors

Verify the pisolar user has necessary group memberships:

```bash
groups pisolar
# Should include: pisolar bluetooth dialout (as needed)
```

### Bluetooth Not Available

Ensure Bluetooth service is running:

```bash
sudo systemctl status bluetooth
sudo systemctl start bluetooth
```
