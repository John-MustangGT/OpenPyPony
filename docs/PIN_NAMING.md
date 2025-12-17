# Pin Naming Reference for hardware.toml

## Standard GPIO Pins
Use the standard CircuitPython pin names:
```toml
pin = "GP0"   # GPIO 0
pin = "GP1"   # GPIO 1
...
pin = "GP28"  # GPIO 28
```

## Special Pins (Pico W)

### Onboard LED
The Pico W's onboard LED is **NOT** on GP25 like the regular Pico.
It's accessed via a special name:

```toml
# ✓ CORRECT
pin = "LED"

# ✗ WRONG (will fail on Pico W)
pin = "GP25"
```

**Note**: The code automatically handles `GP25` → `LED` conversion for compatibility.

### Other Board Pins

```toml
pin = "VBUS_SENSE"   # USB power detection
pin = "NEOPIXEL"     # If board has onboard NeoPixel
```

## I2C/SPI/UART Buses

### STEMMA QT (I2C)
```toml
[interfaces.i2c]
sda = "GP4"   # STEMMA QT SDA (default)
scl = "GP5"   # STEMMA QT SCL (default)
```

Or use the convenience function:
```toml
# This creates I2C on the STEMMA QT connector
i2c = "STEMMA_I2C"
```

### SPI
```toml
[interfaces.spi]
sck = "GP18"   # Clock
mosi = "GP19"  # Data out
miso = "GP16"  # Data in
```

### UART
```toml
[interfaces.uart_gps]
tx = "GP0"
rx = "GP1"
```

## Pin Lookup Order

When resolving a pin string, the code checks in this order:

1. **Special names**: `STEMMA_I2C`
2. **Board aliases**: `LED`, `NEOPIXEL`, `VBUS_SENSE`
3. **GP25 special case**: Converts to `LED` on Pico W
4. **GP## format**: `GP0` through `GP28`
5. **Direct board attribute**: Any other `board.XXX` name

## Examples

```toml
# Heartbeat LED
[indicators.heartbeat_led]
pin = "LED"  # ✓ Works on Pico W

# External LED on breadboard
[indicators.status_led]
pin = "GP15"  # ✓ Standard GPIO

# NeoPixel on data pin
[indicators.neopixel_jewel]
pin = "GP16"  # ✓ Any GPIO with PWM

# I2C accelerometer
[sensors.accelerometer]
# Uses interfaces.i2c pins automatically
```

## Troubleshooting

**Error: `'module' object has no attribute 'GP25'`**
- On Pico W, use `pin = "LED"` instead of `pin = "GP25"`
- The code auto-converts but may show a warning

**Error: `Pin 'GPX' not found on board`**
- Check pin number is valid (GP0-GP28)
- Some pins may not be exposed on your board
- Verify pin isn't reserved (GP23-GP25 used by wireless on Pico W)
