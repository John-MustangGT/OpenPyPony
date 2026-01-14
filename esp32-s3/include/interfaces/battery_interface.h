// include/interfaces/battery_interface.h
// Battery monitoring interface for Feather battery charger

#pragma once

#include <stdint.h>

namespace OpenPony {

// Battery charge status
enum class ChargeStatus {
    UNKNOWN,
    CHARGING,
    DISCHARGING,
    FULL,
    NOT_PRESENT
};

// Battery information
struct BatteryInfo {
    float voltage;              // Battery voltage (V)
    float percent;              // Charge level (0-100%)
    ChargeStatus status;        // Charging status
    bool usb_powered;           // Connected to USB power

    BatteryInfo() : voltage(0), percent(0),
                    status(ChargeStatus::UNKNOWN),
                    usb_powered(false) {}
};

// Abstract battery monitor interface
class BatteryInterface {
public:
    virtual ~BatteryInterface() = default;

    // Read battery information
    virtual BatteryInfo read() = 0;

    // Get individual values
    virtual float getVoltage() = 0;
    virtual float getPercent() = 0;
    virtual ChargeStatus getStatus() = 0;
    virtual bool isUSBPowered() = 0;
};

} // namespace OpenPony
