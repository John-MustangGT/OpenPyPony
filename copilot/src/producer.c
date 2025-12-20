/*
producer.c - Producer (core0) that uses LIS3DH FIFO to push accel samples to ring buffer
               and optionally feeds the hardware watchdog at a configured interval.
*/

#include "producer.h"
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "lis3dh.h"
#include "gps.h"
#include "ring_buffer.h"
#include <stdio.h>
#include <math.h>
#include "pico/time.h"
#include "hardware/watchdog.h"

static int fifo_poll_interval_ms = 50; // default 50ms
static int fifo_watermark = 16;        // default watermark

/* Watchdog feeding */
static int wd_feed_interval_ms = 0; /* 0 = disabled */
static uint64_t wd_last_feed_us = 0;

void producer_set_fifo_params(int poll_ms, int watermark) {
    if (poll_ms > 0) fifo_poll_interval_ms = poll_ms;
    if (watermark >= 1 && watermark <= 31) {
        fifo_watermark = watermark;
        /* reconfigure FIFO if already initialized */
        lis3dh_enable_fifo((uint8_t)fifo_watermark);
    }
}

void producer_set_watchdog_params(int feed_interval_ms) {
    if (feed_interval_ms < 0) feed_interval_ms = 0;
    wd_feed_interval_ms = feed_interval_ms;
    wd_last_feed_us = time_us_64();
}

void producer_init(void) {
    lis3dh_init();
    if (!lis3dh_enable_fifo(fifo_watermark)) {
        printf("[Producer] LIS3DH FIFO enable failed\n");
    } else {
        printf("[Producer] LIS3DH FIFO enabled (watermark=%d)\n", fifo_watermark);
    }
    gps_init();
    ring_buffer_init();
}

/* Poll FIFO and push samples to ring buffer */
static void poll_fifo_and_push(void) {
    const int MAX_BURST = 64;
    float gx[MAX_BURST], gy[MAX_BURST], gz[MAX_BURST];
    int got = lis3dh_read_fifo_samples(MAX_BURST, gx, gy, gz);
    if (got <= 0) return;

    for (int i = 0; i < got; ++i) {
        sample_t s = {0};
        s.timestamp_us = time_us_64();
        s.ax = gx[i]; s.ay = gy[i]; s.az = gz[i];
        s.g_total = sqrtf(s.ax*s.ax + s.ay*s.ay + s.az*s.az);
        s.has_gps = false;
        if (!ring_buffer_push(&s)) {
            /* drop counter handled by ring_buffer */
        }
    }
}

/* Poll GPS and push GPS samples */
static void poll_gps_and_push(void) {
    if (gps_has_fix()) {
        double lat, lon;
        float spd;
        gps_get_last_fix(&lat, &lon, &spd);
        sample_t s = {0};
        s.timestamp_us = time_us_64();
        s.has_gps = true;
        s.lat = lat; s.lon = lon; s.speed = spd;
        ring_buffer_push(&s);
    }
}

void producer_start(void) {
    /* initialize last feed timestamp */
    wd_last_feed_us = time_us_64();

    while (true) {
        poll_fifo_and_push();
        poll_gps_and_push();

        /* Watchdog feeding (if enabled) */
        if (wd_feed_interval_ms > 0) {
            uint64_t now = time_us_64();
            if ((now - wd_last_feed_us) >= (uint64_t)wd_feed_interval_ms * 1000ULL) {
                watchdog_update(); /* kick the hardware watchdog */
                wd_last_feed_us = now;
            }
        }

        sleep_ms(fifo_poll_interval_ms);
    }
}