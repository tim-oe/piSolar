"""Renogy BT-2 sensor implementation."""

import configparser
from pathlib import Path
from string import Template
from typing import Any

from pisolar.logging_config import get_logger
from pisolar.sensors.base_sensor import BaseSensor
from pisolar.sensors.sensor_reading import SensorReading
from pisolar.sensors.solar_reading import SolarReading

logger = get_logger("sensors.renogy")

# Load template once at module level
_CONFIG_TEMPLATE: Template | None = None


def _get_config_template() -> Template:
    """Load the renogy_bt.ini.template file."""
    global _CONFIG_TEMPLATE
    if _CONFIG_TEMPLATE is None:
        # Try config directory relative to project root
        template_path = Path(__file__).parent.parent.parent.parent / "config" / "renogy_bt.ini.template"
        if template_path.exists():
            _CONFIG_TEMPLATE = Template(template_path.read_text())
        else:
            # Fallback: try /etc/pisolar
            etc_path = Path("/etc/pisolar/renogy_bt.ini.template")
            if etc_path.exists():
                _CONFIG_TEMPLATE = Template(etc_path.read_text())
            else:
                raise FileNotFoundError(
                    f"Renogy config template not found at {template_path} or {etc_path}"
                )
    return _CONFIG_TEMPLATE


def _bluetooth_available() -> bool:
    """Return True if a Bluetooth adapter is present (Linux sysfs), or on non-Linux."""
    bt = Path("/sys/class/bluetooth")
    if not bt.exists():
        return True  # non-Linux or no sysfs; let the library handle it
    for adapter in bt.iterdir():
        if adapter.is_dir() and adapter.name.startswith("hci"):
            # Adapter present; sysfs "powered" can lag BlueZ state, so don't require powered==1
            return True
    return False


def _build_config(
    mac_address: str,
    device_alias: str,
    device_id: int = 255,
    adapter: str = "hci0",
) -> configparser.ConfigParser:
    """Build renogybt ConfigParser from template and parameters."""
    template = _get_config_template()
    ini_content = template.substitute(
        mac_address=mac_address,
        device_alias=device_alias,
        device_id=device_id,
        adapter=adapter,
    )
    config = configparser.ConfigParser(inline_comment_prefixes=("#",))
    config.read_string(ini_content)
    return config


class RenogySensor(BaseSensor):
    """Renogy BT-2 Bluetooth module sensor."""

    def __init__(
        self,
        mac_address: str,
        device_alias: str = "BT-2",
        device_id: int = 255,
    ) -> None:
        """
        Initialize the Renogy sensor.

        Args:
            mac_address: Bluetooth MAC address of the BT-2 module
            device_alias: Friendly name for the device
            device_id: Modbus device id (255 = stand-alone, see renogy-bt readme for hub/daisy)
        """
        self._mac_address = mac_address
        self._device_alias = device_alias
        self._device_id = device_id

    @property
    def sensor_type(self) -> str:
        """Return the sensor type identifier."""
        return "solar"

    def read(self) -> list[SensorReading]:
        """Read data from the Renogy BT-2 module."""
        import asyncio

        if not _bluetooth_available():
            raise RuntimeError(
                "No powered Bluetooth adapter found. Turn on Bluetooth and try again."
            )

        from renogybt import RoverClient

        config = _build_config(
            self._mac_address,
            self._device_alias,
            self._device_id,
        )
        data_collected: dict[str, Any] = {}

        read_complete = False

        def on_data_received(client: Any, data: dict[str, Any]) -> None:
            nonlocal read_complete
            data_collected.update(data)
            read_complete = True
            # Stop the client after receiving data (no polling mode)
            try:
                client.stop()
            except Exception as e:
                logger.debug("Non-fatal error during BLE disconnect: %s", e)

        def on_error(client: Any, error: Any) -> None:
            # Note: library calls stop() after this callback, so don't call it here
            logger.error("Renogy read error: %s", error)

        # Suppress "Task exception was never retrieved" for BLE disconnect errors
        # and force-resolve the future if disconnect fails
        def _handle_exception(loop: Any, context: dict[str, Any]) -> None:
            exception = context.get("exception")
            if isinstance(exception, EOFError):
                logger.debug("BLE disconnect EOFError (non-fatal): %s", context.get("message"))
                # Force-resolve the future if it exists and isn't done
                # This prevents the event loop from hanging
                if hasattr(client, "future") and client.future and not client.future.done():
                    client.future.set_result("DISCONNECT_ERROR")
            else:
                # Use default handler for other exceptions
                loop.default_exception_handler(context)

        # Get the event loop that RoverClient will use
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; create one (RoverClient.start() will use it)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        old_handler = loop.get_exception_handler()
        loop.set_exception_handler(_handle_exception)

        client: Any = None
        try:
            client = RoverClient(
                config,
                on_data_callback=on_data_received,
                on_error_callback=on_error,
            )
            client.start()
        finally:
            loop.set_exception_handler(old_handler)

        reading = SolarReading.from_raw_data(
            sensor_type=self.sensor_type,
            name=self._device_alias,
            data=data_collected,
        )
        readings: list[SensorReading] = [reading]

        logger.info(
            "Read %d field(s) from Renogy device %s",
            len(data_collected),
            self._device_alias,
        )

        return readings
