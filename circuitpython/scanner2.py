"""
i2c_scanner_advanced.py - Enhanced I2C scanner with device details

Features:
- Pretty formatted output
- Device identification
- Multiple scans
- Detailed information
"""

import board
import time

class I2CScanner:
    """I2C Bus Scanner with device identification"""
    
    # Known device database
    KNOWN_DEVICES = {
        # OpenPonyLogger devices
        0x10: {
            'name': 'PA1010D GPS',
            'chip': 'MTK3333',
            'type': 'GPS Receiver',
            'i2c_speed': '100kHz/400kHz'
        },
        0x18: {
            'name': 'LIS3DH',
            'chip': 'STMicro LIS3DH',
            'type': '3-Axis Accelerometer',
            'i2c_speed': '100kHz/400kHz'
        },
        0x3C: {
            'name': 'OLED Display',
            'chip': 'SSD1306/SH1106',
            'type': 'Monochrome OLED',
            'i2c_speed': '100kHz/400kHz'
        },
        0x6A: {
            'name': 'LSM6DSOX',
            'chip': 'STMicro LSM6DSOX',
            'type': '6-Axis IMU (Accel + Gyro)',
            'i2c_speed': '100kHz/400kHz/1MHz'
        },
        0x6B: {
            'name': 'LSM6DSOX (alt)',
            'chip': 'STMicro LSM6DSOX',
            'type': '6-Axis IMU (Accel + Gyro)',
            'i2c_speed': '100kHz/400kHz/1MHz'
        },
        
        # Common additional devices
        0x42: {
            'name': 'ESP32 I2C Slave',
            'chip': 'ESP32',
            'type': 'Microcontroller (I2C mode)',
            'i2c_speed': '100kHz/400kHz'
        },
        0x68: {
            'name': 'MPU6050 / DS3231',
            'chip': 'InvenSense MPU6050 or Maxim DS3231',
            'type': '6-Axis IMU or RTC',
            'i2c_speed': '100kHz/400kHz'
        },
    }
    
    def __init__(self):
        """Initialize I2C bus"""
        try:
            self.i2c = board.STEMMA_I2C()
            self.bus_name = "STEMMA_I2C (GP8=SDA, GP9=SCL)"
        except AttributeError:
            import busio
            self.i2c = busio.I2C(board.GP9, board.GP8)
            self.bus_name = "Manual I2C (GP8=SDA, GP9=SCL)"
    
    def scan(self):
        """Scan I2C bus and return device list"""
        while not self.i2c.try_lock():
            pass
        
        try:
            devices = self.i2c.scan()
            return devices
        finally:
            self.i2c.unlock()
    
    def print_header(self):
        """Print scanner header"""
        print()
        print("=" * 70)
        print("  I2C BUS SCANNER - OpenPonyLogger")
        print("=" * 70)
        print(f"  Bus: {self.bus_name}")
        print("=" * 70)
        print()
    
    def print_devices(self, devices):
        """Print device list with details"""
        if len(devices) == 0:
            print("❌ No I2C devices found!")
            print()
            print("Troubleshooting:")
            print("  1. Check power connections (VCC/3V3 and GND)")
            print("  2. Verify SDA/SCL wiring")
            print("  3. Ensure pull-up resistors present (4.7kΩ typical)")
            print("  4. Check if devices are enabled/initialized")
            print()
            return
        
        print(f"✓ Found {len(devices)} device(s):")
        print()
        print("┌" + "─" * 68 + "┐")
        print("│ Dec | Hex  │ Device Name                                       │")
        print("├" + "─" * 68 + "┤")
        
        for addr in devices:
            info = self.KNOWN_DEVICES.get(addr)
            
            dec_str = f"{addr:3d}"
            hex_str = f"0x{addr:02X}"
            
            if info:
                name = info['name']
            else:
                name = "Unknown Device"
            
            print(f"│ {dec_str} │ {hex_str} │ {name:<50}│")
        
        print("└" + "─" * 68 + "┘")
        print()
    
    def print_details(self, devices):
        """Print detailed information about each device"""
        if len(devices) == 0:
            return
        
        print("Device Details:")
        print()
        
        for addr in devices:
            info = self.KNOWN_DEVICES.get(addr)
            hex_str = f"0x{addr:02X}"
            
            print(f"  [{hex_str}] ", end="")
            
            if info:
                print(f"{info['name']}")
                print(f"         Chip: {info['chip']}")
                print(f"         Type: {info['type']}")
                print(f"         I2C Speed: {info['i2c_speed']}")
            else:
                print("Unknown Device")
                print(f"         No information available")
            
            print()
    
    def run(self, show_details=True):
        """Run a complete scan"""
        self.print_header()
        devices = self.scan()
        self.print_devices(devices)
        
        if show_details and len(devices) > 0:
            self.print_details(devices)
        
        print("=" * 70)
        print()


# Run the scanner
if __name__ == "__main__":
    scanner = I2CScanner()
    scanner.run(show_details=True)
    
    print("Scan complete!")
    print()
    print("To run again, press Ctrl+C and re-run this script")
    print("or reset your board.")
