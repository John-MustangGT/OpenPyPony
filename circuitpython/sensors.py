"""
sensors.py - Sensor drivers and management for OpenPonyLogger

Handles all data acquisition sensors:
- Accelerometers: LIS3DH, LSM6DSOX, ICM-20948, MPU-6050/GY-521
- Gyroscopes: LSM6DSOX, ICM-20948, MPU-6050/GY-521
- Magnetometers: ICM-20948, LIS3MDL
- GPS: ATGM336H (UART), PA1010D (I2C/UART)
- Future: CAN bus, OBD-II, tire pressure, etc.
"""

import board
import busio
from hardware_config import hw_config


# =============================================================================
# Sensor Manager (Global Registry)
# =============================================================================

class SensorManager:
    """Registry for all initialized sensors"""
    
    def __init__(self):
        self.sensors = {}
    
    def register(self, name, sensor):
        """Register a sensor"""
        self.sensors[name] = sensor
    
    def get(self, name):
        """Get sensor by name"""
        return self.sensors.get(name)
    
    def list(self):
        """List all registered sensors"""
        return list(self.sensors.keys())


# Global sensor registry
_sensor_manager = SensorManager()


# =============================================================================
# Accelerometer Support
# =============================================================================

def init_accelerometer(i2c_bus):
    """
    Initialize accelerometer (supports multiple types)
    
    Supported sensors:
    - LIS3DH (I2C)
    - LSM6DSOX (I2C) - 6DOF IMU
    - ICM-20948 (I2C) - 9DOF IMU
    - MPU-6050/GY-521 (I2C) - 6DOF IMU
    
    Args:
        i2c_bus: I2C bus object
    
    Returns:
        Accelerometer object or None
    """
    if not hw_config.is_enabled("sensors.accelerometer"):
        print("[Accel] Disabled in config")
        return None
    
    if not i2c_bus:
        print("[Accel] No I2C bus available")
        return None
    
    accel_type = hw_config.get("sensors.accelerometer.type", "LIS3DH").upper()
    accel_addr = hw_config.get_int("sensors.accelerometer.address", 0x18)
    
    try:
        if accel_type == "LIS3DH":
            return _init_lis3dh(i2c_bus, accel_addr)
        elif accel_type == "LSM6DSOX" or accel_type == "LSM6DS":
            return _init_lsm6dsox(i2c_bus, accel_addr)
        elif accel_type == "ICM20948" or accel_type == "ICM-20948":
            return _init_icm20948(i2c_bus, accel_addr)
        elif accel_type == "MPU6050" or accel_type == "MPU-6050" or accel_type == "GY-521":
            return _init_mpu6050(i2c_bus, accel_addr)
        else:
            print(f"[Accel] Unsupported type: {accel_type}")
            return None
            
    except Exception as e:
        print(f"✗ Accelerometer error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _init_lis3dh(i2c_bus, address):
    """Initialize LIS3DH accelerometer"""
    import adafruit_lis3dh
    
    lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c_bus, address=address)
    
    # Configure range
    accel_range = hw_config.get_int("sensors.accelerometer.range", 2)
    if accel_range == 4:
        lis3dh.range = adafruit_lis3dh.RANGE_4_G
    elif accel_range == 8:
        lis3dh.range = adafruit_lis3dh.RANGE_8_G
    elif accel_range == 16:
        lis3dh.range = adafruit_lis3dh.RANGE_16_G
    else:
        lis3dh.range = adafruit_lis3dh.RANGE_2_G
    
    # Configure sample rate
    sample_rate = hw_config.get_int("sensors.accelerometer.sample_rate", 100)
    if sample_rate == 10:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_10_HZ
    elif sample_rate == 25:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_25_HZ
    elif sample_rate == 50:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_50_HZ
    elif sample_rate == 200:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_200_HZ
    elif sample_rate == 400:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_400_HZ
    else:
        lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ
    
    _sensor_manager.register('accelerometer', lis3dh)
    _sensor_manager.register('lis3dh', lis3dh)
    print(f"✓ LIS3DH initialized (±{accel_range}g @ {sample_rate}Hz)")
    return lis3dh


def _init_lsm6dsox(i2c_bus, address):
    """Initialize LSM6DSOX 6DOF IMU (accelerometer + gyro)"""
    import adafruit_lsm6ds
    from adafruit_lsm6ds import LSM6DSOX
    
    sensor = LSM6DSOX(i2c_bus, address=address)
    
    # Configure accelerometer range
    accel_range = hw_config.get_int("sensors.accelerometer.range", 4)
    if accel_range == 2:
        sensor.accelerometer_range = adafruit_lsm6ds.AccelRange.RANGE_2G
    elif accel_range == 4:
        sensor.accelerometer_range = adafruit_lsm6ds.AccelRange.RANGE_4G
    elif accel_range == 8:
        sensor.accelerometer_range = adafruit_lsm6ds.AccelRange.RANGE_8G
    elif accel_range == 16:
        sensor.accelerometer_range = adafruit_lsm6ds.AccelRange.RANGE_16G
    
    # Configure sample rate
    sample_rate = hw_config.get_int("sensors.accelerometer.sample_rate", 104)
    if sample_rate <= 12:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_12_5_HZ
    elif sample_rate <= 26:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_26_HZ
    elif sample_rate <= 52:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_52_HZ
    elif sample_rate <= 104:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_104_HZ
    elif sample_rate <= 208:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_208_HZ
    elif sample_rate <= 416:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_416_HZ
    else:
        sensor.accelerometer_data_rate = adafruit_lsm6ds.Rate.RATE_833_HZ
    
    _sensor_manager.register('accelerometer', sensor)
    _sensor_manager.register('lsm6dsox', sensor)
    _sensor_manager.register('imu', sensor)
    print(f"✓ LSM6DSOX initialized (±{accel_range}g @ {sample_rate}Hz)")
    
    # Also register as gyroscope if enabled
    if hw_config.is_enabled("sensors.gyroscope"):
        _init_lsm6dsox_gyro(sensor)
    
    return sensor


def _init_icm20948(i2c_bus, address):
    """Initialize ICM-20948 9DOF IMU (accelerometer + gyro + magnetometer)"""
    import adafruit_icm20x
    from adafruit_icm20x import ICM20948
    
    sensor = ICM20948(i2c_bus, address=address)
    
    # Configure accelerometer range
    accel_range = hw_config.get_int("sensors.accelerometer.range", 4)
    if accel_range == 2:
        sensor.accelerometer_range = adafruit_icm20x.AccelRange.RANGE_2G
    elif accel_range == 4:
        sensor.accelerometer_range = adafruit_icm20x.AccelRange.RANGE_4G
    elif accel_range == 8:
        sensor.accelerometer_range = adafruit_icm20x.AccelRange.RANGE_8G
    elif accel_range == 16:
        sensor.accelerometer_range = adafruit_icm20x.AccelRange.RANGE_16G
    
    # Configure sample rate (ICM20948 uses data rate divider)
    sample_rate = hw_config.get_int("sensors.accelerometer.sample_rate", 100)
    if sample_rate <= 17:
        sensor.accelerometer_data_rate_divisor = 64  # ~17 Hz
    elif sample_rate <= 34:
        sensor.accelerometer_data_rate_divisor = 32  # ~34 Hz
    elif sample_rate <= 68:
        sensor.accelerometer_data_rate_divisor = 16  # ~68 Hz
    elif sample_rate <= 136:
        sensor.accelerometer_data_rate_divisor = 8   # ~136 Hz
    elif sample_rate <= 273:
        sensor.accelerometer_data_rate_divisor = 4   # ~273 Hz
    else:
        sensor.accelerometer_data_rate_divisor = 2   # ~562 Hz
    
    _sensor_manager.register('accelerometer', sensor)
    _sensor_manager.register('icm20948', sensor)
    _sensor_manager.register('imu', sensor)
    print(f"✓ ICM-20948 initialized (±{accel_range}g @ {sample_rate}Hz)")
    
    # Also register gyroscope and magnetometer if enabled
    if hw_config.is_enabled("sensors.gyroscope"):
        _init_icm20948_gyro(sensor)
    if hw_config.is_enabled("sensors.magnetometer"):
        _init_icm20948_magnetometer(sensor)
    
    return sensor


def _init_mpu6050(i2c_bus, address):
    """Initialize MPU-6050/GY-521 6DOF IMU (accelerometer + gyro)"""
    import adafruit_mpu6050
    
    sensor = adafruit_mpu6050.MPU6050(i2c_bus, address=address)
    
    # Configure accelerometer range
    accel_range = hw_config.get_int("sensors.accelerometer.range", 4)
    if accel_range == 2:
        sensor.accelerometer_range = adafruit_mpu6050.Range.RANGE_2_G
    elif accel_range == 4:
        sensor.accelerometer_range = adafruit_mpu6050.Range.RANGE_4_G
    elif accel_range == 8:
        sensor.accelerometer_range = adafruit_mpu6050.Range.RANGE_8_G
    elif accel_range == 16:
        sensor.accelerometer_range = adafruit_mpu6050.Range.RANGE_16_G
    
    # Configure sample rate (MPU6050 has fixed rates)
    sample_rate = hw_config.get_int("sensors.accelerometer.sample_rate", 100)
    if sample_rate <= 5:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_5_HZ
    elif sample_rate <= 10:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_10_HZ
    elif sample_rate <= 21:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_21_HZ
    elif sample_rate <= 44:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_44_HZ
    elif sample_rate <= 94:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_94_HZ
    elif sample_rate <= 184:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_184_HZ
    else:
        sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_260_HZ
    
    _sensor_manager.register('accelerometer', sensor)
    _sensor_manager.register('mpu6050', sensor)
    _sensor_manager.register('imu', sensor)
    print(f"✓ MPU-6050 initialized (±{accel_range}g @ {sample_rate}Hz)")
    
    # Also register as gyroscope if enabled
    if hw_config.is_enabled("sensors.gyroscope"):
        _init_mpu6050_gyro(sensor)
    
    return sensor


# =============================================================================
# Gyroscope Support
# =============================================================================

def init_gyroscope(i2c_bus):
    """
    Initialize gyroscope (usually part of IMU)
    
    Note: Many gyroscopes are initialized as part of IMU initialization.
    This function handles standalone gyroscope initialization or returns
    the gyroscope portion of an already-initialized IMU.
    
    Args:
        i2c_bus: I2C bus object
    
    Returns:
        Gyroscope object or None
    """
    if not hw_config.is_enabled("sensors.gyroscope"):
        print("[Gyro] Disabled in config")
        return None
    
    # Check if gyro was already initialized as part of IMU
    existing_gyro = _sensor_manager.get('gyroscope')
    if existing_gyro:
        print("[Gyro] Already initialized as part of IMU")
        return existing_gyro
    
    # If not, check sensor type and initialize
    gyro_type = hw_config.get("sensors.gyroscope.type", "").upper()
    
    # If no type specified, check accelerometer type (likely IMU)
    if not gyro_type:
        accel_type = hw_config.get("sensors.accelerometer.type", "").upper()
        if accel_type in ["LSM6DSOX", "ICM20948", "ICM-20948", "MPU6050", "MPU-6050", "GY-521"]:
            gyro_type = accel_type
    
    if not gyro_type:
        print("[Gyro] No gyroscope type specified")
        return None
    
    print(f"[Gyro] Gyroscope is part of IMU, should be initialized with accelerometer")
    return None


def _init_lsm6dsox_gyro(sensor):
    """Configure gyroscope portion of LSM6DSOX"""
    import adafruit_lsm6ds
    
    # Configure gyroscope range
    gyro_range = hw_config.get_int("sensors.gyroscope.range", 250)
    if gyro_range == 125:
        sensor.gyro_range = adafruit_lsm6ds.GyroRange.RANGE_125_DPS
    elif gyro_range == 250:
        sensor.gyro_range = adafruit_lsm6ds.GyroRange.RANGE_250_DPS
    elif gyro_range == 500:
        sensor.gyro_range = adafruit_lsm6ds.GyroRange.RANGE_500_DPS
    elif gyro_range == 1000:
        sensor.gyro_range = adafruit_lsm6ds.GyroRange.RANGE_1000_DPS
    elif gyro_range == 2000:
        sensor.gyro_range = adafruit_lsm6ds.GyroRange.RANGE_2000_DPS
    
    # Configure sample rate
    sample_rate = hw_config.get_int("sensors.gyroscope.sample_rate", 104)
    if sample_rate <= 12:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_12_5_HZ
    elif sample_rate <= 26:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_26_HZ
    elif sample_rate <= 52:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_52_HZ
    elif sample_rate <= 104:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_104_HZ
    elif sample_rate <= 208:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_208_HZ
    elif sample_rate <= 416:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_416_HZ
    else:
        sensor.gyro_data_rate = adafruit_lsm6ds.Rate.RATE_833_HZ
    
    _sensor_manager.register('gyroscope', sensor)
    print(f"  ✓ Gyroscope configured (±{gyro_range}°/s @ {sample_rate}Hz)")


def _init_icm20948_gyro(sensor):
    """Configure gyroscope portion of ICM-20948"""
    import adafruit_icm20x
    
    # Configure gyroscope range
    gyro_range = hw_config.get_int("sensors.gyroscope.range", 250)
    if gyro_range == 250:
        sensor.gyro_range = adafruit_icm20x.GyroRange.RANGE_250_DPS
    elif gyro_range == 500:
        sensor.gyro_range = adafruit_icm20x.GyroRange.RANGE_500_DPS
    elif gyro_range == 1000:
        sensor.gyro_range = adafruit_icm20x.GyroRange.RANGE_1000_DPS
    elif gyro_range == 2000:
        sensor.gyro_range = adafruit_icm20x.GyroRange.RANGE_2000_DPS
    
    # Configure sample rate
    sample_rate = hw_config.get_int("sensors.gyroscope.sample_rate", 100)
    if sample_rate <= 17:
        sensor.gyro_data_rate_divisor = 64
    elif sample_rate <= 34:
        sensor.gyro_data_rate_divisor = 32
    elif sample_rate <= 68:
        sensor.gyro_data_rate_divisor = 16
    elif sample_rate <= 136:
        sensor.gyro_data_rate_divisor = 8
    elif sample_rate <= 273:
        sensor.gyro_data_rate_divisor = 4
    else:
        sensor.gyro_data_rate_divisor = 2
    
    _sensor_manager.register('gyroscope', sensor)
    print(f"  ✓ Gyroscope configured (±{gyro_range}°/s @ {sample_rate}Hz)")


def _init_mpu6050_gyro(sensor):
    """Configure gyroscope portion of MPU-6050"""
    import adafruit_mpu6050
    
    # Configure gyroscope range
    gyro_range = hw_config.get_int("sensors.gyroscope.range", 250)
    if gyro_range == 250:
        sensor.gyro_range = adafruit_mpu6050.GyroRange.RANGE_250_DPS
    elif gyro_range == 500:
        sensor.gyro_range = adafruit_mpu6050.GyroRange.RANGE_500_DPS
    elif gyro_range == 1000:
        sensor.gyro_range = adafruit_mpu6050.GyroRange.RANGE_1000_DPS
    elif gyro_range == 2000:
        sensor.gyro_range = adafruit_mpu6050.GyroRange.RANGE_2000_DPS
    
    _sensor_manager.register('gyroscope', sensor)
    print(f"  ✓ Gyroscope configured (±{gyro_range}°/s)")


# =============================================================================
# Magnetometer Support
# =============================================================================

def init_magnetometer(i2c_bus):
    """
    Initialize magnetometer
    
    Supported sensors:
    - ICM-20948 (I2C) - 9DOF IMU (mag is part of chip)
    - LIS3MDL (I2C) - Standalone magnetometer
    
    Args:
        i2c_bus: I2C bus object
    
    Returns:
        Magnetometer object or None
    """
    if not hw_config.is_enabled("sensors.magnetometer"):
        print("[Mag] Disabled in config")
        return None
    
    if not i2c_bus:
        print("[Mag] No I2C bus available")
        return None
    
    # Check if magnetometer was already initialized as part of IMU
    existing_mag = _sensor_manager.get('magnetometer')
    if existing_mag:
        print("[Mag] Already initialized as part of IMU")
        return existing_mag
    
    mag_type = hw_config.get("sensors.magnetometer.type", "LIS3MDL").upper()
    mag_addr = hw_config.get_int("sensors.magnetometer.address", 0x1C)
    
    try:
        if mag_type == "LIS3MDL":
            return _init_lis3mdl(i2c_bus, mag_addr)
        elif mag_type == "ICM20948" or mag_type == "ICM-20948":
            print("[Mag] ICM-20948 magnetometer is initialized with IMU")
            return None
        else:
            print(f"[Mag] Unsupported type: {mag_type}")
            return None
            
    except Exception as e:
        print(f"✗ Magnetometer error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _init_lis3mdl(i2c_bus, address):
    """Initialize LIS3MDL magnetometer"""
    import adafruit_lis3mdl
    
    sensor = adafruit_lis3mdl.LIS3MDL(i2c_bus, address=address)
    
    # Configure range
    mag_range = hw_config.get_int("sensors.magnetometer.range", 4)
    if mag_range == 4:
        sensor.range = adafruit_lis3mdl.RANGE_4_GAUSS
    elif mag_range == 8:
        sensor.range = adafruit_lis3mdl.RANGE_8_GAUSS
    elif mag_range == 12:
        sensor.range = adafruit_lis3mdl.RANGE_12_GAUSS
    elif mag_range == 16:
        sensor.range = adafruit_lis3mdl.RANGE_16_GAUSS
    
    # Configure data rate
    data_rate = hw_config.get_int("sensors.magnetometer.sample_rate", 80)
    if data_rate <= 0.625:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_0_625_HZ
    elif data_rate <= 1.25:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_1_25_HZ
    elif data_rate <= 2.5:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_2_5_HZ
    elif data_rate <= 5:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_5_HZ
    elif data_rate <= 10:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_10_HZ
    elif data_rate <= 20:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_20_HZ
    elif data_rate <= 40:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_40_HZ
    else:
        sensor.data_rate = adafruit_lis3mdl.DATARATE_80_HZ
    
    # Configure performance mode
    sensor.performance_mode = adafruit_lis3mdl.PERFORMANCEMODE_ULTRAHIGH
    
    _sensor_manager.register('magnetometer', sensor)
    _sensor_manager.register('lis3mdl', sensor)
    print(f"✓ LIS3MDL initialized (±{mag_range}G @ {data_rate}Hz)")
    return sensor


def _init_icm20948_magnetometer(sensor):
    """Configure magnetometer portion of ICM-20948"""
    # ICM-20948 magnetometer is auto-configured when the chip initializes
    # Just register it
    _sensor_manager.register('magnetometer', sensor)
    print(f"  ✓ Magnetometer configured (ICM-20948 AK09916)")


# =============================================================================
# GPS Support
# =============================================================================

def init_gps(i2c_bus=None):
    """
    Initialize GPS module
    
    Supported sensors:
    - ATGM336H (UART)
    - PA1010D (I2C or UART)
    
    Args:
        i2c_bus: I2C bus (required for PA1010D on I2C)
    
    Returns:
        tuple: (GPS object, UART object) or (None, None)
    """
    if not hw_config.is_enabled("gps"):
        print("[GPS] Disabled in config")
        return None, None
    
    gps_type = hw_config.get("gps.type", "ATGM336H").upper()
    gps_interface = hw_config.get("gps.interface", "uart_gps")
    
    try:
        if "PA1010" in gps_type:
            # PA1010D can use I2C or UART
            if "i2c" in gps_interface.lower():
                return _init_pa1010d_i2c(i2c_bus)
            else:
                return _init_pa1010d_uart()
        else:
            # ATGM336H and others use UART
            return _init_gps_uart()
            
    except Exception as e:
        print(f"✗ GPS error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def _init_gps_uart():
    """Initialize GPS via UART (ATGM336H, PA1010D UART mode)"""
    import adafruit_gps
    
    # Get UART interface config
    uart_name = hw_config.get("gps.interface", "uart_gps")
    uart_config = hw_config.get_interface_pins(uart_name)
    
    if not uart_config:
        print(f"[GPS] UART interface '{uart_name}' not found")
        return None, None
    
    tx_pin = uart_config.get('tx')
    rx_pin = uart_config.get('rx')
    baudrate = uart_config.get('baudrate', 9600)
    timeout = uart_config.get('timeout', 10)
    
    if not tx_pin or not rx_pin:
        print(f"[GPS] Invalid UART pins: TX={tx_pin}, RX={rx_pin}")
        return None, None
    
    # Initialize UART
    gps_uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate, timeout=timeout)
    gps = adafruit_gps.GPS(gps_uart, debug=False)
    
    # Configure NMEA sentences
    sentences = hw_config.get("gps.sentences", "0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
    gps.send_command(f'PMTK314,{sentences}'.encode())
    
    # Configure update rate (milliseconds)
    update_rate = hw_config.get_int("gps.update_rate", 1000)
    gps.send_command(f'PMTK220,{update_rate}'.encode())
    
    _sensor_manager.register('gps', gps)
    _sensor_manager.register('gps_uart', gps_uart)
    
    gps_type = hw_config.get("gps.type", "GPS")
    print(f"✓ {gps_type} initialized (UART @ {update_rate}ms)")
    return gps, gps_uart


def _init_pa1010d_uart():
    """Initialize PA1010D via UART"""
    return _init_gps_uart()


def _init_pa1010d_i2c(i2c_bus):
    """Initialize PA1010D via I2C"""
    import adafruit_gps
    
    if not i2c_bus:
        print("[GPS] No I2C bus available for PA1010D")
        return None, None
    
    gps_addr = hw_config.get_int("gps.address", 0x10)
    
    # Initialize GPS on I2C
    gps = adafruit_gps.GPS_GtopI2C(i2c_bus, address=gps_addr, debug=False)
    
    # Configure NMEA sentences
    sentences = hw_config.get("gps.sentences", "0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
    gps.send_command(f'PMTK314,{sentences}'.encode())
    
    # Configure update rate
    update_rate = hw_config.get_int("gps.update_rate", 1000)
    gps.send_command(f'PMTK220,{update_rate}'.encode())
    
    _sensor_manager.register('gps', gps)
    
    print(f"✓ PA1010D initialized (I2C @ {update_rate}ms)")
    return gps, None


# =============================================================================
# Sensor Initialization (Main Entry Point)
# =============================================================================

def init_sensors(i2c_bus=None):
    """
    Initialize all enabled sensors
    
    Args:
        i2c_bus: I2C bus for sensors (if None, I2C sensors won't init)
    
    Returns:
        dict: Dictionary of initialized sensors
    """
    print("\n" + "="*60)
    print("Initializing Sensors...")
    print("="*60)
    
    sensors = {}
    
    # Initialize accelerometer (may also initialize gyro/mag if IMU)
    if i2c_bus:
        accel = init_accelerometer(i2c_bus)
        if accel:
            sensors['accelerometer'] = accel
            # Add backward compat aliases
            if _sensor_manager.get('lis3dh'):
                sensors['lis3dh'] = accel
            if _sensor_manager.get('imu'):
                sensors['imu'] = accel
    else:
        if hw_config.is_enabled("sensors.accelerometer"):
            print("[Accel] Skipped - no I2C bus provided")
    
    # Initialize gyroscope (if standalone)
    if i2c_bus:
        gyro = init_gyroscope(i2c_bus)
        if gyro and gyro not in sensors.values():
            sensors['gyroscope'] = gyro
    
    # Initialize magnetometer (if standalone)
    if i2c_bus:
        mag = init_magnetometer(i2c_bus)
        if mag and mag not in sensors.values():
            sensors['magnetometer'] = mag
    
    # Initialize GPS (uses dedicated UART or I2C)
    gps, gps_uart = init_gps(i2c_bus)
    if gps:
        sensors['gps'] = gps
        if gps_uart:
            sensors['gps_uart'] = gps_uart
    
    # Summary
    print("\n✓ Sensors initialized")
    sensor_types = []
    if 'accelerometer' in sensors:
        sensor_types.append(f"Accelerometer: {hw_config.get('sensors.accelerometer.type', 'Unknown')}")
    if 'gyroscope' in _sensor_manager.list():
        sensor_types.append(f"Gyroscope: {hw_config.get('sensors.gyroscope.type', 'IMU')}")
    if 'magnetometer' in _sensor_manager.list():
        sensor_types.append(f"Magnetometer: {hw_config.get('sensors.magnetometer.type', 'Unknown')}")
    if 'gps' in sensors:
        sensor_types.append(f"GPS: {hw_config.get('gps.type', 'Unknown')}")
    
    print(f"  Active sensors: {len(sensor_types)}")
    for sensor_type in sensor_types:
        print(f"  {sensor_type}")
    
    return sensors


# =============================================================================
# Convenience Functions
# =============================================================================

def get_sensor(name):
    """Get sensor by name from global registry"""
    return _sensor_manager.get(name)


def list_sensors():
    """List all registered sensors"""
    return _sensor_manager.list()


# =============================================================================
# Direct Exports (Backward Compatibility)
# =============================================================================

# These will be set by init_sensors() and available for import
lis3dh = None
gps = None
gps_uart = None
