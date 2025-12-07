"""
OpenPonyLogger - Main Program with GPS Support
Enhanced with settings.toml configuration, splash screen, and SD management
"""

import board
import busio
import adafruit_lis3dh
import displayio
import i2cdisplaybus
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import adafruit_gps
import storage
import sdcardio
import time
import os
from wifi_server import WiFiAPTask, WebServerTask
from scheduler import Task, Scheduler

try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "1.3.0"
    GIT_HASH = "dev"
    BUILD_DATE = "2025-12-07"

# ============================================================================
# Configuration Loading from settings.toml
# ============================================================================

def load_settings():
    """Load settings from settings.toml file"""
    defaults = {
        # WiFi Settings
        'WIFI_SSID': 'OpenPonyLogger',
        'WIFI_PASSWORD': 'mustanggt',
        'DEVICE_NAME': 'OpenPyPony-01',
        
        # GPS Settings
        'GPS_UPDATE_RATE': 1000,  # milliseconds (1Hz)
        'GPS_BAUDRATE': 9600,
        
        # Accelerometer Settings
        'ACCEL_SAMPLE_RATE': 100,  # Hz
        'ACCEL_RANGE': 2,  # ±2g
        
        # Display Settings
        'GFORCE_GRAPH_SCALE': 20,  # pixels per G
        'SPLASH_DURATION': 10,  # seconds
        
        # Logging Settings
        'LOG_FLUSH_SIZE': 50,  # samples before SD flush
        'BYTES_PER_SAMPLE': 90,  # estimated bytes per CSV line with GPS
        
        # SD Card Management
        'SD_HIGH_WATER_MB': 100,  # Start cleanup when < 100MB free
        'SD_LOW_WATER_MB': 200,   # Clean up to 200MB free
        'SD_CHECK_INTERVAL': 600,  # Check every 10 minutes (seconds)
        
        # Status/Debug
        'STATUS_INTERVAL': 5000,  # milliseconds
        'SERIAL_DEBUG': True
    }
    
    settings = defaults.copy()
    
    try:
        with open('/settings.toml', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Type conversion
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    elif value.replace('.', '', 1).isdigit():
                        value = float(value)
                    
                    settings[key] = value
        
        print("✓ Settings loaded from settings.toml")
    except OSError:
        print("⚠ settings.toml not found, using defaults")
    
    return settings

# Load configuration
config = load_settings()

print("=" * 60)
print(f"OpenPyPony v{VERSION}")
print(f"Commit: {GIT_HASH}")
print(f"Built: {BUILD_DATE}")
print(f"Device: {config['DEVICE_NAME']}")
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

# Set data rate
if config['ACCEL_SAMPLE_RATE'] >= 100:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ
elif config['ACCEL_SAMPLE_RATE'] >= 50:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_50_HZ
else:
    lis3dh.data_rate = adafruit_lis3dh.DATARATE_25_HZ

print("   ✓ LIS3DH initialized")

# GPS Module
print("4. Initializing GPS module...")
uart = busio.UART(board.GP0, board.GP1, baudrate=config['GPS_BAUDRATE'], timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
# Configure GPS
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')  # RMC + GGA only
update_cmd = f'PMTK220,{config["GPS_UPDATE_RATE"]}'.encode()
gps.send_command(update_cmd)
print("   ✓ GPS initialized")

# OLED Display
print("5. Initializing OLED display...")
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
print("   ✓ OLED initialized")

# ============================================================================
# Splash Screen
# ============================================================================

def show_splash_screen(duration):
    """Display OpenPyPony splash screen"""
    splash = displayio.Group()
    display.root_group = splash
    
    # Large "OpenPyPony" text
    title1 = label.Label(terminalio.FONT, text="OpenPyPony", color=0xFFFFFF, x=10, y=15)
    title1.scale = 2
    
    # Copyright
    copyright = label.Label(terminalio.FONT, text="(c) 2025 John", color=0xFFFFFF, x=8, y=40)
    copyright2 = label.Label(terminalio.FONT, text="  Orthoefer", color=0xFFFFFF, x=8, y=50)
    
    splash.append(title1)
    splash.append(copyright)
    splash.append(copyright2)
    
    # Display for duration
    time.sleep(duration)

print(f"6. Showing splash screen ({config['SPLASH_DURATION']}s)...")
show_splash_screen(config['SPLASH_DURATION'])

# ============================================================================
# Main Display Layout
# ============================================================================

# Create display layout - comprehensive status
splash = displayio.Group()
display.root_group = splash

# Line 1: Time, GPS Fix, HDOP, Sats
time_label = label.Label(terminalio.FONT, text="--:--", color=0xFFFFFF, x=0, y=5)
gps_status_label = label.Label(terminalio.FONT, text="NoFix", color=0xFFFFFF, x=30, y=5)
hdop_label = label.Label(terminalio.FONT, text="0.0", color=0xFFFFFF, x=65, y=5)
sats_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=100, y=5)

# Line 2-4: Large Speed (left side)
speed_label = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=5, y=25)
speed_label.scale = 3  # Large speed display
speed_unit = label.Label(terminalio.FONT, text="mph", color=0xFFFFFF, x=5, y=50)

# G-Force graph area (right side, y: 15-55, x: 64-127)
# We'll draw this with individual pixels/labels representing the box and dot

# Line 6: SD Card space (in time remaining)
sd_label = label.Label(terminalio.FONT, text="SD: --h --m", color=0xFFFFFF, x=0, y=58)

splash.append(time_label)
splash.append(gps_status_label)
splash.append(hdop_label)
splash.append(sats_label)
splash.append(speed_label)
splash.append(speed_unit)
splash.append(sd_label)

# G-force graph box (drawn with labels)
# Top border
gf_box_top = label.Label(terminalio.FONT, text="_" * 9, color=0xFFFFFF, x=64, y=15)
splash.append(gf_box_top)
# Bottom border
gf_box_bot = label.Label(terminalio.FONT, text="_" * 9, color=0xFFFFFF, x=64, y=55)
splash.append(gf_box_bot)
# Left border (vertical line approximation)
gf_box_left1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=20)
gf_box_left2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=30)
gf_box_left3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=40)
gf_box_left4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=64, y=50)
splash.append(gf_box_left1)
splash.append(gf_box_left2)
splash.append(gf_box_left3)
splash.append(gf_box_left4)
# Right border
gf_box_right1 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=122, y=20)
gf_box_right2 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=122, y=30)
gf_box_right3 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=122, y=40)
gf_box_right4 = label.Label(terminalio.FONT, text="|", color=0xFFFFFF, x=122, y=50)
splash.append(gf_box_right1)
splash.append(gf_box_right2)
splash.append(gf_box_right3)
splash.append(gf_box_right4)

# G-force center crosshairs
gf_center_h = label.Label(terminalio.FONT, text="+", color=0xFFFFFF, x=93, y=35)
splash.append(gf_center_h)

# G-force dot (larger - will be updated in DisplayTask)
gf_dot = label.Label(terminalio.FONT, text="O", color=0xFFFFFF, x=93, y=35)
splash.append(gf_dot)

# Create log file with GPS data columns
log_filename = "/sd/session_{}.csv".format(int(time.monotonic()))
print(f"7. Creating log file: {log_filename}")
log_file = open(log_filename, "w")
log_file.write("timestamp_ms,accel_x,accel_y,accel_z,gforce_x,gforce_y,gforce_z,gforce_total,")
log_file.write("gps_fix,gps_lat,gps_lon,gps_alt_m,gps_speed_mph,gps_heading,gps_sats,gps_hdop\n")
print("   ✓ Log file created")

# Shared data buffer between tasks
data_buffer = {
    'accel': None,
    'gps': None,
    'sd_free_mb': 0,
    'sd_time_remaining_min': 0,
    'system': {
        'uptime': 0,
        'version': VERSION,
        'git_hash': GIT_HASH,
        'build_date': BUILD_DATE,
        'device_name': config['DEVICE_NAME']
    }
}

# ============================================================================
# Task Definitions
# ============================================================================

class AccelerometerTask(Task):
    """Read accelerometer at configured rate"""
    def __init__(self, lis3dh_sensor, buffer, sample_rate):
        interval = int(1000 / sample_rate)  # Convert Hz to ms
        super().__init__("Accelerometer", interval)
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
        
        # Store in shared buffer
        self.buffer['accel'] = {
            'x': x, 'y': y, 'z': z,
            'gx': gx, 'gy': gy, 'gz': gz,
            'g_total': g_total,
            'timestamp': time.monotonic()
        }


class GPSTask(Task):
    """Read GPS at configured rate"""
    def __init__(self, gps_module, buffer, update_rate):
        super().__init__("GPS", update_rate)
        self.gps = gps_module
        self.buffer = buffer
    
    def run(self):
        # Update GPS
        self.gps.update()
        
        # Parse GPS data
        if self.gps.has_fix:
            fix_quality = "3D" if self.gps.fix_quality_3d else "2D"
            
            # Convert speed from knots to MPH
            speed_mph = self.gps.speed_knots * 1.15078 if self.gps.speed_knots else 0
            
            # Get HDOP (horizontal dilution of precision)
            hdop = self.gps.hdop if self.gps.hdop else 99.9
            
            self.buffer['gps'] = {
                'fix': fix_quality,
                'lat': self.gps.latitude,
                'lon': self.gps.longitude,
                'alt_m': self.gps.altitude_m if self.gps.altitude_m else 0,
                'speed_mph': speed_mph,
                'heading': self.gps.track_angle_deg if self.gps.track_angle_deg else 0,
                'sats': self.gps.satellites,
                'hdop': hdop,
                'timestamp': self.gps.timestamp_utc,
                'has_fix': True
            }
        else:
            # No fix
            self.buffer['gps'] = {
                'fix': 'NoFix',
                'lat': 0,
                'lon': 0,
                'alt_m': 0,
                'speed_mph': 0,
                'heading': 0,
                'sats': self.gps.satellites if self.gps.satellites else 0,
                'hdop': 99.9,
                'timestamp': None,
                'has_fix': False
            }


class DisplayTask(Task):
    """Update OLED display at 5Hz with comprehensive status"""
    def __init__(self, labels, buffer, graph_scale):
        super().__init__("Display", 200)  # 200ms = 5Hz
        self.labels = labels
        self.buffer = buffer
        self.graph_scale = graph_scale
        # G-force graph bounds (right side of display)
        self.graph_center_x = 93
        self.graph_center_y = 35
        self.graph_min_x = 70
        self.graph_max_x = 116
        self.graph_min_y = 20
        self.graph_max_y = 50
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        # Update time & GPS fix
        if gps and gps['timestamp']:
            tm = gps['timestamp']
            time_str = "{:02d}:{:02d}".format(tm.tm_hour, tm.tm_min)
        else:
            time_str = "--:--"
        
        fix_str = gps['fix'] if gps else "NoFix"
        hdop_str = "{:.1f}".format(gps['hdop']) if gps and gps['hdop'] < 99 else "--"
        sats_str = "{}".format(gps['sats']) if gps else "0"
        
        self.labels['time'].text = time_str
        self.labels['gps_status'].text = fix_str
        self.labels['hdop'].text = hdop_str
        self.labels['sats'].text = sats_str
        
        # Update large speed display
        if gps:
            speed = int(gps['speed_mph'])
            self.labels['speed'].text = "{}".format(speed)
        else:
            self.labels['speed'].text = "0"
        
        # Update SD card time remaining
        time_remaining = self.buffer.get('sd_time_remaining_min', 0)
        hours = time_remaining // 60
        minutes = time_remaining % 60
        self.labels['sd'].text = "SD:{}h{}m".format(hours, minutes)
        
        # Update G-force dot position
        if accel:
            # Calculate position (larger dot, stays in bounds)
            x_offset = int(accel['gx'] * self.graph_scale)
            y_offset = int(-accel['gy'] * self.graph_scale)  # Negative = forward is up
            
            new_x = self.graph_center_x + x_offset
            new_y = self.graph_center_y + y_offset
            
            # Clamp to graph bounds
            new_x = max(self.graph_min_x, min(self.graph_max_x, new_x))
            new_y = max(self.graph_min_y, min(self.graph_max_y, new_y))
            
            self.labels['gf_dot'].x = new_x
            self.labels['gf_dot'].y = new_y


class SDLoggerTask(Task):
    """Log accelerometer + GPS data to SD card"""
    def __init__(self, file, buffer, flush_size, sample_interval):
        super().__init__("SD Logger", sample_interval)
        self.file = file
        self.buffer = buffer
        self.write_buffer = []
        self.flush_size = flush_size
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        if not accel:
            return
        
        # Format CSV line with accelerometer data
        timestamp = int(accel['timestamp'] * 1000)
        line = "{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},".format(
            timestamp,
            accel['x'], accel['y'], accel['z'],
            accel['gx'], accel['gy'], accel['gz'],
            accel['g_total']
        )
        
        # Add GPS data (or empty fields if no GPS)
        if gps and gps['has_fix']:
            line += "{},{:.6f},{:.6f},{:.1f},{:.1f},{:.1f},{},{:.1f}\n".format(
                gps['fix'],
                gps['lat'], gps['lon'], gps['alt_m'],
                gps['speed_mph'], gps['heading'],
                gps['sats'], gps['hdop']
            )
        else:
            line += "NoFix,0,0,0,0,0,0,99.9\n"
        
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


class SDSpaceTask(Task):
    """Check SD card free space and calculate time remaining"""
    def __init__(self, buffer, bytes_per_sample, sample_rate):
        super().__init__("SD Space", 10000)  # 10 seconds
        self.buffer = buffer
        self.bytes_per_sample = bytes_per_sample
        self.sample_rate = sample_rate
    
    def run(self):
        try:
            stat = os.statvfs("/sd")
            # f_frsize * f_bavail = free space in bytes
            free_bytes = stat[0] * stat[3]
            free_mb = free_bytes // (1024 * 1024)
            self.buffer['sd_free_mb'] = free_mb
            
            # Calculate time remaining
            # bytes/second = bytes_per_sample * sample_rate
            bytes_per_second = self.bytes_per_sample * self.sample_rate
            seconds_remaining = free_bytes // bytes_per_second if bytes_per_second > 0 else 0
            minutes_remaining = seconds_remaining // 60
            
            self.buffer['sd_time_remaining_min'] = minutes_remaining
            
        except Exception as e:
            self.buffer['sd_free_mb'] = 0
            self.buffer['sd_time_remaining_min'] = 0


class SDMaintenanceTask(Task):
    """Manage SD card space - delete old files when low"""
    def __init__(self, buffer, high_water_mb, low_water_mb, check_interval):
        super().__init__("SD Maintenance", check_interval * 1000)  # Convert to ms
        self.buffer = buffer
        self.high_water_mb = high_water_mb
        self.low_water_mb = low_water_mb
    
    def run(self):
        free_mb = self.buffer.get('sd_free_mb', 999999)
        
        if free_mb < self.high_water_mb:
            print(f"\n[SD Maintenance] Low space: {free_mb}MB (threshold: {self.high_water_mb}MB)")
            self.cleanup_old_files()
    
    def cleanup_old_files(self):
        """Delete oldest session files until we reach low water mark"""
        try:
            # Get all session files
            files = []
            for f in os.listdir("/sd"):
                if f.startswith("session_") and f.endswith(".csv"):
                    path = "/sd/" + f
                    stat = os.stat(path)
                    files.append((path, stat[7]))  # (path, mtime)
            
            if not files:
                print("   No session files to delete")
                return
            
            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[1])
            
            deleted_count = 0
            for path, _ in files:
                # Check current free space
                stat = os.statvfs("/sd")
                free_mb = (stat[0] * stat[3]) // (1024 * 1024)
                
                if free_mb >= self.low_water_mb:
                    break
                
                # Delete file
                try:
                    size = os.stat(path)[6]
                    os.remove(path)
                    deleted_count += 1
                    print(f"   Deleted: {path} ({size} bytes)")
                except Exception as e:
                    print(f"   Failed to delete {path}: {e}")
            
            print(f"   Cleanup complete: {deleted_count} files deleted")
            
        except Exception as e:
            print(f"   Cleanup error: {e}")


class StatusTask(Task):
    """Print status to console at configured interval"""
    def __init__(self, buffer, interval_ms, debug_enabled):
        super().__init__("Status", interval_ms)
        self.buffer = buffer
        self.debug_enabled = debug_enabled
    
    def run(self):
        if not self.debug_enabled:
            return
        
        # Update uptime
        uptime = int(time.monotonic())
        self.buffer['system']['uptime'] = uptime
        
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        print("\n" + "=" * 60)
        print(f"Uptime: {uptime}s | SD Free: {self.buffer.get('sd_free_mb', 0)}MB "
              f"({self.buffer.get('sd_time_remaining_min', 0)//60}h {self.buffer.get('sd_time_remaining_min', 0)%60}m)")
        
        if accel:
            print(f"G-Force: X={accel['gx']:+.2f} Y={accel['gy']:+.2f} Z={accel['gz']:+.2f} | Total={accel['g_total']:.2f}g")
        
        if gps:
            print(f"GPS: {gps['fix']} | Sats: {gps['sats']} | HDOP: {gps['hdop']:.1f} | "
                  f"Speed: {gps['speed_mph']:.1f}mph | Heading: {gps['heading']:.0f}°")
            if gps['has_fix']:
                print(f"Position: {gps['lat']:.6f}°, {gps['lon']:.6f}° | Alt: {gps['alt_m']:.1f}m")
        
        print("=" * 60)


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
            print(f"\n[WiFi] AP: {self.wifi_ap.ssid} | IP: {self.wifi_ap.ip_address}")
            print(f"[WiFi] Requests served: {self.web_server.request_count if self.web_server else 0}")


# ============================================================================
# WiFi and Web Server Setup
# ============================================================================

print("\n8. Setting up WiFi Access Point...")
wifi_ap = WiFiAPTask(ssid=config['WIFI_SSID'], password=config['WIFI_PASSWORD'])
if wifi_ap.start():
    print("   ✓ WiFi AP started")
    
    print("9. Starting web server...")
    web_server = WebServerTask(data_buffer, wifi_ap)
    if web_server.start():
        print("   ✓ Web server started")
    else:
        print("   ✗ Web server failed - continuing without web interface")
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
    'sd': sd_label,
    'gf_dot': gf_dot
}

# Add tasks
accel_task = AccelerometerTask(lis3dh, data_buffer, config['ACCEL_SAMPLE_RATE'])
gps_task = GPSTask(gps, data_buffer, config['GPS_UPDATE_RATE'])
display_task = DisplayTask(display_labels, data_buffer, config['GFORCE_GRAPH_SCALE'])
logger_task = SDLoggerTask(log_file, data_buffer, config['LOG_FLUSH_SIZE'], 
                           int(1000 / config['ACCEL_SAMPLE_RATE']))
sd_space_task = SDSpaceTask(data_buffer, config['BYTES_PER_SAMPLE'], config['ACCEL_SAMPLE_RATE'])
sd_maint_task = SDMaintenanceTask(data_buffer, config['SD_HIGH_WATER_MB'], 
                                  config['SD_LOW_WATER_MB'], config['SD_CHECK_INTERVAL'])
status_task = StatusTask(data_buffer, config['STATUS_INTERVAL'], config['SERIAL_DEBUG'])

scheduler.add_task(accel_task)
scheduler.add_task(gps_task)
scheduler.add_task(display_task)
scheduler.add_task(logger_task)
scheduler.add_task(sd_space_task)
scheduler.add_task(sd_maint_task)
scheduler.add_task(status_task)

# Add web server polling task if WiFi is active
if web_server and wifi_ap:
    wifi_monitor_task = WiFiMonitorTask(wifi_ap, web_server)
    scheduler.add_task(wifi_monitor_task)
if web_server:
    webserver_task = WebServerPollingTask(web_server)
    scheduler.add_task(webserver_task)

print("\n" + "=" * 60)
print("Starting data acquisition...")
print("Connect to WiFi: {}".format(wifi_ap.ssid if wifi_ap.ap_active else "N/A"))
print("Web interface: http://{}".format(wifi_ap.ip_address if wifi_ap.ap_active else "N/A"))
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
    print("✓ SD card buffer flushed")
    
    # Print performance statistics
    scheduler.print_stats()
    
    # File info
    print(f"\nLog file: {log_filename}")
    try:
        stat = os.stat(log_filename)
        samples = (stat[6] - 150) // config['BYTES_PER_SAMPLE']
        print(f"File size: {stat[6]} bytes ({stat[6]/1024:.1f} KB)")
        print(f"Estimated samples: ~{samples}")
    except:
        pass
    
    print("\n✓ Shutdown complete")
