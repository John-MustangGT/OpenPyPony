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


update_display_sensor_info()
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
last_telemetry = 0
last_display_update = 0
last_pixel_update = 0
last_heartbeat = 0
last_gps_log = 0
last_rtc_sync = 0

heartbeat_state = False
gps_has_fix = False

# Display labels
if hw.display:
    from displayio import Group
    from adafruit_display_text import label
    import terminalio
    
    splash = Group()
    hw.display.root_group = splash
    
    title_label = label.Label(terminalio.FONT, text="OpenPonyLogger", color=0xFFFFFF, x=10, y=5)
    status_label = label.Label(terminalio.FONT, text="Logging...", color=0xFFFFFF, x=5, y=16)
    accel_label = label.Label(terminalio.FONT, text="A: ---", color=0xFFFFFF, x=5, y=28)
    gyro_label = label.Label(terminalio.FONT, text="G: ---", color=0xFFFFFF, x=5, y=38)
    mag_label = label.Label(terminalio.FONT, text="M: ---", color=0xFFFFFF, x=5, y=48)
    gps_label = label.Label(terminalio.FONT, text="GPS: No fix", color=0xFFFFFF, x=5, y=58)
    
    splash.append(title_label)
    splash.append(status_label)
    if accel:
        splash.append(accel_label)
    if gyro:
        splash.append(gyro_label)
    if mag:
        splash.append(mag_label)
    if gps_handler:
        splash.append(gps_label)

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
            ax, ay, az, accel_ts = accel.read()
            gx_val, gy_val, gz_val = accel.get_g_forces()
            logger.write_accelerometer(gx_val, gy_val, gz_val)
        
        if gyro:
            gx, gy, gz, gyro_ts = gyro.read()
            logger.write_gyroscope(gx, gy, gz)
        
        if mag:
            mx, my, mz, mag_ts = mag.read()
            logger.write_magnetometer(mx, my, mz)
        
        # Update GPS
        if gps_handler:
            gps_handler.update()
            if gps_handler.has_fix():
                gps_has_fix = True
                lat, lon, alt = gps_handler.get_position()
                speed = gps_handler.get_speed()
                heading = gps_handler.get_heading()
                hdop = gps_handler.get_hdop()
                logger.write_gps(lat, lon, alt, speed, heading, hdop)
            else:
                gps_has_fix = False
        
        # 1Hz: Telemetry
        if current_time - last_telemetry >= 1.0:
            last_telemetry = current_time
            
            # Print telemetry
            print(f"[{int(current_time)}s] ", end="")
            
            if accel:
                gx_val, gy_val, gz_val = accel.get_g_forces()
                print(f"Accel: {gx_val:+.2f}g {gy_val:+.2f}g {gz_val:+.2f}g | ", end="")
            
            if gyro:
                gx, gy, gz = gyro.get_last_reading()
                print(f"Gyro: {gx:+.1f}°/s {gy:+.1f}°/s {gz:+.1f}°/s | ", end="")
            
            if mag:
                heading = mag.get_heading()
                field = mag.get_field_strength()
                print(f"Mag: {heading:.0f}° {field:.1f}µT | ", end="")
            
            if gps_handler and gps_has_fix:
                lat, lon, alt = gps_handler.get_position()
                sats = gps_handler.get_satellites()
                print(f"GPS: {sats} sats")
            else:
                print("GPS: No fix")
            
            gc.collect()
        
        # 5Hz: Update display
        if hw.display and current_time - last_display_update >= 0.2:
            last_display_update = current_time
            
            if accel:
                gx_val, gy_val, gz_val = accel.get_g_forces()
                accel_label.text = f"A:{gx_val:+.2f}g"
            
            if gyro:
                ang_vel = gyro.get_angular_velocity()
                gyro_label.text = f"G:{ang_vel:.0f}°/s"
            
            if mag:
                heading = mag.get_heading()
                mag_label.text = f"M:{heading:.0f}°"
            
            if gps_handler:
                if gps_has_fix:
                    sats = gps_handler.get_satellites()
                    gps_label.text = f"GPS:{sats}sat"
                else:
                    gps_label.text = "GPS:NoFix"
        
        # 10Hz: Update NeoPixel (if available)
        if hw.pixel and current_time - last_pixel_update >= 0.1:
            last_pixel_update = current_time
            
            # Color based on sensors active
            if accel:
                gx_val, gy_val, gz_val = accel.get_g_forces()
                g_total = (gx_val**2 + gy_val**2 + gz_val**2)**0.5
                
                # Green = low G, yellow = medium, red = high
                if g_total < 0.5:
                    color = (0, 50, 0)  # Green
                elif g_total < 1.0:
                    color = (50, 50, 0)  # Yellow
                else:
                    color = (50, 0, 0)  # Red
                
                hw.pixel.fill(color)
        
        # 1Hz: Heartbeat LED
        if current_time - last_heartbeat >= 1.0:
            last_heartbeat = current_time
            
            if heartbeat_state:
                hw.heartbeat.value = False
                heartbeat_state = False
            else:
                hw.heartbeat.value = True
                heartbeat_state = True
                
                # LED on-time indicates GPS status
                if gps_has_fix:
                    time.sleep(0.8)  # Long blink = GPS fix
                else:
                    time.sleep(0.2)  # Short blink = no fix
        
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
        
        # 100Hz timing
        time.sleep(0.01)
        loop_count += 1

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
