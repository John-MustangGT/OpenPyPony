/* lis3dh.c - LIS3DH helper with FIFO support (static buffer)
 *
 * Replaced dynamic allocation with a static buffer to avoid malloc in embedded runtime.
 */

#include "lis3dh.h"
#include <stdio.h>
#include "hardware/i2c.h"
#include "pico/stdlib.h"

#define I2C_PORT i2c0
#define LIS3DH_ADDR 0x18

#define LIS3DH_REG_CTRL1 0x20
#define LIS3DH_REG_CTRL4 0x23
#define LIS3DH_REG_CTRL5 0x24
#define LIS3DH_REG_FIFO_CTRL 0x2E
#define LIS3DH_REG_FIFO_SRC 0x2F
#define LIS3DH_REG_OUT_X_L 0x28

#define LIS3DH_MAX_BURST 64
#define LIS3DH_MAX_BURST_BYTES (LIS3DH_MAX_BURST * 6)

/* existing init & simple read (kept) */
bool lis3dh_init(void) {
    uint8_t ctrl1[2] = {LIS3DH_REG_CTRL1, 0x57}; // 100Hz, all axes enabled
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, ctrl1, 2, false) < 0) {
        printf("LIS3DH ctrl1 write failed\n");
    }
    sleep_ms(10);
    uint8_t ctrl4[2] = {LIS3DH_REG_CTRL4, 0x00}; // ±2g, continuous update
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, ctrl4, 2, false) < 0) {
        printf("LIS3DH ctrl4 write failed\n");
    }
    return true;
}

bool lis3dh_read_g(float *gx, float *gy, float *gz) {
    uint8_t reg = LIS3DH_REG_OUT_X_L | 0x80; // auto-increment
    uint8_t buf[6];
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, &reg, 1, true) < 0) return false;
    if (i2c_read_blocking(I2C_PORT, LIS3DH_ADDR, buf, 6, false) < 0) return false;
    int16_t rx = (int16_t)((buf[1] << 8) | buf[0]);
    int16_t ry = (int16_t)((buf[3] << 8) | buf[2]);
    int16_t rz = (int16_t)((buf[5] << 8) | buf[4]);
    const float sensitivity = 0.000061f; // g per LSB for ±2g
    *gx = rx * sensitivity;
    *gy = ry * sensitivity;
    *gz = rz * sensitivity;
    return true;
}

/* Enable FIFO in stream mode with given watermark (1..31).
 * Returns true on success.
 */
bool lis3dh_enable_fifo(uint8_t watermark) {
    if (watermark > 31) watermark = 31;
    uint8_t ctrl5_reg[2];
    // Read CTRL_REG5, set FIFO_EN bit (bit 6)
    ctrl5_reg[0] = LIS3DH_REG_CTRL5;
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, ctrl5_reg, 1, true) < 0) return false;
    if (i2c_read_blocking(I2C_PORT, LIS3DH_ADDR, ctrl5_reg+1, 1, false) < 0) return false;
    ctrl5_reg[1] |= (1 << 6); // set FIFO_EN
    uint8_t write5[2] = {LIS3DH_REG_CTRL5, ctrl5_reg[1]};
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, write5, 2, false) < 0) return false;

    // FIFO_CTRL: FM = 10 (stream mode) -> bits 7:6 = 10b => (2<<6) = 0x80
    uint8_t fifo_ctrl = (2 << 6) | (watermark & 0x1F);
    uint8_t write_fifo[2] = {LIS3DH_REG_FIFO_CTRL, fifo_ctrl};
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, write_fifo, 2, false) < 0) return false;

    return true;
}

/* Return number of samples currently in FIFO (0..31), or -1 on error */
int lis3dh_fifo_count(void) {
    uint8_t reg = LIS3DH_REG_FIFO_SRC;
    uint8_t val;
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, &reg, 1, true) < 0) return -1;
    if (i2c_read_blocking(I2C_PORT, LIS3DH_ADDR, &val, 1, false) < 0) return -1;
    int cnt = val & 0x1F;
    return cnt;
}

/* Read up to max_samples from FIFO into provided arrays; returns number of samples read.
 * For each sample the driver fills gx[i],gy[i],gz[i] (in g).
 * Uses a static buffer to avoid malloc.
 */
int lis3dh_read_fifo_samples(int max_samples, float *gx, float *gy, float *gz) {
    int avail = lis3dh_fifo_count();
    if (avail <= 0) return 0;
    if (avail > max_samples) avail = max_samples;
    if (avail > LIS3DH_MAX_BURST) avail = LIS3DH_MAX_BURST;

    /* static buffer sized for the maximum burst - safe since called from producer core only */
    static uint8_t buf[LIS3DH_MAX_BURST_BYTES];
    uint8_t reg = LIS3DH_REG_OUT_X_L | 0x80;
    int bytes = avail * 6;
    if (i2c_write_blocking(I2C_PORT, LIS3DH_ADDR, &reg, 1, true) < 0) return 0;
    if (i2c_read_blocking(I2C_PORT, LIS3DH_ADDR, buf, bytes, false) < 0) return 0;

    const float sensitivity = 0.000061f; // g per LSB for ±2g
    for (int i = 0; i < avail; ++i) {
        int idx = i * 6;
        int16_t rx = (int16_t)((buf[idx+1] << 8) | buf[idx+0]);
        int16_t ry = (int16_t)((buf[idx+3] << 8) | buf[idx+2]);
        int16_t rz = (int16_t)((buf[idx+5] << 8) | buf[idx+4]);
        gx[i] = rx * sensitivity;
        gy[i] = ry * sensitivity;
        gz[i] = rz * sensitivity;
    }
    return avail;
}