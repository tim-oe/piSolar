#!/usr/bin/env python3
"""
RS485 shakeout test using DFRobot SEN0644 illuminance sensor.

Uses the same DFRobot DFR0845 UART-RS485 adapter as the Renogy path,
but reads a SEN0644 lux sensor instead — useful when the Renogy port is
unavailable but you need to verify:
  - Pi UART GPIO pins are wired and configured correctly
  - DFRobot DFR0845 board is functional
  - RS485 bus communication is end-to-end working

SEN0644 Modbus registers (default slave address 0x01):
  0x0002  UINT16 RO  illuminance high 16 bits  ┐ combine to 32-bit uint
  0x0003  UINT16 RO  illuminance low  16 bits  ┘ divide by 1000 = lux
  0x0064  UINT16 RW  device address (1-254)

Reference: https://wiki.dfrobot.com/sen0644/docs/19609

Usage:
  poetry run python tests/rs485/test_rs485_sen0644.py --port /dev/ttyAMA5
  poetry run python tests/rs485/test_rs485_sen0644.py --port /dev/ttyAMA5 --slave 1 --count 5
  poetry run python tests/rs485/test_rs485_sen0644.py --sweep
"""

import sys
import time

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip install pymodbus pyserial")
    sys.exit(1)

# SEN0644 register map
_REG_LUX_HIGH = 0x0002   # High 16 bits of 32-bit illuminance value
_REG_LUX_LOW  = 0x0003   # Low  16 bits
_REG_ADDR     = 0x0064   # Device address register (RW)
_LUX_SCALE    = 1000.0   # Raw value / 1000 = lux

SWEEP_PORTS = [
    "/dev/ttyAMA5",
    "/dev/ttyAMA4",
    "/dev/ttyAMA3",
    "/dev/ttyAMA2",
    "/dev/ttyAMA1",
    "/dev/ttyAMA0",
    "/dev/ttyUSB0",
]
SWEEP_ADDRESSES = [1, 2, 3, 4, 5]


def _open_client(port: str, baudrate: int, timeout: float) -> ModbusSerialClient | None:
    try:
        client = ModbusSerialClient(
            port=port, baudrate=baudrate, bytesize=8, parity="N", stopbits=1, timeout=timeout
        )
        if client.connect():
            return client
        print(f"  Could not open {port}")
        return None
    except Exception as e:
        print(f"  {port}: {e}")
        return None


def read_lux(client: ModbusSerialClient, slave: int) -> float | None:
    """Read lux from SEN0644. Returns lux value or None on failure."""
    try:
        result = client.read_holding_registers(address=_REG_LUX_HIGH, count=2, device_id=slave)
        if result.isError():
            return None
        raw = (result.registers[0] << 16) | result.registers[1]
        return raw / _LUX_SCALE
    except Exception:
        return None


def test_sen0644(
    port: str = "/dev/ttyAMA5",
    baudrate: int = 9600,
    slave: int = 1,
    timeout: float = 3.0,
    count: int = 3,
) -> bool:
    """Test SEN0644 illuminance sensor on the given port/address.

    Args:
        port:     Serial port path
        baudrate: Baud rate (9600 for SEN0644)
        slave:    Modbus slave address (default 1)
        timeout:  Per-read timeout in seconds
        count:    Number of readings to take

    Returns:
        True if at least one reading succeeded.
    """
    print("=" * 70)
    print("SEN0644 Illuminance Sensor - RS485 Shakeout Test")
    print("=" * 70)
    print(f"Port:          {port}")
    print(f"Baud Rate:     {baudrate}")
    print(f"Slave Address: {slave}")
    print(f"Timeout:       {timeout}s")
    print(f"Readings:      {count}")
    print("-" * 70)

    client = _open_client(port, baudrate, timeout)
    if client is None:
        print("❌ Could not open serial port")
        print(f"\nCheck: ls -l /dev/ttyAMA* and dmesg | grep ttyAMA")
        return False

    print(f"✓ Opened {port}")
    print(f"\nReading lux (registers 0x{_REG_LUX_HIGH:04X}/0x{_REG_LUX_LOW:04X})...")

    success = 0
    for i in range(1, count + 1):
        lux = read_lux(client, slave)
        if lux is not None:
            print(f"  [{i}/{count}] ✓ {lux:.3f} lux")
            success += 1
        else:
            print(f"  [{i}/{count}] ❌ no response")
        if i < count:
            time.sleep(1.0)

    client.close()

    print(f"\n{'-' * 70}")
    print(f"Results: {success}/{count} readings successful")

    if success == 0:
        print("\n❌ NO RESPONSE from SEN0644")
        print("\nChecklist:")
        print("  1. Verify slave address (default 0x01) — run --sweep to scan")
        print("  2. Check A/B wiring — try swapping A and B once")
        print("  3. Confirm GND connected on RS485 screw terminal")
        print("  4. DFRobot VCC must be 5V (not 3.3V)")
        print("  5. Watch DFRobot LEDs — RX should flicker on each attempt")
        print("     If RX flickers but no TX: sensor not responding (address/wiring)")
        print("     If no RX flicker: UART not reaching DFRobot (pin/overlay issue)")
    else:
        print(f"\n✅ SEN0644 responding — UART→DFRobot→RS485 chain is working!")
        print(f"   Pi GPIO12/13 → ttyAMA5 → DFRobot → RS485 bus is verified.")

    return success > 0


def sweep(baudrate: int = 9600, timeout: float = 2.0) -> None:
    """Sweep ports and addresses to find a responding SEN0644."""
    print("=" * 70)
    print("SEN0644 Sweep - scanning ports and slave addresses")
    print("=" * 70)
    print(f"Ports:     {SWEEP_PORTS}")
    print(f"Addresses: {SWEEP_ADDRESSES}")
    print("-" * 70)

    found: list[tuple[str, int, float]] = []

    for port in SWEEP_PORTS:
        print(f"\nPort: {port}")
        client = _open_client(port, baudrate, timeout)
        if client is None:
            print("  (skipped)")
            continue

        for addr in SWEEP_ADDRESSES:
            sys.stdout.write(f"  slave {addr} ... ")
            sys.stdout.flush()
            lux = read_lux(client, addr)
            if lux is not None:
                print(f"✓  {lux:.3f} lux")
                found.append((port, addr, lux))
            else:
                print("no response")
            time.sleep(0.1)

        client.close()

    print(f"\n{'=' * 70}")
    if found:
        print(f"✅ Found {len(found)} responding sensor(s):")
        for port, addr, lux in found:
            print(f"   port={port}  slave={addr}  lux={lux:.3f}")
        port, addr, _ = found[0]
        print(f"\nRun full test with:")
        print(f"  poetry run python tests/rs485/test_rs485_sen0644.py --port {port} --slave {addr}")
    else:
        print("❌ No SEN0644 found on any port/address")
        print("\nPhysical checklist:")
        print("  - DFRobot RX LED should flicker when Pi sends — confirms UART path")
        print("  - If no RX flicker: check dtoverlay in /boot/firmware/config.txt")
        print("  - If RX flickers but no response: check A/B polarity and GND")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Shakeout test for DFRobot SEN0644 illuminance sensor over RS485",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port /dev/ttyAMA5
  %(prog)s --port /dev/ttyAMA5 --slave 1 --count 5 --timeout 5
  %(prog)s --sweep
        """,
    )
    parser.add_argument("--port", default="/dev/ttyAMA5", help="Serial port (default: /dev/ttyAMA5)")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave address (default: 1)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Read timeout seconds (default: 3.0)")
    parser.add_argument("--count", type=int, default=3, help="Number of readings to take (default: 3)")
    parser.add_argument("--sweep", action="store_true", help="Sweep all ports and addresses")

    args = parser.parse_args()

    if args.sweep:
        sweep(baudrate=args.baudrate, timeout=args.timeout)
        sys.exit(0)

    success = test_sen0644(
        port=args.port,
        baudrate=args.baudrate,
        slave=args.slave,
        timeout=args.timeout,
        count=args.count,
    )
    sys.exit(0 if success else 1)
