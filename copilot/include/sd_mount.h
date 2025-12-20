#ifndef SD_MOUNT_H
#define SD_MOUNT_H

#include <stdbool.h>

/* mount_point - FatFS mount path / drive (e.g., "0:" for FatFS or "/sd" if configured)
 * cs_pin      - Chip Select GPIO pin for the SD card (e.g., 17 for GP17)
 *
 * Returns true on success (SD initialized and filesystem mounted), false on error.
 */
bool sd_mount_helper(const char *mount_point, int cs_pin);

#endif // SD_MOUNT_H