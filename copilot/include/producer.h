#ifndef PRODUCER_H
#define PRODUCER_H

#include <stdint.h>

void producer_init(void);
void producer_start(void);

/* Set FIFO polling interval (ms) and LIS3DH FIFO watermark (samples) */
void producer_set_fifo_params(int poll_ms, int watermark);

/* Watchdog feeding: feed_interval_ms = 0 disables feeding from producer.
   If you enable the hardware watchdog in main(), set a feed interval <= timeout_ms. */
void producer_set_watchdog_params(int feed_interval_ms);

#endif