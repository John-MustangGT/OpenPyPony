"""
gps.py - GPS and Satellite Tracker for OpenPonyLogger
"""

import time
import json

class SatelliteTracker:
    """Track GPS satellites from GSV sentences"""
    
    def __init__(self):
        self.satellites = {}
        self.last_update = 0
    
    def update(self, gps_obj):
        """Update satellite data from GPS"""
        # Note: adafruit_gps doesn't expose GSV data directly
        # We'll need to parse it manually or use available data
        # For now, create mock satellite data based on signal
        
        if gps_obj.satellites and gps_obj.satellites > 0:
            # Generate approximate satellite data
            self.satellites = {}
            for i in range(min(gps_obj.satellites, 12)):
                self.satellites[i+1] = {
                    "id": i + 1,
                    "elevation": 30 + (i * 5) % 60,
                    "azimuth": (i * 30) % 360,
                    "snr": 25 + (i * 3) % 30
                }
            self.last_update = time.monotonic()
    
    def get_json(self):
        """Get satellites as JSON"""
        return {
            "type": "satellites",
            "count": len(self.satellites),
            "satellites": list(self.satellites.values())
        }

class GPS:
    def __init__(self, gps_hardware):
        self.gps = gps_hardware
        self.sat_tracker = SatelliteTracker()

    def update(self):
        self.gps.update()
        self.sat_tracker.update(self.gps)

    def read(self):
        """Read GPS data"""
        lat = self.gps.latitude if self.gps.has_fix else 0.0
        lon = self.gps.longitude if self.gps.has_fix else 0.0
        alt = self.gps.altitude_m if self.gps.altitude_m else 0.0
        speed_knots = self.gps.speed_knots if self.gps.speed_knots else 0.0
        speed_mph = speed_knots * 1.15078  # Convert knots to MPH
        sats = self.gps.satellites if self.gps.satellites else 0
        hdop = self.gps.hdop if self.gps.hdop else 0.0
        
        # Determine fix type
        if not self.gps.has_fix:
            fix_type = "NoFix"
        elif self.gps.fix_quality_3d:
            fix_type = "3D"
        else:
            fix_type = "2D"
            
        return {
            "fix": fix_type,
            "lat": round(lat, 6) if lat else 0,
            "lon": round(lon, 6) if lon else 0,
            "alt": round(alt, 1),
            "speed": round(speed_mph, 1),
            "sats": sats,
            "hdop": round(hdop, 1)
        }

    def get_satellites_json(self):
        return self.sat_tracker.get_json()
