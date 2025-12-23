"""
accelerometer.py - Unified accelerometer interface

Supports multiple accelerometer hardware:
- LIS3DH (Adafruit breakout)
- MPU-6050 (GY-521 module) - accelerometer only, gyro only, or both

Configuration via hardware.toml determines which sensor to use.
"""

import board
import busio
from debug import debug_print

# Sensor-specific imports (try/except for optional hardware)
try:
    import adafruit_lis3dh
    LIS3DH_AVAILABLE = True
except ImportError:
    LIS3DH_AVAILABLE = False
    debug_print("LIS3DH", "adafruit_lis3dh not available")

try:
    from mpu6050 import MPU6050, ACCEL_RANGE_2G, ACCEL_RANGE_4G, ACCEL_RANGE_8G, ACCEL_RANGE_16G
    from mpu6050 import GYRO_RANGE_250, GYRO_RANGE_500, GYRO_RANGE_1000, GYRO_RANGE_2000
    MPU6050_AVAILABLE = True
except ImportError:
    MPU6050_AVAILABLE = False
    debug_print("MPU6050", "mpu6050 module not available")


class UnifiedAccelerometer:
    """
    Unified interface for accelerometer hardware
    
    Automatically selects and initializes the correct sensor
    based on hardware configuration.
    """
    
    def __init__(self, hw_config, i2c):
        """
        Initialize accelerometer based on hardware configuration
        
        Args:
            hw_config: Hardware configuration dict
            i2c: I2C bus object
        """
        self.hw_config = hw_config
        self.i2c = i2c
        self.sensor = None
        self.sensor_type = None
        self.has_gyro = False
        
        # Get accelerometer config
        accel_config = hw_config.get('accelerometer', {})
        sensor_type = accel_config.get('sensor', 'lis3dh').lower()
        
        if not accel_config.get('enabled', True):
            debug_print("ACCEL", "Accelerometer disabled in config")
            return
        
        # Initialize appropriate sensor
        if sensor_type == 'lis3dh':
            self._init_lis3dh(accel_config)
        elif sensor_type == 'mpu6050':
            self._init_mpu6050(accel_config, hw_config.get('gyroscope', {}))
        else:
            raise ValueError(f"Unknown accelerometer sensor: {sensor_type}")
        
        debug_print("ACCEL", f"Initialized {self.sensor_type}")
    
    def _init_lis3dh(self, config):
        """Initialize LIS3DH accelerometer"""
        if not LIS3DH_AVAILABLE:
            raise RuntimeError("LIS3DH selected but adafruit_lis3dh not available")
        
        lis3dh_config = config.get('lis3dh', {})
        address = lis3dh_config.get('i2c_address', 0x18)
        
        debug_print("ACCEL", f"Initializing LIS3DH at 0x{address:02X}")
        
        self.sensor = adafruit_lis3dh.LIS3DH_I2C(self.i2c, address=address)
        self.sensor_type = 'lis3dh'
        
        # Set range
        range_g = lis3dh_config.get('range', 2)
        range_map = {
            2: adafruit_lis3dh.RANGE_2_G,
            4: adafruit_lis3dh.RANGE_4_G,
            8: adafruit_lis3dh.RANGE_8_G,
            16: adafruit_lis3dh.RANGE_16_G
        }
        self.sensor.range = range_map.get(range_g, adafruit_lis3dh.RANGE_2_G)
        
        # Set data rate
        rate_hz = lis3dh_config.get('data_rate', 100)
        rate_map = {
            1: adafruit_lis3dh.DATARATE_1_HZ,
            10: adafruit_lis3dh.DATARATE_10_HZ,
            25: adafruit_lis3dh.DATARATE_25_HZ,
            50: adafruit_lis3dh.DATARATE_50_HZ,
            100: adafruit_lis3dh.DATARATE_100_HZ,
            200: adafruit_lis3dh.DATARATE_200_HZ,
            400: adafruit_lis3dh.DATARATE_400_HZ
        }
        self.sensor.data_rate = rate_map.get(rate_hz, adafruit_lis3dh.DATARATE_100_HZ)
        
        debug_print("ACCEL", f"LIS3DH configured: ±{range_g}g @ {rate_hz}Hz")
    
    def _init_mpu6050(self, accel_config, gyro_config):
        """Initialize MPU-6050 IMU"""
        if not MPU6050_AVAILABLE:
            raise RuntimeError("MPU-6050 selected but mpu6050 module not available")
        
        mpu_config = accel_config.get('mpu6050', {})
        address = mpu_config.get('i2c_address', 0x68)
        mode = mpu_config.get('mode', 'accel').lower()
        
        # Check if gyroscope is also enabled
        gyro_enabled = gyro_config.get('enabled', False)
        if gyro_enabled:
            gyro_mpu_config = gyro_config.get('mpu6050', {})
            gyro_mode = gyro_mpu_config.get('mode', 'gyro').lower()
            
            # If both are enabled, use 'both' mode
            if mode == 'accel' and gyro_mode == 'gyro':
                mode = 'both'
                self.has_gyro = True
            elif mode == 'both' or gyro_mode == 'both':
                mode = 'both'
                self.has_gyro = True
        
        debug_print("ACCEL", f"Initializing MPU-6050 at 0x{address:02X}, mode={mode}")
        
        # Map range values
        accel_range_g = mpu_config.get('range', 2)
        accel_range_map = {
            2: ACCEL_RANGE_2G,
            4: ACCEL_RANGE_4G,
            8: ACCEL_RANGE_8G,
            16: ACCEL_RANGE_16G
        }
        accel_range = accel_range_map.get(accel_range_g, ACCEL_RANGE_2G)
        
        gyro_range = GYRO_RANGE_250  # Default
        if self.has_gyro:
            gyro_mpu_config = gyro_config.get('mpu6050', {})
            gyro_range_dps = gyro_mpu_config.get('range', 250)
            gyro_range_map = {
                250: GYRO_RANGE_250,
                500: GYRO_RANGE_500,
                1000: GYRO_RANGE_1000,
                2000: GYRO_RANGE_2000
            }
            gyro_range = gyro_range_map.get(gyro_range_dps, GYRO_RANGE_250)
        
        # Initialize sensor
        self.sensor = MPU6050(
            self.i2c,
            address=address,
            mode=mode,
            accel_range=accel_range,
            gyro_range=gyro_range
        )
        self.sensor_type = 'mpu6050'
        
        # Run self-test
        self.sensor.self_test()
        
        # Calibrate gyro if enabled
        if self.has_gyro:
            self.gyro_offsets = self.sensor.calibrate_gyro()
        else:
            self.gyro_offsets = (0, 0, 0)
    
    @property
    def acceleration(self):
        """
        Get acceleration data
        
        Returns:
            Tuple of (x, y, z) in m/s²
        """
        if self.sensor is None:
            return (0.0, 0.0, 0.0)
        
        return self.sensor.acceleration
    
    @property
    def gyro(self):
        """
        Get gyroscope data (if available)
        
        Returns:
            Tuple of (gx, gy, gz) in degrees/second
            Returns (0, 0, 0) if gyroscope not available
        """
        if not self.has_gyro or self.sensor is None:
            return (0.0, 0.0, 0.0)
        
        if self.sensor_type == 'mpu6050':
            gx, gy, gz = self.sensor.gyro
            # Apply calibration offsets
            gx -= self.gyro_offsets[0]
            gy -= self.gyro_offsets[1]
            gz -= self.gyro_offsets[2]
            return (gx, gy, gz)
        
        return (0.0, 0.0, 0.0)
    
    @property
    def temperature(self):
        """
        Get temperature (if available)
        
        Returns:
            Temperature in Celsius, or None if not available
        """
        if self.sensor is None:
            return None
        
        if self.sensor_type == 'mpu6050':
            return self.sensor.temperature
        
        return None
    
    def read_all(self):
        """
        Read all available sensor data at once
        
        Returns:
            Dict with keys: 'accel', 'gyro' (if available), 'temp' (if available)
        """
        if self.sensor is None:
            return {'accel': (0, 0, 0)}
        
        if self.sensor_type == 'mpu6050':
            return self.sensor.read_all()
        else:
            return {
                'accel': self.acceleration
            }


def setup_accelerometer(hw_config, i2c=None):
    """
    Setup accelerometer based on hardware configuration
    
    Args:
        hw_config: Hardware configuration dict
        i2c: I2C bus (if None, will create one)
    
    Returns:
        UnifiedAccelerometer instance
    """
    if i2c is None:
        # Create I2C bus
        i2c_config = hw_config.get('i2c', {})
        scl_pin = getattr(board, f"GP{i2c_config.get('scl', 9)}")
        sda_pin = getattr(board, f"GP{i2c_config.get('sda', 8)}")
        freq = i2c_config.get('frequency', 400000)
        
        i2c = busio.I2C(scl_pin, sda_pin, frequency=freq)
        debug_print("I2C", f"Created I2C bus: SCL=GP{i2c_config.get('scl')}, SDA=GP{i2c_config.get('sda')}")
    
    return UnifiedAccelerometer(hw_config, i2c)
