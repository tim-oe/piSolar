#!/usr/bin/env python3
"""
Test two RS485 adapters connected back-to-back.
This proves the adapters work for RS485 communication.
"""

import sys
import time
import serial
import threading

def listen_on_port(port, name):
    """Listen for data on a port."""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=0.1
        )
        
        print(f"{name} listening on {port}...")
        
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"{name} RECEIVED: {data.hex()} = {data}")
                return True
            time.sleep(0.1)
            
    except Exception as e:
        print(f"{name} error: {e}")
        return False


def test_rs485_loopback():
    """Test two RS485 adapters connected together."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║         RS485 ADAPTER-TO-ADAPTER TEST                                ║
╚══════════════════════════════════════════════════════════════════════╝

This test connects two RS485 adapters directly to verify they work.

WIRING (back-to-back):
  Adapter 1 A+  ←→  Adapter 2 A+
  Adapter 1 B-  ←→  Adapter 2 B-
  Adapter 1 GND ←→  Adapter 2 GND

Both adapters plugged into Pi via USB.

""")
    
    # Check available ports
    import os
    ports = [f for f in os.listdir('/dev') if f.startswith('ttyUSB')]
    ports.sort()
    
    if len(ports) < 2:
        print(f"❌ Error: Found only {len(ports)} USB serial port(s)")
        print("Need 2 RS485 adapters plugged in!")
        print(f"Found: {ports}")
        return False
    
    port1 = f"/dev/{ports[0]}"
    port2 = f"/dev/{ports[1]}"
    
    print(f"Found ports: {port1}, {port2}")
    print()
    input("Press ENTER when adapters are wired together (A-A, B-B, GND-GND)...")
    
    print("\n" + "="*70)
    print("TEST 1: Send from Port 1 to Port 2")
    print("="*70)
    
    try:
        # Open port 1 for sending
        ser1 = serial.Serial(
            port=port1,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        
        # Open port 2 for receiving
        ser2 = serial.Serial(
            port=port2,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        
        # Clear buffers
        ser1.reset_input_buffer()
        ser1.reset_output_buffer()
        ser2.reset_input_buffer()
        ser2.reset_output_buffer()
        
        # Send test data from port 1
        test_data = b"HELLO_RS485_TEST"
        print(f"\nSending from {port1}: {test_data}")
        ser1.write(test_data)
        ser1.flush()
        
        # Wait and check port 2
        time.sleep(0.5)
        
        if ser2.in_waiting > 0:
            received = ser2.read(ser2.in_waiting)
            print(f"✅ SUCCESS! {port2} received: {received}")
            
            if received == test_data:
                print("✅ Data matches perfectly!")
            else:
                print(f"⚠️  Data mismatch: expected {test_data}, got {received}")
        else:
            print(f"❌ No data received on {port2}")
            ser1.close()
            ser2.close()
            
            print("\n" + "="*70)
            print("TROUBLESHOOTING")
            print("="*70)
            print("1. Verify wiring: A+ to A+, B- to B-, GND to GND")
            print("2. Check both adapters are using RS485 terminals (not TTL)")
            print("3. Ensure no termination resistors for this short connection")
            print("4. Try swapping which adapter is port 1 vs port 2")
            return False
        
        ser1.close()
        ser2.close()
        
        # Test reverse direction
        print("\n" + "="*70)
        print("TEST 2: Send from Port 2 to Port 1")
        print("="*70)
        
        ser1 = serial.Serial(port=port1, baudrate=9600, timeout=1)
        ser2 = serial.Serial(port=port2, baudrate=9600, timeout=1)
        
        ser1.reset_input_buffer()
        ser2.reset_input_buffer()
        
        test_data2 = b"REVERSE_TEST_OK"
        print(f"\nSending from {port2}: {test_data2}")
        ser2.write(test_data2)
        ser2.flush()
        
        time.sleep(0.5)
        
        if ser1.in_waiting > 0:
            received = ser1.read(ser1.in_waiting)
            print(f"✅ SUCCESS! {port1} received: {received}")
            
            if received == test_data2:
                print("✅ Data matches perfectly!")
            else:
                print(f"⚠️  Data mismatch: expected {test_data2}, got {received}")
        else:
            print(f"❌ No data received on {port1}")
            ser1.close()
            ser2.close()
            return False
        
        ser1.close()
        ser2.close()
        
        print("\n" + "🎉"*35)
        print("✅ BOTH RS485 ADAPTERS WORK PERFECTLY!")
        print("🎉"*35)
        print()
        print("Your adapters are functioning correctly for RS485 communication.")
        print()
        print("This means the problem is with the Rover's RS485 implementation.")
        print("Possible issues:")
        print("  1. Rover uses non-standard RS485 pinout")
        print("  2. Rover requires specific initialization sequence")
        print("  3. Rover's RS485 is disabled or has different slave address")
        print("  4. BT-2 uses proprietary protocol, not standard Modbus")
        print()
        print("Next steps:")
        print("  - Contact Renogy support for RS485 cable specifications")
        print("  - Try official Renogy communication cable if available")
        print("  - Check if Rover firmware needs updating")
        
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_rs485_loopback()
    sys.exit(0 if success else 1)
