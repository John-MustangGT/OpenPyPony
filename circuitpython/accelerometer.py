"""
accelerometer.py - LIS3DH Accelerometer Handler
"""

class Accelerometer:
    def __init__(self, lis3dh):
        self.lis3dh = lis3dh

    def read(self):
        """Read accelerometer data"""
        x, y, z = self.lis3dh.acceleration
        gx, gy, gz = x / 9.81, y / 9.81, z / 9.81
        g_total = (gx**2 + gy**2 + gz**2)**0.5
        
        return {
            "x": round(gx, 2),
            "y": round(gy, 2),
            "z": round(gz, 2),
            "total": round(g_total, 2)
        }
