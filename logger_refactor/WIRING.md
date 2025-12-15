# Wiring 

##

| **Device** | **Pin** | **Device** | **Pin** | **Function** |
|---|---|---|---|---|
| Pico | STEMMA QT | LIS3A | STEMMA QT | I2C |
| LIS3A | STEMMA QT | OLED | STEMMA QT | I2C |
| Pico |  1 | ESP-01 | 7/U0RXD | UART TX -> RX |
| Pico |  2 | ESP-01 | 2/U0TXD | UART RX -> TX |
| Pico |  6 |        |   | If Hardwired I2C SDA |
| Pico |  7 |        |   | If Hardwired I2C SCL |
| Pico |  9 | ESP-01 | 6 | ESP-01 Reset |
| Pico | 10 | ATGM331H | PPS | Pulse/Second |
| Pico | 11 | ATGM331H | RX | UART TX -> RX |
| Pico | 12 | ATGM331H | TX | UART RX -> TX |
| Pico | 29 | NeoPixel | Data Input | Control of Light |
| Pico | 29 | NeoPixel | Data Input | Control of Light |
| Pico | 36 | ESP-01   | 8/VCC | 3.3v |
| Pico | 36 | NeoPixel | 5V DC Power | 3.3v |
| Pico | 36 |  | VCC | On I2C Devices if Hardwired |
| Pico | 38 | ESP-01   | 1/GND | Ground |
| Pico | 38 | NeoPixel | GND | Ground |
| Pico | 38 |  | GND | On I2C Devices if Hardwaired |
