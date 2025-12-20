#ifndef BINARY_LOGGER_H
#define BINARY_LOGGER_H

#include <stdint.h>
#include <stdbool.h>

#define OPL_MAX_BLOCK_SIZE 4096
#define OPL_MAX_DATA_PAYLOAD (OPL_MAX_BLOCK_SIZE - 80)

/* Exposed session ID type */
typedef struct {
    uint64_t uuid_part1;
    uint64_t uuid_part2;
} opl_session_id_t;

/* Sample passed between producer/consumer */
typedef struct {
    uint64_t timestamp_us;
    float ax, ay, az;    // accelerometer in g
    float g_total;
    double lat, lon;
    float speed;
    bool has_gps;
} opl_sample_t;

/* Public API */
bool opl_init(const char *mount_path);

/* Start a session. base_path is the SD mount path (e.g., "0:" or "/sd").
   The function will generate a sequential filename session_00001.opl
   (falls back to timestamp-based name if directory scanning not available). */
bool opl_start_session(const char *base_path,
                       const char *session_name,
                       const char *driver_name,
                       const char *vehicle_id,
                       int weather,
                       float ambient_temp,
                       uint32_t config_crc);

/* Add a hardware config item to be written into the session hardware block.
   Should be called before opl_start_session. identifier is string like "LIS3DH@0x18". */
bool opl_add_hardware_item(uint8_t hw_type, uint8_t conn_type, const char *identifier);

/* Write samples */
bool opl_write_accel(float gx, float gy, float gz, uint64_t timestamp_us);
bool opl_write_gps(double lat, double lon, float alt, float speed,
                   float heading, float hdop, uint64_t timestamp_us);

/* Periodic check (time-based flush) */
void opl_check_flush(void);

/* Stop session and finalize file */
void opl_stop_session(void);

/* Runtime configuration setters (defaults are same as prior: 3.0g, 1.0s) */
void opl_set_gforce_threshold(float g);
void opl_set_event_rate_limit(double seconds);

#endif // BINARY_LOGGER_H