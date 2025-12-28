"""
OpenPonyLogger - Main Entry Point (Refactored)

Clean, object-oriented architecture with proper HAL.
"""

import time
from config import Config
from hardware import HardwareAbstractionLayer
from session import SessionManager

# Version information
VERSION = "2.0.0-alpha"
BUILD_DATE = "2024-12-27"

print("\n" + "="*60)
print(f"OpenPonyLogger v{VERSION}")
print(f"Build: {BUILD_DATE}")
print("="*60)

# =============================================================================
# Step 1: Load Configuration
# =============================================================================
print("\n[Boot] Loading configuration...")
config = Config('settings.toml')
config.dump()

# =============================================================================
# Step 2: Initialize Hardware
# =============================================================================
print("\n[Boot] Initializing hardware...")
hal = HardwareAbstractionLayer(config)

# =============================================================================
# Step 3: Time Synchronization (RTC -> GPS)
# =============================================================================
print("\n[Boot] Synchronizing time...")

rtc = hal.get_rtc()
gps = hal.get_gps()

if rtc:
    current_time = rtc.get_time()
    print(f"[RTC] Current time: {current_time}")
else:
    print("[RTC] Not available")

# TODO: Wait for GPS fix and sync RTC
# For now, just check GPS status
if hal.has_gps():
    print("[GPS] Waiting for fix...")
    # In production, we'd wait here for GPS fix and update RTC
    # For now, just show status
    timeout = 10  # seconds
    start = time.monotonic()
    
    while time.monotonic() - start < timeout:
        if gps.update() and gps.has_fix():
            print(f"[GPS] Fix acquired! Satellites: {gps.get_satellites()}")
            gps_time = gps.get_time()
            print(f"[GPS] Time: {gps_time}")
            
            # Sync RTC with GPS time
            if rtc and gps_time:
                rtc.set_time(gps_time)
                print("[RTC] Synchronized with GPS")
            break
        time.sleep(0.1)
    else:
        print("[GPS] No fix within timeout (continuing anyway)")
else:
    print("[GPS] Not available")

# =============================================================================
# Step 4: Session Management
# =============================================================================
print("\n[Boot] Setting up session...")

storage = hal.get_storage()
if storage:
    session_mgr = SessionManager(storage, base_path='/sd')
    session_file = session_mgr.start_new_session()
    print(f"[Session] File: {session_mgr.get_session_path()}")
    
    # List recent sessions
    recent = session_mgr.list_sessions(limit=5)
    if recent:
        print(f"[Session] Recent sessions: {', '.join(recent[:3])}")
else:
    print("[Session] ERROR: No storage available!")
    print("[Session] Cannot proceed without SD card")
    # In production, we'd halt here or go to error state

# =============================================================================
# Step 5: Initialize Display (if present)
# =============================================================================
display = hal.get_display()
if hal.has_display():
    print("[Display] Initializing...")
    display.clear()
    display.text("OpenPonyLogger", 0, 0)
    display.text(f"v{VERSION}", 0, 10)
    display.text("Ready!", 0, 30)
    display.show()
else:
    print("[Display] Not available (optional)")

# =============================================================================
# Step 6: Main Loop (Placeholder)
# =============================================================================
print("\n" + "="*60)
print("System Ready - Entering main loop")
print("Press Ctrl+C to stop")
print("="*60 + "\n")

# Get sensor interfaces
accel = hal.get_accelerometer()

# Simple demo loop - just read sensors
loop_count = 0
last_display_update = 0

try:
    while True:
        current_time = time.monotonic()
        
        # Update GPS
        if gps.update():
            pos = gps.get_position()
            speed = gps.get_speed()
            
            # Read accelerometer
            gx, gy, gz = accel.get_gforce()
            
            # Print status every second
            if loop_count % 10 == 0:
                print(f"[{int(current_time)}s] GPS: {pos[0]:.6f}, {pos[1]:.6f} | "
                      f"Speed: {speed:.1f} m/s | G: {gx:+.2f}, {gy:+.2f}, {gz:+.2f}")
            
            # Update display (5Hz)
            if hal.has_display() and (current_time - last_display_update) >= 0.2:
                display.clear()
                display.text("OpenPonyLogger", 0, 0)
                display.text(f"Sats: {gps.get_satellites()}", 0, 12)
                display.text(f"Speed: {speed:.1f} m/s", 0, 24)
                display.text(f"G: {gx:+.1f} {gy:+.1f} {gz:+.1f}", 0, 36)
                display.show()
                last_display_update = current_time
            
            # TODO: Log data to session file
            # logger.log_frame(gps_data, accel_data, timestamp)
        
        loop_count += 1
        time.sleep(0.1)  # 10Hz main loop

except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Shutdown requested")
    print("="*60)
    
    # TODO: Cleanup
    # - Flush logger buffers
    # - Close session file
    # - Save any pending data
    
    if hal.has_display():
        display.clear()
        display.text("Shutdown", 0, 0)
        display.show()
    
    print("\n✓ Shutdown complete")
