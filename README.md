# OpenPyPony 🐎

**Open-source automotive telemetry system for track day data logging**

OpenPyPony is a low-cost, professional-grade data acquisition system built for the 2014 Ford Mustang GT "Ciara". This CircuitPython prototype validates hardware and software architecture before porting to C/C++ for production use.

### Goals
- OpenSource, MIT Licsense
- Commodity hardware
- Competitive with Commercial Solutions

---

## Project Status: Alpha v0.1

**Current Features:**
- ✅ 3-axis accelerometer (LIS3DH) @ ~10Hz
- ✅ Live OLED display (128x64 SSD1306)
- ✅ SD card data logging (CSV format)
- ✅ WiFi Access Point (192.168.4.1)
- ✅ Web-based telemetry interface
- ✅ State machine task scheduler
- ✅ Buffered SD writes for performance

**Planned:**
- ⏳ Bluetooth OBD-II integration
- ⏳ Advanced web UI with gauges

---

## Hardware

### Bill of Materials
- [BOM File](docs/BOM.md)

### Pinout
- [Wiring table](docs/WIRING.md)
- [PICO_GPIO_TABLE File](docs/PICO_GPIO_TABLE.md)

### Power Consumption

- **Baseline (Accel + OLED):** 20mA @ 5V
- **+ GPS (ATGM336H):** ~140mA @ 5V (0.7W)
- **+ ESP-01:** ~170mA @ 5V (0.8W)
- **+ GPS (ATGM336H)  + ESP-01:** ~210mA @ 5V (1.0W)

**Battery Life:** 8+ hours on 2000mAh USB battery pack

---

## Software Architecture

### State Machine Scheduler

Cooperative multitasking system with independent task scheduling:
```python
Task                 Interval    Purpose
────────────────────────────────────────────────────
Accelerometer        100ms       Read LIS3DH sensor
Display              200ms       Update OLED
SD Logger            100ms       Buffer & flush data
Status               1000ms      Console updates
```

### Data Flow
```
┌─────────────┐
│   Sensors   │  (Accel, GPS, OBD-II)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ data_buffer │  (Shared dictionary)
└──────┬──────┘
       │
       ├─────────────► OLED Display (5Hz)
       ├─────────────► Web Interface (JSON API)
       └─────────────► SD Card Logger (buffered)
```

### File Structure
```
OpenPyPony/
├── circuitpython            # Main Logger
│   ├── code.py		     # Main for startup
│   ├── accelerometer.py     # Accelerometer Class
│   ├── config.py            # Configurtion Class
│   ├── gps.py               # GPS Class
│   ├── hardware_setup.py    # Base hardware Configuration Class
│   ├── neopixel_handler.py  # NeoPixel Class
│   ├── oled.py              # OLed Class
│   ├── rtc_handler.py       # RTC Class
│   ├── sdcard.py            # SD Card/Storage Class
│   ├── serial_com.py        # Serial Communications Class
│   ├── utils.py             # Utilites Class
│   └── esp-client	     # Arduino ESP-01s Webserver
└── docs
    ├── BOM.md               # Bill of Materials
    ├── WIRING.md	     # How to wire it
    └── PICO_GPIO_TABLE.md   # Table of how the GPIOs are used
```

### Data Format

**CSV Log Files:** `/sd/session_{value}.csv`
```csv
# Driver: John
# VIN: 1ZVBP8AM5E5123456
# Start: 785
timestamp,gx,gy,gz,g_total,lat,lon,alt,speed,sats,hdop
785,-0.03,-0.01,1.05,1.05,0,0,0.0,0.0,0,0.0
785,-0.02,-0.0,1.04,1.04,0,0,0.0,0.0,0,1.4
```

---

## Getting Started

### Prerequisites

- CircuitPython 10.x on Raspberry Pi Pico 2W
- Required libraries (place in `lib/`) [CircuitPython Libraries](https://circuitpython.org/libraries):
  - `adafruit_lis3dh`
  - `adafruit_gps`
  - `adafruit_displayio_ssd1306`
  - `adafruit_display_text`
  - `adafruit_bitmap_font`
  - `adafruit_displayio_ssd1306`
  - `neopixel`
  - `sdcardio` (built-in)

### Installation

1. **Flash CircuitPython 10.x** to Pico 2W
2. **Copy files** to CIRCUITPY drive:
```
   logger_refactor/*.py
```
3. **Install required libraries** in `lib/`
4. **Insert formatted SD card** (FAT32)
5. **Reboot** - system starts automatically

### Usage

1. **Power on** - System initializes and starts logging
2. **Connect to WiFi:** SSID `OpenPonyLogger`, password `mustanggt`
3. **Open browser:** Navigate to `http://192.168.4.1`
4. **View live data** - Telemetry updates in real-time
5. **Stop logging** - Press Ctrl+C in serial console

### Web Interface

Access at `http://192.168.4.1` when connected to OpenPonyLogger WiFi:

- **Live G-Force Display** - Real-time accelerometer readings
- **System Status** - Uptime, memory, connection info
- **API Endpoints:**
  - `/api/live` - Current telemetry (JSON)
  - `/api/status` - System information (JSON)

---

## Performance

**Measured Performance (CircuitPython Alpha):**
- Accelerometer sampling: ~10Hz
- Display update: 5Hz
- SD card logging: ~10Hz (buffered, 50 samples)
- Web server: Responsive <100ms
- Total power: 62mA @ 5V

**Target Performance (C/C++ Production):**
- Accelerometer: 100Hz (10x faster)
- GPS: 10Hz
- OBD-II: 1-5Hz
- Dual-core: Core 0 = acquisition, Core 1 = storage/WiFi

---

## Development Roadmap

### Phase 1: Hardware Validation (Current - CircuitPython)
- [x] LIS3DH Accelerometer
- [x] OLED Display
- [x] SD Card Logging
- [x] GPS Module
- [x] WiFi AP + Web Server via esp-01s
- [ ] Bluetooth OBD-II (optional)

### Phase 2: Integration & Testing
- [ ] Complete sensor fusion
- [ ] Extended stress testing
- [ ] Power consumption optimization
- [ ] Web UI enhancement

### Phase 3: Production (C/C++ Port)
- [ ] Dual-core architecture (RP2350)
- [ ] DMA for UART/SPI
- [ ] Hardware interrupts
- [ ] GPS PPS timing (Requires Hardware Interrupts)
- [ ] Lock-free ring buffers
- [ ] Optimized for 100Hz+ sampling

---

## Vehicle Installation (Future)

**Target Vehicle:** 2014 Ford Mustang GT (S197) "Ciara"

**Power Source:** 12V from OBD-II port → LM2596 buck converter → 5V  
**Mounting:** Center console, velcro-mounted enclosure  
**Accelerometer Position:** Near vehicle center of gravity  
**GPS Antenna:** Clear sky view (windshield mount)

---

## Design Philosophy

**"Foundation First"** - Inspired by Carroll Shelby

1. **Validate in CircuitPython** - Fast iteration, prove concepts
2. **Measure real performance** - Know actual achievable sample rates
3. **Find hardware issues early** - I2C conflicts, power, pinouts
4. **Port to C with confidence** - One clean port, not debugging hardware AND code

**Cost Target:** <$100 (vs $400-800 commercial units)

---

## Technical Details

### Why CircuitPython First?

✅ Rapid prototyping (no compile/flash cycle)  
✅ Rich library ecosystem (Adafruit)  
✅ Easy hardware debugging  
✅ Validate architecture before C port  

### Why Port to C/C++?

✅ 10-100x performance improvement  
✅ Dual-core utilization (RP2350)  
✅ DMA and hardware interrupts  
✅ Sub-millisecond timing precision  
✅ Professional-grade data acquisition  

### Communication Protocols

- **I2C:** LIS3DH accelerometer, OLED display
- **SPI:** SD card storage
- **UART:** GPS module (NMEA sentences)
- **WiFi:** Access Point + HTTP server
- **Bluetooth LE:** OBD-II (future)

---

## Contributing

This is a personal project for the 2014 Mustang GT "Ciara", but contributions welcome:

- Hardware improvements
- Code optimization
- Additional sensor support
- Post-processing tools
- Documentation improvements
- Vehicle-specific integrations

---

## License

MIT License - See LICENSE file

---

## Acknowledgments

- **Adafruit** - CircuitPython and hardware libraries
- **Raspberry Pi Foundation** - Pico 2W platform
- **Carroll Shelby** - "Foundation first" philosophy
- **Mustang community** - Inspiration and support

---

## Contact

**Project Lead:** John Orthoefer  
**Repository:** https://github.com/John-MustangGT/OpenPyPony  
**Target Vehicle:** 2014 Ford Mustang GT "Ciara"

---

**Status:** Active Development | **Version:** 0.1.0-alpha | **Last Updated:** December 2024
