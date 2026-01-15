// include/interfaces/gps_interface.h
// GPS Interface - Abstract base class for GPS modules
// Based on CircuitPython GPSInterface abstraction

#pragma once

#include <vector>
#include <stdint.h>

namespace OpenPony {

// GPS position data structure
struct Position {
    double latitude;    // Decimal degrees
    double longitude;   // Decimal degrees
    float altitude;     // Meters above MSL

    Position() : latitude(0.0), longitude(0.0), altitude(0.0) {}
    Position(double lat, double lon, float alt)
        : latitude(lat), longitude(lon), altitude(alt) {}
};

// GPS time structure
struct GPSTime {
    uint16_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;

    GPSTime() : year(0), month(0), day(0), hour(0), minute(0), second(0) {}
};

// Satellite information structure
struct SatelliteInfo {
    uint8_t prn;        // Satellite PRN number
    int16_t elevation;  // Elevation angle (0-90 degrees)
    int16_t azimuth;    // Azimuth angle (0-360 degrees)
    int16_t snr;        // Signal-to-noise ratio (dB), -1 if not available

    SatelliteInfo() : prn(0), elevation(0), azimuth(0), snr(-1) {}
    SatelliteInfo(uint8_t p, int16_t e, int16_t a, int16_t s)
        : prn(p), elevation(e), azimuth(a), snr(s) {}
};

// GPS fix type
enum class FixType {
    NO_FIX,
    FIX_2D,
    FIX_3D
};

// Abstract GPS interface
class GPSInterface {
public:
    virtual ~GPSInterface() = default;

    // Core methods
    virtual bool update() = 0;                              // Update GPS data (call frequently)
    virtual bool hasFix() const = 0;                        // Check if GPS has valid fix

    // Position and navigation
    virtual Position getPosition() const = 0;               // Get current position
    virtual float getSpeed() const = 0;                     // Get speed in m/s
    virtual float getTrack() const = 0;                     // Get course over ground (0-360°)

    // Time
    virtual GPSTime getTime() const = 0;                    // Get GPS UTC time

    // Signal quality
    virtual uint8_t getSatellites() const = 0;              // Get number of satellites in use
    virtual float getHDOP() const = 0;                      // Get horizontal dilution of precision
    virtual FixType getFixType() const = 0;                 // Get fix type (No Fix/2D/3D)
    virtual uint8_t getFixQuality() const = 0;              // Get fix quality (0=no fix, 1=GPS, 2=DGPS)

    // Satellite details (for skyplot)
    virtual std::vector<SatelliteInfo> getSatelliteDetails() const = 0;

    // Configuration
    virtual void setUpdateRate(uint16_t rate_ms) = 0;       // Set update rate in milliseconds
};

} // namespace OpenPony
