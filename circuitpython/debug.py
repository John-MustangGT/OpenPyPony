"""
debug.py - Debug functions

make debug a little more clean
"""

import time
import rtc

class OpenPonyDebug:
    def __init__(self):
        self.rtc = rtc.RTC()

    def debug_message(self, s):
        dt = self.rtc.datetime
        now = f"{dt.tm_hour:02d}:{dt.tm_min:02d}:{dt.tm_sec:02d}"
        print(f"{now} - {s}")
