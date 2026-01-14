// include/interfaces/display_interface.h
// Display Interface - Abstract base class for display devices
// Based on CircuitPython DisplayInterface

#pragma once

#include <Arduino.h>

namespace OpenPony {

// Display interface
class DisplayInterface {
public:
    virtual ~DisplayInterface() = default;

    // Core display operations
    virtual void clear() = 0;                               // Clear display
    virtual void update() = 0;                              // Update/refresh display (if buffered)

    // Status display methods
    virtual void showSplash(const char* message) = 0;       // Show startup splash
    virtual void showStatus(const char* line1,              // Show status text
                           const char* line2 = nullptr,
                           const char* line3 = nullptr) = 0;

    // Session info display
    virtual void updateSessionInfo(uint32_t elapsed_sec,    // Update session information
                                   uint32_t samples) = 0;

    // GPS info display
    virtual void updateGPSInfo(bool has_fix,                // Update GPS status
                              uint8_t satellites,
                              float hdop) = 0;

    // G-force display (for racing)
    virtual void updateGForce(float gx, float gy, float gz) = 0;

    // Display properties
    virtual uint16_t getWidth() const = 0;                  // Get display width
    virtual uint16_t getHeight() const = 0;                 // Get display height
    virtual bool hasColor() const = 0;                      // Check if color display
};

} // namespace OpenPony
