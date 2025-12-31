"""
hardware.py - Hardware Abstraction Layer

Detects and initializes all hardware based on configuration.
Provides unified interface to access all sensors and peripherals.

Pin Assignments:
  GP0/GP1   - ESP-01 UART (TX/RX) - Reserved for future ESP-01 integration
  GP4/GP5   - I2C STEMMA QT (SDA/SCL) - Accelerometer, RTC, OLED
  GP6       - ESP-01 Reset - Reserved for future ESP-01 integration  
  GP7       - GPS PPS (Pulse Per Second) - Reserved for future use
  GP8/GP9   - GPS UART (TX/RX) - ATGM336H GPS module
  GP16-GP19 - SPI (MISO/CS/SCK/MOSI) - SD Card on PiCowbell Adalogger
  GP22      - NeoPixel Jewel - Reserved for future LED integration
"""

import board
import busio
import digitalio
import time
from sensors import (
    LIS3DH, ATGM336H, PCF8523, SSD1306, SDCard, ESP01, MPU6050, ICM20948,
    NullAccelerometer, NullGPS, NullDisplay, NullGyroscope, NullMagnetometer
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
        self.uart_gps = None
        self.uart_esp = None

        # Device references (interfaces)
        self._accelerometer = None
        self._gyroscope = None
        self._magnetometer = None
        self._gps = None
        self._rtc = None
        self._display = None
        self._storage = None
        self._webserver = None

        # Hardware manifest (what's detected/enabled)
        self.manifest = {
            'board': 'Raspberry Pi Pico 2W',
            'accelerometer': None,
            'gyroscope': None,
            'magnetometer': None,
            'gps': None,
            'rtc': None,
            'display': None,
            'storage': None,
            'webserver': None,
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
        
        # Release any existing displays that might hold I2C
        try:
            import displayio
            displayio.release_displays()
        except:
            pass
        
        # I2C bus - STEMMA QT (GP4=SDA, GP5=SCL)
        try:
            # Try to create I2C bus
            self.i2c = busio.I2C(board.GP5, board.GP4)
            
            # Wait for lock
            while not self.i2c.try_lock():
                pass
            
            # Scan for devices
            devices = self.i2c.scan()
            self.i2c.unlock()
            
            print(f"  ✓ I2C initialized (GP5=SCL, GP4=SDA) [STEMMA QT]")
            if devices:
                print(f"    Found {len(devices)} device(s): {[hex(d) for d in devices]}")
            else:
                print(f"    No I2C devices detected")
                
        except ValueError as e:
            print(f"  ✗ I2C init failed: {e}")
            print(f"    Hint: Check if another device is using GP4/GP5")
            self.i2c = None
        except Exception as e:
            print(f"  ✗ I2C init failed: {e}")
            self.i2c = None
        
        # SPI bus for SD card (GP18=SCK, GP19=MOSI, GP16=MISO)
        try:
            self.spi = busio.SPI(board.GP18, board.GP19, board.GP16)
            print("  ✓ SPI initialized (GP18=SCK, GP19=MOSI, GP16=MISO)")
        except Exception as e:
            print(f"  ✗ SPI init failed: {e}")

        # UART0 for ESP-01 (GP0=TX, GP1=RX)
        # Note: Use 9600 baud for debug mode (ESP on GPIO2/0), 115200 for normal mode (ESP on GPIO1/3)
        esp_baudrate = self.config.get('webserver.baudrate', 115200)  # Default to debug mode
        try:
            # Explicitly configure for 8N1 (8 data bits, no parity, 1 stop bit)
            self.uart_esp = busio.UART(board.GP0, board.GP1, baudrate=esp_baudrate,
                                       bits=8, parity=None, stop=1, timeout=0.1)
            print(f"  ✓ UART0 initialized (GP0=TX, GP1=RX, {esp_baudrate} baud, 8N1) [ESP-01]")
        except Exception as e:
            print(f"  ✗ UART0 init failed: {e}")

        # UART1 for GPS (GP8=TX, GP9=RX)
        try:
            self.uart_gps = busio.UART(board.GP8, board.GP9, baudrate=9600, timeout=10)
            print("  ✓ UART1 initialized (GP8=TX, GP9=RX, 9600 baud) [GPS]")
        except Exception as e:
            print(f"  ✗ UART1 init failed: {e}")
    
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

        # Web server (optional - ESP-01)
        self._init_webserver()

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
            self._magnetometer = NullMagnetometer()
            return

        # Check if enabled in config
        if not self.config.get('sensors.accelerometer.enabled', True):
            print("  - Accelerometer disabled in config")
            self._accelerometer = NullAccelerometer()
            self._magnetometer = NullMagnetometer()
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

                # LIS3DH doesn't have gyroscope or magnetometer
                self._magnetometer = NullMagnetometer()

                self.manifest['accelerometer'] = f'LIS3DH @0x{accel_addr:02X}'
                print(f"  ✓ Accelerometer detected (LIS3DH @0x{accel_addr:02X})")

            elif accel_type == 'MPU6050':
                # MPU6050 provides both accelerometer and gyroscope
                self._accelerometer = MPU6050(self.i2c, address=accel_addr)

                # Configure from settings
                accel_range = self.config.get('sensors.accelerometer.range', 2)
                accel_rate = self.config.get('sensors.accelerometer.sample_rate', 100)
                self._accelerometer.configure(accel_range, accel_rate)

                # Also configure gyroscope if enabled
                if self.config.get('sensors.gyroscope.enabled', True):
                    gyro_range = self.config.get('sensors.gyroscope.range', 250)
                    self._accelerometer.configure_gyro(gyro_range)
                    self._gyroscope = self._accelerometer  # Share the same MPU6050 instance
                    self.manifest['gyroscope'] = f'MPU6050 @0x{accel_addr:02X}'
                    print(f"  ✓ Gyroscope detected (MPU6050 @0x{accel_addr:02X})")

                # MPU6050 doesn't have magnetometer
                self._magnetometer = NullMagnetometer()

                self.manifest['accelerometer'] = f'MPU6050 @0x{accel_addr:02X}'
                print(f"  ✓ Accelerometer detected (MPU6050 @0x{accel_addr:02X})")

            elif accel_type == 'ICM20948':
                # ICM-20948 provides accelerometer, gyroscope, and magnetometer
                self._accelerometer = ICM20948(self.i2c, address=accel_addr)

                # Configure from settings
                accel_range = self.config.get('sensors.accelerometer.range', 2)
                accel_rate = self.config.get('sensors.accelerometer.sample_rate', 100)
                self._accelerometer.configure(accel_range, accel_rate)

                # Also configure gyroscope if enabled
                if self.config.get('sensors.gyroscope.enabled', True):
                    gyro_range = self.config.get('sensors.gyroscope.range', 250)
                    self._accelerometer.configure_gyro(gyro_range)
                    self._gyroscope = self._accelerometer  # Share the same ICM20948 instance
                    self.manifest['gyroscope'] = f'ICM20948 @0x{accel_addr:02X}'
                    print(f"  ✓ Gyroscope detected (ICM20948 @0x{accel_addr:02X})")

                # Also configure magnetometer if enabled
                if self.config.get('sensors.magnetometer.enabled', True):
                    self._accelerometer.configure_magnetometer()
                    self._magnetometer = self._accelerometer  # Share the same ICM20948 instance
                    self.manifest['magnetometer'] = f'ICM20948 @0x{accel_addr:02X}'
                    print(f"  ✓ Magnetometer detected (ICM20948 @0x{accel_addr:02X})")
                else:
                    self._magnetometer = NullMagnetometer()

                self.manifest['accelerometer'] = f'ICM20948 @0x{accel_addr:02X}'
                print(f"  ✓ Accelerometer detected (ICM20948 @0x{accel_addr:02X})")

            else:
                print(f"  ✗ Unknown accelerometer type: {accel_type}")
                self._accelerometer = NullAccelerometer()
                self._magnetometer = NullMagnetometer()

        except Exception as e:
            print(f"  ✗ Accelerometer init failed: {e}")
            import traceback
            traceback.print_exception(e)
            self._accelerometer = NullAccelerometer()
            self._magnetometer = NullMagnetometer()
    
    def _init_gps(self):
        """Initialize GPS"""
        if not self.uart_gps:
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
                self._gps = ATGM336H(self.uart_gps)

                # Configure update rate
                gps_rate = self.config.get('gps.update_rate', 1000)
                self._gps.configure_rate(gps_rate)

                self.manifest['gps'] = 'ATGM336H (UART1)'
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

    def _init_webserver(self):
        """Initialize optional ESP-01 web server"""
        if not self.uart_esp:
            print("  - Web server skipped (no UART)")
            self._webserver = None
            return

        # Check if enabled in config
        if not self.config.get('webserver.enabled', False):
            print("  - Web server disabled in config")
            self._webserver = None
            return

        try:
            # Create ESP-01 instance with reset pin
            reset_pin = digitalio.DigitalInOut(board.GP6)
            self._webserver = ESP01(self.uart_esp, reset_pin, debug=False)

            # Reset the ESP (waits for sync marker internally)
            self._webserver.reset()

            # Wait for config request
            print("  [ESP01] Waiting for config request...")
            timeout = 5  # seconds
            start = time.monotonic()

            while time.monotonic() - start < timeout:
                req_type, req_data = self._webserver.update()
                if req_type == 'config_request':
                    # Send configuration
                    config = {
                        'mode': self.config.get('webserver.mode', 'ap'),
                        'ssid': self.config.get('webserver.ssid', 'OpenPonyLogger'),
                        'password': self.config.get('webserver.password', 'mustanggt'),
                        'address': self.config.get('webserver.address', '192.168.4.1'),
                        'netmask': self.config.get('webserver.netmask', '255.255.255.0'),
                        'gateway': self.config.get('webserver.gateway', '192.168.4.1')
                    }
                    self._webserver.send_config(config)

                    # Wait for serving confirmation
                    serving_timeout = 10
                    serving_start = time.monotonic()
                    while time.monotonic() - serving_start < serving_timeout:
                        req_type, req_data = self._webserver.update()
                        if self._webserver.is_ready():
                            self.manifest['webserver'] = f"ESP-01 ({config['mode'].upper()} mode)"
                            print(f"  ✓ Web server ready (ESP-01, {config['ssid']})")
                            return
                        time.sleep(0.1)

                    print("  ✗ Web server timeout waiting for serving")
                    self._webserver = None
                    return

                time.sleep(0.1)

            print("  ✗ Web server timeout waiting for config request")
            self._webserver = None

        except Exception as e:
            print(f"  - Web server init failed: {e}")
            self._webserver = None

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

    def get_webserver(self):
        """
        Get web server interface

        Returns:
            WebServerInterface or None
        """
        return self._webserver

    def get_gyroscope(self):
        """
        Get gyroscope interface

        Returns:
            GyroscopeInterface (may be NullGyroscope if disabled)
        """
        return self._gyroscope

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

    def has_webserver(self):
        """Check if web server available"""
        return self._webserver is not None and self._webserver.is_ready()

    def has_gyroscope(self):
        """Check if real gyroscope available"""
        return self._gyroscope is not None and not isinstance(self._gyroscope, NullGyroscope)

    def get_manifest(self):
        """
        Get hardware manifest dictionary
        
        Returns:
            dict: Hardware manifest
        """
        return self.manifest.copy()
