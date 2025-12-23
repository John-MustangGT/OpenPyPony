"""
mpu6050.py - MPU-6050 (GY-521) 6-axis IMU driver for CircuitPython

Supports:
- Accelerometer-only mode
- Gyroscope-only mode  
- Combined accelerometer + gyroscope mode

Hardware:
- MPU-6050 6-axis IMU (accelerometer + gyroscope)
- GY-521 module (MPU-6050 breakout board)
- I2C interface

Typical connections:
- VCC -> 3.3V
- GND -> GND
- SCL -> GP9 (I2C1 SCL)
- SDA -> GP8 (I2C1 SDA)
- (Optional) INT -> GPIO for interrupt-driven reads
"""

import time
import struct
from micropython import const

# MPU-6050 I2C address options
MPU6050_ADDR_LOW = const(0x68)   # AD0 pin = LOW
MPU6050_ADDR_HIGH = const(0x69)  # AD0 pin = HIGH

# Register addresses
PWR_MGMT_1 = const(0x6B)      # Power management
SMPLRT_DIV = const(0x19)      # Sample rate divider
CONFIG = const(0x1A)          # Configuration
GYRO_CONFIG = const(0x1B)     # Gyroscope configuration
ACCEL_CONFIG = const(0x1C)    # Accelerometer configuration
INT_ENABLE = const(0x38)      # Interrupt enable

# Data registers
ACCEL_XOUT_H = const(0x3B)    # Accelerometer X high byte
TEMP_OUT_H = const(0x41)      # Temperature high byte
GYRO_XOUT_H = const(0x43)     # Gyroscope X high byte

# Configuration values
PWR_MGMT_1_RESET = const(0x80)
PWR_MGMT_1_SLEEP = const(0x40)

# Accelerometer ranges (±g)
ACCEL_RANGE_2G = const(0x00)   # ±2g
ACCEL_RANGE_4G = const(0x08)   # ±4g
ACCEL_RANGE_8G = const(0x10)   # ±8g
ACCEL_RANGE_16G = const(0x18)  # ±16g

# Gyroscope ranges (°/s)
GYRO_RANGE_250 = const(0x00)   # ±250°/s
GYRO_RANGE_500 = const(0x08)   # ±500°/s
GYRO_RANGE_1000 = const(0x10)  # ±1000°/s
GYRO_RANGE_2000 = const(0x18)  # ±2000°/s

# Scale factors (LSB/unit)
ACCEL_SCALE_2G = 16384.0
ACCEL_SCALE_4G = 8192.0
ACCEL_SCALE_8G = 4096.0
ACCEL_SCALE_16G = 2048.0

GYRO_SCALE_250 = 131.0
GYRO_SCALE_500 = 65.5
GYRO_SCALE_1000 = 32.8
GYRO_SCALE_2000 = 16.4


class MPU6050:
    """
    MPU-6050 6-axis IMU driver
    
    Example usage:
    
    # Accelerometer only
    imu = MPU6050(i2c, mode='accel')
    x, y, z = imu.acceleration
    
    # Gyroscope only
    imu = MPU6050(i2c, mode='gyro')
    gx, gy, gz = imu.gyro
    
    # Both (default)
    imu = MPU6050(i2c, mode='both')
    accel = imu.acceleration
    gyro = imu.gyro
    """
    
    def __init__(self, i2c, address=MPU6050_ADDR_LOW, mode='both',
                 accel_range=ACCEL_RANGE_2G, gyro_range=GYRO_RANGE_250):
        """
        Initialize MPU-6050
        
        Args:
            i2c: I2C bus object
            address: I2C address (0x68 or 0x69)
            mode: Operating mode - 'accel', 'gyro', or 'both'
            accel_range: Accelerometer range (ACCEL_RANGE_2G/4G/8G/16G)
            gyro_range: Gyroscope range (GYRO_RANGE_250/500/1000/2000)
        """
        self.i2c = i2c
        self.address = address
        self.mode = mode.lower()
        
        if self.mode not in ('accel', 'gyro', 'both'):
            raise ValueError("mode must be 'accel', 'gyro', or 'both'")
        
        # Check if device is present
        if address not in i2c.scan():
            raise RuntimeError(f"MPU-6050 not found at address 0x{address:02X}")
        
        # Reset device
        self._write_byte(PWR_MGMT_1, PWR_MGMT_1_RESET)
        time.sleep(0.1)  # Wait for reset
        
        # Wake up device (exit sleep mode)
        self._write_byte(PWR_MGMT_1, 0x00)
        time.sleep(0.01)
        
        # Configure accelerometer
        if self.mode in ('accel', 'both'):
            self._write_byte(ACCEL_CONFIG, accel_range)
            self.accel_range = accel_range
            self._set_accel_scale()
        
        # Configure gyroscope
        if self.mode in ('gyro', 'both'):
            self._write_byte(GYRO_CONFIG, gyro_range)
            self.gyro_range = gyro_range
            self._set_gyro_scale()
        
        # Set sample rate to 1kHz / (1 + SMPLRT_DIV)
        # Default: 1kHz / (1 + 0) = 1kHz
        self._write_byte(SMPLRT_DIV, 0)
        
        # Configure digital low pass filter (DLPF)
        # 0x06 = 5Hz bandwidth (good for reducing noise)
        self._write_byte(CONFIG, 0x06)
        
        print(f"[MPU6050] Initialized at 0x{address:02X}")
        print(f"[MPU6050] Mode: {mode}")
        if self.mode in ('accel', 'both'):
            print(f"[MPU6050] Accel range: ±{self._get_accel_range_g()}g")
        if self.mode in ('gyro', 'both'):
            print(f"[MPU6050] Gyro range: ±{self._get_gyro_range_dps()}°/s")
    
    def _write_byte(self, reg, value):
        """Write single byte to register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_bytes(self, reg, length):
        """Read multiple bytes from register"""
        return self.i2c.readfrom_mem(self.address, reg, length)
    
    def _set_accel_scale(self):
        """Set accelerometer scale factor based on range"""
        scales = {
            ACCEL_RANGE_2G: ACCEL_SCALE_2G,
            ACCEL_RANGE_4G: ACCEL_SCALE_4G,
            ACCEL_RANGE_8G: ACCEL_SCALE_8G,
            ACCEL_RANGE_16G: ACCEL_SCALE_16G
        }
        self.accel_scale = scales.get(self.accel_range, ACCEL_SCALE_2G)
    
    def _set_gyro_scale(self):
        """Set gyroscope scale factor based on range"""
        scales = {
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
        """Get gyroscope range in degrees/second"""
        ranges = {
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
            raise RuntimeError("Accelerometer not enabled (mode='{}')".format(self.mode))
        
        # Read 6 bytes (X, Y, Z - each 2 bytes)
        data = self._read_bytes(ACCEL_XOUT_H, 6)
        
        # Unpack as signed 16-bit values (big-endian)
        raw_x, raw_y, raw_z = struct.unpack('>hhh', data)
        
        # Convert to m/s² (1g = 9.80665 m/s²)
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
            raise RuntimeError("Gyroscope not enabled (mode='{}')".format(self.mode))
        
        # Read 6 bytes (X, Y, Z - each 2 bytes)
        data = self._read_bytes(GYRO_XOUT_H, 6)
        
        # Unpack as signed 16-bit values (big-endian)
        raw_x, raw_y, raw_z = struct.unpack('>hhh', data)
        
        # Convert to degrees/second
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
        data = self._read_bytes(TEMP_OUT_H, 2)
        
        # Unpack as signed 16-bit value (big-endian)
        raw_temp = struct.unpack('>h', data)[0]
        
        # Convert to Celsius: Temperature = (TEMP_OUT / 340) + 36.53
        temp_c = (raw_temp / 340.0) + 36.53
        
        return temp_c
    
    def read_all(self):
        """
        Read all sensors at once (accelerometer + gyroscope + temperature)
        More efficient than reading individually.
        
        Returns:
            Dict with keys: 'accel', 'gyro', 'temp'
        """
        result = {}
        
        if self.mode in ('accel', 'both'):
            # Read accel (6 bytes) + temp (2 bytes) + gyro (6 bytes) = 14 bytes
            data = self._read_bytes(ACCEL_XOUT_H, 14)
            
            # Unpack accelerometer
            raw_ax, raw_ay, raw_az = struct.unpack('>hhh', data[0:6])
            result['accel'] = (
                (raw_ax / self.accel_scale) * 9.80665,
                (raw_ay / self.accel_scale) * 9.80665,
                (raw_az / self.accel_scale) * 9.80665
            )
            
            # Unpack temperature
            raw_temp = struct.unpack('>h', data[6:8])[0]
            result['temp'] = (raw_temp / 340.0) + 36.53
            
            if self.mode == 'both':
                # Unpack gyroscope
                raw_gx, raw_gy, raw_gz = struct.unpack('>hhh', data[8:14])
                result['gyro'] = (
                    raw_gx / self.gyro_scale,
                    raw_gy / self.gyro_scale,
                    raw_gz / self.gyro_scale
                )
        
        elif self.mode == 'gyro':
            # Read gyro only + temp
            data = self._read_bytes(TEMP_OUT_H, 8)
            
            # Unpack temperature
            raw_temp = struct.unpack('>h', data[0:2])[0]
            result['temp'] = (raw_temp / 340.0) + 36.53
            
            # Unpack gyroscope
            raw_gx, raw_gy, raw_gz = struct.unpack('>hhh', data[2:8])
            result['gyro'] = (
                raw_gx / self.gyro_scale,
                raw_gy / self.gyro_scale,
                raw_gz / self.gyro_scale
            )
        
        return result
    
    def calibrate_gyro(self, samples=100):
        """
        Calibrate gyroscope by averaging samples at rest
        
        Args:
            samples: Number of samples to average
        
        Returns:
            Tuple of (offset_x, offset_y, offset_z)
        """
        if self.mode not in ('gyro', 'both'):
            raise RuntimeError("Gyroscope not enabled")
        
        print(f"[MPU6050] Calibrating gyro ({samples} samples)...")
        print("[MPU6050] Keep sensor stationary!")
        
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
        
        print(f"[MPU6050] Gyro offsets: X={offset_x:.2f}, Y={offset_y:.2f}, Z={offset_z:.2f} °/s")
        
        return (offset_x, offset_y, offset_z)
    
    def self_test(self):
        """
        Perform basic self-test
        
        Returns:
            True if passed, False if failed
        """
        try:
            # Read WHO_AM_I register (should return 0x68)
            who_am_i = self._read_bytes(0x75, 1)[0]
            if who_am_i != 0x68:
                print(f"[MPU6050] Self-test FAILED: WHO_AM_I = 0x{who_am_i:02X} (expected 0x68)")
                return False
            
            # Test accelerometer
            if self.mode in ('accel', 'both'):
                accel = self.acceleration
                # Check if values are reasonable (should see ~1g on one axis when stationary)
                mag = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
                if mag < 5 or mag > 15:  # Reasonable range: 0.5g to 1.5g
                    print(f"[MPU6050] Self-test WARNING: Accel magnitude = {mag:.2f} m/s²")
            
            # Test gyroscope
            if self.mode in ('gyro', 'both'):
                gyro = self.gyro
                # When stationary, gyro should be near zero
                mag = (gyro[0]**2 + gyro[1]**2 + gyro[2]**2)**0.5
                if mag > 50:  # More than 50°/s when stationary is suspicious
                    print(f"[MPU6050] Self-test WARNING: Gyro magnitude = {mag:.2f} °/s (sensor moving?)")
            
            print("[MPU6050] Self-test PASSED")
            return True
            
        except Exception as e:
            print(f"[MPU6050] Self-test FAILED: {e}")
            return False
