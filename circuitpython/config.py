"""
config.py - Configuration Manager for OpenPonyLogger

Handles TOML parsing, profile switching, and configuration access.
"""

import os


class Config:
    """
    Configuration manager with profile support
    
    Parses settings.toml and provides typed access to configuration values.
    Supports profile switching (e.g., daily -> track mode).
    """
    
    def __init__(self, path='settings.toml'):
        """
        Initialize configuration
        
        Args:
            path: Path to settings.toml file
        """
        self.path = path
        self.config = {}
        self.active_profile = None
        self._load()
    
    def _load(self):
        """Load and parse TOML configuration"""
        if not self._file_exists(self.path):
            print(f"[Config] Warning: {self.path} not found, using defaults")
            self._set_defaults()
            return
        
        try:
            # CircuitPython doesn't have a built-in TOML parser
            # We'll implement a simple one for our needs
            self.config = self._parse_toml(self.path)
            
            # Determine active profile
            startup_profile = self.get('general.StartUp_Config', 'general.daily')
            if '.' in startup_profile:
                self.active_profile = startup_profile
            else:
                self.active_profile = f'general.{startup_profile}'
            
            print(f"[Config] Loaded from {self.path}")
            print(f"[Config] Active profile: {self.active_profile}")
            
        except Exception as e:
            print(f"[Config] Error loading {self.path}: {e}")
            self._set_defaults()
    
    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _parse_toml(self, path):
        """
        Simple TOML parser for CircuitPython
        
        Supports:
        - Sections: [section.subsection]
        - Key-value pairs: key = value
        - Strings, numbers, booleans
        - Comments with #
        """
        config = {}
        current_section = None
        
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Section header
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].strip()
                    continue
                
                # Key-value pair
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove inline comments
                    if '#' in value:
                        value = value.split('#')[0].strip()
                    
                    # Parse value
                    parsed_value = self._parse_value(value)
                    
                    # Store in config dict
                    if current_section:
                        full_key = f"{current_section}.{key}"
                    else:
                        full_key = key
                    
                    config[full_key] = parsed_value
        
        return config
    
    def _parse_value(self, value):
        """Parse TOML value to Python type"""
        # Remove quotes from strings
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        
        # Boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        
        # Hex number
        if value.startswith('0x') or value.startswith('0X'):
            return int(value, 16)
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _set_defaults(self):
        """Set default configuration"""
        self.config = {
            'general.Driver_name': 'Driver',
            'general.Vehicle_id': 'Vehicle',
            'general.NEOPIXEL_ENABLED': False,
            'general.daily.GPS_Update_rate': 1000,
            'general.daily.Accel_sample_rate': 100,
            'general.daily.Gforce_Event_threshold': 2.5,
            'hardware.name': 'OpenPonyLogger',
            'sensors.accelerometer.enabled': True,
            'sensors.accelerometer.type': 'LIS3DH',
            'sensors.accelerometer.address': 0x18,
            'gps.enabled': True,
            'gps.type': 'ATGM336H',
            'radio.mode': 'ap',
            'radio.ssid': 'OpenPonyLogger',
            'radio.password': 'mustanggt',
        }
        self.active_profile = 'general.daily'
    
    def get(self, key, default=None):
        """
        Get configuration value
        
        Args:
            key: Configuration key (dot-separated for nested values)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        # Check if key exists directly
        if key in self.config:
            return self.config[key]
        
        # Check in active profile
        if self.active_profile:
            profile_key = f"{self.active_profile}.{key}"
            if profile_key in self.config:
                return self.config[profile_key]
        
        return default
    
    def get_section(self, section):
        """
        Get all keys in a section
        
        Args:
            section: Section name (e.g., 'hardware' or 'sensors.accelerometer')
            
        Returns:
            Dictionary of keys in section
        """
        result = {}
        prefix = section + '.'
        
        for key, value in self.config.items():
            if key.startswith(prefix):
                # Extract the key after the section prefix
                short_key = key[len(prefix):]
                # Only include direct children (not nested sections)
                if '.' not in short_key:
                    result[short_key] = value
        
        return result
    
    def switch_profile(self, profile_name):
        """
        Switch active profile
        
        Args:
            profile_name: Name of profile (e.g., 'track' or 'general.track')
        """
        if '.' not in profile_name:
            profile_name = f'general.{profile_name}'
        
        self.active_profile = profile_name
        print(f"[Config] Switched to profile: {profile_name}")
    
    def save(self):
        """Save current configuration back to TOML file"""
        # TODO: Implement TOML writing if needed
        print("[Config] Warning: save() not yet implemented")
    
    def dump(self):
        """Print all configuration for debugging"""
        print("\n" + "="*60)
        print("Configuration Dump")
        print("="*60)
        print(f"Active Profile: {self.active_profile}")
        print("-"*60)
        
        # Group by section
        sections = {}
        for key, value in sorted(self.config.items()):
            if '.' in key:
                section = key.rsplit('.', 1)[0]
            else:
                section = 'root'
            
            if section not in sections:
                sections[section] = []
            sections[section].append((key, value))
        
        for section, items in sorted(sections.items()):
            print(f"\n[{section}]")
            for key, value in items:
                short_key = key.split('.')[-1]
                print(f"  {short_key} = {value!r}")
        
        print("="*60 + "\n")
