#include "ring_buffer.h"
#include <string.h>
#include "pico/stdlib.h"
#include "pico/mutex.h"

static sample_t buffer[RING_BUFFER_CAPACITY];
static volatile uint32_t head = 0;
static volatile uint32_t tail = 0;
static mutex_t rb_mutex;

/* Counters */
static volatile uint32_t drop_count = 0;

void ring_buffer_init(void) {
    mutex_init(&rb_mutex);
    head = tail = 0;
    drop_count = 0;
}

static inline uint32_t next_index(uint32_t i) {
    return (i + 1) % RING_BUFFER_CAPACITY;
}

bool ring_buffer_is_empty(void) {
    return head == tail;
}

bool ring_buffer_is_full(void) {
    return next_index(head) == tail;
}

bool ring_buffer_push(const sample_t *s) {
    bool ok = false;
    mutex_enter_blocking(&rb_mutex);
    if (!ring_buffer_is_full()) {
        buffer[head] = *s;
        head = next_index(head);
        ok = true;
    } else {
        drop_count++;
    }
    mutex_exit(&rb_mutex);
    return ok;
}

bool ring_buffer_pop(sample_t *out) {
    bool ok = false;
    mutex_enter_blocking(&rb_mutex);
    if (!ring_buffer_is_empty()) {
        *out = buffer[tail];
        tail = next_index(tail);
        ok = true;
    }
    mutex_exit(&rb_mutex);
    return ok;
}

uint32_t ring_buffer_get_drop_count(void) {
    return drop_count;
}

void ring_buffer_reset_counters(void) {
    drop_count = 0;
}