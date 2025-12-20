#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/uart.h"
#include "pico/multicore.h"
#include "hardware/watchdog.h"

#include "producer.h"
#include "consumer.h"
#include "settings.h"

/* Board-specific pin choices — update for your wiring */
#define I2C_SDA_PIN 8    // example: GP8
#define I2C_SCL_PIN 9
#define I2C_BAUDRATE 400000

/* UART pins for GPS — update to match your board wiring */
#define GPS_UART_TX_PIN 0
#define GPS_UART_RX_PIN 1

int main() {
    stdio_init_all();
    sleep_ms(2000);
    printf("OpenPony RP2x Producer/Consumer booting...\n");

    /* Try loading settings from SD (optional). If SD not mounted yet, settings_load will fail
       silently and defaults will be used. */
    bool settings_ok = settings_load("0:/settings.toml") || settings_load("/sd/settings.toml");
    if (settings_ok) {
        printf("Settings loaded from SD\n");
    } else {
        printf("No settings file found or SD not mounted — using defaults\n");
    }

    /* Read watchdog config from settings (or use defaults) */
    bool wd_enabled = settings_get_bool("WATCHDOG_ENABLE", true);
    int wd_timeout_ms = settings_get_int("WATCHDOG_TIMEOUT_MS", 5000);
    int wd_feed_ms = settings_get_int("WATCHDOG_FEED_INTERVAL_MS", 1000);

    if (wd_enabled) {
        /* Enable watchdog: timeout in ms, pause on debug true to avoid resets while debugging */
        watchdog_enable((uint32_t)wd_timeout_ms, true);
        /* Configure producer to feed watchdog at the requested interval */
        producer_set_watchdog_params(wd_feed_ms);
        printf("Watchdog enabled: timeout=%d ms, feed_interval=%d ms\n", wd_timeout_ms, wd_feed_ms);
    } else {
        producer_set_watchdog_params(0); /* disable feeding */
        printf("Watchdog disabled by settings\n");
    }

    /* Initialize I2C (used by LIS3DH) */
    i2c_init(i2c0, I2C_BAUDRATE);
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);

    /* Initialize GPS UART pins (UART1 used in gps.c but adapt as needed) */
    uart_init(uart1, 9600);
    gpio_set_function(GPS_UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(GPS_UART_RX_PIN, GPIO_FUNC_UART);

    /* Initialize producer; this sets up LIS3DH FIFO, GPS IRQ, and ring buffer */
    producer_init();

    /* Launch consumer on core 1 (it will mount SD and start session) */
    multicore_launch_core1(consumer_entry);

    /* Start producer main loop on core 0 (blocking) */
    producer_start();

    return 0;
}