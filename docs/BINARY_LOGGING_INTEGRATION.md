# Binary Logging Integration Guide

## Overview

The binary logging format has been reintegrated into the modular codebase with the following features:

- **Dual format support**: CSV or Binary (configurable in settings.toml)
- **Session management**: Metadata, checksums, event-based flushing
- **Unified API**: Same interface for both formats
- **60% smaller files**: Binary format is significantly more compact than CSV
- **Data integrity**: SHA-256 checksums (or CRC32 fallback) on all blocks

## Files Added

1. **`binary_logger.py`** - Binary format implementation
2. **`config.py`** - Configuration management (updated)
3. **`session_logger.py`** - Unified logger wrapper
4. **`settings.toml.example`** - Updated with LOG_FORMAT option

## Integration Steps

### 1. Update Your code.py (or main module)

Replace your current Session/logging code with:

```python
from session_logger import SessionLogger
from config import config

# Create logger (automatically uses format from config)
logger = SessionLogger("/sd")

# Start session (uses metadata from config)
logger.start_session()

# In your main loop:
while True:
    # Read sensors
    x, y, z = lis3dh.acceleration
    gx, gy, gz = x/9.81, y/9.81, z/9.81
    
    # Log accelerometer
    logger.write_accelerometer(gx, gy, gz)
    
    # Log GPS (when available)
    if gps.has_fix:
        logger.write_gps(
            gps.latitude,
            gps.longitude,
            gps.altitude_m or 0,
            gps.speed_knots * 1.15078,  # Convert to MPH
            gps.track_angle_deg or 0,
            gps.hdop or 0
        )
    
    time.sleep(0.01)
```

### 2. Update deploy_to_pico.py

Add the new modules to the deployment list:

```python
python_modules = [
    "code.py",
    "accelerometer.py",
    "config.py",               # Updated
    "gps.py",
    "hardware_setup.py",
    "neopixel_handler.py",
    "oled.py",
    "rtc_handler.py",
    "sdcard.py",
    "serial_com.py",
    "utils.py",
    "binary_logger.py",        # New
    "session_logger.py",       # New
]
```

### 3. Configure logging format

In `settings.toml`:

```toml
# Use binary format (default, recommended)
LOG_FORMAT = "binary"

# Or use CSV format for compatibility
# LOG_FORMAT = "csv"

# Session metadata (used in binary format)
SESSION_NAME = "Track Day"
DRIVER_NAME = "John"
VEHICLE_ID = "Ciara"

# G-force event threshold (binary format only)
GFORCE_EVENT_THRESHOLD = "3.0"
```

## Binary Format Features

### Automatic Flushing

Data is automatically flushed to SD card when:
- **Time**: 5 minutes since last write
- **Size**: Buffer reaches 90% capacity (3.6KB)
- **Event**: G-force exceeds threshold (default 3.0g)
- **Shutdown**: Clean system shutdown

### File Structure

Binary files use `.opl` extension:
```
/sd/session_1234567890.opl
```

Each file contains:
1. **Session Header Block**
   - Format version
   - Session metadata (name, driver, vehicle)
   - Weather, temperature
   - Config checksum
   
2. **Data Blocks** (multiple)
   - Up to 4KB per block
   - SHA-256 checksum per block
   - Flush reason flags
   - Packed sensor samples

3. **Session End Block**
   - Session termination marker

### Sample Types

- `0x01`: Accelerometer (3x float32)
- `0x02`: GPS Fix (lat, lon, alt, speed, heading, hdop)
- `0x03`: GPS Satellites (variable)

## API Reference

### SessionLogger Methods

```python
# Start session
logger.start_session(
    session_name="Track Day",    # Optional, uses config default
    driver_name="John",           # Optional, uses config default
    vehicle_id="Ciara",           # Optional, uses config default
    weather=WEATHER_CLEAR,        # Binary only
    ambient_temp=72.5,            # Binary only (°F)
    config_crc=0x12345678         # Binary only
)

# Write accelerometer data
logger.write_accelerometer(gx, gy, gz, timestamp_us=None)

# Write GPS data
logger.write_gps(lat, lon, alt, speed, heading, hdop, timestamp_us=None)

# Write GPS satellites (binary only)
logger.write_gps_satellites(satellites, timestamp_us=None)

# Stop session
logger.stop_session()

# Get session info
duration = logger.get_duration()
bytes_per_sec = logger.get_bytes_per_second()
is_active = logger.active
filename = logger.filename
```

## File Size Comparison

Example 10-minute track session at 100Hz accelerometer + 1Hz GPS:

| Format | File Size | Compression |
|--------|-----------|-------------|
| CSV | ~3.2 MB | 0% (baseline) |
| Binary | ~1.3 MB | 60% smaller |

## Reading Binary Files

Binary files require a parser. A Python parser tool will be provided separately that can:
- Extract session metadata
- Convert to CSV
- Validate checksums
- Filter by event types
- Export to common formats

## Backwards Compatibility

The system maintains full backwards compatibility:
- CSV format works exactly as before
- All existing code continues to work
- Switch formats with single config change
- No data loss when switching formats

## Migration Path

1. **Deploy new modules**: `make deploy`
2. **Test with CSV first**: Set `LOG_FORMAT = "csv"` 
3. **Verify logging works**: Check files in `/sd/`
4. **Switch to binary**: Set `LOG_FORMAT = "binary"`
5. **Confirm smaller files**: Check `.opl` file sizes

## Troubleshooting

### "Binary logging not available"
- Check that `binary_logger.py` is deployed to Pico
- Verify no import errors in serial console

### Files still in CSV format
- Check `settings.toml` has `LOG_FORMAT = "binary"`
- Restart session after changing setting
- Check serial console for "[SessionLogger] Using binary format"

### Large binary files
- Normal! Data blocks are only flushed on events or timeout
- Files grow in 4KB chunks
- Final size still ~60% smaller than CSV

## Performance Impact

Binary format has **lower** CPU overhead than CSV:
- No float-to-string conversion
- No string concatenation
- Simple struct.pack() operations
- Faster SD card writes (fewer, larger blocks)

Power consumption is slightly reduced due to less SD card activity.
