"""
lis3mdl.py - LIS3MDL magnetometer driver for CircuitPython

Supports:
- 3-axis magnetometer (±4/8/12/16 gauss)
- Temperature sensor
- High-performance and low-power modes

Hardware:
- LIS3MDL 3-axis magnetometer
- I2C interface

I2C connections:
- VIN -> 3.3V
- GND -> GND
- SCL -> GP9
- SDA -> GP8
- SDO -> GND (0x1C) or 3.3V (0x1E)
"""

import time
import struct
from micropython import const

# I2C addresses
LIS3MDL_ADDR_LOW = const(0x1C)    # SDO/SA1 = GND
LIS3MDL_ADDR_HIGH = const(0x1E)   # SDO/SA1 = VCC

# Register addresses
WHO_AM_I = const(0x0F)            # Should return 0x3D
CTRL_REG1 = const(0x20)           # Control register 1
CTRL_REG2 = const(0x21)           # Control register 2
CTRL_REG3 = const(0x22)           # Control register 3
CTRL_REG4 = const(0x23)           # Control register 4
STATUS_REG = const(0x27)          # Status register
OUT_X_L = const(0x28)             # X-axis low byte
OUT_TEMP_L = const(0x2E)          # Temperature low byte

# WHO_AM_I value
LIS3MDL_CHIP_ID = const(0x3D)

# Range settings (full scale)
RANGE_4_GAUSS = const(0x00)       # ±4 gauss
RANGE_8_GAUSS = const(0x20)       # ±8 gauss
RANGE_12_GAUSS = const(0x40)      # ±12 gauss
RANGE_16_GAUSS = const(0x60)      # ±16 gauss

# Performance mode
MODE_LOW_POWER = const(0x00)
MODE_MEDIUM = const(0x01)
MODE_HIGH = const(0x02)
MODE_ULTRA_HIGH = const(0x03)

# Data rates (Hz)
ODR_0_625_HZ = const(0x00)
ODR_1_25_HZ = const(0x04)
ODR_2_5_HZ = const(0x08)
ODR_5_HZ = const(0x0C)
ODR_10_HZ = const(0x10)
ODR_20_HZ = const(0x14)
ODR_40_HZ = const(0x18)
ODR_80_HZ = const(0x1C)

# Scale factors (gauss/LSB)
SCALE_4_GAUSS = 6842.0
SCALE_8_GAUSS = 3421.0
SCALE_12_GAUSS = 2281.0
SCALE_16_GAUSS = 1711.0

# Gauss to µT conversion
GAUSS_TO_UT = 100.0


class LIS3MDL:
    """
    LIS3MDL magnetometer driver
    
    Example usage:
        mag = LIS3MDL(i2c)
        mx, my, mz = mag.magnetic
        heading = mag.heading()
    """
    
    def __init__(self, i2c, address=LIS3MDL_ADDR_LOW, 
                 range=RANGE_4_GAUSS, mode=MODE_HIGH, data_rate=ODR_10_HZ):
        """
        Initialize LIS3MDL magnetometer
        
        Args:
            i2c: I2C bus object
            address: I2C address (0x1C or 0x1E)
            range: Magnetic range (RANGE_4/8/12/16_GAUSS)
            mode: Performance mode (MODE_LOW_POWER/MEDIUM/HIGH/ULTRA_HIGH)
            data_rate: Output data rate
        """
        self.i2c = i2c
        self.address = address
        self.range = range
        
        # Check device
        if address not in i2c.scan():
            raise RuntimeError(f"LIS3MDL not found at address 0x{address:02X}")
        
        # Verify chip ID
        chip_id = self._read_byte(WHO_AM_I)
        if chip_id != LIS3MDL_CHIP_ID:
            raise RuntimeError(f"Wrong chip ID: 0x{chip_id:02X} (expected 0x{LIS3MDL_CHIP_ID:02X})")
        
        # Set scale factor
        self._set_scale()
        
        # Configure device
        # CTRL_REG1: Temperature enabled, performance mode, data rate
        ctrl1 = 0x80 | (mode << 5) | data_rate
        self._write_byte(CTRL_REG1, ctrl1)
        
        # CTRL_REG2: Full scale
        self._write_byte(CTRL_REG2, range)
        
        # CTRL_REG3: Continuous conversion mode
        self._write_byte(CTRL_REG3, 0x00)
        
        # CTRL_REG4: Z-axis performance mode
        ctrl4 = mode << 2
        self._write_byte(CTRL_REG4, ctrl4)
        
        # Offsets (will be set by calibration)
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        
        print(f"[LIS3MDL] Initialized at 0x{address:02X}")
        print(f"[LIS3MDL] Range: ±{self._get_range_gauss()} gauss")
        print(f"[LIS3MDL] Mode: {self._get_mode_name(mode)}")
    
    def _write_byte(self, reg, value):
        """Write byte to register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_byte(self, reg):
        """Read byte from register"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def _read_bytes(self, reg, length):
        """Read multiple bytes from register"""
        return self.i2c.readfrom_mem(self.address, reg, length)
    
    def _set_scale(self):
        """Set scale factor based on range"""
        scales = {
            RANGE_4_GAUSS: SCALE_4_GAUSS,
            RANGE_8_GAUSS: SCALE_8_GAUSS,
            RANGE_12_GAUSS: SCALE_12_GAUSS,
            RANGE_16_GAUSS: SCALE_16_GAUSS
        }
        self.scale = scales.get(self.range, SCALE_4_GAUSS)
    
    def _get_range_gauss(self):
        """Get range in gauss"""
        ranges = {RANGE_4_GAUSS: 4, RANGE_8_GAUSS: 8, RANGE_12_GAUSS: 12, RANGE_16_GAUSS: 16}
        return ranges.get(self.range, 4)
    
    def _get_mode_name(self, mode):
        """Get mode name"""
        modes = {
            MODE_LOW_POWER: "Low Power",
            MODE_MEDIUM: "Medium",
            MODE_HIGH: "High Performance",
            MODE_ULTRA_HIGH: "Ultra High Performance"
        }
        return modes.get(mode, "Unknown")
    
    @property
    def magnetic(self):
        """
        Read magnetometer data
        
        Returns:
            Tuple of (mx, my, mz) in µT (microtesla)
        """
        # Wait for data ready
        status = self._read_byte(STATUS_REG)
        if not (status & 0x08):  # ZYXDA bit
            return (0.0, 0.0, 0.0)
        
        # Read 6 bytes (X, Y, Z)
        data = self._read_bytes(OUT_X_L, 6)
        raw_x, raw_y, raw_z = struct.unpack('<hhh', data)
        
        # Convert to gauss
        mx_gauss = raw_x / self.scale
        my_gauss = raw_y / self.scale
        mz_gauss = raw_z / self.scale
        
        # Convert to µT and apply offsets
        mx = (mx_gauss * GAUSS_TO_UT) - self.offset_x
        my = (my_gauss * GAUSS_TO_UT) - self.offset_y
        mz = (mz_gauss * GAUSS_TO_UT) - self.offset_z
        
        return (mx, my, mz)
    
    @property
    def temperature(self):
        """
        Read temperature sensor
        
        Returns:
            Temperature in Celsius (relative, not absolute)
        """
        # Read 2 bytes
        data = self._read_bytes(OUT_TEMP_L, 2)
        raw_temp = struct.unpack('<h', data)[0]
        
        # Convert to Celsius (typical sensitivity: 8 LSB/°C)
        # Note: This is a relative temperature, not calibrated absolute
        temp_c = 25.0 + (raw_temp / 8.0)
        
        return temp_c
    
    def calibrate(self, samples=200):
        """
        Calibrate magnetometer hard-iron offsets
        
        Rotate sensor in all directions during calibration
        
        Args:
            samples: Number of samples to collect
            
        Returns:
            Tuple of (offset_x, offset_y, offset_z) in µT
        """
        print(f"[LIS3MDL] Calibrating magnetometer ({samples} samples)...")
        print("[LIS3MDL] Rotate sensor in all directions!")
        
        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')
        
        for i in range(samples):
            mx, my, mz = self.magnetic
            min_x = min(min_x, mx)
            min_y = min(min_y, my)
            min_z = min(min_z, mz)
            max_x = max(max_x, mx)
            max_y = max(max_y, my)
            max_z = max(max_z, mz)
            time.sleep(0.05)
            
            if i % 20 == 0:
                print(f"  Progress: {i}/{samples}")
        
        # Calculate offsets (center of min/max range)
        self.offset_x = (max_x + min_x) / 2
        self.offset_y = (max_y + min_y) / 2
        self.offset_z = (max_z + min_z) / 2
        
        print(f"[LIS3MDL] Offsets: X={self.offset_x:.1f}, Y={self.offset_y:.1f}, Z={self.offset_z:.1f} µT")
        
        return (self.offset_x, self.offset_y, self.offset_z)
    
    def heading(self):
        """
        Calculate magnetic heading (compass direction)
        
        Assumes sensor is level (parallel to ground)
        
        Returns:
            Heading in degrees (0-360, 0=North)
        """
        import math
        
        mx, my, mz = self.magnetic
        
        # Calculate heading (atan2 returns -π to +π)
        heading_rad = math.atan2(my, mx)
        
        # Convert to degrees
        heading_deg = math.degrees(heading_rad)
        
        # Normalize to 0-360
        if heading_deg < 0:
            heading_deg += 360
        
        return heading_deg
    
    def self_test(self):
        """
        Perform basic self-test
        
        Returns:
            True if passed, False if failed
        """
        try:
            # Verify WHO_AM_I
            chip_id = self._read_byte(WHO_AM_I)
            if chip_id != LIS3MDL_CHIP_ID:
                print(f"[LIS3MDL] Self-test FAILED: Chip ID = 0x{chip_id:02X}")
                return False
            
            # Read magnetometer
            mx, my, mz = self.magnetic
            mag = (mx**2 + my**2 + mz**2)**0.5
            
            # Typical Earth magnetic field: 25-65 µT
            if mag < 10 or mag > 100:
                print(f"[LIS3MDL] Self-test WARNING: Magnitude = {mag:.1f} µT (expected ~25-65 µT)")
                print("[LIS3MDL] Sensor may need calibration or is too close to magnetic interference")
            
            print("[LIS3MDL] Self-test PASSED")
            return True
            
        except Exception as e:
            print(f"[LIS3MDL] Self-test FAILED: {e}")
            return False
