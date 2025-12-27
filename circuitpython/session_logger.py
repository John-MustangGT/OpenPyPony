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
        
        # Import sdcard helper
        try:
            from sdcard import get_sdcard
            sd = get_sdcard()
            if sd and sd.mounted:
                self.log_filename = sd.create_session_filename('csv')
            else:
                # Fallback to timestamp-based naming
                timestamp = int(time.monotonic())
                self.log_filename = f"{self.base_path}/session_{timestamp}.csv"
        except:
            # Fallback to timestamp-based naming
            timestamp = int(time.monotonic())
            self.log_filename = f"{self.base_path}/session_{timestamp}.csv"
        
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


class SessionLogger:
    """Unified logger that supports both CSV and Binary formats"""
    
    def __init__(self, base_path="/sd"):
        self.base_path = base_path
        self.format = config.log_format
        
        # Create appropriate logger
        if self.format == 'binary' and BINARY_AVAILABLE:
            self.logger = BinaryLogger(base_path)
            print(f"[SessionLogger] Using binary format")
        else:
            if self.format == 'binary':
                print(f"[SessionLogger] Binary format requested but not available, using CSV")
            self.logger = CSVLogger(base_path)
            print(f"[SessionLogger] Using CSV format")
    
    def start_session(self, session_name=None, driver_name=None, vehicle_id=None,
                     weather=None, ambient_temp=0, config_crc=0):
        """Start a new logging session"""
        # Use config defaults if not specified
        session_name = session_name or config.session_name
        driver_name = driver_name or config.driver_name
        vehicle_id = vehicle_id or config.vehicle_id
        
        # Binary format gets all metadata
        if isinstance(self.logger, BinaryLogger):
            weather = weather if weather is not None else WEATHER_UNKNOWN
            return self.logger.start_session(
                session_name, driver_name, vehicle_id,
                weather, ambient_temp, config_crc
            )
        else:
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
