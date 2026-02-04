# Renogy Charge Controller Wiring Guide

## Overview

This guide covers wiring Waveshare USB to RS232/485/TTL converter to Renogy charge controllers using both RS232 and RS485 protocols.

---

## Equipment Needed

- Waveshare USB to RS232/485/TTL converter
- Raspberry Pi (or any computer with USB)
- RJ12 to screw terminal adapter (for RS232 - Wanderer)
- RJ45 to screw terminal adapter (for RS485 - Rover)
- Multimeter (for verification)
- Jumper wires or appropriate cables

---

## RS232 Connection (Renogy Wanderer 10A)

### Hardware Configuration

**Waveshare Converter Settings:**
- Set jumpers/switch to **RS232 mode**
- Use DB9 connector or RS232 screw terminals

### RJ12 Connector Pinout

The Renogy Wanderer uses an **RJ12 (6P6C)** connector for communication.

**Pin Identification:**
- Hold RJ12 plug with tab/clip facing DOWN
- Cable entry facing AWAY from you
- Pins numbered LEFT to RIGHT: 1, 2, 3, 4, 5, 6

**RJ12 Pinout:**
```
Pin 1: VCC (not used)
Pin 2: RXD (Receive Data)
Pin 3: TXD (Transmit Data)
Pin 4: GND (Ground)
Pin 5: GND (Ground)
Pin 6: VCC (not used)
```

### Wiring Diagram

**RJ12 Screw Terminals → Waveshare DB9 (RS232):**
```
RJ12 Pin 2 (RXD) ──→ DB9 Pin 2 (RXD)
RJ12 Pin 3 (TXD) ──→ DB9 Pin 3 (TXD)
RJ12 Pin 4 (GND) ──→ DB9 Pin 5 (GND)
```

**If using Waveshare RS232 screw terminals:**
```
RJ12 Pin 2 (RXD) ──→ Waveshare RXD
RJ12 Pin 3 (TXD) ──→ Waveshare TXD
RJ12 Pin 4 (GND) ──→ Waveshare GND
```

### Connection Notes

- ⚠️ **Use straight-through connections** (TXD to TXD, RXD to RXD)
- Do NOT use null modem configuration
- Do NOT connect VCC pins (controller is separately powered)
- Either Pin 4 or Pin 5 can be used for ground (they're tied together)

### Communication Parameters

```
Baud Rate:    9600
Data Bits:    8
Stop Bits:    1
Parity:       None
Protocol:     Modbus RTU
Slave Addr:   1
```

---

## RS485 Connection (Renogy Rover)

### Hardware Configuration

**Waveshare Converter Settings:**
- Set jumpers/switch to **RS485 mode**
- Use RS485 screw terminals (3-wire connection)

### RJ45 Connector Pinout

The Renogy Rover uses an **RJ45 (8P8C)** connector (looks like Ethernet).

**Pin Identification:**
- Hold RJ45 plug with tab/clip facing DOWN
- Cable entry facing AWAY from you
- Pins numbered LEFT to RIGHT: 1, 2, 3, 4, 5, 6, 7, 8

**RJ45 Pinout:**
```
Pin 1: Not used
Pin 2: Not used
Pin 3: A / Data+ (Yellow/White-Orange in T568B)
Pin 4: GND (Blue in T568B)
Pin 5: GND (White-Blue in T568B)
Pin 6: B / Data- (Green/Orange in T568B)
Pin 7: Not used
Pin 8: Not used
```

### Wiring Diagram

**RJ45 Screw Terminals → Waveshare RS485:**
```
RJ45 Pin 3 (A / Data+) ──→ Waveshare A+ / D+
RJ45 Pin 6 (B / Data-) ──→ Waveshare B- / D-
RJ45 Pin 4 (GND)       ──→ Waveshare GND
```

### T568B Ethernet Cable Color Reference

If using a standard Ethernet cable:
```
Pin 3 (A+):  White/Orange stripe
Pin 4 (GND): Blue solid
Pin 5 (GND): White/Blue stripe
Pin 6 (B-):  Orange solid
```

### Connection Notes

- RS485 uses differential signaling (A+ and B-)
- Ground connection is required for proper operation
- Either Pin 4 or Pin 5 can be used for ground
- ⚠️ **Polarity matters**: A must go to A+, B must go to B-
- If communication fails, try swapping A and B

### Communication Parameters

```
Baud Rate:    9600
Data Bits:    8
Stop Bits:    1
Parity:       None
Protocol:     Modbus RTU
Slave Addr:   1
```

---

## Raspberry Pi USB Connection

### Both Protocols

1. **Connect Waveshare to Raspberry Pi:**
   - Plug Waveshare USB converter into any USB port
   - No drivers needed (automatic recognition)

2. **Verify connection:**
```bash
# List USB devices
lsusb

# Check for serial device
ls /dev/ttyUSB*

# Should show: /dev/ttyUSB0 (or ttyUSB1, ttyUSB2, etc.)
```

3. **Set permissions:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

---

## Testing Connection

### Using Minicom (Both Protocols)

```bash
# Install minicom
sudo apt-get install minicom

# Connect to device
minicom -D /dev/ttyUSB0 -b 9600
```

### Using Python with PyModbus

```bash
# Install dependencies
pip3 install pymodbus pyserial
```

**Test Script:**
```python
#!/usr/bin/env python3
from pymodbus.client import ModbusSerialClient

# Create connection
client = ModbusSerialClient(
    port='/dev/ttyUSB0',
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=3
)

# Connect and read data
if client.connect():
    print("Connected!")
    
    # Read battery voltage (register 0x0101)
    result = client.read_holding_registers(0x0101, 1, slave=1)
    if not result.isError():
        voltage = result.registers[0] * 0.1
        print(f"Battery Voltage: {voltage}V")
    
    # Read battery SOC (register 0x0100)
    result = client.read_holding_registers(0x0100, 1, slave=1)
    if not result.isError():
        soc = result.registers[0]
        print(f"Battery SOC: {soc}%")
    
    client.close()
else:
    print("Connection failed")
```

---

## Common Modbus Registers

### Renogy Wanderer & Rover (Both)

| Register | Description | Unit | Scale Factor |
|----------|-------------|------|--------------|
| 0x0100 | Battery SOC | % | 1 |
| 0x0101 | Battery Voltage | V | 0.1 |
| 0x0102 | Charging Current | A | 0.01 |
| 0x0103 | Controller Temperature | °C | 1 (signed) |
| 0x0107 | Solar Panel Voltage | V | 0.1 |
| 0x0108 | Solar Panel Current | A | 0.01 |
| 0x0109 | Solar Panel Power | W | 1 |
| 0x010B | Load Voltage | V | 0.1 |
| 0x010C | Load Current | A | 0.01 |
| 0x010D | Load Power | W | 1 |

---

## Troubleshooting

### No Communication

**Check the following:**
1. Verify correct protocol mode is set on Waveshare (RS232 vs RS485)
2. Confirm wiring connections are correct
3. Ensure baud rate is 9600 on both sides
4. Verify controller is powered on
5. Check `/dev/ttyUSB*` device exists
6. Confirm user is in `dialout` group

### RS232 Specific Issues

- Verify straight-through wiring (not null modem)
- Check TXD and RXD are not swapped
- Confirm ground connection is secure

### RS485 Specific Issues

- Verify A+ to A+ and B- to B- connections
- If no response, try swapping A and B wires
- Ensure ground is connected
- Check termination resistors if using long cables

### Still Not Working?

```bash
# Enable detailed Modbus debugging
import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
```

---

## Safety Notes

- ⚠️ Always power off controllers before connecting/disconnecting
- ⚠️ Do not short VCC to GND
- ⚠️ Use proper wire gauge for current-carrying connections
- ⚠️ Ensure all connections are secure before powering on
- ⚠️ Double-check polarity on RS485 connections

---

## Protocol Comparison

| Feature | RS232 (Wanderer) | RS485 (Rover) |
|---------|------------------|---------------|
| Connector | RJ12 (6-pin) | RJ45 (8-pin) |
| Max Distance | ~15 meters | ~1200 meters |
| Wiring | 3-wire (TX, RX, GND) | 3-wire (A+, B-, GND) |
| Multi-drop | No | Yes (up to 32 devices) |
| Noise Immunity | Low | High |
| Signal Type | Single-ended | Differential |
| Best Use | Short distances | Long distances, industrial |

---

## Additional Resources

- **Renogy Modbus Protocol:** Check Renogy's official documentation
- **PyModbus Documentation:** https://pymodbus.readthedocs.io/
- **Raspberry Pi Serial:** https://www.raspberrypi.com/documentation/

---

## Revision History

- **v1.0** - Initial wiring guide for RS232 and RS485 connections