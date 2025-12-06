"""
OpenPonyLogger - Main Program with State Machine Scheduler
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
from wifi_server import WiFiAPTask, WebServerTask
from scheduler import Task, Scheduler

print("=" * 60)
print("OpenPonyLogger - State Machine Version")
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

# OLED Display
print("4. Initializing OLED display...")
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
print("   ✓ OLED initialized")

# Create display layout
splash = displayio.Group()
display.root_group = splash

title_label = label.Label(terminalio.FONT, text="OpenPonyLogger", color=0xFFFFFF, x=10, y=5)
status_label = label.Label(terminalio.FONT, text="Starting...", color=0xFFFFFF, x=5, y=16)
gx_label = label.Label(terminalio.FONT, text="X: +0.00g", color=0xFFFFFF, x=5, y=30)
gy_label = label.Label(terminalio.FONT, text="Y: +0.00g", color=0xFFFFFF, x=5, y=40)
gz_label = label.Label(terminalio.FONT, text="Z: +0.00g", color=0xFFFFFF, x=5, y=50)
total_label = label.Label(terminalio.FONT, text="T: 1.00g", color=0xFFFFFF, x=5, y=60)

splash.append(title_label)
splash.append(status_label)
splash.append(gx_label)
splash.append(gy_label)
splash.append(gz_label)
splash.append(total_label)

# Create log file
log_filename = "/sd/accel_log_{}.csv".format(int(time.monotonic()))
print(f"5. Creating log file: {log_filename}")
log_file = open(log_filename, "w")
log_file.write("timestamp_ms,accel_x,accel_y,accel_z,gforce_x,gforce_y,gforce_z,gforce_total\n")
print("   ✓ Log file created")

# Shared data buffer between tasks
data_buffer = {}

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


class DisplayTask(Task):
    """Update OLED display at 5Hz"""
    def __init__(self, labels, buffer):
        super().__init__("Display", 200)  # 200ms = 5Hz
        self.labels = labels
        self.buffer = buffer
    
    def run(self):
        accel = self.buffer.get('accel')
        if accel:
            self.labels['gx'].text = "X: {:+.2f}g".format(accel['gx'])
            self.labels['gy'].text = "Y: {:+.2f}g".format(accel['gy'])
            self.labels['gz'].text = "Z: {:+.2f}g".format(accel['gz'])
            self.labels['total'].text = "T: {:.2f}g".format(accel['g_total'])


class SDLoggerTask(Task):
    """Log data to SD card - buffer 50 samples before flush"""
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
    def __init__(self, label, scheduler_ref, buffer):
        super().__init__("Status", 1000)  # 1000ms = 1Hz
        self.label = label
        self.scheduler = scheduler_ref
        self.buffer = buffer
    
    def run(self):
        # Update status on OLED
        uptime = int(time.monotonic())
        self.label.text = "Up: {}s".format(uptime)
        
        # Print to console
        accel = self.buffer.get('accel')
        if accel:
            print("Uptime: {}s | G-Force: X={:+.2f} Y={:+.2f} Z={:+.2f} | Total={:.2f}g".format(
                uptime, accel['gx'], accel['gy'], accel['gz'], accel['g_total']
            ))

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
        super().__init__("WiFi Monitor", 5000)  # Every 5 seconds
        self.wifi_ap = wifi_ap
        self.web_server = web_server
    
    def run(self):
        if self.wifi_ap.ap_active:
            print(f"\n[WiFi Monitor] AP Status:")
            print(f"  SSID: {self.wifi_ap.ssid}")
            print(f"  IP: {self.wifi_ap.ip_address}")
            print(f"  Server requests: {self.web_server.request_count if self.web_server else 'N/A'}")
            
            # Try to get connected clients (if supported)
            try:
                if hasattr(wifi.radio, 'stations'):
                    stations = wifi.radio.stations
                    print(f"  Connected clients: {len(stations)}")
                    for station in stations:
                        print(f"    - {station}")
            except:
                pass

# ============================================================================
# Main Program
# ============================================================================

# ============================================================================
# WiFi and Web Server Setup
# ============================================================================

print("\n6. Setting up WiFi Access Point...")
wifi_ap = WiFiAPTask(ssid="OpenPonyLogger", password="mustanggt")  # Change password as desired
if wifi_ap.start():
    print("   ✓ WiFi AP started")
    
    print("7. Starting web server...")
    web_server = WebServerTask(data_buffer, wifi_ap)
    if web_server.start():
        print("   ✓ Web server started")
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
    'gx': gx_label,
    'gy': gy_label,
    'gz': gz_label,
    'total': total_label
}

# Add tasks
accel_task = AccelerometerTask(lis3dh, data_buffer)
display_task = DisplayTask(display_labels, data_buffer)
logger_task = SDLoggerTask(log_file, data_buffer, flush_size=50)
status_task = StatusTask(status_label, scheduler, data_buffer)

scheduler.add_task(accel_task)
scheduler.add_task(display_task)
scheduler.add_task(logger_task)
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
        samples = (stat[6] - 100) // 60  # Rough estimate (60 bytes per line)
        print(f"File size: {stat[6]} bytes ({stat[6]/1024:.1f} KB)")
        print(f"Estimated samples: ~{samples}")
    except:
        pass
    
    status_label.text = "Stopped"
    print("\n✓ Shutdown complete")
