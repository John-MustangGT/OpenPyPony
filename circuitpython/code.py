"""
main.py - OpenPonyLogger Pico Firmware v2.1 (Refactored)
"""

import time
import json
import hardware_setup as hw
from sensors import init_sensors
from config import config
from accelerometer import Accelerometer
from gps import GPS
from rtc_handler import RTCHandler
from session_logger import SessionLogger
from oled import OLED
from serial_com import JSONProtocol
from neopixel_handler import NeoPixelHandler
from microcontroller import watchdog
from watchdog import WatchDogMode
from debug import OpenPonyDebug

def main():
    # Initialize sensors (separate from system hardware)
    print("\n" + "="*60)
    print("Initializing Data Acquisition...")
    print("="*60)
    
    sensors = init_sensors(hw.i2c)
    
    # Wrap sensors in handler classes
    accel = Accelerometer(sensors.get('lis3dh'))
    gps = GPS(sensors.get('gps'))
    
    # Initialize system components
    rtc = RTCHandler(
        config.get_int("TIMEZONE_OFFSET", -5), 
        config.get_bool("TIMEZONE_AUTO_DST", True)
    )
    session = SessionLogger("/sd")
    oled = OLED(hw.display)
    protocol = JSONProtocol(hw.esp_uart, session, gps)
    neopixel = NeoPixelHandler(hw.pixel)

    # Startup sequence
    neopixel.christmas_tree()
    oled.show_splash("Booting hardware...")
    time.sleep(config.get_float("SPLASH_DURATION", 1.5))
    oled.setup_main_display()
    
    oled.set_splash_status("Starting session...")
    time.sleep(0.5)

    # Auto-start logging
    session_name = config.get("SESSION_NAME", "Track Day!")
    driver_name = config.get("DRIVER_NAME", "John")
    vehicle_id = config.get("VEHICLE_ID", "1ZVBP8AM5E5123456")
    session.start_session(
        session_name=session_name,
        driver_name=driver_name, 
        vehicle_id=vehicle_id
    )

    print("\n" + "="*50)
    print("OpenPonyLogger v2.1 Running")
    print("="*50)

    last_rtc_update = 0
    last_display_update = 0
    last_telemetry_send = 0
    last_satellite_send = 0
    last_satellite_log = 0
    last_neopixel_update = 0
    heartbeat_last_toggle = 0
    last_status_print = 0

    serial_debug = config.get_bool("SERIAL_DEBUG", True)
    status_interval_ms = config.get_int("STATUS_INTERVAL", 5000)

    DEBUG = OpenPonyDebug()

    try:
        while True:
            watchdog.feed()
            # Process serial commands
            protocol.process()
            
            # Update and read sensors
            gps.update()
            
            sensor_data = {
                "t": rtc.get_log_timestamp(),
                "rtc_synced": rtc.synced,
                "g": accel.read(),
                "gps": gps.read()
            }
 
            # get the current system time
            now = time.monotonic()
            
            # Log to SD card
            if session.active:
                session.write_accelerometer(
                    sensor_data["g"]["x"], 
                    sensor_data["g"]["y"], 
                    sensor_data["g"]["z"], 
                    sensor_data["t"]
                )
                session.write_gps(
                    sensor_data["gps"]["lat"], 
                    sensor_data["gps"]["lon"], 
                    sensor_data["gps"]["alt"], 
                    sensor_data["gps"]["speed"], 
                    sensor_data["gps"]["heading"], 
                    sensor_data["gps"]["hdop"], 
                    sensor_data["t"]
                )
                # Log satellite data every 5 minutes (300 seconds)
                gps_obj = sensors.get('gps')
                if gps_obj and gps_obj.has_fix and now - last_satellite_log >= 300.0:
                    last_satellite_log = now
                    sat_data = gps.get_satellites_json()
                    if sat_data and sat_data.get('satellites'):
                        session.write_gps_satellites(
                            sat_data['satellites'],
                            sensor_data["t"]
                        )
                        if serial_debug:
                            print(f"[Log] Satellites logged: {sat_data['count']} sats")

            # Update heartbeat LED (1Hz; on for normal=800ms, error=200ms)
            if now - heartbeat_last_toggle >= 1.0:
                hw.heartbeat.value = True
                heartbeat_last_toggle = now
            elif gps_obj and gps_obj.has_fix and now - heartbeat_last_toggle >= 0.9:
                hw.heartbeat.value = False
            elif (not gps_obj or not gps_obj.has_fix) and now - heartbeat_last_toggle >= 0.1:
                hw.heartbeat.value = False

            # only sync RTC every minute
            if gps_obj and gps_obj.has_fix and now - last_rtc_update >= 60.0:
                last_rtc_update = now
                rtc.sync_from_gps(gps_obj)
            
            # Update NeoPixels (10Hz)
            if now - last_neopixel_update > 0.1:
                last_neopixel_update = now
                neopixel.update(sensor_data, session)
            
            # Update display (5Hz)
            if now - last_display_update > 0.2:
                last_display_update = now
                oled.update(sensor_data, session, rtc)
            
            # Send telemetry (1Hz)
            if serial_debug and now - last_telemetry_send > 1.0:
                last_telemetry_send = now
                if gps_obj and gps_obj.timestamp_utc:
                    def _format_datetime(datetime):
                        date_part = f"{datetime.tm_mon:02}/{datetime.tm_mday:02}/{datetime.tm_year}"
                        time_part = f"{datetime.tm_hour:02}:{datetime.tm_min:02}:{datetime.tm_sec:02}"
                        return f"{date_part} {time_part}"
                    print(f"Fix timestamp: {_format_datetime(gps_obj.timestamp_utc)}")
                else:
                    print(f"No GPS Time")
                DEBUG.debug_message(f"{json.dumps(sensor_data)}")
                protocol.send_telemetry(sensor_data)
            
            # Send satellites (every 5s)
            if serial_debug and now - last_satellite_send > 5.0:
                last_satellite_send = now
                print(f"{gps.get_satellites_json()}")
                protocol.send_satellites()

            if serial_debug and (now * 1000) - last_status_print > status_interval_ms:
                last_status_print = now * 1000
                print(f"Status: {sensor_data}")
            
            time.sleep(0.01)  # 100Hz main loop
            
    except KeyboardInterrupt:
        print("\nStopping...")
        if session.active:
            session.stop()

if __name__ == "__main__":
    main()
