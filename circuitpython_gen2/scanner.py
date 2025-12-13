"""
i2c_scanner.py - Scan and list all I2C devices

Works on: Raspberry Pi Pico, Pico 2, any CircuitPython board
"""

import board
import time

print("=" * 50)
print("I2C Bus Scanner")
print("=" * 50)
print()

# Initialize I2C bus
# Use STEMMA_I2C() if your board supports it (Pico 2 W, Feathers, etc.)
# Otherwise use busio.I2C() with specific pins
try:
    i2c = board.STEMMA_I2C()  # Uses board's default I2C (GP8/GP9 on Pico)
    print("✓ Using STEMMA_I2C()")
except AttributeError:
    # Fallback for boards without STEMMA_I2C
    import busio
    i2c = busio.I2C(board.GP9, board.GP8)  # SCL, SDA
    print("✓ Using manual I2C (GP9=SCL, GP8=SDA)")

print()

# Wait for I2C to be ready
while not i2c.try_lock():
    pass

try:
    print("Scanning I2C bus...")
    print()
    
    # Scan for devices (addresses 0x00 to 0x7F)
    devices = i2c.scan()
    
    if len(devices) == 0:
        print("❌ No I2C devices found!")
        print()
        print("Check:")
        print("  - Are devices powered?")
        print("  - Are SDA/SCL connected correctly?")
        print("  - Are pull-up resistors present? (usually built-in)")
    else:
        print(f"✓ Found {len(devices)} device(s):")
        print()
        print("Address  | Hex    | Possible Device")
        print("-" * 50)
        
        for addr in devices:
            hex_addr = f"0x{addr:02X}"
            dec_addr = f"{addr:3d}"
            
            # Try to identify common devices by address
            device_name = identify_device(addr)
            
            print(f"{dec_addr}      | {hex_addr}  | {device_name}")
    
    print()
    print("=" * 50)
    
finally:
    i2c.unlock()


def identify_device(addr):
    """Identify common I2C devices by address"""
    
    # Common device addresses for OpenPonyLogger
    known_devices = {
        0x10: "PA1010D GPS (MTK3333)",
        0x18: "LIS3DH Accelerometer",
        0x19: "LIS3DH Accelerometer (alt)",
        0x1E: "HMC5883L Magnetometer",
        0x29: "VL53L0X Distance Sensor",
        0x3C: "SSD1306/SH1106 OLED Display",
        0x3D: "SSD1306 OLED Display (alt)",
        0x42: "ESP32 (if configured as I2C slave)",
        0x48: "ADS1115 ADC",
        0x50: "AT24C32 EEPROM",
        0x57: "AT24C32 EEPROM (alt)",
        0x68: "MPU6050 IMU / DS3231 RTC",
        0x69: "MPU6050 IMU (alt)",
        0x6A: "LSM6DSOX IMU",
        0x6B: "LSM6DSOX IMU (alt)",
        0x76: "BMP280/BME280 Pressure Sensor",
        0x77: "BMP280/BME280 Pressure Sensor (alt)",
    }
    
    return known_devices.get(addr, "Unknown device")


print("\nScan complete!")
