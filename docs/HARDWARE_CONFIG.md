# Hardware Configuration Guide

OpenPonyLogger uses `hardware.toml` for flexible hardware configuration without modifying code.

## Quick Start

**1. Edit hardware.toml:**
```toml
[sensors.accelerometer]
enabled = true
range = 2        # Change to 4, 8, or 16 for higher G-forces
sample_rate = 100
```

**2. Deploy to Pico:**
```bash
cp hardware.toml /Volumes/CIRCUITPY/
```

**3. Reboot Pico** - changes take effect immediately

## File Structure

```toml
[interfaces]     # Core communication buses (I2C, SPI, UART)
[sensors]        # Accelerometer, gyro, magnetometer
[gps]           # GPS module configuration
[storage]       # SD card settings
[display]       # OLED display
[indicators]    # LEDs and NeoPixels
[radio]         # ESP-01s WiFi module
[rtc]           # Real-time clock
[expansion]     # Future peripherals (CAN, OBD-II, etc.)
```

## Pin Format

**GPIO Pins:**
```toml
pin = "GP25"    # GPIO 25
pin = "GP0"     # GPIO 0
```

**Special Names:**
```toml
sda = "GP4"             # Explicit GPIO
sda = "STEMMA_I2C"      # Use default STEMMA QT pins (GP4/GP5)
```

## Common Configurations

### Change Accelerometer Range

For higher G-forces (track use):
```toml
[sensors.accelerometer]
range = 8        # 2, 4, 8, or 16 (G-forces)
sample_rate = 100
```

### Change GPS Update Rate

Faster updates (uses more power):
```toml
[gps]
update_rate = 500   # 500ms = 2Hz (default: 1000ms = 1Hz)
```

### Disable NeoPixel

Save power by disabling LEDs:
```toml
[indicators.neopixel_jewel]
enabled = false
```

### Change NeoPixel Brightness

```toml
[indicators.neopixel_jewel]
brightness = 0.5    # 0.0 (off) to 1.0 (max)
```

### Different I2C Pins

If using custom wiring:
```toml
[interfaces.i2c]
sda = "GP26"    # Change from default GP4
scl = "GP27"    # Change from default GP5
```

### Change Timezone

```toml
[rtc]
timezone_offset = -8    # PST (default: -5 for EST)
auto_dst = true
```

## Pin Reference

### Default Pin Assignments

| Peripheral | Pin(s) | Notes |
|------------|--------|-------|
| **I2C (STEMMA QT)** | GP4 (SDA), GP5 (SCL) | Accelerometer, OLED |
| **GPS UART** | GP0 (TX), GP1 (RX) | ATGM336H module |
| **ESP UART** | GP8 (TX), GP9 (RX) | ESP-01s WiFi |
| **SPI (SD Card)** | GP16 (MISO), GP17 (CS), GP18 (SCK), GP19 (MOSI) | MicroSD |
| **Heartbeat LED** | GP25 | Onboard LED |
| **NeoPixel Jewel** | GP22 | 7 RGB LEDs |
| **ESP Reset** | GP6 | ESP-01s reset line |
| **GPS PPS** | GP7 | Pulse per second (optional) |

### Available GPIO

Free pins for expansion:
- GP2, GP3, GP10, GP11, GP12, GP13, GP14, GP15
- GP20, GP21, GP26, GP27, GP28

## Peripheral Details

### Accelerometer (LIS3DH)

```toml
[sensors.accelerometer]
enabled = true
type = "LIS3DH"
interface = "i2c"
address = 0x18
range = 2           # G-force range
sample_rate = 100   # Hz
```

**Range Options:**
- `2` - ±2g (daily driving, low noise)
- `4` - ±4g (spirited driving)
- `8` - ±8g (track day, recommended)
- `16` - ±16g (extreme racing)

**Sample Rate Options:**
- `10`, `25`, `50`, `100`, `200`, `400` Hz

### GPS (ATGM336H)

```toml
[gps]
enabled = true
type = "ATGM336H"
interface = "uart_gps"
update_rate = 1000      # milliseconds
pps_pin = "GP7"         # Pulse per second
pps_enabled = false
sentences = "0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0"
```

**Update Rate:**
- `1000` = 1Hz (default, best battery life)
- `500` = 2Hz (more responsive)
- `200` = 5Hz (racing, high precision)
- `100` = 10Hz (maximum, uses most power)

**NMEA Sentences:**
The `sentences` string configures which GPS data to receive:
- Position 1: GGA (position/fix data) - `1` = enabled
- Position 3: RMC (recommended minimum) - `1` = enabled
- Position 5: GSV (satellites in view) - `5` = enabled

### NeoPixel Jewel Layout

```
      [1]          LED 1: OUT (forward accel)
   [6] [0] [2]     LED 0: Center (master status)
      [5] [3]      LED 2-4: Right side (G-forces)
         [4]       LED 5: PWR (braking)
                   LED 6: Left side (G-forces)
```

**Status Colors (LED 0):**
- Green breathing: GPS fix + logging
- Yellow flashing: Degraded (GPS OR logging)
- Red solid: No GPS, no logging

### Display (SSD1306 OLED)

```toml
[display.oled]
enabled = true
type = "SSD1306"
interface = "i2c"
address = 0x3C
width = 128
height = 64
```

Standard 128x64 I2C OLED compatible with:
- Adafruit SSD1306 displays
- Generic 0.96" OLED modules
- STEMMA QT compatible displays

### SD Card

```toml
[storage.sdcard]
enabled = true
interface = "spi"
cs_pin = "GP17"
mount_point = "/sd"
```

Supports:
- MicroSD cards (FAT32)
- Up to 32GB tested
- Adalogger FeatherWing compatible

## Future Expansion

### CAN Bus (Coming Soon)

```toml
[expansion.can_bus]
enabled = true
type = "MCP2515"
interface = "spi"
cs_pin = "GP13"
int_pin = "GP14"
```

### OBD-II (Planned)

```toml
[expansion.obd2]
enabled = true
type = "ELM327"
interface = "uart"
# Separate UART for OBD-II communication
```

## Troubleshooting

### I2C Device Not Found

```
✗ Accelerometer error: [Errno 19] No such device
```

**Check:**
1. Verify wiring (SDA/SCL not swapped)
2. Check I2C address: `0x18` vs `0x19`
3. Test with i2c scan:
```python
import board
import busio
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
print([hex(x) for x in i2c.scan()])
i2c.unlock()
```

### GPS Not Getting Fix

```
✗ GPS error: timeout
```

**Check:**
1. Antenna has clear view of sky
2. Wait 30-60 seconds for cold start
3. Verify UART pins not swapped (TX↔RX)
4. Check baudrate: `9600` for ATGM336H

### SD Card Mount Failed

```
✗ SD card error: [Errno 19] Unsupported operation
```

**Check:**
1. Card formatted as FAT32
2. Card capacity ≤32GB
3. Card fully inserted
4. SPI wiring correct

### NeoPixel Not Working

```
✗ NeoPixel error: [Errno 22] Invalid argument
```

**Check:**
1. Correct pin (GP22 for default)
2. Power supply adequate (7 LEDs = ~420mA max)
3. Data line not damaged

## Hardware Variants

### Minimal Setup

Disable optional peripherals:
```toml
[indicators.neopixel_jewel]
enabled = false

[display.oled]
enabled = false

[radio.esp01s]
enabled = false
```

Result: Just accelerometer + GPS + SD card

### Developer Edition

All STEMMA QT connections:
```toml
# All peripherals on I2C/STEMMA
# Zero soldering required
```

### Showcase Edition

Full-featured with all extras:
```toml
# All peripherals enabled
# NeoPixel animations
# WiFi web interface
# Real-time display
```

## Best Practices

1. **Test one change at a time** - Easier to debug
2. **Comment out sections** - Use `#` to disable temporarily
3. **Backup working config** - Copy before major changes
4. **Check pin conflicts** - Don't assign same pin to multiple peripherals
5. **Verify after changes** - Watch serial output for errors

## Example Configurations

### Track Day Setup

High sample rates, maximum range:
```toml
[sensors.accelerometer]
range = 8
sample_rate = 200

[gps]
update_rate = 200  # 5Hz

[indicators.neopixel_jewel]
brightness = 1.0   # Max visibility
```

### Battery Saver

Minimum power consumption:
```toml
[sensors.accelerometer]
sample_rate = 50

[gps]
update_rate = 2000  # 0.5Hz

[indicators.neopixel_jewel]
enabled = false

[display.oled]
enabled = false
```

### Development/Debug

Maximum verbosity:
```toml
# Enable all peripherals for testing
# Keep sample rates moderate
[sensors.accelerometer]
sample_rate = 100

[gps]
update_rate = 1000
```

---

**Questions?** Check the [main README](README.md) or open an issue on GitHub.
