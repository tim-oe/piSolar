# Renogy Serial Connection Guides

This document has been split into protocol-specific guides:

## Available Guides

| Protocol | Controller | Status | Document |
|----------|------------|--------|----------|
| RS232 | Renogy Wanderer | **Verified Working** | [RS232.md](RS232.md) |
| RS485 | Renogy Rover | Work In Progress | [RS485.md](RS485.md) |

## Quick Reference

### RS232 (Wanderer)
- Connector: RJ12 (6-pin)
- Pins: 1=TX, 2=RX, 3=GND
- Voltage: ±10V (requires RS232 adapter, not TTL)
- See [RS232.md](RS232.md) for full details

### RS485 (Rover)
- Connector: RJ45 (8-pin)
- Pins: 3=A+, 6=B-, 4=GND
- Differential signaling
- See [RS485.md](RS485.md) for full details

## Common Parameters (Both)

```
Baud Rate:    9600
Data Bits:    8
Stop Bits:    1
Parity:       None
Protocol:     Modbus RTU
Slave Addr:   1
```
