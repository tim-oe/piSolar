# Systemd Service Setup

This guide covers running piSolar as a systemd service for automatic startup and management.

The production setup uses symlinks so `/opt/piSolar` points to the source checkout.
`poetry install` is run once — the same `.venv` is used in both dev and production.

## Prerequisites

- piSolar cloned and `poetry install` run (creates `.venv` inside the project)
- Root access for systemd configuration

## Installation

### 1. Create Required Directories

```bash
sudo mkdir -p /var/log/piSolar /var/lib/piSolar /etc/piSolar
```

### 2. Symlink the Application and Config

```bash
# Point /opt/piSolar at the source checkout
sudo ln -sf /home/tcronin/src/piSolar /opt/piSolar

# Symlink config files into /etc/piSolar
sudo ln -sf /home/tcronin/src/piSolar/config/config.yaml /etc/piSolar/config.yaml
sudo ln -sf /home/tcronin/src/piSolar/config/logging.yaml /etc/piSolar/logging.yaml
```

### 3. Symlink and Enable the Service

```bash
sudo ln -sf /opt/piSolar/systemd/pisolar.service /usr/lib/systemd/system/pisolar.service
sudo systemctl daemon-reload
sudo systemctl enable pisolar
sudo systemctl start pisolar
```

## Updating

After pulling new code, reinstall deps if `pyproject.toml` changed, then restart:

```bash
cd /home/tcronin/src/piSolar
poetry install
sudo systemctl restart pisolar
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
```

Application logs are also written to the file specified in `logging.yaml` (default: `/var/log/piSolar/piSolar.log`).

## Permissions

### Serial Port Access

For RS232/RS485 Modbus, the user needs access to serial devices:

```bash
sudo usermod -a -G dialout tcronin
```

### 1-Wire Access

For temperature sensors, ensure the 1-Wire interface is enabled:

```bash
# Add to /boot/firmware/config.txt (Raspberry Pi OS Bookworm+)
dtoverlay=w1-gpio
```

If you need a specific GPIO for 1-Wire, set it explicitly (example GPIO 27):

```bash
# Add to /boot/firmware/config.txt
dtoverlay=w1-gpio,gpiopin=27
```

After reboot, verify the kernel device appears:

```bash
ls /sys/bus/w1/devices/
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status and recent logs
sudo systemctl status pisolar
sudo journalctl -u pisolar -n 50

# Test manually as the same user the service runs as
/opt/piSolar/.venv/bin/pisolar -c /etc/piSolar/config.yaml -l /etc/piSolar/logging.yaml show-config
```

### Verify Symlinks

```bash
ls -la /opt/piSolar
ls -la /etc/piSolar/
ls -la /usr/lib/systemd/system/pisolar.service
```
