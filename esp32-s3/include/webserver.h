// include/webserver.h
// WebSocket server for real-time telemetry streaming
// JSON format is COMPATIBLE with CircuitPython version and gps-monitor

#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include "interfaces/gps_interface.h"
#include "interfaces/imu_interface.h"

namespace OpenPony {

// Telemetry data structure
struct TelemetryData {
    // Timestamp
    int64_t timestamp;          // Unix timestamp (UTC)

    // GPS data
    double lat;
    double lon;
    float alt;
    float speed;                // m/s (will be converted to MPH for transmission)
    float track;                // GPS track/COG (degrees)
    float heading;              // Compass heading (degrees)
    uint8_t satellites;
    const char* fix_type;       // "No Fix", "2D", "3D"
    float hdop;

    // IMU data
    float gx, gy, gz;          // Accelerometer (g-force)
    float rx, ry, rz;          // Gyroscope (deg/s)

    // Satellite details (optional, sent periodically)
    std::vector<SatelliteInfo>* satellite_details;

    TelemetryData() : timestamp(0), lat(0), lon(0), alt(0), speed(0),
                     track(0), heading(0), satellites(0), fix_type("No Fix"),
                     hdop(99.9), gx(0), gy(0), gz(1.0),
                     rx(0), ry(0), rz(0), satellite_details(nullptr) {}
};

class WebSocketTelemetryServer {
public:
    WebSocketTelemetryServer(uint16_t port = 80);
    ~WebSocketTelemetryServer();

    // Initialize server
    bool begin(const char* ssid, const char* password, bool ap_mode = true);

    // Stop server
    void stop();

    // Send telemetry data to all connected clients
    void sendTelemetry(const TelemetryData& data);

    // Update (call in loop)
    void update();

    // Get connection status
    uint8_t getClientCount() const { return client_count_; }
    bool isRunning() const { return running_; }
    IPAddress getIP() const { return WiFi.localIP(); }

private:
    WebServer http_server_;
    WebSocketsServer ws_server_;
    uint16_t port_;
    bool running_;
    uint8_t client_count_;

    // WebSocket event handler
    void onWebSocketEvent(uint8_t client_num, WStype_t type,
                         uint8_t* payload, size_t length);

    // HTTP handlers
    void handleRoot();
    void handleNotFound();

    // Serialize telemetry to JSON
    String serializeTelemetry(const TelemetryData& data);
};

} // namespace OpenPony
