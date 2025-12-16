"""
binary_logger.py - Binary logging format for OpenPonyLogger

Implements structured binary format with:
- Session management (headers with metadata)
- Data blocks with checksums (SHA-256 or CRC32 fallback)
- Event-based flushing (time, size, high-g events)
- Configurable format (CSV or Binary)
"""

import struct
import time
import os

# Try to import hashlib for SHA-256, fall back to CRC32
try:
    import hashlib
    HAS_HASHLIB = True
except ImportError:
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
        
        # Calculate checksum of header + data
        block_data = bytes(header) + data_payload
        checksum = crc32(block_data).to_bytes(4, 'big')
        
        return block_data + checksum


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
        self.bytes_written = None
    
    def start_session(self, session_name="", driver_name="", vehicle_id="",
                     weather=WEATHER_UNKNOWN, ambient_temp=0, config_crc=0):
        """Start a new logging session"""
        if self.active:
            self.stop_session()
        
        # Create session header
        self.current_session = SessionHeader(
            session_name, driver_name, vehicle_id,
            weather, ambient_temp, config_crc
        )
        
        # Generate filename using sequential numbering
        try:
            from sdcard import get_sdcard
            sd = get_sdcard()
            if sd and sd.mounted:
                self.log_filename = sd.create_session_filename('opl')
            else:
                # Fallback to timestamp-based naming
                timestamp = int(time.monotonic())
                self.log_filename = f"{self.base_path}/session_{timestamp}.opl"
        except:
            # Fallback to timestamp-based naming
            timestamp = int(time.monotonic())
            self.log_filename = f"{self.base_path}/session_{timestamp}.opl"
        
        self.bytes_written = 0
        # Open log file and write session header
        self.log_file = open(self.log_filename, 'wb')
        self.log_file.write(self.current_session.to_bytes())
        self.log_file.flush()
        
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
            self.log_file.write(self.current_block.to_bytes())
            self.log_file.flush()
            self.bytes_written += len(self.current_block.to_bytes())
            
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
    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        """Write accelerometer data"""
        data = struct.pack('<fff', gx, gy, gz)
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        return self.write_sample(SAMPLE_TYPE_ACCELEROMETER, data, timestamp_us, g_total)
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        """Write GPS fix data"""
        data = struct.pack('<ddffff', lat, lon, alt, speed, heading, hdop)
        return self.write_sample(SAMPLE_TYPE_GPS_FIX, data, timestamp_us)
    
    def write_gps_satellites(self, satellites, timestamp_us=None):
        """Write GPS satellite data"""
        # Pack: count (1 byte) + for each sat: id, azimuth, elevation, snr (4 bytes each)
        data = struct.pack('<B', len(satellites))
        for sat in satellites:
            data += struct.pack('<BBBB', sat['id'], sat['azimuth'], sat['elevation'], sat['snr'])
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
