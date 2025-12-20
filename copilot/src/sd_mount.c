/*
sd_mount.c - SPI initialization + SD card mount helper for Pico (pico-extras + FatFS)

Behavior:
- Initializes SPI0 using common Pico SPI pins (user may override CS pin by passing cs_pin).
- Calls pico-extras SD init helper if available, then mounts the FatFS filesystem.
- Returns true on success.

Important:
- This file uses FatFS (ff.h) APIs and (optionally) pico-extras SD helpers.
- If your pico-extras exposes a different SD init API name, change the call in sd_mount_helper.
- The mount_point parameter should be the FatFs drive path used by your environment (commonly "0:" in pico-extras examples).
*/

#include "sd_mount.h"

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/spi.h"
#include "ff.h"
#include "pico/time.h"

/* If you have pico-extras sd_card helper header available, include it and
   enable the SD init call. Example: #include "sd_card.h"
   Uncomment the include below if your pico-extras provides sd_card_init() or similar.
*/
// #include "sd_card.h"

/* Default SPI pins for Pico/standard breakout (change if your wiring differs) */
#ifndef SD_SPI_PORT
#define SD_SPI_PORT spi0
#endif
#ifndef SD_SPI_SCK_PIN
#define SD_SPI_SCK_PIN 18  /* GP18 */
#endif
#ifndef SD_SPI_MOSI_PIN
#define SD_SPI_MOSI_PIN 19 /* GP19 */
#endif
#ifndef SD_SPI_MISO_PIN
#define SD_SPI_MISO_PIN 16 /* GP16 */
#endif

/* FatFS filesystem object (kept static for lifetime) */
static FATFS fs;

/* Try to initialize SD card block device if pico-extras helper is present.
   If not present, we still configure SPI pins and attempt f_mount; many
   examples require calling the sd card init helper prior to mount.
   Adjust the call below to match your pico-extras version if needed.
*/
static bool sd_card_init_platform(int cs_pin) {
    /* Configure SPI interface */
    spi_init(SD_SPI_PORT, 25 * 1000 * 1000); /* 25 MHz, adjust as needed */
    gpio_set_function(SD_SPI_SCK_PIN, GPIO_FUNC_SPI);
    gpio_set_function(SD_SPI_MOSI_PIN, GPIO_FUNC_SPI);
    gpio_set_function(SD_SPI_MISO_PIN, GPIO_FUNC_SPI);

    /* Configure CS pin as output and deassert */
    gpio_init(cs_pin);
    gpio_set_dir(cs_pin, GPIO_OUT);
    gpio_put(cs_pin, 1);

    /* If your pico-extras provides an sd_card_init() / sd_init() helper, call it here.
       Example (pico-extras sd_card API):
         if (!sd_init()) return false;
       Or if it's sd_card_init(spi, cs_pin) use that signature.

       The code below assumes the helper is not available and falls back to just
       SPI pin init + letting f_mount succeed (assuming lower level driver is configured).
    */

    /* If you do have the helper, uncomment and replace the call below with the correct API:
    if (!sd_card_init_helper(SD_SPI_PORT, cs_pin)) {
        return false;
    }
    */

    /* If no helper is available, return true to allow attempting f_mount.
       The actual SD driver that services diskio must have been registered
       (this typically happens when you build and link pico-extras SD glue).
    */
    return true;
}

bool sd_mount_helper(const char *mount_point, int cs_pin) {
    if (!mount_point) return false;

    printf("[SD] Initializing SPI for SD card (CS pin %d)...\n", cs_pin);
    if (!sd_card_init_platform(cs_pin)) {
        printf("[SD] SD platform init failed\n");
        return false;
    }

    /* Attempt to mount the filesystem */
    FRESULT fr = f_mount(&fs, mount_point, 1);
    if (fr == FR_OK) {
        printf("[SD] Mounted FatFS at %s\n", mount_point);
        return true;
    } else {
        printf("[SD] f_mount failed: %d\n", fr);
        /* Possible causes:
           - underlying block device/driver not initialized (call sd_card_init helper)
           - SD card missing or not inserted
           - wrong mount_point string (use "0:" or "/sd" depending on configuration)
        */
        return false;
    }
}