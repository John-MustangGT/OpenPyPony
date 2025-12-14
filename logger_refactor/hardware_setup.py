"""
hardware_setup.py - Hardware setup for OpenPonyLogger
"""

import board
import busio
import digitalio
import neopixel
import adafruit_lis3dh
import adafruit_gps
import displayio
import i2cdisplaybus
import adafruit_displayio_ssd1306
import storage
import sdcardio
import rtc

print("OpenPonyLogger v2.1 - Initializing...")

# Heartbeat LED (GP25)
heartbeat = digitalio.DigitalInOut(board.LED)
heartbeat.direction = digitalio.Direction.OUTPUT
heartbeat.value = False

# NeoPixel Jewel (GP22)
pixel = neopixel.NeoPixel(board.GP22, 7, brightness=0.3, auto_write=False)

# I2C (Accelerometer + OLED)
i2c = board.STEMMA_I2C()

# LIS3DH Accelerometer
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x18)
lis3dh.range = adafruit_lis3dh.RANGE_2_G
lis3dh.data_rate = adafruit_lis3dh.DATARATE_100_HZ

# GPS (UART)
gps_uart = busio.UART(board.GP8, board.GP9, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(gps_uart, debug=False)
gps.send_command(b'PMTK314,0,1,0,1,0,5,0,0,0,0,0,0,0,0,0,0,0,0,0')  # GGA + RMC + GSV
gps.send_command(b'PMTK220,1000')  # 1Hz update

# SD Card
spi = busio.SPI(board.GP18, board.GP19, board.GP16)
sdcard = sdcardio.SDCard(spi, board.GP17)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# OLED Display
displayio.release_displays()
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# UART to ESP-01S (SoftwareSerial compatible)
esp_uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0.1)

# RTC
rtc_clock = rtc.RTC()

print("✓ Hardware initialized")
