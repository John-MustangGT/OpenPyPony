| Physical Pin | GPIO Pin | Function                      | Device/Component                            | Status          |
| :----------- | :------- | :---------------------------- | :------------------------------------------ | :-------------- |
| 1            | GP0      | UART TX                       | ESP-01S                                     | In Use          |
| 2            | GP1      | UART RX                       | ESP-01S                                     | In Use          |
| 3            |          | GND                           | Ground                                      |                 |
| 4            | GP2      | I2C1 SDA                      | I2C1                                        | Reserved        |
| 5            | GP3      | I2C1 SCL                      | I2C1                                        | Reserved        |
| 6            | GP4      | I2C SDA (default `STEMMA_I2C`) | Accelerometer & OLED (shared with CAN bell) | In Use          |
| 7            | GP5      | I2C SCL (default `STEMMA_I2C`) | Accelerometer & OLED (shared with CAN bell) | In Use          |
| 8            |          | GND                           | Ground                                      |                 |
| 9            | GP6      | ESP-01s Reset                 | ESP-01s                                     | In Use          |
| 10           | GP7      | GPS PPS                       | GPS                                         | Reserved        |
| 11           | GP8      | UART TX                       | GPS                                         | In Use          |
| 12           | GP9      | UART RX                       | GPS                                         | In Use          |
| 13           |          | GND                           | Ground                                      |                 |
| 14           | GP10     | SPI1 SCK                      | SPI1                                        | Reserved        |
| 15           | GP11     | SPI1 MOSI                     | SPI1                                        | Reserved        |
| 16           | GP12     | SPI1 MISO                     | SPI1                                        | Reserved        |
| 17           | GP13     | SPI1 CS                       | SPI1                                        | Reserved        |
| 18           |          | GND                           | Ground                                      |                 |
| 19           | GP14     |                               |                                             | Available       |
| 20           | GP15     |                               |                                             | Available       |
| 21           | GP16     | SPI MISO                      | SD Card (shared with CAN bell)              | In Use          |
| 22           | GP17     | SPI CS                        | SD Card                                     | In Use          |
| 23           |          | GND                           | Ground                                      |                 |
| 24           | GP18     | SPI SCK                       | SD Card (shared with CAN bell)              | In Use          |
| 25           | GP19     | SPI MOSI                      | SD Card (shared with CAN bell)              | In Use          |
| 26           | GP20     | SPI CS                        | Adafruit PiCowbell CAN Bus controller       | Reserved        |
| 27           | GP21     | Interrupt                     | Adafruit PiCowbell CAN Bus controller       | Reserved        |
| 28           |          | GND                           | Ground                                      |                 |
| 29           | GP22     | NeoPixel                      | NeoPixel Jewel                              | In Use          |
|              | GP23     | Special Function              | Power Supply Control / WiFi                 | Not Available   |
|              | GP24     | Special Function              | VBUS Sense / WiFi                           | Not Available   |
|              | GP25     | `board.LED`                   | Heartbeat LED                               | In Use          |
| 30           |          | RUN                           | System Reset                                |                 |
| 31           | GP26     | ADC0                          | Analog Input                                | Reserved        |
| 32           | GP27     | ADC1                          | Analog Input                                | Reserved        |
| 33           |          | GND                           | Ground                                      |                 |
| 34           | GP28     | ADC2                          | Analog Input                                | Reserved        |
| 35           |          | ADC_VREF                      | ADC Reference Voltage                       |                 |
| 36           |          | 3V3(OUT)                      | 3.3V Power Output                           |                 |
| 37           |          | 3V3_EN                        | 3.3V Power Enable                           |                 |
| 38           |          | GND                           | Ground                                      |                 |
| 39           |          | VSYS                          | System Input Voltage                        |                 |
| 40           |          | VBUS                          | USB Power Input                             |                 |
