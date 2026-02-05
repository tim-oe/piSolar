# Configuration Guide

This document describes how to configure piSolar for your environment.

## Configuration Files

piSolar uses two configuration files:

- `config.yaml` - Application settings (sensors, schedules, metrics)
- `logging.yaml` - Python logging configuration

**Development (from source tree):**

```bash
# Use configs directly from the project
poetry run pisolar -c config/config.yaml -l config/logging.yaml show-config
```

**Production (systemd service):**

See [SYSTEMD.md](SYSTEMD.md) for deploying configs to `/etc/pisolar/`.

## Application Configuration

The main config file (`config.yaml`) controls sensors and metrics. Use `!ENV ${VAR:default}` for environment variable substitution.

### Full Example

```yaml
temperature:
  enabled: !ENV ${PISOLAR_TEMPERATURE_ENABLED:true}
  schedule:
    cron: !ENV ${PISOLAR_TEMPERATURE_CRON:"*/5 * * * *"}
  sensors:
    - name: "ambient"
      address: "0000007c6850"

renogy:
  enabled: !ENV ${PISOLAR_RENOGY_ENABLED:false}
  sensors:
    # Bluetooth sensor (BT-1/BT-2 module)
    - name: rover
      read_type: bt
      mac_address: !ENV ${PISOLAR_RENOGY_MAC_ADDRESS:"CC:45:A5:AB:F1:0E"}
      device_alias: "BT-TH-A5ABF10E"
    # Serial sensor (RS232/RS485 Modbus)
    - name: wanderer
      read_type: serial
      device_path: "/dev/ttyUSB0"

metrics:
  output_dir: !ENV ${PISOLAR_METRICS_OUTPUT_DIR:/var/lib/pisolar/metrics}
```

### Temperature Sensors

Configure 1-Wire temperature sensors:

```yaml
temperature:
  enabled: true
  schedule:
    cron: "*/5 * * * *"  # Every 5 minutes
  sensors:
    - name: "ambient"
      address: "0000007c6850"  # Sensor ID (from /sys/bus/w1/devices/)
    - name: "battery_compartment"
      address: "000000b4c0d2"
```

### Renogy Sensors

Supports both Bluetooth (BT-1/BT-2) and Serial (RS232/RS485 Modbus) connections.

#### Bluetooth Configuration

```yaml
renogy:
  enabled: true
  sensors:
    - name: rover
      read_type: bt
      mac_address: "CC:45:A5:AB:F1:0E"
      device_alias: "BT-TH-A5ABF10E"
      device_type: rover          # Optional: controller, dcc, rover, wanderer
      scan_timeout: 15.0          # Optional: BLE scan timeout in seconds
      max_retries: 3              # Optional: connection retry attempts
```

#### Serial (Modbus) Configuration

```yaml
renogy:
  enabled: true
  sensors:
    - name: wanderer
      read_type: serial
      device_path: "/dev/ttyUSB0"
      baud_rate: 9600             # Optional: default 9600
      slave_address: 1            # Optional: Modbus slave address, default 1
      max_retries: 3              # Optional: read retry attempts
```

### Metrics Output

Configure where metrics are written:

```yaml
metrics:
  output_dir: /var/lib/pisolar/metrics
```

## Logging Configuration

Logging is configured separately in `logging.yaml` using Python's dictConfig format with `!ENV` tag for environment variable substitution.

### Example logging.yaml

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: "%(asctime)s|%(filename)s:%(lineno)d|%(levelname)s- %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: !ENV ${PISOLAR_LOG_LEVEL:DEBUG}
    formatter: standard
    filename: !ENV ${PISOLAR_LOG_FILE:./pisolar.log}
    maxBytes: 10485760  # 10MB
    backupCount: 5

root:
  level: DEBUG
  handlers: [console, file]

loggers:
  pisolar:
    level: DEBUG
    handlers: [console, file]
    propagate: false
```

See [WeatherWatch logging.yml](https://github.com/tim-oe/WeatherWatch/blob/main/config/logging.yml) for additional reference.

## Environment Variables

Environment variables are substituted in YAML files using the `!ENV ${VAR:default}` syntax.

### Application Settings

```bash
export PISOLAR_TEMPERATURE_ENABLED=false
export PISOLAR_TEMPERATURE_CRON="*/10 * * * *"
export PISOLAR_RENOGY_ENABLED=true
export PISOLAR_RENOGY_MAC_ADDRESS="AA:BB:CC:DD:EE:FF"
export PISOLAR_METRICS_OUTPUT_DIR="/custom/path"
```

### Logging Settings

```bash
export PISOLAR_LOG_LEVEL=DEBUG
export PISOLAR_LOG_FILE=/var/log/pisolar/pisolar.log
```

## Sensor Discovery

### Finding 1-Wire Sensor Addresses

```bash
ls /sys/bus/w1/devices/
# Output: 28-0000007c6850  28-000000b4c0d2  w1_bus_master1
```

The address is the portion after the `28-` prefix (e.g., `0000007c6850`).

### Finding Renogy BT-2 MAC Address

```bash
sudo bluetoothctl
[bluetooth]# scan on
# Look for devices starting with "BT-TH-"
# Example: [NEW] Device CC:45:A5:AB:F1:0E BT-TH-A5ABF10E
```

For detailed Bluetooth setup, see [BLUETOOTH_SETUP.md](BLUETOOTH_SETUP.md).

### Finding Serial Device Path

```bash
ls /dev/ttyUSB*
# Or for built-in serial:
ls /dev/ttyAMA*
```

## Configuration Validation

Test your configuration before deploying:

```bash
# Show parsed configuration
pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml show-config

# Test sensor connectivity
pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml check

# Read sensors once
pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml read-once
```
