#ifndef LIS3DH_H
#define LIS3DH_H

#include <stdint.h>
#include <stdbool.h>

bool lis3dh_init(void);                 // initialize I2C and device
bool lis3dh_read_g(float *gx, float *gy, float *gz); // returns in g units

#endif // LIS3DH_H