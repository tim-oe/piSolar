#!/usr/bin/env python3
"""
RS485 diagnostic test script for Renogy Rover Elite.

This script tests communication with the Renogy Rover Elite 40A charge controller
via RS485 (Modbus RTU protocol) using the VERIFIED pinout:
  - Pin 7 = A+ (Data+)
  - Pin 6 = B- (Data-)
  - Pin 5 = GND

Verified: 2026-02-07 with Rover Elite 40A

Usage examples:

  # Single port/address test (default USB, slave 1):
  poetry run python tests/rs485/test_rs485.py

  # Specific port and address:
  poetry run python tests/rs485/test_rs485.py --port /dev/ttyAMA5 --slave 16

  # Sweep all common ports and addresses automatically:
  poetry run python tests/rs485/test_rs485.py --sweep

  # Longer timeout (useful for UART adapters with slow turnaround):
  poetry run python tests/rs485/test_rs485.py --port /dev/ttyAMA5 --slave 16 --timeout 10
"""

import sys
import time

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip3 install pymodbus pyserial")
    sys.exit(1)

# Ports to sweep in order (USB adapters first, then UART devices)
SWEEP_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyRS232",
    "/dev/ttyAMA0",
    "/dev/ttyAMA1",
    "/dev/ttyAMA2",
    "/dev/ttyAMA3",
    "/dev/ttyAMA4",
    "/dev/ttyAMA5",
    "/dev/ttyS0",
]

# Addresses to sweep (Renogy defaults 1 and 16 first, then others)
SWEEP_ADDRESSES = [16, 1, 2, 3, 4, 5, 6, 247]

TEST_REGISTERS = [
    (0x0100, "Battery SOC", 1, "%"),
    (0x0101, "Battery Voltage", 0.1, "V"),
    (0x0107, "Solar Panel Voltage", 0.1, "V"),
    (0x0102, "Charging Current", 0.01, "A"),
    (0x0109, "Solar Panel Power", 1, "W"),
]


def _open_client(port: str, baudrate: int, timeout: float) -> ModbusSerialClient | None:
    """Open a Modbus serial client, return None if port unavailable."""
    try:
        client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
        )
        if client.connect():
            return client
        print(f"  Could not open {port}")
        return None
    except Exception as e:
        print(f"  {port}: {e}")
        return None


def probe_address(client: ModbusSerialClient, slave_address: int) -> bool:
    """Return True if the slave responds to a single register read."""
    try:
        result = client.read_holding_registers(
            address=0x0100, count=1, device_id=slave_address
        )
        return not result.isError()
    except Exception:
        return False


def test_rs485_connection(
    port: str = "/dev/ttyUSB0",
    baudrate: int = 9600,
    slave_address: int = 1,
    timeout: float = 3.0,
) -> bool:
    """Test RS485 connection to a Renogy controller.

    Args:
        port: Serial port path
        baudrate: Baud rate (9600 for Renogy)
        slave_address: Modbus slave address
        timeout: Per-register read timeout in seconds

    Returns:
        True if at least one register was read successfully.
    """
    print("=" * 70)
    print("RS485 Modbus Connection Test - Rover Elite 40A")
    print("=" * 70)
    print(f"Port:          {port}")
    print(f"Baud Rate:     {baudrate}")
    print(f"Slave Address: {slave_address}")
    print(f"Timeout:       {timeout}s per register")
    print(f"Protocol:      Modbus RTU")
    print("\nVerified Pinout:")
    print("  Pin 7 → RS485 A+ (Data+)")
    print("  Pin 6 → RS485 B- (Data-)")
    print("  Pin 5 → Ground (GND)")
    print("-" * 70)

    print("\n[1] Opening serial port...")
    client = _open_client(port, baudrate, timeout)
    if client is None:
        print("❌ FAILED: Could not connect to serial port")
        print("\nTroubleshooting:")
        print("  1. Check device exists:  ls -la /dev/tty*")
        print("  2. Check permissions:    sudo usermod -a -G dialout $USER")
        print("  3. Log out/in after adding to dialout group")
        print("  4. For USB: verify adapter connected with lsusb")
        print("  5. For UART: verify dtoverlay in /boot/firmware/config.txt")
        return False

    print(f"✓ Opened {port}")

    print("\n[2] Testing Modbus registers...")
    success_count = 0

    for reg_addr, name, scale, unit in TEST_REGISTERS:
        try:
            result = client.read_holding_registers(
                address=reg_addr, count=1, device_id=slave_address
            )
            if result.isError():
                print(f"  ❌ 0x{reg_addr:04X} ({name}): ERROR - {result}")
            else:
                raw_value = result.registers[0]
                scaled_value = raw_value * scale
                print(
                    f"  ✓ 0x{reg_addr:04X} ({name}): {scaled_value:.2f} {unit}"
                    f"  (raw: {raw_value})"
                )
                success_count += 1
        except Exception as e:
            print(f"  ❌ 0x{reg_addr:04X} ({name}): {e}")

    client.close()

    print(f"\n{'-' * 70}")
    print(f"Results: {success_count}/{len(TEST_REGISTERS)} registers read successfully")

    if success_count == 0:
        print("\n❌ NO DATA RECEIVED")
        print("\nNext steps:")
        print("  1. Run --sweep to check all ports and addresses automatically")
        print("  2. Verify RS485 wiring:  A+ → RJ45 pin 7,  B- → pin 6,  GND → pin 5")
        print("  3. Try swapping A and B wires once")
        print("  4. For UART adapters: confirm TX/RX are crossed (Pi TX → module RX)")
        print("  5. Try a longer timeout: --timeout 10")
    elif success_count < len(TEST_REGISTERS):
        print("\n⚠ PARTIAL SUCCESS - some registers unavailable (normal for some models)")
    else:
        print("\n✅ SUCCESS - all registers read successfully!")

    return success_count > 0


def sweep(baudrate: int = 9600, timeout: float = 2.0) -> None:
    """Sweep all common ports and slave addresses to find a responding device.

    Args:
        baudrate: Baud rate to use for all attempts
        timeout: Per-probe timeout in seconds (keep low for fast sweep)
    """
    print("=" * 70)
    print("RS485 Sweep - scanning ports and slave addresses")
    print("=" * 70)
    print(f"Ports:     {SWEEP_PORTS}")
    print(f"Addresses: {SWEEP_ADDRESSES}")
    print(f"Timeout:   {timeout}s per probe")
    print("-" * 70)

    found: list[tuple[str, int]] = []

    for port in SWEEP_PORTS:
        print(f"\nPort: {port}")
        client = _open_client(port, baudrate, timeout)
        if client is None:
            print("  (skipped — could not open)")
            continue

        for addr in SWEEP_ADDRESSES:
            sys.stdout.write(f"  slave {addr:3d} ... ")
            sys.stdout.flush()
            if probe_address(client, addr):
                print("✓ RESPONSE")
                found.append((port, addr))
            else:
                print("no response")
            # Brief inter-request gap
            time.sleep(0.1)

        client.close()

    print(f"\n{'=' * 70}")
    if found:
        print(f"✅ Found {len(found)} responding device(s):")
        for port, addr in found:
            print(f"   port={port}  slave={addr}")
        print(f"\nRun full test with:")
        port, addr = found[0]
        print(f"  poetry run python tests/rs485/test_rs485.py --port {port} --slave {addr}")
    else:
        print("❌ No responding devices found on any port/address combination")
        print("\nPhysical checklist:")
        print("  - A/B polarity: try swapping A and B wires")
        print("  - GND: must be connected end-to-end (Pi GND, adapter GND, Renogy pin 5)")
        print("  - Power: DFR0845 needs 5V (not 3.3V) on its VCC pin")
        print("  - UART overlay: check /boot/firmware/config.txt and dmesg | grep ttyAMA")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test or sweep RS485 connection to Renogy controllers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single port/address test:
  %(prog)s --port /dev/ttyAMA5 --slave 16

  # Auto-sweep all ports and addresses:
  %(prog)s --sweep

  # Sweep with longer timeout (slow UART adapters):
  %(prog)s --sweep --timeout 3
        """,
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        help="Serial port path (default: /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=9600,
        help="Baud rate (default: 9600)",
    )
    parser.add_argument(
        "--slave",
        type=int,
        default=1,
        help="Modbus slave address (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Per-register read timeout in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Sweep all common ports and slave addresses to find device",
    )

    args = parser.parse_args()

    if args.sweep:
        sweep(baudrate=args.baudrate, timeout=args.timeout)
        sys.exit(0)

    success = test_rs485_connection(
        port=args.port,
        baudrate=args.baudrate,
        slave_address=args.slave,
        timeout=args.timeout,
    )
    sys.exit(0 if success else 1)
