"""
binary_logger.py - Binary logging format for OpenPonyLogger

Implements structured binary format with:
- Session management (headers with metadata)
- Data blocks with checksums (CRC32)
- Event-based flushing (time, size, high-g events)
- Configurable format (CSV or Binary)
"""

import struct
import time
import os

# CircuitPython doesn't have hashlib.sha256, so always use CRC32
HAS_HASHLIB = False

# =============================================================================
# Constants
# =============================================================================

# Magic bytes "OPNY"
MAGIC = b'OPNY'
MAGIC_INT = 0x4F504E59

# Format version
FORMAT_VERSION_MAJOR = 2
FORMAT_VERSION_MINOR = 0

# Hardware version
HARDWARE_VERSION_MAJOR = 1
HARDWARE_VERSION_MINOR = 0

# Block types
BLOCK_TYPE_SESSION_HEADER = 0x01
BLOCK_TYPE_DATA = 0x02
BLOCK_TYPE_SESSION_END = 0x03
BLOCK_TYPE_HARDWARE_CONFIG = 0x04  # Hardware configuration block

# Flush flags (bitmask)
FLUSH_FLAG_TIME = 0x01      # Time-based flush (5 minutes)
FLUSH_FLAG_SIZE = 0x02      # Buffer full
FLUSH_FLAG_EVENT = 0x04     # High G-force event
FLUSH_FLAG_MANUAL = 0x08    # Manual flush request
FLUSH_FLAG_SHUTDOWN = 0x10  # System shutdown

# Sample types
SAMPLE_TYPE_ACCELEROMETER = 0x01
SAMPLE_TYPE_GPS_FIX = 0x02
SAMPLE_TYPE_GPS_SATELLITES = 0x03
SAMPLE_TYPE_GYROSCOPE = 0x04
SAMPLE_TYPE_MAGNETOMETER = 0x05
SAMPLE_TYPE_OBD_PID = 0x10
SAMPLE_TYPE_EVENT_MARKER = 0x20

# Weather conditions
WEATHER_UNKNOWN = 0
WEATHER_CLEAR = 1
WEATHER_CLOUDY = 2
WEATHER_RAIN = 3
WEATHER_SNOW = 4
WEATHER_FOG = 5

# Limits
MAX_BLOCK_SIZE = 4096  # 4KB max block size
MAX_SESSION_NAME = 64
MAX_DRIVER_NAME = 32
MAX_VEHICLE_ID = 24
MAX_DATA_PAYLOAD = MAX_BLOCK_SIZE - 80  # Reserve space for headers

MAX_HARDWARE_ITEMS = 32  # Max number of hardware items in config

# Hardware types
HW_TYPE_ACCELEROMETER = 0x01
HW_TYPE_GPS = 0x02
HW_TYPE_DISPLAY = 0x03
HW_TYPE_STORAGE = 0x04
HW_TYPE_RTC = 0x05
HW_TYPE_LED = 0x06
HW_TYPE_NEOPIXEL = 0x07
HW_TYPE_RADIO = 0x08
HW_TYPE_OBD = 0x09
HW_TYPE_CAN = 0x0A

# Connection types
CONN_TYPE_I2C = 0x01
CONN_TYPE_SPI = 0x02
CONN_TYPE_UART = 0x03
CONN_TYPE_GPIO = 0x04
CONN_TYPE_STEMMA_QT = 0x05
CONN_TYPE_BUILTIN = 0x06

# Flush thresholds
FLUSH_TIME_THRESHOLD = 300  # 5 minutes in seconds
FLUSH_GFORCE_THRESHOLD = 3.0  # 3g event threshold


# =============================================================================
# CRC32 Implementation (for CircuitPython compatibility)
# =============================================================================

def _crc32_table():
    """Generate CRC32 lookup table"""
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        table.append(crc)
    return table

_CRC32_TABLE = None

def crc32(data, initial=0):
    """Calculate CRC32 checksum"""
    global _CRC32_TABLE
    if _CRC32_TABLE is None:
        _CRC32_TABLE = _crc32_table()
    
    crc = initial ^ 0xFFFFFFFF
    for byte in data:
        crc = _CRC32_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF

def generate_uuid():
    """Generate a simple UUID-like identifier"""
    ts = int(time.monotonic() * 1000000)
    return struct.pack('<QQ', ts, ts ^ 0xDEADBEEF12345678)

# =============================================================================
# Hardware Block
# =============================================================================

class HardwareConfigBlock:
    """
    Hardware configuration block - describes what hardware is connected
    
    This block is optional but recommended. It documents the exact hardware
    setup used for this session, making it easier to analyze data later.
    """
    
    def __init__(self):
        self.items = []  # List of (hw_type, conn_type, identifier) tuples
    
    def add_hardware(self, hw_type, conn_type, identifier):
        """
        Add hardware item
        
        Args:
            hw_type: Hardware type constant (HW_TYPE_*)
            conn_type: Connection type constant (CONN_TYPE_*)
            identifier: String identifier (e.g., "LIS3DH@0x18", "TX:GP0 RX:GP1")
        """
        if len(self.items) >= MAX_HARDWARE_ITEMS:
            return False
        
        # Truncate identifier to 31 chars max
        identifier = identifier[:31]
        self.items.append((hw_type, conn_type, identifier))
        return True
    
    def to_bytes(self):
        """Serialize to bytes"""
        block = bytearray()
        
        # Magic + Block Type
        block.extend(MAGIC)
        block.append(BLOCK_TYPE_HARDWARE_CONFIG)
        
        # Number of hardware items
        block.append(len(self.items))
        
        # Each hardware item: type (1) + conn_type (1) + id_len (1) + identifier (N)
        for hw_type, conn_type, identifier in self.items:
            block.append(hw_type)
            block.append(conn_type)
            
            id_bytes = identifier.encode('utf-8')
            block.append(len(id_bytes))
            block.extend(id_bytes)
        
        # CRC of entire block
        block_crc = crc32(bytes(block))
        block.extend(struct.pack('<I', block_crc))
        
        return bytes(block)
    
    @staticmethod
    def from_hardware_setup():
        """
        Create hardware config block from current hardware setup
        
        Returns:
            HardwareConfigBlock or None
        """
        try:
            from hardware_config import hw_config
            
            hw_block = HardwareConfigBlock()
            
            # Accelerometer
            if hw_config.is_enabled("sensors.accelerometer"):
                accel_type = hw_config.get("sensors.accelerometer.type", "Unknown")
                i2c_addr = hw_config.get("sensors.accelerometer.i2c_address", "0x18")
                hw_block.add_hardware(
                    HW_TYPE_ACCELEROMETER,
                    CONN_TYPE_I2C,
                    f"{accel_type}@{i2c_addr}"
                )
            
            # GPS
            if hw_config.is_enabled("gps"):
                gps_type = hw_config.get("gps.type", "Unknown")
                tx = hw_config.get("interfaces.uart_gps.tx", "?")
                rx = hw_config.get("interfaces.uart_gps.rx", "?")
                hw_block.add_hardware(
                    HW_TYPE_GPS,
                    CONN_TYPE_UART,
                    f"{gps_type} TX:{tx} RX:{rx}"
                )
            
            # Display
            if hw_config.is_enabled("display.oled"):
                display_type = hw_config.get("display.oled.type", "Unknown")
                i2c_addr = hw_config.get("display.oled.i2c_address", "0x3C")
                hw_block.add_hardware(
                    HW_TYPE_DISPLAY,
                    CONN_TYPE_I2C,
                    f"{display_type}@{i2c_addr}"
                )
            
            # Storage
            if hw_config.is_enabled("storage.sdcard"):
                sck = hw_config.get("interfaces.spi.sck", "?")
                cs = hw_config.get("storage.sdcard.cs_pin", "?")
                hw_block.add_hardware(
                    HW_TYPE_STORAGE,
                    CONN_TYPE_SPI,
                    f"SD SCK:{sck} CS:{cs}"
                )
            
            # RTC
            if hw_config.is_enabled("rtc"):
                rtc_type = hw_config.get("rtc.type", "builtin")
                if rtc_type == "pcf8523":
                    i2c_addr = hw_config.get("rtc.i2c_address", "0x68")
                    hw_block.add_hardware(
                        HW_TYPE_RTC,
                        CONN_TYPE_I2C,
                        f"PCF8523@{i2c_addr}"
                    )
                else:
                    hw_block.add_hardware(
                        HW_TYPE_RTC,
                        CONN_TYPE_BUILTIN,
                        "Pico Internal RTC"
                    )
            
            # Heartbeat LED
            if hw_config.is_enabled("indicators.heartbeat_led"):
                pin = hw_config.get("indicators.heartbeat_led.pin", "?")
                hw_block.add_hardware(
                    HW_TYPE_LED,
                    CONN_TYPE_GPIO,
                    f"Heartbeat {pin}"
                )
            
            # NeoPixel
            if hw_config.is_enabled("indicators.neopixel_jewel"):
                pin = hw_config.get("indicators.neopixel_jewel.pin", "?")
                num = hw_config.get("indicators.neopixel_jewel.num_pixels", 7)
                hw_block.add_hardware(
                    HW_TYPE_NEOPIXEL,
                    CONN_TYPE_GPIO,
                    f"{num}px on {pin}"
                )
            
            # Radio (ESP-01s)
            if hw_config.is_enabled("radio.esp01s"):
                tx = hw_config.get("interfaces.uart_esp.tx", "?")
                rx = hw_config.get("interfaces.uart_esp.rx", "?")
                hw_block.add_hardware(
                    HW_TYPE_RADIO,
                    CONN_TYPE_UART,
                    f"ESP-01s TX:{tx} RX:{rx}"
                )
            
            return hw_block if hw_block.items else None
            
        except Exception as e:
            print(f"[HW Config] Failed to build hardware block: {e}")
            return None

# =============================================================================
# Session Header
# =============================================================================

class SessionHeader:
    """Session header block"""
    
    def __init__(self, session_name="", driver_name="", vehicle_id="", 
                 weather=WEATHER_UNKNOWN, ambient_temp=0, config_crc=0):
        self.session_id = generate_uuid()
        self.timestamp_us = int(time.monotonic() * 1000000)
        self.session_name = session_name[:MAX_SESSION_NAME]
        self.driver_name = driver_name[:MAX_DRIVER_NAME]
        self.vehicle_id = vehicle_id[:MAX_VEHICLE_ID]
        self.weather = weather
        self.ambient_temp = int(ambient_temp * 10)  # 0.1°C resolution
        self.config_crc = config_crc
    
    def to_bytes(self):
        """Serialize to bytes"""
        # Build header
        header = bytearray()
        
        # Magic + Block Type
        header.extend(MAGIC)
        header.append(BLOCK_TYPE_SESSION_HEADER)
        
        # Version info
        header.append(FORMAT_VERSION_MAJOR)
        header.append(FORMAT_VERSION_MINOR)
        header.append(HARDWARE_VERSION_MAJOR)
        header.append(HARDWARE_VERSION_MINOR)
        
        # Timestamp and Session ID
        header.extend(struct.pack('<Q', self.timestamp_us))
        header.extend(self.session_id)
        
        # Session name
        name_bytes = self.session_name.encode('utf-8')[:MAX_SESSION_NAME]
        header.append(len(name_bytes))
        header.extend(name_bytes)
        
        # Driver name
        driver_bytes = self.driver_name.encode('utf-8')[:MAX_DRIVER_NAME]
        header.append(len(driver_bytes))
        header.extend(driver_bytes)
        
        # Vehicle ID
        vehicle_bytes = self.vehicle_id.encode('utf-8')[:MAX_VEHICLE_ID]
        header.append(len(vehicle_bytes))
        header.extend(vehicle_bytes)
        
        # Weather and temperature
        header.append(self.weather)
        header.extend(struct.pack('<h', self.ambient_temp))
        
        # Config CRC
        header.extend(struct.pack('<I', self.config_crc))
        
        # Calculate and append header CRC
        header_crc = crc32(bytes(header))
        header.extend(struct.pack('<I', header_crc))
        
        return bytes(header)


# =============================================================================
# Data Block
# =============================================================================

class DataBlock:
    """Data block with samples"""
    
    def __init__(self, session_id, block_seq):
        self.session_id = session_id
        self.block_sequence = block_seq
        self.timestamp_start = None
        self.timestamp_end = None
        self.flush_flags = 0
        self.samples = []
        self.data_size = 0
    
    def add_sample(self, sample_type, timestamp_us, data):
        """Add a sample to the block"""
        if self.timestamp_start is None:
            self.timestamp_start = timestamp_us
        self.timestamp_end = timestamp_us
        
        # Calculate timestamp offset in ms
        offset_ms = int((timestamp_us - self.timestamp_start) / 1000)
        if offset_ms > 65535:
            offset_ms = 65535
        
        # Build sample: type (1) + offset (2) + length (1) + data (N)
        sample = struct.pack('<BHB', sample_type, offset_ms, len(data)) + data
        
        # Check if adding this sample would exceed max size
        if self.data_size + len(sample) > MAX_DATA_PAYLOAD:
            return False  # Block full
        
        self.samples.append(sample)
        self.data_size += len(sample)
        return True
    
    def is_empty(self):
        """Check if block has no samples"""
        return len(self.samples) == 0
    
    def should_flush(self, current_time, last_flush_time, gforce_total=0):
        """Determine if block should be flushed"""
        # Time threshold
        if current_time - last_flush_time >= FLUSH_TIME_THRESHOLD:
            self.flush_flags |= FLUSH_FLAG_TIME
            return True
        
        # Size threshold (90% full)
        if self.data_size >= int(MAX_DATA_PAYLOAD * 0.9):
            self.flush_flags |= FLUSH_FLAG_SIZE
            return True
        
        # G-force event threshold
        if gforce_total >= FLUSH_GFORCE_THRESHOLD:
            self.flush_flags |= FLUSH_FLAG_EVENT
            return True
        
        return False
    
    def to_bytes(self):
        """Serialize to bytes"""
        if self.is_empty():
            return b''
        
        # Build block header
        header = bytearray()
        
        # Magic + Block Type
        header.extend(MAGIC)
        header.append(BLOCK_TYPE_DATA)
        
        # Session ID and block sequence
        header.extend(self.session_id)
        header.extend(struct.pack('<I', self.block_sequence))
        
        # Timestamps
        header.extend(struct.pack('<Q', self.timestamp_start or 0))
        header.extend(struct.pack('<Q', self.timestamp_end or 0))
        
        # Flush flags, sample count, data size
        header.append(self.flush_flags)
        header.extend(struct.pack('<H', len(self.samples)))
        header.extend(struct.pack('<H', self.data_size))
        
        # Combine all samples
        data_payload = b''.join(self.samples)
        
        # Calculate CRC32 checksum of header + data
        block_data = bytes(header) + data_payload
        checksum = crc32(block_data)
        
        # Return block with CRC32 (4 bytes, little-endian)
        return block_data + struct.pack('<I', checksum)


# =============================================================================
# Binary Logger
# =============================================================================

class BinaryLogger:
    """Binary logging with session management"""
    
    def __init__(self, base_path="/sd"):
        self.base_path = base_path
        self.log_file = None
        self.log_filename = None
        self.current_session = None
        self.current_block = None
        self.block_sequence = 0
        self._last_flush_time = 0
        self.active = False
        self.start_time = None
        self.bytes_written = 0
    
    def start_session(self, session_name="", driver_name="", vehicle_id="",
                     weather=WEATHER_UNKNOWN, ambient_temp=0, config_crc=0,
                     include_hardware=True, filename=None):
        """
        Start a new logging session
    
        Args:
            session_name: Name of session
            driver_name: Driver name
            vehicle_id: Vehicle identifier
            weather: Weather condition code
            ambient_temp: Ambient temperature in °C
            config_crc: Configuration CRC
            include_hardware: If True, write hardware config block (default: True)
            filename: Optional filename (if None, generates timestamp-based name)
        """
        if self.active:
            self.stop_session()
        
        # Create session header
        self.current_session = SessionHeader(
            session_name, driver_name, vehicle_id,
            weather, ambient_temp, config_crc
        )
        
        # Use provided filename or generate fallback
        print(f"[BinaryLog Debug] start_session() called")
        print(f"[BinaryLog Debug]   filename parameter: {filename}")
        
        if filename:
            self.log_filename = filename
            print(f"[BinaryLog Debug]   Using provided filename: {self.log_filename}")
        else:
            # Fallback: timestamp-based (when called directly, not via SessionLogger)
            timestamp = int(time.monotonic())
            self.log_filename = f"{self.base_path}/session_{timestamp}.opl"
            print(f"[BinaryLog Debug]   Generated timestamp filename: {self.log_filename}")
        
        self.bytes_written = 0
        # Open log file and write session header
        self.log_file = open(self.log_filename, 'wb')
        self.log_file.write(self.current_session.to_bytes())
        self.log_file.flush()

        # Store hardware config
        if include_hardware:
            hw_block = HardwareConfigBlock.from_hardware_setup()
            if hw_block:
                self.log_file.write(hw_block.to_bytes())
                print(f"[BinaryLog] Hardware config: {len(hw_block.items)} items")
        
        # Initialize first data block
        self.block_sequence = 0
        self.current_block = DataBlock(
            self.current_session.session_id,
            self.block_sequence
        )
        self.start_time = time.monotonic()
        self._last_flush_time = time.monotonic()
        self.active = True
        
        print(f"[BinaryLog] Session started: {self.log_filename}")
        return self.current_session.session_id
    
    def write_sample(self, sample_type, data, timestamp_us=None, gforce_total=0):
        """Write a sample to the current block"""
        if not self.active:
            return False
        
        if timestamp_us is None:
            timestamp_us = int(time.monotonic() * 1000000)
        
        # Try to add sample to current block
        if not self.current_block.add_sample(sample_type, timestamp_us, data):
            # Block full, flush and create new block
            self._flush_block()
            self.current_block.add_sample(sample_type, timestamp_us, data)
        
        # Check if we should flush
        current_time = time.monotonic()
        if self.current_block.should_flush(current_time, self._last_flush_time, gforce_total):
            self._flush_block()
        
        return True
    
    def _flush_block(self):
        """Flush current block to file"""
        if self.current_block and not self.current_block.is_empty():
            block_bytes = self.current_block.to_bytes()
            self.log_file.write(block_bytes)
            self.log_file.flush()
            self.bytes_written += len(block_bytes)
            
            # Create new block
            self.block_sequence += 1
            self.current_block = DataBlock(
                self.current_session.session_id,
                self.block_sequence
            )
            self._last_flush_time = time.monotonic()
    
    def stop_session(self):
        """Stop current logging session"""
        if not self.active:
            return
        
        # Flush remaining data
        self._flush_block()
        
        # Write session end marker
        end_block = MAGIC + bytes([BLOCK_TYPE_SESSION_END]) + self.current_session.session_id
        self.log_file.write(end_block)
        self.log_file.flush()
        self.log_file.close()
        
        self.active = False
        print(f"[BinaryLog] Session stopped: {self.log_filename}")
    
    # Convenience methods
    def write_metadata(self, message):
        """
        Write metadata/comment to log
    
        Args:
            message: String message to log
    
        Returns:
            bool: True if successful
        """
        if not self.active:
            return False
    
        try:
            # Encode message as UTF-8
            msg_bytes = message.encode('utf-8')
            data = struct.pack(f'<{len(msg_bytes)}s', msg_bytes)
            return self.write_sample(SAMPLE_TYPE_METADATA, data)
        except Exception as e:
            print(f"[Logger] Metadata write error: {e}")
            return False

    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        """Write accelerometer data"""
        data = struct.pack('<fff', gx, gy, gz)
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        return self.write_sample(SAMPLE_TYPE_ACCELEROMETER, data, timestamp_us, g_total)

    def write_gyroscope(self, gx, gy, gz, timestamp_us=None):
        """Write gyroscope data (degrees/sec)"""
        data = struct.pack('<fff', gx, gy, gz)
        return self.write_sample(SAMPLE_TYPE_GYROSCOPE, data, timestamp_us)

    def write_magnetometer(self, mx, my, mz, timestamp_us=None):
        """Write magnetometer data (micro-Tesla)"""
        data = struct.pack('<fff', mx, my, mz)
        return self.write_sample(SAMPLE_TYPE_MAGNETOMETER, data, timestamp_us)
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        """Write GPS fix data"""
        data = struct.pack('<ddffff', lat, lon, alt, speed, heading, hdop)
        return self.write_sample(SAMPLE_TYPE_GPS_FIX, data, timestamp_us)
    
    def write_gps_satellites(self, satellites, timestamp_us=None):
        """
        Write GPS satellite data
        
        Format per satellite:
        - ID: 1 byte (0-255)
        - Azimuth: 2 bytes (0-360 degrees)
        - Elevation: 1 byte (0-90 degrees)
        - SNR: 1 byte (0-99 dB)
        Total: 5 bytes per satellite
        """
        # Pack: count (1 byte) + for each sat: id (1), azimuth (2), elevation (1), snr (1)
        data = struct.pack('<B', len(satellites))
        for sat in satellites:
            # Clamp values to valid ranges
            sat_id = min(255, max(0, sat['id']))
            azimuth = min(360, max(0, sat['azimuth']))
            elevation = min(90, max(0, sat['elevation']))
            snr = min(99, max(0, sat['snr']))
            
            # Pack: id (B), azimuth (H=2 bytes), elevation (B), snr (B)
            data += struct.pack('<BHBB', sat_id, azimuth, elevation, snr)
        
        return self.write_sample(SAMPLE_TYPE_GPS_SATELLITES, data, timestamp_us)

    def get_duration(self):
        """Get current session duration"""
        if not self.active or not self.start_time:
            return 0
        return time.monotonic() - self.start_time

    def get_bytes_per_second(self): 
        """Get average bytes per second"""
        duration = self.get_duration()
        if duration <= 0:
            return 0
        return self.bytes_written / duration
