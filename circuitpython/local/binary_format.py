"""
binary_format.py - OpenPonyLogger Binary Data Format v2

This module implements a structured binary format for high-performance
data logging with:
- Session headers with metadata
- Checksummed data blocks (max 4KB)
- Multiple flush triggers (time, size, event)
- Support for session restarts

Binary Format Overview:
=======================

Session Header Block (Type 0x01):
---------------------------------
| Field                  | Size    | Description                          |
|------------------------|---------|--------------------------------------|
| Magic                  | 4 bytes | "OPNY" (0x4F504E59)                  |
| Block Type             | 1 byte  | 0x01 = Session Header                |
| Format Version         | 2 bytes | Binary format version (major.minor)  |
| Hardware Version       | 2 bytes | Hardware version (major.minor)       |
| Timestamp              | 8 bytes | Unix timestamp (microseconds)        |
| Session ID             | 16 bytes| UUID for this session                |
| Session Name Length    | 1 byte  | Length of session name               |
| Session Name           | N bytes | UTF-8 session name (max 64)          |
| Driver Name Length     | 1 byte  | Length of driver name                |
| Driver Name            | N bytes | UTF-8 driver name (max 32)           |
| Vehicle ID Length      | 1 byte  | Length of VIN/vehicle ID             |
| Vehicle ID             | N bytes | ASCII VIN or vehicle ID (max 24)     |
| Weather Conditions     | 1 byte  | Enum: 0=Unknown, 1=Clear, 2=Rain...  |
| Ambient Temp           | 2 bytes | Temperature in 0.1°C (signed)        |
| Config Checksum        | 4 bytes | CRC32 of settings.toml               |
| Header Checksum        | 4 bytes | CRC32 of header (excl this field)    |

Data Block (Type 0x02):
-----------------------
| Field                  | Size    | Description                          |
|------------------------|---------|--------------------------------------|
| Magic                  | 4 bytes | "OPNY" (0x4F504E59)                  |
| Block Type             | 1 byte  | 0x02 = Data Block                    |
| Block Sequence         | 4 bytes | Sequential block number              |
| Session ID             | 16 bytes| UUID linking to session              |
| Timestamp Start        | 8 bytes | First sample timestamp (us)          |
| Timestamp End          | 8 bytes | Last sample timestamp (us)           |
| Flush Flags            | 1 byte  | Bitmask: 0x01=Time, 0x02=Size, 0x04=Event |
| Sample Count           | 2 bytes | Number of samples in block           |
| Data Size              | 2 bytes | Size of data payload in bytes        |
| Data Payload           | N bytes | Packed sensor data                   |
| Block Checksum         | 32 bytes| SHA-256 of block (excl checksum)     |

Data Payload Format (per sample):
---------------------------------
| Field                  | Size    | Description                          |
|------------------------|---------|--------------------------------------|
| Sample Type            | 1 byte  | Sensor type identifier               |
| Timestamp Offset       | 2 bytes | Milliseconds from block start        |
| Data Length            | 1 byte  | Length of sample data                |
| Sample Data            | N bytes | Sensor-specific data                 |

Sample Types:
- 0x01: Accelerometer (12 bytes: 3x float32)
- 0x02: GPS Fix (24 bytes: lat, lon, alt, speed, heading, hdop)
- 0x03: GPS Satellites (variable)
- 0x10: OBD-II PID (variable: mode, pid, value)
- 0x20: Event marker (variable: event type, description)
"""

import struct
import time
import os

# Try to import hashlib for SHA-256, fall back to simple checksum
# CircuitPython may have hashlib but without sha256
HAS_HASHLIB = False
try:
    import hashlib
    if hasattr(hashlib, 'sha256'):
        HAS_HASHLIB = True
except ImportError:
    pass


def get_safe_timestamp():
    """
    Get a safe timestamp in microseconds.
    
    Falls back to code.py modification time if RTC is not set (year < 2020).
    Returns microseconds since epoch.
    """
    try:
        # Try to get current time
        current = time.time()
        # Check if RTC is set (year should be >= 2020)
        try:
            year = time.localtime(current).tm_year
            if year >= 2020:
                return int(current * 1000000)
        except (OverflowError, OSError):
            pass
        
        # RTC not set - try to use code.py modification time
        try:
            stat = os.stat('/code.py')
            mtime = stat[8]  # st_mtime
            if mtime > 0:
                # Check if mtime is reasonable
                try:
                    year = time.localtime(mtime).tm_year
                    if year >= 2020:
                        print("[BinaryLog] Using code.py mtime as timestamp")
                        return int(mtime * 1000000)
                except:
                    pass
        except OSError:
            pass
        
        # Last resort: use monotonic time from boot
        # This won't be a real timestamp but at least won't crash
        print("[BinaryLog] Warning: Using monotonic time (RTC not set)")
        return int(time.monotonic() * 1000000)
        
    except Exception as e:
        print(f"[BinaryLog] Timestamp error: {e}, using monotonic")
        return int(time.monotonic() * 1000000)

# =============================================================================
# Constants
# =============================================================================

# Magic bytes "OPNY"
MAGIC = b'OPNY'
MAGIC_INT = 0x4F504E59

# Format version
FORMAT_VERSION_MAJOR = 2
FORMAT_VERSION_MINOR = 0

# Hardware version (from settings or default)
HARDWARE_VERSION_MAJOR = 1
HARDWARE_VERSION_MINOR = 0

# Block types
BLOCK_TYPE_SESSION_HEADER = 0x01
BLOCK_TYPE_DATA = 0x02
BLOCK_TYPE_SESSION_END = 0x03

# Flush flags (bitmask)
FLUSH_FLAG_TIME = 0x01      # Time-based flush (5 minutes)
FLUSH_FLAG_SIZE = 0x02      # Buffer full
FLUSH_FLAG_EVENT = 0x04     # High G-force event (>3g)
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
MAX_BLOCK_SIZE = 2048  # 2KB max block size (reduced for memory-constrained devices)
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


def sha256_checksum(data):
    """Calculate SHA-256 checksum, with fallback to CRC32"""
    if HAS_HASHLIB:
        return hashlib.sha256(data).digest()
    else:
        # Fallback: use repeated CRC32 to fill 32 bytes
        # Not cryptographically secure but provides integrity check
        result = bytearray(32)
        for i in range(8):
            # Use different initial values for each CRC to get 32 bytes
            crc = crc32(data, i * 0x12345678)
            result[i*4:(i+1)*4] = struct.pack('<I', crc)
        return bytes(result)


# =============================================================================
# UUID Generation (simple version for CircuitPython)
# =============================================================================

def generate_uuid():
    """Generate a simple UUID-like identifier"""
    try:
        import random
        # Generate 16 random bytes
        return bytes([random.randint(0, 255) for _ in range(16)])
    except:
        # Fallback: use timestamp-based UUID
        ts = int(time.monotonic() * 1000000)
        return struct.pack('<QQ', ts, ts ^ 0xDEADBEEF12345678)


# =============================================================================
# Session Header
# =============================================================================

class SessionHeader:
    """Represents a session header block"""
    
    def __init__(self, session_name="", driver_name="", vehicle_id="",
                 weather=WEATHER_UNKNOWN, ambient_temp_c=None):
        self.session_id = generate_uuid()
        self.timestamp = get_safe_timestamp()  # Microseconds (with fallback)
        self.session_name = session_name[:MAX_SESSION_NAME]
        self.driver_name = driver_name[:MAX_DRIVER_NAME]
        self.vehicle_id = vehicle_id[:MAX_VEHICLE_ID]
        self.weather = weather
        self.ambient_temp = int(ambient_temp_c * 10) if ambient_temp_c else 0
        self.config_checksum = self._calculate_config_checksum()
    
    def _calculate_config_checksum(self):
        """Calculate CRC32 of settings.toml"""
        try:
            with open('/settings.toml', 'rb') as f:
                return crc32(f.read())
        except:
            return 0
    
    def to_bytes(self):
        """Serialize session header to bytes"""
        # Build header without final checksum
        header = bytearray()
        
        # Magic and block type
        header.extend(MAGIC)
        header.append(BLOCK_TYPE_SESSION_HEADER)
        
        # Versions
        header.extend(struct.pack('<BB', FORMAT_VERSION_MAJOR, FORMAT_VERSION_MINOR))
        header.extend(struct.pack('<BB', HARDWARE_VERSION_MAJOR, HARDWARE_VERSION_MINOR))
        
        # Timestamp and session ID
        header.extend(struct.pack('<Q', self.timestamp))
        header.extend(self.session_id)
        
        # Session name (length-prefixed)
        name_bytes = self.session_name.encode('utf-8')[:MAX_SESSION_NAME]
        header.append(len(name_bytes))
        header.extend(name_bytes)
        
        # Driver name (length-prefixed)
        driver_bytes = self.driver_name.encode('utf-8')[:MAX_DRIVER_NAME]
        header.append(len(driver_bytes))
        header.extend(driver_bytes)
        
        # Vehicle ID (length-prefixed)
        # CircuitPython doesn't support errors= keyword, so filter manually
        vehicle_ascii = ''.join(c if ord(c) < 128 else '' for c in self.vehicle_id)
        vehicle_bytes = vehicle_ascii.encode('utf-8')[:MAX_VEHICLE_ID]
        header.append(len(vehicle_bytes))
        header.extend(vehicle_bytes)
        
        # Weather and temperature
        header.append(self.weather)
        header.extend(struct.pack('<h', self.ambient_temp))
        
        # Config checksum
        header.extend(struct.pack('<I', self.config_checksum))
        
        # Calculate and append header checksum
        header_checksum = crc32(bytes(header))
        header.extend(struct.pack('<I', header_checksum))
        
        return bytes(header)
    
    @classmethod
    def from_bytes(cls, data):
        """Deserialize session header from bytes"""
        if len(data) < 39:  # Minimum header size
            raise ValueError("Data too short for session header")
        
        # Verify magic
        if data[:4] != MAGIC:
            raise ValueError("Invalid magic bytes")
        
        # Verify block type
        if data[4] != BLOCK_TYPE_SESSION_HEADER:
            raise ValueError("Not a session header block")
        
        offset = 5
        
        # Parse versions
        format_major, format_minor = struct.unpack_from('<BB', data, offset)
        offset += 2
        hw_major, hw_minor = struct.unpack_from('<BB', data, offset)
        offset += 2
        
        # Parse timestamp and session ID
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        session_id = data[offset:offset+16]
        offset += 16
        
        # Parse session name
        name_len = data[offset]
        offset += 1
        session_name = data[offset:offset+name_len].decode('utf-8')
        offset += name_len
        
        # Parse driver name
        driver_len = data[offset]
        offset += 1
        driver_name = data[offset:offset+driver_len].decode('utf-8')
        offset += driver_len
        
        # Parse vehicle ID
        vehicle_len = data[offset]
        offset += 1
        vehicle_id = data[offset:offset+vehicle_len].decode('utf-8')
        offset += vehicle_len
        
        # Parse weather and temp
        weather = data[offset]
        offset += 1
        ambient_temp = struct.unpack_from('<h', data, offset)[0]
        offset += 2
        
        # Parse checksums
        config_checksum = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        header_checksum = struct.unpack_from('<I', data, offset)[0]
        
        # Verify header checksum
        calculated = crc32(data[:offset])
        if calculated != header_checksum:
            raise ValueError(f"Header checksum mismatch: {calculated} != {header_checksum}")
        
        # Create instance
        header = cls.__new__(cls)
        header.session_id = session_id
        header.timestamp = timestamp
        header.session_name = session_name
        header.driver_name = driver_name
        header.vehicle_id = vehicle_id
        header.weather = weather
        header.ambient_temp = ambient_temp
        header.config_checksum = config_checksum
        
        return header


# =============================================================================
# Data Block
# =============================================================================

class DataBlock:
    """Represents a data block with samples"""
    
    def __init__(self, session_id, sequence_number=0):
        self.session_id = session_id
        self.sequence_number = sequence_number
        self.samples = []
        self.timestamp_start = None
        self.timestamp_end = None
        self.flush_flags = 0
        self._data_size = 0
    
    def add_sample(self, sample_type, data, timestamp_us=None):
        """
        Add a sample to the block
        
        Args:
            sample_type: SAMPLE_TYPE_* constant
            data: bytes of sample data
            timestamp_us: timestamp in microseconds (optional)
        
        Returns:
            True if sample was added, False if block is full
        """
        if timestamp_us is None:
            timestamp_us = int(time.monotonic() * 1000000)
        
        if self.timestamp_start is None:
            self.timestamp_start = timestamp_us
        
        # Calculate timestamp offset in milliseconds
        offset_ms = (timestamp_us - self.timestamp_start) // 1000
        if offset_ms > 65535:
            # Offset too large, need new block
            return False
        
        # Check if adding this sample would exceed max payload
        sample_overhead = 4  # type (1) + offset (2) + length (1)
        if self._data_size + sample_overhead + len(data) > MAX_DATA_PAYLOAD:
            return False
        
        # Add sample
        self.samples.append({
            'type': sample_type,
            'offset_ms': offset_ms,
            'data': data
        })
        
        self._data_size += sample_overhead + len(data)
        self.timestamp_end = timestamp_us
        
        return True
    
    def should_flush(self, current_time_s=None, gforce_total=None):
        """
        Check if block should be flushed
        
        Returns:
            Flush flags if should flush, 0 otherwise
        """
        flags = 0
        
        # Check size threshold
        if self._data_size >= MAX_DATA_PAYLOAD * 0.9:  # 90% full
            flags |= FLUSH_FLAG_SIZE
        
        # Check time threshold
        if current_time_s is not None and self.timestamp_start is not None:
            start_s = self.timestamp_start / 1000000
            if current_time_s - start_s >= FLUSH_TIME_THRESHOLD:
                flags |= FLUSH_FLAG_TIME
        
        # Check G-force event threshold
        if gforce_total is not None and gforce_total >= FLUSH_GFORCE_THRESHOLD:
            flags |= FLUSH_FLAG_EVENT
        
        return flags
    
    def to_bytes(self, flush_flags=0):
        """Serialize data block to bytes"""
        self.flush_flags = flush_flags
        
        # Build block without final checksum
        block = bytearray()
        
        # Magic and block type
        block.extend(MAGIC)
        block.append(BLOCK_TYPE_DATA)
        
        # Block sequence and session ID
        block.extend(struct.pack('<I', self.sequence_number))
        block.extend(self.session_id)
        
        # Timestamps
        block.extend(struct.pack('<Q', self.timestamp_start or 0))
        block.extend(struct.pack('<Q', self.timestamp_end or 0))
        
        # Flush flags and counts
        block.append(self.flush_flags)
        block.extend(struct.pack('<H', len(self.samples)))
        
        # Build data payload
        payload = bytearray()
        for sample in self.samples:
            payload.append(sample['type'])
            payload.extend(struct.pack('<H', sample['offset_ms']))
            payload.append(len(sample['data']))
            payload.extend(sample['data'])
        
        # Data size and payload
        block.extend(struct.pack('<H', len(payload)))
        block.extend(payload)
        
        # Calculate and append SHA-256 checksum
        checksum = sha256_checksum(bytes(block))
        block.extend(checksum)
        
        return bytes(block)
    
    @classmethod
    def from_bytes(cls, data):
        """Deserialize data block from bytes"""
        if len(data) < 80:  # Minimum block size
            raise ValueError("Data too short for data block")
        
        # Verify magic
        if data[:4] != MAGIC:
            raise ValueError("Invalid magic bytes")
        
        # Verify block type
        if data[4] != BLOCK_TYPE_DATA:
            raise ValueError("Not a data block")
        
        offset = 5
        
        # Parse sequence and session ID
        sequence = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        session_id = data[offset:offset+16]
        offset += 16
        
        # Parse timestamps
        ts_start = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        ts_end = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # Parse flags and counts
        flush_flags = data[offset]
        offset += 1
        sample_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Parse data size
        data_size = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Extract checksum from end
        checksum = data[-32:]
        block_data = data[:-32]
        
        # Verify checksum
        calculated = sha256_checksum(block_data)
        if calculated != checksum:
            raise ValueError("Block checksum mismatch")
        
        # Parse samples
        samples = []
        payload_end = offset + data_size
        while offset < payload_end:
            sample_type = data[offset]
            offset += 1
            sample_offset = struct.unpack_from('<H', data, offset)[0]
            offset += 2
            sample_len = data[offset]
            offset += 1
            sample_data = data[offset:offset+sample_len]
            offset += sample_len
            
            samples.append({
                'type': sample_type,
                'offset_ms': sample_offset,
                'data': sample_data
            })
        
        # Create instance
        block = cls.__new__(cls)
        block.session_id = session_id
        block.sequence_number = sequence
        block.samples = samples
        block.timestamp_start = ts_start
        block.timestamp_end = ts_end
        block.flush_flags = flush_flags
        block._data_size = data_size
        
        return block


# =============================================================================
# Binary Logger Manager
# =============================================================================

class BinaryLogger:
    """Manages binary logging sessions and data blocks"""
    
    def __init__(self, log_dir="/sd/logs"):
        self.log_dir = log_dir
        self.current_session = None
        self.current_block = None
        self.block_sequence = 0
        self.log_file = None
        self.log_filename = None
        self._last_flush_time = 0
        
        # Ensure log directory exists
        try:
            os.mkdir(log_dir)
        except OSError:
            pass  # Directory exists
    
    def start_session(self, session_name="", driver_name="", vehicle_id="",
                      weather=WEATHER_UNKNOWN, ambient_temp_c=None):
        """
        Start a new logging session
        
        Creates a new session header and opens a new log file.
        """
        # Close any existing session
        if self.log_file is not None:
            self.stop_session()
        
        # Create session header
        self.current_session = SessionHeader(
            session_name=session_name,
            driver_name=driver_name,
            vehicle_id=vehicle_id,
            weather=weather,
            ambient_temp_c=ambient_temp_c
        )
        
        # Generate filename from timestamp
        try:
            ts = time.localtime(self.current_session.timestamp // 1000000)
            filename = f"session_{ts.tm_year:04d}{ts.tm_mon:02d}{ts.tm_mday:02d}_{ts.tm_hour:02d}{ts.tm_min:02d}{ts.tm_sec:02d}.opl"
        except (OverflowError, OSError):
            # RTC not set - use session ID hex for unique filename
            session_hex = ''.join(f'{b:02x}' for b in self.current_session.session_id[:8])
            filename = f"session_{session_hex}.opl"
        self.log_filename = f"{self.log_dir}/{filename}"
        
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
        self._last_flush_time = time.monotonic()
        
        print(f"[BinaryLog] Started session: {self.log_filename}")
        return self.current_session.session_id
    
    def restart_session(self, **kwargs):
        """
        Restart session (e.g., after settings change)
        
        Preserves session metadata if not provided.
        """
        old_session = self.current_session
        
        if old_session:
            # Use existing values as defaults
            kwargs.setdefault('session_name', old_session.session_name)
            kwargs.setdefault('driver_name', old_session.driver_name)
            kwargs.setdefault('vehicle_id', old_session.vehicle_id)
            kwargs.setdefault('weather', old_session.weather)
            kwargs.setdefault('ambient_temp_c', old_session.ambient_temp / 10 if old_session.ambient_temp else None)
        
        return self.start_session(**kwargs)
    
    def write_sample(self, sample_type, data, timestamp_us=None, gforce_total=None):
        """
        Write a sample to the current block
        
        Args:
            sample_type: SAMPLE_TYPE_* constant
            data: bytes of sample data
            timestamp_us: optional timestamp in microseconds
            gforce_total: optional G-force magnitude for event detection
        
        Returns:
            True if written successfully
        """
        if self.current_block is None or self.log_file is None:
            return False
        
        # Try to add sample to current block
        if not self.current_block.add_sample(sample_type, data, timestamp_us):
            # Block is full, flush and create new one
            self._flush_block(FLUSH_FLAG_SIZE)
        else:
            # Sample added, check if we should flush
            current_time = time.monotonic()
            flush_flags = self.current_block.should_flush(current_time, gforce_total)
            
            if flush_flags:
                self._flush_block(flush_flags)
        
        return True
    
    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        """Convenience method for accelerometer data"""
        data = struct.pack('<fff', gx, gy, gz)
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        return self.write_sample(
            SAMPLE_TYPE_ACCELEROMETER, 
            data, 
            timestamp_us,
            gforce_total=g_total
        )
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        """Convenience method for GPS fix data"""
        # Pack as int32 * 1e7 for lat/lon to preserve precision
        data = struct.pack(
            '<iiffff',
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            speed,
            heading,
            hdop
        )
        return self.write_sample(SAMPLE_TYPE_GPS_FIX, data, timestamp_us)
    
    def write_obd_pid(self, mode, pid, value, timestamp_us=None):
        """Convenience method for OBD-II PID data"""
        # Pack mode (1 byte), PID (2 bytes), value (4 bytes float)
        data = struct.pack('<BHf', mode, pid, value)
        return self.write_sample(SAMPLE_TYPE_OBD_PID, data, timestamp_us)
    
    def write_event(self, event_type, description="", timestamp_us=None):
        """Write an event marker"""
        desc_bytes = description.encode('utf-8')[:64]
        data = struct.pack('<B', event_type) + struct.pack('<B', len(desc_bytes)) + desc_bytes
        return self.write_sample(SAMPLE_TYPE_EVENT_MARKER, data, timestamp_us)
    
    def flush(self, flags=FLUSH_FLAG_MANUAL):
        """Force flush current block"""
        if self.current_block and len(self.current_block.samples) > 0:
            self._flush_block(flags)
    
    def _flush_block(self, flush_flags):
        """Internal method to flush current block and create new one"""
        if self.current_block is None or self.log_file is None:
            return
        
        if len(self.current_block.samples) == 0:
            return  # Nothing to flush
        
        # Write block directly to file (memory-efficient)
        self._write_block_to_file(flush_flags)
        
        # Log flush reason
        reasons = []
        if flush_flags & FLUSH_FLAG_TIME:
            reasons.append("time")
        if flush_flags & FLUSH_FLAG_SIZE:
            reasons.append("size")
        if flush_flags & FLUSH_FLAG_EVENT:
            reasons.append("event")
        if flush_flags & FLUSH_FLAG_MANUAL:
            reasons.append("manual")
        if flush_flags & FLUSH_FLAG_SHUTDOWN:
            reasons.append("shutdown")
        
        print(f"[BinaryLog] Flushed block {self.block_sequence} ({len(self.current_block.samples)} samples, reason: {'+'.join(reasons)})")
        
        # Create new block
        self.block_sequence += 1
        self.current_block = DataBlock(
            self.current_session.session_id,
            self.block_sequence
        )
        self._last_flush_time = time.monotonic()
    
    def _write_block_to_file(self, flush_flags):
        """Write block directly to file in chunks to save memory"""
        import gc
        
        block = self.current_block
        block.flush_flags = flush_flags
        
        # Pre-calculate payload size (without building it)
        payload_size = 0
        for sample in block.samples:
            payload_size += 1 + 2 + 1 + len(sample['data'])  # type + offset + len + data
        
        # Build header (small, fixed size ~45 bytes)
        header = bytearray()
        header.extend(MAGIC)
        header.append(BLOCK_TYPE_DATA)
        header.extend(struct.pack('<I', block.sequence_number))
        header.extend(block.session_id)
        header.extend(struct.pack('<Q', block.timestamp_start or 0))
        header.extend(struct.pack('<Q', block.timestamp_end or 0))
        header.append(block.flush_flags)
        header.extend(struct.pack('<H', len(block.samples)))
        header.extend(struct.pack('<H', payload_size))
        
        # Initialize checksum with header
        if HAS_HASHLIB:
            hasher = hashlib.sha256()
            hasher.update(header)
        else:
            # Fallback: simple checksum
            checksum_val = 0
            for b in header:
                checksum_val = (checksum_val + b) & 0xFFFFFFFF
        
        # Write header
        self.log_file.write(header)
        
        # Write samples one at a time and update checksum
        sample_buf = bytearray(32)  # Reusable buffer for small samples
        for sample in block.samples:
            # Build sample header (4 bytes)
            sample_buf[0] = sample['type']
            struct.pack_into('<H', sample_buf, 1, sample['offset_ms'])
            sample_buf[3] = len(sample['data'])
            
            sample_header = bytes(sample_buf[:4])
            sample_data = sample['data']
            
            # Update checksum
            if HAS_HASHLIB:
                hasher.update(sample_header)
                hasher.update(sample_data)
            else:
                for b in sample_header:
                    checksum_val = (checksum_val + b) & 0xFFFFFFFF
                for b in sample_data:
                    checksum_val = (checksum_val + b) & 0xFFFFFFFF
            
            # Write to file
            self.log_file.write(sample_header)
            self.log_file.write(sample_data)
        
        # Write checksum
        if HAS_HASHLIB:
            checksum = hasher.digest()
        else:
            checksum = struct.pack('<I', checksum_val) + b'\x00' * 28
        
        self.log_file.write(checksum)
        self.log_file.flush()
        
        # Clear samples to free memory
        block.samples.clear()
        gc.collect()
    
    def stop_session(self):
        """Stop current session and close log file"""
        if self.log_file is None:
            return
        
        # Flush any pending data
        self.flush(FLUSH_FLAG_SHUTDOWN)
        
        # Write session end marker
        end_block = bytearray()
        end_block.extend(MAGIC)
        end_block.append(BLOCK_TYPE_SESSION_END)
        end_block.extend(self.current_session.session_id)
        end_block.extend(struct.pack('<Q', int(time.time() * 1000000)))
        end_block.extend(struct.pack('<I', self.block_sequence))
        
        # Checksum
        checksum = crc32(bytes(end_block))
        end_block.extend(struct.pack('<I', checksum))
        
        self.log_file.write(bytes(end_block))
        self.log_file.close()
        
        print(f"[BinaryLog] Session ended: {self.block_sequence + 1} blocks written")
        print(f"[BinaryLog] Log file: {self.log_filename}")
        
        # Clean up
        self.log_file = None
        self.current_session = None
        self.current_block = None
    
    def get_stats(self):
        """Get current logging statistics"""
        return {
            'filename': self.log_filename,
            'blocks_written': self.block_sequence,
            'current_samples': len(self.current_block.samples) if self.current_block else 0,
            'session_id': self.current_session.session_id.hex() if self.current_session else None
        }


# =============================================================================
# Utility Functions
# =============================================================================

def read_log_file(filename):
    """
    Read and parse a complete log file
    
    Yields:
        (block_type, data) tuples
    """
    with open(filename, 'rb') as f:
        while True:
            # Read magic
            magic = f.read(4)
            if not magic:
                break
            
            if magic != MAGIC:
                raise ValueError(f"Invalid magic at offset {f.tell() - 4}")
            
            # Read block type
            block_type = f.read(1)[0]
            
            # Seek back to start of block
            f.seek(-5, 1)
            
            if block_type == BLOCK_TYPE_SESSION_HEADER:
                # Read session header (variable size, read until checksum)
                # This is complex - need to parse incrementally
                # For now, read a reasonable chunk
                header_data = f.read(256)
                yield ('session_header', SessionHeader.from_bytes(header_data))
                
            elif block_type == BLOCK_TYPE_DATA:
                # Read data block header to get size
                header = f.read(47)  # Fixed header portion
                data_size = struct.unpack_from('<H', header, 45)[0]
                remaining = f.read(data_size + 32)  # payload + checksum
                full_block = header + remaining
                yield ('data_block', DataBlock.from_bytes(full_block))
                
            elif block_type == BLOCK_TYPE_SESSION_END:
                # Read session end (fixed size)
                end_data = f.read(33)  # 5 + 16 + 8 + 4
                yield ('session_end', end_data)
                
            else:
                raise ValueError(f"Unknown block type: {block_type}")


def print_log_summary(filename):
    """Print summary of a log file"""
    print(f"\n{'='*60}")
    print(f"Log File Summary: {filename}")
    print('='*60)
    
    total_samples = 0
    total_blocks = 0
    
    for block_type, data in read_log_file(filename):
        if block_type == 'session_header':
            print(f"\nSession: {data.session_name}")
            print(f"  Driver: {data.driver_name}")
            print(f"  Vehicle: {data.vehicle_id}")
            print(f"  Started: {time.localtime(data.timestamp // 1000000)}")
            
        elif block_type == 'data_block':
            total_blocks += 1
            total_samples += len(data.samples)
            
        elif block_type == 'session_end':
            print(f"\nSession ended")
    
    print(f"\nTotal: {total_blocks} blocks, {total_samples} samples")
    print('='*60)
