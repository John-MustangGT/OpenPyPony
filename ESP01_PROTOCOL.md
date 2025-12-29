# ESP-01 Web Server Protocol

This document describes the UART communication protocol between the Raspberry Pi Pico and ESP-01 module for the hybrid web server architecture.

## Hardware Configuration

- **UART0** (Pico → ESP-01): GP0 (TX), GP1 (RX)
- **Baudrate**: 115200
- **Reset Pin**: GP6 (active low)
- **Voltage**: 3.3V (both devices)

## Architecture Overview

The ESP-01 is "dataless" - it only maintains WiFi connections and WebSocket clients. The Pico handles all data, logic, and serves all web content.

**ESP-01 Responsibilities:**
- WiFi AP or STA mode
- HTTP server (pages forwarded to Pico)
- WebSocket server (port 81)
- Broadcast telemetry to all WebSocket clients

**Pico Responsibilities:**
- Serve HTML/JS page content
- Generate telemetry data
- Stream JSON to ESP for WebSocket broadcast
- Handle application logic and data logging

## Boot Sequence

1. **Pico powers on**, initializes UART0 at 115200 baud
2. **Pico pulses GP6 low** (100ms) to reset ESP-01
3. **ESP-01 boots** (~500ms), sends: `ESP:config\n`
4. **Pico sends configuration** (see Config Protocol below)
5. **ESP-01 establishes WiFi**, starts servers, sends: `ESP:serving\n`
6. **System ready** - Pico begins streaming telemetry

## Protocol Messages

All messages are newline-terminated ASCII text.

### ESP-01 → Pico

#### Config Request
```
ESP:config\n
```
Sent on boot or when ESP needs reconfiguration.

#### Serving Confirmation
```
ESP:serving\n
```
ESP is ready, WiFi connected, servers running.

#### Status Update
```
ESP:status clients=2 uptime=3600 rssi=-45\n
```
Sent periodically (~5s). Fields:
- `clients`: Number of WebSocket connections
- `uptime`: Seconds since boot
- `rssi`: WiFi signal strength (optional, STA mode only)

#### Page Request
```
ESP:get /index.html\n
ESP:get /\n
ESP:get /style.css\n
```
Client requested a page. Pico must respond with `FILE:` or `404\n`.

### Pico → ESP-01

#### Configuration
```
CONFIG\n
mode=ap\n
ssid=OpenPonyLogger\n
password=mustanggt\n
address=192.168.4.1\n
netmask=255.255.255.0\n
gateway=192.168.4.1\n
END\n
```

Configuration fields:
- `mode`: `ap` (Access Point) or `sta` (Station/Client)
- `ssid`: Network name (AP mode) or network to join (STA mode)
- `password`: WiFi password (8-63 chars)
- `address`: ESP IP address
- `netmask`: Network mask (typically 255.255.255.0)
- `gateway`: Gateway IP (typically same as address in AP mode)

#### File Response (Known Size)
```
FILE:/index.html:12345\n
<html>...content...</html>
END\n
```

Format: `FILE:<filename>:<size_bytes>\n<content>END\n`
- Size allows ESP to pre-allocate buffer
- Content can be sent in chunks
- `END\n` marks completion

#### File Response (Streaming)
```
FILE:/index.html:0\n
<chunk1>
<chunk2>
...
END\n
```

Format: `FILE:<filename>:0\n<chunks>END\n`
- Size of 0 indicates streaming mode
- ESP reads until `END\n` marker
- Useful for large files (>2KB)

#### 404 Not Found
```
404\n
```
Page not found. ESP returns HTTP 404 to client.

#### WebSocket Telemetry
```
WS:{"lat":42.123456,"lon":-71.123456,"speed":65.5,"gx":0.2,"gy":-0.5,"gz":1.0}\n
```

Format: `WS:<json_object>\n`
- Simple JSON (no nested objects for CircuitPython compatibility)
- ESP broadcasts to ALL connected WebSocket clients
- Sent at 10Hz for smooth real-time updates
- Fields match the web page JavaScript expectations

## Example Session

```
[ESP boots]
ESP → Pico: ESP:config\n

[Pico sends config]
Pico → ESP: CONFIG\n
Pico → ESP: mode=ap\n
Pico → ESP: ssid=OpenPonyLogger\n
Pico → ESP: password=mustanggt\n
Pico → ESP: address=192.168.4.1\n
Pico → ESP: netmask=255.255.255.0\n
Pico → ESP: gateway=192.168.4.1\n
Pico → ESP: END\n

[ESP establishes WiFi and servers]
ESP → Pico: ESP:serving\n

[Client connects via browser]
ESP → Pico: ESP:get /\n

[Pico serves index page]
Pico → ESP: FILE:/index.html:15234\n
Pico → ESP: <!DOCTYPE html><html>...[15234 bytes]...</html>
Pico → ESP: END\n

[Client opens WebSocket, Pico streams data]
Pico → ESP: WS:{"lat":42.333817,"lon":-71.436768,"speed":0.0,"satellites":8,"fix_type":"3D","hdop":1.2,"gx":0.01,"gy":-0.01,"gz":1.05}\n
Pico → ESP: WS:{"lat":42.333817,"lon":-71.436768,"speed":0.0,"satellites":8,"fix_type":"3D","hdop":1.2,"gx":0.01,"gy":-0.01,"gz":1.05}\n
... (every 100ms) ...

[ESP sends status]
ESP → Pico: ESP:status clients=1 uptime=300\n
```

## Configuration in settings.toml

```toml
[webserver]
enabled = true
mode = "ap"                    # "ap" or "sta"
ssid = "OpenPonyLogger"        # AP name or network to join
password = "mustanggt"         # WiFi password (8-63 chars)
address = "192.168.4.1"        # ESP IP address
netmask = "255.255.255.0"      # Network mask
gateway = "192.168.4.1"        # Gateway (usually same as address in AP mode)
```

## ESP-01 Firmware Requirements

Your ESP-01 firmware should implement:

1. **UART Handler**
   - Read lines at 115200 baud
   - Parse commands: CONFIG, WS:, FILE:, 404
   - Send: ESP:config, ESP:serving, ESP:status, ESP:get

2. **WiFi Manager**
   - AP mode: Create access point with configured SSID/password
   - STA mode: Connect to existing WiFi network
   - Handle reconnection on disconnect

3. **HTTP Server** (port 80)
   - Accept HTTP GET requests
   - Forward all requests to Pico via `ESP:get <path>\n`
   - Wait for `FILE:` or `404` response
   - Stream response to client
   - No local file storage needed!

4. **WebSocket Server** (port 81)
   - Accept WebSocket connections
   - Maintain list of connected clients
   - When receiving `WS:<json>\n` from UART, broadcast to all clients
   - Update client count in status messages

5. **Status Reporter**
   - Every 5 seconds send: `ESP:status clients=N uptime=SSSS\n`
   - Helps Pico monitor ESP health

6. **Boot Behavior**
   - On boot: Send `ESP:config\n`
   - Wait for CONFIG sequence
   - Apply configuration
   - Start WiFi, HTTP, and WebSocket servers
   - Send `ESP:serving\n`
   - If WiFi disconnects/fails: restart and re-request config

## Telemetry JSON Format

The Pico sends telemetry with these fields (all optional, but usually present):

```json
{
  "lat": 42.333817,        // GPS latitude (degrees)
  "lon": -71.436768,       // GPS longitude (degrees)
  "alt": 125.5,            // Altitude (meters)
  "speed": 65.5,           // Speed (MPH, already converted)
  "satellites": 8,         // Number of satellites
  "fix_type": "3D",        // "No Fix", "2D", or "3D"
  "hdop": 1.2,             // Horizontal dilution of precision
  "gx": 0.15,              // X G-force (lateral, smoothed)
  "gy": -0.45,             // Y G-force (longitudinal, smoothed)
  "gz": 1.02               // Z G-force (vertical, smoothed)
}
```

JavaScript on the web page parses this and updates the display.

## Error Handling

**ESP-01 Restart:**
- ESP sends `ESP:config\n` again
- Pico re-sends configuration
- Resume operation

**Pico Restart:**
- Pico resets ESP-01 via GP6
- Full init sequence

**WiFi Issues:**
- ESP should retry connection (STA mode)
- If persistent failure, restart and request config

**UART Errors:**
- Both sides should ignore malformed/incomplete lines
- Continue processing next line
- Buffer overflow: discard and start fresh

## Performance Notes

- **Page serving**: <1KB pages send instantly, >10KB may take 1-2 seconds at 115200 baud
- **Telemetry rate**: 10Hz (100ms interval) provides smooth real-time updates
- **WebSocket latency**: <50ms from sensor read to client display
- **Client limit**: ESP-01 can handle 4-5 concurrent WebSocket clients comfortably

## Future Enhancements

Potential protocol additions:
- Binary telemetry mode for higher throughput
- Client-to-Pico commands (start/stop logging, etc.)
- Server-Sent Events (SSE) alternative to WebSocket
- Firmware update over UART from Pico
- Compressed telemetry for lower bandwidth

## Implementation Files

- **Pico Side**:
  - `sensors.py`: ESP01 class (WebServerInterface implementation)
  - `hardware.py`: UART0 and GP6 initialization
  - `code.py`: Request handling and telemetry streaming
  - `webpages.py`: HTML/JS content to serve

- **ESP-01 Side**:
  - Firmware TBD (Arduino/ESP-IDF/MicroPython)
  - Implement protocol as described above
  - Flash to ESP-01 module
