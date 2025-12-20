#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdint.h>
#include <stdbool.h>

#define RING_BUFFER_CAPACITY 2048  // number of samples (tune as needed)

typedef struct {
    uint32_t timestamp_us;
    float ax, ay, az;    // accelerometer in g
    float g_total;
    double lat, lon;
    float speed;
    bool has_gps;
} sample_t;

void ring_buffer_init(void);
bool ring_buffer_push(const sample_t *s);
bool ring_buffer_pop(sample_t *out);
bool ring_buffer_is_empty(void);
bool ring_buffer_is_full(void);

/* Stats / counters */
uint32_t ring_buffer_get_drop_count(void);
void ring_buffer_reset_counters(void);

#endif // RING_BUFFER_H