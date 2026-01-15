// include/interfaces/imu_interface.h
// IMU Interface - Abstract base class for accelerometer and gyroscope
// Based on CircuitPython AccelerometerInterface and GyroscopeInterface

#pragma once

#include <stdint.h>

namespace OpenPony {

// 3-axis vector structure
struct Vector3 {
    float x;
    float y;
    float z;

    Vector3() : x(0.0f), y(0.0f), z(0.0f) {}
    Vector3(float _x, float _y, float _z) : x(_x), y(_y), z(_z) {}
};

// Accelerometer interface
class AccelerometerInterface {
public:
    virtual ~AccelerometerInterface() = default;

    // Read raw acceleration in m/s^2
    virtual Vector3 readAcceleration() = 0;

    // Read acceleration as g-force (1g = 9.81 m/s^2)
    virtual Vector3 readGForce() = 0;

    // Configuration
    virtual void setRange(uint8_t range_g) = 0;             // Set range (2, 4, 8, 16 g)
    virtual void setSampleRate(uint16_t rate_hz) = 0;       // Set sample rate in Hz
};

// Gyroscope interface
class GyroscopeInterface {
public:
    virtual ~GyroscopeInterface() = default;

    // Read rotation rates in degrees/second
    virtual Vector3 readRotation() = 0;

    // Configuration
    virtual void setRange(uint16_t range_dps) = 0;          // Set range (250, 500, 1000, 2000 dps)
};

// Combined IMU interface (accelerometer + gyroscope)
class IMUInterface : public AccelerometerInterface, public GyroscopeInterface {
public:
    virtual ~IMUInterface() = default;

    // Temperature sensor (many IMUs have this)
    virtual float readTemperature() = 0;                    // Read temperature in Celsius
};

} // namespace OpenPony
