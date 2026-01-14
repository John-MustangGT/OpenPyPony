// include/sensors/pa1010d.h
// PA1010D GPS module driver (I2C)
// Adafruit Mini GPS PA1010D on STEMMA QT

#pragma once

#include "interfaces/gps_interface.h"
#include "driver/i2c.h"
#include <vector>
#include <string>

namespace OpenPony {

// NMEA sentence parser
class NMEAParser {
public:
    NMEAParser();

    // Parse NMEA sentence
    bool parse(const char* sentence);

    // Get parsed data
    bool hasPosition() const { return has_position_; }
    double getLatitude() const { return latitude_; }
    double getLongitude() const { return longitude_; }
    float getAltitude() const { return altitude_; }
    float getSpeed() const { return speed_; }
    float getTrack() const { return track_; }
    uint8_t getSatellites() const { return satellites_; }
    float getHDOP() const { return hdop_; }
    FixType getFixType() const { return fix_type_; }

    // Get satellite details (from GPGSV sentences)
    std::vector<SatelliteInfo> getSatelliteDetails() const { return satellite_details_; }

private:
    bool has_position_;
    double latitude_;
    double longitude_;
    float altitude_;
    float speed_;
    float track_;
    uint8_t satellites_;
    float hdop_;
    FixType fix_type_;
    std::vector<SatelliteInfo> satellite_details_;

    // Parse specific sentence types
    bool parseGGA(const char* sentence);
    bool parseRMC(const char* sentence);
    bool parseGSV(const char* sentence);

    // Helper functions
    double parseLatLon(const char* str, const char* dir);
    bool validateChecksum(const char* sentence);
};

class PA1010D : public GPSInterface {
public:
    PA1010D(i2c_port_t i2c_port, uint8_t address = 0x10);
    ~PA1010D();

    // GPSInterface implementation
    bool update() override;
    bool hasFix() const override;
    Position getPosition() const override;
    float getSpeed() const override;
    float getTrack() const override;
    GPSTime getTime() const override;
    uint8_t getSatellites() const override;
    float getHDOP() const override;
    FixType getFixType() const override;
    uint8_t getFixQuality() const override;
    std::vector<SatelliteInfo> getSatelliteDetails() const override;
    void setUpdateRate(uint16_t rate_ms) override;

private:
    i2c_port_t i2c_port_;
    uint8_t address_;
    NMEAParser parser_;
    GPSTime last_time_;

    // Read buffer
    char read_buffer_[256];
    size_t buffer_pos_;

    // Read data from I2C
    bool readData();

    // Send MTK command to GPS
    bool sendCommand(const char* command);
};

} // namespace OpenPony
