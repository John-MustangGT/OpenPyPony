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


class GyroscopeInterface:
    """Base interface for gyroscopes"""

    def read(self):
        """
        Read gyroscope data

        Returns:
            tuple: (x, y, z) in degrees/second or None if read fails
        """
        raise NotImplementedError("Subclass must implement read()")

    def configure(self, range_dps=250, rate_hz=100):
        """
        Configure gyroscope

        Args:
            range_dps: Measurement range in degrees/second (250, 500, 1000, 2000)
            rate_hz: Sample rate in Hz
        """
        raise NotImplementedError("Subclass must implement configure()")

    def get_rotation(self):
        """
        Get rotation rates

        Returns:
            tuple: (rx, ry, rz) in degrees/second
        """
        raise NotImplementedError("Subclass must implement get_rotation()")


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

    def get_fix_quality(self):
        """
        Get GPS fix quality

        Returns:
            int: Fix quality (0=no fix, 1=GPS fix, 2=DGPS fix)
        """
        raise NotImplementedError("Subclass must implement get_fix_quality()")

    def get_fix_type(self):
        """
        Get GPS fix type (2D/3D)

        Returns:
            str: Fix type ('No Fix', '2D', '3D')
        """
        raise NotImplementedError("Subclass must implement get_fix_type()")

    def get_hdop(self):
        """
        Get Horizontal Dilution of Precision

        Returns:
            float: HDOP value (lower is better)
        """
        raise NotImplementedError("Subclass must implement get_hdop()")


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


class WebServerInterface:
    """Base interface for web server (ESP-01)"""

    def reset(self):
        """
        Reset the ESP module

        Returns:
            bool: True if successful
        """
        raise NotImplementedError("Subclass must implement reset()")

    def is_ready(self):
        """
        Check if ESP is ready to serve

        Returns:
            bool: True if serving
        """
        raise NotImplementedError("Subclass must implement is_ready()")

    def send_config(self, config_dict):
        """
        Send configuration to ESP

        Args:
            config_dict: Configuration parameters (mode, ssid, password, etc.)

        Returns:
            bool: True if accepted
        """
        raise NotImplementedError("Subclass must implement send_config()")

    def update(self):
        """
        Process incoming requests from ESP

        Should be called frequently in main loop

        Returns:
            tuple: (request_type, request_data) or (None, None)
        """
        raise NotImplementedError("Subclass must implement update()")

    def stream_telemetry(self, data):
        """
        Stream telemetry data to websockets

        Args:
            data: Telemetry data dict to send

        Returns:
            bool: True if sent
        """
        raise NotImplementedError("Subclass must implement stream_telemetry()")

    def serve_file(self, filename, content):
        """
        Serve file content in response to page request

        Args:
            filename: Requested file name
            content: File content (can be generator for streaming)

        Returns:
            bool: True if sent
        """
        raise NotImplementedError("Subclass must implement serve_file()")

    def get_status(self):
        """
        Get server status

        Returns:
            dict: Status info (clients connected, uptime, etc.)
        """
        raise NotImplementedError("Subclass must implement get_status()")


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


class MPU6050(AccelerometerInterface, GyroscopeInterface):
    """MPU6050/GY-521 6-axis IMU (accelerometer + gyroscope) implementation"""

    def __init__(self, i2c, address=0x68):
        """
        Initialize MPU6050

        Args:
            i2c: I2C bus object
            address: I2C address (0x68 or 0x69, default 0x68)
        """
        try:
            import adafruit_mpu6050
        except ImportError:
            raise ImportError(
                "MPU6050 library not found!\n"
                "Install adafruit_mpu6050 library to /lib/:\n"
                "1. Download CircuitPython bundle from circuitpython.org/libraries\n"
                "2. Copy 'adafruit_mpu6050.mpy' to /lib/\n"
                "3. Copy 'adafruit_register/' folder to /lib/\n"
                "4. Copy 'adafruit_bus_device/' folder to /lib/"
            )

        self.sensor = adafruit_mpu6050.MPU6050(i2c, address=address)

        # Configure defaults
        self.sensor.accelerometer_range = adafruit_mpu6050.Range.RANGE_2_G
        self.sensor.gyro_range = adafruit_mpu6050.GyroRange.RANGE_250_DPS
        self.sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_21_HZ

        self._last_accel = (0.0, 0.0, 0.0)
        self._last_gyro = (0.0, 0.0, 0.0)

        print(f"[MPU6050] Initialized at 0x{address:02X}")

    def read(self):
        """Read raw acceleration in m/s²"""
        try:
            x, y, z = self.sensor.acceleration
            self._last_accel = (x, y, z)
            return (x, y, z)
        except Exception as e:
            print(f"[MPU6050] Accel read error: {e}")
            return self._last_accel

    def configure(self, range_g=2, rate_hz=100):
        """Configure accelerometer range"""
        import adafruit_mpu6050

        # Set accelerometer range
        range_map = {
            2: adafruit_mpu6050.Range.RANGE_2_G,
            4: adafruit_mpu6050.Range.RANGE_4_G,
            8: adafruit_mpu6050.Range.RANGE_8_G,
            16: adafruit_mpu6050.Range.RANGE_16_G
        }

        if range_g in range_map:
            self.sensor.accelerometer_range = range_map[range_g]

        # Set filter bandwidth based on rate
        if rate_hz >= 200:
            self.sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_260_HZ
        elif rate_hz >= 100:
            self.sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_94_HZ
        elif rate_hz >= 50:
            self.sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_44_HZ
        else:
            self.sensor.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_21_HZ

        print(f"[MPU6050] Accel configured: ±{range_g}g")

    def get_gforce(self):
        """Convert acceleration to g-force"""
        x, y, z = self.read()
        return (x / 9.81, y / 9.81, z / 9.81)

    def read_gyro(self):
        """Read raw gyroscope data in degrees/second"""
        try:
            x, y, z = self.sensor.gyro
            self._last_gyro = (x, y, z)
            return (x, y, z)
        except Exception as e:
            print(f"[MPU6050] Gyro read error: {e}")
            return self._last_gyro

    def configure_gyro(self, range_dps=250):
        """Configure gyroscope range"""
        import adafruit_mpu6050

        # Set gyroscope range
        range_map = {
            250: adafruit_mpu6050.GyroRange.RANGE_250_DPS,
            500: adafruit_mpu6050.GyroRange.RANGE_500_DPS,
            1000: adafruit_mpu6050.GyroRange.RANGE_1000_DPS,
            2000: adafruit_mpu6050.GyroRange.RANGE_2000_DPS
        }

        if range_dps in range_map:
            self.sensor.gyro_range = range_map[range_dps]

        print(f"[MPU6050] Gyro configured: ±{range_dps}°/s")

    def get_rotation(self):
        """Get rotation rates in degrees/second"""
        return self.read_gyro()

    def get_temperature(self):
        """Get temperature in Celsius"""
        try:
            return self.sensor.temperature
        except Exception as e:
            print(f"[MPU6050] Temperature read error: {e}")
            return 0.0


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
        # Update GPS data (with error handling for malformed NMEA sentences)
        try:
            self.gps.update()
        except (ValueError, RuntimeError) as e:
            # GPS occasionally sends malformed NMEA data - ignore and continue
            # This prevents crashes during track sessions from corrupted sentences
            return False

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

    def get_fix_quality(self):
        """
        Get GPS fix quality

        Returns:
            int: Fix quality (0=no fix, 1=GPS fix, 2=DGPS fix)
        """
        return self.gps.fix_quality or 0

    def get_fix_type(self):
        """
        Get GPS fix type (2D/3D)

        Returns:
            str: Fix type ('No Fix', '2D', '3D')
        """
        if not self.gps.has_fix:
            return 'No Fix'

        # fix_quality_3d: 1=no fix, 2=2D fix, 3=3D fix
        fix_3d = self.gps.fix_quality_3d or 1
        if fix_3d == 3:
            return '3D'
        elif fix_3d == 2:
            return '2D'
        else:
            return 'No Fix'

    def get_hdop(self):
        """
        Get Horizontal Dilution of Precision

        Returns:
            float: HDOP value (lower is better, <1=excellent, 1-2=good, 2-5=moderate, 5-10=fair, >10=poor)
        """
        return self.gps.hdop

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
        # Validate datetime (GPS sometimes has time but not date)
        year = datetime.tm_year
        month = datetime.tm_mon
        day = datetime.tm_mday

        if year < 2000 or month < 1 or month > 12 or day < 1 or day > 31:
            print(f"[PCF8523] Invalid datetime from GPS: {year:04d}-{month:02d}-{day:02d}")
            print(f"[PCF8523] GPS may have time lock but not date lock yet - waiting...")
            return

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

    def show_splash(self, status="Booting..."):
        """
        Show OpenPony Logger splash screen

        Args:
            status: Status message to display
        """
        self.clear()

        # Title "OpenPony" (large, centered)
        title1 = self.label_class.Label(
            self.terminalio.FONT,
            text="OpenPony",
            color=0xFFFFFF,
            x=20,
            y=8,
            scale=2
        )
        self.group.append(title1)

        # Subtitle "Logger"
        title2 = self.label_class.Label(
            self.terminalio.FONT,
            text="Logger",
            color=0xFFFFFF,
            x=30,
            y=26
        )
        self.group.append(title2)

        # Status message
        status_label = self.label_class.Label(
            self.terminalio.FONT,
            text=status,
            color=0xFFFFFF,
            x=5,
            y=40
        )
        self.group.append(status_label)
        self._labels.append(status_label)  # Store for updates

        # Copyright
        copyright_label = self.label_class.Label(
            self.terminalio.FONT,
            text="(c) 2025",
            color=0xFFFFFF,
            x=40,
            y=56
        )
        self.group.append(copyright_label)

    def update_splash_status(self, status):
        """
        Update splash screen status message

        Args:
            status: New status message
        """
        if self._labels:
            self._labels[0].text = status

    def setup_main_display(self):
        """
        Setup main display with persistent labels

        Creates labels for:
        - Line 1: Status/GPS info
        - Line 2: Satellites
        - Line 3: Speed
        - Line 4: G-forces

        Returns:
            None (labels stored in self._labels for updating)
        """
        self.clear()

        # Line 1: Status (y=8)
        line1 = self.label_class.Label(
            self.terminalio.FONT,
            text="Initializing...",
            color=0xFFFFFF,
            x=0,
            y=8
        )
        self.group.append(line1)
        self._labels.append(line1)

        # Line 2: Satellites (y=20)
        line2 = self.label_class.Label(
            self.terminalio.FONT,
            text="Sats: --",
            color=0xFFFFFF,
            x=0,
            y=20
        )
        self.group.append(line2)
        self._labels.append(line2)

        # Line 3: Speed (y=32)
        line3 = self.label_class.Label(
            self.terminalio.FONT,
            text="Speed: -- m/s",
            color=0xFFFFFF,
            x=0,
            y=32
        )
        self.group.append(line3)
        self._labels.append(line3)

        # Line 4: G-forces (y=44)
        line4 = self.label_class.Label(
            self.terminalio.FONT,
            text="G: -- -- --",
            color=0xFFFFFF,
            x=0,
            y=44
        )
        self.group.append(line4)
        self._labels.append(line4)

        # Line 5: Session info (y=56)
        line5 = self.label_class.Label(
            self.terminalio.FONT,
            text="Ready",
            color=0xFFFFFF,
            x=0,
            y=56
        )
        self.group.append(line5)
        self._labels.append(line5)

    def update_main_display(self, gps_data, accel_data, session_info=None):
        """
        Update main display labels

        Args:
            gps_data: dict with GPS data
            accel_data: dict with accelerometer data
            session_info: Optional dict with session info (name, duration)
        """
        if len(self._labels) < 5:
            return  # Not initialized

        # Line 1: GPS status
        if gps_data.get('satellites', 0) > 0:
            lat = gps_data.get('lat', 0.0)
            lon = gps_data.get('lon', 0.0)
            self._labels[0].text = f"GPS: {lat:+.2f},{lon:+.2f}"
        else:
            self._labels[0].text = "GPS: No Fix"

        # Line 2: Satellites + Fix Type + HDOP
        sats = gps_data.get('satellites', 0)
        fix_type = gps_data.get('fix_type', 'No Fix')
        hdop = gps_data.get('hdop', 99.9)
        if hdop and hdop < 99:
            self._labels[1].text = f"{sats}sat {fix_type} H:{hdop:.1f}"
        else:
            self._labels[1].text = f"{sats}sat {fix_type}"

        # Line 3: Speed
        speed = gps_data.get('speed', 0.0) * 2.237
        self._labels[2].text = f"Speed: {speed:2.1f} MPH"

        # Line 4: G-forces
        gx = accel_data.get('gx', 0.0)
        gy = accel_data.get('gy', 0.0)
        gz = accel_data.get('gz', 1.0)
        self._labels[3].text = f"G:{gx:+.1f} {gy:+.1f} {gz:+.1f}"

        # Line 5: Session info
        if session_info:
            name = session_info.get('name', 'Log')
            duration = session_info.get('duration', 0)
            mins = int(duration / 60)
            secs = int(duration % 60)
            self._labels[4].text = f"{name} {mins:02d}:{secs:02d}"
        else:
            self._labels[4].text = "Ready"


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


class ESP01(WebServerInterface):
    """ESP-01 WiFi web server implementation"""

    def __init__(self, uart, reset_pin, debug=True):
        """
        Initialize ESP-01

        Args:
            uart: UART object connected to ESP-01
            reset_pin: DigitalInOut pin for ESP reset (GP6)
            debug: Enable debug logging of UART traffic (default: True)
        """
        self.uart = uart
        self.reset_pin = reset_pin
        self.debug = debug
        self._ready = False
        self._rx_buffer = bytearray(512)
        self._rx_pos = 0
        self._status = {'clients': 0, 'uptime': 0, 'mode': 'unknown'}
        self._last_status_time = 0
        self._config_sent = False

        # Get actual baudrate from UART object
        baudrate = uart.baudrate if hasattr(uart, 'baudrate') else 'unknown'
        print(f"[ESP01] Initialized ({baudrate} baud)")
        if self.debug:
            print("[ESP01] Debug mode enabled - will show all UART traffic")

    def reset(self):
        """Reset ESP-01 module via hardware pin"""
        import digitalio

        print("[ESP01] Resetting...")

        # Configure reset pin as output
        self.reset_pin.direction = digitalio.Direction.OUTPUT

        # Pulse reset low for 100ms
        self.reset_pin.value = False
        time.sleep(0.1)
        self.reset_pin.value = True

        # Wait for ESP to boot and scan for sync marker (+++)
        # This skips all boot ROM garbage (output at 74880 baud) until we see
        # the sync marker sent by the ESP at the correct baudrate
        # Classic Hayes modem style - just the three plus signs
        print("[ESP01] Waiting for sync marker (+++)")
        sync_buffer = bytearray()
        sync_timeout = 5.0
        sync_start = time.monotonic()
        bytes_discarded = 0

        while time.monotonic() - sync_start < sync_timeout:
            if self.uart.in_waiting:
                byte = self.uart.read(1)
                if byte:
                    bytes_discarded += 1
                    sync_buffer.append(byte[0])

                    # Keep only last 3 bytes in buffer (looking for "+++")
                    if len(sync_buffer) > 3:
                        sync_buffer = sync_buffer[-3:]  # CircuitPython doesn't support pop(0)

                    # Check for sync marker: +++ (0x2B 0x2B 0x2B)
                    if len(sync_buffer) >= 3 and sync_buffer[-3:] == b'+++':
                        if self.debug:
                            print(f"[ESP01] Sync marker found! Discarded {bytes_discarded} bytes of boot output")
                        break
            time.sleep(0.01)
        else:
            # Timeout waiting for sync
            if self.debug:
                print(f"[ESP01] Sync timeout! Discarded {bytes_discarded} bytes, no marker found")

        # Clear internal line buffer
        self._rx_pos = 0

        self._ready = False
        self._config_sent = False

        print("[ESP01] Reset complete, synced")
        return True

    def is_ready(self):
        """Check if ESP is ready to serve"""
        return self._ready

    def send_config(self, config_dict):
        """
        Send configuration to ESP

        Args:
            config_dict: {
                'mode': 'ap' or 'sta',
                'ssid': 'network name',
                'password': 'password',
                'address': '192.168.4.1',
                'netmask': '255.255.255.0',
                'gateway': '192.168.4.1'
            }
        """
        print("[ESP01] Sending config...")

        # Send configuration as simple key=value lines
        try:
            self.uart.write(b'CONFIG\n')
            if self.debug:
                print("[ESP01 TX] CONFIG")

            for key, value in config_dict.items():
                line = f"{key}={value}\n"
                self.uart.write(line.encode())
                if self.debug:
                    print(f"[ESP01 TX] {key}={value}")

            self.uart.write(b'END\n')
            if self.debug:
                print("[ESP01 TX] END")

            self._config_sent = True
            print("[ESP01] Config sent")
            return True

        except Exception as e:
            print(f"[ESP01] Config send failed: {e}")
            return False

    def update(self):
        """
        Process incoming messages from ESP

        Returns:
            tuple: (request_type, request_data) or (None, None)
        """
        # Read available data into buffer
        if self.uart.in_waiting:
            try:
                chunk = self.uart.read(min(self.uart.in_waiting, 256))
                if chunk:
                    for byte in chunk:
                        if byte == ord('\n'):
                            # Process complete line
                            line = bytes(self._rx_buffer[:self._rx_pos]).decode('utf-8', 'ignore').strip()
                            self._rx_pos = 0

                            # Debug: Show incoming line
                            if self.debug and line:
                                print(f"[ESP01 RX] {line}")

                            # Process the line
                            result = self._process_line(line)
                            if result:
                                return result
                        else:
                            # Add to buffer if space available
                            if self._rx_pos < len(self._rx_buffer) - 1:
                                self._rx_buffer[self._rx_pos] = byte
                                self._rx_pos += 1
                            else:
                                # Buffer overflow - reset
                                self._rx_pos = 0
            except Exception as e:
                # Ignore UART errors
                pass

        return (None, None)

    def _process_line(self, line):
        """
        Process a line received from ESP

        Returns:
            tuple: (request_type, request_data) or None
        """
        if not line:
            return None

        # ESP requesting config
        if line == 'ESP:config':
            print("[ESP01] Config requested")
            self._ready = False
            self._config_sent = False
            return ('config_request', None)

        # ESP is now serving
        elif line == 'ESP:serving':
            print("[ESP01] Now serving")
            self._ready = True
            return None

        # Status update: "ESP:status clients=2 uptime=3600"
        elif line.startswith('ESP:status'):
            parts = line.split()
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    try:
                        self._status[key] = int(value) if value.isdigit() else value
                    except:
                        self._status[key] = value
            self._last_status_time = time.monotonic()
            return None

        # Page request: "ESP:get /index.html"
        elif line.startswith('ESP:get'):
            filename = line.split()[1] if len(line.split()) > 1 else '/'
            print(f"[ESP01] Page request: {filename}")
            return ('page_request', filename)

        # File list request: "ESP:list"
        elif line == 'ESP:list':
            print("[ESP01] File list requested")
            return ('file_list_request', None)

        # File download request: "ESP:download filename"
        elif line.startswith('ESP:download'):
            filename = line.split()[1] if len(line.split()) > 1 else None
            if filename:
                print(f"[ESP01] Download requested: {filename}")
                return ('file_download_request', filename)
            return None

        # Session control commands
        elif line == 'ESP:session_stop':
            print("[ESP01] Session stop requested")
            return ('session_stop', None)

        elif line == 'ESP:session_start':
            print("[ESP01] Session start requested")
            return ('session_start', None)

        elif line == 'ESP:session_restart':
            print("[ESP01] Session restart requested")
            return ('session_restart', None)

        elif line.startswith('ESP:session_update'):
            # Format: "ESP:session_update driver=John,vehicle=Mustang,track=Laguna Seca"
            params = line.replace('ESP:session_update ', '', 1)
            print(f"[ESP01] Session update requested: {params}")
            return ('session_update', params)

        elif line == 'ESP:session_info':
            print("[ESP01] Session info requested")
            return ('session_info_request', None)

        # Unknown message
        else:
            return None

    def stream_telemetry(self, data):
        """
        Stream telemetry data to websockets

        Args:
            data: Dict with telemetry data

        Returns:
            bool: True if sent
        """
        if not self._ready:
            return False

        try:
            # Format as JSON-like string
            # Keep it simple for CircuitPython
            msg = "WS:{"
            pairs = []

            for key, value in data.items():
                if isinstance(value, float):
                    pairs.append(f'"{key}":{value:.6f}')
                elif isinstance(value, int):
                    pairs.append(f'"{key}":{value}')
                elif isinstance(value, str):
                    pairs.append(f'"{key}":"{value}"')

            msg += ','.join(pairs)
            msg += "}\n"

            self.uart.write(msg.encode())

            # Debug: Show telemetry (but limit frequency to avoid spam)
            if self.debug:
                # Only show every 10th telemetry message to reduce spam
                if not hasattr(self, '_telemetry_count'):
                    self._telemetry_count = 0
                self._telemetry_count += 1
                if self._telemetry_count % 10 == 0:
                    print(f"[ESP01 TX] WS:{{...}} (telemetry #{self._telemetry_count})")

            return True

        except Exception as e:
            return False

    def serve_file(self, filename, content):
        """
        Serve file content to ESP

        Args:
            filename: Requested filename
            content: String content or iterable of chunks

        Returns:
            bool: True if sent
        """
        try:
            # Send file header
            if isinstance(content, str):
                size = len(content)
                header = f"FILE:{filename}:{size}\n"
                self.uart.write(header.encode())
                if self.debug:
                    print(f"[ESP01 TX] FILE:{filename}:{size}")
                self.uart.write(content.encode())
                if self.debug:
                    print(f"[ESP01 TX] <{size} bytes of content>")
            else:
                # Streaming mode - send chunks
                header = f"FILE:{filename}:0\n"
                self.uart.write(header.encode())
                if self.debug:
                    print(f"[ESP01 TX] FILE:{filename}:0 (streaming)")
                for chunk in content:
                    self.uart.write(chunk.encode() if isinstance(chunk, str) else chunk)

            # Send end marker
            self.uart.write(b"\nEND\n")
            if self.debug:
                print("[ESP01 TX] END")
            return True

        except Exception as e:
            # Send 404
            self.uart.write(b"404\n")
            if self.debug:
                print(f"[ESP01 TX] 404 (error: {e})")
            return False

    def send_file_list(self, file_list):
        """
        Send list of session files to ESP

        Args:
            file_list: List of dicts with file info {'filename', 'size', 'session_num'}

        Returns:
            bool: True if sent
        """
        try:
            # Send file list header
            self.uart.write(f"FILELIST:{len(file_list)}\n".encode())
            if self.debug:
                print(f"[ESP01 TX] FILELIST:{len(file_list)}")

            # Send each file info as JSON-like string
            for file_info in file_list:
                line = f"{file_info['filename']}|{file_info['size']}|{file_info.get('session_num', 0)}\n"
                self.uart.write(line.encode())
                if self.debug:
                    print(f"[ESP01 TX] {file_info['filename']} ({file_info['size']} bytes)")

            # Send end marker
            self.uart.write(b"END\n")
            if self.debug:
                print("[ESP01 TX] END")
            return True

        except Exception as e:
            if self.debug:
                print(f"[ESP01] Error sending file list: {e}")
            return False

    def stream_file(self, filepath):
        """
        Stream file content to ESP for download

        Args:
            filepath: Full path to file

        Returns:
            bool: True if sent successfully
        """
        try:
            import os

            # Get file size
            stat = os.stat(filepath)
            size = stat[6]

            # Send file header with size
            filename = filepath.split('/')[-1]
            self.uart.write(f"DOWNLOAD:{filename}:{size}\n".encode())
            if self.debug:
                print(f"[ESP01 TX] DOWNLOAD:{filename}:{size}")

            # Stream file in chunks
            chunk_size = 512
            bytes_sent = 0
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.uart.write(chunk)
                    bytes_sent += len(chunk)

            # Send end marker
            self.uart.write(b"\nEND\n")
            if self.debug:
                print(f"[ESP01 TX] END ({bytes_sent} bytes sent)")
            return True

        except Exception as e:
            # Send error
            self.uart.write(b"ERROR\n")
            if self.debug:
                print(f"[ESP01 TX] ERROR: {e}")
            return False

    def send_session_status(self, running, session_num):
        """
        Send session status to ESP

        Args:
            running: bool - Whether session is running
            session_num: int - Current session number

        Returns:
            bool: True if sent
        """
        try:
            status_str = "running" if running else "stopped"
            self.uart.write(f"SESSION_STATUS:{status_str},{session_num}\n".encode())
            if self.debug:
                print(f"[ESP01 TX] SESSION_STATUS:{status_str},{session_num}")
            return True
        except Exception as e:
            if self.debug:
                print(f"[ESP01] Error sending session status: {e}")
            return False

    def send_session_info(self, info):
        """
        Send current session info to ESP

        Args:
            info: dict with session info {'session_num', 'running', 'driver', 'vehicle', 'track'}

        Returns:
            bool: True if sent
        """
        try:
            # Send session info header
            self.uart.write(b"SESSION_INFO\n")
            if self.debug:
                print("[ESP01 TX] SESSION_INFO")

            # Send each field
            for key, value in info.items():
                line = f"{key}={value}\n"
                self.uart.write(line.encode())
                if self.debug:
                    print(f"[ESP01 TX] {key}={value}")

            # Send end marker
            self.uart.write(b"END\n")
            if self.debug:
                print("[ESP01 TX] END")
            return True

        except Exception as e:
            if self.debug:
                print(f"[ESP01] Error sending session info: {e}")
            return False

    def get_status(self):
        """Get server status"""
        return self._status.copy()


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


class NullGyroscope(GyroscopeInterface):
    """Stub gyroscope when disabled"""

    def read(self):
        return (0.0, 0.0, 0.0)

    def configure(self, range_dps=250, rate_hz=100):
        pass

    def get_rotation(self):
        return (0.0, 0.0, 0.0)


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

    def get_fix_quality(self):
        return 0

    def get_fix_type(self):
        return 'No Fix'

    def get_hdop(self):
        return None


class NullDisplay(DisplayInterface):
    """Stub display when not present"""
    
    def clear(self):
        pass
    
    def show(self):
        pass
    
    def text(self, string, x, y, color=1):
        pass
