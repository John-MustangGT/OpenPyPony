# OpenPyPony 🐎

**Open-source automotive telemetry system for track day data logging**

OpenPyPony is a low-cost, professional-grade data acquisition system built for the 2014 Ford Mustang GT "Ciara". This CircuitPython prototype validates hardware and software architecture before porting to C/C++ for production use.

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

**In Progress:**
- 🔧 GPS module integration (ATGM336H)
- 🔧 PPS timing synchronization

**Planned:**
- ⏳ Bluetooth OBD-II integration
- ⏳ Port to C/C++ for dual-core RP2350
- ⏳ Advanced web UI with gauges

---

## Hardware

### Bill of Materials

| Component | Part | Purpose | Status |
|-----------|------|---------|--------|
| Microcontroller | Raspberry Pi Pico 2W (RP2350) | Main processor with WiFi | ✅ Working |
| Accelerometer | LIS3DH (I2C) | 3-axis G-force measurement | ✅ Working |
| GPS | ATGM336H (UART) | Position, speed, timing | 🔧 Integrating |
| Display | SSD1306 OLED 128x64 (I2C) | Live telemetry display | ✅ Working |
| Storage | PiCowbell Adalogger + SD card | Data logging | ✅ Working |
| OBD-II | VGate iCar Pro (BLE) | Engine data (future) | ⏳ Planned |

### Pinout
```
Raspberry Pi Pico 2W GPIO Assignment:

GP0  - GPS TX (UART0)
GP1  - GPS RX (UART0)
GP2  - GPS PPS (1Hz timing pulse)
GP8  - I2C SDA (LIS3DH + OLED)
GP9  - I2C SCL (LIS3DH + OLED)
GP12 - SD MISO (SPI1)
GP13 - SD CS
GP14 - SD SCK
GP15 - SD MOSI
GP16 - (Reserved)
GP17 - (Reserved)
GP18 - (Reserved)
GP19 - (Reserved)
```

### Power Consumption

- **Baseline (Accel + OLED):** 20mA @ 5V
- **+ WiFi Active:** 62mA @ 5V (0.31W)
- **+ GPS (estimated):** ~100mA @ 5V (0.5W)

**Battery Life:** 20+ hours on 2000mAh USB battery pack

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
WebServer            10ms        HTTP request polling
WiFi Monitor         5000ms      Connection status
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
├── code.py              # Main program
├── lib/
│   ├── scheduler.py     # Task scheduler
│   └── wifi_server.py   # WiFi AP + HTTP server
├── web/                 # Web interface (on CIRCUITPY drive)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── gauge.min.js
└── version.py           # Auto-generated version info
```

### Data Format

**CSV Log Files:** `/sd/accel_log_<timestamp>.csv`
```csv
timestamp_ms,accel_x,accel_y,accel_z,gforce_x,gforce_y,gforce_z,gforce_total
0,-9.350,-0.280,-2.000,-0.95,-0.03,-0.20,0.97
100,-9.340,-0.290,-2.010,-0.95,-0.03,-0.20,0.97
```

**Future:** GPS data will be added as additional columns

---

## Getting Started

### Prerequisites

- CircuitPython 10.x on Raspberry Pi Pico 2W
- Required libraries (place in `lib/`):
  - `adafruit_lis3dh`
  - `adafruit_displayio_ssd1306`
  - `sdcardio` (built-in)
  - `adafruit_httpserver`

### Installation

1. **Flash CircuitPython 10.x** to Pico 2W
2. **Copy files** to CIRCUITPY drive:
```
   code.py
   lib/scheduler.py
   lib/wifi_server.py
   web/ (entire directory)
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
- [x] WiFi AP + Web Server
- [ ] GPS Module (in progress)
- [ ] GPS PPS timing
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
