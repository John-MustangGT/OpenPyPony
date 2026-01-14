// src/sensors/pa1010d.cpp
// PA1010D GPS module driver implementation

#include "sensors/pa1010d.h"
#include "esp_log.h"
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cmath>

static const char* TAG = "PA1010D";

namespace OpenPony {

// NMEA Parser Implementation

NMEAParser::NMEAParser()
    : has_position_(false)
    , latitude_(0.0)
    , longitude_(0.0)
    , altitude_(0.0f)
    , speed_(0.0f)
    , track_(0.0f)
    , satellites_(0)
    , hdop_(99.99f)
    , fix_type_(FixType::NO_FIX)
{
}

bool NMEAParser::parse(const char* sentence) {
    if (!sentence || sentence[0] != '$') {
        return false;
    }

    // Validate checksum
    if (!validateChecksum(sentence)) {
        ESP_LOGW(TAG, "Invalid checksum: %s", sentence);
        return false;
    }

    // Parse specific sentence types
    if (strncmp(sentence, "$GPGGA", 6) == 0 || strncmp(sentence, "$GNGGA", 6) == 0) {
        return parseGGA(sentence);
    } else if (strncmp(sentence, "$GPRMC", 6) == 0 || strncmp(sentence, "$GNRMC", 6) == 0) {
        return parseRMC(sentence);
    } else if (strncmp(sentence, "$GPGSV", 6) == 0 || strncmp(sentence, "$GNGSV", 6) == 0) {
        return parseGSV(sentence);
    }

    return false;
}

bool NMEAParser::validateChecksum(const char* sentence) {
    const char* star = strchr(sentence, '*');
    if (!star) return false;

    // Calculate checksum
    uint8_t checksum = 0;
    for (const char* p = sentence + 1; p < star; p++) {
        checksum ^= *p;
    }

    // Parse expected checksum
    uint8_t expected = (uint8_t)strtol(star + 1, nullptr, 16);
    return checksum == expected;
}

double NMEAParser::parseLatLon(const char* str, const char* dir) {
    if (!str || !dir || strlen(str) < 4) {
        return 0.0;
    }

    // Parse degrees and minutes (format: DDMM.MMMM or DDDMM.MMMM)
    char deg_str[4] = {0};
    const char* min_str;

    if (strlen(str) > 10) {
        // Longitude: DDD format
        strncpy(deg_str, str, 3);
        min_str = str + 3;
    } else {
        // Latitude: DD format
        strncpy(deg_str, str, 2);
        min_str = str + 2;
    }

    double degrees = atof(deg_str);
    double minutes = atof(min_str);
    double result = degrees + (minutes / 60.0);

    // Apply direction
    if (dir[0] == 'S' || dir[0] == 'W') {
        result = -result;
    }

    return result;
}

bool NMEAParser::parseGGA(const char* sentence) {
    // $GPGGA,HHMMSS.SS,DDMM.MMMM,N,DDDMM.MMMM,E,Q,SS,H.H,AAA.A,M,GGG.G,M,,*CS
    char buffer[128];
    strncpy(buffer, sentence, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    char* token = strtok(buffer, ",");
    int field = 0;
    char lat_str[16] = {0};
    char lat_dir[2] = {0};
    char lon_str[16] = {0};
    char lon_dir[2] = {0};
    uint8_t quality = 0;

    while (token != nullptr && field < 15) {
        switch (field) {
            case 2: // Latitude
                strncpy(lat_str, token, sizeof(lat_str) - 1);
                break;
            case 3: // Latitude direction
                strncpy(lat_dir, token, sizeof(lat_dir) - 1);
                break;
            case 4: // Longitude
                strncpy(lon_str, token, sizeof(lon_str) - 1);
                break;
            case 5: // Longitude direction
                strncpy(lon_dir, token, sizeof(lon_dir) - 1);
                break;
            case 6: // Fix quality
                quality = atoi(token);
                break;
            case 7: // Number of satellites
                satellites_ = atoi(token);
                break;
            case 8: // HDOP
                hdop_ = atof(token);
                break;
            case 9: // Altitude
                altitude_ = atof(token);
                break;
        }
        token = strtok(nullptr, ",");
        field++;
    }

    // Update fix type based on quality
    if (quality == 0) {
        fix_type_ = FixType::NO_FIX;
        has_position_ = false;
    } else if (quality == 1) {
        fix_type_ = FixType::FIX_2D; // Assume 2D for now
        has_position_ = true;
    } else {
        fix_type_ = FixType::FIX_3D;
        has_position_ = true;
    }

    if (has_position_) {
        latitude_ = parseLatLon(lat_str, lat_dir);
        longitude_ = parseLatLon(lon_str, lon_dir);
    }

    return true;
}

bool NMEAParser::parseRMC(const char* sentence) {
    // $GPRMC,HHMMSS.SS,A,DDMM.MMMM,N,DDDMM.MMMM,E,SSS.S,TTT.T,DDMMYY,,,A*CS
    char buffer[128];
    strncpy(buffer, sentence, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    char* token = strtok(buffer, ",");
    int field = 0;
    char lat_str[16] = {0};
    char lat_dir[2] = {0};
    char lon_str[16] = {0};
    char lon_dir[2] = {0};
    char status = 'V';

    while (token != nullptr && field < 13) {
        switch (field) {
            case 2: // Status (A=active, V=void)
                status = token[0];
                break;
            case 3: // Latitude
                strncpy(lat_str, token, sizeof(lat_str) - 1);
                break;
            case 4: // Latitude direction
                strncpy(lat_dir, token, sizeof(lat_dir) - 1);
                break;
            case 5: // Longitude
                strncpy(lon_str, token, sizeof(lon_str) - 1);
                break;
            case 6: // Longitude direction
                strncpy(lon_dir, token, sizeof(lon_dir) - 1);
                break;
            case 7: // Speed over ground (knots)
                speed_ = atof(token) * 0.514444f; // Convert to m/s
                break;
            case 8: // Track angle (degrees)
                track_ = atof(token);
                break;
        }
        token = strtok(nullptr, ",");
        field++;
    }

    if (status == 'A' && strlen(lat_str) > 0) {
        has_position_ = true;
        latitude_ = parseLatLon(lat_str, lat_dir);
        longitude_ = parseLatLon(lon_str, lon_dir);
    }

    return true;
}

bool NMEAParser::parseGSV(const char* sentence) {
    // $GPGSV,N,S,NN,PRN,EL,AZ,SNR,...*CS
    // N = total messages, S = message number, NN = satellites in view
    char buffer[128];
    strncpy(buffer, sentence, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    char* token = strtok(buffer, ",");
    int field = 0;
    int msg_num = 0;
    int total_msgs = 0;

    while (token != nullptr) {
        if (field == 2) {
            msg_num = atoi(token);
        } else if (field == 1) {
            total_msgs = atoi(token);
        } else if (field >= 4 && (field - 4) % 4 == 0) {
            // Satellite info starts at field 4, groups of 4
            int sat_index = (field - 4) / 4;
            if (sat_index < 4) { // Max 4 satellites per GSV message
                SatelliteInfo sat;
                sat.prn = atoi(token);

                // Elevation
                token = strtok(nullptr, ",");
                field++;
                if (token && strlen(token) > 0) {
                    sat.elevation = atoi(token);
                } else {
                    sat.elevation = -1;
                }

                // Azimuth
                token = strtok(nullptr, ",");
                field++;
                if (token && strlen(token) > 0) {
                    sat.azimuth = atoi(token);
                } else {
                    sat.azimuth = -1;
                }

                // SNR
                token = strtok(nullptr, ",*");
                field++;
                if (token && strlen(token) > 0) {
                    sat.snr = atoi(token);
                } else {
                    sat.snr = -1;
                }

                // Add or update satellite in list
                bool found = false;
                for (auto& s : satellite_details_) {
                    if (s.prn == sat.prn) {
                        s = sat;
                        found = true;
                        break;
                    }
                }
                if (!found && sat.prn > 0) {
                    satellite_details_.push_back(sat);
                }
            }
        }
        token = strtok(nullptr, ",*");
        field++;
    }

    // If this was the last GSV message, clean up old satellites
    if (msg_num == total_msgs) {
        // Limit to reasonable number
        if (satellite_details_.size() > 32) {
            satellite_details_.resize(32);
        }
    }

    return true;
}

// PA1010D Implementation

PA1010D::PA1010D(i2c_port_t i2c_port, uint8_t address)
    : i2c_port_(i2c_port)
    , address_(address)
    , buffer_pos_(0)
{
    memset(read_buffer_, 0, sizeof(read_buffer_));
    memset(&last_time_, 0, sizeof(last_time_));
}

PA1010D::~PA1010D() {
}

bool PA1010D::update() {
    return readData();
}

bool PA1010D::readData() {
    // PA1010D sends data via I2C at 0x10
    uint8_t data[128];

    esp_err_t ret = i2c_master_read_from_device(
        i2c_port_,
        address_,
        data,
        sizeof(data),
        pdMS_TO_TICKS(100)
    );

    if (ret != ESP_OK) {
        return false;
    }

    // Process received data
    for (size_t i = 0; i < sizeof(data); i++) {
        char c = (char)data[i];

        // Check for valid NMEA characters
        if (c == 0x00 || c == 0xFF) {
            continue; // Skip padding
        }

        // Check for sentence start
        if (c == '$') {
            buffer_pos_ = 0;
        }

        // Add to buffer
        if (buffer_pos_ < sizeof(read_buffer_) - 1) {
            read_buffer_[buffer_pos_++] = c;
        }

        // Check for sentence end
        if (c == '\n' && buffer_pos_ > 1) {
            read_buffer_[buffer_pos_] = '\0';

            // Parse the sentence
            parser_.parse(read_buffer_);

            buffer_pos_ = 0;
        }
    }

    return true;
}

bool PA1010D::sendCommand(const char* command) {
    // Calculate checksum
    uint8_t checksum = 0;
    for (const char* p = command; *p; p++) {
        checksum ^= *p;
    }

    // Format command with checksum
    char buffer[128];
    snprintf(buffer, sizeof(buffer), "$%s*%02X\r\n", command, checksum);

    // Send via I2C
    esp_err_t ret = i2c_master_write_to_device(
        i2c_port_,
        address_,
        (uint8_t*)buffer,
        strlen(buffer),
        pdMS_TO_TICKS(100)
    );

    return ret == ESP_OK;
}

bool PA1010D::hasFix() const {
    return parser_.hasPosition() && parser_.getFixType() != FixType::NO_FIX;
}

Position PA1010D::getPosition() const {
    Position pos;
    pos.latitude = parser_.getLatitude();
    pos.longitude = parser_.getLongitude();
    pos.altitude = parser_.getAltitude();
    return pos;
}

float PA1010D::getSpeed() const {
    return parser_.getSpeed();
}

float PA1010D::getTrack() const {
    return parser_.getTrack();
}

GPSTime PA1010D::getTime() const {
    return last_time_;
}

uint8_t PA1010D::getSatellites() const {
    return parser_.getSatellites();
}

float PA1010D::getHDOP() const {
    return parser_.getHDOP();
}

FixType PA1010D::getFixType() const {
    return parser_.getFixType();
}

uint8_t PA1010D::getFixQuality() const {
    FixType fix = parser_.getFixType();
    switch (fix) {
        case FixType::NO_FIX: return 0;
        case FixType::FIX_2D: return 1;
        case FixType::FIX_3D: return 2;
        case FixType::DGPS: return 3;
        default: return 0;
    }
}

std::vector<SatelliteInfo> PA1010D::getSatelliteDetails() const {
    return parser_.getSatelliteDetails();
}

void PA1010D::setUpdateRate(uint16_t rate_ms) {
    // MTK command to set update rate
    // PMTK_API_SET_FIX_CTL_1HZ = 1000ms, 5HZ = 200ms, 10HZ = 100ms
    char cmd[32];
    snprintf(cmd, sizeof(cmd), "PMTK220,%d", rate_ms);
    sendCommand(cmd);

    // Enable GPGSV sentences for satellite details
    sendCommand("PMTK314,0,1,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0");
}

} // namespace OpenPony
