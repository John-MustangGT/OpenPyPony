# OpenPonyLogger ESP32-S3

C++ implementation of OpenPonyLogger for ESP32-S3 with native WiFi/BLE support.

## Hardware

- **MCU**: Adafruit ESP32-S3 Feather Reverse TFT
  - 240 MHz dual-core Tensilica processor
  - 512 KB RAM, 8 MB Flash, 2 MB PSRAM
  - Built-in 1.14" 135x240 color TFT (ST7789)
  - Native WiFi and Bluetooth LE
  - STEMMA QT connector for I2C sensors

- **Data Logger**: FeatherWing Adalogger (stacks on Feather)
  - MicroSD card slot on SPI bus
  - High-speed logging capability

- **Sensors** (all on STEMMA QT I2C chain):
  - PA1010D GPS (I2C address 0x10)
  - ICM20948 9-DOF IMU (accelerometer + gyroscope + magnetometer)
  - Future expansion possible

## Architecture

### Multi-Core FreeRTOS Design

**Core 0** (WiFi core):
- WiFi/WebSocket telemetry streaming
- BLE communication (future: OBD2)
- Lower priority, isolated from sensors

**Core 1** (Application core):
- High-priority sensor reading (10-100 Hz)
- Binary data logging to SD card
- Display updates

### Key Features

- **Binary logging**: Same format as CircuitPython version (compatible)
- **WebSocket telemetry**: JSON format compatible with gps-monitor
- **Satellite details**: Periodic transmission for skyplot visualization
- **Dual-core performance**: Sustained 100+ Hz logging with concurrent WiFi
- **Expandable**: Ready for BLE OBD2 integration

## Project Structure

```
esp32-s3/
├── platformio.ini          # PlatformIO configuration
├── include/
│   ├── interfaces/         # Abstract interfaces (GPS, IMU, etc.)
│   ├── sensors/            # Concrete sensor implementations
│   ├── hardware/           # Hardware-specific (display, etc.)
│   ├── config.h            # Configuration management
│   ├── logger.h            # Binary logger
│   └── webserver.h         # WebSocket telemetry server
├── src/
│   ├── main.cpp            # Main application with FreeRTOS tasks
│   ├── sensors/            # Sensor implementations
│   ├── hardware/           # Hardware implementations
│   └── tasks/              # FreeRTOS task implementations
└── lib/                    # Third-party libraries
```

## Development Status

### ✅ Completed
- Project structure
- Abstract interfaces (GPS, IMU, Magnetometer, Display)
- Configuration system design
- Binary logger interface (format compatible)
- WebSocket server interface (JSON compatible)
- FreeRTOS task architecture
- PlatformIO configuration

### 🚧 In Progress
- PA1010D GPS implementation
- ICM20948 IMU implementation
- ST7789 display implementation
- Configuration loader (TOML parser)
- Binary logger implementation
- WebSocket server implementation

### 📋 Planned
- BLE OBD2 integration (vgate icar pro 2)
- Sensor fusion (GPS + IMU + OBD2)
- Advanced features (lap timing, geofencing)

## Building

```bash
# Install PlatformIO
pip install platformio

# Build project
cd esp32-s3
pio run

# Upload to board
pio run --target upload

# Monitor serial output
pio device monitor
```

## Configuration

Settings are stored in `/sd/settings.toml` on the SD card:

```toml
# GPS
gps.enabled = true
gps.type = "PA1010D"
gps.address = 0x10
gps.update_rate = 1000

# IMU
sensors.accelerometer.enabled = true
sensors.accelerometer.type = "ICM20948"
sensors.accelerometer.range = 16
sensors.gyroscope.enabled = true
sensors.gyroscope.range = 2000

# WiFi
radio.mode = "ap"
radio.ssid = "OpenPonyLogger"
radio.password = "mustanggt"

# Telemetry
telemetry.rate = 10
telemetry.satellite_details_interval = 60
```

## Binary Log Format

The ESP32-S3 version uses the **exact same binary format** as the CircuitPython version for full compatibility with existing tools.

Frame size: 64 bytes
- Timestamp: 8 bytes (double)
- GPS lat/lon: 16 bytes (2x double)
- GPS alt/speed: 8 bytes (2x float)
- GPS satellites: 1 byte
- Reserved: 1 byte
- Accelerometer: 12 bytes (3x float)
- Gyroscope: 12 bytes (3x float)
- Reserved: 8 bytes
- CRC32 checksum: 4 bytes

## WebSocket Telemetry

JSON format (10 Hz, compatible with gps-monitor):

```json
{
  "timestamp": 1767203161,
  "lat": 42.333801,
  "lon": -71.436768,
  "alt": 28.7,
  "speed": 1.72,
  "track": 270.0,
  "heading": 270.93,
  "satellites": 5,
  "fix_type": "3D",
  "hdop": 1.4,
  "gx": 0.009,
  "gy": -0.005,
  "gz": 1.012,
  "rx": 0.015,
  "ry": 0.028,
  "rz": -0.005,
  "satellite_details": [
    {"prn": 1, "elevation": 45, "azimuth": 180, "snr": 38},
    {"prn": 3, "elevation": 30, "azimuth": 90, "snr": 42}
  ]
}
```

Satellite details are sent every 60 seconds (configurable).

## Migration from CircuitPython

The abstractions are directly ported from the CircuitPython version:

| CircuitPython | ESP32-S3 C++ |
|--------------|--------------|
| `GPSInterface` | `OpenPony::GPSInterface` |
| `ATGM336H` / `PA1010D` | `OpenPony::PA1010D` |
| `ICM20948` | `OpenPony::ICM20948` |
| `BinaryLogger` | `OpenPony::BinaryLogger` |
| `ESP01` | `OpenPony::WebSocketTelemetryServer` |

## Performance Comparison

| Metric | CircuitPython (RP2040) | ESP32-S3 |
|--------|------------------------|----------|
| CPU Speed | 133 MHz | 240 MHz dual-core |
| RAM | 264 KB | 512 KB + 2 MB PSRAM |
| Log Rate | ~10 Hz | 100+ Hz sustained |
| WiFi | ESP-01 UART bridge | Native, dedicated core |
| BLE | Not practical | Native, excellent support |

## Next Steps

1. **Implement sensor drivers** (PA1010D, ICM20948)
2. **Test basic sensor reading** on STEMMA QT chain
3. **Implement binary logger** with high-speed SD writes
4. **Test WebSocket telemetry** with gps-monitor
5. **Add BLE OBD2** integration (vgate icar pro 2)
6. **Field testing** on track

## License

Same as CircuitPython version - see main README.
