/*
 * esp01s_openponylogger.ino
 * Lightweight web interface for track day telemetry
 */

#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
//#include <ESPAsyncWebSocket.h>
#include <SoftwareSerial.h>
SoftwareSerial Serial2(0, 2);  // RX=GPIO0, TX=GPIO2

const char* ssid = "OpenPonyLogger";
const char* password = "mustanggt";

AsyncWebServer server(80);
AsyncWebSocket ws("/live");

// Current telemetry state
String currentTelemetry = "{}";
String sessionFiles = "";

// ============================================================================
// Lightweight HTML (Embedded)
// ============================================================================

const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenPonyLogger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #fff;
            padding: 10px;
        }
        .header {
            background: #1a1a1a;
            padding: 15px;
            border-bottom: 2px solid #ff6b35;
            margin-bottom: 15px;
        }
        h1 {
            color: #ff6b35;
            font-size: 1.5rem;
        }
        .status {
            display: flex;
            gap: 15px;
            font-size: 0.9rem;
            margin-top: 5px;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #f44336;
            display: inline-block;
        }
        .status-dot.connected { background: #4caf50; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        .card {
            background: #1a1a1a;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 15px;
        }
        .card h2 {
            color: #ff6b35;
            font-size: 1.1rem;
            margin-bottom: 10px;
        }
        .value {
            font-size: 2rem;
            color: #ff6b35;
            font-weight: bold;
        }
        .label {
            color: #808080;
            font-size: 0.8rem;
            margin-bottom: 5px;
        }
        .gps-sky {
            width: 100%;
            height: 250px;
            background: #000;
            border-radius: 50%;
            position: relative;
            border: 2px solid #404040;
        }
        .sat {
            position: absolute;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4caf50;
        }
        .gforce-graph {
            width: 100%;
            height: 250px;
            background: #000;
            border: 1px solid #404040;
            position: relative;
        }
        .session-list {
            list-style: none;
        }
        .session-item {
            background: #252525;
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .btn {
            background: #ff6b35;
            color: #fff;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .btn:hover { background: #ff5722; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐎 OpenPonyLogger</h1>
        <div class="status">
            <span><span class="status-dot" id="wsDot"></span> WebSocket</span>
            <span id="rtcStatus">RTC: --</span>
            <span id="gpsStatus">GPS: --</span>
        </div>
    </div>
    
    <div class="grid">
        <!-- GPS Sky View -->
        <div class="card">
            <h2>GPS Sky View</h2>
            <canvas id="gpsSky" class="gps-sky" width="250" height="250"></canvas>
            <div style="margin-top: 10px;">
                <div class="label">Position</div>
                <div style="font-size: 0.9rem;">
                    Lat: <span id="lat">--</span><br>
                    Lon: <span id="lon">--</span><br>
                    Speed: <span id="speed">--</span> knots<br>
                    HDOP: <span id="hdop">--</span>
                </div>
            </div>
        </div>
        
        <!-- G-Force Display -->
        <div class="card">
            <h2>G-Force</h2>
            <canvas id="gforceGraph" class="gforce-graph" width="300" height="250"></canvas>
            <div style="margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div>
                    <div class="label">Lateral (X)</div>
                    <div class="value" style="font-size: 1.2rem;" id="gx">0.00g</div>
                </div>
                <div>
                    <div class="label">Long (Y)</div>
                    <div class="value" style="font-size: 1.2rem;" id="gy">0.00g</div>
                </div>
                <div>
                    <div class="label">Vert (Z)</div>
                    <div class="value" style="font-size: 1.2rem;" id="gz">1.00g</div>
                </div>
            </div>
        </div>
        
        <!-- Sessions -->
        <div class="card">
            <h2>Recent Sessions</h2>
            <ul class="session-list" id="sessionList">
                <li>Loading...</li>
            </ul>
            <button class="btn" onclick="refreshSessions()">Refresh</button>
        </div>
    </div>
    
    <script>
        // WebSocket connection
        const ws = new WebSocket('ws://' + location.hostname + '/live');
        
        ws.onopen = () => {
            document.getElementById('wsDot').classList.add('connected');
            console.log('Connected');
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updateDisplay(data);
            } catch(e) {
                console.error('Parse error:', e);
            }
        };
        
        ws.onclose = () => {
            document.getElementById('wsDot').classList.remove('connected');
            setTimeout(() => location.reload(), 2000);
        };
        
        // Update display from telemetry
        function updateDisplay(data) {
            // RTC status
            document.getElementById('rtcStatus').textContent = 
                'RTC: ' + (data.rtc_synced ? 'GPS' : 'LOCAL');
            
            // GPS status
            if (data.gps && data.gps.fix) {
                document.getElementById('gpsStatus').textContent = 
                    'GPS: ' + data.gps.sats + ' sats';
                document.getElementById('lat').textContent = data.gps.lat.toFixed(6);
                document.getElementById('lon').textContent = data.gps.lon.toFixed(6);
                document.getElementById('speed').textContent = data.gps.speed.toFixed(1);
                document.getElementById('hdop').textContent = data.gps.hdop;
            } else {
                document.getElementById('gpsStatus').textContent = 'GPS: No Fix';
            }
            
            // G-force
            if (data.g) {
                document.getElementById('gx').textContent = data.g.x.toFixed(2) + 'g';
                document.getElementById('gy').textContent = data.g.y.toFixed(2) + 'g';
                document.getElementById('gz').textContent = data.g.z.toFixed(2) + 'g';
                
                // Draw G-force graph
                drawGForce(data.g.x, data.g.y);
            }
        }
        
        // Draw G-force graph
        function drawGForce(gx, gy) {
            const canvas = document.getElementById('gforceGraph');
            const ctx = canvas.getContext('2d');
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const scale = 100; // pixels per g
            
            // Clear
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Grid
            ctx.strokeStyle = '#404040';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(centerX, 0);
            ctx.lineTo(centerX, canvas.height);
            ctx.moveTo(0, centerY);
            ctx.lineTo(canvas.width, centerY);
            ctx.stroke();
            
            // Circles (0.5g increments)
            for (let i = 1; i <= 2; i++) {
                ctx.beginPath();
                ctx.arc(centerX, centerY, i * scale / 2, 0, Math.PI * 2);
                ctx.stroke();
            }
            
            // Current G-force
            const x = centerX + gx * scale;
            const y = centerY - gy * scale; // Invert Y
            
            ctx.fillStyle = '#ff6b35';
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();
            
            // Line from center
            ctx.strokeStyle = 'rgba(255, 107, 53, 0.5)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(x, y);
            ctx.stroke();
        }
        
        // GPS sky view (simplified)
        function drawGPSSky() {
            const canvas = document.getElementById('gpsSky');
            const ctx = canvas.getContext('2d');
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const radius = canvas.width / 2 - 10;
            
            // Sky background
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Border
            ctx.strokeStyle = '#404040';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.stroke();
            
            // Compass directions
            ctx.fillStyle = '#fff';
            ctx.font = '12px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('N', centerX, 20);
            ctx.fillText('S', centerX, canvas.height - 10);
            ctx.fillText('E', canvas.width - 15, centerY + 5);
            ctx.fillText('W', 15, centerY + 5);
        }
        
        // Request session list
        function refreshSessions() {
            // Send LIST command to Pico via WebSocket
            // (ESP forwards to Pico via UART)
            ws.send('LIST');
        }
        
        // Download session
        function downloadSession(filename) {
            window.location.href = '/download?file=' + filename;
        }
        
        // Initialize
        drawGPSSky();
        setTimeout(refreshSessions, 1000);
    </script>
</body>
</html>
)rawliteral";

// ============================================================================
// Setup
// ============================================================================

void setup() {
    Serial.begin(115200);  // USB debug
    //Serial2.begin(115200); // UART from/to Pico (RX=GPIO3, TX=GPIO1)
    Serial2.begin(9600); // UART from/to Pico (RX=GPIO3, TX=GPIO1)
    delay(1000);
    
    Serial.println("\nOpenPonyLogger ESP-01S v2.0");
    
    // WiFi AP
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ssid, password);
    
    IPAddress IP = WiFi.softAPIP();
    Serial.print("AP IP: ");
    Serial.println(IP);
    
    // WebSocket
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    
    // Main page
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
        request->send_P(200, "text/html", index_html);
    });
    
    // Download handler
    server.on("/download", HTTP_GET, [&](AsyncWebServerRequest *request){
        if (request->hasParam("file")) {
            String filename = request->getParam("file")->value();
            // Request file from Pico
            Serial2.print("GET ");
            Serial2.println(filename);
            // File will be streamed back...
            request->send(200, "text/plain", "Requesting file...");
        }
    });
    
    server.begin();
    Serial.println("Server started!");
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
    // Read telemetry from Pico
    if (Serial2.available()) {
        String line = Serial2.readStringUntil('\n');
        
        // Check if it's a command response or telemetry
        if (line.startsWith("FILES ")) {
            // Session list
            sessionFiles = line.substring(6);
            // TODO: Parse and format for web
        }
        else if (line.startsWith("{")) {
            // Telemetry JSON
            currentTelemetry = line;
            ws.textAll(line);
            
            Serial.print("→ ");
            Serial.println(line);
        }
    }
    
    // Forward commands from WebSocket to Pico
    // (Handled in onWsEvent)
    
    // Memory check every 30 seconds
    static unsigned long lastHeap = 0;
    if (millis() - lastHeap > 30000) {
        lastHeap = millis();
        Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
    }
}

void onWsEvent(AsyncWebSocket *server, AsyncWebSocketClient *client,
               AwsEventType type, void *arg, uint8_t *data, size_t len) {
    
    if(type == WS_EVT_CONNECT) {
        Serial.printf("WebSocket client #%u connected\n", client->id());
        
        // Send current state immediately
        if (currentTelemetry.length() > 0) {
            client->text(currentTelemetry);
        }
    }
    else if(type == WS_EVT_DISCONNECT) {
        Serial.printf("WebSocket client #%u disconnected\n", client->id());
    }
    else if(type == WS_EVT_DATA) {
        // Forward commands to Pico
        String cmd = String((char*)data).substring(0, len);
        Serial2.println(cmd);
        Serial.print("Command → Pico: ");
        Serial.println(cmd);
    }
}