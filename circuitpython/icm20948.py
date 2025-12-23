"""
icm20948.py - ICM-20948 9-axis IMU driver for CircuitPython

Supports:
- 3-axis accelerometer (±2/4/8/16g)
- 3-axis gyroscope (±250/500/1000/2000 dps)
- 3-axis magnetometer (AK09916, ±4900µT)
- Configurable modes: accel-only, gyro-only, mag-only, or combinations

Hardware:
- ICM-20948 9-axis IMU
- I2C interface

I2C connections:
- VIN -> 3.3V
- GND -> GND
- SCL -> GP9
- SDA -> GP8
- AD0 -> GND (0x68) or 3.3V (0x69)
"""

import time
import struct
from micropython import const

# ICM-20948 I2C addresses
ICM20948_ADDR_LOW = const(0x68)   # AD0 = GND
ICM20948_ADDR_HIGH = const(0x69)  # AD0 = VCC

# Register banks
BANK_SEL = const(0x7F)

# Bank 0 registers
WHO_AM_I = const(0x00)            # Should return 0xEA
PWR_MGMT_1 = const(0x06)
PWR_MGMT_2 = const(0x07)
INT_PIN_CFG = const(0x0F)
INT_ENABLE = const(0x10)
INT_ENABLE_1 = const(0x11)
ACCEL_XOUT_H = const(0x2D)
GYRO_XOUT_H = const(0x33)
TEMP_OUT_H = const(0x39)
EXT_SLV_SENS_DATA_00 = const(0x3B)

# Bank 2 registers
ACCEL_CONFIG = const(0x14)
GYRO_CONFIG_1 = const(0x01)
GYRO_SMPLRT_DIV = const(0x00)
ACCEL_SMPLRT_DIV_1 = const(0x10)

# WHO_AM_I value
ICM20948_CHIP_ID = const(0xEA)

# Magnetometer (AK09916) registers
AK09916_ADDR = const(0x0C)
AK09916_WHO_AM_I = const(0x01)    # Should return 0x09
AK09916_ST1 = const(0x10)
AK09916_HXL = const(0x11)
AK09916_CNTL2 = const(0x31)
AK09916_CNTL3 = const(0x32)

# Accelerometer ranges
ACCEL_RANGE_2G = const(0x00)
ACCEL_RANGE_4G = const(0x02)
ACCEL_RANGE_8G = const(0x04)
ACCEL_RANGE_16G = const(0x06)

# Gyroscope ranges
GYRO_RANGE_250 = const(0x00)
GYRO_RANGE_500 = const(0x02)
GYRO_RANGE_1000 = const(0x04)
GYRO_RANGE_2000 = const(0x06)

# Scale factors
ACCEL_SCALE_2G = 16384.0
ACCEL_SCALE_4G = 8192.0
ACCEL_SCALE_8G = 4096.0
ACCEL_SCALE_16G = 2048.0

GYRO_SCALE_250 = 131.0
GYRO_SCALE_500 = 65.5
GYRO_SCALE_1000 = 32.8
GYRO_SCALE_2000 = 16.4

# Magnetometer scale (µT/LSB)
MAG_SCALE = 0.15  # 0.15 µT/LSB for AK09916


class ICM20948:
    """
    ICM-20948 9-axis IMU driver
    
    Example usage:
    
    # All sensors
    imu = ICM20948(i2c, mode='all')
    accel = imu.acceleration
    gyro = imu.gyro
    mag = imu.magnetic
    
    # Accelerometer only
    imu = ICM20948(i2c, mode='accel')
    x, y, z = imu.acceleration
    
    # Magnetometer only
    imu = ICM20948(i2c, mode='mag')
    mx, my, mz = imu.magnetic
    """
    
    def __init__(self, i2c, address=ICM20948_ADDR_LOW, mode='all',
                 accel_range=ACCEL_RANGE_2G, gyro_range=GYRO_RANGE_250):
        """
        Initialize ICM-20948
        
        Args:
            i2c: I2C bus object
            address: I2C address (0x68 or 0x69)
            mode: 'accel', 'gyro', 'mag', 'accel_gyro', 'all'
            accel_range: Accelerometer range
            gyro_range: Gyroscope range
        """
        self.i2c = i2c
        self.address = address
        self.mode = mode.lower()
        self.current_bank = -1
        
        valid_modes = ('accel', 'gyro', 'mag', 'accel_gyro', 'all')
        if self.mode not in valid_modes:
            raise ValueError(f"mode must be one of: {valid_modes}")
        
        # Parse mode flags
        self.use_accel = self.mode in ('accel', 'accel_gyro', 'all')
        self.use_gyro = self.mode in ('gyro', 'accel_gyro', 'all')
        self.use_mag = self.mode in ('mag', 'all')
        
        # Check device
        if address not in i2c.scan():
            raise RuntimeError(f"ICM-20948 not found at address 0x{address:02X}")
        
        # Select bank 0
        self._select_bank(0)
        
        # Verify chip ID
        chip_id = self._read_byte(WHO_AM_I)
        if chip_id != ICM20948_CHIP_ID:
            raise RuntimeError(f"Wrong chip ID: 0x{chip_id:02X} (expected 0x{ICM20948_CHIP_ID:02X})")
        
        # Reset device
        self._write_byte(PWR_MGMT_1, 0x80)
        time.sleep(0.1)
        
        # Wake up device
        self._write_byte(PWR_MGMT_1, 0x01)  # Auto select clock source
        time.sleep(0.01)
        
        # Enable accel and gyro
        pwr_mgmt_2 = 0x00
        if not self.use_accel:
            pwr_mgmt_2 |= 0x38  # Disable accel
        if not self.use_gyro:
            pwr_mgmt_2 |= 0x07  # Disable gyro
        self._write_byte(PWR_MGMT_2, pwr_mgmt_2)
        
        # Configure accelerometer
        if self.use_accel:
            self.accel_range = accel_range
            self._set_accel_scale()
            self._select_bank(2)
            self._write_byte(ACCEL_CONFIG, accel_range << 1)
            self._select_bank(0)
        
        # Configure gyroscope
        if self.use_gyro:
            self.gyro_range = gyro_range
            self._set_gyro_scale()
            self._select_bank(2)
            self._write_byte(GYRO_CONFIG_1, gyro_range << 1)
            self._select_bank(0)
        
        # Configure magnetometer
        if self.use_mag:
            self._init_magnetometer()
        
        print(f"[ICM20948] Initialized at 0x{address:02X}")
        print(f"[ICM20948] Mode: {mode}")
        if self.use_accel:
            print(f"[ICM20948] Accel range: ±{self._get_accel_range_g()}g")
        if self.use_gyro:
            print(f"[ICM20948] Gyro range: ±{self._get_gyro_range_dps()}°/s")
        if self.use_mag:
            print(f"[ICM20948] Magnetometer: AK09916")
    
    def _select_bank(self, bank):
        """Select register bank"""
        if bank != self.current_bank:
            self.i2c.writeto_mem(self.address, BANK_SEL, bytes([bank << 4]))
            self.current_bank = bank
    
    def _write_byte(self, reg, value):
        """Write byte to register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_byte(self, reg):
        """Read byte from register"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def _read_bytes(self, reg, length):
        """Read multiple bytes from register"""
        return self.i2c.readfrom_mem(self.address, reg, length)
    
    def _write_mag_byte(self, reg, value):
        """Write byte to magnetometer register"""
        self.i2c.writeto_mem(AK09916_ADDR, reg, bytes([value]))
    
    def _read_mag_byte(self, reg):
        """Read byte from magnetometer register"""
        return self.i2c.readfrom_mem(AK09916_ADDR, reg, 1)[0]
    
    def _read_mag_bytes(self, reg, length):
        """Read multiple bytes from magnetometer"""
        return self.i2c.readfrom_mem(AK09916_ADDR, reg, length)
    
    def _init_magnetometer(self):
        """Initialize AK09916 magnetometer"""
        # Enable I2C master mode and set speed to 400kHz
        self._select_bank(0)
        self._write_byte(INT_PIN_CFG, 0x02)  # Bypass mode
        time.sleep(0.01)
        
        # Check magnetometer WHO_AM_I
        try:
            mag_id = self._read_mag_byte(AK09916_WHO_AM_I)
            if mag_id != 0x09:
                print(f"[ICM20948] Warning: AK09916 ID = 0x{mag_id:02X} (expected 0x09)")
        except OSError:
            raise RuntimeError("Magnetometer (AK09916) not found")
        
        # Reset magnetometer
        self._write_mag_byte(AK09916_CNTL3, 0x01)
        time.sleep(0.01)
        
        # Set continuous measurement mode 4 (100Hz)
        self._write_mag_byte(AK09916_CNTL2, 0x08)
        time.sleep(0.01)
    
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
            GYRO_RANGE_250: GYRO_SCALE_250,
            GYRO_RANGE_500: GYRO_SCALE_500,
            GYRO_RANGE_1000: GYRO_SCALE_1000,
            GYRO_RANGE_2000: GYRO_SCALE_2000
        }
        self.gyro_scale = scales.get(self.gyro_range, GYRO_SCALE_250)
    
    def _get_accel_range_g(self):
        """Get accelerometer range in g"""
        ranges = {ACCEL_RANGE_2G: 2, ACCEL_RANGE_4G: 4, ACCEL_RANGE_8G: 8, ACCEL_RANGE_16G: 16}
        return ranges.get(self.accel_range, 2)
    
    def _get_gyro_range_dps(self):
        """Get gyroscope range in dps"""
        ranges = {GYRO_RANGE_250: 250, GYRO_RANGE_500: 500, GYRO_RANGE_1000: 1000, GYRO_RANGE_2000: 2000}
        return ranges.get(self.gyro_range, 250)
    
    @property
    def acceleration(self):
        """Read accelerometer (x, y, z) in m/s²"""
        if not self.use_accel:
            raise RuntimeError(f"Accelerometer not enabled (mode='{self.mode}')")
        
        self._select_bank(0)
        data = self._read_bytes(ACCEL_XOUT_H, 6)
        raw_x, raw_y, raw_z = struct.unpack('>hhh', data)
        
        x = (raw_x / self.accel_scale) * 9.80665
        y = (raw_y / self.accel_scale) * 9.80665
        z = (raw_z / self.accel_scale) * 9.80665
        
        return (x, y, z)
    
    @property
    def gyro(self):
        """Read gyroscope (gx, gy, gz) in °/s"""
        if not self.use_gyro:
            raise RuntimeError(f"Gyroscope not enabled (mode='{self.mode}')")
        
        self._select_bank(0)
        data = self._read_bytes(GYRO_XOUT_H, 6)
        raw_x, raw_y, raw_z = struct.unpack('>hhh', data)
        
        gx = raw_x / self.gyro_scale
        gy = raw_y / self.gyro_scale
        gz = raw_z / self.gyro_scale
        
        return (gx, gy, gz)
    
    @property
    def magnetic(self):
        """Read magnetometer (mx, my, mz) in µT"""
        if not self.use_mag:
            raise RuntimeError(f"Magnetometer not enabled (mode='{self.mode}')")
        
        # Check if data is ready
        st1 = self._read_mag_byte(AK09916_ST1)
        if not (st1 & 0x01):
            return (0.0, 0.0, 0.0)  # Data not ready
        
        # Read 6 bytes of mag data
        data = self._read_mag_bytes(AK09916_HXL, 6)
        raw_x, raw_y, raw_z = struct.unpack('<hhh', data)
        
        # Read ST2 to complete measurement
        self._read_mag_byte(0x18)
        
        # Convert to µT
        mx = raw_x * MAG_SCALE
        my = raw_y * MAG_SCALE
        mz = raw_z * MAG_SCALE
        
        return (mx, my, mz)
    
    @property
    def temperature(self):
        """Read temperature in °C"""
        self._select_bank(0)
        data = self._read_bytes(TEMP_OUT_H, 2)
        raw_temp = struct.unpack('>h', data)[0]
        
        # Convert to Celsius: ((TEMP_OUT - RoomTemp_Offset) / Temp_Sensitivity) + 21
        temp_c = (raw_temp / 333.87) + 21.0
        
        return temp_c
    
    def read_all(self):
        """Read all enabled sensors"""
        result = {}
        
        if self.use_accel:
            result['accel'] = self.acceleration
        if self.use_gyro:
            result['gyro'] = self.gyro
        if self.use_mag:
            result['mag'] = self.magnetic
        
        result['temp'] = self.temperature
        
        return result
    
    def calibrate_gyro(self, samples=100):
        """Calibrate gyroscope offsets"""
        if not self.use_gyro:
            raise RuntimeError("Gyroscope not enabled")
        
        print(f"[ICM20948] Calibrating gyro ({samples} samples)...")
        print("[ICM20948] Keep sensor stationary!")
        
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
        
        print(f"[ICM20948] Gyro offsets: X={offset_x:.2f}, Y={offset_y:.2f}, Z={offset_z:.2f} °/s")
        
        return (offset_x, offset_y, offset_z)
    
    def calibrate_magnetometer(self, samples=200):
        """
        Calibrate magnetometer hard-iron offsets
        Rotate sensor in all directions during calibration
        
        Returns:
            Tuple of (offset_x, offset_y, offset_z) in µT
        """
        if not self.use_mag:
            raise RuntimeError("Magnetometer not enabled")
        
        print(f"[ICM20948] Calibrating magnetometer ({samples} samples)...")
        print("[ICM20948] Rotate sensor in all directions!")
        
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
        
        offset_x = (max_x + min_x) / 2
        offset_y = (max_y + min_y) / 2
        offset_z = (max_z + min_z) / 2
        
        print(f"[ICM20948] Mag offsets: X={offset_x:.1f}, Y={offset_y:.1f}, Z={offset_z:.1f} µT")
        
        return (offset_x, offset_y, offset_z)
    
    def self_test(self):
        """Perform basic self-test"""
        try:
            self._select_bank(0)
            chip_id = self._read_byte(WHO_AM_I)
            if chip_id != ICM20948_CHIP_ID:
                print(f"[ICM20948] Self-test FAILED: Chip ID = 0x{chip_id:02X}")
                return False
            
            if self.use_accel:
                accel = self.acceleration
                mag = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
                if mag < 5 or mag > 15:
                    print(f"[ICM20948] Self-test WARNING: Accel magnitude = {mag:.2f} m/s²")
            
            if self.use_gyro:
                gyro = self.gyro
                mag = (gyro[0]**2 + gyro[1]**2 + gyro[2]**2)**0.5
                if mag > 50:
                    print(f"[ICM20948] Self-test WARNING: Gyro magnitude = {mag:.2f} °/s")
            
            if self.use_mag:
                mag_data = self.magnetic
                mag = (mag_data[0]**2 + mag_data[1]**2 + mag_data[2]**2)**0.5
                if mag < 10 or mag > 100:
                    print(f"[ICM20948] Self-test WARNING: Mag magnitude = {mag:.1f} µT")
            
            print("[ICM20948] Self-test PASSED")
            return True
            
        except Exception as e:
            print(f"[ICM20948] Self-test FAILED: {e}")
            return False
