"""
pcf8523_rtc.py - PCF8523 Real-Time Clock support for OpenPonyLogger

Provides time synchronization between PCF8523 RTC and system RTC.
"""

import time
import rtc
import board
import busio


class PCF8523Handler:
    """Handler for PCF8523 Real-Time Clock"""
    
    def __init__(self, i2c, address=0x68, sync_from=True, sync_to=True):
        """
        Initialize PCF8523 RTC
        
        Args:
            i2c: I2C bus object
            address: I2C address (default 0x68)
            sync_from: If True, sync system time FROM RTC on init
            sync_to: If True, sync system time TO RTC when set_time() called
        """
        self.i2c = i2c
        self.address = address
        self.sync_from_rtc = sync_from
        self.sync_to_rtc = sync_to
        self.rtc_device = None
        
        # Import PCF8523 library
        try:
            from adafruit_pcf8523.pcf8523 import PCF8523
            self.rtc_device = PCF8523(i2c)
            print(f"✓ PCF8523 RTC initialized at 0x{address:02X}")
            
            # Sync from RTC to system on boot
            if self.sync_from_rtc:
                self.sync_from_rtc_to_system()
                
        except ImportError:
            print("✗ adafruit_pcf8523 library not installed")
            print("  Install with: circup install adafruit_pcf8523")
            raise
        except Exception as e:
            print(f"✗ PCF8523 initialization failed: {e}")
            raise
    
    def sync_from_rtc_to_system(self):
        """
        Read time from PCF8523 and set system RTC
        
        Returns:
            bool: True if successful
        """
        try:
            # Read time from PCF8523
            rtc_time = self.rtc_device.datetime
            
            # Convert to time.struct_time
            # PCF8523 datetime is: (year, month, day, hour, minute, second, weekday, yearday, isdst)
            # System time.struct_time needs same format
            
            # Set system RTC
            rtc.RTC().datetime = rtc_time
            
            # Format for display
            time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                rtc_time.tm_year, rtc_time.tm_mon, rtc_time.tm_mday,
                rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec
            )
            
            print(f"[RTC] Synced from PCF8523: {time_str}")
            return True
            
        except Exception as e:
            print(f"[RTC] Failed to sync from PCF8523: {e}")
            return False
    
    def sync_from_system_to_rtc(self):
        """
        Write current system time to PCF8523
        
        Returns:
            bool: True if successful
        """
        try:
            # Read system time
            system_time = time.localtime()
            
            # Write to PCF8523
            self.rtc_device.datetime = system_time
            
            # Format for display
            time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                system_time.tm_year, system_time.tm_mon, system_time.tm_mday,
                system_time.tm_hour, system_time.tm_min, system_time.tm_sec
            )
            
            print(f"[RTC] Synced to PCF8523: {time_str}")
            return True
            
        except Exception as e:
            print(f"[RTC] Failed to sync to PCF8523: {e}")
            return False
    
    def set_time(self, year, month, day, hour, minute, second):
        """
        Set time on both system and PCF8523 (if sync_to_rtc enabled)
        
        Args:
            year, month, day, hour, minute, second: Time components
        """
        # Create time struct
        new_time = time.struct_time((
            year, month, day,
            hour, minute, second,
            0,  # weekday (will be calculated)
            -1,  # yearday (will be calculated)
            -1   # isdst
        ))
        
        # Set system RTC
        rtc.RTC().datetime = new_time
        print(f"[RTC] System time set: {year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
        
        # Optionally sync to PCF8523
        if self.sync_to_rtc and self.rtc_device:
            self.sync_from_system_to_rtc()
    
    def get_time(self):
        """
        Get current time from PCF8523
        
        Returns:
            time.struct_time or None
        """
        try:
            return self.rtc_device.datetime
        except Exception as e:
            print(f"[RTC] Failed to read time: {e}")
            return None
    
    def get_time_string(self):
        """
        Get current time as formatted string
        
        Returns:
            str: Time in YYYY-MM-DD HH:MM:SS format
        """
        current_time = self.get_time()
        if current_time:
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                current_time.tm_year, current_time.tm_mon, current_time.tm_mday,
                current_time.tm_hour, current_time.tm_min, current_time.tm_sec
            )
        return "Unknown"
    
    def check_battery(self):
        """
        Check if RTC battery is low
        
        Returns:
            bool: True if battery is good, False if low
        """
        try:
            # PCF8523 has battery_low property
            if hasattr(self.rtc_device, 'battery_low'):
                if self.rtc_device.battery_low:
                    print("[RTC] WARNING: Battery low!")
                    return False
            return True
        except Exception as e:
            print(f"[RTC] Failed to check battery: {e}")
            return True  # Assume OK if we can't check


def setup_rtc(config, i2c=None):
    """
    Setup RTC based on configuration
    
    Args:
        config: HardwareConfig object
        i2c: I2C bus (required for PCF8523)
    
    Returns:
        PCF8523Handler or None
    """
    if not config.is_enabled("rtc"):
        print("[RTC] Disabled in config")
        return None
    
    rtc_type = config.get("rtc.type", "builtin")
    
    if rtc_type == "builtin":
        print("[RTC] Using Pico's built-in RTC")
        # Built-in RTC is always available, no setup needed
        return None
    
    elif rtc_type == "pcf8523":
        if not i2c:
            print("[RTC] ERROR: PCF8523 requires I2C bus")
            return None
        
        # Parse I2C address
        addr_str = config.get("rtc.i2c_address", "0x68")
        if isinstance(addr_str, str):
            address = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)
        else:
            address = addr_str
        
        # Get sync options
        sync_from = config.get_bool("rtc.sync_from_rtc", True)
        sync_to = config.get_bool("rtc.sync_to_rtc", True)
        
        try:
            rtc_handler = PCF8523Handler(
                i2c=i2c,
                address=address,
                sync_from=sync_from,
                sync_to=sync_to
            )
            
            # Check battery status
            rtc_handler.check_battery()
            
            return rtc_handler
            
        except Exception as e:
            print(f"[RTC] Failed to initialize PCF8523: {e}")
            return None
    
    else:
        print(f"[RTC] Unknown type: {rtc_type}")
        return None
