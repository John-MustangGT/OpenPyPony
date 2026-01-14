// src/hardware/feather_battery.cpp
// Adafruit Feather battery monitor implementation

#include "hardware/feather_battery.h"
#include "esp_log.h"
#include "driver/gpio.h"

static const char* TAG = "FeatherBattery";

namespace OpenPony {

FeatherBattery::FeatherBattery()
    : initialized_(false)
{
    last_reading_.voltage = 0.0f;
    last_reading_.percent = 0.0f;
    last_reading_.status = ChargeStatus::UNKNOWN;
    last_reading_.usb_powered = false;
}

FeatherBattery::~FeatherBattery() {
}

bool FeatherBattery::begin() {
    // Configure ADC
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(VBAT_CHANNEL, ADC_ATTEN_DB_11);

    // Characterize ADC
    esp_adc_cal_characterize(
        ADC_UNIT_1,
        ADC_ATTEN_DB_11,
        ADC_WIDTH_BIT_12,
        1100,  // Default Vref
        &adc_chars_
    );

    initialized_ = true;
    ESP_LOGI(TAG, "Battery monitor initialized");
    return true;
}

BatteryInfo FeatherBattery::read() {
    if (!initialized_) {
        return last_reading_;
    }

    // Read ADC multiple times and average
    uint32_t adc_reading = 0;
    const int samples = 10;

    for (int i = 0; i < samples; i++) {
        adc_reading += adc1_get_raw(VBAT_CHANNEL);
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    adc_reading /= samples;

    // Convert to voltage (in mV)
    uint32_t voltage_mv = esp_adc_cal_raw_to_voltage(adc_reading, &adc_chars_);

    // Apply voltage divider ratio to get actual battery voltage
    float voltage = (voltage_mv / 1000.0f) * VOLTAGE_DIVIDER_RATIO;

    // Calculate percentage
    float percent = voltageToPercent(voltage);

    // Determine charge status
    ChargeStatus status;
    if (voltage >= LIPO_MAX_VOLTAGE - 0.05f) {
        status = ChargeStatus::FULL;
    } else if (voltage < LIPO_MIN_VOLTAGE) {
        status = ChargeStatus::LOW;
    } else if (voltage >= 3.9f) {
        status = ChargeStatus::CHARGING; // Likely charging if voltage is high
    } else {
        status = ChargeStatus::DISCHARGING;
    }

    // Check if USB powered (voltage above max indicates charging)
    bool usb_powered = (voltage > LIPO_MAX_VOLTAGE - 0.1f);

    // Update last reading
    last_reading_.voltage = voltage;
    last_reading_.percent = percent;
    last_reading_.status = status;
    last_reading_.usb_powered = usb_powered;

    return last_reading_;
}

float FeatherBattery::getVoltage() {
    BatteryInfo info = read();
    return info.voltage;
}

float FeatherBattery::getPercent() {
    BatteryInfo info = read();
    return info.percent;
}

ChargeStatus FeatherBattery::getStatus() {
    BatteryInfo info = read();
    return info.status;
}

bool FeatherBattery::isUSBPowered() {
    BatteryInfo info = read();
    return info.usb_powered;
}

float FeatherBattery::voltageToPercent(float voltage) {
    // Clamp voltage to valid range
    if (voltage >= LIPO_MAX_VOLTAGE) {
        return 100.0f;
    }
    if (voltage <= LIPO_MIN_VOLTAGE) {
        return 0.0f;
    }

    // LiPo discharge curve approximation (non-linear)
    // This is a simplified 3-point linear interpolation
    // More accurate would be to use a lookup table

    // Voltage points:
    // 4.2V = 100%
    // 3.9V = 75%
    // 3.7V = 50%
    // 3.5V = 25%
    // 3.3V = 0%

    if (voltage >= 3.9f) {
        // 3.9V to 4.2V = 75% to 100%
        return 75.0f + ((voltage - 3.9f) / (LIPO_MAX_VOLTAGE - 3.9f)) * 25.0f;
    } else if (voltage >= 3.7f) {
        // 3.7V to 3.9V = 50% to 75%
        return 50.0f + ((voltage - 3.7f) / 0.2f) * 25.0f;
    } else if (voltage >= 3.5f) {
        // 3.5V to 3.7V = 25% to 50%
        return 25.0f + ((voltage - 3.5f) / 0.2f) * 25.0f;
    } else {
        // 3.3V to 3.5V = 0% to 25%
        return ((voltage - LIPO_MIN_VOLTAGE) / 0.2f) * 25.0f;
    }
}

} // namespace OpenPony
