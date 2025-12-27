"""
oled.py - OLED Display Manager for OpenPonyLogger
"""

import displayio
import terminalio
from adafruit_display_text import label
from utils import format_dms, hdop_to_bars, format_time_hms, estimate_recording_time
import os
import time

class OLED:
    def __init__(self, display):
        self.display = display
        self.splash_group = None
        self.splash_status = None
        self.main_group = None
        self.line1 = None
        self.line2 = None
        self.line3 = None
        self.line4 = None
        self.line5 = None
        self.smooth_x = 0.0
        self.smooth_y = 0.0

    def show_splash(self, status_text="Initializing..."):
        """Display OpenPony splash screen"""
        self.splash_group = displayio.Group()

        # Title (Large font)
        title = label.Label(terminalio.FONT, text="OpenPony", color=0xFFFFFF, x=5, y=8, scale=2)
        self.splash_group.append(title)
        title = label.Label(terminalio.FONT, text="Logger", color=0xFFFFFF, x=10, y=22, scale=1)
        self.splash_group.append(title)
        
        # Status (middle)
        self.splash_status = label.Label(terminalio.FONT, text=status_text, color=0xFFFFFF, x=5, y=35)
        self.splash_group.append(self.splash_status)
        
        # Copyright (bottom)
        copyright_label = label.Label(terminalio.FONT, text="(c) John Orthoefer 2025", color=0xFFFFFF, x=0, y=57)
        self.splash_group.append(copyright_label)
        
        self.display.root_group = self.splash_group

    def setup_main_display(self):
        """Setup the main display screen"""
        self.main_group = displayio.Group()

        self.line1 = label.Label(terminalio.FONT, text="--:--:-- NoFix [  ]", color=0xFFFFFF, x=0, y=5)
        self.line2 = label.Label(terminalio.FONT, text="--- --'-- N --- --'-- W", color=0xFFFFFF, x=0, y=17)
        self.line3 = label.Label(terminalio.FONT, text="0MPH  0.00g", color=0xFFFFFF, x=0, y=29)
        self.line4 = label.Label(terminalio.FONT, text="NoLog 00:00:00", color=0xFFFFFF, x=0, y=41)
        self.line5 = label.Label(terminalio.FONT, text="SD: --h --m remain", color=0xFFFFFF, x=0, y=53)

        for line in [self.line1, self.line2, self.line3, self.line4, self.line5]:
            self.main_group.append(line)
            
        if self.splash_status:
            self.splash_status.text = "Display ready..."
        time.sleep(0.3)
        self.display.root_group = self.main_group

    def update(self, data, session, rtc_handler):
        """Update OLED display with enhanced format"""

        # Line 1: {HH:MM:SS} {GPS Fix} {HDOP bars}
        now = time.localtime()
        time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
        if rtc_handler.synced:
            time_str += chr(0x0f)
        else:
            time_str += chr(0x07)
        
        fix_str = "NoFix"
        hdop = 25.0
        fix_str = data['gps']['fix']
        hdop = data['gps']['hdop']

        self.line1.text = f"{time_str} {fix_str:5s} {hdop:.1f}"
        
        # Line 2: Lat/Long
        self.line2.text = f"{data['gps']['lat']} {data['gps']['lon']}"
        
        # Line 3: {MPH} {Total G Force}
        self.line3.text = f"{data['gps']['speed']:3.0f}MPH  {self._smooth_g(data['accel']['ax'], data['accel']['ay']):+.2f}g"
        
        # Line 4: {Log file name} {File record time}
        if session.active:
            duration = format_time_hms(session.get_duration())
            no_ext = (session.filename.split("."))[0]
            short_name = no_ext.split("_")[1] if session.filename else "NoLog"
            self.line4.text = f"Run:{short_name} {duration}"
        else:
            self.line4.text = "NoLog 00:00:00"
        
        # Line 5: {Estimate of SD Card remaining time}
        if session.active:
            bytes_per_sec = session.get_bytes_per_second()
            # Get current free space
            sd_stat = os.statvfs("/sd")
            free_bytes = sd_stat[0] * sd_stat[3]
            remaining = estimate_recording_time(free_bytes, bytes_per_sec)
            self.line5.text = f"SD: {remaining} remain"
        else:
            # Show total free space in GB
            sd_stat = os.statvfs("/sd")
            free_gb = (sd_stat[0] * sd_stat[3]) / (1024**3)
            self.line5.text = f"SD: {free_gb:.1f}GB free"
        self.display.root_group = self.main_group

    def _smooth_g(self, new_x, new_y):
        self.smooth_x = ((self.smooth_x * 16) - self.smooth_x + new_x)/16
        self.smooth_y = ((self.smooth_y * 16) - self.smooth_y + new_y)/16
        gx = self.smooth_x/9.81
        gy = self.smooth_y/9.81
        return (gx**2 + gy**2)**0.5

    def set_splash_status(self, text):
        if self.splash_status:
            self.splash_status.text = text
