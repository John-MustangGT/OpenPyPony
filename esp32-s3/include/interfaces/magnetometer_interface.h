// include/interfaces/magnetometer_interface.h
// Magnetometer Interface - Abstract base class for compass/magnetometer
// Based on CircuitPython MagnetometerInterface

#pragma once

#include <Arduino.h>
#include "imu_interface.h"  // For Vector3

namespace OpenPony {

// Magnetometer interface
class MagnetometerInterface {
public:
    virtual ~MagnetometerInterface() = default;

    // Read magnetic field in microTesla (µT)
    virtual Vector3 readMagneticField() = 0;

    // Get compass heading in degrees (0-360, 0 = North)
    // Requires calibration for accurate results
    virtual float getHeading() = 0;

    // Calibration
    virtual void startCalibration() = 0;
    virtual void endCalibration() = 0;
    virtual bool isCalibrated() const = 0;
};

} // namespace OpenPony
