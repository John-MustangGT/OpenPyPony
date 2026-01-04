"""
logger.py - Data Logging System

Implements binary (.opl) and CSV loggers with GPS-gated data capture.
Reuses the proven v2 binary format with session/hardware headers.
"""

import struct
import time


class BinaryLogger:
    """
    Binary logger for .opl format
    
    Format:
    - Magic header: "OPL2"
    - Session metadata block (checksummed)
    - Hardware/config block (checksummed)
    - Data frames (checksummed)
    
    This reuses the proven v2 format from your existing implementation.
    """
    
    # Format constants
    MAGIC = b'OPL2'
    VERSION = 2
    HEADER_SIZE = 256
    FRAME_SIZE = 64
    
    def __init__(self, filepath, config, hardware_manifest):
        """
        Initialize binary logger
        
        Args:
            filepath: Path to .opl file
            config: Config object
            hardware_manifest: Hardware manifest dict from HAL
        """
        self.filepath = filepath
        self.config = config
        self.manifest = hardware_manifest
        self.file = None
        self.frame_count = 0
        self.buffer = []
        self.buffer_size = config.get('storage.buffer_size', 50)
        self.last_flush = time.monotonic()
        self.auto_flush_interval = config.get('storage.auto_flush_interval', 5000) / 1000
        
        print(f"[BinaryLogger] Initialized: {filepath}")
        print(f"[BinaryLogger] Buffer size: {self.buffer_size} frames")
    
    def open(self):
        """Open log file and write headers"""
        try:
            self.file = open(self.filepath, 'wb')
            
            # Write magic header
            self.file.write(self.MAGIC)
            
            # Write session metadata
            self._write_session_header()
            
            # Write hardware/config metadata
            self._write_hardware_header()
            
            self.file.flush()
            
            print(f"[BinaryLogger] Opened and wrote headers")
            
        except Exception as e:
            print(f"[BinaryLogger] Error opening file: {e}")
            self.file = None
    
    def _write_session_header(self):
        """Write session metadata block"""
        # Session header format (256 bytes):
        # - Version (2 bytes)
        # - Start timestamp (8 bytes, double)
        # - Driver name (32 bytes, null-terminated string)
        # - Vehicle ID (32 bytes, null-terminated string)
        # - Profile name (32 bytes, null-terminated string)
        # - Reserved (146 bytes)
        # - Checksum (4 bytes, CRC32)
        
        header_data = bytearray(self.HEADER_SIZE)
        offset = 0
        
        # Version
        struct.pack_into('<H', header_data, offset, self.VERSION)
        offset += 2
        
        # Start timestamp (Unix time)
        start_time = time.time()
        struct.pack_into('<d', header_data, offset, start_time)
        offset += 8
        
        # Driver name
        driver = self.config.get('general.Driver_name', 'Unknown')[:31]
        driver_bytes = (driver.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = driver_bytes
        offset += 32

        # Vehicle ID
        vehicle = self.config.get('general.Vehicle_id', 'Unknown')[:31]
        vehicle_bytes = (vehicle.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = vehicle_bytes
        offset += 32

        # Profile name
        profile = self.config.active_profile or 'default'
        profile = profile.split('.')[-1][:31]  # Get last part of 'general.daily'
        profile_bytes = (profile.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = profile_bytes
        offset += 32
        
        # Reserved space (for future use)
        # offset += 146 (already zeroed)
        
        # Calculate checksum (CRC32)
        checksum = self._crc32(header_data[:-4])
        struct.pack_into('<I', header_data, self.HEADER_SIZE - 4, checksum)
        
        # Write to file
        self.file.write(header_data)
    
    def _write_hardware_header(self):
        """Write hardware/config metadata block"""
        # Hardware header format (256 bytes):
        # - Hardware name (64 bytes, null-terminated)
        # - Accelerometer info (64 bytes, null-terminated)
        # - GPS info (64 bytes, null-terminated)
        # - RTC info (32 bytes, null-terminated)
        # - Display info (32 bytes, null-terminated)
        # - Gyroscope info (32 bytes, null-terminated)
        # - Reserved (32 bytes)
        # - Checksum (4 bytes, CRC32)

        header_data = bytearray(self.HEADER_SIZE)
        offset = 0

        # Hardware name
        hw_name = self.config.get('hardware.name', 'OpenPonyLogger')[:63]
        hw_bytes = (hw_name.encode('utf-8') + b'\x00' * 64)[:64]
        header_data[offset:offset+64] = hw_bytes
        offset += 64

        # Accelerometer
        accel_info = self.manifest.get('accelerometer', 'None')
        if accel_info:
            accel_info = str(accel_info)[:63]
        else:
            accel_info = 'None'
        accel_bytes = (accel_info.encode('utf-8') + b'\x00' * 64)[:64]
        header_data[offset:offset+64] = accel_bytes
        offset += 64

        # GPS
        gps_info = self.manifest.get('gps', 'None')
        if gps_info:
            gps_info = str(gps_info)[:63]
        else:
            gps_info = 'None'
        gps_bytes = (gps_info.encode('utf-8') + b'\x00' * 64)[:64]
        header_data[offset:offset+64] = gps_bytes
        offset += 64

        # RTC
        rtc_info = self.manifest.get('rtc', 'None')
        if rtc_info:
            rtc_info = str(rtc_info)[:31]
        else:
            rtc_info = 'None'
        rtc_bytes = (rtc_info.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = rtc_bytes
        offset += 32

        # Display
        display_info = self.manifest.get('display', 'None')
        if display_info:
            display_info = str(display_info)[:31]
        else:
            display_info = 'None'
        display_bytes = (display_info.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = display_bytes
        offset += 32

        # Gyroscope
        gyro_info = self.manifest.get('gyroscope', 'None')
        if gyro_info:
            gyro_info = str(gyro_info)[:31]
        else:
            gyro_info = 'None'
        gyro_bytes = (gyro_info.encode('utf-8') + b'\x00' * 32)[:32]
        header_data[offset:offset+32] = gyro_bytes
        offset += 32

        # Reserved
        # offset += 32 (already zeroed)
        
        # Checksum
        checksum = self._crc32(header_data[:-4])
        struct.pack_into('<I', header_data, self.HEADER_SIZE - 4, checksum)
        
        # Write to file
        self.file.write(header_data)
    
    def log_frame(self, gps_data, accel_data, timestamp, gyro_data=None):
        """
        Log a data frame

        Args:
            gps_data: dict with GPS data (lat, lon, alt, speed, etc.)
            accel_data: dict with accelerometer data (gx, gy, gz)
            timestamp: Unix timestamp (float)
            gyro_data: dict with gyroscope data (rx, ry, rz) [optional]
        """
        if not self.file:
            return

        # Create frame (64 bytes):
        # - Timestamp (8 bytes, double)
        # - GPS latitude (8 bytes, double)
        # - GPS longitude (8 bytes, double)
        # - GPS altitude (4 bytes, float)
        # - GPS speed (4 bytes, float)
        # - GPS satellites (1 byte)
        # - Reserved (1 byte)
        # - Accel gx (4 bytes, float)
        # - Accel gy (4 bytes, float)
        # - Accel gz (4 bytes, float)
        # - Gyro rx (4 bytes, float)
        # - Gyro ry (4 bytes, float)
        # - Gyro rz (4 bytes, float)
        # - Reserved (8 bytes)
        # - Checksum (4 bytes, CRC32)
        
        frame_data = bytearray(self.FRAME_SIZE)
        offset = 0
        
        # Timestamp
        struct.pack_into('<d', frame_data, offset, timestamp)
        offset += 8
        
        # GPS data
        struct.pack_into('<d', frame_data, offset, gps_data.get('lat', 0.0))
        offset += 8
        struct.pack_into('<d', frame_data, offset, gps_data.get('lon', 0.0))
        offset += 8
        struct.pack_into('<f', frame_data, offset, gps_data.get('alt', 0.0))
        offset += 4
        struct.pack_into('<f', frame_data, offset, gps_data.get('speed', 0.0))
        offset += 4
        # Satellites - ensure value fits in unsigned byte (0-255)
        sats = gps_data.get('satellites', 0)
        if sats is None or not isinstance(sats, (int, float)):
            sats = 0
        sats = max(0, min(255, int(sats)))
        struct.pack_into('<B', frame_data, offset, sats)
        offset += 1
        
        # Reserved
        offset += 1
        
        # Accelerometer data
        struct.pack_into('<f', frame_data, offset, accel_data.get('gx', 0.0))
        offset += 4
        struct.pack_into('<f', frame_data, offset, accel_data.get('gy', 0.0))
        offset += 4
        struct.pack_into('<f', frame_data, offset, accel_data.get('gz', 0.0))
        offset += 4

        # Gyroscope data (optional)
        if gyro_data:
            struct.pack_into('<f', frame_data, offset, gyro_data.get('rx', 0.0))
            offset += 4
            struct.pack_into('<f', frame_data, offset, gyro_data.get('ry', 0.0))
            offset += 4
            struct.pack_into('<f', frame_data, offset, gyro_data.get('rz', 0.0))
            offset += 4
        else:
            offset += 12  # Skip gyro data if not available

        # Reserved (for future expansion)
        # offset += 8 (already zeroed)
        
        # Checksum
        checksum = self._crc32(frame_data[:-4])
        struct.pack_into('<I', frame_data, self.FRAME_SIZE - 4, checksum)
        
        # Add to buffer
        self.buffer.append(bytes(frame_data))
        self.frame_count += 1
        
        # Check if we should flush
        current_time = time.monotonic()
        buffer_full = len(self.buffer) >= self.buffer_size
        time_elapsed = (current_time - self.last_flush) >= self.auto_flush_interval
        high_gforce = self._check_high_gforce(accel_data)
        
        if buffer_full or time_elapsed or high_gforce:
            self.flush()
    
    def _check_high_gforce(self, accel_data):
        """Check if current G-force exceeds threshold"""
        if not self.config.get('storage.flush_on_gforce', True):
            return False
        
        threshold = self.config.get('general.Gforce_Event_threshold', 2.5)
        
        gx = accel_data.get('gx', 0.0)
        gy = accel_data.get('gy', 0.0)
        gz = accel_data.get('gz', 1.0)
        
        # Total G-force magnitude
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        
        return g_total >= threshold
    
    def flush(self):
        """Flush buffered frames to file"""
        if not self.file or not self.buffer:
            return
        
        try:
            # Write all buffered frames
            for frame in self.buffer:
                self.file.write(frame)
            
            # Flush to disk
            self.file.flush()
            
            frame_count = len(self.buffer)
            self.buffer.clear()
            self.last_flush = time.monotonic()
            
            if frame_count > 0:
                print(f"[BinaryLogger] Flushed {frame_count} frame(s)")
            
        except Exception as e:
            print(f"[BinaryLogger] Error flushing: {e}")
    
    def close(self):
        """Close log file"""
        if self.file:
            # Flush remaining buffer
            self.flush()
            
            # Close file
            self.file.close()
            self.file = None
            
            print(f"[BinaryLogger] Closed: {self.frame_count} frames written")
    
    def _crc32(self, data):
        """
        Calculate CRC32 checksum
        
        Args:
            data: bytes to checksum
            
        Returns:
            int: CRC32 checksum
        """
        # Simple CRC32 implementation
        # For production, use binascii.crc32 if available
        crc = 0xFFFFFFFF
        
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
        
        return crc ^ 0xFFFFFFFF


class CSVLogger:
    """
    Simple CSV logger (fallback)
    
    Logs basic data to CSV file when binary logging not desired.
    """
    
    def __init__(self, filepath, config):
        """
        Initialize CSV logger
        
        Args:
            filepath: Path to .csv file
            config: Config object
        """
        self.filepath = filepath
        self.config = config
        self.file = None
        self.frame_count = 0
        self.buffer = []
        self.buffer_size = config.get('storage.buffer_size', 50)
        
        print(f"[CSVLogger] Initialized: {filepath}")
    
    def open(self):
        """Open CSV file and write header"""
        try:
            self.file = open(self.filepath, 'w')

            # Write CSV header
            header = "timestamp,lat,lon,alt,speed,satellites,gx,gy,gz,rx,ry,rz\n"
            self.file.write(header)
            self.file.flush()

            print(f"[CSVLogger] Opened and wrote header")

        except Exception as e:
            print(f"[CSVLogger] Error opening file: {e}")
            self.file = None
    
    def log_frame(self, gps_data, accel_data, timestamp, gyro_data=None):
        """
        Log a data frame to CSV

        Args:
            gps_data: dict with GPS data
            accel_data: dict with accelerometer data
            timestamp: Unix timestamp (float)
            gyro_data: dict with gyroscope data [optional]
        """
        if not self.file:
            return

        # Format CSV line
        line = "{:.3f},{:.6f},{:.6f},{:.1f},{:.2f},{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}\n".format(
            timestamp,
            gps_data.get('lat', 0.0),
            gps_data.get('lon', 0.0),
            gps_data.get('alt', 0.0),
            gps_data.get('speed', 0.0),
            gps_data.get('satellites', 0),
            accel_data.get('gx', 0.0),
            accel_data.get('gy', 0.0),
            accel_data.get('gz', 1.0),
            gyro_data.get('rx', 0.0) if gyro_data else 0.0,
            gyro_data.get('ry', 0.0) if gyro_data else 0.0,
            gyro_data.get('rz', 0.0) if gyro_data else 0.0
        )
        
        # Add to buffer
        self.buffer.append(line)
        self.frame_count += 1
        
        # Flush if buffer full
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self):
        """Flush buffered lines to file"""
        if not self.file or not self.buffer:
            return
        
        try:
            # Write all buffered lines
            for line in self.buffer:
                self.file.write(line)
            
            # Flush to disk
            self.file.flush()
            
            line_count = len(self.buffer)
            self.buffer.clear()
            
            if line_count > 0:
                print(f"[CSVLogger] Flushed {line_count} line(s)")
            
        except Exception as e:
            print(f"[CSVLogger] Error flushing: {e}")
    
    def close(self):
        """Close CSV file"""
        if self.file:
            # Flush remaining buffer
            self.flush()
            
            # Close file
            self.file.close()
            self.file = None
            
            print(f"[CSVLogger] Closed: {self.frame_count} lines written")


def create_logger(filepath, config, hardware_manifest=None):
    """
    Factory function to create appropriate logger
    
    Args:
        filepath: Path to log file
        config: Config object
        hardware_manifest: Hardware manifest dict (for binary logger)
        
    Returns:
        BinaryLogger or CSVLogger
    """
    log_format = config.get('storage.log_format', 'binary')
    
    if log_format == 'binary':
        return BinaryLogger(filepath, config, hardware_manifest or {})
    elif log_format == 'csv':
        return CSVLogger(filepath, config)
    else:
        print(f"[Logger] Unknown format '{log_format}', using binary")
        return BinaryLogger(filepath, config, hardware_manifest or {})
