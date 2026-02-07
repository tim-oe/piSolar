#!/usr/bin/env python3
"""
RS485 diagnostic test script for Renogy Rover Elite.

This script tests communication with the Renogy Rover Elite 40A charge controller
via RS485 (Modbus RTU protocol) using the VERIFIED pinout:
  - Pin 7 = A+ (Data+)
  - Pin 6 = B- (Data-)
  - Pin 5 = GND

Verified: 2026-02-07 with Rover Elite 40A
"""

import sys
import time

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip3 install pymodbus pyserial")
    sys.exit(1)


def test_rs485_connection(
    port="/dev/ttyUSB0",
    baudrate=9600,
    slave_address=1,
    verbose=True
):
    """Test RS485 connection to Renogy Rover Elite.
    
    Args:
        port: Serial port path
        baudrate: Baud rate (should be 9600 for Renogy)
        slave_address: Modbus slave address (default 1)
        verbose: Print detailed debug information
    """
    print(f"=" * 70)
    print(f"RS485 Modbus Connection Test - Rover Elite 40A")
    print(f"=" * 70)
    print(f"Port:          {port}")
    print(f"Baud Rate:     {baudrate}")
    print(f"Slave Address: {slave_address}")
    print(f"Protocol:      Modbus RTU")
    print(f"\nVerified Pinout:")
    print(f"  Pin 7 → RS485 A+ (Data+)")
    print(f"  Pin 6 → RS485 B- (Data-)")
    print(f"  Pin 5 → Ground (GND)")
    print(f"-" * 70)
    
    # Create Modbus client
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=3
    )
    
    # Test connection
    print("\n[1] Testing connection...")
    if not client.connect():
        print("❌ FAILED: Could not connect to serial port")
        print("\nTroubleshooting:")
        print("  1. Check that device exists: ls -la /dev/ttyUSB*")
        print("  2. Check permissions: sudo usermod -a -G dialout $USER")
        print("  3. Log out and back in after adding to dialout group")
        print("  4. Verify USB adapter is connected: lsusb")
        return False
    
    print("✓ Connected to serial port")
    
    # Test registers
    test_registers = [
        (0x0100, "Battery SOC", 1, "%"),
        (0x0101, "Battery Voltage", 0.1, "V"),
        (0x0107, "Solar Panel Voltage", 0.1, "V"),
        (0x0102, "Charging Current", 0.01, "A"),
        (0x0109, "Solar Panel Power", 1, "W"),
    ]
    
    print("\n[2] Testing Modbus registers...")
    success_count = 0
    
    for reg_addr, name, scale, unit in test_registers:
        try:
            result = client.read_holding_registers(
                address=reg_addr,
                count=1,
                device_id=slave_address
            )
            
            if result.isError():
                print(f"  ❌ Register 0x{reg_addr:04X} ({name}): ERROR - {result}")
            else:
                raw_value = result.registers[0]
                scaled_value = raw_value * scale
                print(f"  ✓ Register 0x{reg_addr:04X} ({name}): {scaled_value:.2f} {unit} (raw: {raw_value})")
                success_count += 1
                
        except Exception as e:
            print(f"  ❌ Register 0x{reg_addr:04X} ({name}): EXCEPTION - {e}")
    
    client.close()
    
    # Summary
    print(f"\n{'-' * 70}")
    print(f"Results: {success_count}/{len(test_registers)} registers read successfully")
    
    if success_count == 0:
        print("\n❌ NO DATA RECEIVED - Check wiring:")
        print("\nVerified Rover Elite 40A Pinout:")
        print("  RJ45 Pin 7 → RS485 Adapter A+")
        print("  RJ45 Pin 6 → RS485 Adapter B-")
        print("  RJ45 Pin 5 → RS485 Adapter GND")
        print("\nIf using different Rover model, pinout may differ!")
        
    elif success_count < len(test_registers):
        print(f"\n⚠ PARTIAL SUCCESS - Some registers failed")
        print("   This is normal - some registers may not be available")
        
    else:
        print(f"\n✅ SUCCESS - All registers read successfully!")
        
    return success_count > 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test RS485 connection to Renogy Rover Elite")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port path")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baud rate")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave address")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    success = test_rs485_connection(
        port=args.port,
        baudrate=args.baudrate,
        slave_address=args.slave,
        verbose=args.verbose
    )
    
    sys.exit(0 if success else 1)
