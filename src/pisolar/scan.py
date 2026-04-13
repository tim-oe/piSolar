import glob
import sys

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

# Auto-detect all available USB serial ports
available_ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
if not available_ports:
    print("ERROR: No USB serial ports found in /dev/ttyUSB* or /dev/ttyACM*")
    print("Is the adapter plugged in and recognized by the kernel?")
    sys.exit(1)

print(f"Found serial ports: {available_ports}")
PORT = available_ports[0]
print(f"Using: {PORT}")

client = ModbusSerialClient(
    port=PORT,
    framer="rtu",
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1.0,
)

connected = client.connect()
print(f"Connected: {connected}")

try:
    for addr in range(1, 248):
        try:
            result = client.read_holding_registers(0x0100, count=1, device_id=addr)
            if result.isError():
                print(f"  {addr}: modbus error response: {result}")
            else:
                val = result.registers[0]
                print(f"✓ Found at address {addr}, SOC: {val}%")
                break
        except ModbusException as e:
            print(f"  {addr}: {e}")
finally:
    client.close()
