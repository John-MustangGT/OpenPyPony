"""
rtc_handler.py - RTC Handler for OpenPonyLogger
"""

import time

class RTCHandler:
    def __init__(self, rtc_clock):
        self.rtc_clock = rtc_clock
        self._rtc_synced = False

    @property
    def synced(self):
        return self._rtc_synced

    def sync_from_gps(self, gps):
        """Sync RTC from GPS data"""
        if gps.has_fix and not self._rtc_synced and gps.timestamp_utc:
            try:
                self.rtc_clock.datetime = time.struct_time((
                    gps.timestamp_utc.tm_year,
                    gps.timestamp_utc.tm_mon,
                    gps.timestamp_utc.tm_mday,
                    gps.timestamp_utc.tm_hour,
                    gps.timestamp_utc.tm_min,
                    gps.timestamp_utc.tm_sec,
                    0, -1, -1
                ))
                self._rtc_synced = True
                print("✓ RTC synced from GPS")
            except Exception as e:
                print(f"✗ RTC sync error: {e}")

    def get_time(self):
        """Get current time"""
        if self._rtc_synced:
            return time.time()
        else:
            return int(time.monotonic())
