// src/logger.cpp
// Flash-based binary logger with LZ4 compression

#include "logger.h"
#include "esp_log.h"
#include "esp_crc.h"
#include "esp_timer.h"
#include "lz4.h"
#include <dirent.h>
#include <sys/stat.h>
#include <time.h>
#include <algorithm>

static const char* TAG = "FlashLogger";

namespace OpenPony {

// SPIFFS configuration
constexpr const char* SPIFFS_BASE_PATH = "/spiffs";
constexpr const char* SESSION_PREFIX = "session_";

// LZ4 compression configuration
constexpr size_t LZ4_COMPRESS_BATCH_SIZE = FRAME_SIZE * 16;  // Compress 16 frames at a time (1KB)
constexpr size_t LZ4_COMPRESSED_BOUND = LZ4_COMPRESSBATCH_SIZE + (LZ4_COMPRESSBATCH_SIZE / 255) + 16;

// File format with compression:
// [Header: 4 bytes "OPL1"] - OpenPonyLogger format version 1
// [Compressed blocks]
// Each block:
//   - Uncompressed size (4 bytes)
//   - Compressed size (4 bytes)
//   - Compressed data (variable)

FlashLogger::FlashLogger()
    : file_(nullptr)
    , logging_(false)
    , frame_count_(0)
    , bytes_written_(0)
    , buffer_pos_(0)
    , base_path_(SPIFFS_BASE_PATH)
{
    memset(write_buffer_, 0, sizeof(write_buffer_));
}

FlashLogger::~FlashLogger() {
    close();
}

bool FlashLogger::begin() {
    if (!initSPIFFS()) {
        ESP_LOGE(TAG, "Failed to initialize SPIFFS");
        return false;
    }

    ESP_LOGI(TAG, "FlashLogger initialized");
    return true;
}

bool FlashLogger::initSPIFFS() {
    ESP_LOGI(TAG, "Initializing SPIFFS");

    esp_vfs_spiffs_conf_t conf = {
        .base_path = SPIFFS_BASE_PATH,
        .partition_label = nullptr,
        .max_files = 8,
        .format_if_mount_failed = true
    };

    esp_err_t ret = esp_vfs_spiffs_register(&conf);

    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount or format filesystem");
        } else if (ret == ESP_ERR_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to find SPIFFS partition");
        } else {
            ESP_LOGE(TAG, "Failed to initialize SPIFFS (%s)", esp_err_to_name(ret));
        }
        return false;
    }

    // Check filesystem
    size_t total = 0, used = 0;
    ret = esp_spiffs_info(nullptr, &total, &used);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get SPIFFS partition information (%s)", esp_err_to_name(ret));
        return false;
    }

    ESP_LOGI(TAG, "SPIFFS initialized: %d KB total, %d KB used", total / 1024, used / 1024);
    return true;
}

std::string FlashLogger::generateSessionName() {
    time_t now = time(nullptr);
    struct tm timeinfo;
    localtime_r(&now, &timeinfo);

    char filename[64];
    snprintf(filename, sizeof(filename), "%s%04d%02d%02d_%02d%02d%02d.opl",
             SESSION_PREFIX,
             timeinfo.tm_year + 1900,
             timeinfo.tm_mon + 1,
             timeinfo.tm_mday,
             timeinfo.tm_hour,
             timeinfo.tm_min,
             timeinfo.tm_sec);

    return std::string(base_path_) + "/" + filename;
}

bool FlashLogger::startSession(const char* session_name) {
    if (logging_) {
        ESP_LOGW(TAG, "Already logging, stop current session first");
        return false;
    }

    // Generate session name if not provided
    if (session_name == nullptr || strlen(session_name) == 0) {
        current_session_ = generateSessionName();
    } else {
        current_session_ = std::string(base_path_) + "/" + session_name;
    }

    // Open file for writing
    file_ = fopen(current_session_.c_str(), "wb");
    if (!file_) {
        ESP_LOGE(TAG, "Failed to open file for writing: %s", current_session_.c_str());
        return false;
    }

    // Write file header
    const char header[4] = {'O', 'P', 'L', '1'};
    if (fwrite(header, 1, 4, file_) != 4) {
        ESP_LOGE(TAG, "Failed to write file header");
        fclose(file_);
        file_ = nullptr;
        return false;
    }

    logging_ = true;
    frame_count_ = 0;
    bytes_written_ = 4; // Header
    buffer_pos_ = 0;

    ESP_LOGI(TAG, "Started logging session: %s", current_session_.c_str());
    return true;
}

void FlashLogger::stopSession() {
    if (!logging_) {
        return;
    }

    // Flush any remaining buffered data
    flush();

    if (file_) {
        fclose(file_);
        file_ = nullptr;
    }

    logging_ = false;

    ESP_LOGI(TAG, "Stopped logging session: %s (%u frames, %u bytes)",
             current_session_.c_str(), frame_count_, bytes_written_);
}

void FlashLogger::close() {
    stopSession();
}

uint32_t FlashLogger::calculateCRC32(const uint8_t* data, size_t length) {
    return esp_crc32_le(0, data, length);
}

bool FlashLogger::logFrame(double timestamp,
                           const Position& gps_pos,
                           float gps_speed,
                           uint8_t gps_satellites,
                           const Vector3& accel,
                           const Vector3& gyro)
{
    if (!logging_ || !file_) {
        return false;
    }

    // Create data frame
    DataFrame frame;
    memset(&frame, 0, sizeof(frame));

    frame.timestamp = timestamp;
    frame.latitude = gps_pos.latitude;
    frame.longitude = gps_pos.longitude;
    frame.altitude = gps_pos.altitude;
    frame.speed = gps_speed;
    frame.satellites = gps_satellites;
    frame.gx = accel.x;
    frame.gy = accel.y;
    frame.gz = accel.z;
    frame.rx = gyro.x;
    frame.ry = gyro.y;
    frame.rz = gyro.z;

    // Calculate CRC32 (over everything except the checksum field)
    frame.checksum = calculateCRC32((uint8_t*)&frame, sizeof(frame) - sizeof(uint32_t));

    // Write frame to buffer
    return writeFrame(frame);
}

bool FlashLogger::writeFrame(const DataFrame& frame) {
    // Copy frame to write buffer
    if (buffer_pos_ + FRAME_SIZE > BUFFER_SIZE) {
        // Buffer full, flush it
        flush();
    }

    memcpy(write_buffer_ + buffer_pos_, &frame, FRAME_SIZE);
    buffer_pos_ += FRAME_SIZE;
    frame_count_++;

    // Auto-flush every 16 frames (1KB)
    if (buffer_pos_ >= BUFFER_SIZE) {
        flush();
    }

    return true;
}

void FlashLogger::flush() {
    if (!file_ || buffer_pos_ == 0) {
        return;
    }

    // Compress the buffer using LZ4
    char compressed_buffer[LZ4_COMPRESSED_BOUND];
    int compressed_size = LZ4_compress_default(
        (const char*)write_buffer_,
        compressed_buffer,
        buffer_pos_,
        sizeof(compressed_buffer)
    );

    if (compressed_size <= 0) {
        ESP_LOGE(TAG, "LZ4 compression failed");
        // Fallback: write uncompressed
        uint32_t uncompressed_size = buffer_pos_;
        uint32_t size_marker = 0xFFFFFFFF; // Special marker for uncompressed

        fwrite(&size_marker, 1, sizeof(size_marker), file_);
        fwrite(&uncompressed_size, 1, sizeof(uncompressed_size), file_);
        fwrite(write_buffer_, 1, buffer_pos_, file_);

        bytes_written_ += sizeof(size_marker) + sizeof(uncompressed_size) + buffer_pos_;
    } else {
        // Write compressed block:
        // [uncompressed_size][compressed_size][compressed_data]
        uint32_t uncompressed_size = buffer_pos_;
        uint32_t comp_size = compressed_size;

        fwrite(&uncompressed_size, 1, sizeof(uncompressed_size), file_);
        fwrite(&comp_size, 1, sizeof(comp_size), file_);
        fwrite(compressed_buffer, 1, compressed_size, file_);

        bytes_written_ += sizeof(uncompressed_size) + sizeof(comp_size) + compressed_size;

        float ratio = (float)buffer_pos_ / (float)compressed_size;
        ESP_LOGD(TAG, "Compressed %u bytes to %d bytes (ratio: %.2fx)",
                 buffer_pos_, compressed_size, ratio);
    }

    // Reset buffer
    buffer_pos_ = 0;
    fflush(file_);
}

bool FlashLogger::checkStorage() {
    float usage = getUsagePercent();

    if (usage >= HIGH_WATER_MARK * 100.0f) {
        ESP_LOGW(TAG, "Storage high water mark reached: %.1f%%", usage);
        return false;
    }

    return true;
}

bool FlashLogger::cleanupOldSessions() {
    ESP_LOGI(TAG, "Starting storage cleanup");

    auto sessions = listSessions();
    if (sessions.empty()) {
        ESP_LOGW(TAG, "No sessions to clean up");
        return false;
    }

    // Sort sessions by creation time (oldest first)
    std::sort(sessions.begin(), sessions.end(),
              [](const SessionInfo& a, const SessionInfo& b) {
                  return a.created_time < b.created_time;
              });

    // Delete sessions until we're below LOW_WATER_MARK
    float usage = getUsagePercent();
    size_t deleted_count = 0;

    for (const auto& session : sessions) {
        // Don't delete current session
        if (session.filename == current_session_) {
            continue;
        }

        // Check if we're below low water mark
        usage = getUsagePercent();
        if (usage <= LOW_WATER_MARK * 100.0f) {
            break;
        }

        // Delete session
        if (deleteSession(session.filename.c_str())) {
            deleted_count++;
            ESP_LOGI(TAG, "Deleted session: %s", session.filename.c_str());
        }
    }

    ESP_LOGI(TAG, "Cleanup complete: deleted %u sessions, usage: %.1f%%",
             deleted_count, getUsagePercent());

    return deleted_count > 0;
}

std::vector<SessionInfo> FlashLogger::listSessions() {
    std::vector<SessionInfo> sessions;

    DIR* dir = opendir(base_path_.c_str());
    if (!dir) {
        ESP_LOGE(TAG, "Failed to open directory: %s", base_path_.c_str());
        return sessions;
    }

    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        // Skip non-files
        if (entry->d_type != DT_REG) {
            continue;
        }

        // Check if it's a session file (.opl extension)
        const char* name = entry->d_name;
        size_t len = strlen(name);
        if (len < 4 || strcmp(name + len - 4, ".opl") != 0) {
            continue;
        }

        // Get file info
        std::string filepath = base_path_ + "/" + name;
        struct stat st;
        if (stat(filepath.c_str(), &st) == 0) {
            SessionInfo info;
            info.filename = filepath;
            info.size_bytes = st.st_size;
            info.frame_count = (st.st_size - 4) / FRAME_SIZE; // Approximate (ignores compression)
            info.created_time = st.st_mtime;
            sessions.push_back(info);
        }
    }

    closedir(dir);
    return sessions;
}

bool FlashLogger::deleteSession(const char* filename) {
    if (remove(filename) == 0) {
        return true;
    } else {
        ESP_LOGE(TAG, "Failed to delete session: %s", filename);
        return false;
    }
}

size_t FlashLogger::getTotalUsed() {
    size_t total = 0, used = 0;
    esp_err_t ret = esp_spiffs_info(nullptr, &total, &used);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get SPIFFS info");
        return 0;
    }
    return used;
}

size_t FlashLogger::getTotalSize() {
    size_t total = 0, used = 0;
    esp_err_t ret = esp_spiffs_info(nullptr, &total, &used);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get SPIFFS info");
        return 0;
    }
    return total;
}

float FlashLogger::getUsagePercent() {
    size_t total = getTotalSize();
    size_t used = getTotalUsed();

    if (total == 0) {
        return 0.0f;
    }

    return (float)used / (float)total * 100.0f;
}

} // namespace OpenPony
