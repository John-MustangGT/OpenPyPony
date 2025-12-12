"""
main.py - OpenPonyLogger Pico Firmware
CircuitPython version for rapid deployment
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

# ============================================================================
# Hardware Setup
# ============================================================================

print("OpenPonyLogger v2.0 - Initializing...")

# I2C (Accelerometer + OLED)
#i2c = busio.I2C(board.GP9, board.GP8)
i2c = board.STEMMA_I2C()

# LIS3DH Accelerometer
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x18)
lis3dh.range = adafruit_lis3dh.RANGE_2_G
lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ

# GPS (UART)
gps_uart = busio.UART(board.GP8, board.GP9, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(gps_uart, debug=False)
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')  # GGA + RMC
#gps.send_command(b'PMTK220,1000')  # 1Hz update
gps.send_command(b'PMTK220,5000')  # 5Hz update

# SD Card
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
sdcard = sdcardio.SDCard(spi, board.GP17)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# OLED Display
displayio.release_displays()
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# UART to ESP-01S
#esp_uart = busio.UART(board.GP0, board.GP1, baudrate=115200)
esp_uart = busio.UART(board.GP0, board.GP1, baudrate=9600)

# RTC
rtc_clock = rtc.RTC()
rtc_synced = False

print("✓ Hardware initialized")

# ============================================================================
# Display Setup
# ============================================================================

splash = displayio.Group()
display.root_group = splash

line1 = label.Label(terminalio.FONT, text="OpenPonyLogger", color=0xFFFFFF, x=5, y=5)
line2 = label.Label(terminalio.FONT, text="Init...", color=0xFFFFFF, x=5, y=16)
line3 = label.Label(terminalio.FONT, text="GPS: No Fix", color=0xFFFFFF, x=5, y=28)
line4 = label.Label(terminalio.FONT, text="G: 0.00g", color=0xFFFFFF, x=5, y=40)
line5 = label.Label(terminalio.FONT, text="Logging: OFF", color=0xFFFFFF, x=5, y=52)

for line in [line1, line2, line3, line4, line5]:
    splash.append(line)

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
        
    def start(self):
        """Start new recording session"""
        timestamp = time.monotonic()
        self.filename = f"/sd/session_{int(timestamp)}.csv"
        self.file = open(self.filename, "w")
        self.file.write("timestamp,gx,gy,gz,g_total,lat,lon,alt,speed,sats\n")
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
        line += f"{data['gps']['alt']},{data['gps']['speed']},{data['gps']['sats']}\n"
        
        self.file.write(line)
        self.sample_count += 1
        
        # Flush every 50 samples
        if self.sample_count % 50 == 0:
            self.file.flush()
    
    def stop(self):
        """Stop current session"""
        if self.file:
            self.file.flush()
            self.file.close()
        self.active = False
        duration = time.monotonic() - self.start_time if self.start_time else 0
        print(f"✓ Session stopped: {self.sample_count} samples, {duration:.1f}s")
        return self.filename

session = Session()

# ============================================================================
# Serial Protocol Handler
# ============================================================================

class SerialProtocol:
    """Handle commands from ESP-01S"""
    
    def __init__(self, uart):
        self.uart = uart
        self.buffer = ""
    
    def process(self):
        """Check for incoming commands"""
        if self.uart.in_waiting:
            data = self.uart.read(self.uart.in_waiting)
            self.buffer += data.decode('utf-8', 'ignore')
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                self.handle_command(line.strip())
    
    def handle_command(self, cmd):
        """Execute command"""
        if cmd == "LIST":
            self.list_sessions()
        elif cmd.startswith("GET "):
            filename = cmd[4:].strip()
            self.send_file(filename)
        elif cmd == "START":
            session.start()
            self.send_response("OK SESSION_STARTED")
        elif cmd == "STOP":
            filename = session.stop()
            self.send_response(f"OK SESSION_STOPPED {filename}")
    
    def list_sessions(self):
        """Send list of session files"""
        try:
            files = [f for f in os.listdir("/sd") if f.startswith("session_")]
            files.sort(reverse=True)  # Newest first
            files = files[:10]  # Last 10
            
            response = "FILES " + ",".join(files)
            self.send_response(response)
        except Exception as e:
            self.send_response(f"ERROR {e}")
    
    def send_file(self, filename):
        """Send file contents"""
        filepath = f"/sd/{filename}"
        try:
            with open(filepath, 'r') as f:
                self.uart.write(f"FILE_START {filename}\n".encode())
                
                # Send in chunks
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    self.uart.write(chunk.encode())
                
                self.uart.write(b"FILE_END\n")
        except Exception as e:
            self.send_response(f"ERROR {e}")
    
    def send_response(self, msg):
        """Send response to ESP"""
	print(f"Sending: {msg}\n".encode())
        self.uart.write(f"{msg}\n".encode())

protocol = SerialProtocol(esp_uart)

# ============================================================================
# Main Loop
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
    speed = gps.speed_knots if gps.speed_knots else 0.0
    sats = gps.satellites if gps.satellites else 0
    
    # RTC sync from GPS
    global rtc_synced
    if gps.has_fix and not rtc_synced and gps.timestamp_utc:
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
    
    return {
        "t": time.monotonic_ns() // 1000000,  # ms
        "rtc_synced": rtc_synced,
        "g": {
            "x": round(gx, 2),
            "y": round(gy, 2),
            "z": round(gz, 2),
            "total": round(g_total, 2)
        },
        "gps": {
            "fix": gps.has_fix,
            "lat": round(lat, 6) if lat else 0,
            "lon": round(lon, 6) if lon else 0,
            "alt": round(alt, 1),
            "speed": round(speed, 1),
            "sats": sats,
            "hdop": round(gps.hdop, 1) if gps.hdop else 0
        }
    }

def update_display(data):
    """Update OLED display"""
    line2.text = f"RTC: {'GPS' if rtc_synced else 'LOCAL'}"
    
    if data['gps']['fix']:
        line3.text = f"GPS: {data['gps']['sats']} sats"
    else:
        line3.text = "GPS: No Fix"
    
    line4.text = f"G: {data['g']['total']:.2f}g"
    line5.text = f"Log: {'ON' if session.active else 'OFF'}"

def send_telemetry(data):
    """Send JSON telemetry to ESP-01S"""
    json_str = json.dumps(data) + "\n"
    esp_uart.write(json_str.encode())
    print(f"json:{json_str}\n")

# Auto-start logging
session.start()
line5.text = "Log: ON"

print("\n" + "="*50)
print("OpenPonyLogger Running")
print("="*50)

last_display_update = 0
last_telemetry_send = 0

while True:
    try:
        # Process serial commands
        protocol.process()
        
        # Read sensors
        data = read_sensors()
        
        # Log to SD card
        if session.active:
            session.log(data)
        
        # Update display (5Hz)
        now = time.monotonic()
        if now - last_display_update > 0.2:
            last_display_update = now
            update_display(data)
        
        # Send telemetry (10Hz)
        if now - last_telemetry_send > 0.1:
            last_telemetry_send = now
            send_telemetry(data)
        
        time.sleep(0.01)  # 100Hz main loop
        
    except KeyboardInterrupt:
        print("\nStopping...")
        session.stop()
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
