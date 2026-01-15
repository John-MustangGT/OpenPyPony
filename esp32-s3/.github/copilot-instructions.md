# Copilot instructions for OpenPonyLogger (ESP32-S3)

Purpose: give AI coding agents immediate, actionable context to be productive in this repo.

- **Big picture**: This is a native ESP-IDF C++ project built with PlatformIO. The firmware is a dual-core FreeRTOS design: Core 1 (application) runs high-priority sensor reads and logging; Core 0 (WiFi) runs the network/telemetry stack. Primary data flow: `sensor_task` -> shared `SensorData` (mutex-protected) -> `logging_task` writes frames via `FlashLogger` -> `wifi_task`/`WebSocketTelemetryServer` sends telemetry.

- **Where to look first**: `src/main.cpp`, `include/config.h`, `src/config.cpp`, `src/webserver.cpp`, `include/interfaces/`, `src/sensors/`, `include/logger.h`, `src/logger.cpp`.

- **Key files & roles**:
  - `src/main.cpp`: task creation, I2C init, sensor/driver instantiation, task-to-core pinning (`xTaskCreatePinnedToCore`).
  - `include/interfaces/`: abstract interfaces for GPS, IMU, magnetometer, display, battery, vehicle—implementations live in `src/sensors` and `src/hardware`.
  - `include/config.h` & `src/config.cpp`: runtime configuration API (`Config::getInt/getString/getBool`) and default keys like `telemetry.satellite_details_interval`.
  - `include/logger.h` and `src/logger.cpp`: flash logger API (`FlashLogger::begin`, `startSession`, `logFrame`, `flush`, `cleanupOldSessions`).
  - `src/webserver.cpp`: WebSocket telemetry server stub (not implemented). Agents implementing telemetry should match `TelemetryData` serialization expected by `websocket` consumers.
  - `platformio.ini`: build flags, board (`adafruit_feather_esp32s3_tft`), monitor and upload settings—must be used for builds.

- **Build / debug / run workflows (exact commands)**:
  - Build: `pio run` (first run downloads ESP-IDF toolchain)
  - Upload: `pio run --target upload` (use `--upload-port` when needed)
  - Monitor: `pio device monitor` (115200 baud; configured filters include `esp32_exception_decoder`)
  - Clean: `pio run --target clean`
  - Erase flash: `pio run --target erase`

- **Project-specific conventions**:
  - Native ESP-IDF APIs are preferred; avoid Arduino abstractions.
  - Use `I2C_NUM_0` with the predefined pins in `src/main.cpp` (SDA=GPIO3, SCL=GPIO4). GPS I2C address: `0x10` (see `new PA1010D(I2C_MASTER_NUM, 0x10)`).
  - Task affinity matters: sensor + logging tasks run on core 1; WiFi runs on core 0. Preserve `xTaskCreatePinnedToCore` semantics.
  - Configuration keys are dot-separated strings used via `Config::get*` (e.g., `telemetry.rate`, `telemetry.satellite_details_interval`). Prefer to read via `config.getInt("telemetry.satellite_details_interval", 60)`.
  - No SD card by default — logs are stored in flash using `FlashLogger` and obey a ring-buffer cleanup policy (90% → 60%). Partitioning is defined in `partitions.csv`.

- **Integration points & TODOs** (existing stubs / places to implement):
  - `src/webserver.cpp`: WebSocket server is a stub—implement `begin`, `sendTelemetry`, and JSON serialization.
  - Display driver is TODO (ST7789) — main has a TODO comment where `display` should be instantiated.
  - Sensor drivers: implementations for `PA1010D` and `ICM20948` exist but may be incomplete; tests should focus on I2C initialization (`i2c_master_init()`) and sensor `begin()` semantics.

- **Code patterns to follow / examples**:
  - Locking and sharing sensor data: use `sensor_data_mutex` around `shared_sensor_data` (see `sensor_task` and `logging_task`).
  - Logging API example (from `src/main.cpp`):
    ```cpp
    if (logger->logFrame(timestamp, position, speed, satellites, accel, gyro)) {
         frames_logged++;
    }
    ```
  - Telemetry send path: assemble `TelemetryData` from `shared_sensor_data` and call `telemetry_server->sendTelemetry(telemetry)`.

- **Build flags & style**: `platformio.ini` sets `-std=gnu++17`, `-O2`, `-ffast-math` and suppresses some warnings (`-Wno-error=unused-variable`). Maintain these flags when adding new code.

- **Testing advice (practical, repo-specific)**:
  - First build will be slow (ESP-IDF download). Use `pio run -v` only when debugging build failures.
  - Use `pio device monitor` while running on hardware to check FreeRTOS logs: the app prints startup markers and periodic stats from `stats_task`.
  - To simulate sensors, create mock implementations of interfaces in `include/interfaces` and inject them in `app_main` before creating tasks.

- **When changing core/task affinity or timing**: make small, incremental changes and verify RAM/stack usage — WiFi task requires larger stack size (`STACK_SIZE_WIFI` = 8192).

If anything important is missing or you'd like a shorter/longer version, tell me which areas to expand (build, telemetry, sensor drivers, or config).
