// include/logger.h
// Binary logger for high-speed sensor data logging
// Format is COMPATIBLE with CircuitPython version

#pragma once

#include <Arduino.h>
#include <SD.h>
#include "interfaces/gps_interface.h"
#include "interfaces/imu_interface.h"

namespace OpenPony {

// Frame size: 64 bytes (same as CircuitPython)
// Layout:
// - Timestamp (8 bytes, double)
// - GPS latitude (8 bytes, double)
// - GPS longitude (8 bytes, double)
// - GPS altitude (4 bytes, float)
// - GPS speed (4 bytes, float)
// - GPS satellites (1 byte)
// - Reserved (1 byte)
// - Accel gx (4 bytes, float)
// - Accel gy (4 bytes, float)
// - Accel gz (4 bytes, float)
// - Gyro rx (4 bytes, float)
// - Gyro ry (4 bytes, float)
// - Gyro rz (4 bytes, float)
// - Reserved (8 bytes)
// - Checksum (4 bytes, CRC32)
constexpr size_t FRAME_SIZE = 64;

// Session data frame
struct DataFrame {
    double timestamp;       // Unix timestamp (seconds since epoch)
    double latitude;        // Decimal degrees
    double longitude;       // Decimal degrees
    float altitude;         // Meters
    float speed;            // m/s
    uint8_t satellites;     // Number of satellites
    uint8_t reserved1;      // Reserved byte
    float gx;              // Accelerometer X (g-force)
    float gy;              // Accelerometer Y (g-force)
    float gz;              // Accelerometer Z (g-force)
    float rx;              // Gyroscope X (deg/s)
    float ry;              // Gyroscope Y (deg/s)
    float rz;              // Gyroscope Z (deg/s)
    uint8_t reserved2[8];   // Reserved bytes
    uint32_t checksum;      // CRC32 checksum
} __attribute__((packed));

class BinaryLogger {
public:
    BinaryLogger();
    ~BinaryLogger();

    // Initialize logger (create session file)
    bool begin(const char* session_name = nullptr);

    // Close logger and flush data
    void close();

    // Log a frame of data
    bool logFrame(double timestamp,
                  const Position& gps_pos,
                  float gps_speed,
                  uint8_t gps_satellites,
                  const Vector3& accel,
                  const Vector3& gyro);

    // Get statistics
    uint32_t getFrameCount() const { return frame_count_; }
    size_t getBytesWritten() const { return bytes_written_; }
    bool isLogging() const { return file_ && logging_; }

    // Flush buffer to SD card
    void flush();

private:
    File file_;
    bool logging_;
    uint32_t frame_count_;
    size_t bytes_written_;
    char session_filepath_[64];

    // Write buffer for performance (write in larger chunks)
    static constexpr size_t BUFFER_SIZE = 1024;  // 16 frames
    uint8_t write_buffer_[BUFFER_SIZE];
    size_t buffer_pos_;

    // Generate session filename
    void generateSessionName(char* buffer, size_t len);

    // Calculate CRC32 checksum
    uint32_t calculateCRC32(const uint8_t* data, size_t length);

    // Write frame to file (with buffering)
    bool writeFrame(const DataFrame& frame);
};

} // namespace OpenPony
