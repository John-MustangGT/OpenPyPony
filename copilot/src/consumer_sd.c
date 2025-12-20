/* consumer_sd.c - Consumer (core1) that mounts SD, loads settings, and starts binary logging
 *
 * This version loads /sd/settings.toml (or "0:/settings.toml" depending on mount)
 * and applies configurable parameters:
 *   - GFORCE_EVENT_THRESHOLD (float)
 *   - EVENT_RATE_LIMIT_S (float)
 *   - FIFO_POLL_MS (int)
 *   - FIFO_WATERMARK (int)
 *
 * The settings parser is minimal and supports key = value lines.
 */

#include "consumer.h"
#include "binary_logger.h"
#include "ring_buffer.h"
#include "settings.h"
#include "producer.h"

#include <stdio.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "ff.h"

/* sd_mount_helper from src/sd_mount.c */
bool sd_mount_helper(const char *mount_point, int cs_pin);

void consumer_entry(void) {
    const char *mount_point = "0:"; /* fatfs drive (pico-extras examples) */
    int sd_cs_pin = 17; /* default CS pin (GP17) */

    printf("[Consumer] attempting SD mount at %s\n", mount_point);
    if (!sd_mount_helper(mount_point, sd_cs_pin)) {
        printf("[Consumer] SD mount failed; continuing without persistence\n");
    } else {
        printf("[Consumer] SD mounted\n");
    }

    /* Load settings from SD if present */
    /* Try typical path first */
    const char *settings_path = "0:/settings.toml";
    if (!settings_load(settings_path)) {
        /* fallback to /sd/settings.toml if your mount uses that */
        settings_path = "/sd/settings.toml";
        (void) settings_load(settings_path); /* ignore failure */
    }

    /* Read configured values and apply them */
    float cfg_gforce = settings_get_float("GFORCE_EVENT_THRESHOLD", 3.0f);
    float cfg_event_rate = settings_get_float("EVENT_RATE_LIMIT_S", 1.0f);
    int cfg_fifo_poll = settings_get_int("FIFO_POLL_MS", 50);
    int cfg_fifo_wm = settings_get_int("FIFO_WATERMARK", 16);

    printf("[Consumer] settings: GFORCE=%.2f EVENT_RATE=%.2f FIFO_POLL=%d FIFO_WM=%d\n",
           cfg_gforce, cfg_event_rate, cfg_fifo_poll, cfg_fifo_wm);

    opl_set_gforce_threshold(cfg_gforce);
    opl_set_event_rate_limit((double)cfg_event_rate);
    producer_set_fifo_params(cfg_fifo_poll, cfg_fifo_wm);

    /* Add hardware config entries (example) - call before starting session */
    opl_add_hardware_item(0x01 /* HW_TYPE_ACCELEROMETER */, 0x01 /* CONN_TYPE_I2C */, "LIS3DH@0x18");
    opl_add_hardware_item(0x02 /* HW_TYPE_GPS */, 0x03 /* CONN_TYPE_UART */, "ATGM336H TX:GP0 RX:GP1");

    /* Start session */
    if (!opl_start_session(mount_point, "Track Day", "John", "Ciara", 1 /* WEATHER_CLEAR */, 18.5f, 0x12345678)) {
        printf("[Consumer] Failed to start .opl session\n");
    } else {
        printf("[Consumer] .opl session started\n");
    }

    /* Consumer loop: pop samples from ring buffer and write to binary logger */
    while (true) {
        sample_t s;
        if (ring_buffer_pop(&s)) {
            uint64_t ts = s.timestamp_us ? s.timestamp_us : time_us_64();
            if (s.has_gps) {
                opl_write_gps(s.lat, s.lon, 0.0f, s.speed, 0.0f, 0.0f, ts);
            } else {
                opl_write_accel(s.ax, s.ay, s.az, ts);
            }
        } else {
            opl_check_flush();
            sleep_ms(5);
        }
    }

    /* unreachable but tidy */
    opl_stop_session();
}