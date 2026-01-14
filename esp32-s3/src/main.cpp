// src/main.cpp
// OpenPonyLogger ESP32-S3 Main Application
// Multi-core FreeRTOS architecture for concurrent sensor/WiFi/logging

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include "config.h"
#include "logger.h"
#include "webserver.h"
#include "interfaces/gps_interface.h"
#include "interfaces/imu_interface.h"
#include "interfaces/magnetometer_interface.h"
#include "interfaces/display_interface.h"

// TODO: Include concrete implementations
// #include "sensors/pa1010d.h"
// #include "sensors/icm20948.h"
// #include "hardware/st7789_display.h"

using namespace OpenPony;

// ============================================================================
// Global Objects
// ============================================================================

Config config;
BinaryLogger logger;
WebSocketTelemetryServer* telemetry_server = nullptr;

// Sensor interfaces (will be initialized in setup)
GPSInterface* gps = nullptr;
IMUInterface* imu = nullptr;
MagnetometerInterface* mag = nullptr;
DisplayInterface* display = nullptr;

// FreeRTOS task handles
TaskHandle_t sensorTaskHandle = NULL;
TaskHandle_t loggingTaskHandle = NULL;
TaskHandle_t wifiTaskHandle = NULL;

// Synchronization
SemaphoreHandle_t sensorDataMutex = NULL;

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
    uint32_t timestamp_ms;
    bool data_ready;
} shared_sensor_data;

// Statistics
volatile uint32_t sensor_loop_count = 0;
volatile uint32_t frames_logged = 0;
volatile uint32_t telemetry_sent = 0;

// ============================================================================
// FreeRTOS Tasks
// ============================================================================

// Task 1: Sensor Reading (Core 1, high priority)
// Reads GPS, IMU, magnetometer at high rate
void sensorTask(void* parameter) {
    Serial.println("[Task] Sensor task started on core " + String(xPortGetCoreID()));

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t sensor_period = pdMS_TO_TICKS(100);  // 10 Hz

    while (true) {
        // Update GPS (call frequently, it handles its own throttling)
        if (gps) {
            gps->update();
        }

        // Read sensor data
        SensorData local_data;
        local_data.timestamp_ms = millis();

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
        if (xSemaphoreTake(sensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            shared_sensor_data = local_data;
            xSemaphoreGive(sensorDataMutex);
        }

        sensor_loop_count++;

        // Sleep until next period
        vTaskDelayUntil(&last_wake_time, sensor_period);
    }
}

// Task 2: Data Logging (Core 1, medium priority)
// Writes sensor data to SD card at high rate
void loggingTask(void* parameter) {
    Serial.println("[Task] Logging task started on core " + String(xPortGetCoreID()));

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t log_period = pdMS_TO_TICKS(100);  // 10 Hz

    while (true) {
        // Read shared sensor data
        SensorData local_data;
        bool has_data = false;

        if (xSemaphoreTake(sensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            if (shared_sensor_data.data_ready) {
                local_data = shared_sensor_data;
                has_data = true;
            }
            xSemaphoreGive(sensorDataMutex);
        }

        // Log to SD card
        if (has_data && logger.isLogging() && local_data.gps_fix) {
            double timestamp = local_data.timestamp_ms / 1000.0;

            if (logger.logFrame(timestamp,
                              local_data.gps_position,
                              local_data.gps_speed,
                              local_data.gps_satellites,
                              local_data.accel,
                              local_data.gyro)) {
                frames_logged++;
            }
        }

        // Periodic flush to SD card (every 5 seconds)
        if (frames_logged % 50 == 0 && frames_logged > 0) {
            logger.flush();
        }

        vTaskDelayUntil(&last_wake_time, log_period);
    }
}

// Task 3: WiFi/WebSocket Telemetry (Core 0, low priority)
// Streams telemetry to connected clients
void wifiTask(void* parameter) {
    Serial.println("[Task] WiFi task started on core " + String(xPortGetCoreID()));

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t telemetry_period = pdMS_TO_TICKS(100);  // 10 Hz
    uint32_t last_satellite_details_time = 0;
    const uint32_t satellite_details_interval = config.getInt("telemetry.satellite_details_interval", 60) * 1000;

    while (true) {
        // Update WebSocket server
        if (telemetry_server) {
            telemetry_server->update();
        }

        // Send telemetry if clients connected
        if (telemetry_server && telemetry_server->getClientCount() > 0) {
            SensorData local_data;
            bool has_data = false;

            if (xSemaphoreTake(sensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                if (shared_sensor_data.data_ready) {
                    local_data = shared_sensor_data;
                    has_data = true;
                }
                xSemaphoreGive(sensorDataMutex);
            }

            if (has_data) {
                TelemetryData telemetry;
                telemetry.timestamp = local_data.timestamp_ms / 1000;
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
                uint32_t now = millis();
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

// ============================================================================
// Setup & Loop
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(2000);  // Wait for serial monitor

    Serial.println("\n\n========================================");
    Serial.println("OpenPonyLogger ESP32-S3");
    Serial.println("Version: 2.0.0-esp32s3");
    Serial.println("========================================\n");

    // Create mutex for sensor data protection
    sensorDataMutex = xSemaphoreCreateMutex();
    if (!sensorDataMutex) {
        Serial.println("[ERROR] Failed to create mutex!");
        while(1) delay(1000);
    }

    // Initialize I2C bus (STEMMA QT)
    Wire.begin();
    Wire.setClock(400000);  // 400 kHz Fast Mode
    Serial.println("[I2C] Bus initialized at 400 kHz");

    // Initialize SPI bus (SD card)
    // TODO: Configure SPI pins for FeatherWing
    SPI.begin();
    Serial.println("[SPI] Bus initialized");

    // Load configuration
    Serial.println("\n[Config] Loading configuration...");
    config.load();
    Serial.println("[Config] Configuration loaded");

    // Initialize SD card
    Serial.println("\n[SD] Initializing SD card...");
    // TODO: Set correct CS pin for FeatherWing Adalogger
    if (SD.begin(33)) {  // Replace with correct pin
        Serial.println("[SD] Card initialized successfully");
    } else {
        Serial.println("[SD] Card initialization failed!");
    }

    // Initialize sensors
    Serial.println("\n[Sensors] Initializing...");

    // TODO: Initialize PA1010D GPS
    // gps = new PA1010D(&Wire);
    Serial.println("[GPS] PA1010D (stub - not implemented yet)");

    // TODO: Initialize ICM20948 IMU
    // imu = new ICM20948(&Wire);
    // mag = imu;  // ICM20948 has integrated magnetometer
    Serial.println("[IMU] ICM20948 (stub - not implemented yet)");

    // TODO: Initialize ST7789 TFT display
    // display = new ST7789Display();
    Serial.println("[Display] ST7789 TFT (stub - not implemented yet)");

    // Start binary logger
    Serial.println("\n[Logger] Starting binary logger...");
    if (logger.begin()) {
        Serial.println("[Logger] Logger started successfully");
    } else {
        Serial.println("[Logger] Failed to start logger!");
    }

    // Initialize WiFi and WebSocket server
    Serial.println("\n[WiFi] Starting WiFi...");
    String wifi_mode = config.getString("radio.mode", "ap");
    String wifi_ssid = config.getString("radio.ssid", "OpenPonyLogger");
    String wifi_password = config.getString("radio.password", "mustanggt");

    telemetry_server = new WebSocketTelemetryServer(80);
    if (telemetry_server->begin(wifi_ssid.c_str(), wifi_password.c_str(), wifi_mode == "ap")) {
        Serial.print("[WiFi] Server started at ");
        Serial.println(telemetry_server->getIP());
        Serial.println("[WiFi] WebSocket telemetry available on port 80");
    } else {
        Serial.println("[WiFi] Failed to start server!");
    }

    // Create FreeRTOS tasks
    Serial.println("\n[Tasks] Creating FreeRTOS tasks...");

    // Sensor task on Core 1 (high priority)
    xTaskCreatePinnedToCore(
        sensorTask,           // Function
        "SensorTask",         // Name
        4096,                 // Stack size
        NULL,                 // Parameters
        2,                    // Priority (high)
        &sensorTaskHandle,    // Handle
        1                     // Core 1
    );

    // Logging task on Core 1 (medium priority)
    xTaskCreatePinnedToCore(
        loggingTask,
        "LoggingTask",
        4096,
        NULL,
        1,                    // Priority (medium)
        &loggingTaskHandle,
        1                     // Core 1
    );

    // WiFi task on Core 0 (low priority, isolated from sensors)
    xTaskCreatePinnedToCore(
        wifiTask,
        "WiFiTask",
        8192,                 // Larger stack for WiFi
        NULL,
        0,                    // Priority (low)
        &wifiTaskHandle,
        0                     // Core 0 (WiFi core)
    );

    Serial.println("[Tasks] All tasks created successfully");
    Serial.println("\n========================================");
    Serial.println("System Ready!");
    Serial.println("========================================\n");
}

void loop() {
    // Main loop runs on Core 1
    // Just print statistics every 5 seconds
    static uint32_t last_stats_time = 0;
    uint32_t now = millis();

    if (now - last_stats_time >= 5000) {
        Serial.println("\n--- Statistics ---");
        Serial.printf("Sensor loops: %u\n", sensor_loop_count);
        Serial.printf("Frames logged: %u\n", frames_logged);
        Serial.printf("Telemetry sent: %u\n", telemetry_sent);
        if (telemetry_server) {
            Serial.printf("WiFi clients: %u\n", telemetry_server->getClientCount());
        }
        Serial.printf("Free heap: %u bytes\n", ESP.getFreeHeap());
        Serial.println("------------------\n");

        last_stats_time = now;
    }

    delay(100);
}
