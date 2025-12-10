"""
OpenPonyLogger - Main Program with Binary Format v2 Integration
Now with session management, checksummed data blocks, and event-based flushing
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

# Import WiFi and logging modules
from wifi_server import (
    WiFiAPTask, WebServerTask, sync_gps_time, is_gps_time_synced,
    start_binary_log, stop_binary_log, get_binary_log_stats,
    SENSOR_ACCELEROMETER, SENSOR_GPS
)

# Import binary format for direct logging
try:
    from binary_format import (
        BinaryLogger, WEATHER_UNKNOWN,
        FLUSH_FLAG_EVENT, FLUSH_FLAG_MANUAL
    )
    HAS_BINARY_FORMAT = True
except ImportError:
    HAS_BINARY_FORMAT = False
    print("Warning: binary_format module not available")

from scheduler import Task, Scheduler

try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "1.3.0"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

# =============================================================================
# Configuration Loading
# =============================================================================

def load_settings():
    """Load configuration from settings.toml with comprehensive defaults"""
    defaults = {
        # WiFi
        'WIFI_SSID': 'OpenPonyLogger',
        'WIFI_PASSWORD': 'mustanggt',
        'DEVICE_NAME': 'OpenPyPony-01',
        
        # Session Metadata (for binary logging)
        'SESSION_NAME': '',
        'DRIVER_NAME': '',
        'VEHICLE_ID': '',
        
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
        'BINARY_LOGGING': True,  # Now enabled by default
        'LOG_FLUSH_SIZE': 50,
        'BYTES_PER_SAMPLE': 90,
        
        # Event thresholds
        'GFORCE_EVENT_THRESHOLD': 3.0,  # G-force to trigger immediate flush
        
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
    config_checksum = 0
    
    try:
        # Try loading from settings.toml
        with open('/settings.toml', 'r') as f:
            content = f.read()
            # Calculate checksum for change detection
            for c in content:
                config_checksum = (config_checksum + ord(c)) & 0xFFFFFFFF
            
            for line in content.split('\n'):
                line = line.strip()
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
    
    settings['_CONFIG_CHECKSUM'] = config_checksum
    return settings

# Load configuration
config = load_settings()

# Extract commonly-used settings
TIMEZONE_OFFSET = config['TIMEZONE_OFFSET']
DST_ENABLED = config['DST_ENABLED']
BINARY_LOGGING = config['BINARY_LOGGING']
AP_NO_DEFAULT_ROUTE = config['AP_NO_DEFAULT_ROUTE']
SPLASH_DURATION = config['SPLASH_DURATION']
GFORCE_EVENT_THRESHOLD = config.get('GFORCE_EVENT_THRESHOLD', 3.0)

print("=" * 60)
print(f"OpenPyPony v{VERSION}")
print(f"Device: {config['DEVICE_NAME']}")
print(f"Commit: {GIT_HASH}")
print(f"Built: {BUILD_DATE}")
print(f"Timezone: UTC{TIMEZONE_OFFSET:+d} DST={DST_ENABLED}")
print(f"Binary Logging: {BINARY_LOGGING}")
print(f"G-Force Event Threshold: {GFORCE_EVENT_THRESHOLD}g")
print("=" * 60)

# =============================================================================
# Hardware Initialization
# =============================================================================

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

# Create logs directory
try:
    os.mkdir("/sd/logs")
except OSError:
    pass  # Directory exists

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

# =============================================================================
# Splash Screen
# =============================================================================

def show_splash_screen(duration):
    """Display OpenPyPony splash screen with copyright"""
    splash_group = displayio.Group()
    display.root_group = splash_group
    
    title = label.Label(terminalio.FONT, text="OpenPyPony", color=0xFFFFFF, x=10, y=15)
    title.scale = 2
    
    copyright1 = label.Label(terminalio.FONT, text="(c) 2025 John", color=0xFFFFFF, x=8, y=40)
    copyright2 = label.Label(terminalio.FONT, text="  Orthoefer", color=0xFFFFFF, x=8, y=50)
    
    splash_group.append(title)
    splash_group.append(copyright1)
    splash_group.append(copyright2)
    
    time.sleep(duration)

print(f"5. Showing splash screen ({SPLASH_DURATION}s)...")
show_splash_screen(SPLASH_DURATION)

# =============================================================================
# Main Display Layout
# =============================================================================

splash = displayio.Group()
display.root_group = splash

# Line 1: Time, GPS Fix, HDOP, Sats
time_label = label.Label(terminalio.FONT, text="--:--", color=0xFFFFFF, x=0, y=5)
gps_status_label = label.Label(terminalio.FONT, text="NoFix", color=0xFFFFFF, x=30, y=5)
hdop_label = label.Label(terminalio.FONT, text="0.0", color=0xFFFFFF, x=65, y=5)
sats_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=100, y=5)

# Lines 2-4: Large Speed Display
speed_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=5, y=25)
speed_label.scale = 3
speed_unit = label.Label(terminalio.FONT, text="mph", color=0xFFFFFF, x=5, y=50)

# G-Force Box elements
gf_box_top = label.Label(terminalio.FONT, text="_"*9, color=0xFFFFFF, x=64, y=15)
gf_box_bot = label.Label(terminalio.FONT, text="_"*9, color=0xFFFFFF, x=64, y=55)
gf_box_left1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=20)
gf_box_left2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=30)
gf_box_left3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=40)
gf_box_left4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=50)
gf_box_right1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=20)
gf_box_right2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=30)
gf_box_right3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=40)
gf_box_right4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=120, y=50)
gf_center_h = label.Label(terminalio.FONT, text="+", color=0xFFFFFF, x=92, y=35)
gf_dot = label.Label(terminalio.FONT, text="O", color=0xFFFFFF, x=92, y=35)

# Line 6: SD Card Time Remaining / Session Info
sd_label = label.Label(terminalio.FONT, text="SD: --h --m", color=0xFFFFFF, x=0, y=60)

# Append all labels
for lbl in [time_label, gps_status_label, hdop_label, sats_label,
            speed_label, speed_unit,
            gf_box_top, gf_box_bot,
            gf_box_left1, gf_box_left2, gf_box_left3, gf_box_left4,
            gf_box_right1, gf_box_right2, gf_box_right3, gf_box_right4,
            gf_center_h, gf_dot, sd_label]:
    splash.append(lbl)

# Shared data buffer
data_buffer = {}

# Binary logger instance (managed separately from wifi_server's global)
binary_logger = None

# =============================================================================
# Binary Logging Setup
# =============================================================================

if BINARY_LOGGING and HAS_BINARY_FORMAT:
    print("6. Starting binary logging session...")
    binary_logger = BinaryLogger(log_dir="/sd/logs")
    
    session_id = binary_logger.start_session(
        session_name=config.get('SESSION_NAME', f"Session {int(time.monotonic())}"),
        driver_name=config.get('DRIVER_NAME', ''),
        vehicle_id=config.get('VEHICLE_ID', ''),
        weather=WEATHER_UNKNOWN
    )
    
    if session_id:
        print(f"   ✓ Binary logging started")
        print(f"   Session ID: {session_id.hex()}")
    else:
        print("   ✗ Binary logging failed to start")
        binary_logger = None
else:
    print("6. Binary logging disabled")

# =============================================================================
# Task Definitions
# =============================================================================

class AccelerometerTask(Task):
    """Read accelerometer at 10Hz and log to binary format"""
    def __init__(self, lis3dh_sensor, buffer, logger=None):
        super().__init__("Accelerometer", 100)  # 100ms = 10Hz
        self.sensor = lis3dh_sensor
        self.buffer = buffer
        self.logger = logger
        self.event_threshold = GFORCE_EVENT_THRESHOLD
    
    def run(self):
        x, y, z = self.sensor.acceleration
        
        gx = x / 9.81
        gy = y / 9.81
        gz = z / 9.81
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        
        timestamp_us = int(time.monotonic() * 1000000)
        
        # Store in shared buffer
        self.buffer['accel'] = {
            'x': x, 'y': y, 'z': z,
            'gx': gx, 'gy': gy, 'gz': gz,
            'g_total': g_total,
            'timestamp': time.monotonic()
        }
        
        # Write to binary log
        if self.logger:
            self.logger.write_accelerometer(gx, gy, gz, timestamp_us)


class GPSTask(Task):
    """Read GPS data and sync time when fix is good"""
    def __init__(self, buffer, logger=None):
        super().__init__("GPS", 1000)  # 1Hz GPS updates
        self.buffer = buffer
        self.logger = logger
        self.uart = None
        self.gps_module = None
        self.time_synced_this_session = False
        
        # Initialize GPS UART
        try:
            import adafruit_gps
            self.uart = busio.UART(board.GP0, board.GP1, baudrate=config['GPS_BAUDRATE'], timeout=10)
            self.gps_module = adafruit_gps.GPS(self.uart, debug=False)
            
            self.gps_module.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
            update_cmd = f'PMTK220,{config["GPS_UPDATE_RATE"]}'.encode()
            self.gps_module.send_command(update_cmd)
            
            print(f"   ✓ GPS initialized ({config['GPS_BAUDRATE']} baud)")
        except Exception as e:
            print(f"   ✗ GPS init failed: {e}")
            self.enabled = False
    
    def run(self):
        if not self.gps_module:
            return
        
        try:
            self.gps_module.update()
            timestamp_us = int(time.monotonic() * 1000000)
            
            if self.gps_module.has_fix:
                lat = self.gps_module.latitude
                lon = self.gps_module.longitude
                alt = self.gps_module.altitude_m or 0
                speed = self.gps_module.speed_knots or 0
                heading = self.gps_module.track_angle_deg or 0
                sats = self.gps_module.satellites or 0
                fix_quality = self.gps_module.fix_quality
                hdop = self.gps_module.hdop or 99.9
                
                self.buffer['gps'] = {
                    'lat': lat, 'lon': lon, 'alt': alt,
                    'speed': speed, 'heading': heading,
                    'satellites': sats, 'fix_quality': fix_quality,
                    'hdop': hdop, 'timestamp': time.monotonic()
                }
                
                # Sync time if good fix
                if (fix_quality >= 1 and sats >= 4 and 
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
                
                # Write to binary log
                if self.logger:
                    self.logger.write_gps(lat, lon, alt, speed, heading, hdop, timestamp_us)
            else:
                self.buffer['gps'] = {
                    'lat': 0, 'lon': 0, 'alt': 0,
                    'speed': 0, 'heading': 0,
                    'satellites': self.gps_module.satellites or 0,
                    'fix_quality': 0, 'hdop': 99.9,
                    'timestamp': time.monotonic()
                }
        
        except Exception as e:
            print(f"[GPS] Error: {e}")


class DisplayTask(Task):
    """Update OLED display at 5Hz"""
    def __init__(self, labels, buffer):
        super().__init__("Display", 200)  # 200ms = 5Hz
        self.labels = labels
        self.buffer = buffer
        self.gforce_scale = config.get('GFORCE_GRAPH_SCALE', 20)
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        # Update time display
        fix_quality = gps.get('fix_quality', 0) if gps else 0
        if gps and fix_quality > 0:
            try:
                import rtc
                now = rtc.RTC().datetime
                time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}"
            except:
                time_str = "--:--"
            
            fix_str = "3D" if fix_quality >= 2 else "2D" if fix_quality >= 1 else "NoFix"
            hdop = gps.get('hdop', 99.9)
            sats = gps.get('satellites', 0)
            
            self.labels['time'].text = time_str
            self.labels['gps_status'].text = fix_str
            self.labels['hdop'].text = f"{hdop:.1f}"
            self.labels['sats'].text = str(sats)
        else:
            uptime = int(time.monotonic())
            self.labels['time'].text = f"{uptime}s"
            self.labels['gps_status'].text = "NoFix"
            self.labels['hdop'].text = "--"
            self.labels['sats'].text = "0"
        
        # Update speed
        if gps and gps.get('fix_quality', 0) > 0:
            speed_mph = gps.get('speed', 0) * 1.15078
            self.labels['speed'].text = f"{int(speed_mph)}"
        else:
            self.labels['speed'].text = "0"
        
        # Update G-Force dot
        if accel:
            gx, gy = accel['gx'], accel['gy']
            dot_x = 92 + int(gx * self.gforce_scale)
            dot_y = 35 - int(gy * self.gforce_scale)
            dot_x = max(68, min(116, dot_x))
            dot_y = max(18, min(52, dot_y))
            self.labels['gf_dot'].x = dot_x
            self.labels['gf_dot'].y = dot_y
        
        # Update SD card info
        try:
            stat = os.statvfs('/sd')
            free_bytes = stat[0] * stat[3]
            bytes_per_second = config.get('BYTES_PER_SAMPLE', 90) * config.get('ACCEL_SAMPLE_RATE', 100)
            
            if bytes_per_second > 0:
                seconds_remaining = free_bytes / bytes_per_second
                hours = int(seconds_remaining // 3600)
                minutes = int((seconds_remaining % 3600) // 60)
                self.labels['sd'].text = f"SD: {hours}h {minutes}m"
        except:
            pass


class BinaryFlushTask(Task):
    """Periodically check if binary log needs flushing"""
    def __init__(self, logger, buffer):
        super().__init__("BinaryFlush", 5000)  # Check every 5 seconds
        self.logger = logger
        self.buffer = buffer
    
    def run(self):
        if not self.logger:
            return
        
        # Check for high G-force events
        accel = self.buffer.get('accel')
        if accel and accel.get('g_total', 0) >= GFORCE_EVENT_THRESHOLD:
            print(f"[Binary] High G-force event: {accel['g_total']:.2f}g")
            self.logger.flush(FLUSH_FLAG_EVENT)


class StatusTask(Task):
    """Print status to console"""
    def __init__(self, scheduler_ref, buffer, logger=None):
        super().__init__("Status", 5000)  # Every 5 seconds
        self.scheduler = scheduler_ref
        self.buffer = buffer
        self.logger = logger
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        parts = [f"Up: {int(time.monotonic())}s"]
        
        if accel:
            parts.append(f"G: {accel['g_total']:.2f}g")
        
        if gps and gps.get('fix_quality', 0) > 0:
            parts.append(f"GPS: {gps.get('satellites', 0)}sat {gps.get('speed', 0):.1f}kts")
        
        if self.logger:
            stats = self.logger.get_stats()
            parts.append(f"Blk: {stats['blocks_written']}")
        
        print(" | ".join(parts))


class WebServerPollingTask(Task):
    """Poll web server for requests"""
    def __init__(self, web_server):
        super().__init__("WebServer", 10)
        self.web_server = web_server
    
    def run(self):
        self.web_server.poll()


class ConfigWatchTask(Task):
    """Watch for config changes and restart session if needed"""
    def __init__(self, logger, original_checksum):
        super().__init__("ConfigWatch", 30000)  # Check every 30 seconds
        self.logger = logger
        self.last_checksum = original_checksum
    
    def run(self):
        if not self.logger:
            return
        
        try:
            # Recalculate config checksum
            checksum = 0
            with open('/settings.toml', 'r') as f:
                for c in f.read():
                    checksum = (checksum + ord(c)) & 0xFFFFFFFF
            
            if checksum != self.last_checksum:
                print("[Config] Settings changed, restarting session...")
                self.logger.restart_session()
                self.last_checksum = checksum
        except:
            pass


# =============================================================================
# WiFi and Web Server Setup
# =============================================================================

print("\n7. Setting up WiFi Access Point...")
wifi_ap = WiFiAPTask(
    ssid=config['WIFI_SSID'],
    password=config['WIFI_PASSWORD'],
    no_default_route=AP_NO_DEFAULT_ROUTE
)

web_server = None
if wifi_ap.start():
    print("   ✓ WiFi AP started")
    
    print("8. Starting web server...")
    web_server = WebServerTask(data_buffer, wifi_ap)
    if web_server.start():
        print("   ✓ Web server started")
        print(f"\n   → Access web interface at: http://{wifi_ap.ip_address}")
    else:
        print("   ✗ Web server failed")
        web_server = None
else:
    print("   ✗ WiFi AP failed")

# =============================================================================
# Build Scheduler
# =============================================================================

print("\n" + "=" * 60)
print("Building scheduler...")
print("=" * 60)

scheduler = Scheduler()

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
scheduler.add_task(AccelerometerTask(lis3dh, data_buffer, binary_logger))
scheduler.add_task(GPSTask(data_buffer, binary_logger))
scheduler.add_task(DisplayTask(display_labels, data_buffer))
scheduler.add_task(StatusTask(scheduler, data_buffer, binary_logger))

if binary_logger:
    scheduler.add_task(BinaryFlushTask(binary_logger, data_buffer))
    scheduler.add_task(ConfigWatchTask(binary_logger, config.get('_CONFIG_CHECKSUM', 0)))

if web_server:
    scheduler.add_task(WebServerPollingTask(web_server))

# =============================================================================
# Main Loop
# =============================================================================

print("\n" + "=" * 60)
print("Starting data acquisition...")
print("Press Ctrl+C to stop")
print("=" * 60 + "\n")

try:
    scheduler.run()
except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("Shutting down...")
    print("=" * 60)
    
    # Stop binary logging
    if binary_logger:
        print("\nStopping binary logging session...")
        binary_logger.stop_session()
        print("✓ Binary log closed")
    
    # Print stats
    scheduler.print_stats()
    
    # Final status
    sd_label.text = "Stopped"
    print("\n✓ Shutdown complete")
