# Bill of Materials (BOM)
## Base Hardware
This is the minium required for basic functionality. 

| **Item** | **Source** | **Description** | **Price** | **Notes** |
|----------|------------|-----------------|-----------|-----------|
| Core Controler | Adafruit | [Raspberry Pi Pico 2W w/ Header](https://www.adafruit.com/product/6315) | $8 | |
| RTC/SD/STEMMA QT | Adafruit | [Adafruit PiCowbell Adalogger for Pico](https://www.adafruit.com/product/6355) | $8 | |
| Accelerometer | Adafruit | [Adafruit LIS3DH Triple-Axis Accelerometer](https://www.adafruit.com/product/2809) | $5 | |
| GPS | Amazon | [ATGM336H GPS+BDS](https://a.co/d/deHz62V) | $19 | 2 Pack |
| I2C Wire | Amazon | [Stemma QT Wire](https://a.co/d/aZcuxtA) | $10 | |
| Battery | Amazon | [CR1220 Lithium Button Cell](https://a.co/d/gfTqBbn) | $5 | |
|  |  | **Total** | $55 | |

## Add-ons/Upgrades
None of these are *required* for the logger to work. Just makes it **better**.  I have tested these devices. 

| **Item** | **Source** | **Description** | **Price** | **Notes** |
|----------|------------|-----------------|-----------|-----------|
| AP/Webserver | Amazon | [ESP-01s Wifi Transceiver](https://a.co/d/bhfUw6T) | $10 | Live data view, and session management (5 pack) |
| ESP-01 Programmer | Amazon | [ESP-01 Programmer USB](https://a.co/d/1xvccZ6) | $9 | Not used in the device (2 pack) |
| Display | Adafruit | [Monochrome 0.96" 128x64 OLED Display](https://www.adafruit.com/product/326) | $18 | STEMA QT version |
| Display | Amazon | [0.96" OLED 128x64 Display Module](https://a.co/d/gzruQRj) | $13 | DIY Version (5 pack) |
| Lights | Adafruit | [NeoPixel Jewel](https://www.adafruit.com/product/2226) | $6 | Some status dazzle |
| GPS Antenna | Amazon | [SMA GPS Antenna](https://a.co/d/cPT4l4I) | $8 | Much better antenna |
| u.fl pigtail | Amazon | [U.FL to SMA cable](https://a.co/d/cPT4l4I) | $10 | Needed to hook up the antenna (5 pack) | 

## Future
These are things I've not yet checked that they work but should with no or minor changes.  Some of these I have not even bought yet. 
 
| **Item** | **Source** | **Description** | **Price** | **Notes** |
|----------|------------|-----------------|-----------|-----------|
| GPS | Adafruit | [Mini GPS PA1010D](https://www.adafruit.com/product/4415) | $30 | Hook it up with the UART |
| Accelerometer + Gyro | Adafruit | [LSSM6DSOX](https://www.adafruit.com/product/4438) | $12 | No Gyro logging | 
| CAN Bus | Adafruit | [PiCowbell CAN Bus](https://www.adafruit.com/product/5728) | $13 | Future |
| AP/Webserver | Adafruit | [ESP32 Feather V2](https://www.adafruit.com/product/5900) | $21 | Replacement for ESP-01 |
| AP/Webserver | Adafruit | [ESP32-S3 Reverse Feather](https://www.adafruit.com/product/5691) | $25 | Replacement for ESP-01 with Display |
| ODB-II | Amazon | [Vgate iCar Pro Bluetooth 4.0](https://a.co/d/dlr0cjr) | $32 | **Next up for intergration** |
