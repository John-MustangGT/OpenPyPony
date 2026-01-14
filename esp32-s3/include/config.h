// include/config.h
// Configuration management for OpenPonyLogger
// Based on CircuitPython config.py

#pragma once

#include <Arduino.h>
#include <map>
#include <string>

namespace OpenPony {

// Configuration class - stores runtime configuration
class Config {
public:
    Config();
    ~Config() = default;

    // Load configuration from SD card (settings.toml)
    bool load(const char* filepath = "/sd/settings.toml");

    // Save configuration to SD card
    bool save(const char* filepath = "/sd/settings.toml");

    // Get configuration values with defaults
    String getString(const char* key, const char* defaultValue = "") const;
    int getInt(const char* key, int defaultValue = 0) const;
    float getFloat(const char* key, float defaultValue = 0.0f) const;
    bool getBool(const char* key, bool defaultValue = false) const;

    // Set configuration values
    void set(const char* key, const String& value);
    void set(const char* key, int value);
    void set(const char* key, float value);
    void set(const char* key, bool value);

    // Check if key exists
    bool has(const char* key) const;

private:
    std::map<String, String> config_;
    void setDefaults();
};

// Default configuration values (matches CircuitPython config.py)
struct DefaultConfig {
    // Logging
    static constexpr bool LOG_ENABLED = true;
    static constexpr const char* LOG_FORMAT = "binary";  // "binary" or "csv"

    // Display
    static constexpr bool DISPLAY_ENABLED = true;
    static constexpr float DISPLAY_UPDATE_RATE = 5.0f;  // Hz

    // GPS
    static constexpr bool GPS_ENABLED = true;
    static constexpr const char* GPS_TYPE = "PA1010D";   // PA1010D (I2C) or ATGM336H (UART)
    static constexpr uint8_t GPS_I2C_ADDRESS = 0x10;
    static constexpr uint16_t GPS_UPDATE_RATE = 1000;    // ms

    // Accelerometer
    static constexpr bool ACCEL_ENABLED = true;
    static constexpr const char* ACCEL_TYPE = "ICM20948";
    static constexpr uint8_t ACCEL_RANGE = 16;           // g
    static constexpr uint16_t ACCEL_SAMPLE_RATE = 100;   // Hz

    // Gyroscope
    static constexpr bool GYRO_ENABLED = true;
    static constexpr uint16_t GYRO_RANGE = 2000;         // dps

    // Magnetometer
    static constexpr bool MAG_ENABLED = true;

    // WiFi
    static constexpr const char* WIFI_MODE = "ap";       // "ap" or "sta"
    static constexpr const char* WIFI_SSID = "OpenPonyLogger";
    static constexpr const char* WIFI_PASSWORD = "mustanggt";
    static constexpr const char* WIFI_AP_IP = "192.168.4.1";

    // WebSocket telemetry
    static constexpr uint16_t TELEMETRY_PORT = 80;
    static constexpr uint16_t TELEMETRY_RATE = 10;       // Hz
    static constexpr uint16_t SATELLITE_DETAILS_INTERVAL = 60;  // seconds

    // BLE (future)
    static constexpr bool BLE_ENABLED = false;
    static constexpr const char* BLE_OBD2_NAME = "vgate icar pro";
};

} // namespace OpenPony
