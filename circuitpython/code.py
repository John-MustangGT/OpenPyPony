"""
OpenPonyLogger - Main Program with Real Data Integration
Now serves actual sensor data to web interface with GPS time sync
"""

import board
import busio
import adafruit_lis3dh
import displayio
import i2cdisplaybus
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import storage
import sdcardio
import time
import os
import struct
from wifi_server import (WiFiAPTask, WebServerTask, sync_gps_time, 
                         start_binary_log, write_binary_message, stop_binary_log,
                         SENSOR_ACCELEROMETER, SENSOR_GPS, 
                         DATA_ACCEL_XYZ, DATA_GPS_FIX)
from scheduler import Task, Scheduler

try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

# ============================================================================
# Configuration Loading
# ============================================================================

def load_settings():
    """Load configuration from settings.toml with comprehensive defaults"""
    defaults = {
        # WiFi
        'WIFI_SSID': 'OpenPonyLogger',
        'WIFI_PASSWORD': 'mustanggt',
        'DEVICE_NAME': 'OpenPyPony-01',
        
        # Display
        'SPLASH_DURATION': 3,
        'GFORCE_GRAPH_SCALE': 20,
        
        # Time
        'TIMEZONE_OFFSET': 0,
        'DST_ENABLED': False,
        
        # GPS
        'GPS_UPDATE_RATE': 1000,
        'GPS_BAUDRATE': 9600,
        
        # Accelerometer
        'ACCEL_SAMPLE_RATE': 100,
        'ACCEL_RANGE': 2,
        
        # Logging
        'BINARY_LOGGING': False,
        'LOG_FLUSH_SIZE': 50,
        'BYTES_PER_SAMPLE': 90,
        
        # SD Card Management
        'SD_HIGH_WATER_MB': 100,
        'SD_LOW_WATER_MB': 200,
        'SD_CHECK_INTERVAL': 600,
        
        # WiFi AP
        'AP_NO_DEFAULT_ROUTE': True,
        
        # Status/Debug
        'STATUS_INTERVAL': 5000,
        'SERIAL_DEBUG': True
    }
    
    settings = defaults.copy()
    
    try:
        # Try loading from settings.toml
        with open('/settings.toml', 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                    
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Type conversion
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.replace('-', '', 1).isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).replace('-', '', 1).isdigit():
                    value = float(value)
                
                if key in settings:
                    settings[key] = value
        
        print("✓ Settings loaded from settings.toml")
    except OSError:
        print("⚠ settings.toml not found, using defaults")
    
    return settings

# Load configuration
config = load_settings()

# Extract commonly-used settings as module-level variables
TIMEZONE_OFFSET = config['TIMEZONE_OFFSET']
DST_ENABLED = config['DST_ENABLED']
BINARY_LOGGING = config['BINARY_LOGGING']
AP_NO_DEFAULT_ROUTE = config['AP_NO_DEFAULT_ROUTE']
SPLASH_DURATION = config['SPLASH_DURATION']

print("=" * 60)
print(f"OpenPyPony v{VERSION}")
print(f"Device: {config['DEVICE_NAME']}")
print(f"Commit: {GIT_HASH}")
print(f"Built: {BUILD_DATE}")
print(f"Timezone: UTC{TIMEZONE_OFFSET:+d} DST={DST_ENABLED}")
print(f"Binary Logging: {BINARY_LOGGING}")
print(f"AP No Default Route: {AP_NO_DEFAULT_ROUTE}")
print(f"Splash Duration: {SPLASH_DURATION}s")
print("=" * 60)

# ============================================================================
# Hardware Initialization
# ============================================================================

# Release displays
displayio.release_displays()

# I2C for accelerometer and OLED
print("\n1. Initializing I2C bus...")
i2c = busio.I2C(board.GP9, board.GP8)
print("   ✓ I2C initialized")

# SD Card SPI
print("2. Initializing SD card...")
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
sdcard = sdcardio.SDCard(spi, board.GP17)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")
print("   ✓ SD card mounted")

# LIS3DH Accelerometer
print("3. Initializing LIS3DH accelerometer...")
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x18)

# Set range based on config
if config['ACCEL_RANGE'] == 2:
    lis3dh.range = adafruit_lis3dh.RANGE_2_G
elif config['ACCEL_RANGE'] == 4:
    lis3dh.range = adafruit_lis3dh.RANGE_4_G
elif config['ACCEL_RANGE'] == 8:
    lis3dh.range = adafruit_lis3dh.RANGE_8_G
else:
    lis3dh.range = adafruit_lis3dh.RANGE_2_G

# Set data rate based on config
if config['ACCEL_SAMPLE_RATE'] >= 100:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ
elif config['ACCEL_SAMPLE_RATE'] >= 50:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_50_HZ
elif config['ACCEL_SAMPLE_RATE'] >= 25:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_25_HZ
else:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_10_HZ

print(f"   ✓ LIS3DH initialized ({config['ACCEL_SAMPLE_RATE']}Hz, ±{config['ACCEL_RANGE']}g)")

# OLED Display
print("4. Initializing OLED display...")
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
print("   ✓ OLED initialized")

# ============================================================================
# Splash Screen
# ============================================================================

def show_splash_screen(duration):
    """Display OpenPyPony splash screen with copyright"""
    splash_group = displayio.Group()
    display.root_group = splash_group
    
    # Large "OpenPyPony" text (2x scale)
    title = label.Label(terminalio.FONT, text="OpenPyPony", color=0xFFFFFF, x=10, y=15)
    title.scale = 2
    
    # Copyright notice
    copyright1 = label.Label(terminalio.FONT, text="(c) 2025 John", color=0xFFFFFF, x=8, y=40)
    copyright2 = label.Label(terminalio.FONT, text="  Orthoefer", color=0xFFFFFF, x=8, y=50)
    
    splash_group.append(title)
    splash_group.append(copyright1)
    splash_group.append(copyright2)
    
    # Display for configured duration
    time.sleep(duration)

print(f"5. Showing splash screen ({SPLASH_DURATION}s)...")
show_splash_screen(SPLASH_DURATION)

# ============================================================================
# Main Display Layout
# ============================================================================

# Create display layout
splash = displayio.Group()
display.root_group = splash

# Line 1: Time, GPS Fix, HDOP, Sats (top status bar)
time_label = label.Label(terminalio.FONT, text="--:--", color=0xFFFFFF, x=0, y=5)
gps_status_label = label.Label(terminalio.FONT, text="NoFix", color=0xFFFFFF, x=30, y=5)
hdop_label = label.Label(terminalio.FONT, text="0.0", color=0xFFFFFF, x=65, y=5)
sats_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=100, y=5)

# Lines 2-4: Large Speed Display (left side)
speed_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=5, y=25)
speed_label.scale = 3  # Large 3x scale for visibility
speed_unit = label.Label(terminalio.FONT, text="mph", color=0xFFFFFF, x=5, y=50)

# G-Force Box (right side, approximately x=64-127)
# Top border
gf_box_top = label.Label(terminalio.FONT, text="_"*9, color=0xFFFFFF, x=64, y=15)
# Bottom border  
gf_box_bot = label.Label(terminalio.FONT, text="_"*9, color=0xFFFFFF, x=64, y=55)
# Left border (vertical lines)
gf_box_left1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=20)
gf_box_left2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=30)
gf_box_left3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=40)
gf_box_left4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=50)
# Right border (vertical lines)
gf_box_right1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=20)
gf_box_right2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=30)
gf_box_right3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=40)
gf_box_right4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=50)
# Center crosshair
gf_center_h = label.Label(terminalio.FONT, text="+", color=0xFFFFFF, x=92, y=35)
# G-force dot marker (will move based on acceleration)
gf_dot = label.Label(terminalio.FONT, text="O", color=0xFFFFFF, x=92, y=35)

# Line 6: SD Card Time Remaining
sd_label = label.Label(terminalio.FONT, text="SD: --h --m", color=0xFFFFFF, x=0, y=60)

# Append all labels to display group
splash.append(time_label)
splash.append(gps_status_label)
splash.append(hdop_label)
splash.append(sats_label)
splash.append(speed_label)
splash.append(speed_unit)
splash.append(gf_box_top)
splash.append(gf_box_bot)
splash.append(gf_box_left1)
splash.append(gf_box_left2)
splash.append(gf_box_left3)
splash.append(gf_box_left4)
splash.append(gf_box_right1)
splash.append(gf_box_right2)
splash.append(gf_box_right3)
splash.append(gf_box_right4)
splash.append(gf_center_h)
splash.append(gf_dot)
splash.append(sd_label)

# Create CSV log file (for compatibility)
log_filename = "/sd/accel_log_{}.csv".format(int(time.monotonic()))
print(f"5. Creating CSV log file: {log_filename}")
log_file = open(log_filename, "w")
log_file.write("timestamp_ms,accel_x,accel_y,accel_z,gforce_x,gforce_y,gforce_z,gforce_total\n")
print("   ✓ CSV log file created")

# Start binary logging if enabled
if BINARY_LOGGING:
    print("7. Starting binary logging...")
    start_binary_log()

# Shared data buffer between tasks
data_buffer = {}

# GPS time sync tracking
gps_time_last_check = 0
GPS_TIME_CHECK_INTERVAL = 60  # Check GPS time every 60 seconds

# ============================================================================
# Task Definitions
# ============================================================================

class AccelerometerTask(Task):
    """Read accelerometer at 10Hz and store in data buffer"""
    def __init__(self, lis3dh_sensor, buffer):
        super().__init__("Accelerometer", 100)  # 100ms = 10Hz
        self.sensor = lis3dh_sensor
        self.buffer = buffer
    
    def run(self):
        # Read raw acceleration
        x, y, z = self.sensor.acceleration
        
        # Convert to G-force
        gx = x / 9.81
        gy = y / 9.81
        gz = z / 9.81
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        
        # Store in shared buffer (for web interface)
        self.buffer['accel'] = {
            'x': x, 'y': y, 'z': z,
            'gx': gx, 'gy': gy, 'gz': gz,
            'g_total': g_total,
            'timestamp': time.monotonic()
        }
        
        # Write to binary log if enabled
        if BINARY_LOGGING:
            # Pack accelerometer data
            payload = struct.pack(
                '<fff',  # 3 floats
                gx, gy, gz
            )
            write_binary_message(SENSOR_ACCELEROMETER, DATA_ACCEL_XYZ, payload)


class GPSTask(Task):
    """Read GPS data and sync time when fix is good"""
    def __init__(self, buffer):
        super().__init__("GPS", 1000)  # 1Hz GPS updates
        self.buffer = buffer
        self.uart = None
        self.gps_module = None
        self.time_synced_this_session = False
        
        # Initialize GPS UART
        try:
            import adafruit_gps
            self.uart = busio.UART(board.GP0, board.GP1, baudrate=config['GPS_BAUDRATE'], timeout=10)
            self.gps_module = adafruit_gps.GPS(self.uart, debug=False)
            
            # Configure GPS
            self.gps_module.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
            update_cmd = f'PMTK220,{config["GPS_UPDATE_RATE"]}'.encode()
            self.gps_module.send_command(update_cmd)
            
            print(f"   ✓ GPS initialized ({config['GPS_BAUDRATE']} baud, {config['GPS_UPDATE_RATE']}ms)")
        except Exception as e:
            print(f"   ✗ GPS init failed: {e}")
            self.enabled = False
    
    def run(self):
        if not self.gps_module:
            return
        
        try:
            self.gps_module.update()
            
            # Check if we have a valid fix
            if self.gps_module.has_fix:
                # Update buffer with GPS data
                self.buffer['gps'] = {
                    'lat': self.gps_module.latitude,
                    'lon': self.gps_module.longitude,
                    'alt': self.gps_module.altitude_m or 0,
                    'speed': self.gps_module.speed_knots or 0,
                    'heading': self.gps_module.track_angle_deg or 0,
                    'satellites': self.gps_module.satellites or 0,
                    'fix_quality': self.gps_module.fix_quality,
                    'hdop': self.gps_module.hdop or 99.9,
                    'timestamp': time.monotonic()
                }
                
                # Update satellite list if available
                if hasattr(self.gps_module, 'satellites_used'):
                    satellites = []
                    for i in range(len(self.gps_module.satellites_used)):
                        satellites.append({
                            'id': self.gps_module.satellites_used[i],
                            'snr': 30 + i * 5  # Placeholder - real SNR not available in all GPS modules
                        })
                    self.buffer['gps_satellites'] = satellites
                
                # Sync time if we have a good fix and haven't synced yet
                if (self.gps_module.fix_quality is not None and
                    self.gps_module.fix_quality >= 1 and 
                    self.gps_module.satellites is not None and
                    self.gps_module.satellites >= 4 and
                    not self.time_synced_this_session):
                    
                    gps_time = {
                        'year': self.gps_module.timestamp_utc.tm_year,
                        'month': self.gps_module.timestamp_utc.tm_mon,
                        'day': self.gps_module.timestamp_utc.tm_mday,
                        'hour': self.gps_module.timestamp_utc.tm_hour,
                        'minute': self.gps_module.timestamp_utc.tm_min,
                        'second': self.gps_module.timestamp_utc.tm_sec
                    }
                    
                    if sync_gps_time(gps_time, TIMEZONE_OFFSET, DST_ENABLED):
                        self.time_synced_this_session = True
                        print("[GPS] Time synchronized to local timezone")
                
                # Write to binary log if enabled
                if BINARY_LOGGING:
                    payload = struct.pack(
                        '<iiifff',  # lat, lon (as int32 * 1e7), alt, speed, heading, hdop
                        int(self.gps_module.latitude * 1e7),
                        int(self.gps_module.longitude * 1e7),
                        int(self.gps_module.altitude_m or 0),
                        self.gps_module.speed_knots or 0,
                        self.gps_module.track_angle_deg or 0,
                        self.gps_module.hdop or 99.9
                    )
                    write_binary_message(SENSOR_GPS, DATA_GPS_FIX, payload)
            else:
                # No fix
                self.buffer['gps'] = {
                    'lat': 0, 'lon': 0, 'alt': 0,
                    'speed': 0, 'heading': 0,
                    'satellites': self.gps_module.satellites or 0,
                    'fix_quality': 0,
                    'hdop': 99.9,
                    'timestamp': time.monotonic()
                }
        
        except Exception as e:
            print(f"[GPS] Error: {e}")


class DisplayTask(Task):
    """Update OLED display at 5Hz with comprehensive layout"""
    def __init__(self, labels, buffer):
        super().__init__("Display", 200)  # 200ms = 5Hz
        self.labels = labels
        self.buffer = buffer
        self.gforce_scale = config.get('GFORCE_GRAPH_SCALE') or 20  # Pixels per G
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        # Line 1: Time, Fix Type, HDOP, Satellites
        fix_quality = gps.get('fix_quality') or 0 if gps else 0
        if gps and fix_quality > 0:
            # Show GPS time from RTC (already synced to local time)
            try:
                import rtc
                now = rtc.RTC().datetime
                time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}"
            except:
                time_str = "--:--"
            
            # Fix type
            if fix_quality >= 2:
                fix_str = "3D"
            elif fix_quality >= 1:
                fix_str = "2D"
            else:
                fix_str = "NoFix"
            
            # HDOP and satellites
            hdop = gps.get('hdop') or 99.9
            sats = gps.get('satellites') or 0
            
            self.labels['time'].text = time_str
            self.labels['gps_status'].text = fix_str
            self.labels['hdop'].text = f"{hdop:.1f}"
            self.labels['sats'].text = str(sats)
        else:
            # No GPS fix - show uptime
            uptime = int(time.monotonic())
            self.labels['time'].text = f"{uptime}s"
            self.labels['gps_status'].text = "NoFix"
            self.labels['hdop'].text = "--"
            self.labels['sats'].text = "0"
        
        # Lines 2-4: Large Speed Display
        speed_fix_quality = gps.get('fix_quality') or 0 if gps else 0
        if gps and speed_fix_quality > 0:
            speed_knots = gps.get('speed') or 0
            speed_mph = speed_knots * 1.15078
            self.labels['speed'].text = f"{int(speed_mph)}"
        else:
            self.labels['speed'].text = "0"
        
        # G-Force Box: Update dot position based on lateral/longitudinal acceleration
        if accel:
            # Map acceleration to display coordinates
            # Box center is at (92, 35), box spans roughly ±28 pixels
            gx = accel['gx']  # Lateral (left/right)
            gy = accel['gy']  # Longitudinal (forward/back)
            
            # Scale and clamp
            dot_x = 92 + int(gx * self.gforce_scale)
            dot_y = 35 - int(gy * self.gforce_scale)  # Negative because Y increases downward
            
            # Clamp to box boundaries (approximately 64-120 x, 15-55 y)
            dot_x = max(68, min(116, dot_x))
            dot_y = max(18, min(52, dot_y))
            
            self.labels['gf_dot'].x = dot_x
            self.labels['gf_dot'].y = dot_y
        
        # Line 6: SD Card Time Remaining
        try:
            import os
            stat = os.statvfs('/sd')
            free_bytes = stat[0] * stat[3]
            free_mb = free_bytes / (1024 * 1024)
            
            # Calculate time remaining
            bytes_per_sample = config.get('BYTES_PER_SAMPLE') or 90
            sample_rate = config.get('ACCEL_SAMPLE_RATE') or 100
            bytes_per_second = bytes_per_sample * sample_rate
            
            if bytes_per_second > 0:
                seconds_remaining = free_bytes / bytes_per_second
                hours = int(seconds_remaining // 3600)
                minutes = int((seconds_remaining % 3600) // 60)
                self.labels['sd'].text = f"SD: {hours}h {minutes}m"
            else:
                self.labels['sd'].text = f"SD: {int(free_mb)}MB"
        except:
            self.labels['sd'].text = "SD: --"



class SDLoggerTask(Task):
    """Log data to CSV file - buffer 50 samples before flush"""
    def __init__(self, file, buffer, flush_size=50):
        super().__init__("SD Logger", 100)  # 100ms = 10Hz
        self.file = file
        self.buffer = buffer
        self.write_buffer = []
        self.flush_size = flush_size
    
    def run(self):
        accel = self.buffer.get('accel')
        if not accel:
            return
        
        # Format CSV line
        timestamp = int(accel['timestamp'] * 1000)
        line = "{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}\n".format(
            timestamp,
            accel['x'], accel['y'], accel['z'],
            accel['gx'], accel['gy'], accel['gz'],
            accel['g_total']
        )
        
        # Add to buffer
        self.write_buffer.append(line)
        
        # Flush when buffer is full
        if len(self.write_buffer) >= self.flush_size:
            for l in self.write_buffer:
                self.file.write(l)
            self.file.flush()
            self.write_buffer.clear()
    
    def flush(self):
        """Force flush remaining data"""
        if self.write_buffer:
            for l in self.write_buffer:
                self.file.write(l)
            self.file.flush()
            self.write_buffer.clear()


class StatusTask(Task):
    """Print status to console every second"""
    def __init__(self, scheduler_ref, buffer):
        super().__init__("Status", 1000)  # 1000ms = 1Hz
        self.scheduler = scheduler_ref
        self.buffer = buffer
    
    def run(self):
        # Get data
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        # Build console status line
        status_parts = []
        status_parts.append(f"Uptime: {int(time.monotonic())}s")
        
        if accel:
            status_parts.append(f"G: X={accel['gx']:+.2f} Y={accel['gy']:+.2f} Z={accel['gz']:+.2f} T={accel['g_total']:.2f}g")
        
        if gps:
            sats = gps.get('satellites') or 0
            speed_knots = gps.get('speed') or 0
            fix_quality = gps.get('fix_quality') or 0
            if fix_quality > 0:
                status_parts.append(f"GPS: {sats}sat {speed_knots:.1f}kts")
            else:
                status_parts.append(f"GPS: {sats}sat NoFix")
        
        print(" | ".join(status_parts))


class WebServerPollingTask(Task):
    """Poll web server for incoming HTTP requests"""
    def __init__(self, web_server):
        super().__init__("WebServer", 10)  # Poll every 10ms
        self.web_server = web_server
    
    def run(self):
        self.web_server.poll()


class WiFiMonitorTask(Task):
    """Monitor WiFi connections and server activity"""
    def __init__(self, wifi_ap, web_server):
        super().__init__("WiFi Monitor", 30000)  # Every 30 seconds
        self.wifi_ap = wifi_ap
        self.web_server = web_server
    
    def run(self):
        if self.wifi_ap.ap_active:
            print(f"\n[WiFi] AP: {self.wifi_ap.ssid} | IP: {self.wifi_ap.ip_address} | Requests: {self.web_server.request_count}")


# ============================================================================
# WiFi and Web Server Setup
# ============================================================================

print("\n8. Setting up WiFi Access Point...")
wifi_ap = WiFiAPTask(ssid="OpenPonyLogger", password="mustanggt", no_default_route=AP_NO_DEFAULT_ROUTE)
if wifi_ap.start():
    print("   ✓ WiFi AP started")
    
    print("9. Starting web server...")
    web_server = WebServerTask(data_buffer, wifi_ap)
    if web_server.start():
        print("   ✓ Web server started")
        print(f"\n   → Access web interface at: http://{wifi_ap.ip_address}")
    else:
        print("   ✗ Web server failed - continuing without WiFi")
        web_server = None
else:
    print("   ✗ WiFi AP failed - continuing without WiFi")
    web_server = None

print("\n" + "=" * 60)
print("Building scheduler...")
print("=" * 60)

# Create scheduler
scheduler = Scheduler()

# Create display labels dictionary for DisplayTask
display_labels = {
    'time': time_label,
    'gps_status': gps_status_label,
    'hdop': hdop_label,
    'sats': sats_label,
    'speed': speed_label,
    'gf_dot': gf_dot,
    'sd': sd_label
}

# Add tasks
accel_task = AccelerometerTask(lis3dh, data_buffer)
gps_task = GPSTask(data_buffer)
display_task = DisplayTask(display_labels, data_buffer)
logger_task = SDLoggerTask(log_file, data_buffer, flush_size=50)
status_task = StatusTask(scheduler, data_buffer)

scheduler.add_task(accel_task)
scheduler.add_task(gps_task)
scheduler.add_task(display_task)
scheduler.add_task(logger_task)
scheduler.add_task(status_task)

# Add web server tasks if WiFi is active
if web_server and wifi_ap:
    wifi_monitor_task = WiFiMonitorTask(wifi_ap, web_server)
    scheduler.add_task(wifi_monitor_task)
    
    webserver_task = WebServerPollingTask(web_server)
    scheduler.add_task(webserver_task)

print("\n" + "=" * 60)
print("Starting data acquisition...")
print("Press Ctrl+C to stop")
print("=" * 60 + "\n")

# Run scheduler
try:
    scheduler.run()
except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("Shutting down...")
    print("=" * 60)
    
    # Flush remaining SD card buffer
    print("\nFlushing SD card buffer...")
    logger_task.flush()
    log_file.close()
    print("✓ CSV log file closed")
    
    # Stop binary logging if active
    if BINARY_LOGGING:
        stop_binary_log()
    
    # Print performance statistics
    scheduler.print_stats()
    
    # File info
    print(f"\nLog file: {log_filename}")
    try:
        stat = os.stat(log_filename)
        samples = (stat[6] - 100) // 60  # Rough estimate (60 bytes per line)
        print(f"File size: {stat[6]} bytes ({stat[6]/1024:.1f} KB)")
        print(f"Estimated samples: ~{samples}")
    except:
        pass
    
    status_label.text = "Stopped"
    print("\n✓ Shutdown complete")
