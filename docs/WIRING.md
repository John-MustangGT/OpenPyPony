# Wiring 

##

| **Device** | **Name**     | **Pin**   | **Device** | **Pin**     | **Function** |
|------------|--------------|-----------|------------|-------------|--------------|
| Pico       |              | STEMMA QT | LIS3A      | STEMMA QT   | I2C          |
| LIS3A      |              | STEMMA QT | OLED       | STEMMA QT   | I2C          |
| Pico       | GP0/UART0 TX | 1         | ESP-01     | 7/U0RXD     | UART TX -> RX |
| Pico       | GP1/UART0 RX | 2         | ESP-01     | 2/U0TXD     | UART RX -> TX |
| Pico       | GP4/I2C0 SDA | 6         |            |             | If Hardwired I2C SDA |
| Pico       | GP5/I2C0 SCL | 7         |            |             | If Hardwired I2C SCL |
| Pico       | GP6          | 9         | ESP-01     | 6           | ESP-01 Reset |
| Pico       | GP7          | 10        | ATGM331H   | PPS         | Pulse/Second |
| Pico       | GP8/UART1 TX | 11        | ATGM331H   | RX          | UART TX -> RX |
| Pico       | GP9/UART1 RX | 12        | ATGM331H   | TX          | UART RX -> TX |
| Pico       | GP22         | 29        | NeoPixel   | Data Input  | Control of Light |
| Pico       | 3V3(OUT)     | 36        | ESP-01     | 8/VCC       | 3.3v |
| Pico       | 3V3(OUT)     | 36        | NeoPixel   | 5V DC Power | 3.3v |
| Pico       | 3V3(OUT)     | 36        | VCC        |             | On I2C Devices if Hardwired |
| Pico       | GND          | 38        | ESP-01     | 1/GND       | Ground |
| Pico       | GND          | 38        | NeoPixel   | GND         | Ground |
| Pico       | GND          | 38        | GND        |             | On I2C Devices if Hardwired |
