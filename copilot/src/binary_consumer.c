#include "binary_logger.h"
#include "ring_buffer.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

/*
 Consumer module intended to run on core1.
 It pops samples from the ring buffer and writes them to a .opl session
 using the binary logger implementation above.
*/

void consumer_entry(void); // main entry (used by multicore_launch_core1)

void consumer_entry(void) {
    const char *sd_mount = "/sd"; // adjust as needed; ensure SD is mounted here
    /* Initialize binary logger and start a session */
    opl_init(sd_mount);

    /* Example metadata - adapt to config or session naming scheme */
    const char *session_name = "Track Day";
    const char *driver_name = "John";
    const char *vehicle_id = "Ciara";

    if (!opl_start_session(sd_mount, session_name, driver_name, vehicle_id, 1, 18.5f, 0x12345678)) {
        printf("[BinaryConsumer] Failed to start .opl session\n");
        return;
    }
    printf("[BinaryConsumer] Binary session started\n");

    /* Main consumer loop: pop samples and write to binary logger */
    while (1) {
        opl_sample_t s;
        if (ring_buffer_pop(&s)) {
            uint64_t ts = s.timestamp_us ? s.timestamp_us : (uint64_t) ( (uint64_t) time(NULL) * 1000000ULL );
            if (s.has_gps) {
                /* The Python format expects lat, lon, alt, speed, heading, hdop.
                   We only have speed and lat/lon in the sample struct here; pass 0 for others if unknown */
                opl_write_gps(s.lat, s.lon, 0.0f, s.speed, 0.0f, 0.0f, ts);
            } else {
                opl_write_accel(s.ax, s.ay, s.az, ts);
            }
        } else {
            /* no data - periodically check flush condition and sleep briefly */
            opl_check_flush();
            usleep(1000); // 1ms
        }
    }

    /* Never reached in this sample; if you exit, stop session cleanly */
    opl_stop_session();
}