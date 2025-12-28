"""
hardware.py - Hardware Abstraction Layer

Detects and initializes all hardware based on configuration.
Provides unified interface to access all sensors and peripherals.
"""

import board
import busio
from sensors import (
    LIS3DH, ATGM336H, PCF8523, SSD1306, SDCard,
    NullAccelerometer, NullGPS, NullDisplay
)


class HardwareAbstractionLayer:
    """
    Hardware Abstraction Layer
    
    Detects and initializes all hardware components based on configuration.
    Provides unified access to sensors through abstract interfaces.
    """
    
    def __init__(self, config):
        """
        Initialize HAL
        
        Args:
            config: Config object
        """
        self.config = config
        
        # Hardware references
        self.i2c = None
        self.spi = None
        self.uart = None
        
        # Device references (interfaces)
        self._accelerometer = None
        self._gps = None
        self._rtc = None
        self._display = None
        self._storage = None
        
        # Hardware manifest (what's detected/enabled)
        self.manifest = {
            'board': 'Raspberry Pi Pico 2W',
            'accelerometer': None,
            'gps': None,
            'rtc': None,
            'display': None,
            'storage': None,
            'neopixel': False,
        }
        
        print("\n" + "="*60)
        print("Hardware Abstraction Layer - Initialization")
        print("="*60)
        
        # Initialize buses
        self._init_buses()
        
        # Detect and initialize devices
        self.detect_devices()
        
        print("="*60 + "\n")
    
    def _init_buses(self):
        """Initialize communication buses (I2C, SPI, UART)"""
        print("\n[HAL] Initializing buses...")
        
        # I2C bus (GP8=SDA, GP9=SCL)
        try:
            self.i2c = busio.I2C(board.GP9, board.GP8)
            print("  ✓ I2C initialized (GP9=SCL, GP8=SDA)")
        except Exception as e:
            print(f"  ✗ I2C init failed: {e}")
        
        # SPI bus for SD card (GP18=SCK, GP19=MOSI, GP16=MISO)
        try:
            self.spi = busio.SPI(board.GP18, board.GP19, board.GP16)
            print("  ✓ SPI initialized (GP18=SCK, GP19=MOSI, GP16=MISO)")
        except Exception as e:
            print(f"  ✗ SPI init failed: {e}")
        
        # UART for GPS (GP0=TX, GP1=RX)
        try:
            self.uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=10)
            print("  ✓ UART initialized (GP0=TX, GP1=RX, 9600 baud)")
        except Exception as e:
            print(f"  ✗ UART init failed: {e}")
    
    def detect_devices(self):
        """Detect and initialize all configured devices"""
        print("\n[HAL] Detecting devices...")
        
        # SD Card (required - PiCowbell Adalogger)
        self._init_storage()
        
        # RTC (required - PiCowbell Adalogger PCF8523)
        self._init_rtc()
        
        # Accelerometer (required - LIS3DH)
        self._init_accelerometer()
        
        # GPS (required - ATGM336H)
        self._init_gps()
        
        # Display (optional - SSD1306 OLED)
        self._init_display()
        
        # Print manifest
        self._print_manifest()
    
    def _init_storage(self):
        """Initialize SD card storage"""
        try:
            # CS pin is GP17 for PiCowbell Adalogger
            cs_pin = board.GP17
            
            self._storage = SDCard(self.spi, cs_pin)
            
            if self._storage.mount('/sd'):
                self.manifest['storage'] = 'SD Card (PiCowbell)'
                print("  ✓ SD Card detected and mounted")
            else:
                print("  ✗ SD Card mount failed")
                self._storage = None
                
        except Exception as e:
            print(f"  ✗ SD Card init failed: {e}")
            self._storage = None
    
    def _init_rtc(self):
        """Initialize RTC"""
        if not self.i2c:
            print("  ✗ RTC skipped (no I2C)")
            return
        
        try:
            self._rtc = PCF8523(self.i2c)
            self.manifest['rtc'] = 'PCF8523 (PiCowbell)'
            print("  ✓ RTC detected (PCF8523)")
            
        except Exception as e:
            print(f"  ✗ RTC init failed: {e}")
            self._rtc = None
    
    def _init_accelerometer(self):
        """Initialize accelerometer"""
        if not self.i2c:
            print("  ✗ Accelerometer skipped (no I2C)")
            self._accelerometer = NullAccelerometer()
            return
        
        # Check if enabled in config
        if not self.config.get('sensors.accelerometer.enabled', True):
            print("  - Accelerometer disabled in config")
            self._accelerometer = NullAccelerometer()
            return
        
        try:
            accel_type = self.config.get('sensors.accelerometer.type', 'LIS3DH')
            accel_addr = self.config.get('sensors.accelerometer.address', 0x18)
            
            if accel_type == 'LIS3DH':
                self._accelerometer = LIS3DH(self.i2c, address=accel_addr)
                
                # Configure from settings
                accel_range = self.config.get('sensors.accelerometer.range', 2)
                accel_rate = self.config.get('sensors.accelerometer.sample_rate', 100)
                self._accelerometer.configure(accel_range, accel_rate)
                
                self.manifest['accelerometer'] = f'LIS3DH @0x{accel_addr:02X}'
                print(f"  ✓ Accelerometer detected (LIS3DH @0x{accel_addr:02X})")
            else:
                print(f"  ✗ Unknown accelerometer type: {accel_type}")
                self._accelerometer = NullAccelerometer()
                
        except Exception as e:
            print(f"  ✗ Accelerometer init failed: {e}")
            self._accelerometer = NullAccelerometer()
    
    def _init_gps(self):
        """Initialize GPS"""
        if not self.uart:
            print("  ✗ GPS skipped (no UART)")
            self._gps = NullGPS()
            return
        
        # Check if enabled in config
        if not self.config.get('gps.enabled', True):
            print("  - GPS disabled in config")
            self._gps = NullGPS()
            return
        
        try:
            gps_type = self.config.get('gps.type', 'ATGM336H')
            
            if gps_type == 'ATGM336H':
                self._gps = ATGM336H(self.uart)
                
                # Configure update rate
                gps_rate = self.config.get('gps.update_rate', 1000)
                self._gps.configure_rate(gps_rate)
                
                self.manifest['gps'] = 'ATGM336H (UART)'
                print(f"  ✓ GPS detected (ATGM336H, {1000/gps_rate:.1f}Hz)")
            else:
                print(f"  ✗ Unknown GPS type: {gps_type}")
                self._gps = NullGPS()
                
        except Exception as e:
            print(f"  ✗ GPS init failed: {e}")
            self._gps = NullGPS()
    
    def _init_display(self):
        """Initialize optional OLED display"""
        if not self.i2c:
            print("  - Display skipped (no I2C)")
            self._display = NullDisplay()
            return
        
        try:
            # Try to detect SSD1306 at 0x3C
            self._display = SSD1306(self.i2c, width=128, height=64, address=0x3C)
            self.manifest['display'] = 'SSD1306 128x64 @0x3C'
            print("  ✓ Display detected (SSD1306 128x64)")
            
        except Exception as e:
            print("  - Display not detected (optional)")
            self._display = NullDisplay()
    
    def _print_manifest(self):
        """Print hardware manifest"""
        print("\n[HAL] Hardware Manifest:")
        print("-"*60)
        
        for device, info in self.manifest.items():
            if info:
                status = "✓"
                value = info
            else:
                status = "✗"
                value = "Not detected"
            
            print(f"  {status} {device:20s}: {value}")
        
        print("-"*60)
    
    # =========================================================================
    # Public Interface - Device Accessors
    # =========================================================================
    
    def get_accelerometer(self):
        """
        Get accelerometer interface
        
        Returns:
            AccelerometerInterface (may be NullAccelerometer if disabled)
        """
        return self._accelerometer
    
    def get_gps(self):
        """
        Get GPS interface
        
        Returns:
            GPSInterface (may be NullGPS if disabled)
        """
        return self._gps
    
    def get_rtc(self):
        """
        Get RTC interface
        
        Returns:
            RTCInterface or None
        """
        return self._rtc
    
    def get_display(self):
        """
        Get display interface
        
        Returns:
            DisplayInterface (may be NullDisplay if not present)
        """
        return self._display
    
    def get_storage(self):
        """
        Get storage interface
        
        Returns:
            StorageInterface or None
        """
        return self._storage
    
    def has_accelerometer(self):
        """Check if real accelerometer available"""
        return not isinstance(self._accelerometer, NullAccelerometer)
    
    def has_gps(self):
        """Check if real GPS available"""
        return not isinstance(self._gps, NullGPS)
    
    def has_rtc(self):
        """Check if RTC available"""
        return self._rtc is not None
    
    def has_display(self):
        """Check if real display available"""
        return not isinstance(self._display, NullDisplay)
    
    def has_storage(self):
        """Check if storage available"""
        return self._storage is not None and self._storage.is_mounted()
    
    def get_manifest(self):
        """
        Get hardware manifest dictionary
        
        Returns:
            dict: Hardware manifest
        """
        return self.manifest.copy()
