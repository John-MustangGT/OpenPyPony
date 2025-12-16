"""
config.py - Configuration management for OpenPonyLogger

Handles loading settings from settings.toml and environment variables
"""

import os

class Config:
    """Configuration settings"""
    
    def __init__(self):
        # Logging format
        self.log_format = self._get('LOG_FORMAT', 'binary').lower()  # 'binary' or 'csv'
        
        # Session metadata
        self.session_name = self._get('SESSION_NAME', 'Track Day')
        self.driver_name = self._get('DRIVER_NAME', 'Unknown')
        self.vehicle_id = self._get('VEHICLE_ID', 'Unknown')
        
        # Sample rates
        self.accel_sample_rate = self.get_int('ACCEL_SAMPLE_RATE', 100)  # Hz
        self.gps_update_rate = self.get_int('GPS_UPDATE_RATE', 1000)  # ms
        
        # Thresholds
        self.gforce_event_threshold = self.get_float('GFORCE_EVENT_THRESHOLD', 3.0)
        
        # Display
        self.splash_duration = self.get_float('SPLASH_DURATION', 2.0)  # seconds
        self.oled_brightness = self.get_int('OLED_BRIGHTNESS', 255)
        
        # NeoPixel
        self.neopixel_brightness = self.get_float('NEOPIXEL_BRIGHTNESS', 0.3)
        self.neopixel_enabled = self.get_bool('NEOPIXEL_ENABLED', True)
        
        # WiFi
        self.wifi_ssid = self._get('WIFI_SSID', 'OpenPonyLogger')
        self.wifi_password = self._get('WIFI_PASSWORD', 'mustanggt')
        self.wifi_enabled = self.get_bool('WIFI_ENABLED', True)
        
        # Debug
        self.serial_debug = self.get_bool('SERIAL_DEBUG', True)
        
        # Storage
        self.sd_path = '/sd'
        
    def _get(self, key, default=''):
        """Get config value from environment or return default"""
        return os.getenv(key, default)
    
    def get(self, key, default=''):
        """Get config value (public method)"""
        return self._get(key, default)
    
    def get_int(self, key, default=0):
        """Get config value as integer"""
        try:
            return int(self._get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key, default=0.0):
        """Get config value as float"""
        try:
            return float(self._get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key, default=False):
        """Get config value as boolean"""
        value = self._get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def to_dict(self):
        """Convert config to dictionary"""
        return {
            'log_format': self.log_format,
            'session_name': self.session_name,
            'driver_name': self.driver_name,
            'vehicle_id': self.vehicle_id,
            'accel_sample_rate': self.accel_sample_rate,
            'gps_update_rate': self.gps_update_rate,
            'gforce_event_threshold': self.gforce_event_threshold,
            'splash_duration': self.splash_duration,
            'oled_brightness': self.oled_brightness,
            'neopixel_brightness': self.neopixel_brightness,
            'neopixel_enabled': self.neopixel_enabled,
            'wifi_ssid': self.wifi_ssid,
            'wifi_enabled': self.wifi_enabled,
            'serial_debug': self.serial_debug,
        }
    
    def __repr__(self):
        return f"Config(log_format={self.log_format}, driver={self.driver_name}, vehicle={self.vehicle_id})"


# Global config instance
config = Config()
