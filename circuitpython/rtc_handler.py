"""
rtc_handler.py - RTC time synchronization from GPS

Handles syncing the Pico's RTC from GPS time with proper timezone conversion
"""

import time
import rtc

class RTCHandler:
    """Manage RTC synchronization from GPS"""
    
    def __init__(self, timezone_offset=-5, auto_dst=True):
        """
        Initialize RTC handler
        
        Args:
            timezone_offset: Hours offset from UTC (e.g., -5 for EST, -8 for PST)
            auto_dst: Automatically apply DST rules (US rules)
        """
        self.rtc = rtc.RTC()
        self.timezone_offset = timezone_offset
        self.auto_dst = auto_dst
        self.synced = False
        self.last_sync_time = 0
    
    def is_dst(self, year, month, day, hour):
        """
        Check if DST is active (US rules: 2nd Sunday March - 1st Sunday November)
        
        Args:
            year, month, day, hour: UTC time components
        
        Returns:
            True if DST should be applied
        """
        if not self.auto_dst:
            return False
        
        # DST doesn't apply in these months
        if month < 3 or month > 11:
            return False
        if month > 3 and month < 11:
            return True
        
        # Find second Sunday in March (DST starts 2am)
        # Find first Sunday in November (DST ends 2am)
        # Simple approximation: DST active if in April-October
        # For March/November, need day-of-week calculation
        
        # Simplified: if month is 3 (March) or 11 (November), assume mid-month
        if month == 3:
            return day > 14  # After mid-March
        if month == 11:
            return day < 7   # Before early November
        
        return True
    
    def sync_from_gps(self, gps):
        """
        Sync RTC from GPS object
        
        Args:
            gps: adafruit_gps.GPS object with fix
        
        Returns:
            True if sync successful
        """
        if not gps.has_fix:
            return False
        
        if not gps.timestamp_utc:
            return False
        
        try:
            # Get UTC time from GPS
            utc = gps.timestamp_utc
            year = utc.tm_year
            month = utc.tm_mon
            day = utc.tm_mday
            hour = utc.tm_hour
            minute = utc.tm_min
            second = utc.tm_sec
            
            # Validate year (GPS needs time to acquire)
            if year < 2020 or year > 2100:
                print(f"[RTC] Invalid GPS year: {year}")
                return False
            
            # Calculate timezone offset
            offset = self.timezone_offset
            if self.is_dst(year, month, day, hour):
                offset += 1
                print(f"[RTC] Applying DST (offset: {offset})")
            
            # Apply timezone offset
            local_hour = hour + offset
            local_day = day
            local_month = month
            local_year = year
            
            # Handle day rollover
            if local_hour >= 24:
                local_hour -= 24
                local_day += 1
                
                # Handle month rollover
                days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                if local_year % 4 == 0 and (local_year % 100 != 0 or local_year % 400 == 0):
                    days_in_month[1] = 29
                
                if local_day > days_in_month[local_month - 1]:
                    local_day = 1
                    local_month += 1
                    if local_month > 12:
                        local_month = 1
                        local_year += 1
            
            elif local_hour < 0:
                local_hour += 24
                local_day -= 1
                
                # Handle month underflow
                if local_day < 1:
                    local_month -= 1
                    if local_month < 1:
                        local_month = 12
                        local_year -= 1
                    
                    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                    if local_year % 4 == 0 and (local_year % 100 != 0 or local_year % 400 == 0):
                        days_in_month[1] = 29
                    
                    local_day = days_in_month[local_month - 1]
            
            # Set RTC
            self.rtc.datetime = time.struct_time((
                local_year,
                local_month,
                local_day,
                local_hour,
                minute,
                second,
                0,  # weekday (calculated by RTC)
                -1,  # yearday (calculated by RTC)
                -1   # DST flag
            ))
            
            self.synced = True
            self.last_sync_time = time.monotonic()
            
            print(f"[RTC] ✓ Synced: {local_year}-{local_month:02d}-{local_day:02d} " + 
                  f"{local_hour:02d}:{minute:02d}:{second:02d} " +
                  f"(UTC {hour:02d}:{minute:02d}, offset {offset})")
            
            return True
            
        except Exception as e:
            print(f"[RTC] Sync failed: {e}")
            import traceback
            traceback.print_exception(e)
            return False
    
    def get_time_string(self):
        """Get formatted time string HH:MM:SS"""
        if not self.synced:
            return "--:--:--"
        
        now = time.localtime()
        return f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
    
    def get_time(self):
        """Alias for get_time_string() for compatibility"""
        return self.get_time_string()
    
    def get_timestamp(self):
        """
        Get current timestamp as integer (microseconds since epoch)
        
        For binary logging - returns microseconds since Jan 1, 2000
        (CircuitPython epoch)
        
        Returns:
            int: Microseconds since epoch, or 0 if not synced
        """
        if not self.synced:
            return 0
        
        try:
            import time
            # Get current time as struct_time
            now = time.localtime()
            
            # Convert to seconds since CircuitPython epoch (2000-01-01)
            # This is a simplified calculation
            seconds = time.mktime(now)
            
            # Convert to microseconds
            return int(seconds * 1_000_000)
            
        except Exception as e:
            print(f"[RTC] Timestamp error: {e}")
            return 0
    
    def get_monotonic_us(self):
        """
        Get monotonic time in microseconds
        
        Useful for relative timestamps that don't depend on RTC sync.
        Always works, even if RTC not synced.
        
        Returns:
            int: Microseconds since boot
        """
        return int(time.monotonic() * 1_000_000)
    
    def get_log_timestamp(self):
        """
        Get best available timestamp for logging
        
        Returns absolute timestamp (microseconds since epoch) if RTC synced,
        otherwise returns monotonic time (microseconds since boot).
        
        This is the recommended method for data logging as it always
        returns a valid timestamp regardless of RTC sync status.
        
        Returns:
            int: Microseconds (either absolute or relative)
        """
        if self.synced:
            return self.get_timestamp()
        else:
            return self.get_monotonic_us()
    
    def get_date_string(self):
        """Get formatted date string YYYY-MM-DD"""
        if not self.synced:
            return "----------"
        
        now = time.localtime()
        return f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d}"
    
    def get_date(self):
        """Alias for get_date_string() for compatibility"""
        return self.get_date_string()
    
    def needs_resync(self, interval_seconds=3600):
        """
        Check if RTC needs re-syncing
        
        Args:
            interval_seconds: Minimum seconds between syncs (default 1 hour)
        
        Returns:
            True if sync should be attempted
        """
        if not self.synced:
            return True
        
        return (time.monotonic() - self.last_sync_time) > interval_seconds
