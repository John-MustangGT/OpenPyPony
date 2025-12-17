"""
hardware_setup.py - Hardware setup for OpenPonyLogger

Reads hardware.toml and initializes all configured peripherals.
"""

import board
import busio
import digitalio
import storage
import sdcardio
import rtc
import time
import json
from hardware_config import hw_config

print("OpenPonyLogger v2.1 - Initializing...")

# Dictionary to store initialized hardware
hardware = {}

# =============================================================================
# Heartbeat LED
# =============================================================================

if hw_config.is_enabled("indicators.heartbeat_led"):
    try:
        heartbeat_pin = hw_config.get_pin("indicators.heartbeat_led.pin")
        if heartbeat_pin:
            heartbeat = digitalio.DigitalInOut(heartbeat_pin)
            heartbeat.direction = digitalio.Direction.OUTPUT
            heartbeat.value = False
            hardware['heartbeat'] = heartbeat
            print("✓ Heartbeat LED initialized")
    except Exception as e:
        print(f"✗ Heartbeat LED error: {e}")

# =============================================================================
# NeoPixel Jewel
# =============================================================================

if hw_config.is_enabled("indicators.neopixel_jewel"):
    try:
        import neopixel
        
        pixel_pin = hw_config.get_pin("indicators.neopixel_jewel.pin")
        num_pixels = hw_config.get_int("indicators.neopixel_jewel.num_pixels", 7)
        brightness = hw_config.get_float("indicators.neopixel_jewel.brightness", 0.3)
        
        if pixel_pin:
            pixel = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=brightness, auto_write=False)
            hardware['neopixel'] = pixel
            print(f"✓ NeoPixel Jewel initialized ({num_pixels} LEDs)")
    except Exception as e:
        print(f"✗ NeoPixel error: {e}")

# =============================================================================
# I2C Interface
# =============================================================================

if hw_config.is_enabled("interfaces.i2c"):
    try:
        i2c_pins = hw_config.get_interface_pins("i2c")
        
        # Use STEMMA_I2C() for default pins
        sda_str = hw_config.get("interfaces.i2c.sda")
        if sda_str == "GP4" or sda_str == "STEMMA_I2C":
            i2c = board.STEMMA_I2C()
        else:
            sda = i2c_pins.get('sda')
            scl = i2c_pins.get('scl')
            frequency = i2c_pins.get('frequency', 100000)
            
            # Verify pins are actual Pin objects
            if sda is None or scl is None:
                raise ValueError(f"Invalid I2C pins: SDA={sda}, SCL={scl}")
            
            i2c = busio.I2C(scl, sda, frequency=frequency)
        
        hardware['i2c'] = i2c
        print("✓ I2C initialized")
    except Exception as e:
        print(f"✗ I2C error: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        hardware['i2c'] = None

# =============================================================================
# Accelerometer
# =============================================================================

if hw_config.is_enabled("sensors.accelerometer") and hardware.get('i2c'):
    try:
        import adafruit_lis3dh
        
        accel_type = hw_config.get("sensors.accelerometer.type", "LIS3DH")
        accel_addr = hw_config.get_int("sensors.accelerometer.address", 0x18)
        
        if accel_type.upper() == "LIS3DH":
            lis3dh = adafruit_lis3dh.LIS3DH_I2C(hardware['i2c'], address=accel_addr)
            
            # Configure range
            accel_range = hw_config.get_int("sensors.accelerometer.range", 2)
            if accel_range == 4:
                lis3dh.range = adafruit_lis3dh.RANGE_4_G
            elif accel_range == 8:
                lis3dh.range = adafruit_lis3dh.RANGE_8_G
            elif accel_range == 16:
                lis3dh.range = adafruit_lis3dh.RANGE_16_G
            else:
                lis3dh.range = adafruit_lis3dh.RANGE_2_G
            
            # Configure sample rate
            sample_rate = hw_config.get_int("sensors.accelerometer.sample_rate", 100)
            if sample_rate == 10:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_10_HZ
            elif sample_rate == 25:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_25_HZ
            elif sample_rate == 50:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_50_HZ
            elif sample_rate == 200:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_200_HZ
            elif sample_rate == 400:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_400_HZ
            else:
                lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ
            
            hardware['accelerometer'] = lis3dh
            print(f"✓ {accel_type} initialized (±{accel_range}g @ {sample_rate}Hz)")
    except Exception as e:
        print(f"✗ Accelerometer error: {e}")

# =============================================================================
# GPS Module
# =============================================================================

if hw_config.is_enabled("gps"):
    try:
        import adafruit_gps
        
        # Get UART interface
        uart_name = hw_config.get("gps.interface", "uart_gps")
        uart_config = hw_config.get_interface_pins(uart_name)
        
        if uart_config:
            tx_pin = uart_config.get('tx')
            rx_pin = uart_config.get('rx')
            baudrate = uart_config.get('baudrate', 9600)
            timeout = uart_config.get('timeout', 10)
            
            gps_uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate, timeout=timeout)
            gps = adafruit_gps.GPS(gps_uart, debug=False)
            
            # Configure sentences
            sentences = hw_config.get("gps.sentences", "0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0")
            gps.send_command(f'PMTK314,{sentences}'.encode())
            
            # Configure update rate
            update_rate = hw_config.get_int("gps.update_rate", 1000)
            gps.send_command(f'PMTK220,{update_rate}'.encode())
            
            hardware['gps'] = gps
            hardware['gps_uart'] = gps_uart
            
            gps_type = hw_config.get("gps.type", "GPS")
            print(f"✓ {gps_type} initialized ({update_rate}ms update)")
    except Exception as e:
        print(f"✗ GPS error: {e}")

# =============================================================================
# SD Card
# =============================================================================

if hw_config.is_enabled("storage.sdcard"):
    try:
        # Get SPI interface
        spi_config = hw_config.get_interface_pins("spi")
        
        if spi_config:
            sck = spi_config.get('sck')
            mosi = spi_config.get('mosi')
            miso = spi_config.get('miso')
            
            spi = busio.SPI(sck, mosi, miso)
            
            # Get CS pin
            cs_pin = hw_config.get_pin("storage.sdcard.cs_pin")
            
            if cs_pin:
                sdcard = sdcardio.SDCard(spi, cs_pin)
                vfs = storage.VfsFat(sdcard)
                
                mount_point = hw_config.get("storage.sdcard.mount_point", "/sd")
                storage.mount(vfs, mount_point)
                
                hardware['sdcard'] = sdcard
                hardware['spi'] = spi
                print(f"✓ SD card mounted at {mount_point}")
    except Exception as e:
        print(f"✗ SD card error: {e}")

# =============================================================================
# OLED Display
# =============================================================================

if hw_config.is_enabled("display.oled") and hardware.get('i2c'):
    try:
        import displayio
        import i2cdisplaybus
        import adafruit_displayio_ssd1306
        
        displayio.release_displays()
        
        display_addr = hw_config.get_int("display.oled.address", 0x3C)
        width = hw_config.get_int("display.oled.width", 128)
        height = hw_config.get_int("display.oled.height", 64)
        
        display_bus = i2cdisplaybus.I2CDisplayBus(hardware['i2c'], device_address=display_addr)
        display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=width, height=height)
        
        hardware['display'] = display
        hardware['display_bus'] = display_bus
        print(f"✓ OLED display initialized ({width}x{height})")
    except Exception as e:
        print(f"✗ OLED display error: {e}")

# =============================================================================
# ESP-01S Radio
# =============================================================================

if hw_config.is_enabled("radio.esp01s"):
    try:
        # Reset ESP-01s
        reset_pin = hw_config.get_pin("radio.esp01s.reset_pin")
        
        if reset_pin:
            esp_reset = digitalio.DigitalInOut(reset_pin)
            esp_reset.direction = digitalio.Direction.OUTPUT
            esp_reset.value = True
            time.sleep(0.1)
            esp_reset.value = False
            
            reset_duration = hw_config.get_float("radio.esp01s.reset_duration", 0.05)
            time.sleep(reset_duration)
            
            esp_reset.value = True
            print("ESP-01s reset signal sent.")
        
        # Initialize UART
        uart_name = hw_config.get("radio.esp01s.interface", "uart_esp")
        uart_config = hw_config.get_interface_pins(uart_name)
        
        if uart_config:
            tx_pin = uart_config.get('tx')
            rx_pin = uart_config.get('rx')
            baudrate = uart_config.get('baudrate', 115200)
            timeout = uart_config.get('timeout', 0.1)
            
            esp_uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate, timeout=timeout)
            
            # Wait for ready message
            ready_timeout = hw_config.get_float("radio.esp01s.ready_timeout", 5.0)
            start_time = time.monotonic()
            esp_ready = False
            
            while time.monotonic() - start_time < ready_timeout:
                line = esp_uart.readline()
                if line:
                    try:
                        line_str = line.decode('utf-8').strip()
                        if line_str:
                            message = json.loads(line_str)
                            if message.get("type") == "esp_ready":
                                print("ESP-01s is ready.")
                                esp_ready = True
                                break
                    except (ValueError, TypeError, UnicodeError):
                        pass
            
            if not esp_ready:
                print("⚠ ESP-01s did not send ready message in time.")
            
            hardware['esp_uart'] = esp_uart
            hardware['esp_ready'] = esp_ready
    except Exception as e:
        print(f"✗ ESP-01s error: {e}")

# =============================================================================
# Real-Time Clock
# =============================================================================

if hw_config.is_enabled("rtc"):
    try:
        from pcf8523_rtc import setup_rtc
        
        # Get I2C bus if needed for external RTC
        i2c_bus = hardware.get('i2c')
        
        # Setup RTC (handles both builtin and PCF8523)
        rtc_handler = setup_rtc(hw_config, i2c=i2c_bus)
        
        if rtc_handler:
            # PCF8523 handler
            hardware['rtc'] = rtc_handler
            hardware['rtc_type'] = 'pcf8523'
        else:
            # Built-in RTC
            rtc_clock = rtc.RTC()
            hardware['rtc'] = rtc_clock
            hardware['rtc_type'] = 'builtin'
            print("✓ RTC initialized (built-in)")
            
    except Exception as e:
        print(f"✗ RTC error: {e}")
        import traceback
        traceback.print_exc()

# =============================================================================
# Summary
# =============================================================================

print("\n✓ Hardware initialized")
print(f"  Active peripherals: {len(hardware)}")
if hw_config.is_enabled("sensors.accelerometer"):
    print(f"  Accelerometer: {hw_config.get('sensors.accelerometer.type', 'Unknown')}")
if hw_config.is_enabled("gps"):
    print(f"  GPS: {hw_config.get('gps.type', 'Unknown')}")
if hw_config.is_enabled("storage.sdcard"):
    print(f"  Storage: SD card")
if hw_config.is_enabled("display.oled"):
    print(f"  Display: {hw_config.get('display.oled.type', 'Unknown')}")


def get_hardware(name):
    """
    Get initialized hardware peripheral
    
    Args:
        name: Hardware name (e.g., 'accelerometer', 'gps', 'display')
    
    Returns:
        Hardware object or None
    """
    return hardware.get(name)


def list_hardware():
    """List all initialized hardware"""
    return list(hardware.keys())


def get_rtc_handler():
    """
    Get RTC handler
    
    Returns:
        PCF8523Handler if using PCF8523, rtc.RTC if builtin, or None
    """
    return hardware.get('rtc')


def get_rtc_type():
    """
    Get RTC type
    
    Returns:
        str: 'pcf8523', 'builtin', or None
    """
    return hardware.get('rtc_type')


def set_system_time(year, month, day, hour, minute, second):
    """
    Set system time (and optionally sync to RTC)
    
    Args:
        year, month, day, hour, minute, second: Time components
    """
    rtc_handler = get_rtc_handler()
    rtc_type = get_rtc_type()
    
    if rtc_type == 'pcf8523' and rtc_handler:
        # PCF8523 handler has set_time that syncs both
        rtc_handler.set_time(year, month, day, hour, minute, second)
    else:
        # Set built-in RTC directly
        new_time = time.struct_time((
            year, month, day,
            hour, minute, second,
            0, -1, -1
        ))
        rtc.RTC().datetime = new_time
        print(f"[RTC] System time set: {year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")


def get_time_string():
    """
    Get current time as formatted string
    
    Returns:
        str: Time in YYYY-MM-DD HH:MM:SS format
    """
    rtc_handler = get_rtc_handler()
    rtc_type = get_rtc_type()
    
    if rtc_type == 'pcf8523' and rtc_handler:
        return rtc_handler.get_time_string()
    else:
        current = time.localtime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            current.tm_year, current.tm_mon, current.tm_mday,
            current.tm_hour, current.tm_min, current.tm_sec
        )


# =============================================================================
# Direct Exports for Backward Compatibility
# =============================================================================

# Export hardware objects directly for easier access
# These can be imported as: from hardware_setup import lis3dh, gps, display, etc.

lis3dh = hardware.get('accelerometer')      # LIS3DH accelerometer
gps = hardware.get('gps')                   # GPS module
gps_uart = hardware.get('gps_uart')         # GPS UART
display = hardware.get('display')           # OLED display
display_bus = hardware.get('display_bus')   # Display bus
sdcard = hardware.get('sdcard')             # SD card
spi = hardware.get('spi')                   # SPI bus
i2c = hardware.get('i2c')                   # I2C bus
heartbeat = hardware.get('heartbeat')       # Heartbeat LED
pixel = hardware.get('neopixel')            # NeoPixel Jewel
esp_uart = hardware.get('esp_uart')         # ESP-01s UART
esp_ready = hardware.get('esp_ready', False) # ESP ready flag
rtc_clock = hardware.get('rtc')             # RTC
