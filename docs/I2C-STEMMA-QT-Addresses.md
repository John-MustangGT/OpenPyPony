# I2C STEMMA QT Address Map - OpenPonyLogger

This document tracks all I2C devices connected to the STEMMA QT bus (GP4=SDA, GP5=SCL) on the Raspberry Pi Pico 2W.

## Current I2C Devices

| Address | Device | Component | Notes |
|---------|--------|-----------|-------|
| **0x10** | PA1010D | GPS Module (I2C) | Adafruit Mini GPS PA1010D (optional, I2C alternative to UART GPS) |
| **0x18** | LIS3DH | 3-Axis Accelerometer | Adafruit LIS3DH (optional, original sensor) |
| **0x3C** | SSD1306 | OLED Display (128x64) | PiCowbell Proto |
| **0x68** | PCF8523 | Real-Time Clock (RTC) | PiCowbell Proto (built-in) |
| **0x69** | MPU6050 or ICM-20948 | 6-Axis or 9-Axis IMU | **Choose one** - both default to 0x69 |

## Sensor Capabilities

### LIS3DH (3-Axis Accelerometer)
- **Address:** 0x18 or 0x19 (via SDO jumper)
- **Features:** 3-axis accelerometer only
- **Part:** Adafruit LIS3DH Breakout
- **Status:** Original sensor, optional

### MPU-6050 (6-Axis IMU)
- **Address:** 0x68 or 0x69 (via AD0 jumper)
- **Features:** 3-axis accelerometer + 3-axis gyroscope
- **Part:** Adafruit MPU-6050 STEMMA QT (PID 3886)
- **Note:** Requires AD0 jumper to avoid RTC conflict

### ICM-20948 (9-Axis IMU)
- **Address:** 0x68 or 0x69 (via AD0 jumper)
- **Features:** 3-axis accelerometer + 3-axis gyroscope + 3-axis magnetometer (compass)
- **Part:** Adafruit ICM-20948 STEMMA QT
- **Note:** Most advanced option, includes compass/magnetometer

### PA1010D (GPS Module - I2C)
- **Address:** 0x10 (fixed, cannot be changed)
- **Features:** GPS receiver with I2C interface (MTK3333 chipset)
- **Part:** Adafruit Mini GPS PA1010D
- **Note:** I2C alternative to UART GPS, frees up UART1 for other uses
- **Library:** `adafruit_gps` (same as ATGM336H)

### ATGM336H (GPS Module - UART)
- **Interface:** UART (GP8/GP9)
- **Features:** GPS receiver with UART interface (MTK3333 chipset)
- **Part:** Various ATGM336H modules
- **Note:** Default GPS option, uses UART1
- **Library:** `adafruit_gps`

## Address Conflicts

### Resolved: MPU6050/ICM20948 vs PCF8523 RTC

**Problem:** The MPU-6050 and ICM-20948 both default to address 0x68, which conflicts with the PiCowbell PCF8523 RTC.

**Solution:** Bridge the AD0 solder jumper on the back of the MPU-6050 or ICM-20948 board to change its address to 0x69.

**Configuration Examples:**

MPU-6050:
```toml
[sensors.accelerometer]
type = "MPU6050"
address = 0x69  # Changed from default 0x68 to avoid RTC conflict
range = 2
sample_rate = 100

[sensors.gyroscope]
enabled = true
range = 250
```

ICM-20948:
```toml
[sensors.accelerometer]
type = "ICM20948"
address = 0x69  # Changed from default 0x68 to avoid RTC conflict
range = 2
sample_rate = 100

[sensors.gyroscope]
enabled = true
range = 250

[sensors.magnetometer]
enabled = true
```

PA1010D GPS (I2C):
```toml
[gps]
enabled = true
type = "PA1010D"
address = 0x10  # Fixed I2C address
update_rate = 1000  # 1Hz update rate (1000ms)
```

ATGM336H GPS (UART):
```toml
[gps]
enabled = true
type = "ATGM336H"
update_rate = 1000  # 1Hz update rate (1000ms)
```

**Important:** You cannot use both MPU-6050 and ICM-20948 at the same time (they both use 0x69). Choose one based on your needs:
- MPU-6050: Basic 6-axis IMU (accel + gyro)
- ICM-20948: Advanced 9-axis IMU (accel + gyro + magnetometer/compass)

**GPS Options:** Choose between PA1010D (I2C) or ATGM336H (UART):
- PA1010D: I2C GPS, frees up UART1, uses STEMMA QT connector
- ATGM336H: UART GPS, traditional interface, uses GP8/GP9

## Common I2C Addresses (7-bit)

For reference, here are typical I2C addresses for common sensors:

| Address Range | Common Devices |
|--------------|----------------|
| 0x18-0x19 | LIS3DH Accelerometer |
| 0x20-0x27 | MCP23017 I/O Expander, PCF8574 |
| 0x28-0x29 | BNO055 9-DOF IMU |
| 0x3C-0x3D | SSD1306 OLED Display |
| 0x40-0x4F | PCA9685 PWM Driver, INA219 Current Sensor |
| 0x48-0x4B | ADS1115 ADC, TMP102 Temperature |
| 0x50-0x57 | AT24C EEPROM |
| 0x60-0x6F | MPL3115A2 Altimeter, MCP4725 DAC |
| 0x68-0x69 | MPU6050/MPU9250 IMU, PCF8523/DS1307 RTC |
| 0x76-0x77 | BMP280/BME280 Pressure/Humidity |

## Available Addresses

The following addresses are currently **unused** and available for future devices:

- 0x11-0x17
- 0x18-0x19 (LIS3DH no longer used)
- 0x20-0x2F
- 0x3D
- 0x40-0x67
- 0x6A-0x6F
- 0x70-0x77

**Note:** 0x10 is now used by PA1010D GPS if configured for I2C

## Hardware Configuration

### Adafruit MPU-6050 STEMMA QT (PID 3886)

**Default Address:** 0x68
**Alternate Address:** 0x69 (when AD0 jumper bridged)

**To change address to 0x69:**
1. Locate the AD0 solder jumper on the back of the board
2. Bridge the jumper pads with solder
3. Update `settings.toml` with `address = 0x69`

**Library Required:** `adafruit_mpu6050.mpy`, `adafruit_register/`, `adafruit_bus_device/`

### Adafruit ICM-20948 STEMMA QT

**Default Address:** 0x68
**Alternate Address:** 0x69 (when AD0 jumper bridged)

**To change address to 0x69:**
1. Locate the AD0 solder jumper on the back of the board
2. Bridge the jumper pads with solder
3. Update `settings.toml` with `address = 0x69`

**Library Required:** `adafruit_icm20x.mpy`, `adafruit_register/`, `adafruit_bus_device/`

**Magnetometer Features:**
- Provides compass heading (0-360°)
- Magnetic field measurement in microteslas (µT)
- Useful for navigation and orientation tracking

### Adafruit Mini GPS PA1010D

**Fixed Address:** 0x10 (cannot be changed)
**Interface:** I2C (also supports UART, but OpenPonyLogger uses I2C mode)

**Configuration:**
1. Connect to STEMMA QT connector on PiCowbell
2. Update `settings.toml` with `type = "PA1010D"` and `address = 0x10`
3. GPS will use I2C instead of UART, freeing up UART1

**Library Required:** `adafruit_gps.mpy`

**Benefits:**
- Same adafruit_gps library as ATGM336H (no new dependencies)
- Frees up UART1 (GP8/GP9) for other uses
- Clean STEMMA QT connection (no jumper wires)
- MTK3333 chipset - same as many GPS modules

**Limitations:**
- Fixed I2C address (0x10), cannot be changed
- Slightly slower update rate over I2C vs UART (but still sufficient for racing)

### PiCowbell Proto

**Fixed Addresses:**
- **0x68:** PCF8523 RTC (built-in, cannot be changed)
- **0x3C:** SSD1306 OLED (depends on display model)

## Notes

- All addresses are 7-bit I2C addresses
- The I2C bus can support up to 127 devices (addresses 0x08-0x77)
- Addresses 0x00-0x07 and 0x78-0x7F are reserved
- Always check for address conflicts when adding new STEMMA QT devices
- Use `i2cdetect` or the boot-up I2C scan to verify connected devices

## I2C Scan Output

Example output from OpenPonyLogger boot (with PA1010D GPS):

```
[HAL] Initializing buses...
  ✓ I2C initialized (GP5=SCL, GP4=SDA) [STEMMA QT]
    Found 4 device(s): ['0x10', '0x3c', '0x68', '0x69']
```

Example output without PA1010D (UART GPS only):

```
[HAL] Initializing buses...
  ✓ I2C initialized (GP5=SCL, GP4=SDA) [STEMMA QT]
    Found 3 device(s): ['0x3c', '0x68', '0x69']
```

## Last Updated

2025-01-03 - Added PA1010D I2C GPS support at 0x10 (optional alternative to UART GPS)
