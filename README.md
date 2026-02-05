# piSolar

Solar system monitoring service for Raspberry Pi. Collects metrics from temperature sensors (1-Wire) and Renogy BT-2 Bluetooth module.

## Features

- **Temperature Sensors**: Reads 1-Wire temperature sensors via `w1thermsensor`
- **Renogy Bluetooth**: Reads solar charge controller data via BT-1/BT-2 modules
- **Renogy Serial**: Reads solar charge controller data via RS232/RS485 Modbus
- **Cron Scheduling**: Configurable schedules using cron syntax
- **YAML Configuration**: Config files with environment variable overrides
- **External Logging Config**: Python logging dictConfig from YAML with `!ENV` tag support
- **Event-Driven Architecture**: Pluggable consumers via event bus
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

For detailed configuration options, see **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**.

**Quick start:**

```bash
sudo mkdir -p /etc/pisolar
sudo cp config/config.yaml /etc/pisolar/config.yaml
sudo cp config/logging.yaml /etc/pisolar/logging.yaml
# Edit configs as needed, then test:
pisolar -c /etc/pisolar/config.yaml -l /etc/pisolar/logging.yaml show-config
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

### Poetry Run Targets

The project provides convenient run targets for common tasks:

```bash
poetry run pisolar          # Run the pisolar CLI
poetry run lint             # Check code style (isort, black, flake8)
poetry run format           # Auto-fix code formatting (isort, black)
```

### Testing

```bash
poetry run pytest                          # Run all tests
poetry run pytest tests/test_pisolar.py    # Run a single test file
poetry run pytest tests/test_pisolar.py::test_version  # Run a single test
poetry run pytest -k "test_read"           # Run tests matching pattern
poetry run pytest --cov                    # Run tests with coverage
poetry run pytest --cov --cov-report=html  # Coverage with HTML report
```

### Code Formatting & Linting

```bash
# Combined targets (recommended)
poetry run lint             # Check all style issues (fails if issues found)
poetry run format           # Auto-fix formatting issues

# Individual tools
poetry run black src tests            # Format code with black
poetry run isort src tests            # Sort imports with isort
poetry run flake8 src tests           # Check style with flake8
poetry run pylint src                 # Lint code with pylint
```

## Project Structure

```
piSolar/
├── src/pisolar/
│   ├── __init__.py
│   ├── __main__.py           # Module entry point
│   ├── cli.py                # CLI commands
│   ├── event_bus.py          # Event publishing system
│   ├── logging_config.py     # YAML logging with !ENV support
│   ├── scheduler.py          # APScheduler wrapper
│   ├── config/
│   │   ├── settings.py       # Application settings
│   │   ├── renogy_config.py  # Renogy sensor configuration
│   │   └── ...               # Other config models
│   ├── sensors/
│   │   ├── base_sensor.py    # Base sensor class
│   │   ├── renogy/
│   │   │   ├── sensor.py           # Renogy sensor facade
│   │   │   ├── bluetooth_reader.py # BT-1/BT-2 reader
│   │   │   ├── modbus_reader.py    # RS232/RS485 Modbus reader
│   │   │   └── reading.py          # SolarReading model
│   │   └── temperature/
│   │       ├── sensor.py     # 1-Wire temperature sensors
│   │       └── reading.py    # TemperatureReading model
│   └── services/
│       ├── metrics.py        # Metrics recording
│       └── consumers.py      # Event consumers
├── tests/                    # Test files mirror src/ structure
│   ├── config/
│   ├── sensors/
│   │   ├── renogy/
│   │   └── temperature/
│   └── services/
├── scripts/
│   └── lint.py               # Linting script for poetry run targets
├── config/
│   ├── config.yaml           # Application configuration
│   └── logging.yaml          # Logging configuration
├── systemd/
│   └── pisolar.service       # Systemd unit file
└── pyproject.toml
```
