// include/logger.h
// Flash-based binary logger with ring buffer policy
// Format is COMPATIBLE with CircuitPython version

#pragma once

#include <stdio.h>
#include <vector>
#include <string>
#include "esp_vfs.h"
#include "esp_spiffs.h"
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

// Storage policy
constexpr float HIGH_WATER_MARK = 0.90f;  // 90% full triggers cleanup
constexpr float LOW_WATER_MARK = 0.60f;   // Delete until 60% full

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

// Session metadata
struct SessionInfo {
    std::string filename;
    size_t size_bytes;
    uint32_t frame_count;
    time_t created_time;

    SessionInfo() : size_bytes(0), frame_count(0), created_time(0) {}
};

class FlashLogger {
public:
    FlashLogger();
    ~FlashLogger();

    // Initialize flash filesystem and logger
    bool begin();

    // Start new logging session (creates new file)
    bool startSession(const char* session_name = nullptr);

    // Stop current session
    void stopSession();

    // Close logger
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
    const char* getCurrentSession() const { return current_session_.c_str(); }

    // Flush buffer to flash
    void flush();

    // Flash storage management
    bool checkStorage();                    // Check if cleanup needed
    bool cleanupOldSessions();              // Delete old sessions until LOW_WATER_MARK
    std::vector<SessionInfo> listSessions(); // List all sessions on flash
    bool deleteSession(const char* filename); // Delete specific session
    size_t getTotalUsed();                  // Get total flash usage
    size_t getTotalSize();                  // Get total flash size
    float getUsagePercent();                // Get usage percentage

private:
    FILE* file_;
    bool logging_;
    uint32_t frame_count_;
    size_t bytes_written_;
    std::string current_session_;
    std::string base_path_;

    // Write buffer for performance (16 frames = 1KB)
    static constexpr size_t BUFFER_SIZE = FRAME_SIZE * 16;
    uint8_t write_buffer_[BUFFER_SIZE];
    size_t buffer_pos_;

    // Generate session filename with timestamp
    std::string generateSessionName();

    // Calculate CRC32 checksum
    uint32_t calculateCRC32(const uint8_t* data, size_t length);

    // Write frame to file (with buffering)
    bool writeFrame(const DataFrame& frame);

    // Initialize SPIFFS filesystem
    bool initSPIFFS();
};

} // namespace OpenPony
