// src/webserver.cpp
// WebSocket server stub implementation for ESP-IDF

#include "webserver.h"
#include "esp_log.h"
#include <sstream>
#include <iomanip>

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
    ESP_LOGI(TAG, "WebSocket server init (stub): SSID=%s, AP=%d", ssid ? ssid : "(null)", ap_mode);
    // Minimal stub implementation: mark running so higher-level code can operate
    // Actual WiFi/AP initialization and websocket listener are not implemented here.
    running_ = true;
    client_count_ = 0;
    return true;
}

void WebSocketTelemetryServer::stop() {
    running_ = false;
    client_count_ = 0;
}

void WebSocketTelemetryServer::sendTelemetry(const TelemetryData& data) {
    // Serialize to JSON and log it for debugging. Real websocket send not implemented.
    std::string json = serializeTelemetry(data);
    ESP_LOGD(TAG, "Telemetry JSON: %s", json.c_str());
}

void WebSocketTelemetryServer::update() {
    // Stub - no actual update
}

std::string WebSocketTelemetryServer::getIP() const {
    return "0.0.0.0";
}

std::string WebSocketTelemetryServer::serializeTelemetry(const TelemetryData& data) {
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(6);
    ss << "{";
    ss << "\"timestamp\":" << data.timestamp << ",";
    ss << "\"lat\":" << data.lat << ",";
    ss << "\"lon\":" << data.lon << ",";
    ss << std::setprecision(3);
    ss << "\"alt\":" << data.alt << ",";
    ss << "\"speed\":" << data.speed << ",";
    ss << "\"track\":" << data.track << ",";
    ss << "\"heading\":" << data.heading << ",";
    ss << "\"satellites\":" << static_cast<int>(data.satellites) << ",";
    ss << std::setprecision(2);
    ss << "\"hdop\":" << data.hdop << ",";
    ss << "\"fix_type\":\"" << (data.fix_type ? data.fix_type : "No Fix") << "\",";

    // IMU
    ss << std::setprecision(6);
    ss << "\"gx\":" << data.gx << ",";
    ss << "\"gy\":" << data.gy << ",";
    ss << "\"gz\":" << data.gz << ",";
    ss << "\"rx\":" << data.rx << ",";
    ss << "\"ry\":" << data.ry << ",";
    ss << "\"rz\":" << data.rz;

    // Satellite details if present
    if (data.satellite_details && !data.satellite_details->empty()) {
        ss << ",\"satellite_details\":[";
        bool first = true;
        for (const auto& s : *data.satellite_details) {
            if (!first) ss << ",";
            first = false;
            ss << "{";
            ss << "\"prn\":" << s.prn << ",";
            ss << "\"elevation\":" << static_cast<int>(s.elevation) << ",";
            ss << "\"azimuth\":" << static_cast<int>(s.azimuth) << ",";
            ss << "\"snr\":" << static_cast<int>(s.snr);
            ss << "}";
        }
        ss << "]";
    }

    ss << "}";
    return ss.str();
}

} // namespace OpenPony
