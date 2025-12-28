# OpenPonyLogger - Architecture Overview

## System Architecture

OpenPonyLogger uses a modern OOP architecture with Hardware Abstraction Layer (HAL) for the CircuitPython codebase.

### Design Principles

1. **Separation of Concerns** - Hardware setup, sensor management, and logging are separate modules
2. **Hardware Abstraction** - Pin assignments and hardware config in TOML files, not hardcoded
3. **Unified Interfaces** - Common interfaces for sensors and logging regardless of underlying hardware
4. **Configuration-Driven** - Runtime behavior controlled by config files (hardware.toml, settings.toml)

## Module Structure

### Core Modules

```
circuitpython/
├── code.py                 # Main entry point
├── config.py               # Environment-based configuration
├── hardware_config.py      # TOML-based hardware configuration
├── hardware_setup.py       # System peripheral initialization (HAL)
├── sensors.py              # Sensor initialization and management
├── session_logger.py       # Unified logging interface
├── binary_logger.py        # Binary format implementation
├── gps.py                  # GPS wrapper class
├── oled.py                 # OLED display manager
├── neopixel_handler.py     # NeoPixel indicator handler
├── rtc_handler.py          # RTC wrapper
├── pcf8523_rtc.py          # PCF8523 RTC driver
└── unified_accelerometer.py # Accelerometer wrapper
```

### Hardware Abstraction Layer (HAL)

**hardware_setup.py** provides initialization for:
- I2C bus (STEMMA QT compatible)
- SPI bus (for SD card)
- UART interfaces (GPS, ESP-01S radio)
- OLED display (SSD1306)
- SD card storage
- RTC (PCF8523 or built-in)
- Status indicators (heartbeat LED, NeoPixels)
- Watchdog timer

**hardware_config.py** provides:
- TOML configuration loader
- Type-safe config access (get_int, get_float, get_bool, get_pin)
- Pin string to Pin object conversion ("GP4" → board.GP4)
- Interface pin mapping (I2C, SPI, UART)
- Peripheral enable/disable flags

### Sensor Management

**sensors.py** supports:
- **Accelerometers**: LIS3DH, LSM6DSOX, ICM-20948, MPU-6050
- **Gyroscopes**: LSM6DSOX, ICM-20948, MPU-6050 (via IMU)
- **Magnetometers**: ICM-20948, LIS3MDL
- **GPS**: ATGM336H (UART), PA1010D (I2C/UART)

Features:
- Auto-detection of IMU sensors (6DOF/9DOF)
- Configurable sample rates and ranges
- Sensor registry for easy access
- Graceful fallback when sensors unavailable

### Logging System

**session_logger.py** provides unified interface for:
- **Binary format (.opl)**: Structured binary with CRC32 checksums
- **CSV format (.csv)**: Human-readable text logs

Features:
- Sequential session numbering (session_00001.opl, session_00002.opl, ...)
- Session metadata (driver, vehicle, weather, temperature)
- Hardware configuration block (documents exact setup)
- Event-based flushing (time, size, high-G events)
- GPS-gated logging (only log when GPS has fix)

Binary format structure:
```
Session Header Block:
- Magic bytes "OPNY"
- Format version
- Session ID (UUID)
- Metadata (session name, driver, vehicle, weather, temp)
- CRC32 checksum

Hardware Config Block (optional):
- List of connected hardware
- Connection types and addresses
- CRC32 checksum

Data Blocks:
- Session ID + sequence number
- Timestamp range
- Samples (accelerometer, GPS, gyro, mag)
- Flush flags
- CRC32 checksum

Session End Block:
- Magic bytes + session ID
```

### Configuration System

**config.py** - Environment variables (settings.toml):
```python
LOG_FORMAT = "binary"          # or "csv"
SESSION_NAME = "Track Day"
DRIVER_NAME = "John"
VEHICLE_ID = "Ciara"
ACCEL_SAMPLE_RATE = 100       # Hz
GPS_UPDATE_RATE = 1000        # ms
GFORCE_EVENT_THRESHOLD = 3.0  # g
NEOPIXEL_ENABLED = True
WIFI_ENABLED = True
```

**hardware.toml** - Hardware configuration:
```toml
[interfaces.i2c]
enabled = true
sda = "GP4"
scl = "GP5"

[interfaces.spi]
enabled = true
sck = "GP18"
mosi = "GP19"
miso = "GP16"

[sensors.accelerometer]
enabled = true
type = "LIS3DH"
address = 0x18
range = 16          # ±16g
sample_rate = 100   # Hz

[gps]
enabled = true
type = "ATGM336H"
interface = "uart_gps"
update_rate = 1000  # ms
```

## Data Flow

### Initialization Sequence

1. **hardware_setup.py** - Initialize system peripherals
   - Release displays (for I2C init)
   - Initialize I2C, SPI, UART buses
   - Mount SD card
   - Initialize OLED, RTC, indicators

2. **sensors.py** - Initialize data acquisition sensors
   - Initialize accelerometer (may also init gyro/mag if IMU)
   - Initialize standalone gyro/mag (if not part of IMU)
   - Initialize GPS (UART or I2C)

3. **code.py** - Initialize handlers and logger
   - Create sensor wrapper objects (GPS, UnifiedAccelerometer, etc.)
   - Initialize OLED display manager
   - Initialize NeoPixel handler
   - Start logging session

### Main Loop Flow (100Hz target)

```
┌─────────────────────────────────────┐
│          Main Loop (100Hz)          │
└─────────────────────────────────────┘
           │
           ├─→ Read Accelerometer (100Hz)
           │   └─→ Log to session file
           │
           ├─→ Read Gyroscope (if available)
           │   └─→ Log to session file
           │
           ├─→ Read Magnetometer (if available)
           │   └─→ Log to session file
           │
           ├─→ Update GPS
           │   ├─→ Has fix? Log position, speed, heading
           │   └─→ No fix? Store zero values
           │
           ├─→ Update Display (5Hz)
           │   └─→ Show time, GPS, accel, session info
           │
           ├─→ Update NeoPixels (10Hz)
           │   └─→ Show status indicators
           │
           ├─→ Heartbeat LED (1Hz)
           │   └─→ Long blink = GPS fix, short = no fix
           │
           ├─→ Print Telemetry (1Hz)
           │   └─→ Console output for debugging
           │
           ├─→ Sync RTC from GPS (60s)
           │   └─→ Set system time when GPS has fix
           │
           └─→ Log GPS satellites (5min)
               └─→ Record satellite data for debugging
```

## Hardware Configuration

### Raspberry Pi Pico 2W Pin Assignments

**I2C (STEMMA QT)**
- GP4: SDA (LIS3DH accelerometer @ 0x18)
- GP5: SCL
- GP4/GP5: Also OLED display @ 0x3C
- GP4/GP5: Also PCF8523 RTC @ 0x68

**UART GPS (ATGM336H)**
- GP8: TX (to GPS RX)
- GP9: RX (from GPS TX)
- Baudrate: 9600

**SPI (SD Card)**
- GP16: MISO
- GP18: SCK
- GP19: MOSI
- GP17: CS

**Indicators**
- GP25: Heartbeat LED (onboard LED)
- GP10: NeoPixel Jewel (7 LEDs)

**Radio (ESP-01S) - Optional**
- GP0: TX
- GP1: RX
- GP2: Reset

## Key Features

### GPS-Gated Logging

The logger only writes GPS data when a valid fix is available. This prevents logging of invalid position data while still recording accelerometer data.

```python
if gps_handler.has_fix():
    gps_has_fix = True
    data['gps']['lat'], data['gps']['lon'], data['gps']['alt'] = gps_handler.get_position()
    logger.write_gps(...)
else:
    gps_has_fix = False
    # Store zero/default values but still log accelerometer
```

### Session Management

Sessions are automatically numbered sequentially using `session_last.txt`:
- session_00001.opl
- session_00002.opl
- ...
- session_99999.opl (then wraps to 1)

Each session includes:
- Unique session ID (UUID)
- Metadata (driver, vehicle, session name)
- Hardware configuration snapshot
- All sensor data with microsecond timestamps

### Display Updates

OLED shows real-time data:
```
14:32:45☼ 3D    2.1
38°12'45N 122°27'18W
45MPH  +1.23g
Run:00012 00:05:23
SD: 2h 15m remain
```

Line breakdown:
1. Time (☼=synced, •=not synced), GPS fix type, HDOP
2. Latitude/Longitude
3. Speed, lateral G-force
4. Session number, duration
5. Estimated recording time remaining

### Event-Based Flushing

Binary logger flushes data to SD card when:
- **Time**: Every 5 minutes
- **Size**: Data block 90% full (prevents overflow)
- **Event**: High G-force detected (>3g)
- **Manual**: Explicit flush requested
- **Shutdown**: Session stopped

This balances write performance with data safety.

## Testing Checklist

- [ ] I2C bus initialization (displayio.release_displays() called first)
- [ ] LIS3DH accelerometer detection and configuration
- [ ] ATGM336H GPS UART communication
- [ ] PCF8523 RTC time sync
- [ ] SD card mount and write
- [ ] OLED display updates
- [ ] NeoPixel indicators
- [ ] Session logger file creation
- [ ] Accelerometer data logging (100Hz)
- [ ] GPS data logging (when fix available)
- [ ] Session numbering (incremental)
- [ ] Data integrity (CRC32 checksums)

## Known Issues

1. **GPS fix acquisition**: Can take 30-60 seconds outdoors for cold start
2. **PCF8523 import path**: Must use `from adafruit_pcf8523.pcf8523 import PCF8523`
3. **I2C init order**: Must call `displayio.release_displays()` before I2C init

## Future Enhancements

- [ ] OBD-II integration (CAN bus)
- [ ] WiFi telemetry streaming
- [ ] Real-time track overlay
- [ ] Lap timing with geo-fencing
- [ ] Temperature sensors
- [ ] Tire pressure monitoring
- [ ] Video timestamp synchronization
