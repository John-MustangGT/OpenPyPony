/* settings.c - minimal key=value settings parser
 *
 * Supported file format:
 *  - Lines formatted as: key = value
 *  - Comments start with '#' and are ignored
 *  - Values without quotes are parsed as string; number parsing provided via getters
 *
 * This is intentionally small and robust for embedded use.
 */

#include "settings.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_KV 128
#define MAX_KEY_LEN 64
#define MAX_VAL_LEN 128

typedef struct {
    char key[MAX_KEY_LEN];
    char val[MAX_VAL_LEN];
} kv_t;

static kv_t kvs[MAX_KV];
static int kv_count = 0;

static char *trim(char *s) {
    while (s && *s && isspace((unsigned char)*s)) s++;
    if (!s) return s;
    char *end = s + strlen(s) - 1;
    while (end > s && isspace((unsigned char)*end)) *end-- = '\0';
    return s;
}

bool settings_load(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return false;
    kv_count = 0;
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        /* strip newline */
        char *nl = strchr(p, '\n'); if (nl) *nl = '\0';
        /* skip comments and blank lines */
        char *hash = strchr(p, '#');
        if (hash) *hash = '\0';
        char *eq = strchr(p, '=');
        if (!eq) continue;
        *eq = '\0';
        char *k = trim(p);
        char *v = trim(eq + 1);
        if (!k || !*k) continue;
        if (!v) v = "";
        /* remove surrounding quotes if present */
        if (v[0] == '"' || v[0] == '\'') {
            size_t len = strlen(v);
            if (len >= 2 && v[len-1] == v[0]) {
                v[len-1] = '\0';
                v++;
            }
        }
        if (kv_count < MAX_KV) {
            strncpy(kvs[kv_count].key, k, MAX_KEY_LEN-1);
            kvs[kv_count].key[MAX_KEY_LEN-1] = '\0';
            strncpy(kvs[kv_count].val, v, MAX_VAL_LEN-1);
            kvs[kv_count].val[MAX_VAL_LEN-1] = '\0';
            kv_count++;
        }
    }
    fclose(f);
    return true;
}

static const char *settings_lookup(const char *key) {
    for (int i = 0; i < kv_count; ++i) {
        if (strcmp(kvs[i].key, key) == 0) return kvs[i].val;
    }
    return NULL;
}

int settings_get_int(const char *key, int default_value) {
    const char *v = settings_lookup(key);
    if (!v) return default_value;
    return atoi(v);
}

double settings_get_double(const char *key, double default_value) {
    const char *v = settings_lookup(key);
    if (!v) return default_value;
    return atof(v);
}

float settings_get_float(const char *key, float default_value) {
    const char *v = settings_lookup(key);
    if (!v) return default_value;
    return (float) atof(v);
}

bool settings_get_bool(const char *key, bool default_value) {
    const char *v = settings_lookup(key);
    if (!v) return default_value;
    if (strcasecmp(v, "true") == 0 || strcmp(v, "1") == 0 || strcasecmp(v, "yes") == 0) return true;
    return false;
}

const char *settings_get_string(const char *key, const char *default_value) {
    const char *v = settings_lookup(key);
    if (!v) return default_value;
    return v;
}

void settings_free(void) {
    kv_count = 0;
    /* nothing else to free in current implementation */
}