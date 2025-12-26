# Wiring 

##

| **Device** | **Pin** | **Device** | **Pin** | **Function** |
|---|--|---|---|---|---|
| Pico || STEMMA QT | LIS3A | STEMMA QT | I2C |
| LIS3A || STEMMA QT | OLED | STEMMA QT | I2C |
| Pico | GP0/UART0 TX |  1 | ESP-01 | 7/U0RXD | UART TX -> RX |
| Pico | GP1/UART0 RX |  2 | ESP-01 | 2/U0TXD | UART RX -> TX |
| Pico | GP4/I2C0 SDA | 6 |        |   | If Hardwired I2C SDA |
| Pico | GP5/I2C0 SCL |  7 |        |   | If Hardwired I2C SCL |
| Pico |  9 | GP6 | ESP-01 | 6 | ESP-01 Reset |
| Pico | 10 | GP7 || ATGM331H | PPS | Pulse/Second |
| Pico | 11 | GP8/UART1 TX | ATGM331H | RX | UART TX -> RX |
| Pico | 12 | GP9/UART1 RX | ATGM331H | TX | UART RX -> TX |
| Pico | 29 | GP22 | NeoPixel | Data Input | Control of Light |
| Pico | 36 | 3V3(OUT) | ESP-01   | 8/VCC | 3.3v |
| Pico | 36 | 3V3(OUT) | NeoPixel | 5V DC Power | 3.3v |
| Pico | 36 | 3V3(OUT) | | VCC | On I2C Devices if Hardwired |
| Pico | 38 | GND | ESP-01   | 1/GND | Ground |
| Pico | 38 | GND | NeoPixel | GND | Ground |
| Pico | 38 | GND |  | GND | On I2C Devices if Hardwaired |
