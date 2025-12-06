"""
GPS Test Program with I2C Resource Reset
Tests ATGM336H GPS module with SSD1306 OLED display

This version resets the I2C bus before initializing.
"""

import board
import busio
import time
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
from i2cdisplaybus import I2CDisplayBus

print("\n" + "="*50)
print("OpenPonyLogger GPS Test - Initializing...")
print("="*50)

# Release any existing displays and I2C
displayio.release_displays()

# Try to deinit any existing I2C on GP8/GP9
try:
    temp_i2c = busio.I2C(board.GP9, board.GP8)
    temp_i2c.deinit()
    print("Released existing I2C on GP8/GP9")
except:
    pass

# Small delay to let hardware settle
time.sleep(0.1)

# Initialize UART for GPS (GP0=TX from GPS, GP1=RX to GPS)
print("Initializing GPS UART on GP0/GP1...")
uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=0.1)

# Initialize I2C for OLED with explicit pull-ups
print("Initializing I2C on GP8/GP9...")
try:
    i2c = busio.I2C(board.GP9, board.GP8)  # SCL=GP9, SDA=GP8
    print("I2C initialized successfully")
except ValueError as e:
    print(f"ERROR: I2C failed to initialize: {e}")
    print("\nTrying alternate configuration (no OLED)...")
    i2c = None

# Initialize OLED Display (128x64) only if I2C worked
display = None
if i2c:
    try:
        print("Initializing OLED display...")
        display_bus = I2CDisplayBus(i2c, device_address=0x3C)
        display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
        print("OLED display ready")
    except Exception as e:
        print(f"OLED initialization failed: {e}")
        print("Continuing with serial output only...")
        display = None

# Create display group if we have a display
if display:
    splash = displayio.Group()
    display.root_group = splash

    title_label = label.Label(
        terminalio.FONT, text="GPS Test", color=0xFFFFFF, x=0, y=4
    )
    status_label = label.Label(
        terminalio.FONT, text="Waiting...", color=0xFFFFFF, x=0, y=14
    )
    lat_label = label.Label(
        terminalio.FONT, text="Lat: --", color=0xFFFFFF, x=0, y=24
    )
    lon_label = label.Label(
        terminalio.FONT, text="Lon: --", color=0xFFFFFF, x=0, y=34
    )
    alt_label = label.Label(
        terminalio.FONT, text="Alt: --", color=0xFFFFFF, x=0, y=44
    )
    sats_label = label.Label(
        terminalio.FONT, text="Sats: 0", color=0xFFFFFF, x=0, y=54
    )

    splash.append(title_label)
    splash.append(status_label)
    splash.append(lat_label)
    splash.append(lon_label)
    splash.append(alt_label)
    splash.append(sats_label)

# GPS data storage
gps_data = {
    'latitude': None,
    'lat_dir': None,
    'longitude': None,
    'lon_dir': None,
    'altitude': None,
    'satellites': 0,
    'fix_quality': 0,
    'hdop': None,
    'speed': None,
    'heading': None,
    'fix_type': 'No Fix'
}

def parse_coordinate(coord_str, direction):
    """Convert NMEA coordinate format to decimal degrees"""
    if not coord_str or not direction:
        return None
    
    try:
        if len(coord_str) < 4:
            return None
            
        dot_pos = coord_str.find('.')
        if dot_pos == -1:
            return None
            
        if direction in ['N', 'S']:
            degrees = float(coord_str[:2])
            minutes = float(coord_str[2:])
        else:
            degrees = float(coord_str[:3])
            minutes = float(coord_str[3:])
        
        decimal = degrees + (minutes / 60.0)
        
        if direction in ['S', 'W']:
            decimal = -decimal
            
        return decimal
        
    except (ValueError, IndexError):
        return None

def parse_gga(sentence):
    """Parse GPGGA sentence"""
    parts = sentence.split(',')
    if len(parts) < 15:
        return
    
    try:
        gps_data['latitude'] = parse_coordinate(parts[2], parts[3])
        gps_data['lat_dir'] = parts[3]
        gps_data['longitude'] = parse_coordinate(parts[4], parts[5])
        gps_data['lon_dir'] = parts[5]
        gps_data['fix_quality'] = int(parts[6]) if parts[6] else 0
        gps_data['satellites'] = int(parts[7]) if parts[7] else 0
        gps_data['hdop'] = float(parts[8]) if parts[8] else None
        gps_data['altitude'] = float(parts[9]) if parts[9] else None
        
        if gps_data['fix_quality'] == 0:
            gps_data['fix_type'] = 'No Fix'
        elif gps_data['fix_quality'] == 1:
            gps_data['fix_type'] = 'GPS'
        elif gps_data['fix_quality'] == 2:
            gps_data['fix_type'] = 'DGPS'
        else:
            gps_data['fix_type'] = f'Fix {gps_data["fix_quality"]}'
            
    except (ValueError, IndexError) as e:
        print(f"Parse error: {e}")

def parse_rmc(sentence):
    """Parse GPRMC sentence"""
    parts = sentence.split(',')
    if len(parts) < 12:
        return
    
    try:
        if parts[7]:
            gps_data['speed'] = float(parts[7])
        if parts[8]:
            gps_data['heading'] = float(parts[8])
    except (ValueError, IndexError) as e:
        print(f"RMC parse error: {e}")

def verify_checksum(sentence):
    """Verify NMEA sentence checksum"""
    if '*' not in sentence:
        return False
    
    try:
        data, checksum = sentence.split('*')
        if data.startswith('$'):
            data = data[1:]
        
        calc_checksum = 0
        for char in data:
            calc_checksum ^= ord(char)
        
        return calc_checksum == int(checksum, 16)
        
    except (ValueError, IndexError):
        return False

def process_nmea_sentence(sentence):
    """Process a single NMEA sentence"""
    sentence = sentence.strip()
    
    if not sentence.startswith('$'):
        return
    
    if not verify_checksum(sentence):
        print(f"Checksum failed: {sentence}")
        return
    
    if 'GGA' in sentence:
        parse_gga(sentence)
        print(f"GGA: {sentence}")
    elif 'RMC' in sentence:
        parse_rmc(sentence)
        print(f"RMC: {sentence}")
    elif 'GSA' in sentence or 'GSV' in sentence:
        print(f"SAT: {sentence}")

def update_display():
    """Update OLED display with current GPS data"""
    if not display:
        return
    
    status_label.text = gps_data['fix_type']
    
    if gps_data['latitude'] is not None:
        lat_label.text = f"Lat:{gps_data['latitude']:8.5f}"
    else:
        lat_label.text = "Lat: --"
    
    if gps_data['longitude'] is not None:
        lon_label.text = f"Lon:{gps_data['longitude']:8.5f}"
    else:
        lon_label.text = "Lon: --"
    
    if gps_data['altitude'] is not None:
        alt_label.text = f"Alt:{gps_data['altitude']:6.1f}m"
    else:
        alt_label.text = "Alt: --"
    
    sats_label.text = f"Sats: {gps_data['satellites']}"

def print_gps_summary():
    """Print formatted GPS data summary to console"""
    print("\n=== GPS Data Summary ===")
    print(f"Fix Type: {gps_data['fix_type']}")
    print(f"Satellites: {gps_data['satellites']}")
    
    if gps_data['latitude'] is not None:
        print(f"Latitude:  {gps_data['latitude']:.6f}° {gps_data['lat_dir']}")
    else:
        print("Latitude:  No data")
    
    if gps_data['longitude'] is not None:
        print(f"Longitude: {gps_data['longitude']:.6f}° {gps_data['lon_dir']}")
    else:
        print("Longitude: No data")
    
    if gps_data['altitude'] is not None:
        print(f"Altitude:  {gps_data['altitude']:.1f} m")
    
    if gps_data['hdop'] is not None:
        print(f"HDOP:      {gps_data['hdop']:.1f}")
    
    if gps_data['speed'] is not None:
        print(f"Speed:     {gps_data['speed']:.1f} knots ({gps_data['speed'] * 1.15078:.1f} mph)")
    
    if gps_data['heading'] is not None:
        print(f"Heading:   {gps_data['heading']:.1f}°")
    
    print("=======================\n")

# Main program
print("\n" + "="*50)
if display:
    print("Mode: GPS + OLED Display")
else:
    print("Mode: GPS Serial Output Only")
print("="*50)
print("\nWaiting for GPS data...")
print("-"*50 + "\n")

sentence_buffer = ""
last_summary_time = time.monotonic()
last_display_update = time.monotonic()

while True:
    data = uart.read(128)
    
    if data:
        try:
            text = data.decode('ascii')
            sentence_buffer += text
            
            while '\n' in sentence_buffer:
                line, sentence_buffer = sentence_buffer.split('\n', 1)
                if line:
                    process_nmea_sentence(line)
            
        except Exception as e:
            print(f"Error processing data: {e}")
    
    current_time = time.monotonic()
    
    # Update display every 0.5 seconds if available
    if display and (current_time - last_display_update >= 0.5):
        update_display()
        last_display_update = current_time
    
    # Print summary every 5 seconds
    if current_time - last_summary_time >= 5.0:
        print_gps_summary()
        last_summary_time = current_time
    
    time.sleep(0.01)
