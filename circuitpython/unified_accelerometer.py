"""
unified_accelerometer.py - Unified accelerometer handler
Supports: LIS3DH, LSM6DSOX, ICM-20948, MPU-6050
"""

import time

class UnifiedAccelerometer:
    """Unified handler for all supported accelerometers"""
    
    def __init__(self, accel_sensor):
        """
        Initialize accelerometer handler
        
        Args:
            accel_sensor: Initialized accelerometer object
        """
        self.sensor = accel_sensor
        self.sensor_type = type(accel_sensor).__name__
        
        # Determine sensor type and capabilities
        if 'LIS3DH' in self.sensor_type:
            self.name = 'LIS3DH'
            self.has_tap = True
        elif 'LSM6DSOX' in self.sensor_type or 'LSM6DS' in self.sensor_type:
            self.name = 'LSM6DSOX'
            self.has_tap = False
        elif 'ICM20948' in self.sensor_type or 'ICM' in self.sensor_type:
            self.name = 'ICM-20948'
            self.has_tap = False
        elif 'MPU6050' in self.sensor_type or 'MPU' in self.sensor_type:
            self.name = 'MPU-6050'
            self.has_tap = False
        else:
            self.name = 'Unknown'
            self.has_tap = False
        
        # Peak tracking
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
        
        # Last reading cache
        self.last_x = 0.0
        self.last_y = 0.0
        self.last_z = 0.0
        self.last_timestamp = 0
        
        print(f"  Accelerometer handler: {self.name}")
    
    def read(self):
        """
        Read acceleration values
        
        Returns:
            tuple: (x, y, z, timestamp) in m/s²
        """
        try:
            # All supported sensors use .acceleration property
            x, y, z = self.sensor.acceleration
            
            # Update cache
            self.last_x = x
            self.last_y = y
            self.last_z = z
            self.last_timestamp = time.monotonic()
            
            # Update peaks (absolute values)
            self.peak_x = max(self.peak_x, abs(x))
            self.peak_y = max(self.peak_y, abs(y))
            self.peak_z = max(self.peak_z, abs(z))
            
            return (x, y, z, self.last_timestamp)
            
        except Exception as e:
            print(f"Accel read error: {e}")
            return (0.0, 0.0, 0.0, time.monotonic())
    
    def get_g_forces(self):
        """
        Get acceleration as G-forces
        
        Returns:
            tuple: (gx, gy, gz) in g
        """
        x, y, z, _ = self.read()
        return (x / 9.81, y / 9.81, z / 9.81)
    
    def get_total_g(self):
        """
        Get total G-force magnitude
        
        Returns:
            float: Total g-force
        """
        gx, gy, gz = self.get_g_forces()
        return (gx**2 + gy**2 + gz**2)**0.5
    
    def get_last_reading(self):
        """Get the last cached reading without triggering a new read"""
        return (self.last_x, self.last_y, self.last_z)
    
    def get_peaks(self):
        """
        Get peak acceleration values
        
        Returns:
            tuple: (peak_x, peak_y, peak_z) in m/s²
        """
        return (self.peak_x, self.peak_y, self.peak_z)
    
    def reset_peaks(self):
        """Reset peak tracking"""
        self.peak_x = 0.0
        self.peak_y = 0.0
        self.peak_z = 0.0
    
    def format_reading(self):
        """
        Format current reading for display
        
        Returns:
            str: Formatted string
        """
        gx, gy, gz = self.get_g_forces()
        return f"X:{gx:+.2f}g Y:{gy:+.2f}g Z:{gz:+.2f}g"
    
    def check_tap(self):
        """
        Check for tap detection (LIS3DH only)
        
        Returns:
            tuple: (tapped, tap_type) where tap_type is 1 or 2
        """
        if not self.has_tap:
            return (False, 0)
        
        try:
            if hasattr(self.sensor, 'tapped'):
                tapped = self.sensor.tapped
                if tapped:
                    # Try to determine single vs double tap
                    # LIS3DH has different attributes depending on library version
                    if hasattr(self.sensor, 'tap'):
                        return (True, self.sensor.tap)
                    else:
                        return (True, 1)  # Assume single tap
                return (False, 0)
        except Exception as e:
            print(f"Tap check error: {e}")
        
        return (False, 0)
