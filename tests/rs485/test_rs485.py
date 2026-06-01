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

  # Load port/slave/adapter from config.yaml (recommended):
  poetry run python tests/rs485/test_rs485.py --config config/config.yaml

  # Specific port and address:
  poetry run python tests/rs485/test_rs485.py --port /dev/ttyAMA5 --slave 16

  # Raw pyserial transport (for GPIO UART adapters like DFRobot DFR0845):
  poetry run python tests/rs485/test_rs485.py --config config/config.yaml --raw

  # Live wind sensor test (SEN0483 shakeout when Renogy unavailable):
  poetry run python tests/rs485/test_rs485.py --port /dev/ttyAMA5 --slave 3 --wind

  # Sweep all common ports and addresses automatically:
  poetry run python tests/rs485/test_rs485.py --sweep
"""

import sys
import time

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip3 install pymodbus pyserial")
    sys.exit(1)

try:
    import serial as _serial
except ImportError:
    _serial = None  # type: ignore[assignment]


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def read_register_raw(port_path: str, slave: int, register: int, count: int = 1, baudrate: int = 9600) -> list[int] | None:
    """Read Modbus register(s) using raw pyserial — no buffer flush between TX and RX.

    Does NOT sleep between TX and RX — the response arrives immediately after
    TX completes on GPIO UART adapters (DFR0845). Any sleep would cause the
    response to be missed on the first read attempt.
    """
    if _serial is None:
        print("ERROR: pyserial not installed")
        return None
    payload = bytes([slave, 0x03, register >> 8, register & 0xFF, count >> 8, count & 0xFF])
    crc = _crc16(payload)
    frame = payload + bytes([crc & 0xFF, crc >> 8])
    expected = 3 + count * 2 + 2
    try:
        with _serial.Serial(port_path, baudrate=baudrate, bytesize=8, parity="N", stopbits=1, timeout=0.001) as port:
            port.reset_input_buffer()
            port.write(frame)
            port.flush()
            buf = bytearray()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                chunk = port.read(64)
                if chunk:
                    buf += chunk
                if len(buf) >= expected:
                    break
        if len(buf) < expected:
            return None
        computed = _crc16(bytes(buf[:-2]))
        received = buf[-2] | (buf[-1] << 8)
        if computed != received:
            return None
        return [(buf[3 + i * 2] << 8) | buf[4 + i * 2] for i in range(count)]
    except Exception as e:
        print(f"  raw serial error: {e}")
        return None

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


def _load_from_config(config_path: str) -> tuple[str, int, int, str]:
    """Load port, slave, baudrate, adapter from the first serial Renogy sensor in config.yaml.

    Returns:
        (port, slave_address, baud_rate, serial_adapter)
    """
    try:
        from pyaml_env import parse_config
    except ImportError:
        print("ERROR: pyaml_env not installed — cannot load config")
        sys.exit(1)

    cfg = parse_config(config_path)
    sensors = cfg.get("renogy", {}).get("sensors", [])
    for s in sensors:
        if s.get("read_type") == "serial":
            adapter = s.get("serial_adapter", "usb")
            if adapter == "uart":
                port = s.get("uart_device_path") or s.get("device_path", "/dev/ttyAMA5")
            else:
                port = s.get("device_path", "/dev/ttyUSB0")
            slave = int(s.get("slave_address", 1))
            baud = int(s.get("baud_rate", 9600))
            print(f"Loaded from config: port={port} slave={slave} baud={baud} adapter={adapter}")
            return port, slave, baud, adapter

    print("No serial Renogy sensor found in config — using defaults")
    return "/dev/ttyUSB0", 1, 9600, "usb"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test or sweep RS485 connection to Renogy controllers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load settings from config.yaml (recommended):
  %(prog)s --config config/config.yaml

  # Specific port and address:
  %(prog)s --port /dev/ttyAMA5 --slave 16

  # Raw pyserial transport (auto-selected when config has serial_adapter: uart):
  %(prog)s --config config/config.yaml --raw

  # Live wind sensor shakeout (SEN0483):
  %(prog)s --port /dev/ttyAMA5 --slave 3 --wind

  # Auto-sweep all ports and addresses:
  %(prog)s --sweep
        """,
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to piSolar config.yaml — loads port/slave/adapter automatically",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port path (overrides config)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=None,
        help="Baud rate (overrides config, default: 9600)",
    )
    parser.add_argument(
        "--slave",
        type=int,
        default=None,
        help="Modbus slave address (overrides config, default: 1)",
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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Use raw pyserial transport (auto-enabled when config has serial_adapter: uart)",
    )
    parser.add_argument(
        "--wind",
        action="store_true",
        help="Read SEN0483 wind speed register (0x0000) — shakeout test without Renogy",
    )

    args = parser.parse_args()

    if args.sweep:
        sweep(baudrate=args.baudrate or 9600, timeout=args.timeout)
        sys.exit(0)

    # Resolve port/slave/baud/adapter from config or CLI
    port, slave, baudrate, adapter = "/dev/ttyUSB0", 1, 9600, "usb"
    if args.config:
        port, slave, baudrate, adapter = _load_from_config(args.config)
    if args.port:
        port = args.port
    if args.slave is not None:
        slave = args.slave
    if args.baudrate is not None:
        baudrate = args.baudrate

    # Auto-enable raw transport for UART adapter
    use_raw = args.raw or adapter == "uart"

    if args.wind:
        print(f"Reading SEN0483 wind speed — port={port} slave={slave}")
        print("Press Ctrl+C to stop.\n")
        try:
            while True:
                regs = read_register_raw(port, slave, 0x0000, count=1, baudrate=baudrate)
                if regs is not None:
                    speed = regs[0] / 10.0
                    print(f"  Wind speed: {speed:.1f} m/s  (raw={regs[0]})")
                else:
                    print("  No response")
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopped.")
        sys.exit(0)

    if use_raw:
        print(f"Raw pyserial transport — port={port} slave={slave} adapter={adapter}")
        success = False
        for reg, label in [
            (0x0000, "reg 0x0000 (wind speed / generic first register)"),
            (0x0100, "reg 0x0100 (Renogy battery SOC)"),
        ]:
            print(f"  Trying {label}...")
            regs = read_register_raw(port, slave, reg, count=1, baudrate=baudrate)
            if regs is not None:
                print(f"  ✅ {label} = {regs[0]}")
                success = True
                break
            print(f"  ❌ No response")
        sys.exit(0 if success else 1)

    success = test_rs485_connection(
        port=port,
        baudrate=baudrate,
        slave_address=slave,
        timeout=args.timeout,
    )
    sys.exit(0 if success else 1)
