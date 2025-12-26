"""
OpenPonyLogger - Main Program
Displays active sensors and logs data
"""

import board
import time
import gc

# Import hardware and sensors
import hardware_setup as hw
from sensors import init_sensors, get_sensor, list_sensors
from unified_accelerometer import UnifiedAccelerometer
from gps import GPS
from session_logger import SessionLogger 
from neopixel_handler import NeoPixelHandler
from oled import OLED

# Import gyro/mag if available
try:
    from gyroscope import Gyroscope
    GYRO_AVAILABLE = True
except ImportError:
    GYRO_AVAILABLE = False

try:
    from magnetometer import Magnetometer
    MAG_AVAILABLE = True
except ImportError:
    MAG_AVAILABLE = False

try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

print("=" * 60)
print(f"OpenPonyLogger v{VERSION}")
print(f"Commit: {GIT_HASH}")
print(f"Built: {BUILD_DATE}")
print("=" * 60)

# =============================================================================
# Initialize Sensors
# =============================================================================

sensors = init_sensors(hw.i2c)

# Create sensor handlers
accel = None
gyro = None
mag = None
gps_handler = None
neopixel_handler = None

if sensors.get('accelerometer'):
    accel = UnifiedAccelerometer(sensors['accelerometer'])
    print("✓ Accelerometer handler ready")

if GYRO_AVAILABLE and get_sensor('gyroscope'):
    gyro = Gyroscope(get_sensor('gyroscope'))
    print("✓ Gyroscope handler ready")

if MAG_AVAILABLE and get_sensor('magnetometer'):
    mag = Magnetometer(get_sensor('magnetometer'))
    print("✓ Magnetometer handler ready")

if sensors.get('gps'):
    gps_handler = GPS(get_sensor('gps'))
    print("✓ GPS handler ready")

if hw.display:
    oled_handler = OLED(hw.display)
    oled_handler.setup_main_display()

if hw.neopixel:
    neopixel_handler = NeoPixelHandler(hw.pixel)

# =============================================================================
# Display Active Sensors on OLED
# =============================================================================

def update_display_sensor_info():
    """Update OLED with active sensor list"""
    if not hw.display:
        return
    
    from displayio import Group
    from adafruit_display_text import label
    import terminalio
    
    splash = Group()
    
    # Title
    title = label.Label(terminalio.FONT, text="OpenPonyLogger", color=0xFFFFFF, x=5, y=5)
    splash.append(title)
    
    # Sensor list
    y_pos = 18
    sensor_list = list_sensors()
    
    if 'accelerometer' in sensor_list:
        from hardware_config import hw_config
        accel_type = hw_config.get("sensors.accelerometer.type", "Accel")
        lbl = label.Label(terminalio.FONT, text=f"A: {accel_type}", color=0xFFFFFF, x=5, y=y_pos)
        splash.append(lbl)
        y_pos += 10
    
    if 'gyroscope' in sensor_list:
        lbl = label.Label(terminalio.FONT, text="G: Gyro", color=0xFFFFFF, x=5, y=y_pos)
        splash.append(lbl)
        y_pos += 10
    
    if 'magnetometer' in sensor_list:
        lbl = label.Label(terminalio.FONT, text="M: Mag", color=0xFFFFFF, x=5, y=y_pos)
        splash.append(lbl)
        y_pos += 10
    
    if 'gps' in sensor_list:
        lbl = label.Label(terminalio.FONT, text="GPS: Active", color=0xFFFFFF, x=5, y=y_pos)
        splash.append(lbl)
        y_pos += 10
    
    # Status
    status = label.Label(terminalio.FONT, text="Ready", color=0xFFFFFF, x=5, y=y_pos)
    splash.append(status)
    
    hw.display.root_group = splash


if oled_handler:
    oled_handler.show_splash()
    time.sleep(2)
    
#update_display_sensor_info()
if neopixel_handler:
    neopixel_handler.christmas_tree()
else:
    time.sleep(2)  # Show sensor list for 2 seconds

# =============================================================================
# Initialize Binary Logger
# =============================================================================

logger = SessionLogger("/sd")
session_id = logger.start_session(
    session_name="Track Day",
    driver_name="John",
    vehicle_id="Ciara"
)
print(f"\n✓ Session started: {session_id}")

# =============================================================================
# Main Loop Counters
# =============================================================================

loop_count = 0
loop_Hz = 0
last_telemetry = 0
last_display_update = 0
last_pixel_update = 0
last_heartbeat = 0
last_gps_log = 0
last_rtc_sync = 0

heartbeat_state = False
gps_has_fix = False

# empty last value
data = { 'gps': {}, 'gyro': {}, 'accel': {}, 'mag': {} }

# 
# TODO - this needs to come from the config
print("\n" + "="*60)
print("Starting main loop...")
print("  100Hz: Sensor reading + logging")
print("  5Hz:   Display updates")
print("  10Hz:  NeoPixel updates")
print("  1Hz:   Telemetry + heartbeat")
print("  5min:  GPS satellite logging")
print("Press Ctrl+C to stop")
print("="*60 + "\n")

# =============================================================================
# Main Loop
# =============================================================================

try:
    while True:
        current_time = time.monotonic()
        
        # 100Hz: Read sensors and log
        if accel:
            data['accel']['ax'], data['accel']['ay'], data['accel']['az'], data['accel']['ts'] = accel.read()
            data['accel']['gx'], data['accel']['gy'], data['accel']['gz'] = accel.get_g_forces()
            data['accel']['total'] = data['accel']['gx'] + data['accel']['gy']
            logger.write_accelerometer(data['accel']['gx'], data['accel']['gy'], data['accel']['gz'])
        
        if gyro:
            data['gyro']['gx'], data['gyro']['gy'], data['gyro']['gz'] = gyro.read()
            data['gyro']['ang_vel'] = gyro.get_angular_velocity()
            logger.write_gyroscope(data['gyro']['gx'], data['gyro']['gy'], data['gyro']['gz'])
        
        if mag:
            data['mag']['mx'], data['mag']['my'], data['mag']['mz'] = mag.read()
            data['mag']['heading'] = mag.get_heading()
            data['mag']['field'] = mag.get_field_strength()
            logger.write_magnetometer(data['mag']['mx'], data['mag']['my'], data['mag']['mz'])
        
        # Update GPS
        if gps_handler:
            gps_handler.update()
            if gps_handler.has_fix():
                gps_has_fix = True
                data['gps']['fix'] = gps_handler.fix_type()
                data['gps']['lat'], data['gps']['lon'], data['gps']['alt'] = gps_handler.get_position()
                data['gps']['speed'] = gps_handler.get_speed()
                data['gps']['heading'] = gps_handler.get_heading()
                data['gps']['hdop'] = gps_handler.get_hdop()
                data['gps']['sats'] = gps_handler.get_satellites()
                logger.write_gps(data['gps']['lat'], data['gps']['lon'], data['gps']['alt'], 
                    data['gps']['speed'], data['gps']['heading'], data['gps']['hdop'])
            else:
                gps_has_fix = False
                data['gps'] = {
                    'fix':      "NoFix",
                    'lat':      0.0,
                    'lon':      0.0,
                    'alt':      0.0,
                    'speed':    0.0,
                    'heading':  0.0,
                    'hdop':    25.9,
                    'stats':    0,
                }
            data['gps']['has_fix'] = gps_has_fix
        
        # 1Hz: Telemetry
        if current_time - last_telemetry >= 1.0:
            last_telemetry = current_time
            
            # Print telemetry
            print(f"[{int(current_time)}s] ", end="")
            
            if accel:
                print("Accel: {:+.2f}g {:+.2f}g {:+.2f}g | ".format(
                    data['accel']['gx'], data['accel']['gy'], data['accel']['gz']), end="")
            
            if gyro:
                print("Gyro: {:+.1f}°/s {:+.1f}°/s {:+.1f}°/s | ".format(
                    data['gyro']['gx'], data['gyro']['gy'], data['gyro']['gz']), end="")
            
            if mag:
                heading = mag.get_heading()
                field = mag.get_field_strength()
                print("Mag: {:.0f}° {:.1f}µT | ".format(
                    data['mag']['heading'],data['mag']['field']) , end="")
            
            if gps_handler and gps_has_fix:
                print("GPS: {} sats @{}".format(
                    data['gps']['sats'], data['gps']['hdop']))
            else:
                print("GPS: No fix")
            
            gc.collect()
        
        # 5Hz: Update display
        if hw.display and current_time - last_display_update >= 0.2:
            last_display_update = current_time
            oled_handler.update(data, logger)
            
        # 10Hz: Update NeoPixel (if available)
        if hw.neopixel and current_time - last_pixel_update >= 0.1:
            last_pixel_update = current_time
            neopixel_handler.update(data)
        
        # 1Hz: Heartbeat LED
        heartbeat_length = current_time - last_heartbeat
        if heartbeat_length >= 1.0:
            last_heartbeat = current_time
            hw.heartbeat.value = True
            print(f"{loop_Hz}Hz")
            loop_Hz = 0
        else:    
            if hw.heartbeat.value:
                if ((gps_has_fix and heartbeat_length >= 0.8) or 
                    (not gps_has_fix and heartbeat_length >= 0.2)):
                    hw.heartbeat.value = False
                    heartbeat_state = False
        
        # 5 min: Log GPS satellites
        if gps_handler and current_time - last_gps_log >= 300:
            last_gps_log = current_time
            sat_data = gps_handler.get_satellite_data()
            if sat_data:
                print(f"[GPS] {sat_data}")
        
        # 60s: Sync RTC from GPS
        if gps_handler and gps_has_fix and current_time - last_rtc_sync >= 60:
            last_rtc_sync = current_time
            if gps_handler.has_time():
                dt = gps_handler.get_datetime()
                if dt:
                    hw.set_system_time(dt)
                    print(f"[RTC] Synced from GPS: {hw.get_time_string()}")
        
        loop_count += 1
        loop_Hz += 1

except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Shutting down...")
    print("="*60)
    
    # Stop logging
    logger.stop_session()
    
    # Print peaks
    if accel:
        peaks = accel.get_peaks()
        print(f"\nAccel Peaks: X={peaks[0]:.2f}g Y={peaks[1]:.2f}g Z={peaks[2]:.2f}g")
    
    if gyro:
        peaks = gyro.get_peaks()
        print(f"Gyro Peaks: X={peaks[0]:.1f}°/s Y={peaks[1]:.1f}°/s Z={peaks[2]:.1f}°/s")
    
    if mag:
        peaks = mag.get_peaks()
        print(f"Mag Peaks: X={peaks[0]:.1f}µT Y={peaks[1]:.1f}µT Z={peaks[2]:.1f}µT")
    
    print(f"\nTotal loops: {loop_count}")
    print("\n✓ Shutdown complete")
