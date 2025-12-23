"""
gyroscope.py - Gyroscope data handler for OpenPonyLogger

Handles gyroscope data from various IMUs:
- LSM6DSOX
- ICM-20948
- MPU-6050/GY-521
"""

import time


class Gyroscope:
    """Gyroscope data handler"""
    
    def __init__(self, gyro_sensor):
        """
        Initialize gyroscope handler
        
        Args:
            gyro_sensor: Gyroscope sensor object (IMU with .gyro property)
        """
        self.sensor = gyro_sensor
        self.last_reading = None
        self.last_timestamp = 0
        
        # Peak tracking
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
    
    def read(self):
        """
        Read gyroscope data
        
        Returns:
            tuple: (gx, gy, gz, timestamp) in degrees/sec
        """
        try:
            gx, gy, gz = self.sensor.gyro
            timestamp = time.monotonic()
            
            self.last_reading = (gx, gy, gz)
            self.last_timestamp = timestamp
            
            # Update peaks
            if abs(gx) > abs(self.peak_x):
                self.peak_x = gx
            if abs(gy) > abs(self.peak_y):
                self.peak_y = gy
            if abs(gz) > abs(self.peak_z):
                self.peak_z = gz
            
            return gx, gy, gz, timestamp
            
        except Exception as e:
            print(f"[Gyro] Read error: {e}")
            return 0.0, 0.0, 0.0, time.monotonic()
    
    def get_last_reading(self):
        """Get last reading without triggering new read"""
        return self.last_reading if self.last_reading else (0.0, 0.0, 0.0)
    
    def get_peaks(self):
        """Get peak rotation rates"""
        return self.peak_x, self.peak_y, self.peak_z
    
    def reset_peaks(self):
        """Reset peak tracking"""
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
    
    def format_reading(self, gx=None, gy=None, gz=None):
        """
        Format gyroscope reading for display
        
        Args:
            gx, gy, gz: Rotation rates (if None, uses last reading)
        
        Returns:
            str: Formatted string
        """
        if gx is None:
            if self.last_reading:
                gx, gy, gz = self.last_reading
            else:
                return "No data"
        
        return f"X:{gx:+6.1f}°/s Y:{gy:+6.1f}°/s Z:{gz:+6.1f}°/s"
    
    def get_angular_velocity(self):
        """
        Get total angular velocity magnitude
        
        Returns:
            float: Total angular velocity in degrees/sec
        """
        if not self.last_reading:
            return 0.0
        
        gx, gy, gz = self.last_reading
        return (gx**2 + gy**2 + gz**2)**0.5
