"""
hardware_config.py - Hardware configuration loader for OpenPonyLogger

Loads hardware.toml and provides type-safe access to hardware configuration.
"""

import board

class HardwareConfig:
    """Hardware configuration manager"""
    
    def __init__(self, config_dict):
        """
        Initialize from parsed TOML dictionary
        
        Args:
            config_dict: Dictionary from toml.load()
        """
        self._config = config_dict
    
    def _get_nested(self, path, default=None):
        """
        Get nested config value using dot notation
        
        Args:
            path: Dot-separated path (e.g., "sensors.accelerometer.enabled")
            default: Default value if not found
        
        Returns:
            Value at path or default
        """
        keys = path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get(self, path, default=None):
        """Get config value (string)"""
        return self._get_nested(path, default)
    
    def get_bool(self, path, default=False):
        """Get boolean config value"""
        value = self._get_nested(path, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def get_int(self, path, default=0):
        """Get integer config value"""
        value = self._get_nested(path, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def get_float(self, path, default=0.0):
        """Get float config value"""
        value = self._get_nested(path, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
    def get_pin(self, path, default=None):
        """
        Get board pin from config
        
        Args:
            path: Config path (e.g., "indicators.heartbeat_led.pin")
            default: Default pin if not found
        
        Returns:
            board.Pin object or None
        """
        pin_str = self.get(path)
        if not pin_str:
            return default
        
        return self.pin_from_string(pin_str)
    
    @staticmethod
    def pin_from_string(pin_str):
        """
        Convert pin string to board.Pin object
        
        Args:
            pin_str: Pin string (e.g., "GP25", "LED", "STEMMA_I2C")
        
        Returns:
            board.Pin object or None
        """
        if not pin_str:
            return None
        
        # Debug output
        # print(f"[Debug] pin_from_string: '{pin_str}' (type: {type(pin_str).__name__})")
        
        # Handle special names
        if pin_str == "STEMMA_I2C":
            return board.STEMMA_I2C()
        
        # Common board aliases
        # On Pico W, GP25 is the LED but accessed as board.LED
        board_aliases = {
            'GP25': 'LED',  # Pico/Pico W onboard LED
            'LED': 'LED',
            'NEOPIXEL': 'NEOPIXEL',
            'VBUS_SENSE': 'VBUS_SENSE',
        }
        
        # Check if this pin has a board alias
        if pin_str in board_aliases:
            alias = board_aliases[pin_str]
            try:
                pin_obj = getattr(board, alias)
                # print(f"[Debug] Converted '{pin_str}' via alias '{alias}' → {pin_obj}")
                return pin_obj
            except AttributeError:
                # If alias doesn't exist, continue to GP## handling
                pass
        
        # Handle GP## format
        if isinstance(pin_str, str) and pin_str.startswith("GP"):
            try:
                pin_num = int(pin_str[2:])
                pin_obj = getattr(board, f"GP{pin_num}")
                # print(f"[Debug] Converted '{pin_str}' → {pin_obj}")
                return pin_obj
            except (ValueError, AttributeError) as e:
                # Special case: GP25 on Pico W
                if pin_num == 25:
                    try:
                        pin_obj = getattr(board, 'LED')
                        print(f"[Info] GP25 → board.LED (Pico W onboard LED)")
                        return pin_obj
                    except AttributeError:
                        pass
                print(f"[Warning] Failed to convert pin '{pin_str}': {e}")
                return None
        
        # Try direct board attribute
        try:
            return getattr(board, pin_str)
        except AttributeError:
            print(f"[Warning] Pin '{pin_str}' not found on board")
            return None
    
    def is_enabled(self, path):
        """
        Check if a peripheral is enabled
        
        Args:
            path: Base path (e.g., "sensors.accelerometer")
        
        Returns:
            bool: True if enabled
        """
        return self.get_bool(f"{path}.enabled", False)
    
    def get_interface_pins(self, interface_name):
        """
        Get all pins for an interface
        
        Args:
            interface_name: Interface name (e.g., "i2c", "spi")
        
        Returns:
            dict: Pin mappings with actual Pin objects
        """
        base_path = f"interfaces.{interface_name}"
        if not self.is_enabled(base_path):
            return {}
        
        pins = {}
        interface_config = self._get_nested(base_path, {})
        
        # Known pin parameter names that should be converted to Pin objects
        pin_params = ['sda', 'scl', 'sck', 'mosi', 'miso', 'tx', 'rx', 'cs']
        
        for key, value in interface_config.items():
            if key == "enabled":
                continue
            
            # Convert pin strings to Pin objects
            if key in pin_params and isinstance(value, str):
                pin_obj = self.pin_from_string(value)
                pins[key] = pin_obj
            else:
                # Keep other values as-is (baudrate, frequency, etc.)
                pins[key] = value
        
        return pins


def load_hardware_config(filepath="/hardware.toml"):
    """
    Load hardware configuration from TOML file
    
    Args:
        filepath: Path to hardware.toml
    
    Returns:
        HardwareConfig object
    """
    import os
    
    # Check if file exists (handle both /hardware.toml and hardware.toml)
    filename = filepath.lstrip('/')
    
    try:
        files = os.listdir('/')
        if filename not in files:
            print(f"[Hardware] No {filename} found - using defaults")
            return HardwareConfig({})
    except:
        # If we can't list dir, try to open the file anyway
        pass
    
    print(f"[Hardware] Loading {filepath}...")
    
    try:
        # Try cptoml (CircuitPython TOML library)
        import cptoml
        with open(filepath, 'r') as f:
            config_dict = cptoml.load(f)
        print(f"[Hardware] Loaded with cptoml ({len(config_dict)} sections)")
        return HardwareConfig(config_dict)
    except ImportError:
        print("[Hardware] cptoml not available, using simple parser...")
        
        # Try simple TOML parser fallback
        try:
            config_dict = parse_simple_toml(filepath)
            print(f"[Hardware] Loaded with simple parser ({len(config_dict)} sections)")
            return HardwareConfig(config_dict)
        except Exception as e:
            print(f"[Hardware] Simple parser failed: {e}")
            import traceback
            traceback.print_exc()
            return HardwareConfig({})
    except Exception as e:
        print(f"[Hardware] Error loading {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return HardwareConfig({})


def parse_simple_toml(filepath):
    """
    Simple TOML parser for basic configs (fallback when cptoml not available)
    
    Supports:
    - key = value
    - [section]
    - [section.subsection]
    - Comments (#)
    - Strings, numbers, booleans
    
    Does NOT support:
    - Arrays
    - Inline tables
    - Multi-line strings
    - Datetime
    
    Args:
        filepath: Path to TOML file
    
    Returns:
        dict: Parsed configuration
    """
    config = {}
    current_section = config
    section_path = []
    
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Section header
            if line.startswith('[') and line.endswith(']'):
                section_name = line[1:-1].strip()
                section_path = section_name.split('.')
                
                # Navigate to section, creating nested dicts as needed
                current_section = config
                for part in section_path:
                    if part not in current_section:
                        current_section[part] = {}
                    current_section = current_section[part]
                continue
            
            # Key-value pair
            if '=' in line:
                # Split on first =
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Parse value (handles quotes and comments properly)
                parsed_value = parse_toml_value(value)
                current_section[key] = parsed_value
    
    return config


def parse_toml_value(value):
    """
    Parse a TOML value string
    
    Args:
        value: String representation of value
    
    Returns:
        Parsed value (str, int, float, bool)
    """
    value = value.strip()
    
    # Remove inline comments (but not inside quotes)
    if '#' in value:
        # Check if # is outside quotes
        in_quotes = False
        quote_char = None
        for i, char in enumerate(value):
            if char in ('"', "'") and (i == 0 or value[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            elif char == '#' and not in_quotes:
                # Found comment outside quotes
                value = value[:i].strip()
                break
    
    # String (quoted)
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        # Remove quotes and return content
        return value[1:-1]
    
    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    
    # Integer
    try:
        if '.' not in value:
            return int(value)
    except ValueError:
        pass
    
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    
    # Fallback to string (unquoted)
    return value


# Global hardware config instance
hw_config = load_hardware_config()


# Convenience functions
def is_enabled(peripheral_path):
    """Check if peripheral is enabled"""
    return hw_config.is_enabled(peripheral_path)

def get_pin(pin_path):
    """Get board pin"""
    return hw_config.get_pin(pin_path)

def get_config(path, default=None):
    """Get config value"""
    return hw_config.get(path, default)
