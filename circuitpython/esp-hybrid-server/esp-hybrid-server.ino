/**
 * esp-hybrid-server.ino
 *
 * OpenPonyLogger ESP-01 Hybrid Web Server
 *
 * This ESP-01 firmware is "dataless" - it only maintains WiFi connections
 * and WebSocket clients. All content is served by the Pico via UART.
 *
 * Protocol: See ESP01_PROTOCOL.md
 *
 * UART Configuration Modes:
 * - Normal Mode (DEBUG_MODE = 0): Hardware UART on GPIO1(TX)/GPIO3(RX) @ 115200 baud
 * - Debug Mode (DEBUG_MODE = 1): Software Serial on GPIO2(TX)/GPIO0(RX) @ 9600 baud
 *
 * Debug mode allows USB serial monitoring while communicating with Pico
 * on alternate pins at slower speed for troubleshooting.
 *
 * Architecture:
 * - ESP handles WiFi (AP or STA mode)
 * - ESP runs HTTP server (port 80) and WebSocket server (port 81)
 * - All page requests forwarded to Pico via UART
 * - Pico streams page content back via UART
 * - Telemetry JSON broadcast to all WebSocket clients
 */

// Version information
#define ESP_VERSION "1.0.0"
#define ESP_GIT_SHA "5e29f43"  // Update this when committing major changes

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>

// ============================================================================
// UART Mode Configuration
// ============================================================================

// Set to 1 for debug mode (GPIO2/0 @ 9600), 0 for normal mode (GPIO1/3 @ 115200)
#define DEBUG_MODE 0

#if DEBUG_MODE
  // Debug mode: Software Serial on GPIO2(TX) and GPIO0(RX) @ 9600 baud
  // Allows USB Serial debugging on hardware UART
  #include <SoftwareSerial.h>
  #define PICO_RX_PIN 0   // GPIO0 - RX from Pico
  #define PICO_TX_PIN 2   // GPIO2 - TX to Pico
  #define UART_BAUD 9600
  SoftwareSerial PicoSerial(PICO_RX_PIN, PICO_TX_PIN);  // RX, TX
  #define DEBUG_SERIAL Serial  // Hardware UART available for debugging
#else
  // Normal mode: Hardware UART on GPIO1(TX) and GPIO3(RX) @ 115200 baud
  #define UART_BAUD 115200
  #define PicoSerial Serial
  // No debug serial available in normal mode
#endif

// ============================================================================
// Embedded HTML Page (PROGMEM saves RAM)
// ============================================================================

const char INDEX_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OpenPony Logger</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial,sans-serif;background:#1a1a1a;color:#e0e0e0;padding:20px}.header{text-align:center;margin-bottom:20px;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:10px}.header h1{color:white;font-size:2em}.header .time{color:rgba(255,255,255,0.8);font-size:0.9em;margin-top:5px;font-family:'Courier New',monospace}.status{text-align:center;padding:10px;margin-bottom:20px;border-radius:5px;font-weight:bold}.status.connected{background:#2d5016;color:#7dff7d}.status.disconnected{background:#501616;color:#ff7d7d}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}.card{background:#2a2a2a;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.3)}.card h2{color:#667eea;font-size:1.2em;margin-bottom:15px;border-bottom:2px solid #667eea;padding-bottom:8px}.large-value{font-size:3em;text-align:center;font-weight:bold;color:#667eea;margin:20px 0;font-family:'Courier New',monospace}.metric{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #3a3a3a}.metric-label{color:#999;font-size:0.9em}.metric-value{color:#e0e0e0;font-weight:bold;font-family:'Courier New',monospace}</style></head><body>
<div class="header"><h1>🏎️ OpenPony Logger</h1><div class="time" id="time">--</div></div>
<div id="status" class="status disconnected">Connecting...</div>
<div class="grid">
<div class="card"><h2>Speed</h2><div class="large-value" id="speed">0.0</div><div style="text-align:center;color:#999">MPH</div></div>
<div class="card"><h2>GPS</h2>
<div class="metric"><span class="metric-label">Lat</span><span class="metric-value" id="lat">--</span></div>
<div class="metric"><span class="metric-label">Lon</span><span class="metric-value" id="lon">--</span></div>
<div class="metric"><span class="metric-label">Sats</span><span class="metric-value" id="sats">0</span></div></div>
<div class="card"><h2>G-Forces</h2>
<div class="metric"><span class="metric-label">X</span><span class="metric-value" id="gx">+0.0</span></div>
<div class="metric"><span class="metric-label">Y</span><span class="metric-value" id="gy">+0.0</span></div>
<div class="metric"><span class="metric-label">Z</span><span class="metric-value" id="gz">+1.0</span></div></div>
</div>
<div class="card" style="grid-column:1/-1"><h2>Session Control</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px">
<div><div class="metric"><span class="metric-label">Session #</span><span class="metric-value" id="session-num">--</span></div>
<div class="metric"><span class="metric-label">Status</span><span class="metric-value" id="session-status">--</span></div></div>
<div style="display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap">
<button id="btn-start" onclick="sessionStart()" style="background:#2d5016;color:#7dff7d;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;font-weight:bold">▶ Start</button>
<button id="btn-stop" onclick="sessionStop()" style="background:#501616;color:#ff7d7d;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;font-weight:bold">⏹ Stop</button>
<button onclick="sessionRestart()" style="background:#667eea;color:white;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;font-weight:bold">🔄 Restart</button>
</div></div>
<div id="session-form" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px">
<input type="text" id="input-driver" placeholder="Driver Name" style="background:#3a3a3a;color:#e0e0e0;border:1px solid #667eea;padding:8px;border-radius:5px">
<input type="text" id="input-vehicle" placeholder="Vehicle" style="background:#3a3a3a;color:#e0e0e0;border:1px solid #667eea;padding:8px;border-radius:5px">
<input type="text" id="input-track" placeholder="Track/Location" style="background:#3a3a3a;color:#e0e0e0;border:1px solid #667eea;padding:8px;border-radius:5px">
</div>
<button onclick="updateSession()" style="background:#764ba2;color:white;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%">💾 Save & Restart Session</button>
</div>
<div class="card" style="grid-column:1/-1"><h2>Session Files</h2>
<button onclick="loadFiles()" style="background:#667eea;color:white;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;margin-bottom:10px">Refresh</button>
<div id="files" style="overflow-x:auto">Loading...</div></div>
<div class="card" style="grid-column:1/-1;font-size:0.85em;color:#999;text-align:center">
<div style="display:flex;justify-content:space-around;flex-wrap:wrap;gap:20px">
<div><strong>ESP Firmware:</strong> <span id="esp-version">Loading...</span></div>
<div><strong>Pico Firmware:</strong> <span id="pico-version">Loading...</span></div>
</div></div>
</div><script>
function loadFiles(){fetch('/api/files').then(r=>r.json()).then(files=>{let html='<table style="width:100%;border-collapse:collapse">';html+='<tr style="border-bottom:2px solid #667eea"><th style="text-align:left;padding:8px">Session</th><th style="text-align:left;padding:8px">File</th><th style="text-align:right;padding:8px">Size</th><th style="text-align:center;padding:8px">Download</th></tr>';files.forEach(f=>{const sizeMB=(f.size/1024/1024).toFixed(2);const sizeKB=(f.size/1024).toFixed(1);const size=f.size>1024*1024?sizeMB+' MB':sizeKB+' KB';html+=`<tr style="border-bottom:1px solid #3a3a3a"><td style="padding:8px">#${f.session}</td><td style="padding:8px">${f.filename}</td><td style="text-align:right;padding:8px">${size}</td><td style="text-align:center;padding:8px"><a href="/api/download?file=${f.filename}" download="${f.filename}" style="background:#667eea;color:white;text-decoration:none;padding:4px 12px;border-radius:3px;font-size:0.9em">⬇</a></td></tr>`});html+='</table>';document.getElementById('files').innerHTML=html}).catch(()=>{document.getElementById('files').innerHTML='<p style="color:#ff7d7d">Error loading files</p>'})}
function loadVersions(){fetch('/api/version').then(r=>r.json()).then(v=>{document.getElementById('esp-version').textContent=v.esp_version+' ('+v.esp_git+')';document.getElementById('pico-version').textContent=v.pico_version+' ('+v.pico_git+')'}).catch(()=>{document.getElementById('esp-version').textContent='Error';document.getElementById('pico-version').textContent='Error'})}
function loadSessionInfo(){fetch('/api/session/info').then(r=>r.json()).then(s=>{document.getElementById('session-num').textContent='#'+s.session_num;document.getElementById('session-status').textContent=s.running?'Running':'Stopped';document.getElementById('session-status').style.color=s.running?'#7dff7d':'#ff7d7d';document.getElementById('input-driver').value=s.driver;document.getElementById('input-vehicle').value=s.vehicle;document.getElementById('input-track').value=s.track;document.getElementById('btn-start').disabled=s.running;document.getElementById('btn-stop').disabled=!s.running}).catch(()=>console.error('Failed to load session info'))}
function sessionStart(){fetch('/api/session/start',{method:'POST'}).then(()=>setTimeout(loadSessionInfo,500)).catch(e=>alert('Error: '+e))}
function sessionStop(){fetch('/api/session/stop',{method:'POST'}).then(()=>setTimeout(loadSessionInfo,500)).catch(e=>alert('Error: '+e))}
function sessionRestart(){if(confirm('Restart session? Current session will be closed and a new one will begin.')){fetch('/api/session/restart',{method:'POST'}).then(()=>setTimeout(loadSessionInfo,500)).catch(e=>alert('Error: '+e))}}
function updateSession(){const driver=document.getElementById('input-driver').value;const vehicle=document.getElementById('input-vehicle').value;const track=document.getElementById('input-track').value;if(!driver&&!vehicle&&!track){alert('Please enter at least one field');return}if(confirm('Save session info and restart? Current session will be closed and a new one will begin with the updated information.')){const formData=new FormData();if(driver)formData.append('driver',driver);if(vehicle)formData.append('vehicle',vehicle);if(track)formData.append('track',track);fetch('/api/session/update',{method:'POST',body:formData}).then(()=>setTimeout(loadSessionInfo,500)).catch(e=>alert('Error: '+e))}}
window.addEventListener('load',()=>{loadFiles();loadVersions();loadSessionInfo()});
let ws=new WebSocket('ws://'+window.location.hostname+'/ws');
ws.onopen=()=>{document.getElementById('status').textContent='Connected';document.getElementById('status').className='status connected'};
ws.onmessage=(e)=>{const d=JSON.parse(e.data);
if(d.timestamp){const date=new Date(d.timestamp*1000);document.getElementById('time').textContent=date.toLocaleString()}
if(d.speed)document.getElementById('speed').textContent=d.speed.toFixed(1);
if(d.lat)document.getElementById('lat').textContent=d.lat.toFixed(6);
if(d.lon)document.getElementById('lon').textContent=d.lon.toFixed(6);
if(d.satellites)document.getElementById('sats').textContent=d.satellites;
if(d.gx)document.getElementById('gx').textContent=(d.gx>=0?'+':'')+d.gx.toFixed(2);
if(d.gy)document.getElementById('gy').textContent=(d.gy>=0?'+':'')+d.gy.toFixed(2);
if(d.session_status){document.getElementById('session-num').textContent='#'+d.session_status.session_num;document.getElementById('session-status').textContent=d.session_status.running?'Running':'Stopped';document.getElementById('session-status').style.color=d.session_status.running?'#7dff7d':'#ff7d7d';document.getElementById('btn-start').disabled=d.session_status.running;document.getElementById('btn-stop').disabled=!d.session_status.running}
if(d.gz)document.getElementById('gz').textContent=(d.gz>=0?'+':'')+d.gz.toFixed(2)};
ws.onclose=()=>{document.getElementById('status').textContent='Disconnected';document.getElementById('status').className='status disconnected';setTimeout(()=>location.reload(),2000)};
</script></body></html>
)rawliteral";

// ============================================================================
// Configuration
// ============================================================================

#define STATUS_INTERVAL 5000  // Send status every 5 seconds

// WiFi configuration (received from Pico)
String wifi_mode = "ap";      // "ap" or "sta"
String wifi_ssid = "";
String wifi_password = "";
IPAddress wifi_address;
IPAddress wifi_netmask;
IPAddress wifi_gateway;

// Version information (received from Pico)
String pico_version = "unknown";
String pico_git = "unknown";

// Session information (received from Pico)
bool session_running = true;
int session_num = 0;
String session_driver = "Unknown";
String session_vehicle = "Unknown";
String session_track = "";
AsyncWebServerRequest* sessionInfoRequest = nullptr;

// ============================================================================
// Servers
// ============================================================================

AsyncWebServer httpServer(80);
AsyncWebSocket wsServer("/ws");

// ============================================================================
// State
// ============================================================================

bool configReceived = false;
bool wifiReady = false;
unsigned long lastStatusTime = 0;

// Incoming line buffer from Pico
String uartLineBuffer = "";
const size_t MAX_UART_LINE = 512;

// File browser state
struct FileInfo {
    String filename;
    uint32_t size;
    uint16_t session_num;
};
FileInfo fileList[10];  // Store up to 10 files
int fileCount = 0;
bool fileListReady = false;
AsyncWebServerRequest* fileListRequest = nullptr;
unsigned long fileListRequestTime = 0;

// File download state (using pre-allocated buffer with size limits)
bool downloadingFile = false;
String downloadFilename = "";
uint32_t downloadSize = 0;
String downloadBuffer = "";
AsyncWebServerRequest* downloadRequest = nullptr;
unsigned long downloadRequestTime = 0;

const uint32_t MAX_DOWNLOAD_SIZE = 32768;  // 32KB max file size for downloads

const unsigned long FILE_REQUEST_TIMEOUT = 3000;  // 3 second timeout for stalled transfers
const unsigned long DOWNLOAD_ACTIVITY_TIMEOUT = 5000;  // 5 seconds with no data = timeout

// ============================================================================
// Setup
// ============================================================================

void setup() {
    // Initialize UART for Pico communication
#if DEBUG_MODE
    // Debug mode: Initialize software serial for Pico, hardware serial for debug
    DEBUG_SERIAL.begin(115200);  // Hardware UART for USB debugging
    PicoSerial.begin(UART_BAUD);  // Software serial for Pico @ 9600
    delay(100);
    DEBUG_SERIAL.println("\n\n=== ESP-01 Debug Mode ===");
    DEBUG_SERIAL.println("SoftwareSerial on GPIO2(TX)/GPIO0(RX) @ 9600 baud");
    DEBUG_SERIAL.println("USB Serial available for debugging");
    DEBUG_SERIAL.println("========================\n");
#else
    // Normal mode: Hardware UART for Pico @ 115200, 8N1 format
    PicoSerial.begin(UART_BAUD, SERIAL_8N1);
    PicoSerial.setRxBufferSize(1024);
    delay(100);
#endif

    // Request configuration from Pico
    requestConfig();

    // Wait for configuration (with timeout)
    unsigned long start = millis();
#if DEBUG_MODE
    DEBUG_SERIAL.println("Waiting for config from Pico...");
#endif
    while (!configReceived && (millis() - start < 10000)) {
        processUART();
        delay(10);
    }

    if (!configReceived) {
#if DEBUG_MODE
        DEBUG_SERIAL.println("Config timeout - using defaults");
#endif
        // No config received - use defaults and try again later
        wifi_mode = "ap";
        wifi_ssid = "OpenPonyLogger";
        wifi_password = "mustanggt";
        wifi_address = IPAddress(192, 168, 4, 1);
        wifi_netmask = IPAddress(255, 255, 255, 0);
        wifi_gateway = IPAddress(192, 168, 4, 1);
    }
#if DEBUG_MODE
    else {
        DEBUG_SERIAL.println("Config received from Pico");
    }
#endif

    // Setup WiFi
    setupWiFi();

    // Setup HTTP server
    setupHTTPServer();

    // Setup WebSocket server
    setupWebSocket();

    // Start servers
    httpServer.begin();

    // Notify Pico we're serving
    sendLine("ESP:serving");

    wifiReady = true;
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
    // Process incoming UART data from Pico
    processUART();

    // Check for file list request timeout
    if (fileListRequest != nullptr && (millis() - fileListRequestTime > FILE_REQUEST_TIMEOUT)) {
        fileListRequest->send(504, "text/plain", "Timeout - no response from logger");
        fileListRequest = nullptr;
    }

    // Check for file download request timeout (uses activity timeout - resets when data arrives)
    if (downloadRequest != nullptr && (millis() - downloadRequestTime > DOWNLOAD_ACTIVITY_TIMEOUT)) {
        downloadRequest->send(504, "text/plain", "Download timeout - no data from logger");
        downloadRequest = nullptr;
        downloadingFile = false;
        downloadBuffer = "";
    }

    // Cleanup WebSocket clients
    wsServer.cleanupClients();

    // Send periodic status updates
    if (wifiReady && (millis() - lastStatusTime > STATUS_INTERVAL)) {
        sendStatus();
        lastStatusTime = millis();
    }

    yield();
}

// ============================================================================
// WiFi Setup
// ============================================================================

void setupWiFi() {
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);

    if (wifi_mode == "ap") {
        // Access Point mode
        WiFi.mode(WIFI_AP);
        WiFi.softAPConfig(wifi_address, wifi_gateway, wifi_netmask);
        WiFi.softAP(wifi_ssid.c_str(), wifi_password.c_str());
    } else {
        // Station mode - connect to existing network
        WiFi.mode(WIFI_STA);
        WiFi.config(wifi_address, wifi_gateway, wifi_netmask);
        WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());

        // Wait for connection (30 second timeout)
        int timeout = 30;
        while (WiFi.status() != WL_CONNECTED && timeout > 0) {
            delay(1000);
            timeout--;
        }

        // If failed, fall back to AP mode
        if (WiFi.status() != WL_CONNECTED) {
            wifi_mode = "ap";
            wifi_ssid = "OpenPonyLogger-Fallback";
            WiFi.mode(WIFI_AP);
            WiFi.softAPConfig(wifi_address, wifi_gateway, wifi_netmask);
            WiFi.softAP(wifi_ssid.c_str(), wifi_password.c_str());
        }
    }
}

// ============================================================================
// HTTP Server Setup
// ============================================================================

void setupHTTPServer() {
    // Serve static HTML page from PROGMEM (completely non-blocking)
    httpServer.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
        request->send_P(200, "text/html", INDEX_HTML);
    });

    httpServer.on("/index.html", HTTP_GET, [](AsyncWebServerRequest *request){
        request->send_P(200, "text/html", INDEX_HTML);
    });

    // File list API - request list from Pico and return as JSON
    httpServer.on("/api/files", HTTP_GET, [](AsyncWebServerRequest *request){
        // If already processing a request, reject
        if (fileListRequest != nullptr) {
            request->send(503, "text/plain", "Busy");
            return;
        }

        // Request file list from Pico
        sendLine("ESP:list");

        // Store request for async response
        fileListRequest = request;
        fileListRequestTime = millis();
        fileListReady = false;

        // Response will be sent when FILELIST arrives from Pico
        // Handled in processLine() when END marker received
    });

    // File download API - request file from Pico and send to browser
    httpServer.on("/api/download", HTTP_GET, [](AsyncWebServerRequest *request){
        if (!request->hasParam("file")) {
            request->send(400, "text/plain", "Missing file parameter");
            return;
        }

        // Check if already downloading
        if (downloadingFile) {
            request->send(503, "text/plain", "Download already in progress");
            return;
        }

        String filename = request->getParam("file")->value();

        // Reset download state
        downloadingFile = true;
        downloadFilename = filename;
        downloadBuffer = "";
        downloadRequestTime = millis();
        downloadRequest = request;

        // Request file from Pico
        sendLine("ESP:download " + filename);

        // Response will be sent when file arrives and is complete
    });

    // Version info API - returns both ESP and Pico versions
    httpServer.on("/api/version", HTTP_GET, [](AsyncWebServerRequest *request){
        String json = "{";
        json += "\"esp_version\":\"" + String(ESP_VERSION) + "\",";
        json += "\"esp_git\":\"" + String(ESP_GIT_SHA) + "\",";
        json += "\"pico_version\":\"" + pico_version + "\",";
        json += "\"pico_git\":\"" + pico_git + "\"";
        json += "}";
        request->send(200, "application/json", json);
    });

    // Session control APIs
    httpServer.on("/api/session/stop", HTTP_POST, [](AsyncWebServerRequest *request){
        sendLine("ESP:session_stop");
        request->send(200, "text/plain", "Stop command sent");
    });

    httpServer.on("/api/session/start", HTTP_POST, [](AsyncWebServerRequest *request){
        sendLine("ESP:session_start");
        request->send(200, "text/plain", "Start command sent");
    });

    httpServer.on("/api/session/restart", HTTP_POST, [](AsyncWebServerRequest *request){
        sendLine("ESP:session_restart");
        request->send(200, "text/plain", "Restart command sent");
    });

    httpServer.on("/api/session/update", HTTP_POST, [](AsyncWebServerRequest *request){
        // Get parameters from POST body
        String driver = request->hasParam("driver", true) ? request->getParam("driver", true)->value() : "";
        String vehicle = request->hasParam("vehicle", true) ? request->getParam("vehicle", true)->value() : "";
        String track = request->hasParam("track", true) ? request->getParam("track", true)->value() : "";

        // Build command string
        String cmd = "ESP:session_update ";
        if (driver.length() > 0) cmd += "driver=" + driver;
        if (vehicle.length() > 0) {
            if (driver.length() > 0) cmd += ",";
            cmd += "vehicle=" + vehicle;
        }
        if (track.length() > 0) {
            if (driver.length() > 0 || vehicle.length() > 0) cmd += ",";
            cmd += "track=" + track;
        }

        sendLine(cmd);
        request->send(200, "text/plain", "Update command sent");
    });

    httpServer.on("/api/session/info", HTTP_GET, [](AsyncWebServerRequest *request){
        // Request session info from Pico
        if (sessionInfoRequest != nullptr) {
            request->send(503, "text/plain", "Busy");
            return;
        }

        sendLine("ESP:session_info");
        sessionInfoRequest = request;
        // Response will be sent when SESSION_INFO arrives from Pico
    });

    // 404 handler
    httpServer.onNotFound([](AsyncWebServerRequest *request){
        request->send(404, "text/plain", "Not Found");
    });
}

// ============================================================================
// WebSocket Setup
// ============================================================================

void setupWebSocket() {
    wsServer.onEvent([](AsyncWebSocket *server, AsyncWebSocketClient *client,
                        AwsEventType type, void *arg, uint8_t *data, size_t len) {

        if (type == WS_EVT_CONNECT) {
            // Client connected - just keep connection open
            // Telemetry will be broadcast to all clients
        }
        else if (type == WS_EVT_DISCONNECT) {
            // Client disconnected - cleanup is automatic
        }
        else if (type == WS_EVT_DATA) {
            // Client sent data - forward to Pico (future enhancement)
        }
    });

    httpServer.addHandler(&wsServer);
}

// ============================================================================
// UART Communication
// ============================================================================

void processUART() {
    while (PicoSerial.available()) {
        char c = PicoSerial.read();

        // If downloading file, buffer all bytes (including binary data)
        if (downloadingFile && downloadSize > 0) {
            downloadBuffer += c;

            // Reset timeout on activity (every 256 bytes to reduce overhead)
            if (downloadBuffer.length() % 256 == 0) {
                downloadRequestTime = millis();
            }

            // Check if we've received all the file data plus END marker
            if (downloadBuffer.length() >= downloadSize) {
                // Check for END marker after binary data
                if (downloadBuffer.endsWith("\nEND\n") || downloadBuffer.endsWith("\nEND")) {
                    // Remove END marker from buffer
                    int endPos = downloadBuffer.lastIndexOf("\nEND");
                    if (endPos > 0) {
                        downloadBuffer = downloadBuffer.substring(0, endPos);
                    }

                    // Send file to browser
                    if (downloadRequest) {
                        AsyncWebServerResponse *response = downloadRequest->beginResponse(
                            "application/octet-stream", downloadSize,
                            [](uint8_t *buffer, size_t maxLen, size_t index) -> size_t {
                                // Copy chunk of download buffer to output
                                size_t remaining = downloadBuffer.length() - index;
                                size_t toSend = (remaining < maxLen) ? remaining : maxLen;
                                if (toSend > 0) {
                                    memcpy(buffer, downloadBuffer.c_str() + index, toSend);
                                }
                                return toSend;
                            });
                        response->addHeader("Content-Disposition", "attachment; filename=\"" + downloadFilename + "\"");
                        downloadRequest->send(response);
                        downloadRequest = nullptr;
                    }

                    // Reset download state
                    downloadingFile = false;
                    downloadBuffer = "";
                }
            }
            continue;
        }

        // Normal line-based processing
        if (c == '\n') {
            // Complete line received
            if (uartLineBuffer.length() > 0) {
#if DEBUG_MODE
                DEBUG_SERIAL.print("[PICO RX] ");
                DEBUG_SERIAL.println(uartLineBuffer);
#endif
                processLine(uartLineBuffer);
                uartLineBuffer = "";
            }
        } else if (c >= 32 && c <= 126) {
            // Printable ASCII
            uartLineBuffer += c;

            // Prevent buffer overflow
            if (uartLineBuffer.length() > MAX_UART_LINE) {
                uartLineBuffer = "";
            }
        }
    }
}

void processLine(const String& line) {
    // CONFIG sequence
    if (line == "CONFIG") {
        // Start of configuration
        return;
    }

    // Check for END marker - could be config, file list, or session info
    if (line == "END") {
        // If we were receiving session info, send the response
        if (receivingSessionInfo && sessionInfoRequest != nullptr) {
            String json = "{";
            json += "\"session_num\":" + String(session_num) + ",";
            json += "\"running\":" + String(session_running ? "true" : "false") + ",";
            json += "\"driver\":\"" + session_driver + "\",";
            json += "\"vehicle\":\"" + session_vehicle + "\",";
            json += "\"track\":\"" + session_track + "\"";
            json += "}";

            sessionInfoRequest->send(200, "application/json", json);
            sessionInfoRequest = nullptr;
            receivingSessionInfo = false;
        }

        // If we have a file list request pending, this is the end of file list
        if (fileListRequest != nullptr && fileCount >= 0) {
            // Build JSON response
            String json = "[";
            for (int i = 0; i < fileCount; i++) {
                if (i > 0) json += ",";
                json += "{";
                json += "\"filename\":\"" + fileList[i].filename + "\",";
                json += "\"size\":" + String(fileList[i].size) + ",";
                json += "\"session\":" + String(fileList[i].session_num);
                json += "}";
            }
            json += "]";

            fileListRequest->send(200, "application/json", json);
            fileListRequest = nullptr;
            fileListReady = true;
        }

        // Also mark config as received (doesn't hurt if already set)
        configReceived = true;
        return;
    }

    // Configuration parameter: key=value
    if (line.indexOf('=') > 0 && !configReceived) {
        int eqPos = line.indexOf('=');
        String key = line.substring(0, eqPos);
        String value = line.substring(eqPos + 1);

        if (key == "mode") wifi_mode = value;
        else if (key == "ssid") wifi_ssid = value;
        else if (key == "password") wifi_password = value;
        else if (key == "address") wifi_address.fromString(value);
        else if (key == "netmask") wifi_netmask.fromString(value);
        else if (key == "gateway") wifi_gateway.fromString(value);
        else if (key == "pico_version") pico_version = value;
        else if (key == "pico_git") pico_git = value;

        return;
    }

    // WebSocket telemetry: WS:{json}
    if (line.startsWith("WS:")) {
        String json = line.substring(3);
        wsServer.textAll(json);
        return;
    }

    // Session status response: SESSION_STATUS:status,session_num
    if (line.startsWith("SESSION_STATUS:")) {
        String data = line.substring(15);
        int commaPos = data.indexOf(',');
        if (commaPos > 0) {
            String status = data.substring(0, commaPos);
            session_num = data.substring(commaPos + 1).toInt();
            session_running = (status == "running");

            // Broadcast status update to WebSocket clients
            String wsMsg = "{\"session_status\":{";
            wsMsg += "\"running\":" + String(session_running ? "true" : "false") + ",";
            wsMsg += "\"session_num\":" + String(session_num);
            wsMsg += "}}";
            wsServer.textAll(wsMsg);
        }
        return;
    }

    // Session info response header: SESSION_INFO
    static bool receivingSessionInfo = false;
    static String sessionInfoData = "";

    if (line == "SESSION_INFO") {
        receivingSessionInfo = true;
        sessionInfoData = "";
        return;
    }

    // Session info field (while receiving session info)
    if (receivingSessionInfo && line.indexOf('=') > 0) {
        int eqPos = line.indexOf('=');
        String key = line.substring(0, eqPos);
        String value = line.substring(eqPos + 1);

        if (key == "session_num") session_num = value.toInt();
        else if (key == "running") session_running = (value == "True" || value == "true" || value == "1");
        else if (key == "driver") session_driver = value;
        else if (key == "vehicle") session_vehicle = value;
        else if (key == "track") session_track = value;

        // Check for END on next iteration
        return;
    }

    // File list response: FILELIST:count
    if (line.startsWith("FILELIST:")) {
        int count = line.substring(9).toInt();
        fileCount = 0;  // Reset counter
        return;
    }

    // File list entry: filename|size|session_num
    if (fileCount < 10 && line.indexOf('|') > 0) {
        int pipe1 = line.indexOf('|');
        int pipe2 = line.indexOf('|', pipe1 + 1);
        if (pipe2 > pipe1) {
            fileList[fileCount].filename = line.substring(0, pipe1);
            fileList[fileCount].size = line.substring(pipe1 + 1, pipe2).toInt();
            fileList[fileCount].session_num = line.substring(pipe2 + 1).toInt();
            fileCount++;
            return;
        }
    }

    // File download start: DOWNLOAD:filename:size
    if (line.startsWith("DOWNLOAD:")) {
        int colon1 = line.indexOf(':', 9);
        if (colon1 > 0) {
            downloadFilename = line.substring(9, colon1);
            downloadSize = line.substring(colon1 + 1).toInt();
            downloadRequestTime = millis();  // Reset timeout - data is arriving

            // Check if file is too large for available memory
            uint32_t freeHeap = ESP.getFreeHeap();
            uint32_t requiredMem = downloadSize + 512;  // File + overhead

            if (downloadSize > MAX_DOWNLOAD_SIZE || requiredMem > (freeHeap - 8192)) {
                // File too large - reject download
                if (downloadRequest) {
                    String errorMsg = "File too large (" + String(downloadSize) +
                                    " bytes). Max: " + String(MAX_DOWNLOAD_SIZE) +
                                    " bytes, Free heap: " + String(freeHeap) + " bytes";
                    downloadRequest->send(507, "text/plain", errorMsg);
                    downloadRequest = nullptr;
                }
                downloadingFile = false;
                return;
            }

            // Pre-allocate memory for download buffer to avoid reallocations
            downloadBuffer.reserve(downloadSize + 100);
        }
        return;
    }

    // Download error
    if (line == "ERROR") {
        if (downloadingFile && downloadRequest) {
            downloadRequest->send(500, "text/plain", "Download failed");
            downloadingFile = false;
            downloadRequest = nullptr;
        }
        return;
    }

    // Ignore page serving messages (HTML is now static on ESP)
    if (line.startsWith("FILE:") || line.startsWith("ESP:get") || line == "404") {
        return;
    }
}

void sendLine(const String& line) {
#if DEBUG_MODE
    DEBUG_SERIAL.print("[PICO TX] ");
    DEBUG_SERIAL.println(line);
#endif
    PicoSerial.println(line);
}

void requestConfig() {
    delay(100);
    sendLine("+++");
    sendLine("ESP:config");
}

void sendStatus() {
    int clients = wsServer.count();
    unsigned long uptime = millis() / 1000;

    String status = "ESP:status clients=" + String(clients) +
                    " uptime=" + String(uptime);

    // Add RSSI if in STA mode
    if (wifi_mode == "sta" && WiFi.status() == WL_CONNECTED) {
        status += " rssi=" + String(WiFi.RSSI());
    }

    sendLine(status);
}
