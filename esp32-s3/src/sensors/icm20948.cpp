// src/sensors/icm20948.cpp
// ICM20948 9-DOF IMU driver implementation

#include "sensors/icm20948.h"
#include "esp_log.h"
#include <cmath>

static const char* TAG = "ICM20948";

namespace OpenPony {

// ICM20948 register banks
constexpr uint8_t BANK_0 = 0x00;
constexpr uint8_t BANK_2 = 0x20;
constexpr uint8_t BANK_3 = 0x30;

// WHO_AM_I expected value
constexpr uint8_t ICM20948_WHO_AM_I_VALUE = 0xEA;

// Power management
constexpr uint8_t PWR_MGMT_1_RESET = 0x80;
constexpr uint8_t PWR_MGMT_1_SLEEP = 0x40;
constexpr uint8_t PWR_MGMT_1_CLKSEL_AUTO = 0x01;

// Accelerometer config
constexpr uint8_t ACCEL_FS_SEL_2G = 0x00;
constexpr uint8_t ACCEL_FS_SEL_4G = 0x02;
constexpr uint8_t ACCEL_FS_SEL_8G = 0x04;
constexpr uint8_t ACCEL_FS_SEL_16G = 0x06;

// Gyroscope config
constexpr uint8_t GYRO_FS_SEL_250DPS = 0x00;
constexpr uint8_t GYRO_FS_SEL_500DPS = 0x02;
constexpr uint8_t GYRO_FS_SEL_1000DPS = 0x04;
constexpr uint8_t GYRO_FS_SEL_2000DPS = 0x06;

// Magnetometer (AK09916) via I2C master
constexpr uint8_t AK09916_ADDRESS = 0x0C;
constexpr uint8_t AK09916_WHO_AM_I = 0x01;
constexpr uint8_t AK09916_CNTL2 = 0x31;
constexpr uint8_t AK09916_CNTL3 = 0x32;
constexpr uint8_t AK09916_HXL = 0x11;
constexpr uint8_t AK09916_MODE_100HZ = 0x08;

ICM20948::ICM20948(i2c_port_t i2c_port, uint8_t address)
    : i2c_port_(i2c_port)
    , address_(address)
    , accel_range_(2)
    , gyro_range_(250)
    , magnetometer_enabled_(false)
    , mag_calibrated_(false)
    , mag_offset_x_(0.0f)
    , mag_offset_y_(0.0f)
    , mag_offset_z_(0.0f)
{
    last_accel_ = {0.0f, 0.0f, 0.0f};
    last_gyro_ = {0.0f, 0.0f, 0.0f};
    last_mag_ = {0.0f, 0.0f, 0.0f};
}

ICM20948::~ICM20948() {
}

bool ICM20948::begin() {
    // Reset the device
    if (!reset()) {
        ESP_LOGE(TAG, "Failed to reset device");
        return false;
    }

    vTaskDelay(pdMS_TO_TICKS(100));

    // Check WHO_AM_I
    if (!checkWhoAmI()) {
        ESP_LOGE(TAG, "WHO_AM_I check failed");
        return false;
    }

    // Wake up the device
    selectBank(BANK_0);
    if (!writeRegister(ICM20948_Reg::PWR_MGMT_1, PWR_MGMT_1_CLKSEL_AUTO)) {
        ESP_LOGE(TAG, "Failed to wake device");
        return false;
    }

    vTaskDelay(pdMS_TO_TICKS(50));

    // Initialize accelerometer
    if (!initAccelerometer()) {
        ESP_LOGE(TAG, "Failed to initialize accelerometer");
        return false;
    }

    // Initialize gyroscope
    if (!initGyroscope()) {
        ESP_LOGE(TAG, "Failed to initialize gyroscope");
        return false;
    }

    // Initialize magnetometer
    if (!initMagnetometer()) {
        ESP_LOGW(TAG, "Failed to initialize magnetometer");
        // Continue without magnetometer
    }

    ESP_LOGI(TAG, "ICM20948 initialized successfully");
    return true;
}

bool ICM20948::reset() {
    selectBank(BANK_0);
    return writeRegister(ICM20948_Reg::PWR_MGMT_1, PWR_MGMT_1_RESET);
}

bool ICM20948::checkWhoAmI() {
    selectBank(BANK_0);
    uint8_t who_am_i = 0;
    if (!readRegister(ICM20948_Reg::WHO_AM_I, &who_am_i)) {
        return false;
    }

    ESP_LOGI(TAG, "WHO_AM_I: 0x%02X (expected 0x%02X)", who_am_i, ICM20948_WHO_AM_I_VALUE);
    return who_am_i == ICM20948_WHO_AM_I_VALUE;
}

bool ICM20948::initAccelerometer() {
    selectBank(BANK_2);

    // Set accelerometer range to 2g
    uint8_t config = ACCEL_FS_SEL_2G << 1;
    if (!writeRegister(ICM20948_Reg::ACCEL_CONFIG, config)) {
        return false;
    }

    accel_range_ = 2;
    return true;
}

bool ICM20948::initGyroscope() {
    selectBank(BANK_2);

    // Set gyroscope range to 250 dps
    uint8_t config = GYRO_FS_SEL_250DPS << 1;
    if (!writeRegister(ICM20948_Reg::GYRO_CONFIG_1, config)) {
        return false;
    }

    gyro_range_ = 250;
    return true;
}

bool ICM20948::initMagnetometer() {
    // Note: ICM20948 magnetometer requires I2C master setup
    // For simplicity, we'll mark it as not enabled for now
    // Full implementation would require setting up the auxiliary I2C master
    magnetometer_enabled_ = false;
    ESP_LOGW(TAG, "Magnetometer initialization not fully implemented");
    return false;
}

bool ICM20948::selectBank(uint8_t bank) {
    return writeRegister(ICM20948_Reg::REG_BANK_SEL, bank);
}

bool ICM20948::writeRegister(uint8_t reg, uint8_t value) {
    uint8_t data[2] = {reg, value};
    esp_err_t ret = i2c_master_write_to_device(
        i2c_port_,
        address_,
        data,
        2,
        pdMS_TO_TICKS(100)
    );
    return ret == ESP_OK;
}

bool ICM20948::readRegister(uint8_t reg, uint8_t* value) {
    esp_err_t ret = i2c_master_write_read_device(
        i2c_port_,
        address_,
        &reg,
        1,
        value,
        1,
        pdMS_TO_TICKS(100)
    );
    return ret == ESP_OK;
}

bool ICM20948::readRegisters(uint8_t reg, uint8_t* buffer, size_t len) {
    esp_err_t ret = i2c_master_write_read_device(
        i2c_port_,
        address_,
        &reg,
        1,
        buffer,
        len,
        pdMS_TO_TICKS(100)
    );
    return ret == ESP_OK;
}

Vector3 ICM20948::readAcceleration() {
    selectBank(BANK_0);

    uint8_t data[6];
    if (!readRegisters(ICM20948_Reg::ACCEL_XOUT_H, data, 6)) {
        ESP_LOGE(TAG, "Failed to read acceleration");
        return last_accel_;
    }

    // Combine high and low bytes
    int16_t raw_x = (int16_t)((data[0] << 8) | data[1]);
    int16_t raw_y = (int16_t)((data[2] << 8) | data[3]);
    int16_t raw_z = (int16_t)((data[4] << 8) | data[5]);

    // Convert to m/s² (1g = 9.80665 m/s²)
    float scale = (accel_range_ * 9.80665f) / 32768.0f;
    last_accel_.x = raw_x * scale;
    last_accel_.y = raw_y * scale;
    last_accel_.z = raw_z * scale;

    return last_accel_;
}

Vector3 ICM20948::readGForce() {
    selectBank(BANK_0);

    uint8_t data[6];
    if (!readRegisters(ICM20948_Reg::ACCEL_XOUT_H, data, 6)) {
        ESP_LOGE(TAG, "Failed to read g-force");
        return {0.0f, 0.0f, 0.0f};
    }

    // Combine high and low bytes
    int16_t raw_x = (int16_t)((data[0] << 8) | data[1]);
    int16_t raw_y = (int16_t)((data[2] << 8) | data[3]);
    int16_t raw_z = (int16_t)((data[4] << 8) | data[5]);

    // Convert to g
    float scale = (float)accel_range_ / 32768.0f;
    Vector3 g_force;
    g_force.x = raw_x * scale;
    g_force.y = raw_y * scale;
    g_force.z = raw_z * scale;

    return g_force;
}

void ICM20948::setRange(uint8_t range_g) {
    selectBank(BANK_2);

    uint8_t config;
    switch (range_g) {
        case 2:
            config = ACCEL_FS_SEL_2G << 1;
            accel_range_ = 2;
            break;
        case 4:
            config = ACCEL_FS_SEL_4G << 1;
            accel_range_ = 4;
            break;
        case 8:
            config = ACCEL_FS_SEL_8G << 1;
            accel_range_ = 8;
            break;
        case 16:
            config = ACCEL_FS_SEL_16G << 1;
            accel_range_ = 16;
            break;
        default:
            ESP_LOGW(TAG, "Invalid accelerometer range: %d", range_g);
            return;
    }

    writeRegister(ICM20948_Reg::ACCEL_CONFIG, config);
}

void ICM20948::setSampleRate(uint16_t rate_hz) {
    // Sample rate configuration not implemented yet
    ESP_LOGW(TAG, "setSampleRate not implemented");
}

Vector3 ICM20948::readRotation() {
    selectBank(BANK_0);

    uint8_t data[6];
    if (!readRegisters(ICM20948_Reg::GYRO_XOUT_H, data, 6)) {
        ESP_LOGE(TAG, "Failed to read rotation");
        return last_gyro_;
    }

    // Combine high and low bytes
    int16_t raw_x = (int16_t)((data[0] << 8) | data[1]);
    int16_t raw_y = (int16_t)((data[2] << 8) | data[3]);
    int16_t raw_z = (int16_t)((data[4] << 8) | data[5]);

    // Convert to rad/s (gyro_range_ is in dps)
    float scale = (gyro_range_ * M_PI / 180.0f) / 32768.0f;
    last_gyro_.x = raw_x * scale;
    last_gyro_.y = raw_y * scale;
    last_gyro_.z = raw_z * scale;

    return last_gyro_;
}

void ICM20948::setRange(uint16_t range_dps) {
    selectBank(BANK_2);

    uint8_t config;
    switch (range_dps) {
        case 250:
            config = GYRO_FS_SEL_250DPS << 1;
            gyro_range_ = 250;
            break;
        case 500:
            config = GYRO_FS_SEL_500DPS << 1;
            gyro_range_ = 500;
            break;
        case 1000:
            config = GYRO_FS_SEL_1000DPS << 1;
            gyro_range_ = 1000;
            break;
        case 2000:
            config = GYRO_FS_SEL_2000DPS << 1;
            gyro_range_ = 2000;
            break;
        default:
            ESP_LOGW(TAG, "Invalid gyroscope range: %d", range_dps);
            return;
    }

    writeRegister(ICM20948_Reg::GYRO_CONFIG_1, config);
}

Vector3 ICM20948::readMagneticField() {
    if (!magnetometer_enabled_) {
        return last_mag_;
    }

    // Magnetometer reading not fully implemented
    ESP_LOGW(TAG, "readMagneticField not fully implemented");
    return last_mag_;
}

float ICM20948::getHeading() {
    if (!magnetometer_enabled_) {
        return 0.0f;
    }

    Vector3 mag = readMagneticField();

    // Apply calibration offsets
    float mx = mag.x - mag_offset_x_;
    float my = mag.y - mag_offset_y_;

    // Calculate heading (0-360 degrees)
    float heading = atan2f(my, mx) * 180.0f / M_PI;
    if (heading < 0) {
        heading += 360.0f;
    }

    return heading;
}

void ICM20948::startCalibration() {
    mag_offset_x_ = 0.0f;
    mag_offset_y_ = 0.0f;
    mag_offset_z_ = 0.0f;
    mag_calibrated_ = false;
    ESP_LOGI(TAG, "Magnetometer calibration started");
}

void ICM20948::endCalibration() {
    mag_calibrated_ = true;
    ESP_LOGI(TAG, "Magnetometer calibration complete");
}

bool ICM20948::isCalibrated() const {
    return mag_calibrated_;
}

float ICM20948::readTemperature() {
    selectBank(BANK_0);

    uint8_t data[2];
    if (!readRegisters(0x39, data, 2)) { // TEMP_OUT_H register
        ESP_LOGE(TAG, "Failed to read temperature");
        return 0.0f;
    }

    // Combine high and low bytes
    int16_t raw_temp = (int16_t)((data[0] << 8) | data[1]);

    // Convert to Celsius
    // Formula from datasheet: ((TEMP_OUT - RoomTemp_Offset) / Temp_Sensitivity) + 21
    float temperature = (raw_temp / 333.87f) + 21.0f;

    return temperature;
}

} // namespace OpenPony
