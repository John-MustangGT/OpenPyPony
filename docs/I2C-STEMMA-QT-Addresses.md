# I2C STEMMA QT Address Map - OpenPonyLogger

This document tracks all I2C devices connected to the STEMMA QT bus (GP4=SDA, GP5=SCL) on the Raspberry Pi Pico 2W.

## Current I2C Devices

| Address | Device | Component | Notes |
|---------|--------|-----------|-------|
| **0x3C** | SSD1306 | OLED Display (128x64) | PiCowbell Proto |
| **0x68** | PCF8523 | Real-Time Clock (RTC) | PiCowbell Proto (built-in) |
| **0x69** | MPU6050 | 6-Axis IMU (Accel + Gyro) | Adafruit STEMMA QT MPU-6050 (AD0 bridged) |

## Address Conflicts

### Resolved: MPU6050 vs PCF8523 RTC

**Problem:** Both the Adafruit MPU-6050 and PiCowbell PCF8523 RTC default to address 0x68.

**Solution:** Bridge the AD0 solder jumper on the back of the MPU-6050 board to change its address to 0x69.

**Configuration:**
```toml
[sensors.accelerometer]
type = "MPU6050"
address = 0x69  # Changed from default 0x68 to avoid RTC conflict
range = 2
sample_rate = 100
```

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

- 0x18-0x19 (LIS3DH no longer used)
- 0x20-0x2F
- 0x3D
- 0x40-0x67
- 0x6A-0x6F
- 0x70-0x77

## Hardware Configuration

### Adafruit MPU-6050 STEMMA QT (PID 3886)

**Default Address:** 0x68
**Alternate Address:** 0x69 (when AD0 jumper bridged)

**To change address to 0x69:**
1. Locate the AD0 solder jumper on the back of the board
2. Bridge the jumper pads with solder
3. Update `settings.toml` with `address = 0x69`

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

Example output from OpenPonyLogger boot:

```
[HAL] Initializing buses...
  ✓ I2C initialized (GP5=SCL, GP4=SDA) [STEMMA QT]
    Found 3 device(s): ['0x3c', '0x68', '0x69']
```

## Last Updated

2025-01-31 - Added MPU6050 at 0x69 (AD0 bridged to resolve conflict with PCF8523 RTC)
