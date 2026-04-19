"""
Command-line interface for piSolar.

Usage:
  pisolar run
  pisolar check
  pisolar read_once
  pisolar show_config

  see https://click.palletsprojects.com/en/stable/
"""

import sys

import click

from pisolar.config.settings import Settings
from pisolar.logging_config import get_logger, setup_logging
from pisolar.scheduler_service import SchedulerService
from pisolar.sensors.renogy.renogy_sensor import RenogySensor
from pisolar.sensors.temperature.temperature_reading import TemperatureReading
from pisolar.sensors.temperature.temperature_sensor import TemperatureSensor
from pisolar.services.db.mysql_consumer import MySQLConsumer
from pisolar.services.logging_consumer import LoggingConsumer
from pisolar.services.metrics_service import MetricsService
from pisolar.services.rabbitmq_consumer import RabbitMQConsumer
from pisolar.services.sqlite_consumer import SqliteConsumer

DEFAULT_CONFIG = "/etc/piSolar/config.yaml"
DEFAULT_LOG_CONFIG = "/etc/piSolar/logging.yaml"


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=DEFAULT_CONFIG,
    help="Path to configuration file",
)
@click.option(
    "--log-config",
    "-l",
    type=click.Path(exists=True),
    default=DEFAULT_LOG_CONFIG,
    help="Path to logging configuration file",
)
@click.pass_context  # type: ignore[arg-type]
def main(ctx: click.Context, config: str, log_config: str) -> None:
    """piSolar - Solar system monitoring service."""
    ctx.ensure_object(dict)

    setup_logging(log_config)
    ctx.obj["settings"] = Settings.from_yaml(config)


@main.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the monitoring service."""
    settings: Settings = ctx.obj["settings"]
    logger = get_logger("cli")

    logger.info("Starting piSolar monitoring service")

    LoggingConsumer()

    sqlite_consumer: SqliteConsumer | None = None
    if settings.storage.enabled:
        sqlite_consumer = SqliteConsumer(
            db_path=settings.storage.db_path,
            retention_days=settings.storage.retention_days,
        )
        logger.info("SQLite storage enabled: %s", settings.storage.db_path)

    if settings.rabbitmq.enabled:
        RabbitMQConsumer(settings.rabbitmq)
        logger.info(
            "RabbitMQ publishing enabled: exchange=%s",
            settings.rabbitmq.exchange,
        )

    mysql_consumer: MySQLConsumer | None = None
    if settings.mysql.enabled:
        mysql_consumer = MySQLConsumer(settings.mysql)
        logger.info("MySQL storage enabled: %s", settings.mysql.url)

    metrics_service = MetricsService()
    scheduler = SchedulerService()

    if settings.temperature.enabled:
        sensor_configs = [
            {"id": s.id, "address": s.address} for s in settings.temperature.sensors
        ]
        temp_sensor = TemperatureSensor(sensor_configs)

        def read_temperature() -> None:
            readings = temp_sensor.read()
            metrics_service.record(readings)

        scheduler.add_job(
            read_temperature,
            settings.temperature.schedule.cron,
            job_id="temperature_sensor",
        )
        logger.info("Temperature sensor enabled with %d sensors", len(sensor_configs))

    if settings.renogy.enabled and settings.renogy.sensors:
        # Create sensors for each configured Renogy device
        renogy_sensors = [RenogySensor(config) for config in settings.renogy.sensors]

        def read_renogy() -> None:
            for sensor in renogy_sensors:
                try:
                    readings = sensor.read()
                    metrics_service.record(readings)
                except Exception as e:
                    logger.error("Failed to read from %s: %s", sensor.name, e)

        scheduler.add_job(
            read_renogy,
            settings.renogy.schedule.cron,
            job_id="renogy_sensors",
        )
        logger.info(
            "Renogy sensors enabled: %s",
            ", ".join(s.name for s in renogy_sensors),
        )

    if sqlite_consumer and settings.storage.prune_schedule.enabled:

        def prune_readings() -> None:
            sqlite_consumer.prune()

        scheduler.add_job(
            prune_readings,
            settings.storage.prune_schedule.cron,
            job_id="prune_readings",
        )
        logger.info(
            "Prune job enabled: retention=%d days, schedule=%s",
            settings.storage.retention_days,
            settings.storage.prune_schedule.cron,
        )

    logger.info("Scheduler starting...")
    try:
        scheduler.start()
    finally:
        if mysql_consumer:
            mysql_consumer.close()


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Check sensor availability."""
    settings: Settings = ctx.obj["settings"]

    click.echo("Checking sensors...")

    if settings.temperature.enabled and settings.temperature.sensors:
        sensor_configs = [
            {"id": s.id, "address": s.address} for s in settings.temperature.sensors
        ]
        temp_sensor = TemperatureSensor(sensor_configs)
        try:
            readings = temp_sensor.read()
            click.echo(f"  Temperature sensors: ✓ {len(readings)} sensor(s) read")
        except Exception as e:
            click.echo(f"  Temperature sensors: ✗ {e}")
    else:
        click.echo("  Temperature sensors: ✗ no sensors configured")

    if settings.renogy.enabled and settings.renogy.sensors:
        for sensor_config in settings.renogy.sensors:
            sensor = RenogySensor(sensor_config)
            conn_type = sensor_config.read_type
            try:
                readings = sensor.read()
                count = len(readings)
                click.echo(
                    f"  Renogy [{conn_type}] {sensor.name}: ✓ {count} reading(s)"
                )
            except Exception as e:
                click.echo(f"  Renogy [{conn_type}] {sensor.name}: ✗ {e}")
    else:
        click.echo("  Renogy sensors: ✗ no sensors configured")


@main.command()
@click.pass_context
def read_once(ctx: click.Context) -> None:
    """Read all sensors once and output to console."""
    settings: Settings = ctx.obj["settings"]
    logger = get_logger("cli")

    click.echo("Reading sensors...")

    LoggingConsumer()

    mysql_consumer: MySQLConsumer | None = None
    if settings.mysql.enabled:
        mysql_consumer = MySQLConsumer(settings.mysql)
        logger.info("MySQL storage enabled: %s", settings.mysql.url)

    if settings.storage.enabled:
        SqliteConsumer(
            db_path=settings.storage.db_path,
            retention_days=settings.storage.retention_days,
        )
        logger.info("SQLite storage enabled: %s", settings.storage.db_path)

    if settings.rabbitmq.enabled:
        RabbitMQConsumer(settings.rabbitmq)
        logger.info(
            "RabbitMQ publishing enabled: exchange=%s",
            settings.rabbitmq.exchange,
        )

    metrics_service = MetricsService()
    all_readings = []

    if settings.temperature.enabled:
        sensor_configs = [
            {"id": s.id, "address": s.address} for s in settings.temperature.sensors
        ]
        temp_sensor = TemperatureSensor(sensor_configs)
        readings = temp_sensor.read()
        all_readings.extend(readings)
        metrics_service.record(readings)
        for reading in readings:
            # Temperature sensors always return TemperatureReading
            temp_reading = reading  # type: TemperatureReading
            click.echo(
                f"  [temp] {temp_reading.name}: {temp_reading.value:.2f} {temp_reading.unit}"
            )

    if settings.renogy.enabled and settings.renogy.sensors:
        for sensor_config in settings.renogy.sensors:
            sensor = RenogySensor(sensor_config)
            conn_type = sensor_config.read_type
            try:
                readings = sensor.read()
                all_readings.extend(readings)
                metrics_service.record(readings)
                for reading in readings:
                    click.echo(f"  [solar/{conn_type}] {reading.name}:")
                    # Display all available data from to_dict()
                    data = reading.to_dict()
                    for key, value in data.items():
                        if key in ("type", "name", "read_time"):
                            continue  # Skip metadata already shown
                        # Format the key nicely
                        display_key = key.replace("_", " ").title()
                        click.echo(f"    {display_key}: {value}")
            except Exception as e:
                click.echo(f"  [solar/{conn_type}] {sensor.name}: ✗ {e}")

    if not all_readings:
        click.echo("  No readings available")
        if mysql_consumer:
            mysql_consumer.close()
        sys.exit(1)

    click.echo(f"\nTotal: {len(all_readings)} readings")

    if mysql_consumer:
        mysql_consumer.close()


@main.command()
@click.pass_context
def show_config(ctx: click.Context) -> None:
    """Display current configuration."""
    settings: Settings = ctx.obj["settings"]

    click.echo("Current configuration:")
    click.echo("  Temperature sensor:")
    click.echo(f"    enabled: {settings.temperature.enabled}")
    click.echo(f"    sensors: {len(settings.temperature.sensors)}")
    for sensor in settings.temperature.sensors:
        click.echo(f"      - {sensor.name}: {sensor.address}")
    click.echo(f"    schedule: {settings.temperature.schedule.cron}")

    click.echo("  Renogy sensors:")
    click.echo(f"    enabled: {settings.renogy.enabled}")
    click.echo(f"    schedule: {settings.renogy.schedule.cron}")
    click.echo(f"    sensors: {len(settings.renogy.sensors)}")
    for sensor_config in settings.renogy.sensors:
        if sensor_config.read_type == "bt":
            click.echo(f"      - {sensor_config.name} [bluetooth]:")
            click.echo(f"          mac_address: {sensor_config.mac_address}")
            click.echo(f"          device_alias: {sensor_config.device_alias}")
            click.echo(f"          scan_timeout: {sensor_config.scan_timeout}s")
        else:
            click.echo(f"      - {sensor_config.name} [serial/modbus]:")
            click.echo(f"          device_path: {sensor_config.device_path}")
            click.echo(f"          baud_rate: {sensor_config.baud_rate}")
            click.echo(f"          slave_address: {sensor_config.slave_address}")
        click.echo(f"          device_type: {sensor_config.device_type}")
        click.echo(f"          max_retries: {sensor_config.max_retries}")

    click.echo("  Metrics:")
    click.echo(f"    output_dir: {settings.metrics.output_dir}")

    click.echo("  Storage:")
    click.echo(f"    enabled: {settings.storage.enabled}")
    click.echo(f"    db_path: {settings.storage.db_path}")
    click.echo(f"    retention_days: {settings.storage.retention_days}")
    click.echo(f"    prune_schedule: {settings.storage.prune_schedule.cron}")
    click.echo(f"    prune_enabled: {settings.storage.prune_schedule.enabled}")
