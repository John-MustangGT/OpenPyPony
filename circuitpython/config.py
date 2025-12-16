"""
config.py - Configuration parser for OpenPonyLogger
"""

class Config:
    def __init__(self, filepath="settings.toml"):
        self.settings = {}
        self.load(filepath)

    def load(self, filepath):
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        self.settings[key] = value
        except OSError as e:
            print(f"Error loading settings file: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def get_int(self, key, default=0):
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_float(self, key, default=0.0):
        try:
            return float(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key, default=False):
        value = self.get(key, str(default)).lower()
        return value == "true"

config = Config("/settings.toml")
