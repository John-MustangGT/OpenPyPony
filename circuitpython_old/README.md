# OpenPyPony 🐎

Open-source automotive telemetry system for track day data logging.

## Features

- Real-time OBD-II data monitoring
- GPS tracking with satellite visualization
- 3-axis accelerometer for G-force measurement
- Session recording and playback
- Web-based interface
- Low-cost ($33 vs $400-800 commercial units)

## Quick Start

### Hardware
- Raspberry Pi Pico 2W
- LIS3DH Accelerometer
- ATGM336H GPS Module
- PiCowbell Adalogger
- See [BOM.md](hardware/BOM.md)

### Installation
```bash
# Clone repository
git clone https://github.com/John-MustangGT/OpenPyPony.git
cd OpenPyPony

# Install dependencies
pip install circup mpy-cross

# Deploy to Pico
make deploy-mpy
```

### Quick Deploy
```bash
make deploy-mpy    # Deploy with optimizations
```

## Documentation

- [Build Guide](docs/BUILD_GUIDE.md)
- [User Guide](docs/USER_GUIDE.md)
- [Deployment Guide](tools/README.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Project Structure
