/**
 * esp-client-enhanced.ino
 * 
 * OpenPonyLogger ESP-01S Client with JSON Protocol
 * 
 * Features:
 * - Bidirectional JSON communication with Pico
 * - Enhanced web interface with satellite display
 * - File management (list, download, delete)
 * - Session control (start/stop)
 * - Real-time telemetry via WebSocket
 */

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>
#include <SoftwareSerial.h>
#include <ArduinoJson.h>

// ============================================================================
// Pin Configuration
// ============================================================================

#define PICO_RX_PIN 0  // GPIO0 - RX from Pico
#define PICO_TX_PIN 2  // GPIO2 - TX to Pico

SoftwareSerial PicoSerial(PICO_RX_PIN, PICO_TX_PIN);

// ============================================================================
// WiFi Configuration
// ============================================================================

const char* ssid = "OpenPonyLogger";
const char* password = "mustanggt";

IPAddress local_IP(192, 168, 4, 2);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

// ============================================================================
// Web Server
// ============================================================================

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// ============================================================================
// Data Storage
// ============================================================================

struct TelemetryData {
    bool valid = false;
    float gx, gy, gz, g_total;
    float lat, lon, alt, speed;
    int sats;
    float hdop;
    String fix_type;
    unsigned long last_update = 0;
};

TelemetryData telemetry;

struct SatelliteData {
    int id;
    int elevation;
    int azimuth;
    int snr;
};

std::vector<SatelliteData> satellites;
unsigned long last_sat_update = 0;

// ============================================================================
// JSON Buffer
// ============================================================================

String jsonBuffer = "";

// ============================================================================
// Setup
// ============================================================================

void setup() {
    // USB Serial for debugging
    Serial.begin(115200);
    delay(100);
    
    Serial.println("\n\n========================================");
    Serial.println("OpenPonyLogger ESP-01S Client v2.1");
    Serial.println("========================================\n");
    
    // GPIO setup
    pinMode(PICO_RX_PIN, INPUT_PULLUP);
    pinMode(PICO_TX_PIN, OUTPUT);
    digitalWrite(PICO_TX_PIN, HIGH);
    delay(100);
    
    // Initialize SoftwareSerial to Pico
    PicoSerial.begin(9600);
    Serial.println("✓ SoftwareSerial initialized (9600 baud)");
    
    // Connect to WiFi
    Serial.print("Connecting to WiFi: ");
    Serial.println(ssid);
    
    if (!WiFi.config(local_IP, gateway, subnet)) {
        Serial.println("✗ Failed to configure static IP");
    }
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("✓ WiFi connected!");
        Serial.print("  IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("✗ WiFi connection failed!");
    }
    
    // ========================================================================
    // Web Server Routes
    // ========================================================================
    
    // Serve main page
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
        request->send(200, "text/html", getMainPage());
    });
    
    // API: Get current telemetry
    server.on("/api/telemetry", HTTP_GET, [](AsyncWebServerRequest *request){
        String json = getTelemetryJSON();
        request->send(200, "application/json", json);
    });
    
    // API: Get satellites
    server.on("/api/satellites", HTTP_GET, [](AsyncWebServerRequest *request){
        // Request fresh satellite data from Pico
        sendCommandToPico("{\"cmd\":\"GET_SATELLITES\"}");
        
        String json = getSatellitesJSON();
        request->send(200, "application/json", json);
    });
    
    // API: List files
    server.on("/api/files", HTTP_GET, [](AsyncWebServerRequest *request){
        // Request file list from Pico
        sendCommandToPico("{\"cmd\":\"LIST\"}");
        delay(500);  // Wait for response
        
        request->send(200, "text/plain", "File list requested");
    });
    
    // API: Download file
    server.on("/api/download", HTTP_GET, [](AsyncWebServerRequest *request){
        if (!request->hasParam("file")) {
            request->send(400, "text/plain", "Missing file parameter");
            return;
        }
        
        String filename = request->getParam("file")->value();
        
        // Request file from Pico
        StaticJsonDocument<256> doc;
        doc["cmd"] = "GET";
        doc["file"] = filename;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Download started");
    });
    
    // API: Delete file
    server.on("/api/delete", HTTP_DELETE, [](AsyncWebServerRequest *request){
        if (!request->hasParam("file")) {
            request->send(400, "text/plain", "Missing file parameter");
            return;
        }
        
        String filename = request->getParam("file")->value();
        
        // Send delete command to Pico
        StaticJsonDocument<256> doc;
        doc["cmd"] = "DELETE";
        doc["file"] = filename;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Delete requested");
    });
    
    // API: Start session
    server.on("/api/start", HTTP_POST, [](AsyncWebServerRequest *request){
        String driver = request->hasParam("driver") ? 
                       request->getParam("driver")->value() : "Unknown";
        String vin = request->hasParam("vin") ? 
                    request->getParam("vin")->value() : "Unknown";
        
        StaticJsonDocument<256> doc;
        doc["cmd"] = "START_SESSION";
        doc["driver"] = driver;
        doc["vin"] = vin;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Session start requested");
    });
    
    // API: Stop session
    server.on("/api/stop", HTTP_POST, [](AsyncWebServerRequest *request){
        sendCommandToPico("{\"cmd\":\"STOP_SESSION\"}");
        request->send(200, "text/plain", "Session stop requested");
    });
    
    // WebSocket handler
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    
    // Start server
    server.begin();
    Serial.println("✓ Web server started");
    
    Serial.println("\n========================================");
    Serial.println("Ready!");
    Serial.println("========================================\n");
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
    // Clean up WebSocket clients
    ws.cleanupClients();
    
    // Process data from Pico
    processSerialData();
    
    delay(10);
}

// ============================================================================
// Serial Communication
// ============================================================================

void processSerialData() {
    if (PicoSerial.available()) {
        char c = PicoSerial.read();
        
        if (c == '\n') {
            // Complete JSON object received
            if (jsonBuffer.length() > 0) {
                processJSONMessage(jsonBuffer);
                jsonBuffer = "";
            }
        } else {
            jsonBuffer += c;
        }
    }
}

void processJSONMessage(String json) {
    Serial.print("Pico → ESP: ");
    Serial.println(json);
    
    StaticJsonDocument<2048> doc;
    DeserializationError error = deserializeJson(doc, json);
    
    if (error) {
        Serial.print("JSON parse error: ");
        Serial.println(error.c_str());
        return;
    }
    
    String type = doc["type"] | "";
    
    if (type == "update") {
        handleTelemetryUpdate(doc);
    }
    else if (type == "satellites") {
        handleSatelliteUpdate(doc);
    }
    else if (type == "files") {
        handleFileList(doc);
    }
    else if (type == "file_start" || type == "file_chunk" || type == "file_end") {
        handleFileTransfer(doc);
    }
    else if (type == "ok" || type == "error") {
        handleResponse(doc);
    }
}

void handleTelemetryUpdate(JsonDocument& doc) {
    JsonObject data = doc["data"];
    
    telemetry.valid = true;
    telemetry.gx = data["g"]["x"];
    telemetry.gy = data["g"]["y"];
    telemetry.gz = data["g"]["z"];
    telemetry.g_total = data["g"]["total"];
    
    telemetry.lat = data["gps"]["lat"];
    telemetry.lon = data["gps"]["lon"];
    telemetry.alt = data["gps"]["alt"];
    telemetry.speed = data["gps"]["speed"];
    telemetry.sats = data["gps"]["sats"];
    telemetry.hdop = data["gps"]["hdop"];
    telemetry.fix_type = data["gps"]["fix"] | "NoFix";
    
    telemetry.last_update = millis();
    
    // Serialize and broadcast to WebSocket clients
    String json;                    // ← ADD THIS
    serializeJson(doc, json);       // ← ADD THIS
    ws.textAll(json);
}

void handleSatelliteUpdate(JsonDocument& doc) {
    satellites.clear();
    
    JsonArray sats = doc["satellites"];
    for (JsonObject sat : sats) {
        SatelliteData sd;
        sd.id = sat["id"];
        sd.elevation = sat["elevation"];
        sd.azimuth = sat["azimuth"];
        sd.snr = sat["snr"];
        satellites.push_back(sd);
    }
    
    last_sat_update = millis();
    
    // Broadcast to WebSocket clients
    String json;
    serializeJson(doc, json);
    ws.textAll(json);
}

void handleFileList(JsonDocument& doc) {
    // Forward to WebSocket clients
    String json;
    serializeJson(doc, json);
    ws.textAll(json);
}

void handleFileTransfer(JsonDocument& doc) {
    // Forward to WebSocket clients for handling
    String json;
    serializeJson(doc, json);
    ws.textAll(json);
}

void handleResponse(JsonDocument& doc) {
    String type = doc["type"];
    String message = doc["message"] | "";
    
    Serial.print("Response: ");
    Serial.println(message);
    
    // Forward to WebSocket clients
    String json;
    serializeJson(doc, json);
    ws.textAll(json);
}

void sendCommandToPico(String json) {
    Serial.print("ESP → Pico: ");
    Serial.println(json);
    
    PicoSerial.println(json);
}

// ============================================================================
// JSON Generators
// ============================================================================

String getTelemetryJSON() {
    StaticJsonDocument<512> doc;
    
    doc["valid"] = telemetry.valid;
    
    if (telemetry.valid) {
        JsonObject g = doc.createNestedObject("g");
        g["x"] = telemetry.gx;
        g["y"] = telemetry.gy;
        g["z"] = telemetry.gz;
        g["total"] = telemetry.g_total;
        
        JsonObject gps = doc.createNestedObject("gps");
        gps["fix"] = telemetry.fix_type;
        gps["lat"] = telemetry.lat;
        gps["lon"] = telemetry.lon;
        gps["alt"] = telemetry.alt;
        gps["speed"] = telemetry.speed;
        gps["sats"] = telemetry.sats;
        gps["hdop"] = telemetry.hdop;
    }
    
    String json;
    serializeJson(doc, json);
    return json;
}

String getSatellitesJSON() {
    StaticJsonDocument<2048> doc;
    
    doc["count"] = satellites.size();
    doc["last_update"] = last_sat_update;
    
    JsonArray sats = doc.createNestedArray("satellites");
    for (const SatelliteData& sat : satellites) {
        JsonObject obj = sats.createNestedObject();
        obj["id"] = sat.id;
        obj["elevation"] = sat.elevation;
        obj["azimuth"] = sat.azimuth;
        obj["snr"] = sat.snr;
    }
    
    String json;
    serializeJson(doc, json);
    return json;
}

// ============================================================================
// WebSocket Handler
// ============================================================================

void onWsEvent(AsyncWebSocket *server, AsyncWebSocketClient *client,
               AwsEventType type, void *arg, uint8_t *data, size_t len) {
    
    if (type == WS_EVT_CONNECT) {
        Serial.printf("WebSocket #%u connected\n", client->id());
        
        // Send current telemetry to new client
        if (telemetry.valid) {
            String json = getTelemetryJSON();
            client->text(json);
        }
    }
    else if (type == WS_EVT_DISCONNECT) {
        Serial.printf("WebSocket #%u disconnected\n", client->id());
    }
    else if (type == WS_EVT_DATA) {
        AwsFrameInfo *info = (AwsFrameInfo*)arg;
        
        if (info->final && info->index == 0 && info->len == len) {
            String msg = "";
            for (size_t i = 0; i < len; i++) {
                msg += (char)data[i];
            }
            
            Serial.print("WS → Pico: ");
            Serial.println(msg);
            
            // Forward to Pico
            sendCommandToPico(msg);
        }
    }
}

// ============================================================================
// HTML Page
// ============================================================================

String getMainPage() {
    return R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenPonyLogger</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #fff;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            color: #ff6b35;
            margin-bottom: 20px;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
        }
        
        .tab {
            padding: 10px 20px;
            background: none;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 16px;
            border-bottom: 3px solid transparent;
        }
        
        .tab.active {
            color: #ff6b35;
            border-bottom-color: #ff6b35;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .data-item {
            text-align: center;
        }
        
        .data-label {
            color: #888;
            font-size: 14px;
            margin-bottom: 5px;
        }
        
        .data-value {
            font-size: 24px;
            font-weight: bold;
            color: #ff6b35;
            font-family: 'Courier New', monospace;
        }
        
        button {
            padding: 10px 20px;
            background: #ff6b35;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
        }
        
        button:hover {
            background: #ff5722;
        }
        
        button.secondary {
            background: #333;
        }
        
        button.secondary:hover {
            background: #444;
        }
        
        button.danger {
            background: #f44336;
        }
        
        button.danger:hover {
            background: #d32f2f;
        }
        
        #satellite-sky {
            width: 100%;
            max-width: 600px;
            height: 600px;
            margin: 0 auto;
            background: #0a0a0a;
            border: 2px solid #333;
            border-radius: 50%;
        }
        
        .file-list {
            list-style: none;
        }
        
        .file-item {
            background: #222;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .file-info {
            flex: 1;
        }
        
        .file-actions {
            display: flex;
            gap: 10px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        input {
            padding: 10px;
            background: #222;
            border: 1px solid #333;
            color: #fff;
            border-radius: 6px;
            flex: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐎 OpenPonyLogger</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('telemetry')">Telemetry</button>
            <button class="tab" onclick="showTab('satellites')">Satellites</button>
            <button class="tab" onclick="showTab('files')">Sessions</button>
            <button class="tab" onclick="showTab('control')">Control</button>
        </div>
        
        <!-- Telemetry Tab -->
        <div id="telemetry" class="tab-content active">
            <div class="card">
                <h2>G-Force</h2>
                <div class="data-grid">
                    <div class="data-item">
                        <div class="data-label">Lateral (X)</div>
                        <div class="data-value" id="gx">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Longitudinal (Y)</div>
                        <div class="data-value" id="gy">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Vertical (Z)</div>
                        <div class="data-value" id="gz">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Total</div>
                        <div class="data-value" id="g-total">--</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>GPS</h2>
                <div class="data-grid">
                    <div class="data-item">
                        <div class="data-label">Fix</div>
                        <div class="data-value" id="gps-fix">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Satellites</div>
                        <div class="data-value" id="gps-sats">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Speed (MPH)</div>
                        <div class="data-value" id="gps-speed">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">HDOP</div>
                        <div class="data-value" id="gps-hdop">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Latitude</div>
                        <div class="data-value" id="gps-lat">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Longitude</div>
                        <div class="data-value" id="gps-lon">--</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Altitude</div>
                        <div class="data-value" id="gps-alt">--</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Satellites Tab -->
        <div id="satellites" class="tab-content">
            <div class="card">
                <h2>Satellite Sky View</h2>
                <canvas id="satellite-sky"></canvas>
                <p style="text-align: center; color: #888; margin-top: 10px;">
                    Last Update: <span id="sat-update">Never</span>
                </p>
            </div>
        </div>
        
        <!-- Files Tab -->
        <div id="files" class="tab-content">
            <div class="card">
                <h2>Session Files</h2>
                <button onclick="refreshFiles()">Refresh</button>
                <ul class="file-list" id="file-list">
                    <li>Loading...</li>
                </ul>
            </div>
        </div>
        
        <!-- Control Tab -->
        <div id="control" class="tab-content">
            <div class="card">
                <h2>Session Control</h2>
                
                <div class="controls">
                    <input type="text" id="driver-name" placeholder="Driver Name" value="John">
                    <input type="text" id="car-vin" placeholder="VIN" value="1ZVBP8AM5E5123456">
                </div>
                
                <div class="controls">
                    <button onclick="startSession()">▶ Start Session</button>
                    <button class="danger" onclick="stopSession()">⏹ Stop Session</button>
                </div>
                
                <div id="session-status" style="margin-top: 20px; color: #888;">
                    Status: Ready
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let ws;
        let satellites = [];
        
        function init() {
            connectWebSocket();
            refreshFiles();
            drawSatelliteSky();
        }
        
        function connectWebSocket() {
            ws = new WebSocket('ws://' + location.hostname + '/ws');
            
            ws.onopen = () => {
                console.log('WebSocket connected');
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    console.error('JSON parse error:', e);
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket closed, reconnecting...');
                setTimeout(connectWebSocket, 2000);
            };
        }
        
        function handleMessage(data) {
            if (data.type === 'update') {
                updateTelemetry(data.data);
            } else if (data.type === 'satellites') {
                updateSatellites(data);
            } else if (data.type === 'files') {
                displayFiles(data.files);
            }
        }
        
        function updateTelemetry(data) {
            // G-Force
            document.getElementById('gx').textContent = data.g.x.toFixed(2) + 'g';
            document.getElementById('gy').textContent = data.g.y.toFixed(2) + 'g';
            document.getElementById('gz').textContent = data.g.z.toFixed(2) + 'g';
            document.getElementById('g-total').textContent = data.g.total.toFixed(2) + 'g';
            
            // GPS
            document.getElementById('gps-fix').textContent = data.gps.fix;
            document.getElementById('gps-sats').textContent = data.gps.sats;
            document.getElementById('gps-speed').textContent = data.gps.speed.toFixed(1);
            document.getElementById('gps-hdop').textContent = data.gps.hdop.toFixed(1);
            document.getElementById('gps-lat').textContent = data.gps.lat.toFixed(6);
            document.getElementById('gps-lon').textContent = data.gps.lon.toFixed(6);
            document.getElementById('gps-alt').textContent = data.gps.alt.toFixed(1) + 'm';
        }
        
        function updateSatellites(data) {
            satellites = data.satellites;
            document.getElementById('sat-update').textContent = new Date().toLocaleTimeString();
            drawSatelliteSky();
        }
        
        function drawSatelliteSky() {
            const canvas = document.getElementById('satellite-sky');
            const ctx = canvas.getContext('2d');
            const size = Math.min(canvas.width, canvas.height);
            const centerX = size / 2;
            const centerY = size / 2;
            const radius = size / 2 - 40;
            
            // Clear
            ctx.fillStyle = '#0a0a0a';
            ctx.fillRect(0, 0, size, size);
            
            // Draw circles
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 1;
            for (let i = 1; i <= 3; i++) {
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius * i / 3, 0, Math.PI * 2);
                ctx.stroke();
            }
            
            // Draw compass
            ctx.fillStyle = '#fff';
            ctx.font = '20px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('N', centerX, centerY - radius - 15);
            ctx.fillText('S', centerX, centerY + radius + 25);
            ctx.textAlign = 'right';
            ctx.fillText('W', centerX - radius - 15, centerY + 7);
            ctx.textAlign = 'left';
            ctx.fillText('E', centerX + radius + 15, centerY + 7);
            
            // Draw satellites
            satellites.forEach(sat => {
                const angle = (sat.azimuth - 90) * Math.PI / 180;
                const distance = radius * (1 - sat.elevation / 90);
                const x = centerX + distance * Math.cos(angle);
                const y = centerY + distance * Math.sin(angle);
                
                // Color by SNR
                let color;
                if (sat.snr > 35) color = '#4caf50';
                else if (sat.snr > 25) color = '#ffc107';
                else color = '#f44336';
                
                // Draw satellite
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 8, 0, Math.PI * 2);
                ctx.fill();
                
                // Draw ID
                ctx.fillStyle = '#fff';
                ctx.font = '12px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(sat.id, x, y - 12);
            });
        }
        
        function refreshFiles() {
            fetch('/api/files')
                .then(() => {
                    // Files will come via WebSocket
                    document.getElementById('file-list').innerHTML = '<li>Loading...</li>';
                });
        }
        
        function displayFiles(files) {
            const list = document.getElementById('file-list');
            
            if (files.length === 0) {
                list.innerHTML = '<li>No session files</li>';
                return;
            }
            
            list.innerHTML = files.map(file => `
                <li class="file-item">
                    <div class="file-info">
                        <strong>${file.file}</strong><br>
                        <small>Driver: ${file.driver} | VIN: ${file.vin} | ${(file.size/1024).toFixed(1)} KB</small>
                    </div>
                    <div class="file-actions">
                        <button class="secondary" onclick="downloadFile('${file.file}')">Download</button>
                        <button class="danger" onclick="deleteFile('${file.file}')">Delete</button>
                    </div>
                </li>
            `).join('');
        }
        
        function downloadFile(filename) {
            window.location.href = '/api/download?file=' + filename;
        }
        
        function deleteFile(filename) {
            if (!confirm('Delete ' + filename + '?')) return;
            
            fetch('/api/delete?file=' + filename, { method: 'DELETE' })
                .then(() => {
                    setTimeout(refreshFiles, 500);
                });
        }
        
        function startSession() {
            const driver = document.getElementById('driver-name').value;
            const vin = document.getElementById('car-vin').value;
            
            fetch('/api/start?driver=' + encodeURIComponent(driver) + '&vin=' + encodeURIComponent(vin), {
                method: 'POST'
            }).then(() => {
                document.getElementById('session-status').textContent = 'Status: Recording...';
            });
        }
        
        function stopSession() {
            fetch('/api/stop', { method: 'POST' })
                .then(() => {
                    document.getElementById('session-status').textContent = 'Status: Stopped';
                    setTimeout(refreshFiles, 500);
                });
        }
        
        function showTab(tab) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(el => {
                el.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(el => {
                el.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            
            // Redraw satellite sky if switching to that tab
            if (tab === 'satellites') {
                drawSatelliteSky();
            }
        }
        
        // Initialize
        window.addEventListener('load', init);
    </script>
</body>
</html>
)rawliteral";
}