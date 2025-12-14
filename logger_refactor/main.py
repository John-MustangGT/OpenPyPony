"""
main.py - OpenPonyLogger Pico Firmware v2.1 (Refactored)
"""

import time
import hardware_setup as hw
from accelerometer import Accelerometer
from gps import GPS
from rtc_handler import RTCHandler
from storage import Session, FileManager
from oled import OLED
from serial_com import JSONProtocol
from neopixel_handler import NeoPixelHandler

def main():
    # Initialize components
    accel = Accelerometer(hw.lis3dh)
    gps = GPS(hw.gps)
    rtc = RTCHandler(hw.rtc_clock)
    session = Session(rtc)
    oled = OLED(hw.display)
    protocol = JSONProtocol(hw.esp_uart, session, gps)
    neopixel = NeoPixelHandler(hw.pixel)

    # Startup sequence
    neopixel.christmas_tree()
    oled.show_splash("Booting hardware...")
    time.sleep(1.5)
    oled.setup_main_display()
    
    oled.set_splash_status("Starting session...")
    time.sleep(0.5)

    # Auto-start logging
    session.start("John", "1ZVBP8AM5E5123456")

    print("\n" + "="*50)
    print("OpenPonyLogger v2.1 Running")
    print("="*50)

    last_display_update = 0
    last_telemetry_send = 0
    last_satellite_send = 0
    last_neopixel_update = 0
    heartbeat_last_toggle = 0

    try:
        while True:
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
            
            # Sync RTC
            rtc.sync_from_gps(gps.gps)

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
            
            # Update NeoPixels (10Hz)
            if now - last_neopixel_update > 0.1:
                last_neopixel_update = now
                neopixel.update(sensor_data, session)
            
            # Update display (5Hz)
            if now - last_display_update > 0.2:
                last_display_update = now
                oled.update(sensor_data, session, rtc)
            
            # Send telemetry (1Hz)
            if now - last_telemetry_send > 1.0:
                last_telemetry_send = now
                print(f"{sensor_data}\n")
                protocol.send_telemetry(sensor_data)
            
            # Send satellites (every 5s)
            if now - last_satellite_send > 5.0:
                last_satellite_send = now
                print(f"{gps.get_satellites_json()}\n")
                protocol.send_satellites()
            
            time.sleep(0.01)  # 100Hz main loop
            
    except KeyboardInterrupt:
        print("\nStopping...")
        if session.active:
            session.stop()

if __name__ == "__main__":
    main()
