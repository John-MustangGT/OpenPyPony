"""
sdcard.py - SD card, session and file management for OpenPonyLogger
"""

import os
import time
import storage
import sdcardio
import struct

from config import config
from binary_format import BinaryLogger, SAMPLE_TYPE_ACCELEROMETER, SAMPLE_TYPE_GPS_FIX

class FileManager:
    """Manage session files"""
    
    @staticmethod
    def list_files():
        """List all session files with metadata"""
        files = []
        
        try:
            for filename in os.listdir("/sd"):
                if filename.startswith("session_") and (filename.endswith(".csv") or filename.endswith(".bin")):
                    filepath = f"/sd/{filename}"
                    stat = os.stat(filepath)
                    size = stat[6]
                    mtime = stat[8]
                    
                    # Try to read metadata from file
                    driver = "Unknown"
                    vin = "Unknown"
                    
                    try:
                        with open(filepath, 'r') as f:
                            for _ in range(3):  # Read first 3 lines
                                line = f.readline()
                                if line.startswith("# Driver:"):
                                    driver = line.split(":", 1)[1].strip()
                                elif line.startswith("# VIN:"):
                                    vin = line.split(":", 1)[1].strip()
                    except:
                        pass
                    
                    files.append({
                        "file": filename,
                        "size": size,
                        "mtime": mtime,
                        "driver": driver,
                        "vin": vin
                    })
            
            # Sort by filename (newest first)
            files.sort(key=lambda x: x["mtime"], reverse=True)
            
        except Exception as e:
            print(f"Error listing files: {e}")
        
        return files
    
    @staticmethod
    def delete_file(filename):
        """Delete a session file"""
        filepath = f"/sd/{filename}"
        try:
            os.remove(filepath)
            print(f"✓ Deleted: {filename}")
            return True
        except Exception as e:
            print(f"✗ Error deleting {filename}: {e}")
            return False

class Session:
    def __init__(self, rtc_handler):
        self.active = False
        self.file = None
        self.filename = None
        self.sample_count = 0
        self.start_time = None
        self.bytes_written = 0
        self.driver_name = "Unknown"
        self.car_vin = "Unknown"
        self.rtc_handler = rtc_handler
        self.log_flush_size = config.get_int("LOG_FLUSH_SIZE", 50)
        self.log_format = config.get("LOGGING_FORMAT", "binary")
        self.binary_logger = None
        
    def start(self, driver="Unknown", vin="Unknown"):
        """Start new recording session"""
        self.driver_name = driver
        self.car_vin = vin
        
        timestamp = self.rtc_handler.get_time()
        
        if self.log_format == "binary":
            self.binary_logger = BinaryLogger(log_dir="/sd")
            self.binary_logger.start_session(session_name=f"session_{timestamp}", driver_name=driver, vehicle_id=vin)
            self.filename = self.binary_logger.log_filename
        else: # csv
            self.filename = f"session_{timestamp}.csv"
            filepath = f"/sd/{self.filename}"
            self.file = open(filepath, "w")
            # Write header with metadata
            header = f"# Driver: {driver}\n"
            header += f"# VIN: {vin}\n"
            header += f"# Start: {timestamp}\n"
            header += "timestamp,gx,gy,gz,g_total,lat,lon,alt,speed,sats,hdop\n"
            self.file.write(header)
            self.bytes_written = len(header)

        self.active = True
        self.sample_count = 0
        self.start_time = time.monotonic()
        
        print(f"✓ Session started: {self.filename}")
        return self.filename
    
    def log(self, data):
        """Write data to current session"""
        if not self.active:
            return

        if self.log_format == "binary":
            if self.binary_logger:
                timestamp_us = data['t'] * 1000000
                self.binary_logger.write_accelerometer(data['g']['x'], data['g']['y'], data['g']['z'], timestamp_us=timestamp_us)
                
                # The binary format specifies heading, which is not in the sensor data. I will add a dummy value.
                self.binary_logger.write_gps(data['gps']['lat'], data['gps']['lon'], data['gps']['alt'], data['gps']['speed'], data['gps']['heading'], data['gps']['hdop'], timestamp_us=timestamp_us)
        else: # csv
            if not self.file:
                return
            # CSV format
            line = f"{data['t']},{data['g']['x']},{data['g']['y']},{data['g']['z']},"
            line += f"{data['g']['total']},{data['gps']['lat']},{data['gps']['lon']},"
            line += f"{data['gps']['alt']},{data['gps']['speed']},{data['gps']['sats']},"
            line += f"{data['gps']['hdop']}\n"
            
            self.file.write(line)
            self.bytes_written += len(line)
            self.sample_count += 1
            
            # Flush every N samples
            if self.sample_count % self.log_flush_size == 0:
                self.file.flush()
    
    def stop(self):
        """Stop current session"""
        if self.log_format == "binary":
            if self.binary_logger:
                self.binary_logger.stop_session()
        else: # csv
            if self.file:
                self.file.flush()
                self.file.close()
        
        filename = self.filename
        self.active = False
        self.filename = None
        self.file = None
        self.binary_logger = None
        
        duration = time.monotonic() - self.start_time if self.start_time else 0
        print(f"✓ Session stopped: {self.sample_count} samples, {duration:.1f}s")
        return filename
    
    def get_duration(self):
        """Get current session duration"""
        if not self.active or not self.start_time:
            return 0
        return time.monotonic() - self.start_time
    
    def get_bytes_per_second(self):
        """Get average bytes per second for this session"""
        duration = self.get_duration()
        if duration <= 0:
            return 0
        if self.log_format == "binary":
            # This is not accurate for binary format, as the size is not tracked here.
            # The BinaryLogger does not expose the total bytes written.
            # Returning a placeholder value.
            return 0
        else:
            return self.bytes_written / duration
