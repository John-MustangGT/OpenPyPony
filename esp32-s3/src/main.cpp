// src/main.cpp
// OpenPonyLogger ESP32-S3 Main Application
// Pure ESP-IDF implementation with native FreeRTOS

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <inttypes.h>

// ESP-IDF core
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"

// ESP-IDF drivers
#include "driver/i2c.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"

// ESP-IDF WiFi/networking
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "lwip/sockets.h"

// Project includes
#include "config.h"
#include "logger.h"
#include "webserver.h"
#include "interfaces/gps_interface.h"
#include "interfaces/imu_interface.h"
#include "interfaces/magnetometer_interface.h"
#include "interfaces/display_interface.h"
#include "interfaces/battery_interface.h"
#include "interfaces/vehicle_interface.h"

// Concrete sensor implementations
#include "sensors/pa1010d.h"
#include "sensors/icm20948.h"
#include "hardware/feather_battery.h"

// TODO: Display implementation
// #include "hardware/st7789_display.h"

using namespace OpenPony;

// ============================================================================
// Configuration & Constants
// ============================================================================

static const char *TAG = "OpenPony";

// I2C Configuration (STEMMA QT on Feather)
#define I2C_MASTER_SCL_IO           GPIO_NUM_4      // Feather I2C SCL
#define I2C_MASTER_SDA_IO           GPIO_NUM_3      // Feather I2C SDA
#define I2C_PWR_IO                  GPIO_NUM_7      // Power control for sensors
#define I2C_MASTER_NUM              I2C_NUM_0
#define I2C_MASTER_FREQ_HZ          400000          // 400 kHz Fast Mode
#define I2C_MASTER_TIMEOUT_MS       1000

// TFT Display SPI (on Feather Reverse - display on BOTTOM, always visible!)
#define TFT_SPI_HOST               SPI3_HOST
#define TFT_PIN_MOSI               GPIO_NUM_35
#define TFT_PIN_CLK                GPIO_NUM_36
#define TFT_PIN_CS                 GPIO_NUM_7
#define TFT_PIN_DC                 GPIO_NUM_39
#define TFT_PIN_RST                GPIO_NUM_40
#define TFT_PIN_BL                 GPIO_NUM_45     // Backlight

// No SD card - using flash storage (4-5 MB available)

// Task priorities (0 = lowest, configMAX_PRIORITIES-1 = highest)
#define PRIORITY_SENSOR_TASK        3              // High priority
#define PRIORITY_LOGGING_TASK       2              // Medium priority
#define PRIORITY_WIFI_TASK          1              // Low priority

// Task stack sizes
#define STACK_SIZE_SENSOR           4096
#define STACK_SIZE_LOGGING          4096
#define STACK_SIZE_WIFI             8192           // WiFi needs more stack

// ============================================================================
// Global Objects
// ============================================================================

Config config;
FlashLogger* logger = nullptr;
WebSocketTelemetryServer* telemetry_server = nullptr;

// Sensor interfaces (will be initialized in setup)
GPSInterface* gps = nullptr;
IMUInterface* imu = nullptr;
MagnetometerInterface* mag = nullptr;
DisplayInterface* display = nullptr;
BatteryInterface* battery = nullptr;
VehicleInterface* vehicle = nullptr;

// FreeRTOS synchronization
SemaphoreHandle_t sensor_data_mutex = nullptr;
QueueHandle_t log_queue = nullptr;

// Shared sensor data (protected by mutex)
struct SensorData {
    Position gps_position;
    float gps_speed;
    float gps_track;
    uint8_t gps_satellites;
    GPSTime gps_time;
    bool gps_fix;
    FixType gps_fix_type;
    float gps_hdop;

    Vector3 accel;
    Vector3 gyro;
    float heading;

    std::vector<SatelliteInfo> satellite_details;
    int64_t timestamp_us;
    bool data_ready;
} shared_sensor_data;

// Statistics
volatile uint32_t sensor_loop_count = 0;
volatile uint32_t frames_logged = 0;
volatile uint32_t telemetry_sent = 0;

// ============================================================================
// I2C Bus Initialization
// ============================================================================

static esp_err_t i2c_master_init(void)
{
    i2c_config_t conf = {};
    conf.mode = I2C_MODE_MASTER;
    conf.sda_io_num = I2C_MASTER_SDA_IO;
    conf.scl_io_num = I2C_MASTER_SCL_IO;
    conf.sda_pullup_en = GPIO_PULLUP_ENABLE;
    conf.scl_pullup_en = GPIO_PULLUP_ENABLE;
    conf.master.clk_speed = I2C_MASTER_FREQ_HZ;
    conf.clk_flags = 0;
    
    gpio_set_direction(I2C_PWR_IO, GPIO_MODE_OUTPUT);
    gpio_set_level(I2C_PWR_IO, 1);

    esp_err_t err = i2c_param_config(I2C_MASTER_NUM, &conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C param config failed: %s", esp_err_to_name(err));
        return err;
    }

    err = i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2C driver install failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "I2C bus initialized at %d Hz", I2C_MASTER_FREQ_HZ);
    return ESP_OK;
}

// ============================================================================
// Storage Management
// ============================================================================

// Check flash storage and cleanup if needed (90% → 60% policy)
static void check_flash_storage(void* parameter)
{
    while (true) {
        // Check every 30 seconds
        vTaskDelay(pdMS_TO_TICKS(30000));

        if (logger) {
            float usage = logger->getUsagePercent();
            ESP_LOGI(TAG, "Flash usage: %.1f%%", usage * 100);

            if (usage >= HIGH_WATER_MARK) {
                ESP_LOGW(TAG, "Flash at %.1f%% - cleaning up old sessions...", usage * 100);
                if (logger->cleanupOldSessions()) {
                    ESP_LOGI(TAG, "Cleanup complete - now at %.1f%%", logger->getUsagePercent() * 100);
                } else {
                    ESP_LOGE(TAG, "Cleanup failed!");
                }
            }
        }
    }
}

// ============================================================================
// FreeRTOS Tasks
// ============================================================================

// Task 1: Sensor Reading (Core 1, high priority)
static void sensor_task(void* parameter)
{
    ESP_LOGI(TAG, "Sensor task started on core %d", xPortGetCoreID());

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t sensor_period = pdMS_TO_TICKS(100);  // 10 Hz

    while (true) {
        // Update GPS (call frequently, it handles its own throttling)
        if (gps) {
            gps->update();
        }

        // Read sensor data
        SensorData local_data = {};
        local_data.timestamp_us = esp_timer_get_time();

        if (gps && gps->hasFix()) {
            local_data.gps_position = gps->getPosition();
            local_data.gps_speed = gps->getSpeed();
            local_data.gps_track = gps->getTrack();
            local_data.gps_satellites = gps->getSatellites();
            local_data.gps_time = gps->getTime();
            local_data.gps_fix = true;
            local_data.gps_fix_type = gps->getFixType();
            local_data.gps_hdop = gps->getHDOP();
        } else {
            local_data.gps_fix = false;
        }

        if (imu) {
            local_data.accel = imu->readGForce();
            local_data.gyro = imu->readRotation();
        }

        if (mag) {
            local_data.heading = mag->getHeading();
        }

        local_data.data_ready = true;

        // Copy to shared data (protected by mutex)
        if (xSemaphoreTake(sensor_data_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            shared_sensor_data = local_data;
            xSemaphoreGive(sensor_data_mutex);
        }

        sensor_loop_count++;

        // Sleep until next period
        vTaskDelayUntil(&last_wake_time, sensor_period);
    }
}

// Task 2: Data Logging (Core 1, medium priority)
static void logging_task(void* parameter)
{
    ESP_LOGI(TAG, "Logging task started on core %d", xPortGetCoreID());

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t log_period = pdMS_TO_TICKS(100);  // 10 Hz
    uint32_t flush_counter = 0;

    while (true) {
        // Read shared sensor data
        SensorData local_data = {};
        bool has_data = false;

        if (xSemaphoreTake(sensor_data_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            if (shared_sensor_data.data_ready) {
                local_data = shared_sensor_data;
                has_data = true;
            }
            xSemaphoreGive(sensor_data_mutex);
        }

        // Log to SD card
        if (has_data && logger && logger->isLogging() && local_data.gps_fix) {
            double timestamp = local_data.timestamp_us / 1000000.0;

            if (logger->logFrame(timestamp,
                                local_data.gps_position,
                                local_data.gps_speed,
                                local_data.gps_satellites,
                                local_data.accel,
                                local_data.gyro)) {
                frames_logged++;
                flush_counter++;
            }
        }

        // Periodic flush to SD card (every 50 frames = 5 seconds at 10 Hz)
        if (flush_counter >= 50) {
            if (logger) {
                logger->flush();
            }
            flush_counter = 0;
        }

        vTaskDelayUntil(&last_wake_time, log_period);
    }
}

// Task 3: WiFi/WebSocket Telemetry (Core 0, low priority)
static void wifi_task(void* parameter)
{
    ESP_LOGI(TAG, "WiFi task started on core %d", xPortGetCoreID());

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t telemetry_period = pdMS_TO_TICKS(100);  // 10 Hz
    int64_t last_satellite_details_time = 0;
    const int64_t satellite_details_interval = config.getInt("telemetry.satellite_details_interval", 60) * 1000000LL;

    while (true) {
        // Update WebSocket server
        if (telemetry_server) {
            telemetry_server->update();
        }

        // Send telemetry if clients connected
        if (telemetry_server && telemetry_server->getClientCount() > 0) {
            SensorData local_data = {};
            bool has_data = false;

            if (xSemaphoreTake(sensor_data_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                if (shared_sensor_data.data_ready) {
                    local_data = shared_sensor_data;
                    has_data = true;
                }
                xSemaphoreGive(sensor_data_mutex);
            }

            if (has_data) {
                TelemetryData telemetry;
                telemetry.timestamp = local_data.timestamp_us / 1000000;
                telemetry.lat = local_data.gps_position.latitude;
                telemetry.lon = local_data.gps_position.longitude;
                telemetry.alt = local_data.gps_position.altitude;
                telemetry.speed = local_data.gps_speed;
                telemetry.track = local_data.gps_track;
                telemetry.heading = local_data.heading;
                telemetry.satellites = local_data.gps_satellites;
                telemetry.hdop = local_data.gps_hdop;
                telemetry.gx = local_data.accel.x;
                telemetry.gy = local_data.accel.y;
                telemetry.gz = local_data.accel.z;
                telemetry.rx = local_data.gyro.x;
                telemetry.ry = local_data.gyro.y;
                telemetry.rz = local_data.gyro.z;

                // Set fix type string
                switch (local_data.gps_fix_type) {
                    case FixType::FIX_3D: telemetry.fix_type = "3D"; break;
                    case FixType::FIX_2D: telemetry.fix_type = "2D"; break;
                    default: telemetry.fix_type = "No Fix"; break;
                }

                // Include satellite details periodically
                int64_t now = esp_timer_get_time();
                if (now - last_satellite_details_time >= satellite_details_interval) {
                    if (gps) {
                        auto sat_details = gps->getSatelliteDetails();
                        if (!sat_details.empty()) {
                            telemetry.satellite_details = &sat_details;
                            last_satellite_details_time = now;
                        }
                    }
                }

                telemetry_server->sendTelemetry(telemetry);
                telemetry_sent++;
            }
        }

        vTaskDelayUntil(&last_wake_time, telemetry_period);
    }
}

// Statistics task (prints stats every 5 seconds)
static void stats_task(void* parameter)
{
    while (true) {
        ESP_LOGI(TAG, "=== Statistics ===");
        ESP_LOGI(TAG, "Sensor loops: %" PRIu32, sensor_loop_count);
        ESP_LOGI(TAG, "Frames logged: %" PRIu32, frames_logged);
        ESP_LOGI(TAG, "Telemetry sent: %" PRIu32, telemetry_sent);
        if (telemetry_server) {
            ESP_LOGI(TAG, "WiFi clients: %u", telemetry_server->getClientCount());
        }
        ESP_LOGI(TAG, "Free heap: %" PRIu32 " bytes", esp_get_free_heap_size());
        ESP_LOGI(TAG, "Min free heap: %" PRIu32 " bytes", esp_get_minimum_free_heap_size());

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

// ============================================================================
// Main Application Entry Point
// ============================================================================

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "OpenPonyLogger ESP32-S3");
    ESP_LOGI(TAG, "Version: %s", OPENPONY_VERSION);
    ESP_LOGI(TAG, "ESP-IDF: %s", esp_get_idf_version());
    ESP_LOGI(TAG, "========================================");

    // Initialize NVS (required for WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize TCP/IP stack (required for WiFi)
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Create mutex for sensor data protection
    sensor_data_mutex = xSemaphoreCreateMutex();
    if (sensor_data_mutex == nullptr) {
        ESP_LOGE(TAG, "Failed to create mutex!");
        return;
    }

    // Initialize I2C bus (STEMMA QT sensors)
    ESP_ERROR_CHECK(i2c_master_init());

    // Load configuration
    ESP_LOGI(TAG, "Loading configuration...");
    config.load();

    // Initialize flash logger
    ESP_LOGI(TAG, "Initializing flash storage logger...");
    logger = new FlashLogger();
    if (logger->begin()) {
        ESP_LOGI(TAG, "Flash logger initialized - %.1f%% used",
                 logger->getUsagePercent() * 100);

        // Start new logging session
        if (logger->startSession()) {
            ESP_LOGI(TAG, "Session started: %s", logger->getCurrentSession());
        }
    } else {
        ESP_LOGE(TAG, "Flash logger init failed!");
    }

    // Initialize sensors
    ESP_LOGI(TAG, "Initializing sensors...");

    // Initialize PA1010D GPS
    gps = new PA1010D(I2C_MASTER_NUM, 0x10);
    if (gps) {
        ((PA1010D*)gps)->setUpdateRate(100);  // 10 Hz
        ESP_LOGI(TAG, "GPS: PA1010D initialized");
    } else {
        ESP_LOGE(TAG, "Failed to create PA1010D GPS");
    }

    // Initialize ICM20948 IMU
    ICM20948* icm = new ICM20948(I2C_MASTER_NUM);
    if (icm && icm->begin()) {
        imu = icm;
        mag = icm;  // ICM20948 has integrated magnetometer
        icm->setRange((uint8_t)16);  // 16g accelerometer range for track use
        icm->setRange((uint16_t)2000);  // 2000 dps gyroscope range
        ESP_LOGI(TAG, "IMU: ICM20948 initialized (16g accel, 2000dps gyro)");
    } else {
        ESP_LOGE(TAG, "Failed to initialize ICM20948 IMU");
        delete icm;
    }

    // Initialize Battery Monitor
    battery = new FeatherBattery();
    if (battery && ((FeatherBattery*)battery)->begin()) {
        BatteryInfo info = battery->read();
        ESP_LOGI(TAG, "Battery: %.2fV (%.0f%%)", info.voltage, info.percent);
    } else {
        ESP_LOGE(TAG, "Failed to initialize battery monitor");
    }

    // TODO: Initialize ST7789 TFT display
    // display = new ST7789Display();
    ESP_LOGI(TAG, "Display: ST7789 TFT (not implemented yet)");

    // Initialize WiFi and WebSocket server
    ESP_LOGI(TAG, "Starting WiFi...");
    // TODO: Initialize WebSocket server
    // telemetry_server = new WebSocketTelemetryServer(80);
    // telemetry_server->begin(...);

    // Create FreeRTOS tasks
    ESP_LOGI(TAG, "Creating FreeRTOS tasks...");

    // Sensor task on Core 1 (high priority)
    xTaskCreatePinnedToCore(
        sensor_task,
        "sensor",
        STACK_SIZE_SENSOR,
        nullptr,
        PRIORITY_SENSOR_TASK,
        nullptr,
        1  // Core 1
    );

    // Logging task on Core 1 (medium priority)
    xTaskCreatePinnedToCore(
        logging_task,
        "logging",
        STACK_SIZE_LOGGING,
        nullptr,
        PRIORITY_LOGGING_TASK,
        nullptr,
        1  // Core 1
    );

    // WiFi task on Core 0 (low priority, isolated)
    xTaskCreatePinnedToCore(
        wifi_task,
        "wifi",
        STACK_SIZE_WIFI,
        nullptr,
        PRIORITY_WIFI_TASK,
        nullptr,
        0  // Core 0 (WiFi core)
    );

    // Statistics task (can run on either core)
    xTaskCreate(
        stats_task,
        "stats",
        2048,
        nullptr,
        0,  // Lowest priority
        nullptr
    );

    // Storage management task (monitors flash, cleans up at 90%)
    xTaskCreate(
        check_flash_storage,
        "storage",
        2048,
        nullptr,
        0,  // Lowest priority
        nullptr
    );

    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "System Ready!");
    ESP_LOGI(TAG, "========================================");

    // app_main returns, but FreeRTOS tasks continue running
}
