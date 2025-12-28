# OpenPonyLogger - Refactored Core Architecture

**Version:** 2.0.0-alpha  
**Date:** 2024-12-27

## Overview

Complete refactor of OpenPonyLogger with clean object-oriented design, proper hardware abstraction, and minimal dependencies on external code.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      code.py                            │
│                   (Main Entry)                          │
└────────────┬───────────────────────────┬────────────────┘
             │                           │
             ▼                           ▼
      ┌────────────┐            ┌──────────────┐
      │  Config    │            │  Hardware    │
      │  Manager   │            │  Abstraction │
      │            │            │    Layer     │
      └────────────┘            └──────┬───────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │ Sensors  │      │ Storage  │      │ Display  │
              │Interface │      │Interface │      │Interface │
              └──────────┘      └──────────┘      └──────────┘
                    │
         ┌──────────┼──────────┐
         ▼          ▼          ▼
    ┌────────┐ ┌───────┐ ┌───────┐
    │LIS3DH  │ │ATGM336│ │PCF8523│
    │ Accel  │ │  GPS  │ │  RTC  │
    └────────┘ └───────┘ └───────┘
```

## Key Components

### 1. Configuration System (`config.py`)
- **Single TOML file** with sections
- **Profile support** (daily/track modes)
- **Type-safe access** with defaults
- **Dot notation** for nested values

```python
config = Config('settings.toml')
update_rate = config.get('gps.update_rate', 1000)
config.switch_profile('track')
```

### 2. Hardware Abstraction Layer (`hardware.py`)
- **Auto-detection** of connected devices
- **Graceful fallback** with Null implementations
- **Unified interface** - swap hardware without code changes
- **Hardware manifest** - know what's connected

```python
hal = HardwareAbstractionLayer(config)
accel = hal.get_accelerometer()  # Returns interface, not concrete class
gx, gy, gz = accel.get_gforce()  # Works even if accel disabled
```

### 3. Sensor Interfaces (`sensors.py`)
- **Abstract base classes** define contracts
- **Multiple implementations** per sensor type
- **Null implementations** for disabled hardware
- **No coupling** to specific hardware

Interfaces:
- `AccelerometerInterface` - 3-axis acceleration
- `GPSInterface` - Position, time, speed
- `RTCInterface` - Real-time clock
- `DisplayInterface` - Screen output
- `StorageInterface` - SD card access

### 4. Session Management (`session.py`)
- **Sequential numbering** via `session_last.txt`
- **File naming** - `session_XXXXX.opl`
- **Persistent state** across reboots
- **Session listing** and management

```python
session_mgr = SessionManager(storage)
filename = session_mgr.start_new_session()
# Creates: /sd/session_00042.opl
```

## Supported Hardware

### Required (Base Build)
- **Raspberry Pi Pico 2W** - Main MCU
- **PiCowbell Adalogger**
  - SD card slot (SPI)
  - PCF8523 RTC (I2C)
  - STEMMA QT connector
- **LIS3DH Accelerometer** (I2C @0x18)
- **ATGM336H GPS** (UART)

### Optional
- **SSD1306 OLED** (128x64, I2C @0x3C)
- **NeoPixel Jewel** (future)
- **ESP-01 WiFi** (future)

## Pin Assignments

| Function      | Pins          | Bus  |
|---------------|---------------|------|
| I2C (Sensors) | GP8/GP9       | I2C  |
| GPS           | GP0/GP1       | UART |
| SD Card       | GP16/17/18/19 | SPI  |

## Configuration File Structure

```toml
[general]
StartUp_Config = "daily"
Driver_name = "John"
Vehicle_id = "Ciara"

[general.daily]
GPS_Update_rate = 1000
Accel_sample_rate = 100

[general.track]
GPS_Update_rate = 200
Accel_sample_rate = 200

[sensors.accelerometer]
enabled = true
type = "LIS3DH"
address = 0x18
range = 2

[gps]
enabled = true
type = "ATGM336H"
update_rate = 1000
```

## Boot Sequence

1. **Load Configuration** - Parse settings.toml
2. **Initialize Hardware** - Auto-detect via HAL
3. **Sync Time** - RTC → GPS sync
4. **Start Session** - Increment session number
5. **Main Loop** - GPS-gated logging

## Logging Strategy

- **Only log when GPS.update() returns True**
- **Binary .opl format** (default)
  - Session header
  - Hardware/config metadata
  - Checksummed data blocks
- **CSV fallback** (basic data only)
- **Buffered writes** (50 samples default)
- **Event-triggered flush** (high G-force)

## Migration from v1.x

The refactored code is a **clean slate** - no backward compatibility with the messy v1.x codebase.

**Key differences:**
- Single `settings.toml` vs separate hardware.toml
- HAL abstracts all hardware
- No scattered initialization code
- Proper OOP throughout
- Session-based instead of timestamp-based files

## Next Steps

### Phase 1: Core Foundation ✅
- [x] Config system
- [x] HAL with device detection
- [x] Sensor interfaces
- [x] Session management
- [x] Example code.py

### Phase 2: Logger Implementation
- [ ] Binary logger class (reuse v2 format)
- [ ] CSV logger class
- [ ] GPS-gated data capture
- [ ] Buffered writes with flush triggers

### Phase 3: Display & Feedback
- [ ] OLED status display
- [ ] NeoPixel support
- [ ] Boot animations
- [ ] G-force visualization

### Phase 4: ESP-01 Integration
- [ ] UART protocol handler
- [ ] Config push on boot
- [ ] File proxy (GET/POST)
- [ ] WebSocket forwarding @5Hz

## Development Notes

### Design Principles
1. **Separation of Concerns** - Each module has one job
2. **Dependency Injection** - Pass interfaces, not implementations
3. **Graceful Degradation** - Work with missing hardware
4. **Configuration-Driven** - Behavior via settings.toml
5. **Fail-Fast** - Errors are obvious, not hidden

### Why This Refactor?
- Old code had accumulated cruft
- Mixed concerns (WiFi + logging + display)
- Hard-coded hardware assumptions
- Difficult to test or modify
- "Dead" code from abandoned features

### What's Better?
- **Clean slate** - no legacy baggage
- **Proper abstractions** - swap hardware easily
- **Testable** - interfaces make mocking trivial
- **Maintainable** - clear structure
- **Extensible** - add features without breaking existing code

## File Structure

```
refactored_core/
├── code.py              # Main entry point
├── config.py            # Configuration manager
├── hardware.py          # Hardware abstraction layer
├── sensors.py           # Sensor interfaces + implementations
├── session.py           # Session management
└── logger.py            # Binary/CSV loggers (TODO)
```

## Usage

1. Copy `settings.toml.example` to `settings.toml`
2. Customize configuration
3. Deploy to Pico:
   ```bash
   cp refactored_core/* /Volumes/CIRCUITPY/
   cp settings.toml /Volumes/CIRCUITPY/
   ```
4. Reboot Pico - logs to `/sd/session_XXXXX.opl`

## License

MIT License - Same as original OpenPonyLogger

---

**Status:** Alpha - Core architecture complete, logger implementation in progress
