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
            pin_str: Pin string (e.g., "GP25", "STEMMA_I2C")
        
        Returns:
            board.Pin object or None
        """
        if not pin_str:
            return None
        
        # Handle special names
        if pin_str == "STEMMA_I2C":
            return board.STEMMA_I2C()
        
        # Handle GP## format
        if pin_str.startswith("GP"):
            try:
                pin_num = int(pin_str[2:])
                return getattr(board, f"GP{pin_num}")
            except (ValueError, AttributeError):
                return None
        
        # Try direct board attribute
        try:
            return getattr(board, pin_str)
        except AttributeError:
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
            dict: Pin mappings
        """
        base_path = f"interfaces.{interface_name}"
        if not self.is_enabled(base_path):
            return {}
        
        pins = {}
        interface_config = self._get_nested(base_path, {})
        
        for key, value in interface_config.items():
            if key == "enabled":
                continue
            if isinstance(value, str) and (value.startswith("GP") or value == "STEMMA_I2C"):
                pins[key] = self.pin_from_string(value)
            else:
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
    try:
        import toml
        with open(filepath, 'r') as f:
            config_dict = toml.load(f)
        return HardwareConfig(config_dict)
    except ImportError:
        print("[Hardware] Warning: toml module not available")
        print("[Hardware] Install with: circup install circuitpython-toml")
        return HardwareConfig({})
    except Exception as e:
        print(f"[Hardware] Error loading {filepath}: {e}")
        return HardwareConfig({})


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
