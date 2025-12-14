"""
utils.py - Utility functions for OpenPonyLogger
"""

def format_dms(decimal_degrees, is_latitude=True):
    """Convert decimal degrees to DMS format"""
    if decimal_degrees is None or decimal_degrees == 0:
        return "--- --'--" + (" N" if is_latitude else " W")
    
    # Determine hemisphere
    if is_latitude:
        hemisphere = "N" if decimal_degrees >= 0 else "S"
    else:
        hemisphere = "E" if decimal_degrees >= 0 else "W"
    
    # Convert to positive
    decimal_degrees = abs(decimal_degrees)
    
    # Extract degrees, minutes, seconds
    degrees = int(decimal_degrees)
    minutes_decimal = (decimal_degrees - degrees) * 60
    minutes = int(minutes_decimal)
    seconds = int((minutes_decimal - minutes) * 60)
    
    return f"{degrees:3d} {minutes:2d}'{seconds:2d}\"{hemisphere}"

def hdop_to_bars(hdop):
    """Convert HDOP to signal strength bars (0-3)"""
    if hdop is None or hdop == 0:
        return 0
    elif hdop < 1.5:
        return 3  # Excellent
    elif hdop < 3.0:
        return 2  # Good
    elif hdop < 5.0:
        return 1  # Fair
    else:
        return 0  # Poor

def format_time_hms(seconds):
    """Format seconds as HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def estimate_recording_time(free_bytes, bytes_per_second):
    """Estimate remaining recording time"""
    if bytes_per_second <= 0:
        return "Unknown"
    
    seconds_remaining = free_bytes / bytes_per_second
    hours = int(seconds_remaining // 3600)
    minutes = int((seconds_remaining % 3600) // 60)
    
    if hours > 99:
        return "99h+"
    elif hours > 0:
        return f"{hours:2d}h {minutes:2d}m"
    else:
        return f"{minutes:3d}m"
