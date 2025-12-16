"""
main.py - OpenPonyLogger Pico Firmware v2.1 (Refactored)
"""

import time
import hardware_setup as hw
from config import config
from accelerometer import Accelerometer
from gps import GPS
from rtc_handler import RTCHandler
from sdcard import Session, FileManager
from oled import OLED
from serial_com import JSONProtocol
from neopixel_handler import NeoPixelHandler
from microcontroller import watchdog
from watchdog import WatchDogMode

def main():
    # Initialize components
    accel = Accelerometer(hw.lis3dh)
    gps = GPS(hw.gps)
    rtc = RTCHandler(hw.rtc_clock)
    session = Session(rtc)
    oled = OLED(hw.display)
    protocol = JSONProtocol(hw.esp_uart, session, gps)
    neopixel = NeoPixelHandler(hw.pixel)

    # Setup watchdog
    watchdog.timeout = 8
    watchdog.mode = WatchDogMode.RESET
    watchdog.feed()

    # Startup sequence
    neopixel.christmas_tree()
    oled.show_splash("Booting hardware...")
    time.sleep(config.get_float("SPLASH_DURATION", 1.5))
    oled.setup_main_display()
    
    oled.set_splash_status("Starting session...")
    time.sleep(0.5)

    # Auto-start logging
    driver_name = config.get("DRIVER_NAME", "John")
    vehicle_id = config.get("VEHICLE_ID", "1ZVBP8AM5E5123456")
    session.start(driver_name, vehicle_id)

    print("\n" + "="*50)
    print("OpenPonyLogger v2.1 Running")
    print("="*50)

    last_rtc_update = 0
    last_display_update = 0
    last_telemetry_send = 0
    last_satellite_send = 0
    last_neopixel_update = 0
    heartbeat_last_toggle = 0
    last_status_print = 0

    serial_debug = config.get_bool("SERIAL_DEBUG", True)
    status_interval_ms = config.get_int("STATUS_INTERVAL", 5000)

    try:
        while True:
            watchdog.feed()
            # Process serial commands
            protocol.process()
            
            # Update and read sensors
            gps.update()
            
            sensor_data = {
                "t": rtc.get_time(),
                "rtc_synced": rtc.synced,
                "g": accel.read(),
                "gps": gps.read()
            }
            
            # Log to SD card
            if session.active:
                session.log(sensor_data)

            # Update heartbeat LED (1Hz, 100ms on)
            now = time.monotonic()
            if now - heartbeat_last_toggle >= 1.0:
                hw.heartbeat.value = True
                heartbeat_last_toggle = now
            elif now - heartbeat_last_toggle >= 0.1:
                hw.heartbeat.value = False

            # only sync RTC every minute
            if now - last_rtc_update >= 60.0 and hw.gps.has_fix:
                last_rtc_update = now
                rtc.sync_from_gps(gps.gps)
            
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
                if not hw.gps.timestamp_utc:
                    print("No GPS Time")
                else:
                    def _format_datetime(datetime):
                        date_part = f"{datetime.tm_mon:02}/{datetime.tm_mday:02}/{datetime.tm_year}"
                        time_part = f"{datetime.tm_hour:02}:{datetime.tm_min:02}:{datetime.tm_sec:02}"
                        return f"{date_part} {time_part}"
                    print(f"Fix timestamp: {_format_datetime(hw.gps.timestamp_utc)}")
                print(f"{sensor_data}")
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
