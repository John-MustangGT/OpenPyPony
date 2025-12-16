# RTC Sync Fix Example
# Add this to your main code.py or wherever you're handling GPS updates

"""
The issue: GPS shows correct UTC time (14:32:59) but OLED shows wrong local time (8:53)

Root cause: RTC sync is either:
1. Not happening at all
2. Happening with wrong timezone offset
3. Happening once with old GPS data then never updating

Solution: Use the new RTCHandler module with proper sync logic
"""

from rtc_handler import RTCHandler
import time

# Initialize RTC handler (adjust timezone for your location)
# EST = -5, EDT = -4 (but auto_dst=True handles this)
# PST = -8, PDT = -7
rtc_handler = RTCHandler(timezone_offset=-5, auto_dst=True)

# In your main loop, after GPS update:
def update_gps_and_sync_rtc(gps):
    """Update GPS and sync RTC if needed"""
    
    gps.update()
    
    # Only try to sync RTC when we have a good GPS fix
    if gps.has_fix and rtc_handler.needs_resync():
        if rtc_handler.sync_from_gps(gps):
            print(f"[Main] RTC synced successfully")
    
    # Return whether RTC is synced (for display purposes)
    return rtc_handler.synced


# In your OLED display update:
def update_display(data, rtc_synced):
    """Update OLED with proper time handling"""
    
    # Line 1: {HH:MM:SS} {GPS Fix} {HDOP bars}
    if rtc_synced:
        time_str = rtc_handler.get_time_string()  # Uses RTC
    else:
        time_str = "--:--:--"
    
    # ... rest of display update
    line1.text = f"{time_str} {fix_str} {bars}"


# Example main loop structure:
"""
rtc_handler = RTCHandler(timezone_offset=-5, auto_dst=True)
last_display_update = 0

while True:
    # Update GPS and RTC
    rtc_synced = update_gps_and_sync_rtc(gps)
    
    # Read other sensors
    data = read_sensors()
    
    # Update display periodically
    now = time.monotonic()
    if now - last_display_update > 0.2:  # 5Hz
        last_display_update = now
        update_display(data, rtc_synced)
    
    time.sleep(0.01)
"""

# DEBUGGING: Add this to see what's happening:
"""
# After GPS update, print both GPS time and RTC time
if gps.has_fix:
    utc = gps.timestamp_utc
    print(f"GPS UTC: {utc.tm_year}-{utc.tm_mon:02d}-{utc.tm_mday:02d} " +
          f"{utc.tm_hour:02d}:{utc.tm_min:02d}:{utc.tm_sec:02d}")
    
    if rtc_handler.synced:
        now = time.localtime()
        print(f"RTC Local: {now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d} " +
              f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}")
    else:
        print("RTC: Not synced yet")
"""

# COMMON ISSUES AND FIXES:

# Issue 1: RTC syncs once but never updates
# Fix: Call needs_resync() and sync_from_gps() in main loop

# Issue 2: Wrong timezone
# Fix: Check timezone_offset parameter (EST=-5, CST=-6, MST=-7, PST=-8)

# Issue 3: DST not applied
# Fix: Ensure auto_dst=True (default)

# Issue 4: GPS time is invalid (year < 2020)
# Fix: RTCHandler now validates before syncing

# Issue 5: Display shows old time after reboot
# Fix: Check rtc_synced flag before displaying time
