"""Solar sensor reading for Renogy charge controller data."""

from typing import Any

from pisolar.sensors.sensor_reading import SensorReading


class SolarReading(SensorReading):
    """Solar/charge-controller reading with typed fields for Renogy data."""

    # Device info
    model: str | None = None
    device_id: int | None = None

    # Battery status
    battery_percentage: int | None = None
    battery_voltage: float | None = None
    battery_current: float | None = None
    battery_temperature: int | None = None  # Celsius
    battery_type: str | None = None  # open, sealed, gel, lithium, custom

    # Controller status
    controller_temperature: int | None = None  # Celsius
    charging_status: str | None = None  # deactivated, activated, mppt, etc.

    # Load output
    load_status: str | None = None  # on, off
    load_voltage: float | None = None
    load_current: float | None = None
    load_power: int | None = None  # watts

    # PV (solar panel) input
    pv_voltage: float | None = None
    pv_current: float | None = None
    pv_power: int | None = None  # watts

    # Daily statistics
    max_charging_power_today: int | None = None  # watts
    max_discharging_power_today: int | None = None  # watts
    charging_amp_hours_today: int | None = None  # Ah
    discharging_amp_hours_today: int | None = None  # Ah
    power_generation_today: int | None = None  # Wh
    power_consumption_today: int | None = None  # Wh

    # Lifetime statistics
    power_generation_total: int | None = None  # Wh

    @classmethod
    def from_raw_data(
        cls,
        sensor_type: str,
        name: str,
        data: dict[str, Any],
        read_duration_ms: float | None = None,
    ) -> "SolarReading":
        """Create a SolarReading from raw Renogy library data dict."""
        # Filter out internal fields (__device, __client, function)
        filtered = {k: v for k, v in data.items() if not k.startswith("_") and k != "function"}
        return cls(
            type=sensor_type,
            name=name,
            read_duration_ms=read_duration_ms,
            **filtered,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert reading to dictionary, excluding None values."""
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO string for JSON serialization
        if "read_time" in data:
            data["read_time"] = data["read_time"].isoformat()
        return data
