"""
lsm6dsox.py - LSM6DSOX 6-axis IMU driver for CircuitPython

Supports:
- 3-axis accelerometer (±2/4/8/16g)
- 3-axis gyroscope (±125/250/500/1000/2000 dps)
- Configurable modes: accel-only, gyro-only, or both

Hardware:
- LSM6DSOX 6-axis IMU
- I2C or SPI interface (I2C implementation)

I2C connections:
- VIN -> 3.3V
- GND -> GND
- SCL -> GP9
- SDA -> GP8
- SDO -> GND (0x6A) or 3.3V (0x6B)
"""

import time
import struct
from micropython import const

# I2C addresses
LSM6DSOX_ADDR_LOW = const(0x6A)   # SDO/SA0 = GND
LSM6DSOX_ADDR_HIGH = const(0x6B)  # SDO/SA0 = VCC

# Register addresses
WHO_AM_I = const(0x0F)            # Should return 0x6C
CTRL1_XL = const(0x10)            # Accelerometer control
CTRL2_G = const(0x11)             # Gyroscope control
CTRL3_C = const(0x12)             # Control register 3
CTRL4_C = const(0x13)             # Control register 4

# Data registers
OUTX_L_G = const(0x22)            # Gyroscope X low byte
OUTX_L_A = const(0x28)            # Accelerometer X low byte
OUT_TEMP_L = const(0x20)          # Temperature low byte

# WHO_AM_I value
LSM6DSOX_CHIP_ID = const(0x6C)

# Accelerometer ranges
ACCEL_RANGE_2G = const(0x00)
ACCEL_RANGE_4G = const(0x08)
ACCEL_RANGE_8G = const(0x0C)
ACCEL_RANGE_16G = const(0x04)

# Gyroscope ranges
GYRO_RANGE_125 = const(0x02)
GYRO_RANGE_250 = const(0x00)
GYRO_RANGE_500 = const(0x04)
GYRO_RANGE_1000 = const(0x08)
GYRO_RANGE_2000 = const(0x0C)

# Output Data Rates (ODR)
ODR_POWER_DOWN = const(0x00)
ODR_12_5_HZ = const(0x10)
ODR_26_HZ = const(0x20)
ODR_52_HZ = const(0x30)
ODR_104_HZ = const(0x40)
ODR_208_HZ = const(0x50)
ODR_416_HZ = const(0x60)
ODR_833_HZ = const(0x70)
ODR_1660_HZ = const(0x80)
ODR_3330_HZ = const(0x90)
ODR_6660_HZ = const(0xA0)

# Scale factors (LSB/unit)
ACCEL_SCALE_2G = 16384.0
ACCEL_SCALE_4G = 8192.0
ACCEL_SCALE_8G = 4096.0
ACCEL_SCALE_16G = 2048.0

GYRO_SCALE_125 = 262.0
GYRO_SCALE_250 = 131.0
GYRO_SCALE_500 = 65.5
GYRO_SCALE_1000 = 32.8
GYRO_SCALE_2000 = 16.4


class LSM6DSOX:
    """
    LSM6DSOX 6-axis IMU driver
    
    Example usage:
    
    # Accelerometer only
    imu = LSM6DSOX(i2c, mode='accel')
    x, y, z = imu.acceleration
    
    # Gyroscope only
    imu = LSM6DSOX(i2c, mode='gyro')
    gx, gy, gz = imu.gyro
    
    # Both (default)
    imu = LSM6DSOX(i2c, mode='both')
    accel = imu.acceleration
    gyro = imu.gyro
    """
    
    def __init__(self, i2c, address=LSM6DSOX_ADDR_LOW, mode='both',
                 accel_range=ACCEL_RANGE_2G, gyro_range=GYRO_RANGE_250,
                 accel_odr=ODR_104_HZ, gyro_odr=ODR_104_HZ):
        """
        Initialize LSM6DSOX
        
        Args:
            i2c: I2C bus object
            address: I2C address (0x6A or 0x6B)
            mode: 'accel', 'gyro', or 'both'
            accel_range: Accelerometer range
            gyro_range: Gyroscope range
            accel_odr: Accelerometer output data rate
            gyro_odr: Gyroscope output data rate
        """
        self.i2c = i2c
        self.address = address
        self.mode = mode.lower()
        
        if self.mode not in ('accel', 'gyro', 'both'):
            raise ValueError("mode must be 'accel', 'gyro', or 'both'")
        
        # Check device
        if address not in i2c.scan():
            raise RuntimeError(f"LSM6DSOX not found at address 0x{address:02X}")
        
        # Verify chip ID
        chip_id = self._read_byte(WHO_AM_I)
        if chip_id != LSM6DSOX_CHIP_ID:
            raise RuntimeError(f"Wrong chip ID: 0x{chip_id:02X} (expected 0x{LSM6DSOX_CHIP_ID:02X})")
        
        # Software reset
        self._write_byte(CTRL3_C, 0x01)
        time.sleep(0.01)
        
        # Configure accelerometer
        if self.mode in ('accel', 'both'):
            self.accel_range = accel_range
            self._set_accel_scale()
            self._write_byte(CTRL1_XL, accel_odr | accel_range)
        else:
            self._write_byte(CTRL1_XL, ODR_POWER_DOWN)
        
        # Configure gyroscope
        if self.mode in ('gyro', 'both'):
            self.gyro_range = gyro_range
            self._set_gyro_scale()
            self._write_byte(CTRL2_G, gyro_odr | gyro_range)
        else:
            self._write_byte(CTRL2_G, ODR_POWER_DOWN)
        
        # Enable block data update
        self._write_byte(CTRL3_C, 0x40)
        
        print(f"[LSM6DSOX] Initialized at 0x{address:02X}")
        print(f"[LSM6DSOX] Mode: {mode}")
        if self.mode in ('accel', 'both'):
            print(f"[LSM6DSOX] Accel range: ±{self._get_accel_range_g()}g")
        if self.mode in ('gyro', 'both'):
            print(f"[LSM6DSOX] Gyro range: ±{self._get_gyro_range_dps()}°/s")
    
    def _write_byte(self, reg, value):
        """Write byte to register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_byte(self, reg):
        """Read byte from register"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def _read_bytes(self, reg, length):
        """Read multiple bytes from register"""
        return self.i2c.readfrom_mem(self.address, reg, length)
    
    def _set_accel_scale(self):
        """Set accelerometer scale factor"""
        scales = {
            ACCEL_RANGE_2G: ACCEL_SCALE_2G,
            ACCEL_RANGE_4G: ACCEL_SCALE_4G,
            ACCEL_RANGE_8G: ACCEL_SCALE_8G,
            ACCEL_RANGE_16G: ACCEL_SCALE_16G
        }
        self.accel_scale = scales.get(self.accel_range, ACCEL_SCALE_2G)
    
    def _set_gyro_scale(self):
        """Set gyroscope scale factor"""
        scales = {
            GYRO_RANGE_125: GYRO_SCALE_125,
            GYRO_RANGE_250: GYRO_SCALE_250,
            GYRO_RANGE_500: GYRO_SCALE_500,
            GYRO_RANGE_1000: GYRO_SCALE_1000,
            GYRO_RANGE_2000: GYRO_SCALE_2000
        }
        self.gyro_scale = scales.get(self.gyro_range, GYRO_SCALE_250)
    
    def _get_accel_range_g(self):
        """Get accelerometer range in g"""
        ranges = {
            ACCEL_RANGE_2G: 2,
            ACCEL_RANGE_4G: 4,
            ACCEL_RANGE_8G: 8,
            ACCEL_RANGE_16G: 16
        }
        return ranges.get(self.accel_range, 2)
    
    def _get_gyro_range_dps(self):
        """Get gyroscope range in dps"""
        ranges = {
            GYRO_RANGE_125: 125,
            GYRO_RANGE_250: 250,
            GYRO_RANGE_500: 500,
            GYRO_RANGE_1000: 1000,
            GYRO_RANGE_2000: 2000
        }
        return ranges.get(self.gyro_range, 250)
    
    @property
    def acceleration(self):
        """
        Read accelerometer data
        
        Returns:
            Tuple of (x, y, z) in m/s²
        """
        if self.mode not in ('accel', 'both'):
            raise RuntimeError(f"Accelerometer not enabled (mode='{self.mode}')")
        
        # Read 6 bytes
        data = self._read_bytes(OUTX_L_A, 6)
        
        # Unpack as signed 16-bit values (little-endian)
        raw_x, raw_y, raw_z = struct.unpack('<hhh', data)
        
        # Convert to m/s²
        x = (raw_x / self.accel_scale) * 9.80665
        y = (raw_y / self.accel_scale) * 9.80665
        z = (raw_z / self.accel_scale) * 9.80665
        
        return (x, y, z)
    
    @property
    def gyro(self):
        """
        Read gyroscope data
        
        Returns:
            Tuple of (gx, gy, gz) in degrees/second
        """
        if self.mode not in ('gyro', 'both'):
            raise RuntimeError(f"Gyroscope not enabled (mode='{self.mode}')")
        
        # Read 6 bytes
        data = self._read_bytes(OUTX_L_G, 6)
        
        # Unpack as signed 16-bit values (little-endian)
        raw_x, raw_y, raw_z = struct.unpack('<hhh', data)
        
        # Convert to dps
        gx = raw_x / self.gyro_scale
        gy = raw_y / self.gyro_scale
        gz = raw_z / self.gyro_scale
        
        return (gx, gy, gz)
    
    @property
    def temperature(self):
        """
        Read temperature sensor
        
        Returns:
            Temperature in Celsius
        """
        # Read 2 bytes
        data = self._read_bytes(OUT_TEMP_L, 2)
        raw_temp = struct.unpack('<h', data)[0]
        
        # Convert to Celsius: 25°C + (value / 256)
        temp_c = 25.0 + (raw_temp / 256.0)
        
        return temp_c
    
    def read_all(self):
        """
        Read all sensors at once
        
        Returns:
            Dict with keys: 'accel', 'gyro', 'temp'
        """
        result = {}
        
        if self.mode in ('accel', 'both'):
            result['accel'] = self.acceleration
        
        if self.mode in ('gyro', 'both'):
            result['gyro'] = self.gyro
        
        result['temp'] = self.temperature
        
        return result
    
    def calibrate_gyro(self, samples=100):
        """
        Calibrate gyroscope
        
        Args:
            samples: Number of samples to average
            
        Returns:
            Tuple of (offset_x, offset_y, offset_z)
        """
        if self.mode not in ('gyro', 'both'):
            raise RuntimeError("Gyroscope not enabled")
        
        print(f"[LSM6DSOX] Calibrating gyro ({samples} samples)...")
        print("[LSM6DSOX] Keep sensor stationary!")
        
        sum_x = sum_y = sum_z = 0
        
        for i in range(samples):
            gx, gy, gz = self.gyro
            sum_x += gx
            sum_y += gy
            sum_z += gz
            time.sleep(0.01)
        
        offset_x = sum_x / samples
        offset_y = sum_y / samples
        offset_z = sum_z / samples
        
        print(f"[LSM6DSOX] Gyro offsets: X={offset_x:.2f}, Y={offset_y:.2f}, Z={offset_z:.2f} °/s")
        
        return (offset_x, offset_y, offset_z)
    
    def self_test(self):
        """
        Perform basic self-test
        
        Returns:
            True if passed, False if failed
        """
        try:
            # Verify WHO_AM_I
            chip_id = self._read_byte(WHO_AM_I)
            if chip_id != LSM6DSOX_CHIP_ID:
                print(f"[LSM6DSOX] Self-test FAILED: Chip ID = 0x{chip_id:02X}")
                return False
            
            # Test accelerometer
            if self.mode in ('accel', 'both'):
                accel = self.acceleration
                mag = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
                if mag < 5 or mag > 15:
                    print(f"[LSM6DSOX] Self-test WARNING: Accel magnitude = {mag:.2f} m/s²")
            
            # Test gyroscope
            if self.mode in ('gyro', 'both'):
                gyro = self.gyro
                mag = (gyro[0]**2 + gyro[1]**2 + gyro[2]**2)**0.5
                if mag > 50:
                    print(f"[LSM6DSOX] Self-test WARNING: Gyro magnitude = {mag:.2f} °/s")
            
            print("[LSM6DSOX] Self-test PASSED")
            return True
            
        except Exception as e:
            print(f"[LSM6DSOX] Self-test FAILED: {e}")
            return False
