#ifndef SETTINGS_H
#define SETTINGS_H

#include <stdbool.h>

/* Load settings file from given path (e.g., "/sd/settings.toml" or "0:/settings.toml").
   Returns true on success, false on failure. */
bool settings_load(const char *path);

/* Getter helpers */
int settings_get_int(const char *key, int default_value);
double settings_get_double(const char *key, double default_value);
float settings_get_float(const char *key, float default_value);
bool settings_get_bool(const char *key, bool default_value);
const char *settings_get_string(const char *key, const char *default_value);

/* Free any allocated resources (optional) */
void settings_free(void);

#endif // SETTINGS_H