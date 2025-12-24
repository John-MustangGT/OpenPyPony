"""
neopixel_handler.py - NeoPixel Handler for OpenPonyLogger
"""

import time
import math

class NeoPixelHandler:
    def __init__(self, pixel):
        self.pixel = pixel

    def christmas_tree(self):
        """Startup animation - christmas tree effect"""
        colors = [(255, 191, 0), (255, 191, 0), (255, 191, 0), (0, 255, 0)]
        for c in colors:
            for i in range(7):
                self.pixel[i] = c
                self.pixel.show()
                time.sleep(0.1)
            self.pixel.show()
            time.sleep(0.5)
            self.pixel.fill((0, 0, 0))

    def _g_to_color(self, g_value, max_g=1.5):
        """Map G-force to color: green=accel, red=decel, brightness=magnitude"""
        intensity = min(abs(g_value) / max_g, 1.0)
        if g_value > 0.1:
            return (0, int(255 * intensity), 0)  # Green for positive
        elif g_value < -0.1:
            return (int(255 * intensity), 0, 0)  # Red for negative
        else:
            return (0, 0, 0)  # Standing

    def _tire_load_color(self, gx, gy, position):
        """
        Calculate tire load color based on weight transfer
        Position: 'rf', 'rr', 'lf', 'lr'
        """
        vertical_load = 0.25
        
        if position in ['rf', 'lf']:
            vertical_load += -gy * 0.3
        else:
            vertical_load += gy * 0.3
        
        if position in ['rf', 'rr']:
            vertical_load += -gx * 0.3
        else:
            vertical_load += gx * 0.3
        
        vertical_load = max(0, min(vertical_load, 1.5))
        intensity = abs(vertical_load)
        
        if abs(gx) < 0.1 and abs(gy) < 0.1:
            r, g, b = 0, 0, 0
        elif intensity < 0.5:
            r = 0
            g = int(intensity * 2 * 255)
            b = int((1 - intensity * 2) * 255)
        else:
            r = int((intensity - 0.5) * 2 * 255)
            g = 255
            b = 0
        
        return (r, g, b)

    def update(self, data):
        """
        Update NeoPixel Jewel based on G-force and system status
        """
        gx = data['gx']
        gy = data['gy']
        
        if data['gps_fix'] and data['gps_hdop'] < 2.0:
            status_color = (0, 255, 0)
            breathe = True
        elif data['gps_fix'] and data['gps_hdop'] < 10:
            status_color = (255, 255, 0)
            breathe = False
        else:
            status_color = (255, 0, 0)
            breathe = False
        
        if breathe:
            t = time.monotonic()
            intensity = 0.2 + 0.3 * (1 + math.sin(t / 6 * math.pi))
            self.pixel[0] = tuple(int(c * intensity) for c in status_color)
        else:
            if status_color == (255, 255, 0):
                flash_on = int(time.monotonic() * 2) % 2
                self.pixel[0] = status_color if flash_on else (0, 0, 0)
            else:
                self.pixel[0] = status_color
        
        self.pixel[1] = self._g_to_color(gy)
        self.pixel[2] = self._tire_load_color(gx, gy, 'rf')
        self.pixel[3] = self._tire_load_color(gx, gy, 'rr')
        self.pixel[4] = self._g_to_color(gx)
        self.pixel[5] = self._tire_load_color(gx, gy, 'lr')
        self.pixel[6] = self._tire_load_color(gx, gy, 'lf')
        
        self.pixel.show()
