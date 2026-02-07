# RS485 Test Scripts

This folder contains test utilities for RS485 communication with Renogy Rover Elite 40A.

## Available Tests

### 1. test_rs485.py - Main Diagnostic Test

Tests Modbus communication with the Rover Elite using the verified pinout.

**Usage:**
```bash
poetry run python tests/rs485/test_rs485.py
poetry run python tests/rs485/test_rs485.py --port /dev/ttyUSB0 -v
```

**Verified Pinout (Rover Elite 40A):**
- Pin 7 → RS485 A+
- Pin 6 → RS485 B-
- Pin 5 → GND

### 2. test_rs485_adapter_loopback.py - Adapter Verification Test

Tests two RS485 adapters connected back-to-back (null modem style).
Useful for verifying your RS485 adapters work before connecting to Rover.

**Setup:**
```
Adapter 1          Adapter 2
A+ ←───────────→ A+
B- ←───────────→ B-
GND ←──────────→ GND
```

**Usage:**
```bash
# Connect two RS485 adapters together
# Both must be plugged into Pi via USB
poetry run python tests/rs485/test_rs485_adapter_loopback.py
```

**What this proves:**
- ✅ Your RS485 adapters work correctly
- ✅ Your USB connection is good
- ✅ Serial communication is functioning

If this test passes but Rover connection fails, the issue is with pinout/wiring, not adapters.

## Quick Start

1. **First verify your adapters work:**
   ```bash
   # Wire two adapters together and run
   poetry run python tests/rs485/test_rs485_adapter_loopback.py
   ```

2. **Then test Rover connection:**
   ```bash
   # Wire adapter to Rover (pins 7, 6, 5) and run
   poetry run python tests/rs485/test_rs485.py
   ```

## Troubleshooting

If tests fail:

1. **Check permissions:**
   ```bash
   ls -la /dev/ttyUSB*
   sudo usermod -a -G dialout $USER
   # Log out and back in
   ```

2. **Verify USB adapter:**
   ```bash
   lsusb | grep -i ftdi
   ```

3. **Check Waveshare adapter settings:**
   - Mode switch: RS485 (not RS232)
   - Termination: OFF (for cables < 10m)

4. **Verify pinout:**
   - Rover Elite 40A uses pins 7, 6, 5
   - Other Rover models may use different pins!
   - See docs/RS485.md for details

## References

- Full documentation: `docs/RS485.md`
- Hardware diagnostics: `docs/RS485_HARDWARE_DIAGNOSTICS.md`
- Wiring diagrams: `docs/RS485_WIRING_DIAGRAM.md`
