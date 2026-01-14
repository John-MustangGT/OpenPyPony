// include/interfaces/vehicle_interface.h
// Vehicle parameters interface - Abstract base for CAN/OBD2/ELM327
// Future integration with vgate icar pro 2 BLE OBD2

#pragma once

#include <stdint.h>

namespace OpenPony {

// Vehicle data structure
struct VehicleData {
    // Engine
    float rpm;                  // Engine RPM
    float throttle_position;    // Throttle position (0-100%)
    float engine_load;          // Engine load (0-100%)
    float coolant_temp;         // Coolant temperature (°C)
    float intake_temp;          // Intake air temperature (°C)

    // Speed/transmission
    float vehicle_speed;        // Vehicle speed (km/h)
    uint8_t gear;              // Current gear (0 = N, 1-6 = gears)

    // Fuel
    float fuel_pressure;        // Fuel pressure (kPa)
    float fuel_rate;           // Fuel consumption rate (L/h)
    float fuel_level;          // Fuel level (0-100%)

    // Timing
    float ignition_timing;     // Ignition timing advance (degrees)

    // Battery/electrical
    float battery_voltage;     // Battery voltage (V)

    // Status flags
    bool mil_active;           // Check engine light
    bool available;            // Data source connected

    VehicleData() : rpm(0), throttle_position(0), engine_load(0),
                    coolant_temp(0), intake_temp(0), vehicle_speed(0),
                    gear(0), fuel_pressure(0), fuel_rate(0), fuel_level(0),
                    ignition_timing(0), battery_voltage(0),
                    mil_active(false), available(false) {}
};

// Abstract vehicle interface (CAN, OBD2, etc.)
class VehicleInterface {
public:
    virtual ~VehicleInterface() = default;

    // Connection
    virtual bool begin() = 0;                       // Initialize connection
    virtual bool isConnected() const = 0;           // Check if connected
    virtual void disconnect() = 0;                  // Disconnect

    // Data retrieval
    virtual bool update() = 0;                      // Update all PIDs
    virtual VehicleData getData() const = 0;        // Get current vehicle data

    // Configuration
    virtual void setUpdateRate(uint16_t rate_ms) = 0;  // Set update rate
};

// Null vehicle (when no OBD2/CAN available)
class NullVehicle : public VehicleInterface {
public:
    bool begin() override { return true; }
    bool isConnected() const override { return false; }
    void disconnect() override {}
    bool update() override { return false; }
    VehicleData getData() const override { return VehicleData(); }
    void setUpdateRate(uint16_t rate_ms) override {}
};

} // namespace OpenPony
