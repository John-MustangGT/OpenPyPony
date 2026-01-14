// include/sensors/icm20948.h
// ICM20948 9-DOF IMU driver (I2C)
// Accelerometer + Gyroscope + Magnetometer

#pragma once

#include "interfaces/imu_interface.h"
#include "interfaces/magnetometer_interface.h"
#include "driver/i2c.h"

namespace OpenPony {

// ICM20948 I2C address
constexpr uint8_t ICM20948_ADDRESS = 0x69;

// Register definitions
namespace ICM20948_Reg {
    constexpr uint8_t WHO_AM_I = 0x00;
    constexpr uint8_t PWR_MGMT_1 = 0x06;
    constexpr uint8_t ACCEL_XOUT_H = 0x2D;
    constexpr uint8_t GYRO_XOUT_H = 0x33;
    constexpr uint8_t ACCEL_CONFIG = 0x14;
    constexpr uint8_t GYRO_CONFIG_1 = 0x01;
    constexpr uint8_t REG_BANK_SEL = 0x7F;
}

class ICM20948 : public IMUInterface, public MagnetometerInterface {
public:
    ICM20948(i2c_port_t i2c_port, uint8_t address = ICM20948_ADDRESS);
    ~ICM20948();

    // Initialization
    bool begin();

    // AccelerometerInterface implementation
    Vector3 readAcceleration() override;
    Vector3 readGForce() override;
    void setRange(uint8_t range_g) override;
    void setSampleRate(uint16_t rate_hz) override;

    // GyroscopeInterface implementation
    Vector3 readRotation() override;
    void setRange(uint16_t range_dps) override;

    // MagnetometerInterface implementation
    Vector3 readMagneticField() override;
    float getHeading() override;
    void startCalibration() override;
    void endCalibration() override;
    bool isCalibrated() const override;

    // IMUInterface implementation
    float readTemperature() override;

private:
    i2c_port_t i2c_port_;
    uint8_t address_;
    uint8_t accel_range_;       // g (2, 4, 8, 16)
    uint16_t gyro_range_;       // dps (250, 500, 1000, 2000)
    bool magnetometer_enabled_;
    bool mag_calibrated_;

    // Magnetometer calibration
    float mag_offset_x_;
    float mag_offset_y_;
    float mag_offset_z_;

    // Last readings for error handling
    Vector3 last_accel_;
    Vector3 last_gyro_;
    Vector3 last_mag_;

    // I2C helpers
    bool writeRegister(uint8_t reg, uint8_t value);
    bool readRegister(uint8_t reg, uint8_t* value);
    bool readRegisters(uint8_t reg, uint8_t* buffer, size_t len);
    bool selectBank(uint8_t bank);

    // Initialization helpers
    bool reset();
    bool checkWhoAmI();
    bool initAccelerometer();
    bool initGyroscope();
    bool initMagnetometer();
};

} // namespace OpenPony
