/**
 * esp-client-hardware-uart.ino
 * 
 * OpenPonyLogger ESP-01S Client - Hardware UART Version
 * 
 * Hardware UART on GPIO1 (TX) and GPIO3 (RX)
 * Runs at 57600 baud for reliable JSON communication
 * 
 * NOTE: You CANNOT use USB Serial (Serial) for debugging when using
 *       hardware UART for Pico communication!
 */

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>
#include <ArduinoJson.h>

// ============================================================================
// UART Configuration
// ============================================================================

// ESP-01S has ONE hardware UART:
// - GPIO1 (TX) - Transmit to Pico
// - GPIO3 (RX) - Receive from Pico
//
// This is the SAME UART used for USB programming!
// We sacrifice USB debugging to get reliable high-speed UART

#define PicoSerial Serial  // Use hardware UART (GPIO1=TX, GPIO3=RX)
#define UART_BAUD 115200    // Fast and reliable!

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
// HTML Page - Chunked for ESP-01S Memory Limits
// ============================================================================

const char HTML_HEADER[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenPonyLogger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #ff6b35; margin-bottom: 20px; }
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
        .tab.active { color: #ff6b35; border-bottom-color: #ff6b35; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
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
        .data-item { text-align: center; }
        .data-label { color: #888; font-size: 14px; margin-bottom: 5px; }
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
        button:hover { background: #ff5722; }
        button.secondary { background: #333; }
        button.secondary:hover { background: #444; }
        button.danger { background: #f44336; }
        button.danger:hover { background: #d32f2f; }
        #satellite-sky {
            width: 100%;
            max-width: 400px;
            height: 400px;
            margin: 0 auto;
            background: #0a0a0a;
            border: 2px solid #333;
            border-radius: 50%;
        }
        .file-list { list-style: none; }
        .file-item {
            background: #222;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .file-info { flex: 1; }
        .file-actions { display: flex; gap: 10px; }
        .controls { display: flex; gap: 10px; margin-bottom: 20px; }
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
)rawliteral";

const char HTML_TELEMETRY[] PROGMEM = R"rawliteral(
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
                </div>
            </div>
        </div>
)rawliteral";

const char HTML_SATELLITES[] PROGMEM = R"rawliteral(
        <div id="satellites" class="tab-content">
            <div class="card">
                <h2>Satellite Sky View</h2>
                <canvas id="satellite-sky"></canvas>
                <p style="text-align: center; color: #888; margin-top: 10px;">
                    Last Update: <span id="sat-update">Never</span>
                </p>
            </div>
        </div>
)rawliteral";

const char HTML_FILES[] PROGMEM = R"rawliteral(
        <div id="files" class="tab-content">
            <div class="card">
                <h2>Session Files</h2>
                <button onclick="refreshFiles()">Refresh</button>
                <ul class="file-list" id="file-list">
                    <li>Loading...</li>
                </ul>
            </div>
        </div>
)rawliteral";

const char HTML_CONTROL[] PROGMEM = R"rawliteral(
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
)rawliteral";

const char HTML_JAVASCRIPT[] PROGMEM = R"rawliteral(
    <script>
let ws;let satellites=[];function init(){connectWebSocket();refreshFiles();drawSatelliteSky()}
function connectWebSocket(){ws=new WebSocket('ws://'+location.hostname+'/ws');ws.onopen=()=>console.log('Connected');ws.onmessage=(e)=>{try{const data=JSON.parse(e.data);handleMessage(data)}catch(err){console.error(err)}};ws.onclose=()=>setTimeout(connectWebSocket,2000)}
function handleMessage(data){if(data.type==='update')updateTelemetry(data.data);else if(data.type==='satellites')updateSatellites(data);else if(data.type==='files')displayFiles(data.files);}
function updateTelemetry(d){document.getElementById('gx').textContent=d.g.x.toFixed(2)+'g';document.getElementById('gy').textContent=d.g.y.toFixed(2)+'g';document.getElementById('gz').textContent=d.g.z.toFixed(2)+'g';document.getElementById('g-total').textContent=d.g.total.toFixed(2)+'g';document.getElementById('gps-fix').textContent=d.gps.fix;document.getElementById('gps-sats').textContent=d.gps.sats;document.getElementById('gps-speed').textContent=d.gps.speed.toFixed(1);document.getElementById('gps-hdop').textContent=d.gps.hdop.toFixed(1);document.getElementById('gps-lat').textContent=d.gps.lat.toFixed(6);document.getElementById('gps-lon').textContent=d.gps.lon.toFixed(6)}
function updateSatellites(data){satellites=data.satellites;document.getElementById('sat-update').textContent=new Date().toLocaleTimeString();drawSatelliteSky()}
function drawSatelliteSky(){const canvas=document.getElementById('satellite-sky');const ctx=canvas.getContext('2d');const size=Math.min(canvas.width,canvas.height);const cx=size/2,cy=size/2,r=size/2-20;ctx.fillStyle='#0a0a0a';ctx.fillRect(0,0,size,size);ctx.strokeStyle='#333';ctx.lineWidth=1;for(let i=1;i<=3;i++){ctx.beginPath();ctx.arc(cx,cy,r*i/3,0,Math.PI*2);ctx.stroke()}
ctx.fillStyle='#fff';ctx.font='16px sans-serif';ctx.textAlign='center';ctx.fillText('N',cx,cy-r-10);ctx.fillText('S',cx,cy+r+20);satellites.forEach(sat=>{const angle=(sat.azimuth-90)*Math.PI/180;const dist=r*(1-sat.elevation/90);const x=cx+dist*Math.cos(angle);const y=cy+dist*Math.sin(angle);ctx.fillStyle=sat.snr>35?'#4caf50':sat.snr>25?'#ffc107':'#f44336';ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff';ctx.font='10px sans-serif';ctx.fillText(sat.id,x,y-10)})}
function refreshFiles(){fetch('/api/files');document.getElementById('file-list').innerHTML='<li>Loading...</li>'}
function displayFiles(files){const list=document.getElementById('file-list');if(files.length===0){list.innerHTML='<li>No files</li>';return}
list.innerHTML=files.map(f=>`
                <li class="file-item">
                    <div class="file-info">
                        <strong>${f.file}</strong><br>
                        <small>Driver: ${f.driver} | VIN: ${f.vin}</small>
                    </div>
                    <div class="file-actions">
                        <button class="secondary" onclick="window.location='/api/download?file=${f.file}'">Download</button>
                        <button class="danger" onclick="deleteFile('${f.file}')">Delete</button>
                    </div>
                </li>
            `).join('')}
function deleteFile(fn){if(!confirm('Delete '+fn+'?'))return;fetch('/api/delete?file='+fn,{method:'DELETE'}).then(()=>setTimeout(refreshFiles,500))}
function startSession(){const driver=document.getElementById('driver-name').value;const vin=document.getElementById('car-vin').value;fetch('/api/start?driver='+encodeURIComponent(driver)+'&vin='+encodeURIComponent(vin),{method:'POST'}).then(()=>{document.getElementById('session-status').textContent='Status: Recording...'})}
function stopSession(){fetch('/api/stop',{method:'POST'}).then(()=>{document.getElementById('session-status').textContent='Status: Stopped';setTimeout(refreshFiles,500)})}
function showTab(tab){document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));document.getElementById(tab).classList.add('active');event.target.classList.add('active');if(tab==='satellites')drawSatelliteSky();}
window.addEventListener('load',init)
    </script>
</body>
</html>
)rawliteral";

// ============================================================================
// JSON Buffer
// ============================================================================

String jsonBuffer = "";
const size_t MAX_JSON_BUFFER = 4096;  // Larger buffer for 57600 baud

// ============================================================================
// Setup
// ============================================================================

void setup() {
    // Initialize Hardware UART for Pico communication
    // NOTE: This disables USB Serial debugging!
    PicoSerial.begin(UART_BAUD);
    PicoSerial.setRxBufferSize(1024);  // Increase RX buffer
    
    delay(500);  // Let UART stabilize
    
    // Send startup message to Pico
    PicoSerial.println("{\"type\":\"esp_ready\"}");
    
    // Connect to WiFi
    WiFi.mode(WIFI_AP);
    WiFi.config(local_IP, gateway, subnet);
    WiFi.softAP(ssid, password);
    
    // Wait for connection (no serial debug available)
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        // Notify Pico of WiFi status
        StaticJsonDocument<128> doc;
        doc["type"] = "wifi_status";
        doc["connected"] = true;
        doc["ip"] = WiFi.localIP().toString();
        
        String json;
        serializeJson(doc, json);
        PicoSerial.println(json);
    }
    
    // ========================================================================
    // Web Server Routes
    // ========================================================================
    
    server.on("/", HTTP_GET, handleRootPage);
    
    server.on("/api/telemetry", HTTP_GET, [](AsyncWebServerRequest *request){
        String json = getTelemetryJSON();
        request->send(200, "application/json", json);
    });
    
    server.on("/api/satellites", HTTP_GET, [](AsyncWebServerRequest *request){
        sendCommandToPico("{\"cmd\":\"GET_SATELLITES\"}");
        String json = getSatellitesJSON();
        request->send(200, "application/json", json);
    });
    
    server.on("/api/files", HTTP_GET, [](AsyncWebServerRequest *request){
        sendCommandToPico("{\"cmd\":\"LIST\"}");
        delay(100);
        request->send(200, "text/plain", "File list requested");
    });
    
    server.on("/api/download", HTTP_GET, [](AsyncWebServerRequest *request){
        if (!request->hasParam("file")) {
            request->send(400, "text/plain", "Missing file parameter");
            return;
        }
        
        String filename = request->getParam("file")->value();
        
        StaticJsonDocument<256> doc;
        doc["cmd"] = "GET";
        doc["file"] = filename;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Download started");
    });
    
    server.on("/api/delete", HTTP_DELETE, [](AsyncWebServerRequest *request){
        if (!request->hasParam("file")) {
            request->send(400, "text/plain", "Missing file parameter");
            return;
        }
        
        String filename = request->getParam("file")->value();
        
        StaticJsonDocument<256> doc;
        doc["cmd"] = "DELETE";
        doc["file"] = filename;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Delete requested");
    });
    
    server.on("/api/start", HTTP_POST, [](AsyncWebServerRequest *request){
        String driver = "Unknown";
        String vin = "Unknown";
        
        if (request->hasParam("driver", true)) {
            driver = request->getParam("driver", true)->value();
        }
        if (request->hasParam("vin", true)) {
            vin = request->getParam("vin", true)->value();
        }
        
        StaticJsonDocument<256> doc;
        doc["cmd"] = "START_SESSION";
        doc["driver"] = driver;
        doc["vin"] = vin;
        
        String json;
        serializeJson(doc, json);
        sendCommandToPico(json);
        
        request->send(200, "text/plain", "Session start requested");
    });
    
    server.on("/api/stop", HTTP_POST, [](AsyncWebServerRequest *request){
        sendCommandToPico("{\"cmd\":\"STOP_SESSION\"}");
        request->send(200, "text/plain", "Session stop requested");
    });
    
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    
    server.begin();
    
    // Notify Pico that ESP is ready
    PicoSerial.println("{\"type\":\"ready\"}");
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
    ws.cleanupClients();
    processSerialData();
    delay(1);  // Very small delay
}

// ============================================================================
// Serial Communication
// ============================================================================

void processSerialData() {
    while (PicoSerial.available()) {
        char c = PicoSerial.read();
        
        if (c == '\n') {
            // Complete JSON line received
            if (jsonBuffer.length() > 0) {
                processJSONMessage(jsonBuffer);
                jsonBuffer = "";
            }
        } else if (c >= 32 && c <= 126) {
            // Only accept printable ASCII
            jsonBuffer += c;
            
            // Prevent buffer overflow
            if (jsonBuffer.length() > MAX_JSON_BUFFER) {
                jsonBuffer = "";  // Discard corrupted data
            }
        }
        // Ignore non-printable characters (except newline)
    }
}

void processJSONMessage(const String& jsonString) {
    StaticJsonDocument<2048> doc;
    DeserializationError error = deserializeJson(doc, jsonString);
    
    if (error) {
        // Don't spam errors, just drop bad packets
        return;
    }
    
    String type = doc["type"] | "";
    
    if (type == "update") {
        handleTelemetryUpdate(doc, jsonString);
    }
    else if (type == "satellites") {
        handleSatelliteUpdate(doc, jsonString);
    }
    else if (type == "files") {
        handleFileList(doc, jsonString);
    }
    else if (type == "file_start" || type == "file_chunk" || type == "file_end") {
        handleFileTransfer(doc, jsonString);
    }
    else if (type == "ok" || type == "error") {
        handleResponse(doc, jsonString);
    }
}

void handleTelemetryUpdate(JsonDocument& doc, const String& jsonString) {
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
    
    // Broadcast to WebSocket clients
    ws.textAll(jsonString);
}

void handleSatelliteUpdate(JsonDocument& doc, const String& jsonString) {
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
    ws.textAll(jsonString);
}

void handleFileList(JsonDocument& doc, const String& jsonString) {
    ws.textAll(jsonString);
}

void handleFileTransfer(JsonDocument& doc, const String& jsonString) {
    ws.textAll(jsonString);
}

void handleResponse(JsonDocument& doc, const String& jsonString) {
    ws.textAll(jsonString);
}

void sendCommandToPico(const String& json) {
    PicoSerial.println(json);
}
// ============================================================================
// Serve HTML Page - Chunked Response
// ============================================================================

void handleRootPage(AsyncWebServerRequest *request) {
    AsyncResponseStream *response = request->beginResponseStream("text/html");
    
    // Send chunks from PROGMEM
    response->print(FPSTR(HTML_HEADER));
    response->print(FPSTR(HTML_TELEMETRY));
    response->print(FPSTR(HTML_SATELLITES));
    response->print(FPSTR(HTML_FILES));
    response->print(FPSTR(HTML_CONTROL));
    response->print(FPSTR(HTML_JAVASCRIPT));
    
    request->send(response);
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
        if (telemetry.valid) {
            String json = getTelemetryJSON();
            client->text(json);
        }
    }
    else if (type == WS_EVT_DATA) {
        AwsFrameInfo *info = (AwsFrameInfo*)arg;
        
        if (info->final && info->index == 0 && info->len == len) {
            String msg = "";
            for (size_t i = 0; i < len; i++) {
                msg += (char)data[i];
            }
            sendCommandToPico(msg);
        }
    }
}
