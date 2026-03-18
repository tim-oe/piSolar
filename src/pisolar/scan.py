import minimalmodbus, serial

for addr in range(1, 248):
    try:
        inst = minimalmodbus.Instrument('/dev/ttyUSB0', addr)
        inst.serial.baudrate = 9600
        inst.serial.bytesize = 8
        inst.serial.parity = serial.PARITY_NONE
        inst.serial.stopbits = 1
        inst.serial.timeout = 0.5
        inst.mode = minimalmodbus.MODE_RTU
        val = inst.read_register(0x0100, 0)
        print(f"✓ Found at address {addr}, SOC: {val}%")
        break
    except Exception as e:
        print(f"  {addr}: {e}")