/* binary_logger.c - Binary logging format (FatFS + time_us_64)
 *
 * Changes:
 * - Replaced compile-time thresholds with runtime-configurable variables
 * - Provided opl_set_gforce_threshold() and opl_set_event_rate_limit()
 * - Uses time_us_64() for timestamps (microsecond resolution)
 *
 * Note: This file assumes FatFS (pico-extras) is available and initialized.
 */

#include "binary_logger.h"

#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

#include "ff.h"      /* FatFs */
#include "diskio.h"  /* disk I/O (if needed) */
#include "pico/time.h" /* time_us_64() */

#define MAGIC_BYTES "OPNY"
#define FORMAT_VERSION_MAJOR 2
#define FORMAT_VERSION_MINOR 0
#define HARDWARE_VERSION_MAJOR 1
#define HARDWARE_VERSION_MINOR 0

#define BLOCK_TYPE_SESSION_HEADER 0x01
#define BLOCK_TYPE_DATA           0x02
#define BLOCK_TYPE_SESSION_END    0x03
#define BLOCK_TYPE_HARDWARE_CONFIG 0x04

#define SAMPLE_TYPE_ACCELEROMETER 0x01
#define SAMPLE_TYPE_GPS_FIX       0x02

#define FLUSH_FLAG_TIME  0x01
#define FLUSH_FLAG_SIZE  0x02
#define FLUSH_FLAG_EVENT 0x04

/* Defaults; now runtime-configurable via setter functions */
static float gforce_threshold = 3.0f;
static double event_rate_limit_s = 1.0;

/* Other constants */
#define FLUSH_TIME_THRESHOLD_SECS 300    /* 5 minutes */
#define MAX_BLOCK_SIZE OPL_MAX_BLOCK_SIZE
#define MAX_DATA_PAYLOAD OPL_MAX_DATA_PAYLOAD

#define MAX_HW_ITEMS 32
#define MAX_HW_ID_LEN 31

/* CRC table (lazy init) */
static uint32_t crc_table[256];
static int crc_table_init = 0;

static void init_crc_table(void) {
    if (crc_table_init) return;
    const uint32_t poly = 0xEDB88320UL;
    for (int i = 0; i < 256; ++i) {
        uint32_t crc = i;
        for (int j = 0; j < 8; ++j) {
            if (crc & 1) crc = (crc >> 1) ^ poly;
            else crc >>= 1;
        }
        crc_table[i] = crc;
    }
    crc_table_init = 1;
}

static uint32_t crc32_compute(const uint8_t *data, size_t len) {
    init_crc_table();
    uint32_t crc = 0xFFFFFFFFUL;
    for (size_t i = 0; i < len; ++i) {
        uint8_t b = data[i];
        crc = crc_table[(crc ^ b) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFUL;
}

/* helper little-endian writes */
static void write_le_u16(uint8_t *buf, uint16_t v) { buf[0] = v & 0xFF; buf[1] = (v >> 8) & 0xFF; }
static void write_le_u32(uint8_t *buf, uint32_t v) { buf[0]=v&0xFF; buf[1]=(v>>8)&0xFF; buf[2]=(v>>16)&0xFF; buf[3]=(v>>24)&0xFF; }
static void write_le_u64(uint8_t *buf, uint64_t v) {
    for (int i=0;i<8;i++) buf[i] = (v >> (8*i)) & 0xFF;
}

/* Block builder */
typedef struct {
    uint8_t payload[MAX_DATA_PAYLOAD];
    uint16_t data_size;
    uint16_t sample_count;
    uint8_t flush_flags;
    uint64_t ts_start;
    uint64_t ts_end;
    uint32_t block_sequence;
    uint8_t session_id[16];
} opl_block_t;

static void block_reset(opl_block_t *b) {
    memset(b, 0, sizeof(*b));
    b->data_size = 0;
    b->sample_count = 0;
    b->flush_flags = 0;
    b->ts_start = 0;
    b->ts_end = 0;
}

/* Hardware config item storage */
typedef struct {
    uint8_t hw_type;
    uint8_t conn_type;
    char identifier[MAX_HW_ID_LEN + 1]; // null-terminated
} hw_item_t;

static hw_item_t hw_items[MAX_HW_ITEMS];
static int hw_item_count = 0;

/* Logger global state using FatFs types */
static FIL log_fp; /* FatFs file object */
static bool file_open = false;
static char current_filename[256];
static opl_block_t current_block;
static opl_session_id_t current_session;
static bool logger_active = false;
/* last_flush_time: seconds (double) using time_us_64() / 1e6 */
static double last_flush_time = 0.0;
static double last_event_flush_time = 0.0;

static DIR dir;
static FILINFO fno;

/* Utilities: scan directory using FatFs to compute next session number */
static int get_next_session_number_fatfs(const char *base_path) {
    FRESULT fr;
    int maxn = 0;

    fr = f_opendir(&dir, base_path);
    if (fr != FR_OK) return -1;

    while (1) {
        fr = f_readdir(&dir, &fno);
        if (fr != FR_OK || fno.fname[0] == 0) break; /* error or end */
        const char *name = fno.fname;
        /* Look for files like session_XXXXX.opl */
        if (strncmp(name, "session_", 8) != 0) continue;
        const char *dot = strrchr(name, '.');
        if (!dot) continue;
        if (strcmp(dot, ".opl") != 0) continue;
        size_t len = dot - (name + 8);
        if (len <= 0 || len >= 64) continue;
        char numbuf[64];
        memcpy(numbuf, name + 8, len);
        numbuf[len] = '\0';
        int n = atoi(numbuf);
        if (n > maxn) maxn = n;
    }
    f_closedir(&dir);
    return maxn + 1;
}

/* Add hardware item to list (truncate identifier if needed) */
bool opl_add_hardware_item(uint8_t hw_type, uint8_t conn_type, const char *identifier) {
    if (hw_item_count >= MAX_HW_ITEMS) return false;
    hw_items[hw_item_count].hw_type = hw_type;
    hw_items[hw_item_count].conn_type = conn_type;
    strncpy(hw_items[hw_item_count].identifier, identifier, MAX_HW_ID_LEN);
    hw_items[hw_item_count].identifier[MAX_HW_ID_LEN] = '\0';
    hw_item_count++;
    return true;
}

/* Write hardware config block to file (FatFs) */
static bool write_hardware_block_fatfs(FIL *fp) {
    if (!fp) return false;
    if (hw_item_count == 0) return true; /* nothing to write */

    uint8_t buf[MAX_BLOCK_SIZE];
    size_t pos = 0;

    memcpy(buf + pos, MAGIC_BYTES, 4); pos += 4;
    buf[pos++] = BLOCK_TYPE_HARDWARE_CONFIG;
    buf[pos++] = (uint8_t) hw_item_count;

    for (int i = 0; i < hw_item_count; ++i) {
        hw_item_t *it = &hw_items[i];
        buf[pos++] = it->hw_type;
        buf[pos++] = it->conn_type;
        size_t idlen = strnlen(it->identifier, MAX_HW_ID_LEN);
        buf[pos++] = (uint8_t) idlen;
        if (idlen) {
            memcpy(buf + pos, it->identifier, idlen);
            pos += idlen;
        }
    }

    uint32_t crc = crc32_compute(buf, pos);
    write_le_u32(buf + pos, crc); pos += 4;

    UINT bw;
    FRESULT fr = f_write(fp, buf, pos, &bw);
    if (fr != FR_OK || bw != pos) return false;
    f_sync(fp);
    return true;
}

/* Write session header via FatFs */
static bool write_session_header_fatfs(FIL *fp,
                                 const char *session_name,
                                 const char *driver_name,
                                 const char *vehicle_id,
                                 int weather,
                                 float ambient_temp,
                                 uint32_t config_crc)
{
    if (!fp) return false;
    uint8_t buf[1024];
    size_t pos = 0;

    memcpy(buf + pos, MAGIC_BYTES, 4); pos += 4;
    buf[pos++] = BLOCK_TYPE_SESSION_HEADER;

    buf[pos++] = FORMAT_VERSION_MAJOR;
    buf[pos++] = FORMAT_VERSION_MINOR;
    buf[pos++] = HARDWARE_VERSION_MAJOR;
    buf[pos++] = HARDWARE_VERSION_MINOR;

    uint64_t ts_us = time_us_64();
    write_le_u64(buf + pos, ts_us); pos += 8;

    write_le_u64(buf + pos, current_session.uuid_part1); pos += 8;
    write_le_u64(buf + pos, current_session.uuid_part2); pos += 8;

    size_t sn = session_name ? strnlen(session_name, MAX_SESSION_NAME) : 0;
    if (sn > MAX_SESSION_NAME) sn = MAX_SESSION_NAME;
    buf[pos++] = (uint8_t) sn;
    if (sn) { memcpy(buf + pos, session_name, sn); pos += sn; }

    size_t dn = driver_name ? strnlen(driver_name, MAX_DRIVER_NAME) : 0;
    if (dn > MAX_DRIVER_NAME) dn = MAX_DRIVER_NAME;
    buf[pos++] = (uint8_t) dn;
    if (dn) { memcpy(buf + pos, driver_name, dn); pos += dn; }

    size_t vid = vehicle_id ? strnlen(vehicle_id, MAX_VEHICLE_ID) : 0;
    if (vid > MAX_VEHICLE_ID) vid = MAX_VEHICLE_ID;
    buf[pos++] = (uint8_t) vid;
    if (vid) { memcpy(buf + pos, vehicle_id, vid); pos += vid; }

    buf[pos++] = (uint8_t) weather;
    int16_t amb = (int16_t) (ambient_temp * 10.0f);
    write_le_u16(buf + pos, (uint16_t) amb); pos += 2;

    write_le_u32(buf + pos, config_crc); pos += 4;

    uint32_t header_crc = crc32_compute(buf, pos);
    write_le_u32(buf + pos, header_crc); pos += 4;

    UINT bw;
    FRESULT fr = f_write(fp, buf, pos, &bw);
    if (fr != FR_OK || bw != pos) return false;
    f_sync(fp);
    return true;
}

/* Block serialization and file write (FatFs) */
static bool write_block_to_file_fatfs(FIL *fp, opl_block_t *b) {
    if (!fp || !b) return false;
    if (b->sample_count == 0) return true;

    uint8_t header[128];
    size_t hpos = 0;
    memcpy(header + hpos, MAGIC_BYTES, 4); hpos += 4;
    header[hpos++] = BLOCK_TYPE_DATA;

    memcpy(header + hpos, b->session_id, 16); hpos += 16;

    write_le_u32(header + hpos, b->block_sequence); hpos += 4;
    write_le_u64(header + hpos, b->ts_start); hpos += 8;
    write_le_u64(header + hpos, b->ts_end); hpos += 8;

    header[hpos++] = b->flush_flags;
    write_le_u16(header + hpos, b->sample_count); hpos += 2;
    write_le_u16(header + hpos, b->data_size); hpos += 2;

    size_t tot = hpos + b->data_size;
    uint8_t *tmp = malloc(tot);
    if (!tmp) return false;
    memcpy(tmp, header, hpos);
    memcpy(tmp + hpos, b->payload, b->data_size);
    uint32_t crc = crc32_compute(tmp, tot);
    free(tmp);

    UINT bw;
    FRESULT fr;
    fr = f_write(fp, header, hpos, &bw);
    if (fr != FR_OK || bw != hpos) return false;
    fr = f_write(fp, b->payload, b->data_size, &bw);
    if (fr != FR_OK || bw != b->data_size) return false;

    uint8_t crcbytes[4];
    write_le_u32(crcbytes, crc);
    fr = f_write(fp, crcbytes, 4, &bw);
    if (fr != FR_OK || bw != 4) return false;

    f_sync(fp);
    return true;
}

/* Helpers to add samples to block */
static bool block_add_accel(opl_block_t *b, uint64_t ts_us, float gx, float gy, float gz) {
    if (!b) return false;
    if (b->ts_start == 0) b->ts_start = ts_us;
    b->ts_end = ts_us;
    uint32_t offset_ms = (uint32_t) ((ts_us - b->ts_start) / 1000);
    if (offset_ms > 0xFFFF) offset_ms = 0xFFFF;

    uint8_t header[4];
    header[0] = SAMPLE_TYPE_ACCELEROMETER;
    header[1] = offset_ms & 0xFF;
    header[2] = (offset_ms >> 8) & 0xFF;
    header[3] = 12; /* 3 * float32 */

    if (b->data_size + 4 + 12 > MAX_DATA_PAYLOAD) return false;

    memcpy(b->payload + b->data_size, header, 4);
    b->data_size += 4;

    uint32_t tmp;
    memcpy(&tmp, &gx, 4);
    b->payload[b->data_size++] = tmp & 0xFF; b->payload[b->data_size++] = (tmp>>8)&0xFF; b->payload[b->data_size++] = (tmp>>16)&0xFF; b->payload[b->data_size++] = (tmp>>24)&0xFF;
    memcpy(&tmp, &gy, 4);
    b->payload[b->data_size++] = tmp & 0xFF; b->payload[b->data_size++] = (tmp>>8)&0xFF; b->payload[b->data_size++] = (tmp>>16)&0xFF; b->payload[b->data_size++] = (tmp>>24)&0xFF;
    memcpy(&tmp, &gz, 4);
    b->payload[b->data_size++] = tmp & 0xFF; b->payload[b->data_size++] = (tmp>>8)&0xFF; b->payload[b->data_size++] = (tmp>>16)&0xFF; b->payload[b->data_size++] = (tmp>>24)&0xFF;

    b->sample_count++;
    return true;
}

static bool block_add_gps(opl_block_t *b, uint64_t ts_us, double lat, double lon, float alt, float speed, float heading, float hdop) {
    if (!b) return false;
    if (b->ts_start == 0) b->ts_start = ts_us;
    b->ts_end = ts_us;
    uint32_t offset_ms = (uint32_t) ((ts_us - b->ts_start) / 1000);
    if (offset_ms > 0xFFFF) offset_ms = 0xFFFF;

    const uint8_t payload_len = 8 + 8 + 4 + 4 + 4 + 4; // ddffff = 32
    uint8_t header[4];
    header[0] = SAMPLE_TYPE_GPS_FIX;
    header[1] = offset_ms & 0xFF;
    header[2] = (offset_ms >> 8) & 0xFF;
    header[3] = payload_len;

    if (b->data_size + 4 + payload_len > MAX_DATA_PAYLOAD) return false;

    memcpy(b->payload + b->data_size, header, 4); b->data_size += 4;

    uint64_t tmp64;
    memcpy(&tmp64, &lat, 8);
    for (int i=0;i<8;i++) b->payload[b->data_size++] = (tmp64 >> (8*i)) & 0xFF;
    memcpy(&tmp64, &lon, 8);
    for (int i=0;i<8;i++) b->payload[b->data_size++] = (tmp64 >> (8*i)) & 0xFF;

    uint32_t tmp32;
    memcpy(&tmp32, &alt, 4);
    for (int i=0;i<4;i++) b->payload[b->data_size++] = (tmp32 >> (8*i)) & 0xFF;
    memcpy(&tmp32, &speed, 4);
    for (int i=0;i<4;i++) b->payload[b->data_size++] = (tmp32 >> (8*i)) & 0xFF;
    memcpy(&tmp32, &heading, 4);
    for (int i=0;i<4;i++) b->payload[b->data_size++] = (tmp32 >> (8*i)) & 0xFF;
    memcpy(&tmp32, &hdop, 4);
    for (int i=0;i<4;i++) b->payload[b->data_size++] = (tmp32 >> (8*i)) & 0xFF;

    b->sample_count++;
    return true;
}

/* Public API implementations */

bool opl_init(const char *mount_path) {
    (void) mount_path;
    /* No-op: assume SD mount done elsewhere (e.g., sd_card_mount example).
       If desired, mount logic can be added here using f_mount(). */
    return true;
}

/* Generate sequential filename using FatFs directory scan */
static bool generate_sequential_filename_fatfs(const char *base_path, char *out, size_t out_len) {
    int next = get_next_session_number_fatfs(base_path);
    if (next > 0) {
        int n = snprintf(out, out_len, "%s/session_%05d.opl", base_path, next);
        return (n > 0 && (size_t)n < out_len);
    }
    return false;
}

static void generate_timestamp_filename(const char *base_path, char *out, size_t out_len) {
    uint64_t ts = time_us_64(); /* use microsecond-based time for better uniqueness */
    snprintf(out, out_len, "%s/session_%" PRIu64 ".opl", base_path, ts);
}

static void generate_session_uuid(opl_session_id_t *sid) {
    uint64_t ts = time_us_64();
    sid->uuid_part1 = ts;
    sid->uuid_part2 = ts ^ 0xDEADBEEF12345678ULL;
}

bool opl_start_session(const char *base_path,
                       const char *session_name,
                       const char *driver_name,
                       const char *vehicle_id,
                       int weather,
                       float ambient_temp,
                       uint32_t config_crc)
{
    if (logger_active) opl_stop_session();

    if (!generate_sequential_filename_fatfs(base_path, current_filename, sizeof(current_filename))) {
        generate_timestamp_filename(base_path, current_filename, sizeof(current_filename));
    }

    FRESULT fr = f_open(&log_fp, current_filename, FA_WRITE | FA_CREATE_ALWAYS);
    if (fr != FR_OK) {
        return false;
    }
    file_open = true;

    generate_session_uuid(&current_session);

    block_reset(&current_block);
    current_block.block_sequence = 0;
    memcpy(current_block.session_id, &current_session.uuid_part1, 8);
    memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);

    if (!write_session_header_fatfs(&log_fp, session_name, driver_name, vehicle_id, weather, ambient_temp, config_crc)) {
        f_close(&log_fp); file_open = false;
        return false;
    }

    if (hw_item_count > 0) {
        /* best-effort; continue even if hardware block write fails */
        write_hardware_block_fatfs(&log_fp);
    }

    last_flush_time = (double) time_us_64() / 1e6;
    last_event_flush_time = 0.0;
    logger_active = true;
    return true;
}

bool opl_write_accel(float gx, float gy, float gz, uint64_t timestamp_us) {
    if (!logger_active) return false;
    if (timestamp_us == 0) timestamp_us = time_us_64();
    if (!block_add_accel(&current_block, timestamp_us, gx, gy, gz)) {
        write_block_to_file_fatfs(&log_fp, &current_block);
        current_block.block_sequence++;
        block_reset(&current_block);
        memcpy(current_block.session_id, &current_session.uuid_part1, 8);
        memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);
        if (!block_add_accel(&current_block, timestamp_us, gx, gy, gz)) return false;
    }

    float gtot = sqrtf(gx*gx + gy*gy + gz*gz);

    if (gtot >= gforce_threshold) {
        /* Rate-limit forced (g-force) flushes to at most one per event_rate_limit_s seconds */
        double now = (double) time_us_64() / 1e6;
        if (now - last_event_flush_time >= event_rate_limit_s) {
            current_block.flush_flags |= FLUSH_FLAG_EVENT;
            write_block_to_file_fatfs(&log_fp, &current_block);
            current_block.block_sequence++;
            block_reset(&current_block);
            memcpy(current_block.session_id, &current_session.uuid_part1, 8);
            memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);
            last_flush_time = (double) time_us_64() / 1e6;
            last_event_flush_time = now;
        } else {
            /* Skip immediate flush due to rate limit: sample remains in current block */
        }
    } else if (current_block.data_size >= (int)(MAX_DATA_PAYLOAD * 0.9f)) {
        current_block.flush_flags |= FLUSH_FLAG_SIZE;
        write_block_to_file_fatfs(&log_fp, &current_block);
        current_block.block_sequence++;
        block_reset(&current_block);
        memcpy(current_block.session_id, &current_session.uuid_part1, 8);
        memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);
        last_flush_time = (double) time_us_64() / 1e6;
    }

    return true;
}

bool opl_write_gps(double lat, double lon, float alt, float speed,
                   float heading, float hdop, uint64_t timestamp_us)
{
    if (!logger_active) return false;
    if (timestamp_us == 0) timestamp_us = time_us_64();
    if (!block_add_gps(&current_block, timestamp_us, lat, lon, alt, speed, heading, hdop)) {
        write_block_to_file_fatfs(&log_fp, &current_block);
        current_block.block_sequence++;
        block_reset(&current_block);
        memcpy(current_block.session_id, &current_session.uuid_part1, 8);
        memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);
        if (!block_add_gps(&current_block, timestamp_us, lat, lon, alt, speed, heading, hdop)) return false;
    }
    return true;
}

void opl_check_flush(void) {
    if (!logger_active) return;
    double now = (double) time_us_64() / 1e6;
    if (now - last_flush_time >= FLUSH_TIME_THRESHOLD_SECS) {
        current_block.flush_flags |= FLUSH_FLAG_TIME;
        write_block_to_file_fatfs(&log_fp, &current_block);
        current_block.block_sequence++;
        block_reset(&current_block);
        memcpy(current_block.session_id, &current_session.uuid_part1, 8);
        memcpy(current_block.session_id + 8, &current_session.uuid_part2, 8);
        last_flush_time = now;
    }
}

void opl_stop_session(void) {
    if (!logger_active) return;
    if (current_block.sample_count > 0) {
        write_block_to_file_fatfs(&log_fp, &current_block);
    }
    /* write session end marker: MAGIC + BLOCK_TYPE_SESSION_END + session_id */
    uint8_t endbuf[4 + 1 + 16];
    memcpy(endbuf, MAGIC_BYTES, 4);
    endbuf[4] = BLOCK_TYPE_SESSION_END;
    memcpy(endbuf + 5, &current_session.uuid_part1, 8);
    memcpy(endbuf + 5 + 8, &current_session.uuid_part2, 8);

    UINT bw;
    f_write(&log_fp, endbuf, sizeof(endbuf), &bw);
    f_sync(&log_fp);
    f_close(&log_fp);
    file_open = false;
    logger_active = false;

    /* clear hardware items so next session can repopulate if desired */
    hw_item_count = 0;
    memset(hw_items, 0, sizeof(hw_items));
}

/* Setters for runtime configuration */
void opl_set_gforce_threshold(float g) {
    if (g > 0.0f) gforce_threshold = g;
}
void opl_set_event_rate_limit(double seconds) {
    if (seconds >= 0.0) event_rate_limit_s = seconds;
}