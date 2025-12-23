"""
sensors.py - Sensor drivers and management for OpenPonyLogger

Handles all data acquisition sensors:
- Accelerometer (LIS3DH)
- GPS (ATGM336H)
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
# Accelerometer (LIS3DH)
# =============================================================================

def init_accelerometer(i2c_bus):
    """
    Initialize LIS3DH accelerometer
    
    Args:
        i2c_bus: I2C bus object
    
    Returns:
        LIS3DH object or None
    """
    if not hw_config.is_enabled("sensors.accelerometer"):
        print("[Accel] Disabled in config")
        return None
    
    if not i2c_bus:
        print("[Accel] No I2C bus available")
        return None
    
    try:
        import adafruit_lis3dh
        
        accel_type = hw_config.get("sensors.accelerometer.type", "LIS3DH")
        accel_addr = hw_config.get_int("sensors.accelerometer.address", 0x18)
        
        if accel_type.upper() != "LIS3DH":
            print(f"[Accel] Unsupported type: {accel_type}")
            return None
        
        lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c_bus, address=accel_addr)
        
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
        _sensor_manager.register('lis3dh', lis3dh)  # Alias
        print(f"✓ {accel_type} initialized (±{accel_range}g @ {sample_rate}Hz)")
        return lis3dh
        
    except Exception as e:
        print(f"✗ Accelerometer error: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# GPS (ATGM336H)
# =============================================================================

def init_gps():
    """
    Initialize GPS module
    
    Returns:
        tuple: (GPS object, UART object) or (None, None)
    """
    if not hw_config.is_enabled("gps"):
        print("[GPS] Disabled in config")
        return None, None
    
    try:
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
        # Format: GLL,RMC,VTG,GGA,GSA,GSV,Reserved,Reserved,Reserved,Reserved...
        # Default: enable RMC (1) and GGA (3), enable GSV (5) for satellites
        sentences = hw_config.get("gps.sentences", "0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
        gps.send_command(f'PMTK314,{sentences}'.encode())
        
        # Configure update rate (milliseconds)
        update_rate = hw_config.get_int("gps.update_rate", 1000)
        gps.send_command(f'PMTK220,{update_rate}'.encode())
        
        _sensor_manager.register('gps', gps)
        _sensor_manager.register('gps_uart', gps_uart)
        
        gps_type = hw_config.get("gps.type", "ATGM336H")
        print(f"✓ {gps_type} initialized ({update_rate}ms update)")
        return gps, gps_uart
        
    except Exception as e:
        print(f"✗ GPS error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


# =============================================================================
# Sensor Initialization (Main Entry Point)
# =============================================================================

def init_sensors(i2c_bus=None):
    """
    Initialize all enabled sensors
    
    Args:
        i2c_bus: I2C bus for accelerometer (if None, sensors requiring I2C won't init)
    
    Returns:
        dict: Dictionary of initialized sensors
    """
    print("\n" + "="*60)
    print("Initializing Sensors...")
    print("="*60)
    
    sensors = {}
    
    # Initialize accelerometer (requires I2C)
    if i2c_bus:
        accel = init_accelerometer(i2c_bus)
        if accel:
            sensors['accelerometer'] = accel
            sensors['lis3dh'] = accel  # Alias for backward compat
    else:
        if hw_config.is_enabled("sensors.accelerometer"):
            print("[Accel] Skipped - no I2C bus provided")
    
    # Initialize GPS (uses dedicated UART)
    gps, gps_uart = init_gps()
    if gps:
        sensors['gps'] = gps
        sensors['gps_uart'] = gps_uart
    
    # Summary
    print("\n✓ Sensors initialized")
    print(f"  Active sensors: {len([k for k in sensors.keys() if k in ['accelerometer', 'gps']])}")
    if 'accelerometer' in sensors:
        print(f"  Accelerometer: {hw_config.get('sensors.accelerometer.type', 'Unknown')}")
    if 'gps' in sensors:
        print(f"  GPS: {hw_config.get('gps.type', 'Unknown')}")
    
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
