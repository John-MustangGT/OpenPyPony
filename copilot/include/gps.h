#ifndef GPS_H
#define GPS_H

#include <stdbool.h>

void gps_init(void);
bool gps_has_fix(void);
void gps_get_last_fix(double *lat, double *lon, float *speed);

#endif // GPS_H