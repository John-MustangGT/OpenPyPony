#!/usr/bin/env python3
"""
opl_types.py - Shared types, constants, and utilities for OpenPonyLogger

This module provides:
- File format constants (magic bytes, block types, sample types)
- Timestamp handling (Unix epoch conversions, monotonic detection)
- Data type definitions and conversions
- Common validation logic

All OPL tools (opl2csv, opl2traccar, opl-info) should import from here
to ensure consistent handling of the binary format.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import struct


# ============================================================================
# File Format Constants
# ============================================================================

# Magic bytes and version
MAGIC_BYTES = b'OPNY'
FORMAT_VERSION_MAJOR = 2
FORMAT_VERSION_MINOR = 0

# Block types
BLOCK_TYPE_SESSION_HEADER = 0x01
BLOCK_TYPE_HARDWARE_CONFIG = 0x02
BLOCK_TYPE_DATA_BLOCK = 0x03
BLOCK_TYPE_SESSION_END = 0x04

# Hardware types
HW_TYPE_MAP = {
    0x01: "Accelerometer",
    0x02: "GPS",
    0x03: "Display",
    0x04: "Storage",
    0x05: "RTC",
    0x06: "LED",
    0x07: "NeoPixel",
    0x08: "Radio",
    0x09: "OBD",
    0x0A: "CAN"
}

# Connection types
CONN_TYPE_MAP = {
    0x01: "I2C",
    0x02: "SPI",
    0x03: "UART",
    0x04: "GPIO",
    0x05: "STEMMA QT",
    0x06: "Built-in"
}

# Sample types
SAMPLE_TYPE_ACCELEROMETER = 0x01
SAMPLE_TYPE_GPS_FIX = 0x02
SAMPLE_TYPE_GPS_SATELLITES = 0x03
SAMPLE_TYPE_OBD_PID = 0x10
SAMPLE_TYPE_EVENT_MARKER = 0x20

# Weather conditions
WEATHER_MAP = {
    0: "Unknown",
    1: "Clear",
    2: "Cloudy",
    3: "Rain",
    4: "Snow",
    5: "Fog"
}

# Flush flags
FLUSH_FLAG_TIME = 0x01
FLUSH_FLAG_SIZE = 0x02
FLUSH_FLAG_EVENT = 0x04
FLUSH_FLAG_MANUAL = 0x08
FLUSH_FLAG_SHUTDOWN = 0x10


# ============================================================================
# Timestamp Handling
# ============================================================================

class OPLTimestamp:
    """
    Handle OpenPonyLogger timestamps
    
    Timestamps in OPL files are microseconds since Unix epoch (1970-01-01).
    However, before GPS/RTC sync, the Pico may log using monotonic time
    (microseconds since boot), creating a discontinuity when sync occurs.
    
    This class provides utilities to:
    - Detect monotonic vs RTC-synced timestamps
    - Convert to datetime objects
    - Calculate durations
    - Find verified time ranges
    """
    
    # Threshold: timestamps below this are monotonic (< ~16 minutes uptime)
    MONOTONIC_THRESHOLD = 1_000_000_000  # 1 billion µs = ~16.7 minutes
    
    # Threshold: timestamps above this are RTC-synced (year 2000+)
    # 946,684,800 seconds = Jan 1, 2000 00:00:00 UTC (from Unix epoch 1970)
    RTC_THRESHOLD = 946_684_800_000_000  # microseconds
    
    @staticmethod
    def is_monotonic(timestamp_us: int) -> bool:
        """Check if timestamp is monotonic (pre-RTC sync)"""
        return timestamp_us < OPLTimestamp.MONOTONIC_THRESHOLD
    
    @staticmethod
    def is_rtc_synced(timestamp_us: int) -> bool:
        """Check if timestamp is RTC-synced (year 2000+)"""
        return timestamp_us >= OPLTimestamp.RTC_THRESHOLD
    
    @staticmethod
    def to_datetime(timestamp_us: int, tz=None) -> Optional[datetime]:
        """
        Convert timestamp to datetime
        
        Args:
            timestamp_us: Microseconds since Unix epoch (1970-01-01)
            tz: Timezone (default: None for local, use timezone.utc for UTC)
        
        Returns:
            datetime object, or None if monotonic timestamp
        """
        if OPLTimestamp.is_monotonic(timestamp_us):
            return None  # Can't convert monotonic to absolute time
        
        if tz:
            return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=tz)
        else:
            return datetime.fromtimestamp(timestamp_us / 1_000_000)
    
    @staticmethod
    def to_duration(timestamp_us: int) -> timedelta:
        """Convert timestamp to duration (for monotonic time)"""
        return timedelta(microseconds=timestamp_us)
    
    @staticmethod
    def find_verified_range(timestamps: List[int]) -> Optional[tuple]:
        """
        Find verified RTC-synced time range
        
        Args:
            timestamps: List of timestamps (microseconds)
        
        Returns:
            (first_rtc, last_rtc) tuple, or None if no RTC timestamps
        """
        rtc_timestamps = [t for t in timestamps if OPLTimestamp.is_rtc_synced(t)]
        if not rtc_timestamps:
            return None
        return (min(rtc_timestamps), max(rtc_timestamps))
    
    @staticmethod
    def classify_timestamps(timestamps: List[int]) -> Dict[str, int]:
        """
        Classify timestamps by type
        
        Returns:
            Dictionary with counts:
            - monotonic: Count of monotonic timestamps
            - rtc: Count of RTC-synced timestamps
            - invalid: Count of timestamps in the gap between thresholds
        """
        monotonic = sum(1 for t in timestamps if OPLTimestamp.is_monotonic(t))
        rtc = sum(1 for t in timestamps if OPLTimestamp.is_rtc_synced(t))
        invalid = len(timestamps) - monotonic - rtc
        
        return {
            'monotonic': monotonic,
            'rtc': rtc,
            'invalid': invalid,
            'total': len(timestamps)
        }


# ============================================================================
# Data Type Definitions
# ============================================================================

@dataclass
class SessionHeader:
    """Session header information"""
    format_version: str
    hw_version: str
    timestamp: datetime
    session_id: str
    session_name: str
    driver_name: str
    vehicle_id: str
    weather: str
    ambient_temp: float
    config_crc: int


@dataclass
class HardwareConfig:
    """Hardware configuration block"""
    count: int
    items: List[Dict[str, str]]  # Each item: {type, connection, identifier}


@dataclass
class DataBlock:
    """Data block information"""
    block_seq: int
    timestamp_start: int
    timestamp_end: int
    flush_flags: int
    samples: List[Dict[str, Any]]


@dataclass
class AccelSample:
    """Accelerometer sample"""
    timestamp_us: int
    gx: float
    gy: float
    gz: float


@dataclass
class GPSSample:
    """GPS fix sample"""
    timestamp_us: int
    lat: float
    lon: float
    alt: float
    speed: float
    heading: float
    hdop: float


@dataclass
class SatelliteSample:
    """GPS satellite data sample"""
    timestamp_us: int
    satellites: List[Dict[str, int]]  # Each: {id, snr, flags} or {id, azimuth, elevation, snr}


# ============================================================================
# Sample Parsing
# ============================================================================

class SampleParser:
    """Parse binary sample data"""
    
    @staticmethod
    def parse_accelerometer(data: bytes) -> Optional[Dict[str, float]]:
        """
        Parse accelerometer sample (12 bytes: 3x float32)
        
        Returns:
            {gx, gy, gz} or None if invalid
        """
        if len(data) < 12:
            return None
        
        gx, gy, gz = struct.unpack('<fff', data[:12])
        return {'gx': gx, 'gy': gy, 'gz': gz}
    
    @staticmethod
    def parse_gps_fix(data: bytes) -> Optional[Dict[str, float]]:
        """
        Parse GPS fix sample (24 bytes: 6x float32)
        
        Returns:
            {lat, lon, alt, speed, heading, hdop} or None if invalid
        """
        if len(data) < 24:
            return None
        
        lat, lon, alt, speed, heading, hdop = struct.unpack('<ffffff', data[:24])
        return {
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'speed': speed,
            'heading': heading,
            'hdop': hdop
        }
    
    @staticmethod
    def parse_gps_satellites(data: bytes) -> Optional[List[Dict[str, int]]]:
        """
        Parse GPS satellite data
        
        Two formats supported:
        - Compact: 3 bytes per satellite (id, snr, flags)
        - Full: 4 bytes per satellite (id, azimuth, elevation, snr)
        
        Returns:
            List of satellite dicts or None if invalid
        """
        if len(data) == 0:
            return None
        
        satellites = []
        
        # Try 4-byte format first (id, azimuth, elevation, snr)
        if len(data) % 4 == 0:
            count = len(data) // 4
            for i in range(count):
                sat_id, azimuth, elevation, snr = struct.unpack('<BBBB', data[i*4:i*4+4])
                satellites.append({
                    'id': sat_id,
                    'azimuth': azimuth,
                    'elevation': elevation,
                    'snr': snr
                })
            return satellites
        
        # Try 3-byte format (id, snr, flags)
        if len(data) % 3 == 0:
            count = len(data) // 3
            for i in range(count):
                sat_id, snr, flags = struct.unpack('<BBB', data[i*3:i*3+3])
                satellites.append({
                    'id': sat_id,
                    'snr': snr,
                    'flags': flags
                })
            return satellites
        
        return None


# ============================================================================
# Data Validation
# ============================================================================

class OPLValidator:
    """Validate OPL data"""
    
    @staticmethod
    def is_valid_magic(magic: bytes) -> bool:
        """Check if magic bytes are valid"""
        return magic == MAGIC_BYTES
    
    @staticmethod
    def is_valid_version(major: int, minor: int) -> bool:
        """Check if format version is supported"""
        # Support v2.0 and future v2.x versions
        return major == FORMAT_VERSION_MAJOR
    
    @staticmethod
    def is_valid_gps_fix(fix: Dict[str, float]) -> bool:
        """
        Check if GPS fix is valid
        
        Valid if:
        - Latitude in range [-90, 90]
        - Longitude in range [-180, 180]
        - HDOP > 0 (has fix)
        """
        return (
            -90 <= fix['lat'] <= 90 and
            -180 <= fix['lon'] <= 180 and
            fix['hdop'] > 0
        )
    
    @staticmethod
    def is_valid_accel(accel: Dict[str, float]) -> bool:
        """
        Check if accelerometer reading is valid
        
        Valid if total G-force is reasonable (< 10g for normal driving)
        """
        g_total = (accel['gx']**2 + accel['gy']**2 + accel['gz']**2) ** 0.5
        return 0 < g_total < 10.0


# ============================================================================
# Unit Conversions
# ============================================================================

class UnitConverter:
    """Convert between units"""
    
    @staticmethod
    def mph_to_knots(mph: float) -> float:
        """Convert MPH to knots (for Traccar)"""
        return mph * 0.868976
    
    @staticmethod
    def knots_to_mph(knots: float) -> float:
        """Convert knots to MPH"""
        return knots / 0.868976
    
    @staticmethod
    def meters_to_feet(meters: float) -> float:
        """Convert meters to feet"""
        return meters * 3.28084
    
    @staticmethod
    def feet_to_meters(feet: float) -> float:
        """Convert feet to meters"""
        return feet / 3.28084
    
    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return celsius * 9/5 + 32
    
    @staticmethod
    def fahrenheit_to_celsius(fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9


# ============================================================================
# Sample Type Names
# ============================================================================

SAMPLE_TYPE_NAMES = {
    SAMPLE_TYPE_ACCELEROMETER: 'accel',
    SAMPLE_TYPE_GPS_FIX: 'gps',
    SAMPLE_TYPE_GPS_SATELLITES: 'satellites',
    SAMPLE_TYPE_OBD_PID: 'obd',
    SAMPLE_TYPE_EVENT_MARKER: 'event'
}

def get_sample_type_name(sample_type: int) -> str:
    """Get human-readable sample type name"""
    return SAMPLE_TYPE_NAMES.get(sample_type, f'unknown_{sample_type:#x}')


# ============================================================================
# Utility Functions
# ============================================================================

def format_timestamp(timestamp_us: int, show_type: bool = False) -> str:
    """
    Format timestamp for display
    
    Args:
        timestamp_us: Timestamp in microseconds
        show_type: If True, append (monotonic) or (RTC) indicator
    
    Returns:
        Formatted string
    """
    if OPLTimestamp.is_monotonic(timestamp_us):
        duration = OPLTimestamp.to_duration(timestamp_us)
        suffix = " (monotonic)" if show_type else ""
        return f"{timestamp_us:,} µs = {duration}{suffix}"
    
    dt = OPLTimestamp.to_datetime(timestamp_us)
    suffix = " (RTC)" if show_type else ""
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}{suffix}"


def format_duration(duration_us: int) -> str:
    """
    Format duration for display
    
    Args:
        duration_us: Duration in microseconds
    
    Returns:
        Formatted string (HH:MM:SS or MM:SS for short durations)
    """
    duration = timedelta(microseconds=duration_us)
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 3600:  # Less than 1 hour
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_filesize(bytes: int) -> str:
    """Format file size for display"""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    else:
        return f"{bytes / (1024 * 1024):.1f} MB"


# ============================================================================
# Version Info
# ============================================================================

def get_version_string() -> str:
    """Get version string for tools"""
    return f"OpenPonyLogger Format v{FORMAT_VERSION_MAJOR}.{FORMAT_VERSION_MINOR}"


if __name__ == '__main__':
    # Self-test
    print(get_version_string())
    print()
    
    # Test timestamp handling
    print("Timestamp Tests:")
    print("-" * 60)
    
    # Monotonic timestamp (1 second since boot)
    ts_mono = 1_000_000
    print(f"Monotonic: {format_timestamp(ts_mono, show_type=True)}")
    print(f"  Is monotonic: {OPLTimestamp.is_monotonic(ts_mono)}")
    print(f"  Is RTC: {OPLTimestamp.is_rtc_synced(ts_mono)}")
    print()
    
    # RTC timestamp (Dec 17, 2025)
    ts_rtc = 1_765_892_623_000_000
    print(f"RTC: {format_timestamp(ts_rtc, show_type=True)}")
    print(f"  Is monotonic: {OPLTimestamp.is_monotonic(ts_rtc)}")
    print(f"  Is RTC: {OPLTimestamp.is_rtc_synced(ts_rtc)}")
    print(f"  Datetime: {OPLTimestamp.to_datetime(ts_rtc)}")
    print()
    
    # Test classification
    timestamps = [1_000_000, 2_000_000, ts_rtc, ts_rtc + 1_000_000]
    classification = OPLTimestamp.classify_timestamps(timestamps)
    print("Classification:")
    for key, value in classification.items():
        print(f"  {key}: {value}")
    print()
    
    # Test conversions
    print("Unit Conversions:")
    print("-" * 60)
    print(f"60 MPH = {UnitConverter.mph_to_knots(60):.2f} knots")
    print(f"100 meters = {UnitConverter.meters_to_feet(100):.2f} feet")
    print(f"20°C = {UnitConverter.celsius_to_fahrenheit(20):.1f}°F")
