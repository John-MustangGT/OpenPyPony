// src/webserver.cpp
// WebSocket server stub implementation for ESP-IDF

#include "webserver.h"
#include "esp_log.h"

static const char* TAG = "WebServer";

namespace OpenPony {

WebSocketTelemetryServer::WebSocketTelemetryServer(uint16_t port)
    : port_(port)
    , running_(false)
    , client_count_(0)
{
}

WebSocketTelemetryServer::~WebSocketTelemetryServer() {
    stop();
}

bool WebSocketTelemetryServer::begin(const char* ssid, const char* password, bool ap_mode) {
    ESP_LOGI(TAG, "WebSocket server stub - not implemented yet");
    ESP_LOGI(TAG, "SSID: %s, AP mode: %d", ssid, ap_mode);
    running_ = false;
    return false;
}

void WebSocketTelemetryServer::stop() {
    running_ = false;
    client_count_ = 0;
}

void WebSocketTelemetryServer::sendTelemetry(const TelemetryData& data) {
    // Stub - no actual sending
    (void)data;
}

void WebSocketTelemetryServer::update() {
    // Stub - no actual update
}

std::string WebSocketTelemetryServer::getIP() const {
    return "0.0.0.0";
}

std::string WebSocketTelemetryServer::serializeTelemetry(const TelemetryData& data) {
    // Stub - would create JSON string here
    (void)data;
    return "{}";
}

} // namespace OpenPony
