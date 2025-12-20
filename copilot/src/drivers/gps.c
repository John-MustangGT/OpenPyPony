#include "gps.h"
#include <stdio.h>
#include <string.h>
#include "hardware/uart.h"
#include "pico/stdlib.h"

#define UART_PORT uart1
#define GPS_BAUD 9600

static volatile double last_lat = 0.0;
static volatile double last_lon = 0.0;
static volatile float last_speed = 0.0;
static volatile bool have_fix = false;

static void uart_irq() {
    // Simple line reader; on real device use a proper NMEA parser
    static char linebuf[128];
    static int idx = 0;
    while (uart_is_readable(UART_PORT)) {
        char c = uart_getc(UART_PORT);
        if (c == '\n' || idx >= (int)sizeof(linebuf)-1) {
            linebuf[idx] = '\0';
            // rudimentary: parse $GPRMC lat/lon/speed (comma-separated)
            if (strstr(linebuf, "$GPRMC") != NULL) {
                // Tokenize and extract fields: time,status,lat,N,lon,E,speed_knots,course,date,...
                char *p = linebuf;
                int field = 0;
                char *tok;
                char tmp[128];
                strncpy(tmp, linebuf, sizeof(tmp)-1);
                tmp[sizeof(tmp)-1] = '\0';
                tok = strtok(tmp, ",");
                double lat = 0.0, lon = 0.0;
                float spd = 0.0;
                bool valid = false;
                while (tok) {
                    // field indexes (GPRMC): 2=status,3=lat,4=N/S,5=lon,6=E/W,7=speed
                    if (field == 2) { if (tok[0]=='A') valid = true; } // simplistic
                    if (field == 3) { lat = atof(tok); }
                    if (field == 4 && tok[0]=='S') lat = -lat;
                    if (field == 5) { lon = atof(tok); }
                    if (field == 6 && tok[0]=='W') lon = -lon;
                    if (field == 7) spd = atof(tok); // knots
                    tok = strtok(NULL, ","); field++;
                }
                if (valid) {
                    // convert lat/lon from DDMM.MMMM to degrees if needed; simplified here
                    last_lat = lat; last_lon = lon; last_speed = spd * 0.514444f;
                    have_fix = true;
                }
            }
            idx = 0;
        } else {
            linebuf[idx++] = c;
        }
    }
}

void gps_init(void) {
    uart_init(UART_PORT, GPS_BAUD);
    // configure pins in main; attach irq here
    irq_set_exclusive_handler(UART1_IRQ, uart_irq);
    irq_set_enabled(UART1_IRQ, true);
    uart_set_irq_enables(UART_PORT, true, false);
}

bool gps_has_fix(void) {
    return have_fix;
}

void gps_get_last_fix(double *lat, double *lon, float *speed) {
    if (lat) *lat = last_lat;
    if (lon) *lon = last_lon;
    if (speed) *speed = last_speed;
}