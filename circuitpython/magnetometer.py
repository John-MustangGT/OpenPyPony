"""
magnetometer.py - Magnetometer data handler for OpenPonyLogger

Handles magnetometer data from various sensors:
- LIS3MDL
- ICM-20948 (AK09916)
"""

import time
import math


class Magnetometer:
    """Magnetometer data handler"""
    
    def __init__(self, mag_sensor):
        """
        Initialize magnetometer handler
        
        Args:
            mag_sensor: Magnetometer sensor object
        """
        self.sensor = mag_sensor
        self.last_reading = None
        self.last_timestamp = 0
        
        # Calibration offsets (set via calibration)
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        
        # Peak tracking
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
    
    def read(self):
        """
        Read magnetometer data
        
        Returns:
            tuple: (mx, my, mz, timestamp) in micro-Tesla
        """
        try:
            mx, my, mz = self.sensor.magnetic
            timestamp = time.monotonic()
            
            # Apply calibration offsets
            mx -= self.offset_x
            my -= self.offset_y
            mz -= self.offset_z
            
            self.last_reading = (mx, my, mz)
            self.last_timestamp = timestamp
            
            # Update peaks
            if abs(mx) > abs(self.peak_x):
                self.peak_x = mx
            if abs(my) > abs(self.peak_y):
                self.peak_y = my
            if abs(mz) > abs(self.peak_z):
                self.peak_z = mz
            
            return mx, my, mz, timestamp
            
        except Exception as e:
            print(f"[Mag] Read error: {e}")
            return 0.0, 0.0, 0.0, time.monotonic()
    
    def get_last_reading(self):
        """Get last reading without triggering new read"""
        return self.last_reading if self.last_reading else (0.0, 0.0, 0.0)
    
    def get_peaks(self):
        """Get peak magnetic field strengths"""
        return self.peak_x, self.peak_y, self.peak_z
    
    def reset_peaks(self):
        """Reset peak tracking"""
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
    
    def get_heading(self):
        """
        Calculate magnetic heading (0-360°)
        
        Note: This is a simple 2D heading calculation.
        For accurate heading, you need proper tilt compensation
        using accelerometer data.
        
        Returns:
            float: Heading in degrees (0° = North, 90° = East)
        """
        if not self.last_reading:
            return 0.0
        
        mx, my, mz = self.last_reading
        
        # Calculate heading (atan2 gives -180 to +180)
        heading = math.atan2(my, mx) * 180.0 / math.pi
        
        # Normalize to 0-360
        if heading < 0:
            heading += 360.0
        
        return heading
    
    def get_field_strength(self):
        """
        Get total magnetic field strength
        
        Returns:
            float: Field strength in micro-Tesla
        """
        if not self.last_reading:
            return 0.0
        
        mx, my, mz = self.last_reading
        return (mx**2 + my**2 + mz**2)**0.5
    
    def set_calibration(self, offset_x, offset_y, offset_z):
        """
        Set calibration offsets
        
        Args:
            offset_x, offset_y, offset_z: Calibration offsets in micro-Tesla
        """
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z = offset_z
        print(f"[Mag] Calibration set: X={offset_x:.1f} Y={offset_y:.1f} Z={offset_z:.1f}")
    
    def format_reading(self, mx=None, my=None, mz=None):
        """
        Format magnetometer reading for display
        
        Args:
            mx, my, mz: Field strengths (if None, uses last reading)
        
        Returns:
            str: Formatted string
        """
        if mx is None:
            if self.last_reading:
                mx, my, mz = self.last_reading
            else:
                return "No data"
        
        return f"X:{mx:+6.1f}µT Y:{my:+6.1f}µT Z:{mz:+6.1f}µT"
