# piSolar

Solar system monitoring service for Raspberry Pi. Collects metrics from temperature sensors (1-Wire) and Renogy BT-2 Bluetooth module.

## Features

- **Temperature Sensors**: Reads 1-Wire temperature sensors via `w1thermsensor`
- **Renogy BT-2**: Reads solar charge controller data via Bluetooth
- **Cron Scheduling**: Configurable schedules using cron syntax
- **YAML Configuration**: Config files with environment variable overrides
- **External Logging Config**: Python logging dictConfig from YAML with `!ENV` tag support
- **Systemd Service**: Run as a system service

## Installation

```bash
poetry install
```

### Renogy BT-2 support (optional)

For detailed Bluetooth setup instructions, see **[docs/BLUETOOTH_SETUP.md](docs/BLUETOOTH_SETUP.md)**.

**Quick start:**

1. Ensure Bluetooth is enabled and powered on:
   ```bash
   sudo systemctl enable bluetooth
   sudo systemctl start bluetooth
   sudo bluetoothctl power on
   ```

2. Clone the renogy-bt library:
   ```bash
   git clone https://github.com/cyrils/renogy-bt.git ~/src/renogy-bt
   ```

3. Install its dependencies:
   ```bash
   poetry run pip install -r ~/src/renogy-bt/requirements.txt
   ```

4. Run pisolar with `PYTHONPATH`:
   ```bash
   PYTHONPATH=~/src/renogy-bt poetry run pisolar -c config/config.yaml -l config/logging.yaml read-once
   ```

## Configuration

Copy the sample configs and customize:

```bash
sudo mkdir -p /etc/pisolar
sudo cp config/config.yaml /etc/pisolar/config.yaml
sudo cp config/logging.yaml /etc/pisolar/logging.yaml
```

### Application Configuration

The main config file (`config.yaml`) controls sensors and metrics. Use `!ENV ${VAR:default}` for environment variable substitution:

```yaml
temperature:
  enabled: !ENV ${PISOLAR_TEMPERATURE_ENABLED:true}
  schedule:
    cron: !ENV ${PISOLAR_TEMPERATURE_CRON:"*/5 * * * *"}

renogy:
  enabled: !ENV ${PISOLAR_RENOGY_ENABLED:false}
  mac_address: !ENV ${PISOLAR_RENOGY_MAC_ADDRESS:""}

metrics:
  output_dir: !ENV ${PISOLAR_METRICS_OUTPUT_DIR:/var/lib/pisolar/metrics}
```

### Logging Configuration

Logging is configured separately in `logging.yaml` using Python's dictConfig format with `!ENV` tag for environment variable substitution:

```yaml
handlers:
  file:
    level: !ENV ${PISOLAR_LOG_LEVEL:DEBUG}
    filename: !ENV ${PISOLAR_LOG_FILE:./pisolar.log}
```

See [WeatherWatch logging.yml](https://github.com/tim-oe/WeatherWatch/blob/main/config/logging.yml) for reference.

### Environment Variables

Environment variables are substituted in YAML files using the `!ENV ${VAR:default}` syntax:

```bash
export PISOLAR_TEMPERATURE_ENABLED=false
export PISOLAR_RENOGY_MAC_ADDRESS="AA:BB:CC:DD:EE:FF"
export PISOLAR_METRICS_OUTPUT_DIR="/custom/path"
```

Logging settings (used via `!ENV` in logging.yaml):

```bash
export PISOLAR_LOG_LEVEL=DEBUG
export PISOLAR_LOG_FILE=/var/log/pisolar/pisolar.log
```

## Usage

### CLI Commands

```bash
pisolar --help                           # Show help
pisolar run                              # Start the monitoring service
pisolar check                            # Check sensor availability
pisolar read-once                        # Read all sensors once (for testing)
pisolar show-config                      # Display current configuration
pisolar -c config.yaml -l logging.yaml run  # Specify config files
```

## Systemd Service

### Installation

```bash
# Create user and directories
sudo useradd -r -s /bin/false pisolar
sudo mkdir -p /opt/pisolar /var/log/pisolar /var/lib/pisolar /etc/pisolar
sudo chown pisolar:pisolar /var/log/pisolar /var/lib/pisolar

# Copy configuration
sudo cp config/config.yaml /etc/pisolar/
sudo cp config/logging.yaml /etc/pisolar/

# Install the application
cd /opt/pisolar
sudo python -m venv .venv
sudo .venv/bin/pip install /path/to/piSolar

# Install service
sudo cp systemd/pisolar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pisolar
sudo systemctl start pisolar
```

### Service Commands

```bash
sudo systemctl status pisolar   # Check status
sudo systemctl start pisolar    # Start service
sudo systemctl stop pisolar     # Stop service
sudo systemctl restart pisolar  # Restart service
sudo journalctl -u pisolar -f   # View logs
```

## Development Commands

### Testing

```bash
poetry run pytest                          # Run all tests
poetry run pytest tests/test_pisolar.py    # Run a single test file
poetry run pytest tests/test_pisolar.py::test_version  # Run a single test
poetry run pytest --cov                    # Run tests with coverage
poetry run pytest --cov --cov-report=html  # Coverage with HTML report
```

### Code Formatting

```bash
poetry run black src tests            # Format code
poetry run isort src tests            # Sort imports
```

### Linting

```bash
poetry run pylint src                 # Lint code
poetry run flake8 src tests           # Flake8 checks
```

## Project Structure

```
piSolar/
├── src/pisolar/
│   ├── __init__.py
│   ├── __main__.py         # Module entry point
│   ├── cli.py              # CLI commands
│   ├── config.py           # Application configuration
│   ├── logging_config.py   # YAML logging with !ENV support
│   ├── scheduler.py        # APScheduler wrapper
│   ├── sensors/
│   │   ├── base.py         # Base sensor class
│   │   ├── temperature.py  # 1-Wire temperature sensors
│   │   └── renogy.py       # Renogy BT-2 integration
│   └── services/
│       └── metrics.py      # Metrics recording
├── tests/
├── config/
│   ├── config.yaml         # Application configuration
│   └── logging.yaml        # Logging configuration
├── systemd/
│   └── pisolar.service     # Systemd unit file
└── pyproject.toml
```
