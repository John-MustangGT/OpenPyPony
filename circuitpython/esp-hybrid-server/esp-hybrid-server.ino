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

// Page serving state
bool servingPage = false;
AsyncWebServerRequest* currentPageRequest = nullptr;
String pageContentBuffer = "";  // Buffer content until ready to send
unsigned long pageRequestTime = 0;  // Track when page request started
const unsigned long PAGE_TIMEOUT_MS = 5000;  // 5 second timeout

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

    // Check for page request timeout
    if (servingPage && (millis() - pageRequestTime > PAGE_TIMEOUT_MS)) {
        if (currentPageRequest) {
            currentPageRequest->send(504, "text/plain", "Gateway timeout - no response from logger");
        }
        servingPage = false;
        currentPageRequest = nullptr;
        pageContentBuffer = "";
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
    // Catch-all handler - forward ALL page requests to Pico
    // This is truly async - we buffer content and send when complete
    httpServer.onNotFound([](AsyncWebServerRequest *request) {
        String path = request->url();

        // If already serving a page, reject this request
        if (servingPage) {
            request->send(503, "text/plain", "Server busy - try again");
            return;
        }

        // Request page from Pico
        sendLine("ESP:get " + path);

        // Store request for async response and clear buffer
        currentPageRequest = request;
        servingPage = true;
        pageRequestTime = millis();
        pageContentBuffer = "";

        // Register disconnect handler to clean up if client disconnects
        request->onDisconnect([]() {
            servingPage = false;
            currentPageRequest = nullptr;
            pageContentBuffer = "";
        });

        // Don't send yet! Response will be sent when Pico sends all data
        // Main loop handles timeout checking
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

    if (line == "END") {
        // End of configuration
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

        return;
    }

    // WebSocket telemetry: WS:{json}
    if (line.startsWith("WS:")) {
        String json = line.substring(3);
        wsServer.textAll(json);
        return;
    }

    // File serving: FILE:filename:size
    if (line.startsWith("FILE:")) {
        if (!servingPage) return;

        // Parse FILE:filename:size
        int colon1 = line.indexOf(':', 5);
        if (colon1 < 0) return;

        String filename = line.substring(5, colon1);
        int size = line.substring(colon1 + 1).toInt();

        // Size will be followed by content and END marker
        // We'll accumulate content until we see END
        return;
    }

    // File content or end marker
    if (servingPage) {
        if (line == "END") {
            // Finish serving the page - send buffered content
            if (currentPageRequest) {
                currentPageRequest->send(200, "text/html", pageContentBuffer);
            }
            servingPage = false;
            currentPageRequest = nullptr;
            pageContentBuffer = "";
        } else {
            // Content line - add to buffer
            pageContentBuffer += line;
            pageContentBuffer += "\n";
        }
        return;
    }

    // 404 Not Found
    if (line == "404") {
        if (servingPage && currentPageRequest) {
            currentPageRequest->send(404, "text/plain", "Not Found");
            servingPage = false;
            currentPageRequest = nullptr;
            pageContentBuffer = "";
        }
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
