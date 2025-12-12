"""
logger.py - OpenPonyLogger Pico Firmware v2.1
Enhanced with JSON protocol and improved display
"""

import os
import board
import busio
import time
import digitalio
import adafruit_lis3dh
import adafruit_gps
import displayio
import terminalio
from adafruit_display_text import label
import i2cdisplaybus
import adafruit_displayio_ssd1306
import storage
import sdcardio
import json
import rtc
import math

# ============================================================================
# Hardware Setup
# ============================================================================

print("OpenPonyLogger v2.1 - Initializing...")

# I2C (Accelerometer + OLED)
i2c = board.STEMMA_I2C()

# LIS3DH Accelerometer
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x18)
lis3dh.range = adafruit_lis3dh.RANGE_2_G
lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ

# GPS (UART)
gps_uart = busio.UART(board.GP8, board.GP9, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(gps_uart, debug=False)
gps.send_command(b'PMTK314,0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0')  # GGA + RMC + GSV
gps.send_command(b'PMTK220,1000')  # 1Hz update

# SD Card
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
sdcard = sdcardio.SDCard(spi, board.GP17)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# Get SD card capacity
sd_stat = os.statvfs("/sd")
sd_total_bytes = sd_stat[0] * sd_stat[2]
sd_free_bytes = sd_stat[0] * sd_stat[3]

# OLED Display
displayio.release_displays()
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# UART to ESP-01S (SoftwareSerial compatible)
esp_uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=0.1)

# RTC
rtc_clock = rtc.RTC()
rtc_synced = False

print("✓ Hardware initialized")

# ============================================================================
# Display Setup
# ============================================================================

splash = displayio.Group()
display.root_group = splash

line1 = label.Label(terminalio.FONT, text="--:--:-- NoFix [  ]", color=0xFFFFFF, x=0, y=5)
line2 = label.Label(terminalio.FONT, text="--- --'-- N --- --'-- W", color=0xFFFFFF, x=0, y=17)
line3 = label.Label(terminalio.FONT, text="0MPH  0.00g", color=0xFFFFFF, x=0, y=29)
line4 = label.Label(terminalio.FONT, text="NoLog 00:00:00", color=0xFFFFFF, x=0, y=41)
line5 = label.Label(terminalio.FONT, text="SD: --h --m remain", color=0xFFFFFF, x=0, y=53)

for line in [line1, line2, line3, line4, line5]:
    splash.append(line)

# ============================================================================
# Utility Functions
# ============================================================================

def format_dms(decimal_degrees, is_latitude=True):
    """Convert decimal degrees to DMS format"""
    if decimal_degrees is None or decimal_degrees == 0:
        return "--- --'--" + (" N" if is_latitude else " W")
    
    # Determine hemisphere
    if is_latitude:
        hemisphere = "N" if decimal_degrees >= 0 else "S"
    else:
        hemisphere = "E" if decimal_degrees >= 0 else "W"
    
    # Convert to positive
    decimal_degrees = abs(decimal_degrees)
    
    # Extract degrees, minutes, seconds
    degrees = int(decimal_degrees)
    minutes_decimal = (decimal_degrees - degrees) * 60
    minutes = int(minutes_decimal)
    seconds = int((minutes_decimal - minutes) * 60)
    
    return f"{degrees:3d}°{minutes:2d}'{seconds:2d}\"{hemisphere}"

def hdop_to_bars(hdop):
    """Convert HDOP to signal strength bars (0-3)"""
    if hdop is None or hdop == 0:
        return 0
    elif hdop < 1.5:
        return 3  # Excellent
    elif hdop < 3.0:
        return 2  # Good
    elif hdop < 5.0:
        return 1  # Fair
    else:
        return 0  # Poor

def format_time_hms(seconds):
    """Format seconds as HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def estimate_recording_time(free_bytes, bytes_per_second):
    """Estimate remaining recording time"""
    if bytes_per_second <= 0:
        return "Unknown"
    
    seconds_remaining = free_bytes / bytes_per_second
    hours = int(seconds_remaining // 3600)
    minutes = int((seconds_remaining % 3600) // 60)
    
    if hours > 99:
        return "99h+"
    elif hours > 0:
        return f"{hours:2d}h {minutes:2d}m"
    else:
        return f"{minutes:3d}m"

# ============================================================================
# Session Management
# ============================================================================

class Session:
    def __init__(self):
        self.active = False
        self.file = None
        self.filename = None
        self.sample_count = 0
        self.start_time = None
        self.bytes_written = 0
        self.driver_name = "Unknown"
        self.car_vin = "Unknown"
        
    def start(self, driver="Unknown", vin="Unknown"):
        """Start new recording session"""
        self.driver_name = driver
        self.car_vin = vin
        
        timestamp = time.time() if rtc_synced else int(time.monotonic())
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
        
        # Flush every 50 samples
        if self.sample_count % 50 == 0:
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

session = Session()

# ============================================================================
# Satellite Tracker
# ============================================================================

class SatelliteTracker:
    """Track GPS satellites from GSV sentences"""
    
    def __init__(self):
        self.satellites = {}
        self.last_update = 0
    
    def update(self, gps_obj):
        """Update satellite data from GPS"""
        # Note: adafruit_gps doesn't expose GSV data directly
        # We'll need to parse it manually or use available data
        # For now, create mock satellite data based on signal
        
        if gps_obj.satellites and gps_obj.satellites > 0:
            # Generate approximate satellite data
            self.satellites = {}
            for i in range(min(gps_obj.satellites, 12)):
                self.satellites[i+1] = {
                    "id": i + 1,
                    "elevation": 30 + (i * 5) % 60,
                    "azimuth": (i * 30) % 360,
                    "snr": 25 + (i * 3) % 30
                }
            self.last_update = time.monotonic()
    
    def get_json(self):
        """Get satellites as JSON"""
        return {
            "type": "satellites",
            "count": len(self.satellites),
            "satellites": list(self.satellites.values())
        }

sat_tracker = SatelliteTracker()

# ============================================================================
# File Manager
# ============================================================================

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
                        "driver": driver,
                        "vin": vin
                    })
            
            # Sort by filename (newest first)
            files.sort(key=lambda x: x["file"], reverse=True)
            
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

# ============================================================================
# JSON Protocol Handler (FIXED)
# ============================================================================

class JSONProtocol:
    """Handle JSON commands from ESP-01S"""
    
    def __init__(self, uart):
        self.uart = uart
        self.buffer = ""
        self.chunk_size = 512
    
    def process(self):
        """Check for incoming commands"""
        if self.uart.in_waiting:
            try:
                # Read available bytes
                data = self.uart.read(self.uart.in_waiting)
                
                # Decode with error handling
                try:
                    decoded = data.decode('utf-8')
                except UnicodeError:
                    # Try with 'ignore' error handler
                    decoded = data.decode('utf-8', 'ignore')
                    print("Warning: Ignored invalid UTF-8 bytes")
                
                self.buffer += decoded
                
                # Process complete JSON objects (newline delimited)
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        self.handle_line(line)
                        
            except Exception as e:
                print(f"Serial process error: {e}")
                # Clear buffer on error
                self.buffer = ""
    
    def handle_line(self, line):
        """Process a single line of JSON"""
        try:
            cmd = json.loads(line)
            self.handle_command(cmd)
        except ValueError as e:
            # JSON decode error
            print(f"JSON decode error: {e}")
            print(f"Invalid JSON: {line[:50]}...")  # Show first 50 chars
        except Exception as e:
            print(f"Line handling error: {e}")
    
    def handle_command(self, cmd):
        """Execute command"""
        try:
            cmd_type = cmd.get("cmd", "")
            
            if cmd_type == "LIST":
                self.send_file_list()
            
            elif cmd_type == "GET":
                filename = cmd.get("file", "")
                if filename:
                    self.send_file(filename)
                else:
                    self.send_error("Missing file parameter")
            
            elif cmd_type == "DELETE":
                filename = cmd.get("file", "")
                if filename:
                    success = FileManager.delete_file(filename)
                    if success:
                        self.send_response({"type": "ok", "message": "File deleted"})
                    else:
                        self.send_error("Delete failed")
                else:
                    self.send_error("Missing file parameter")
            
            elif cmd_type == "START_SESSION":
                driver = cmd.get("driver", "Unknown")
                vin = cmd.get("vin", "Unknown")
                filename = session.start(driver, vin)
                self.send_response({
                    "type": "ok",
                    "message": "Session started",
                    "file": filename
                })
            
            elif cmd_type == "STOP_SESSION":
                if session.active:
                    filename = session.stop()
                    self.send_response({
                        "type": "ok",
                        "message": "Session stopped",
                        "file": filename
                    })
                else:
                    self.send_error("No active session")
            
            elif cmd_type == "GET_SATELLITES":
                self.send_satellites()
            
            else:
                print(f"Unknown command: {cmd_type}")
                
        except Exception as e:
            print(f"Command handling error: {e}")
            self.send_error(f"Error: {e}")
    
    def send_file_list(self):
        """Send list of session files"""
        try:
            files = FileManager.list_files()
            response = {
                "type": "files",
                "count": len(files),
                "files": files
            }
            self.send_json(response)
        except Exception as e:
            print(f"File list error: {e}")
            self.send_error(f"List error: {e}")
    
    def send_file(self, filename):
        """Send file contents in chunks"""
        filepath = f"/sd/{filename}"
        
        try:
            stat = os.stat(filepath)
            file_size = stat[6]
            
            # Send file start
            self.send_json({
                "type": "file_start",
                "file": filename,
                "size": file_size
            })
            
            # Send file data in chunks
            with open(filepath, 'r') as f:
                chunk_num = 0
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    self.send_json({
                        "type": "file_chunk",
                        "file": filename,
                        "chunk": chunk_num,
                        "data": chunk
                    })
                    chunk_num += 1
                    time.sleep(0.05)  # Small delay between chunks
            
            # Send file end
            self.send_json({
                "type": "file_end",
                "file": filename,
                "chunks": chunk_num
            })
            
        except OSError as e:
            print(f"File error: {e}")
            self.send_error(f"File error: {e}")
        except Exception as e:
            print(f"Send file error: {e}")
            self.send_error(f"Error: {e}")
    
    def send_satellites(self):
        """Send satellite data"""
        try:
            self.send_json(sat_tracker.get_json())
        except Exception as e:
            print(f"Satellite send error: {e}")
    
    def send_response(self, response):
        """Send generic response"""
        self.send_json(response)
    
    def send_error(self, message):
        """Send error response"""
        try:
            self.send_json({
                "type": "error",
                "message": str(message)
            })
        except Exception as e:
            print(f"Error sending error: {e}")
    
    def send_json(self, obj):
        """Send JSON object"""
        try:
            json_str = json.dumps(obj) + "\n"
            self.uart.write(json_str.encode('utf-8'))
        except Exception as e:
            print(f"JSON send error: {e}")
protocol = JSONProtocol(esp_uart)

# ============================================================================
# Sensor Reading
# ============================================================================

def read_sensors():
    """Read all sensors and return data packet"""
    
    # Accelerometer
    x, y, z = lis3dh.acceleration
    gx, gy, gz = x/9.81, y/9.81, z/9.81
    g_total = (gx**2 + gy**2 + gz**2)**0.5
    
    # GPS
    gps.update()
    lat = gps.latitude if gps.has_fix else 0.0
    lon = gps.longitude if gps.has_fix else 0.0
    alt = gps.altitude_m if gps.altitude_m else 0.0
    speed_knots = gps.speed_knots if gps.speed_knots else 0.0
    speed_mph = speed_knots * 1.15078  # Convert knots to MPH
    sats = gps.satellites if gps.satellites else 0
    hdop = gps.hdop if gps.hdop else 0.0
    
    # Determine fix type
    if not gps.has_fix:
        fix_type = "NoFix"
    elif gps.fix_quality_3d:
        fix_type = "3D"
    else:
        fix_type = "2D"
    
    # RTC sync from GPS
    global rtc_synced
    if gps.has_fix and not rtc_synced and gps.timestamp_utc:
        try:
            rtc_clock.datetime = time.struct_time((
                gps.timestamp_utc.tm_year,
                gps.timestamp_utc.tm_mon,
                gps.timestamp_utc.tm_mday,
                gps.timestamp_utc.tm_hour,
                gps.timestamp_utc.tm_min,
                gps.timestamp_utc.tm_sec,
                0, -1, -1
            ))
            rtc_synced = True
            print("✓ RTC synced from GPS")
        except:
            pass
    
    # Update satellite tracker
    sat_tracker.update(gps)
    
    return {
        "t": time.time() if rtc_synced else int(time.monotonic()),
        "rtc_synced": rtc_synced,
        "g": {
            "x": round(gx, 2),
            "y": round(gy, 2),
            "z": round(gz, 2),
            "total": round(g_total, 2)
        },
        "gps": {
            "fix": fix_type,
            "lat": round(lat, 6) if lat else 0,
            "lon": round(lon, 6) if lon else 0,
            "alt": round(alt, 1),
            "speed": round(speed_mph, 1),
            "sats": sats,
            "hdop": round(hdop, 1)
        }
    }

# ============================================================================
# Display Update
# ============================================================================

def update_display(data):
    """Update OLED display with enhanced format"""
    
    # Line 1: {HH:MM:SS} {GPS Fix} {HDOP bars}
    if rtc_synced:
        now = time.localtime()
        time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
    else:
        time_str = "--:--:--"
    
    fix_str = data['gps']['fix']
    hdop_bars = hdop_to_bars(data['gps']['hdop'])
    bars = "[" + "■" * hdop_bars + " " * (3 - hdop_bars) + "]"
    
    line1.text = f"{time_str} {fix_str:5s} {bars}"
    
    # Line 2: {DDD° MM:SS N/S DDD° MM:SS E/W}
    lat_dms = format_dms(data['gps']['lat'], is_latitude=True)
    lon_dms = format_dms(data['gps']['lon'], is_latitude=False)
    line2.text = f"{lat_dms} {lon_dms}"
    
    # Line 3: {MPH} {Total G Force}
    line3.text = f"{data['gps']['speed']:3.0f}MPH  {data['g']['total']:.2f}g"
    
    # Line 4: {Log file name} {File record time}
    if session.active:
        duration = format_time_hms(session.get_duration())
        short_name = session.filename[:8] if session.filename else "NoLog"
        line4.text = f"{short_name} {duration}"
    else:
        line4.text = "NoLog 00:00:00"
    
    # Line 5: {Estimate of SD Card remaining time}
    if session.active:
        bytes_per_sec = session.get_bytes_per_second()
        # Get current free space
        sd_stat = os.statvfs("/sd")
        free_bytes = sd_stat[0] * sd_stat[3]
        remaining = estimate_recording_time(free_bytes, bytes_per_sec)
        line5.text = f"SD: {remaining} remain"
    else:
        # Show total free space in GB
        sd_stat = os.statvfs("/sd")
        free_gb = (sd_stat[0] * sd_stat[3]) / (1024**3)
        line5.text = f"SD: {free_gb:.1f}GB free"

# ============================================================================
# Telemetry Sender
# ============================================================================

def send_telemetry(data):
    """Send JSON update message to ESP"""
    msg = {
        "type": "update",
        "data": data
    }
    protocol.send_json(msg)

# ============================================================================
# Main Loop
# ============================================================================

# Auto-start logging
session.start("John", "1ZVBP8AM5E5123456")

print("\n" + "="*50)
print("OpenPonyLogger v2.1 Running")
print("="*50)

last_display_update = 0
last_telemetry_send = 0
last_satellite_send = 0

try:
    while True:
        # Process serial commands
        protocol.process()
        
        # Read sensors
        data = read_sensors()
        
        # Log to SD card
        if session.active:
            session.log(data)
        
        now = time.monotonic()
        
        # Update display (5Hz)
        if now - last_display_update > 0.2:
            last_display_update = now
            update_display(data)
        
        # Send telemetry (1Hz)
        if now - last_telemetry_send > 1.0:
            last_telemetry_send = now
            send_telemetry(data)
        
        # Send satellites (every 120s)
        if now - last_satellite_send > 120.0:
            last_satellite_send = now
            protocol.send_satellites()
        
        time.sleep(0.01)  # 100Hz main loop
        
except KeyboardInterrupt:
    print("\nStopping...")
    if session.active:
        session.stop()
