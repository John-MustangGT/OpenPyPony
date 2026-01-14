// include/hardware/feather_battery.h
// Adafruit Feather battery monitor
// Uses ADC to read VBAT pin

#pragma once

#include "interfaces/battery_interface.h"
#include "driver/adc.h"
#include "esp_adc_cal.h"

namespace OpenPony {

// Feather ESP32-S3 battery pins
constexpr gpio_num_t VBAT_PIN = GPIO_NUM_2;  // VBAT ADC pin on Feather ESP32-S3
constexpr adc1_channel_t VBAT_CHANNEL = ADC1_CHANNEL_1;  // GPIO2 = ADC1_CH1

class FeatherBattery : public BatteryInterface {
public:
    FeatherBattery();
    ~FeatherBattery();

    // Initialize ADC
    bool begin();

    // BatteryInterface implementation
    BatteryInfo read() override;
    float getVoltage() override;
    float getPercent() override;
    ChargeStatus getStatus() override;
    bool isUSBPowered() override;

private:
    esp_adc_cal_characteristics_t adc_chars_;
    bool initialized_;

    // Last reading
    BatteryInfo last_reading_;

    // Voltage divider on Feather (typically 2:1)
    static constexpr float VOLTAGE_DIVIDER_RATIO = 2.0f;

    // LiPo voltage range
    static constexpr float LIPO_MAX_VOLTAGE = 4.2f;
    static constexpr float LIPO_MIN_VOLTAGE = 3.3f;

    // Convert voltage to percentage (non-linear LiPo curve approximation)
    float voltageToPercent(float voltage);
};

} // namespace OpenPony
