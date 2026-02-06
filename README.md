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

## Prereguisits 
- python
- poetry
- raspberry pi 3, 4, 5, zero
- renogy charge controller 
    - wanderer BT-1
    - rover B2-2

## [Testbed](docs/TEST_BED.md)

## [Solar Testbed](docs/SOLAR_TESTBED.md)

## Installation

```bash
poetry install
```

## Hardware Setup

### Raspberry Pi Prerequisites

- **Bluetooth**: Enable Bluetooth on your Pi for BT-1/BT-2 modules.
  - See [Raspberry Pi Bluetooth documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#bluetooth).

- **1-Wire**: Enable 1-Wire interface for DS18B20 temperature sensors.
  - See [Raspberry Pi 1-Wire documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#one-wire).

### Renogy Sensors

Renogy charge controllers can be read via Bluetooth or Serial connections:

| Connection | status | Module | Documentation |
|------------|--------|--------|---------------|
| Bluetooth | verified| BT-1/BT-2 | [bluetooth setup](docs/BLUETOOTH_SETUP.md) |
| RS232 | verified | RJ12 cable | [rs 232](docs/RS232.md) |
| RS485 | **WIP** | RJ45 cable | [rs 485](docs/RS485.md) |

For Modbus protocol details, see [rover modbus](docs/rover_modbus.pdf).

## Configuration

See **[yaml configuration](docs/CONFIGURATION.md)** for configuration options.

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

## Systemd Service

To run piSolar as a system service, see **[systemd](docs/SYSTEMD.md)**.
