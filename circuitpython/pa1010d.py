"""
pa1010d.py - PA1010D GPS module driver for CircuitPython

Supports both UART and I2C interfaces for the PA1010D GPS module
(Adafruit Mini GPS PA1010D, MTK3333 chipset)

Hardware:
- PA1010D GPS module
- UART interface (default)
- I2C/STEMMA QT interface (optional)

UART connections:
- TX -> GP0 (UART0 RX)
- RX -> GP1 (UART0 TX)
- VIN -> 3.3V
- GND -> GND

I2C/STEMMA QT connections:
- SCL -> GP9 (I2C1 SCL)
- SDA -> GP8 (I2C1 SDA)
- VIN -> 3.3V
- GND -> GND
"""

import time
from micropython import const

# I2C address for PA1010D
PA1010D_ADDR = const(0x10)

# Common NMEA sentence types
NMEA_GGA = b'$GPGGA'  # Fix data
NMEA_RMC = b'$GPRMC'  # Recommended minimum
NMEA_GSA = b'$GPGSA'  # DOP and active satellites
NMEA_GSV = b'$GPGSV'  # Satellites in view
NMEA_VTG = b'$GPVTG'  # Track and ground speed

# GPS fix quality
FIX_INVALID = const(0)
FIX_GPS = const(1)
FIX_DGPS = const(2)


class PA1010D:
    """
    PA1010D GPS module driver
    
    Supports both UART and I2C interfaces
    
    Example usage (UART):
        uart = busio.UART(board.GP0, board.GP1, baudrate=9600)
        gps = PA1010D(uart, mode='uart')
        
    Example usage (I2C):
        i2c = busio.I2C(board.GP9, board.GP8)
        gps = PA1010D(i2c, mode='i2c')
    """
    
    def __init__(self, interface, mode='uart', timeout=1.0):
        """
        Initialize PA1010D GPS module
        
        Args:
            interface: UART or I2C bus object
            mode: 'uart' or 'i2c'
            timeout: Read timeout in seconds
        """
        self.mode = mode.lower()
        self.timeout = timeout
        
        if self.mode == 'uart':
            self.uart = interface
            self.i2c = None
        elif self.mode == 'i2c':
            self.i2c = interface
            self.uart = None
            # Check if GPS is present on I2C
            if PA1010D_ADDR not in self.i2c.scan():
                raise RuntimeError(f"PA1010D not found at I2C address 0x{PA1010D_ADDR:02X}")
        else:
            raise ValueError("mode must be 'uart' or 'i2c'")
        
        # GPS state
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.speed_knots = None
        self.speed_mph = None
        self.track_angle = None
        self.satellites = None
        self.fix_quality = FIX_INVALID
        self.timestamp = None
        self.date = None
        self.hdop = None
        
        # Buffer for partial sentences
        self._buffer = bytearray()
        
        print(f"[PA1010D] Initialized in {mode.upper()} mode")
    
    def _read_uart(self):
        """Read available data from UART"""
        if self.uart.in_waiting > 0:
            data = self.uart.read(self.uart.in_waiting)
            if data:
                self._buffer.extend(data)
    
    def _read_i2c(self):
        """Read available data from I2C"""
        try:
            # PA1010D can provide up to 255 bytes at a time over I2C
            data = bytearray(255)
            self.i2c.readfrom_into(PA1010D_ADDR, data)
            
            # Find actual data (stop at first 0x0A or null)
            end_idx = 0
            for i, byte in enumerate(data):
                if byte == 0x0A or byte == 0x00:
                    end_idx = i + 1
                    break
            
            if end_idx > 0:
                self._buffer.extend(data[:end_idx])
        except OSError:
            # No data available
            pass
    
    def update(self):
        """
        Read and process GPS data
        
        Returns:
            True if new data was processed, False otherwise
        """
        # Read data from interface
        if self.mode == 'uart':
            self._read_uart()
        else:
            self._read_i2c()
        
        # Process complete NMEA sentences
        updated = False
        while b'\n' in self._buffer:
            # Extract one sentence
            line_end = self._buffer.index(b'\n')
            sentence = bytes(self._buffer[:line_end])
            self._buffer = self._buffer[line_end + 1:]
            
            # Parse sentence
            if self._parse_sentence(sentence):
                updated = True
        
        return updated
    
    def _parse_sentence(self, sentence):
        """
        Parse NMEA sentence
        
        Args:
            sentence: NMEA sentence bytes
            
        Returns:
            True if sentence was parsed successfully
        """
        # Remove \r if present
        sentence = sentence.rstrip(b'\r')
        
        # Check for valid sentence
        if not sentence.startswith(b'$'):
            return False
        
        # Verify checksum if present
        if b'*' in sentence:
            data, checksum = sentence.rsplit(b'*', 1)
            try:
                expected = int(checksum, 16)
                actual = 0
                for byte in data[1:]:  # Skip $
                    actual ^= byte
                if actual != expected:
                    return False
            except ValueError:
                return False
        
        # Split into fields
        try:
            fields = sentence.split(b',')
        except:
            return False
        
        # Parse based on sentence type
        sentence_type = fields[0]
        
        if sentence_type == NMEA_GGA:
            return self._parse_gga(fields)
        elif sentence_type == NMEA_RMC:
            return self._parse_rmc(fields)
        elif sentence_type == NMEA_GSA:
            return self._parse_gsa(fields)
        
        return False
    
    def _parse_gga(self, fields):
        """Parse $GPGGA sentence (fix data)"""
        try:
            # Time (hhmmss.sss)
            if fields[1]:
                self.timestamp = fields[1].decode('ascii')
            
            # Latitude (ddmm.mmmm)
            if fields[2] and fields[3]:
                lat = float(fields[2])
                lat_deg = int(lat / 100)
                lat_min = lat - (lat_deg * 100)
                self.latitude = lat_deg + lat_min / 60.0
                if fields[3] == b'S':
                    self.latitude = -self.latitude
            
            # Longitude (dddmm.mmmm)
            if fields[4] and fields[5]:
                lon = float(fields[4])
                lon_deg = int(lon / 100)
                lon_min = lon - (lon_deg * 100)
                self.longitude = lon_deg + lon_min / 60.0
                if fields[5] == b'W':
                    self.longitude = -self.longitude
            
            # Fix quality
            if fields[6]:
                self.fix_quality = int(fields[6])
            
            # Number of satellites
            if fields[7]:
                self.satellites = int(fields[7])
            
            # HDOP
            if fields[8]:
                self.hdop = float(fields[8])
            
            # Altitude
            if fields[9]:
                self.altitude = float(fields[9])
            
            return True
        except (ValueError, IndexError):
            return False
    
    def _parse_rmc(self, fields):
        """Parse $GPRMC sentence (recommended minimum)"""
        try:
            # Time
            if fields[1]:
                self.timestamp = fields[1].decode('ascii')
            
            # Status (A=valid, V=invalid)
            if fields[2] != b'A':
                return False
            
            # Latitude
            if fields[3] and fields[4]:
                lat = float(fields[3])
                lat_deg = int(lat / 100)
                lat_min = lat - (lat_deg * 100)
                self.latitude = lat_deg + lat_min / 60.0
                if fields[4] == b'S':
                    self.latitude = -self.latitude
            
            # Longitude
            if fields[5] and fields[6]:
                lon = float(fields[5])
                lon_deg = int(lon / 100)
                lon_min = lon - (lon_deg * 100)
                self.longitude = lon_deg + lon_min / 60.0
                if fields[6] == b'W':
                    self.longitude = -self.longitude
            
            # Speed (knots)
            if fields[7]:
                self.speed_knots = float(fields[7])
                self.speed_mph = self.speed_knots * 1.15078  # knots to mph
            
            # Track angle
            if fields[8]:
                self.track_angle = float(fields[8])
            
            # Date (ddmmyy)
            if fields[9]:
                self.date = fields[9].decode('ascii')
            
            return True
        except (ValueError, IndexError):
            return False
    
    def _parse_gsa(self, fields):
        """Parse $GPGSA sentence (DOP and active satellites)"""
        try:
            # HDOP (field 16)
            if len(fields) > 16 and fields[16]:
                self.hdop = float(fields[16])
            return True
        except (ValueError, IndexError):
            return False
    
    @property
    def has_fix(self):
        """Check if GPS has a valid fix"""
        return self.fix_quality > FIX_INVALID and self.latitude is not None
    
    @property
    def fix_quality_3d(self):
        """Check if GPS has 3D fix (altitude valid)"""
        return self.fix_quality > FIX_INVALID and self.altitude is not None
    
    def send_command(self, command):
        """
        Send PMTK command to GPS
        
        Args:
            command: PMTK command string (e.g., "PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
        """
        # Calculate checksum
        checksum = 0
        for char in command:
            checksum ^= ord(char)
        
        # Format command
        cmd = f"${command}*{checksum:02X}\r\n"
        
        # Send via appropriate interface
        if self.mode == 'uart':
            self.uart.write(cmd.encode('ascii'))
        else:
            # I2C mode - PA1010D accepts commands over I2C
            self.i2c.writeto(PA1010D_ADDR, cmd.encode('ascii'))
        
        print(f"[PA1010D] Sent: {cmd.strip()}")
    
    def set_update_rate(self, rate_hz):
        """
        Set GPS update rate
        
        Args:
            rate_hz: Update rate in Hz (1, 5, or 10)
        """
        rate_map = {
            1: 1000,   # 1 Hz = 1000ms
            5: 200,    # 5 Hz = 200ms
            10: 100    # 10 Hz = 100ms
        }
        
        interval = rate_map.get(rate_hz, 1000)
        self.send_command(f"PMTK220,{interval}")
    
    def set_output_sentences(self, gga=True, rmc=True, vtg=False, gsa=False, gsv=False):
        """
        Configure which NMEA sentences to output
        
        Args:
            gga: Enable GGA (fix data)
            rmc: Enable RMC (recommended minimum)
            vtg: Enable VTG (course and speed)
            gsa: Enable GSA (DOP and active satellites)
            gsv: Enable GSV (satellites in view)
        """
        # PMTK314 sets output sentences
        # Format: GLL,RMC,VTG,GGA,GSA,GSV,...
        cmd = "PMTK314,0,{},{},{},{},{},0,0,0,0,0,0,0,0,0,0,0,0,0".format(
            1 if rmc else 0,
            1 if vtg else 0,
            1 if gga else 0,
            1 if gsa else 0,
            1 if gsv else 0
        )
        self.send_command(cmd)
    
    def factory_reset(self):
        """Reset GPS to factory defaults"""
        self.send_command("PMTK104")
        time.sleep(1)
    
    def hot_start(self):
        """Hot start (use all available data)"""
        self.send_command("PMTK101")
    
    def warm_start(self):
        """Warm start (don't use ephemeris)"""
        self.send_command("PMTK102")
    
    def cold_start(self):
        """Cold start (clear all data)"""
        self.send_command("PMTK103")
    
    def standby_mode(self):
        """Enter standby mode (low power)"""
        self.send_command("PMTK161,0")
    
    def get_info(self):
        """
        Get GPS module information
        
        Returns:
            Dict with GPS status and capabilities
        """
        return {
            'mode': self.mode,
            'has_fix': self.has_fix,
            'fix_quality': self.fix_quality,
            'satellites': self.satellites,
            'hdop': self.hdop,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed_mph': self.speed_mph,
            'track_angle': self.track_angle,
            'timestamp': self.timestamp,
            'date': self.date
        }
