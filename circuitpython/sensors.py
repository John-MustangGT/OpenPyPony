"""
sensors.py - Hardware Interfaces and Implementations

Defines base interfaces and concrete implementations for all sensors.
Note: CircuitPython doesn't have 'abc' module, so we use simple base classes.
"""

import time


# =============================================================================
# Base Interfaces (not abstract, but serve as contracts)
# =============================================================================

class AccelerometerInterface:
    """Base interface for accelerometers"""
    
    def read(self):
        """
        Read acceleration data
        
        Returns:
            tuple: (x, y, z) in m/s² or None if read fails
        """
        raise NotImplementedError("Subclass must implement read()")
    
    def configure(self, range_g=2, rate_hz=100):
        """
        Configure accelerometer
        
        Args:
            range_g: Measurement range in g (2, 4, 8, 16)
            rate_hz: Sample rate in Hz
        """
        raise NotImplementedError("Subclass must implement configure()")
    
    def get_gforce(self):
        """
        Get G-force vector
        
        Returns:
            tuple: (gx, gy, gz) in g units
        """
        raise NotImplementedError("Subclass must implement get_gforce()")


class GPSInterface:
    """Base interface for GPS modules"""
    
    def update(self):
        """
        Update GPS data (call frequently)
        
        Returns:
            bool: True if new valid data available
        """
        raise NotImplementedError("Subclass must implement update()")
    
    def has_fix(self):
        """
        Check if GPS has valid fix
        
        Returns:
            bool: True if valid fix
        """
        raise NotImplementedError("Subclass must implement has_fix()")
    
    def get_time(self):
        """
        Get GPS time
        
        Returns:
            struct_time or None if no fix
        """
        raise NotImplementedError("Subclass must implement get_time()")
    
    def get_position(self):
        """
        Get GPS position
        
        Returns:
            tuple: (latitude, longitude, altitude) or (None, None, None)
        """
        raise NotImplementedError("Subclass must implement get_position()")
    
    def get_speed(self):
        """
        Get GPS speed
        
        Returns:
            float: Speed in m/s or None
        """
        raise NotImplementedError("Subclass must implement get_speed()")
    
    def get_satellites(self):
        """
        Get number of satellites
        
        Returns:
            int: Number of satellites in use
        """
        raise NotImplementedError("Subclass must implement get_satellites()")


class RTCInterface:
    """Base interface for Real-Time Clocks"""
    
    def get_time(self):
        """
        Get current time from RTC
        
        Returns:
            struct_time
        """
        raise NotImplementedError("Subclass must implement get_time()")
    
    def set_time(self, datetime):
        """
        Set RTC time
        
        Args:
            datetime: struct_time or datetime object
        """
        raise NotImplementedError("Subclass must implement set_time()")


class DisplayInterface:
    """Base interface for displays"""
    
    def clear(self):
        """Clear display"""
        raise NotImplementedError("Subclass must implement clear()")
    
    def show(self):
        """Update display"""
        raise NotImplementedError("Subclass must implement show()")
    
    def text(self, string, x, y, color=1):
        """
        Draw text
        
        Args:
            string: Text to display
            x: X coordinate
            y: Y coordinate
            color: Color (1=white, 0=black for monochrome)
        """
        raise NotImplementedError("Subclass must implement text()")


class StorageInterface:
    """Base interface for storage (SD card)"""
    
    def mount(self, path='/sd'):
        """
        Mount storage
        
        Args:
            path: Mount point path
            
        Returns:
            bool: True if successful
        """
        raise NotImplementedError("Subclass must implement mount()")
    
    def is_mounted(self):
        """Check if storage is mounted"""
        raise NotImplementedError("Subclass must implement is_mounted()")
    
    def get_free_space(self):
        """
        Get free space
        
        Returns:
            int: Free bytes
        """
        raise NotImplementedError("Subclass must implement get_free_space()")


# =============================================================================
# Concrete Implementations
# =============================================================================

class LIS3DH(AccelerometerInterface):
    """LIS3DH 3-axis accelerometer implementation"""
    
    def __init__(self, i2c, address=0x18):
        """
        Initialize LIS3DH
        
        Args:
            i2c: I2C bus object
            address: I2C address (0x18 or 0x19)
        """
        import adafruit_lis3dh
        
        self.sensor = adafruit_lis3dh.LIS3DH_I2C(i2c, address=address)
        self.sensor.range = adafruit_lis3dh.RANGE_2_G
        self.sensor.data_rate = adafruit_lis3dh.DATARATE_100_HZ
        self._last_reading = (0.0, 0.0, 0.0)
        
        print(f"[LIS3DH] Initialized at 0x{address:02X}")
    
    def read(self):
        """Read raw acceleration in m/s²"""
        try:
            x, y, z = self.sensor.acceleration
            self._last_reading = (x, y, z)
            return (x, y, z)
        except Exception as e:
            print(f"[LIS3DH] Read error: {e}")
            return self._last_reading
    
    def configure(self, range_g=2, rate_hz=100):
        """Configure sensor range and data rate"""
        import adafruit_lis3dh
        
        # Set range
        range_map = {
            2: adafruit_lis3dh.RANGE_2_G,
            4: adafruit_lis3dh.RANGE_4_G,
            8: adafruit_lis3dh.RANGE_8_G,
            16: adafruit_lis3dh.RANGE_16_G
        }
        
        if range_g in range_map:
            self.sensor.range = range_map[range_g]
        
        # Set data rate (closest match)
        rate_map = {
            1: adafruit_lis3dh.DATARATE_1_HZ,
            10: adafruit_lis3dh.DATARATE_10_HZ,
            25: adafruit_lis3dh.DATARATE_25_HZ,
            50: adafruit_lis3dh.DATARATE_50_HZ,
            100: adafruit_lis3dh.DATARATE_100_HZ,
            200: adafruit_lis3dh.DATARATE_200_HZ,
            400: adafruit_lis3dh.DATARATE_400_HZ
        }
        
        # Find closest rate
        closest = min(rate_map.keys(), key=lambda x: abs(x - rate_hz))
        self.sensor.data_rate = rate_map[closest]
        
        print(f"[LIS3DH] Configured: ±{range_g}g, {closest}Hz")
    
    def get_gforce(self):
        """Convert acceleration to g-force"""
        x, y, z = self.read()
        return (x / 9.81, y / 9.81, z / 9.81)


class ATGM336H(GPSInterface):
    """ATGM336H GPS module implementation"""
    
    def __init__(self, uart):
        """
        Initialize ATGM336H GPS
        
        Args:
            uart: UART object connected to GPS module
        """
        import adafruit_gps
        
        self.gps = adafruit_gps.GPS(uart, debug=False)
        
        # Configure GPS
        self.gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')  # RMC + GGA
        self.gps.send_command(b'PMTK220,1000')  # 1Hz update rate
        
        self._last_update = 0
        
        print("[ATGM336H] Initialized")
    
    def update(self):
        """
        Update GPS data
        
        Returns:
            bool: True if new valid data received
        """
        # Update GPS data
        self.gps.update()
        
        # Check if we have new data
        if self.gps.has_fix:
            current_time = time.monotonic()
            if current_time - self._last_update >= 0.1:  # Throttle updates
                self._last_update = current_time
                return True
        
        return False
    
    def has_fix(self):
        """Check if GPS has valid fix"""
        return self.gps.has_fix
    
    def get_time(self):
        """Get GPS time as struct_time"""
        if not self.gps.has_fix:
            return None
        return self.gps.timestamp_utc
    
    def get_position(self):
        """Get GPS position (lat, lon, alt)"""
        if not self.gps.has_fix:
            return (None, None, None)
        
        return (
            self.gps.latitude,
            self.gps.longitude,
            self.gps.altitude_m
        )
    
    def get_speed(self):
        """Get GPS speed in m/s"""
        if not self.gps.has_fix:
            return None
        
        # Convert knots to m/s
        if self.gps.speed_knots is not None:
            return self.gps.speed_knots * 0.514444
        return None
    
    def get_satellites(self):
        """Get number of satellites"""
        return self.gps.satellites or 0
    
    def configure_rate(self, rate_ms=1000):
        """
        Configure GPS update rate
        
        Args:
            rate_ms: Update period in milliseconds (200-10000)
        """
        rate_ms = max(200, min(10000, rate_ms))
        cmd = f'PMTK220,{rate_ms}'.encode()
        self.gps.send_command(cmd)
        print(f"[ATGM336H] Update rate: {rate_ms}ms ({1000/rate_ms:.1f}Hz)")


class PCF8523(RTCInterface):
    """PCF8523 Real-Time Clock implementation"""
    
    def __init__(self, i2c):
        """
        Initialize PCF8523 RTC
        
        Args:
            i2c: I2C bus object
        """
        from adafruit_pcf8523.pcf8523 import PCF8523 as PCF8523_Driver
        
        self.rtc = PCF8523_Driver(i2c)
        
        print("[PCF8523] Initialized")
    
    def get_time(self):
        """Get current time from RTC"""
        return self.rtc.datetime
    
    def set_time(self, datetime):
        """Set RTC time"""
        self.rtc.datetime = datetime
        print(f"[PCF8523] Time set to {datetime}")


class SSD1306(DisplayInterface):
    """SSD1306 OLED display implementation"""
    
    def __init__(self, i2c, width=128, height=64, address=0x3C):
        """
        Initialize SSD1306 OLED
        
        Args:
            i2c: I2C bus object
            width: Display width in pixels
            height: Display height in pixels
            address: I2C address
        """
        import displayio
        import i2cdisplaybus
        import adafruit_displayio_ssd1306
        import terminalio
        from adafruit_display_text import label
        
        # Release any existing displays
        displayio.release_displays()
        
        # Create display
        display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=address)
        self.display = adafruit_displayio_ssd1306.SSD1306(
            display_bus, 
            width=width, 
            height=height
        )
        
        # Create display group
        self.group = displayio.Group()
        self.display.root_group = self.group
        
        # Store references for text rendering
        self.terminalio = terminalio
        self.label_class = label
        self._labels = []
        
        self.width = width
        self.height = height
        
        print(f"[SSD1306] Initialized {width}x{height}")
    
    def clear(self):
        """Clear display"""
        # Remove all items from group
        while len(self.group):
            self.group.pop()
        self._labels = []
    
    def show(self):
        """Update display (auto-updates in CircuitPython)"""
        pass
    
    def text(self, string, x, y, color=1):
        """
        Draw text at position
        
        Args:
            string: Text to display
            x: X coordinate
            y: Y coordinate  
            color: 1 for white, 0 for black
        """
        text_label = self.label_class.Label(
            self.terminalio.FONT,
            text=string,
            color=0xFFFFFF if color else 0x000000,
            x=x,
            y=y
        )
        
        self.group.append(text_label)
        self._labels.append(text_label)
    
    def update_text(self, index, new_text):
        """
        Update existing text label
        
        Args:
            index: Index of label to update
            new_text: New text string
        """
        if 0 <= index < len(self._labels):
            self._labels[index].text = new_text


class SDCard(StorageInterface):
    """SD Card storage implementation"""
    
    def __init__(self, spi, cs_pin):
        """
        Initialize SD card
        
        Args:
            spi: SPI bus object
            cs_pin: Chip select pin
        """
        import sdcardio
        import storage
        
        self.spi = spi
        self.cs_pin = cs_pin
        self.vfs = None
        self.mount_path = None
        self._sdcard = None
        
        print("[SDCard] Initialized")
    
    def mount(self, path='/sd'):
        """Mount SD card"""
        import sdcardio
        import storage
        
        try:
            self._sdcard = sdcardio.SDCard(self.spi, self.cs_pin)
            self.vfs = storage.VfsFat(self._sdcard)
            storage.mount(self.vfs, path)
            self.mount_path = path
            
            print(f"[SDCard] Mounted at {path}")
            return True
            
        except Exception as e:
            print(f"[SDCard] Mount failed: {e}")
            return False
    
    def is_mounted(self):
        """Check if SD card is mounted"""
        return self.vfs is not None and self.mount_path is not None
    
    def get_free_space(self):
        """Get free space in bytes"""
        if not self.is_mounted():
            return 0
        
        import os
        
        try:
            stat = os.statvfs(self.mount_path)
            return stat[0] * stat[3]  # block_size * free_blocks
        except:
            return 0


# =============================================================================
# Null/Stub Implementations (for disabled hardware)
# =============================================================================

class NullAccelerometer(AccelerometerInterface):
    """Stub accelerometer when disabled"""
    
    def read(self):
        return (0.0, 0.0, 9.81)
    
    def configure(self, range_g=2, rate_hz=100):
        pass
    
    def get_gforce(self):
        return (0.0, 0.0, 1.0)


class NullGPS(GPSInterface):
    """Stub GPS when disabled"""
    
    def update(self):
        return False
    
    def has_fix(self):
        return False
    
    def get_time(self):
        return None
    
    def get_position(self):
        return (None, None, None)
    
    def get_speed(self):
        return None
    
    def get_satellites(self):
        return 0


class NullDisplay(DisplayInterface):
    """Stub display when not present"""
    
    def clear(self):
        pass
    
    def show(self):
        pass
    
    def text(self, string, x, y, color=1):
        pass
