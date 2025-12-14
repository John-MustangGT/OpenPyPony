"""
storage.py - SD card, session and file management for OpenPonyLogger
"""

import os
import time
import storage
import sdcardio

from config import config

class FileManager:
    """Manage session files"""
    
    @staticmethod
    def list_files():
        """List all session files with metadata"""
        files = []
        
        try:
            for filename in os.listdir("/sd"):
                if filename.startswith("session_") and filename.endswith(".csv"):
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
        
    def start(self, driver="Unknown", vin="Unknown"):
        """Start new recording session"""
        self.driver_name = driver
        self.car_vin = vin
        
        timestamp = self.rtc_handler.get_time()
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
        if not self.active or not self.file:
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
        if self.file:
            self.file.flush()
            self.file.close()
        
        filename = self.filename
        self.active = False
        self.filename = None
        self.file = None
        
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
        return self.bytes_written / duration
