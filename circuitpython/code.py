"""
OpenPonyLogger - Main Program with GPS Support
Logs accelerometer + GPS data with comprehensive OLED status display
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
    VERSION = "unknown"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

print("=" * 60)
print(f"OpenPyPony v{VERSION}")
print(f"Commit: {GIT_HASH}")
print(f"Built: {BUILD_DATE}")
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
lis3dh.range = adafruit_lis3dh.RANGE_2_G
lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ
print("   ✓ LIS3DH initialized")

# GPS Module
print("4. Initializing GPS module...")
uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
# Configure GPS
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')  # RMC + GGA only
gps.send_command(b'PMTK220,1000')  # 1Hz update rate
print("   ✓ GPS initialized")

# OLED Display
print("5. Initializing OLED display...")
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
print("   ✓ OLED initialized")

# Create display layout - comprehensive status
splash = displayio.Group()
display.root_group = splash

# Line 1: Time & GPS Fix
time_label = label.Label(terminalio.FONT, text="--:--:-- NoFix", color=0xFFFFFF, x=0, y=5)
# Line 2: Speed & Heading
speed_label = label.Label(terminalio.FONT, text="0mph 0deg", color=0xFFFFFF, x=0, y=15)
# Line 3-5: G-Force cartesian graph (will be drawn with pixels)
# Line 6: SD Card space
sd_label = label.Label(terminalio.FONT, text="SD: --MB", color=0xFFFFFF, x=0, y=58)

splash.append(time_label)
splash.append(speed_label)
splash.append(sd_label)

# Create log file with GPS data columns
log_filename = "/sd/session_{}.csv".format(int(time.monotonic()))
print(f"6. Creating log file: {log_filename}")
log_file = open(log_filename, "w")
log_file.write("timestamp_ms,accel_x,accel_y,accel_z,gforce_x,gforce_y,gforce_z,gforce_total,")
log_file.write("gps_fix,gps_lat,gps_lon,gps_alt_m,gps_speed_mph,gps_heading,gps_sats\n")
print("   ✓ Log file created")

# Shared data buffer between tasks
data_buffer = {
    'accel': None,
    'gps': None,
    'sd_free_mb': 0
}

# ============================================================================
# Task Definitions
# ============================================================================

class AccelerometerTask(Task):
    """Read accelerometer at 10Hz"""
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
        
        # Store in shared buffer
        self.buffer['accel'] = {
            'x': x, 'y': y, 'z': z,
            'gx': gx, 'gy': gy, 'gz': gz,
            'g_total': g_total,
            'timestamp': time.monotonic()
        }


class GPSTask(Task):
    """Read GPS at 1Hz"""
    def __init__(self, gps_module, buffer):
        super().__init__("GPS", 1000)  # 1000ms = 1Hz
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
            
            self.buffer['gps'] = {
                'fix': fix_quality,
                'lat': self.gps.latitude,
                'lon': self.gps.longitude,
                'alt_m': self.gps.altitude_m if self.gps.altitude_m else 0,
                'speed_mph': speed_mph,
                'heading': self.gps.track_angle_deg if self.gps.track_angle_deg else 0,
                'sats': self.gps.satellites,
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
                'timestamp': None,
                'has_fix': False
            }


class DisplayTask(Task):
    """Update OLED display at 5Hz with comprehensive status"""
    def __init__(self, labels, buffer, display_obj):
        super().__init__("Display", 200)  # 200ms = 5Hz
        self.labels = labels
        self.buffer = buffer
        self.display = display_obj
        self.graph_center_x = 96  # Right side of screen
        self.graph_center_y = 38  # Middle of graph area
        self.graph_scale = 15     # Pixels per G
    
    def run(self):
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        # Update time & GPS fix
        if gps and gps['timestamp']:
            tm = gps['timestamp']
            time_str = "{:02d}:{:02d}:{:02d}".format(tm.tm_hour, tm.tm_min, tm.tm_sec)
        else:
            time_str = "--:--:--"
        
        fix_str = gps['fix'] if gps else "NoFix"
        self.labels['time'].text = "{} {}".format(time_str, fix_str)
        
        # Update speed & heading
        if gps:
            speed = int(gps['speed_mph'])
            heading = int(gps['heading'])
            self.labels['speed'].text = "{}mph {}deg".format(speed, heading)
        else:
            self.labels['speed'].text = "0mph 0deg"
        
        # Update SD card space
        sd_free = self.buffer.get('sd_free_mb', 0)
        self.labels['sd'].text = "SD: {}MB".format(sd_free)
        
        # Draw G-force cartesian graph
        if accel:
            self.draw_gforce_graph(accel['gx'], accel['gy'])
    
    def draw_gforce_graph(self, gx, gy):
        """Draw small cartesian graph of lateral/longitudinal G-forces"""
        # Clear graph area (lines 25-55, x: 64-128)
        # Note: In production, use a bitmap overlay for efficiency
        
        # For now, we'll update text representation
        # In a full implementation, you'd use displayio shapes or a bitmap
        # This is a simplified version showing the concept
        
        # Calculate position on graph
        x_pos = int(self.graph_center_x + gx * self.graph_scale)
        y_pos = int(self.graph_center_y - gy * self.graph_scale)  # Invert Y
        
        # Clamp to display bounds
        x_pos = max(64, min(127, x_pos))
        y_pos = max(25, min(55, y_pos))
        
        # Note: Full implementation would draw crosshairs and dot
        # For text-only display, we show values
        # Add a small text indicator
        if not hasattr(self, 'gforce_indicator'):
            self.gforce_indicator = label.Label(
                terminalio.FONT, 
                text=".", 
                color=0xFFFFFF, 
                x=x_pos, 
                y=y_pos
            )
            self.display.root_group.append(self.gforce_indicator)
        else:
            self.gforce_indicator.x = x_pos
            self.gforce_indicator.y = y_pos


class SDLoggerTask(Task):
    """Log accelerometer + GPS data to SD card"""
    def __init__(self, file, buffer, flush_size=50):
        super().__init__("SD Logger", 100)  # 100ms = 10Hz
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
            line += "{},{:.6f},{:.6f},{:.1f},{:.1f},{:.1f},{}\n".format(
                gps['fix'],
                gps['lat'], gps['lon'], gps['alt_m'],
                gps['speed_mph'], gps['heading'],
                gps['sats']
            )
        else:
            line += "NoFix,0,0,0,0,0,0\n"
        
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
    """Check SD card free space every 10 seconds"""
    def __init__(self, buffer):
        super().__init__("SD Space", 10000)  # 10000ms = 10 seconds
        self.buffer = buffer
    
    def run(self):
        try:
            stat = os.statvfs("/sd")
            # f_frsize * f_bavail = free space in bytes
            free_bytes = stat[0] * stat[3]
            free_mb = free_bytes // (1024 * 1024)
            self.buffer['sd_free_mb'] = free_mb
        except:
            self.buffer['sd_free_mb'] = 0


class StatusTask(Task):
    """Print status to console every 5 seconds"""
    def __init__(self, buffer):
        super().__init__("Status", 5000)  # 5000ms = 5 seconds
        self.buffer = buffer
    
    def run(self):
        # Print comprehensive status
        uptime = int(time.monotonic())
        accel = self.buffer.get('accel')
        gps = self.buffer.get('gps')
        
        print("\n" + "=" * 60)
        print(f"Uptime: {uptime}s | SD Free: {self.buffer.get('sd_free_mb', 0)}MB")
        
        if accel:
            print(f"G-Force: X={accel['gx']:+.2f} Y={accel['gy']:+.2f} Z={accel['gz']:+.2f} | Total={accel['g_total']:.2f}g")
        
        if gps:
            print(f"GPS: {gps['fix']} | Sats: {gps['sats']} | Speed: {gps['speed_mph']:.1f}mph | Heading: {gps['heading']:.0f}°")
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

print("\n7. Setting up WiFi Access Point...")
wifi_ap = WiFiAPTask(ssid="OpenPonyLogger", password="mustanggt")
if wifi_ap.start():
    print("   ✓ WiFi AP started")
    
    print("8. Starting web server...")
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
    'speed': speed_label,
    'sd': sd_label
}

# Add tasks
accel_task = AccelerometerTask(lis3dh, data_buffer)
gps_task = GPSTask(gps, data_buffer)
display_task = DisplayTask(display_labels, data_buffer, display)
logger_task = SDLoggerTask(log_file, data_buffer, flush_size=50)
sd_space_task = SDSpaceTask(data_buffer)
status_task = StatusTask(data_buffer)

scheduler.add_task(accel_task)
scheduler.add_task(gps_task)
scheduler.add_task(display_task)
scheduler.add_task(logger_task)
scheduler.add_task(sd_space_task)
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
        samples = (stat[6] - 150) // 80  # Rough estimate (80 bytes per line with GPS)
        print(f"File size: {stat[6]} bytes ({stat[6]/1024:.1f} KB)")
        print(f"Estimated samples: ~{samples}")
    except:
        pass
    
    print("\n✓ Shutdown complete")
