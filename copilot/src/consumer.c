#include "consumer.h"
#include "ring_buffer.h"
#include "pico/stdlib.h"
#include <stdio.h>
#include <string.h>

// FatFS headers & SD init must be added to your project
// #include "ff.h"

void consumer_write_csv_line(const sample_t *s) {
    // Placeholder: write CSV to SD card
    // Use FatFS: f_write, etc. Example CSV:
    // TIMESTAMP_US,AX,AY,AZ,G_TOTAL,LAT,LON,SPEED,HAS_GPS\n
    char line[256];
    int n = snprintf(line, sizeof(line), "%lu,%.3f,%.3f,%.3f,%.3f,%.6f,%.6f,%.2f,%d\n",
        (unsigned long)s->timestamp_us, s->ax, s->ay, s->az, s->g_total,
        s->lat, s->lon, s->speed, s->has_gps ? 1 : 0);
    // TODO: write to file on SD with FatFS
    // f_write(&fp, line, n, &bw);
    // For now, print to console for debugging
    printf("%s", line);
}

void consumer_entry(void) {
    // Initialize SD/FAT here (spi, mount, open file)
    // mount filesystem and open session file, e.g., /sd/session_00001.csv

    while (true) {
        sample_t s;
        if (ring_buffer_pop(&s)) {
            consumer_write_csv_line(&s);
        } else {
            // No data; wait a short time
            sleep_ms(1);
        }
    }
}