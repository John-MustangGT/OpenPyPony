"""
OpenPonyLogger - Main Entry Point (Refactored)

Clean, object-oriented architecture with proper HAL.
"""

import time
from config import Config
from hardware import HardwareAbstractionLayer
from session import SessionManager
from logger import create_logger
from webpages import get_page

# Version information
VERSION = "2.0.0-alpha"
BUILD_DATE = "2024-12-27"
GIT_SHA = "eb647bc"  # Update this when committing major changes

# Session state
session_running = True  # Whether logging is active
session_driver = None
session_vehicle = None
session_track = None

print("\n" + "="*60)
print(f"OpenPonyLogger v{VERSION}")
print(f"Build: {BUILD_DATE}")
print(f"Git SHA: {GIT_SHA}")
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

# Show splash screen if display available
display = hal.get_display()
if hal.has_display():
    display.show_splash("Initializing...")

# =============================================================================
# Step 3: Time Synchronization (RTC -> GPS)
# =============================================================================
print("\n[Boot] Synchronizing time...")

# Update splash status
if hal.has_display():
    display.update_splash_status("Syncing time...")

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

# Update splash status
if hal.has_display():
    display.update_splash_status("Starting session...")

storage = hal.get_storage()
logger = None

if storage:
    session_mgr = SessionManager(storage, base_path='/sd')
    session_file = session_mgr.start_new_session()
    session_path = session_mgr.get_session_path()
    print(f"[Session] File: {session_path}")

    # List recent sessions
    recent = session_mgr.list_sessions(limit=5)
    if recent:
        print(f"[Session] Recent sessions: {', '.join(recent[:3])}")

    # Create and open logger
    logger = create_logger(session_path, config, hal.manifest)
    logger.open()
else:
    print("[Session] ERROR: No storage available!")
    print("[Session] Cannot proceed without SD card")
    # In production, we'd halt here or go to error state

# =============================================================================
# Step 5: Setup Main Display
# =============================================================================
if hal.has_display():
    print("[Display] Setting up main display...")
    import time
    time.sleep(1)  # Show splash for 1 second
    display.setup_main_display()
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
webserver = hal.get_webserver()

# Main loop
loop_count = 0
last_display_update = 0
last_telemetry_send = 0
session_start_time = time.monotonic()

# Exponential Moving Average state for display smoothing
# EMA formula: smoothed = alpha * new_value + (1 - alpha) * previous_smoothed
EMA_ALPHA = 0.2  # Higher = more responsive, Lower = more smoothed
ema_gx = 0.0
ema_gy = 0.0
ema_gz = 1.0

try:
    while True:
        current_time = time.monotonic()

        # Handle web server requests (page requests from ESP-01)
        if webserver:
            req_type, req_data = webserver.update()
            if req_type == 'page_request':
                page_content = get_page(req_data)
                if page_content:
                    webserver.serve_file(req_data, page_content)
                    print(f"[Web] Served: {req_data}")
                else:
                    webserver.serve_file(req_data, get_page('/404.html'))
                    print(f"[Web] 404: {req_data}")
            elif req_type == 'config_request':
                # Re-send config if ESP restarted
                config_dict = {
                    'mode': hal.config.get('webserver.mode', 'ap'),
                    'ssid': hal.config.get('webserver.ssid', 'OpenPonyLogger'),
                    'password': hal.config.get('webserver.password', 'mustanggt'),
                    'address': hal.config.get('webserver.address', '192.168.4.1'),
                    'netmask': hal.config.get('webserver.netmask', '255.255.255.0'),
                    'gateway': hal.config.get('webserver.gateway', '192.168.4.1'),
                    'pico_version': f"{VERSION}",
                    'pico_git': GIT_SHA
                }
                webserver.send_config(config_dict)
                print("[Web] Re-sent config to ESP")
            elif req_type == 'file_list_request':
                # Send list of recent session files
                print("[Web] File list requested")
                try:
                    if storage and 'session_mgr' in globals():
                        print("[Web] Querying session manager...")
                        sessions = session_mgr.list_sessions(limit=10)
                        print(f"[Web] Found {len(sessions)} sessions")
                        file_list = []
                        for session_file in sessions:
                            info = session_mgr.get_session_info(session_file)
                            if info:
                                file_list.append(info)
                        webserver.send_file_list(file_list)
                        print(f"[Web] Sent file list ({len(file_list)} files)")
                    else:
                        # No storage available - send empty list
                        print("[Web] No storage - sending empty list")
                        webserver.send_file_list([])
                except Exception as e:
                    print(f"[Web] ERROR getting file list: {e}")
                    import traceback
                    traceback.print_exception(e)
                    webserver.send_file_list([])
            elif req_type == 'file_download_request':
                # Stream file for download
                print(f"[Web] File download requested: {req_data}")
                try:
                    if storage and 'session_mgr' in globals():
                        filename = req_data
                        filepath = f"{session_mgr.base_path}/{filename}"
                        webserver.stream_file(filepath)
                        print(f"[Web] Streaming file: {filename}")
                    else:
                        print("[Web] ERROR: No storage - cannot download file")
                except Exception as e:
                    print(f"[Web] ERROR streaming file: {e}")
                    import traceback
                    traceback.print_exception(e)
            elif req_type == 'session_stop':
                # Stop logging
                print("[Web] Session stop requested")
                session_running = False
                webserver.send_session_status(session_running, session_mgr.current_session if storage else 0)
            elif req_type == 'session_start':
                # Start logging
                print("[Web] Session start requested")
                session_running = True
                webserver.send_session_status(session_running, session_mgr.current_session if storage else 0)
            elif req_type == 'session_restart':
                # Restart session (close current, start new)
                print("[Web] Session restart requested")
                if logger:
                    logger.close()
                if storage and 'session_mgr' in globals():
                    session_file = session_mgr.start_new_session()
                    session_path = session_mgr.get_session_path()
                    print(f"[Session] Restarted: {session_path}")
                    logger = create_logger(session_path, config, hal.manifest)
                    logger.open()
                    session_start_time = time.monotonic()
                session_running = True
                webserver.send_session_status(session_running, session_mgr.current_session if storage else 0)
            elif req_type == 'session_update':
                # Update session info and restart
                print(f"[Web] Session update requested: {req_data}")
                # Parse session info from req_data
                try:
                    params = {}
                    for param in req_data.split(','):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            params[key.strip()] = value.strip()

                    # Update config with new session info
                    if 'driver' in params:
                        config.config['general.Driver_name'] = params['driver']
                        session_driver = params['driver']
                        print(f"[Session] Updated driver: {params['driver']}")
                    if 'vehicle' in params:
                        config.config['general.Vehicle_id'] = params['vehicle']
                        session_vehicle = params['vehicle']
                        print(f"[Session] Updated vehicle: {params['vehicle']}")
                    if 'track' in params:
                        session_track = params.get('track', '')
                        print(f"[Session] Updated track: {params['track']}")

                    # Restart session with new info
                    if logger:
                        logger.close()
                    if storage and 'session_mgr' in globals():
                        session_file = session_mgr.start_new_session()
                        session_path = session_mgr.get_session_path()
                        print(f"[Session] Restarted with new info: {session_path}")
                        logger = create_logger(session_path, config, hal.manifest)
                        logger.open()
                        session_start_time = time.monotonic()
                    session_running = True
                    webserver.send_session_status(session_running, session_mgr.current_session if storage else 0)
                except Exception as e:
                    print(f"[Web] ERROR updating session: {e}")
                    import traceback
                    traceback.print_exception(e)
            elif req_type == 'session_info_request':
                # Send current session info
                print("[Web] Session info requested")
                info = {
                    'session_num': session_mgr.current_session if storage else 0,
                    'running': session_running,
                    'driver': config.get('general.Driver_name', 'Unknown'),
                    'vehicle': config.get('general.Vehicle_id', 'Unknown'),
                    'track': session_track or ''
                }
                webserver.send_session_info(info)

        # Update GPS (with error handling for malformed NMEA sentences)
        try:
            gps.update()
        except (IndexError, ValueError) as e:
            # GPS library can crash on malformed NMEA data - just skip this update
            pass

        # Read accelerometer (RAW values for logging)
        gx, gy, gz = accel.get_gforce()

        # Prepare data for logging (handle None values from GPS)
        position = gps.get_position() if gps.has_fix() else (0.0, 0.0, 0.0)
        speed = gps.get_speed() if gps.has_fix() else 0.0

        gps_data = {
            'lat': position[0] or 0.0,
            'lon': position[1] or 0.0,
            'alt': position[2] or 0.0,
            'speed': speed or 0.0,
            'satellites': gps.get_satellites() or 0,
            'fix_type': gps.get_fix_type(),
            'hdop': gps.get_hdop() or 99.9
        }

        accel_data = {
            'gx': gx or 0.0,
            'gy': gy or 0.0,
            'gz': gz or 1.0  # Default to 1g for z-axis if None
        }

        # Apply EMA smoothing for display ONLY (log raw values!)
        ema_gx = EMA_ALPHA * accel_data['gx'] + (1.0 - EMA_ALPHA) * ema_gx
        ema_gy = EMA_ALPHA * accel_data['gy'] + (1.0 - EMA_ALPHA) * ema_gy
        ema_gz = EMA_ALPHA * accel_data['gz'] + (1.0 - EMA_ALPHA) * ema_gz

        accel_data_smoothed = {
            'gx': ema_gx,
            'gy': ema_gy,
            'gz': ema_gz
        }

        # Log data frame (only if session is running)
        if logger and session_running:
            logger.log_frame(gps_data, accel_data, time.time())

        # Print status every second
        if loop_count % 10 == 0:
            if gps.has_fix():
                print(f"[{int(current_time)}s] GPS: {gps_data['lat']:.6f}, {gps_data['lon']:.6f} | "
                      f"Speed: {gps_data['speed']:.1f} m/s | G: {accel_data['gx']:+.2f}, {accel_data['gy']:+.2f}, {accel_data['gz']:+.2f}")
            else:
                print(f"[{int(current_time)}s] GPS: No fix ({gps_data['satellites']} sats) | "
                      f"G: {accel_data['gx']:+.2f}, {accel_data['gy']:+.2f}, {accel_data['gz']:+.2f}")

        # Update display (5Hz) - using persistent labels, no flickering!
        if hal.has_display() and (current_time - last_display_update) >= 0.2:
            # Prepare session info
            session_info = None
            if logger:
                duration = current_time - session_start_time
                session_info = {
                    'name': 'Log',
                    'duration': duration
                }

            # Update display labels with SMOOTHED G-forces (no clear/redraw!)
            display.update_main_display(gps_data, accel_data_smoothed, session_info)
            last_display_update = current_time

        # Stream telemetry to web server (10Hz) - send SMOOTHED G-forces for display
        if webserver and (current_time - last_telemetry_send) >= 0.1:
            # Get GPS timestamp (UTC) and convert to Unix timestamp
            gps_time = gps.get_time()
            if gps_time:
                # Convert struct_time to Unix timestamp (seconds since epoch)
                # struct_time: (year, month, day, hour, minute, second, weekday, yearday, isdst)
                import time as time_module
                try:
                    timestamp = time_module.mktime(gps_time)
                except:
                    timestamp = 0
            else:
                timestamp = 0

            telemetry = {
                'timestamp': int(timestamp),  # Unix timestamp (UTC)
                'lat': gps_data['lat'],
                'lon': gps_data['lon'],
                'alt': gps_data['alt'],
                'speed': gps_data['speed'] * 2.237,  # Convert m/s to MPH for display
                'satellites': gps_data['satellites'],
                'fix_type': gps_data['fix_type'],
                'hdop': gps_data['hdop'],
                'gx': accel_data_smoothed['gx'],
                'gy': accel_data_smoothed['gy'],
                'gz': accel_data_smoothed['gz']
            }
            webserver.stream_telemetry(telemetry)
            last_telemetry_send = current_time

        loop_count += 1
        time.sleep(0.1)  # 10Hz main loop

except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Shutdown requested")
    print("="*60)

    # Cleanup: close logger and flush all data
    if logger:
        print("[Shutdown] Closing logger...")
        logger.close()

    # Display shutdown message
    if hal.has_display():
        display.show_splash("Shutdown")
        time.sleep(0.5)
        display.update_splash_status("Data saved")
        time.sleep(1)

    print("\n✓ Shutdown complete")
    print(f"✓ Logged {loop_count} samples")
