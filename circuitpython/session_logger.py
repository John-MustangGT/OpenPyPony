"""
session_logger.py - Unified session logging (CSV and Binary formats)

Provides a common interface for logging that supports both formats
"""

import time
import os
from config import config

# Import binary logger
try:
    from binary_logger import BinaryLogger, WEATHER_UNKNOWN
    BINARY_AVAILABLE = True
except ImportError:
    BINARY_AVAILABLE = False
    print("[SessionLogger] Binary logging not available")


# =============================================================================
# Session Numbering (shared by both CSV and Binary formats)
# =============================================================================

def _file_exists(path):
    """Check if file exists"""
    try:
        os.stat(path)
        print(f"[Session Debug] File exists: {path}")
        return True
    except OSError as e:
        print(f"[Session Debug] File not found: {path} (error: {e})")
        return False


def _get_next_session_number(base_path="/sd"):
    """
    Get next session number from persistent counter
    
    Uses session_last.txt to track the last session number.
    Returns incremented number and updates the file.
    
    Returns:
        int: Next session number (1-99999)
    """
    counter_file = f"{base_path}/session_last.txt"
    print(f"[Session Debug] Looking for counter file: {counter_file}")
    n = 1
    
    # Try to read existing counter
    if _file_exists(counter_file):
        print(f"[Session Debug] Counter file exists, reading...")
        try:
            with open(counter_file, 'r') as f:
                line = f.readline().strip()
                print(f"[Session Debug] Read line: '{line}'")
                if line:
                    n = int(line)
                    print(f"[Session Debug] Parsed number: {n}")
                    n += 1
                    print(f"[Session Debug] Incremented to: {n}")
                else:
                    print(f"[Session Debug] Empty line, using n=1")
        except ValueError as e:
            print(f"[Session Debug] ValueError parsing number: {e}, resetting to 1")
            n = 1
        except OSError as e:
            print(f"[Session Debug] OSError reading file: {e}, resetting to 1")
            n = 1
    else:
        print(f"[Session Debug] Counter file doesn't exist, starting at 1")
    
    # Wrap at 99999 (5 digits)
    if n > 99999:
        print(f"[Session Debug] Number {n} > 99999, wrapping to 1")
        n = 1
    
    # Write new counter
    print(f"[Session Debug] Writing {n} to counter file...")
    try:
        with open(counter_file, 'w') as f:
            f.write(f"{n}\n")
            f.flush()  # Force write
        print(f"[Session Debug] Successfully wrote {n} to {counter_file}")
        
        # Verify write
        if _file_exists(counter_file):
            with open(counter_file, 'r') as f:
                verify = f.readline().strip()
                print(f"[Session Debug] Verification read: '{verify}'")
        else:
            print(f"[Session Debug] WARNING: File disappeared after write!")
            
    except OSError as e:
        print(f"[Session Debug] ERROR writing counter: {e}")
    
    print(f"[Session Debug] Returning session number: {n}")
    return n


def create_session_filename(base_path="/sd", extension="opl"):
    """
    Create session filename with sequential numbering
    
    Args:
        base_path: Base directory (default: /sd)
        extension: File extension (opl or csv)
    
    Returns:
        str: Full path like "/sd/session_00001.opl"
    """
    print(f"[Session Debug] create_session_filename called with base_path='{base_path}', extension='{extension}'")
    n = _get_next_session_number(base_path)
    filename = f"{base_path}/session_{n:05d}.{extension}"
    print(f"[Session Debug] Generated filename: {filename}")
    return filename


# =============================================================================
# CSV Logger
# =============================================================================

class CSVLogger:
    """CSV format logger"""
    
    def __init__(self, base_path="/sd"):
        self.base_path = base_path
        self.log_file = None
        self.log_filename = None
        self.sample_count = 0
        self.start_time = None
        self.bytes_written = 0
        self.active = False
    
    def start_session(self, session_name="", driver_name="", vehicle_id="", **kwargs):
        """Start new CSV logging session"""
        if self.active:
            self.stop_session()
        
        # Use sequential numbering
        self.log_filename = create_session_filename(self.base_path, 'csv')
        
        # Open log file
        self.log_file = open(self.log_filename, "w")
        
        # Write header with metadata
        header = f"# Session: {session_name}\n"
        header += f"# Driver: {driver_name}\n"
        header += f"# Vehicle: {vehicle_id}\n"
        header += f"# Start: {int(time.monotonic())}\n"
        header += "timestamp,gx,gy,gz,g_total,lat,lon,alt,speed,sats,hdop\n"
        
        self.log_file.write(header)
        self.bytes_written = len(header)
        self.active = True
        self.sample_count = 0
        self.start_time = time.monotonic()
        
        print(f"[CSVLog] Session started: {self.log_filename}")
        return int(time.monotonic())
    
    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        """Write accelerometer data (buffered until GPS data available)"""
        if not self.active:
            return False
        
        # Store for combining with GPS data
        self._last_accel = (gx, gy, gz)
        self._last_accel_time = timestamp_us or int(time.monotonic() * 1000000)
        return True
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        """Write GPS data combined with last accelerometer reading"""
        if not self.active:
            return False
        
        timestamp = timestamp_us or int(time.monotonic() * 1000000)
        
        # Get last accelerometer data
        if hasattr(self, '_last_accel'):
            gx, gy, gz = self._last_accel
        else:
            gx, gy, gz = 0.0, 0.0, 1.0
        
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        
        # Write CSV line
        line = f"{timestamp},{gx:.3f},{gy:.3f},{gz:.3f},{g_total:.3f},"
        line += f"{lat:.6f},{lon:.6f},{alt:.1f},{speed:.1f},0,{hdop:.1f}\n"
        
        self.log_file.write(line)
        self.bytes_written += len(line)
        self.sample_count += 1
        
        # Flush every 50 samples
        if self.sample_count % 50 == 0:
            self.log_file.flush()
        
        return True
    
    def write_gps_satellites(self, satellites, timestamp_us=None):
        """GPS satellites (not logged in CSV format)"""
        pass
    
    def stop_session(self):
        """Stop current session"""
        if not self.active:
            return
        
        self.log_file.flush()
        self.log_file.close()
        
        duration = time.monotonic() - self.start_time if self.start_time else 0
        print(f"[CSVLog] Session stopped: {self.sample_count} samples, {duration:.1f}s")
        
        self.active = False
        return self.log_filename
    
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


# =============================================================================
# Binary Logger Wrapper (adds session numbering)
# =============================================================================

class BinaryLoggerWrapper:
    """
    Wrapper around BinaryLogger that adds sequential session numbering
    
    This ensures both CSV and Binary formats use the same numbering scheme
    """
    
    def __init__(self, base_path="/sd"):
        self.base_path = base_path
        self.logger = BinaryLogger(base_path)
    
    def start_session(self, session_name="", driver_name="", vehicle_id="",
                     weather=None, ambient_temp=0, config_crc=0, include_hardware=True):
        """Start session with sequential filename"""
        print(f"[Session Debug] BinaryLoggerWrapper.start_session() called")
        print(f"  base_path: {self.base_path}")
        
        # Generate sequential filename
        print(f"[Session Debug] Calling create_session_filename()...")
        filename = create_session_filename(self.base_path, 'opl')
        print(f"[Session Debug] Got filename: {filename}")
        
        # Pass filename to BinaryLogger.start_session() so it doesn't generate its own
        print(f"[Session Debug] Calling logger.start_session() with filename parameter...")
        result = self.logger.start_session(
            session_name=session_name,
            driver_name=driver_name,
            vehicle_id=vehicle_id,
            weather=weather,
            ambient_temp=ambient_temp,
            config_crc=config_crc,
            include_hardware=include_hardware,
            filename=filename  # THIS IS THE KEY! Pass our sequential filename
        )
        print(f"[Session Debug] logger.start_session() returned: {result}")
        print(f"[Session Debug] Actual filename used: {self.logger.log_filename}")
        return result
    
    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        return self.logger.write_accelerometer(gx, gy, gz, timestamp_us)
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        return self.logger.write_gps(lat, lon, alt, speed, heading, hdop, timestamp_us)
    
    def write_gps_satellites(self, satellites, timestamp_us=None):
        return self.logger.write_gps_satellites(satellites, timestamp_us)
    
    def stop_session(self):
        return self.logger.stop_session()
    
    def get_duration(self):
        return self.logger.get_duration()
    
    def get_bytes_per_second(self):
        return self.logger.get_bytes_per_second()
    
    @property
    def active(self):
        return self.logger.active
    
    @property
    def log_filename(self):
        return self.logger.log_filename
    
    @property
    def sample_count(self):
        return 0  # Binary format doesn't track samples


# =============================================================================
# Unified Session Logger
# =============================================================================

class SessionLogger:
    """Unified logger that supports both CSV and Binary formats"""
    
    def __init__(self, base_path="/sd"):
        self.base_path = base_path
        self.format = config.log_format
        
        print(f"[SessionLogger Debug] __init__ called with base_path='{base_path}'")
        print(f"[SessionLogger Debug] config.log_format = '{self.format}'")
        print(f"[SessionLogger Debug] BINARY_AVAILABLE = {BINARY_AVAILABLE}")
        
        # Create appropriate logger
        if self.format == 'binary' and BINARY_AVAILABLE:
            print(f"[SessionLogger Debug] Creating BinaryLoggerWrapper...")
            self.logger = BinaryLoggerWrapper(base_path)
            print(f"[SessionLogger Debug] Created logger type: {type(self.logger)}")
            print(f"[SessionLogger Debug] Logger is BinaryLoggerWrapper: {isinstance(self.logger, BinaryLoggerWrapper)}")
            print(f"[SessionLogger] Using binary format")
        else:
            if self.format == 'binary':
                print(f"[SessionLogger] Binary format requested but not available, using CSV")
            self.logger = CSVLogger(base_path)
            print(f"[SessionLogger] Using CSV format")
    
    def start_session(self, session_name=None, driver_name=None, vehicle_id=None,
                     weather=None, ambient_temp=0, config_crc=0):
        """Start a new logging session"""
        print(f"[SessionLogger Debug] start_session() called")
        print(f"[SessionLogger Debug]   session_name={session_name}")
        print(f"[SessionLogger Debug]   driver_name={driver_name}")
        print(f"[SessionLogger Debug]   vehicle_id={vehicle_id}")
        print(f"[SessionLogger Debug]   weather={weather}")
        print(f"[SessionLogger Debug]   self.logger type: {type(self.logger)}")
        print(f"[SessionLogger Debug]   Is BinaryLoggerWrapper? {isinstance(self.logger, BinaryLoggerWrapper)}")
        
        # Use config defaults if not specified
        session_name = session_name or config.session_name
        driver_name = driver_name or config.driver_name
        vehicle_id = vehicle_id or config.vehicle_id
        
        # Binary format gets all metadata
        if isinstance(self.logger, BinaryLoggerWrapper):
            print(f"[SessionLogger Debug] Calling BinaryLoggerWrapper.start_session()...")
            weather = weather if weather is not None else WEATHER_UNKNOWN
            return self.logger.start_session(
                session_name, driver_name, vehicle_id,
                weather, ambient_temp, config_crc
            )
        else:
            print(f"[SessionLogger Debug] Calling CSVLogger.start_session()...")
            # CSV format gets basic metadata
            return self.logger.start_session(
                session_name, driver_name, vehicle_id
            )
    
    def write_accelerometer(self, gx, gy, gz, timestamp_us=None):
        """Write accelerometer data"""
        return self.logger.write_accelerometer(gx, gy, gz, timestamp_us)
    
    def write_gps(self, lat, lon, alt, speed, heading, hdop, timestamp_us=None):
        """Write GPS data"""
        return self.logger.write_gps(lat, lon, alt, speed, heading, hdop, timestamp_us)
    
    def write_gps_satellites(self, satellites, timestamp_us=None):
        """Write GPS satellite data (binary format only)"""
        if hasattr(self.logger, 'write_gps_satellites'):
            return self.logger.write_gps_satellites(satellites, timestamp_us)
        return True
    
    def stop_session(self):
        """Stop current session"""
        return self.logger.stop_session()
    
    def get_duration(self):
        """Get current session duration"""
        if hasattr(self.logger, 'get_duration'):
            return self.logger.get_duration()
        return 0
    
    def get_bytes_per_second(self):
        """Get average bytes per second"""
        if hasattr(self.logger, 'get_bytes_per_second'):
            return self.logger.get_bytes_per_second()
        return 0
    
    @property
    def active(self):
        """Check if logging is active"""
        return self.logger.active
    
    @property
    def filename(self):
        """Get current log filename"""
        return self.logger.log_filename if hasattr(self.logger, 'log_filename') else None
    
    @property
    def sample_count(self):
        """Get sample count (CSV only)"""
        return self.logger.sample_count if hasattr(self.logger, 'sample_count') else 0
