// src/config.cpp
// Configuration management implementation (stub for ESP-IDF)

#include "config.h"
#include "esp_log.h"
#include <cstring>

static const char* TAG = "Config";

namespace OpenPony {

Config::Config() {
    setDefaults();
}

bool Config::load(const char* filepath) {
    ESP_LOGI(TAG, "Config load (stub): %s", filepath);
    // For now, just use defaults
    return true;
}

bool Config::save(const char* filepath) {
    ESP_LOGI(TAG, "Config save (stub): %s", filepath);
    return true;
}

std::string Config::getString(const char* key, const char* defaultValue) const {
    auto it = config_.find(key);
    if (it != config_.end()) {
        return it->second;
    }
    return std::string(defaultValue);
}

int Config::getInt(const char* key, int defaultValue) const {
    auto it = config_.find(key);
    if (it != config_.end()) {
        return atoi(it->second.c_str());
    }
    return defaultValue;
}

float Config::getFloat(const char* key, float defaultValue) const {
    auto it = config_.find(key);
    if (it != config_.end()) {
        return atof(it->second.c_str());
    }
    return defaultValue;
}

bool Config::getBool(const char* key, bool defaultValue) const {
    auto it = config_.find(key);
    if (it != config_.end()) {
        return it->second == "true" || it->second == "1";
    }
    return defaultValue;
}

void Config::set(const char* key, const std::string& value) {
    config_[key] = value;
}

void Config::set(const char* key, int value) {
    config_[key] = std::to_string(value);
}

void Config::set(const char* key, float value) {
    config_[key] = std::to_string(value);
}

void Config::set(const char* key, bool value) {
    config_[key] = value ? "true" : "false";
}

bool Config::has(const char* key) const {
    return config_.find(key) != config_.end();
}

void Config::setDefaults() {
    // Set defaults from DefaultConfig
    config_["log.enabled"] = "true";
    config_["log.format"] = "binary";
    config_["display.enabled"] = "true";
    config_["display.update_rate"] = "5.0";
    config_["gps.enabled"] = "true";
    config_["gps.type"] = "PA1010D";
    config_["gps.update_rate"] = "1000";
    config_["telemetry.port"] = "80";
    config_["telemetry.rate"] = "10";
    config_["telemetry.satellite_details_interval"] = "60";
    // Hardware: default STEMMA I2C power pin for Adafruit Feather Reverse TFT
    // Many Feather variants expose a power enable pin for the STEMMA connector (vsensor/TFT_I2C_POWER)
    // Default to GPIO2 which is the Feather's VSENSOR/I2C power control on some boards.
    config_["hardware.stemma_power_pin"] = "2";
}

} // namespace OpenPony
