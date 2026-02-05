"""Solar sensor reading for Renogy charge controller data.

This module defines the data model for readings from Renogy solar charge
controllers (Wanderer, Rover, etc.) via Bluetooth (BT-1/BT-2) or Modbus
(RS232/RS485).

Data Format References:
    - Official Renogy Rover Modbus Protocol (local):
      docs/rover_modbus.pdf (preferred) or docs/rover_modbus.docx
    - Renogy Modbus Protocol PDF (online mirror):
      https://github.com/cyrils/renogy-bt/blob/main/doc/Renogy%20Rover%20Modbus%20Protocol.pdf
    - SRNE MPPT Protocol (similar register layout):
      https://github.com/corbinbs/solern/blob/master/doc/SRNE_MPPT_Solar_Charge_Controller.md

Modbus Register Map (from docs/rover_modbus.docx):
    0x0100: Battery SOC (%)
    0x0101: Battery voltage (raw * 0.1 = V)
    0x0102: Charging current (raw * 0.01 = A)
    0x0103: Combined temperature register:
            - High byte: Controller temp (sign+magnitude: b7=sign, b0-b6=value)
            - Low byte: Battery temp (sign+magnitude: b7=sign, b0-b6=value)
    0x0104: Street light (load) voltage (raw * 0.1 = V)
    0x0105: Street light (load) current (raw * 0.01 = A)
    0x0106: Street light (load) power (W)
    0x0107: PV voltage (raw * 0.1 = V)
    0x0108: PV current (raw * 0.01 = A)
    0x0109: Charging power (W)
    0x010B: Battery min voltage today (raw * 0.1 = V)
    0x010C: Battery max voltage today (raw * 0.1 = V)
    0x010D: Max charging current today (raw * 0.01 = A)
    0x010E: Max discharging current today (raw * 0.01 = A)
    0x010F: Max charging power today (W)
    0x0110: Max discharging power today (W)
    0x0111: Charging amp-hours today (Ah)
    0x0112: Discharging amp-hours today (Ah)
    0x0113: Power generation today (raw * 0.0001 = kWh, or raw * 0.1 = Wh)
    0x0114: Power consumption today (raw * 0.0001 = kWh, or raw * 0.1 = Wh)
    0x0120: Charging status (high byte: light status, low byte: charge mode)
"""

from typing import Any

from pisolar.sensors.sensor_reading import SensorReading


class SolarReading(SensorReading):
    """Solar/charge-controller reading with typed fields for Renogy data.

    All fields are optional as not all devices/protocols return all values.
    Scale factors are applied during reading; values here are in final units.
    """

    # Device info (from 0x000A-0x0014 device info registers)
    model: str | None = None  # Controller model string
    device_id: int | None = None  # Modbus device ID (typically 1)

    # Battery status
    battery_percentage: int | None = None  # SOC % (0x0100, scale: 1)
    battery_voltage: float | None = None  # Volts (0x0101, scale: 0.1)
    battery_current: float | None = None  # Amps (0x0102, scale: 0.01)
    battery_temperature: int | None = None  # Celsius (0x0103 low byte, signed)
    battery_type: str | None = None  # open, sealed, gel, lithium, custom

    # Controller status
    controller_temperature: int | None = None  # Celsius (0x0103 high byte, signed)
    charging_status: str | None = None  # deactivated, activated, mppt, boost, etc.

    # Load output (street light)
    load_status: str | None = None  # on, off (from 0x0120 high byte b7)
    load_voltage: float | None = None  # Volts (0x0104, scale: 0.1)
    load_current: float | None = None  # Amps (0x0105, scale: 0.01)
    load_power: int | None = None  # Watts (0x0106, scale: 1)

    # PV (solar panel) input
    pv_voltage: float | None = None  # Volts (0x0107, scale: 0.1)
    pv_current: float | None = None  # Amps (0x0108, scale: 0.01)
    pv_power: int | None = None  # Watts (0x0109, scale: 1)

    # Daily statistics
    battery_min_voltage_today: float | None = None  # Volts (0x010B, scale: 0.1)
    battery_max_voltage_today: float | None = None  # Volts (0x010C, scale: 0.1)
    max_charging_current_today: float | None = None  # Amps (0x010D, scale: 0.01)
    max_discharging_current_today: float | None = None  # Amps (0x010E, scale: 0.01)
    max_charging_power_today: int | None = None  # Watts (0x010F, scale: 1)
    max_discharging_power_today: int | None = None  # Watts (0x0110, scale: 1)
    charging_amp_hours_today: int | None = None  # Ah (0x0111, scale: 1)
    discharging_amp_hours_today: int | None = None  # Ah (0x0112, scale: 1)
    power_generation_today: float | None = None  # Wh (0x0113, raw * 0.1)
    power_consumption_today: float | None = None  # Wh (0x0114, raw * 0.1)

    # Lifetime statistics
    power_generation_total: int | None = None  # Wh (0x0115-0x0116, 32-bit)

    @classmethod
    def from_raw_data(
        cls,
        sensor_type: str,
        name: str,
        data: dict[str, Any],
        read_duration_ms: float | None = None,
    ) -> "SolarReading":
        """Create a SolarReading from raw Renogy library data dict.

        Args:
            sensor_type: Type identifier (typically "solar")
            name: Device name/alias
            data: Raw data dictionary from Bluetooth or Modbus reader
            read_duration_ms: Optional read duration in milliseconds

        Returns:
            SolarReading instance with parsed values
        """
        # Filter out internal fields (__device, __client, function)
        filtered = {
            k: v for k, v in data.items() if not k.startswith("_") and k != "function"
        }
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
