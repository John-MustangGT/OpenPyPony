# ESP-01 Hybrid Server Firmware

This directory contains the ESP-01 firmware for OpenPonyLogger's hybrid web server architecture.

## UART Mode Configuration

The firmware supports two UART modes via `#define DEBUG_MODE` in the sketch:

### Debug Mode (DEBUG_MODE = 1) - **RECOMMENDED FOR TESTING**
- **GPIO Pins**: GPIO2 (TX to Pico) and GPIO0 (RX from Pico)
- **Baud Rate**: 9600
- **Advantage**: Hardware UART (GPIO1/3) remains free for USB serial debugging!
- **Use Case**: Initial testing, protocol debugging, troubleshooting
- **Wiring**:
  - ESP GPIO2 → Pico GP1 (UART0 RX)
  - ESP GPIO0 → Pico GP0 (UART0 TX)
- **Pico Config**: Set `webserver.baudrate = 9600` in `settings.toml`

### Normal Mode (DEBUG_MODE = 0) - Production
- **GPIO Pins**: GPIO1 (TX) and GPIO3 (RX) - Hardware UART
- **Baud Rate**: 115200
- **Advantage**: Faster, more reliable for production use
- **Disadvantage**: No USB serial debugging (same pins used for programming)
- **Wiring**:
  - ESP GPIO1 → Pico GP1 (UART0 RX)
  - ESP GPIO3 → Pico GP0 (UART0 TX)
- **Pico Config**: Set `webserver.baudrate = 115200` in `settings.toml`

**To switch modes**: Edit line 35 in `esp-hybrid-server.ino`:
```cpp
#define DEBUG_MODE 1  // 1 = debug (GPIO2/0 @ 9600), 0 = normal (GPIO1/3 @ 115200)
```

## Firmware Versions

### `esp-hybrid-server.ino` (NEW - Recommended)
Implements the dataless hybrid architecture where:
- ESP-01 only handles WiFi, HTTP, and WebSocket connections
- All HTML/content served by Pico via UART
- Simple text-based protocol (see `../ESP01_PROTOCOL.md`)
- Minimal memory footprint
- Supports AP and STA modes via Pico configuration
- **NEW**: Debug mode with USB serial monitoring!

### `esp-client.ino` (OLD - Legacy)
Original JSON-based client with:
- Full HTML stored in ESP PROGMEM
- JSON protocol for all communication
- Session control features
- File management UI
- Higher memory usage

## Hardware Requirements

- **ESP-01** or **ESP-01S** module (ESP8266)
- **3.3V power supply** (stable, 250mA+ recommended)
- **USB-to-Serial adapter** for programming (3.3V logic levels!)
- **Pull-up/down resistors** for programming mode:
  - CH_PD (EN): 10kΩ pull-up to 3.3V
  - GPIO0: 10kΩ pull-up (hold LOW for programming)
  - GPIO2: 10kΩ pull-up
  - RST: 10kΩ pull-up (optional)

## Software Requirements

### Arduino IDE Setup

1. **Install Arduino IDE** (1.8.19+ or 2.x)
   - Download from: https://www.arduino.cc/en/software

2. **Add ESP8266 Board Support**
   - Open Arduino IDE
   - Go to `File → Preferences`
   - Add to "Additional Board Manager URLs":
     ```
     http://arduino.esp8266.com/stable/package_esp8266com_index.json
     ```
   - Go to `Tools → Board → Boards Manager`
   - Search for "esp8266"
   - Install "ESP8266 by ESP8266 Community" (version 3.0.0+)

3. **Install Required Libraries**
   - Go to `Tools → Manage Libraries`
   - Install the following:
     - **ESPAsyncTCP** by Me-No-Dev
     - **ESPAsyncWebServer** by Me-No-Dev
     - **EspSoftwareSerial** by Dirk Kaar, Peter Lerup (for DEBUG_MODE)

   If not available in Library Manager, install manually:
   ```bash
   cd ~/Arduino/libraries/
   git clone https://github.com/me-no-dev/ESPAsyncTCP.git
   git clone https://github.com/me-no-dev/ESPAsyncWebServer.git
   git clone https://github.com/plerup/espsoftwareserial.git
   ```

   **Note**: SoftwareSerial is only required if using DEBUG_MODE = 1

### Board Configuration

In Arduino IDE, select:
- **Board**: "Generic ESP8266 Module"
- **Flash Size**: "1MB (FS:none OTA:~502KB)"
- **Flash Mode**: "DIO" (or "DOUT" for older modules)
- **Flash Frequency**: "40MHz"
- **CPU Frequency**: "80MHz"
- **Upload Speed**: "115200"
- **Port**: Your USB-to-Serial adapter port

## Compiling the Firmware

### For Hybrid Server (Recommended)

1. Open `esp-hybrid-server.ino` in Arduino IDE
2. Verify/Compile: Click the checkmark button or `Ctrl+R`
3. Check for errors in the console

Expected output:
```
Sketch uses XXXXX bytes (XX%) of program storage space.
Global variables use XXXXX bytes (XX%) of dynamic memory.
```

Should fit comfortably in 1MB ESP-01 with <50% memory usage.

### For Legacy Client

1. Open `esp-client.ino` in Arduino IDE
2. May require more flash space due to stored HTML
3. If you get memory errors, use "1MB (FS:64KB OTA:~470KB)" flash size

## Flashing the ESP-01

### Wiring for Programming

Connect ESP-01 to USB-to-Serial adapter:

```
ESP-01        USB-Serial
------        ----------
VCC    --->   3.3V (NOT 5V!)
GND    --->   GND
TX     --->   RX
RX     --->   TX
CH_PD  --->   3.3V (via 10kΩ)
GPIO0  --->   GND (programming mode)
GPIO2  --->   3.3V (via 10kΩ)
```

### Programming Steps

1. **Enter Programming Mode**:
   - Connect GPIO0 to GND
   - Power cycle the ESP-01 (disconnect/reconnect VCC)
   - ESP will boot in programming mode

2. **Upload Firmware**:
   - Click Upload button in Arduino IDE or `Ctrl+U`
   - Wait for upload to complete (~30 seconds)
   - Look for "Hard resetting via RTS pin..." in console

3. **Exit Programming Mode**:
   - Disconnect GPIO0 from GND
   - Power cycle the ESP-01 again
   - ESP will boot normally with new firmware

### Troubleshooting Upload

**"Failed to connect":**
- Check wiring (TX/RX crossed?)
- Verify 3.3V power (measure with multimeter)
- Try lower upload speed (57600)
- Ensure GPIO0 is LOW during power-on

**"Timed out waiting for packet header":**
- Reset ESP while keeping GPIO0 LOW
- Try different USB-to-Serial adapter
- Check for stable 3.3V power supply

**"Invalid head of packet":**
- Wrong flash mode (try DOUT instead of DIO)
- Bad connection or noisy power
- Try slower upload speed

## Testing the Firmware

### Standalone Test (No Pico)

After flashing `esp-hybrid-server.ino`:

1. Power the ESP-01 normally (GPIO0 floating/pulled high)
2. ESP will boot and request config via UART
3. After 10 second timeout, it will use defaults:
   - Mode: AP
   - SSID: "OpenPonyLogger"
   - Password: "mustanggt"
   - IP: 192.168.4.1

4. Connect to WiFi "OpenPonyLogger" (password: mustanggt)
5. Browse to http://192.168.4.1/
6. Will timeout (no Pico to serve content) but proves WiFi works

### With Pico Integration

1. Connect ESP-01 to Pico:
   ```
   ESP-01        Pico
   ------        ----
   VCC    --->   3.3V (or external 3.3V supply)
   GND    --->   GND
   TX     --->   GP1 (UART0 RX)
   RX     --->   GP0 (UART0 TX)
   ```

2. Enable web server in Pico's `settings.toml`:
   ```toml
   [webserver]
   enabled = true
   mode = "ap"
   ssid = "OpenPonyLogger"
   password = "mustanggt"
   address = "192.168.4.1"
   ```

3. Power on Pico (ESP will be reset via GP6)
4. Watch Pico serial console for:
   ```
   [ESP01] Resetting...
   [ESP01] Waiting for config request...
   [ESP01] Sending config...
   ✓ Web server ready (ESP-01, OpenPonyLogger)
   ```

5. Connect to WiFi and browse to http://192.168.4.1/
6. Should see OpenPonyLogger telemetry dashboard!

## Serial Monitoring

**IMPORTANT**: When using hardware UART on ESP-01 (GPIO1/GPIO3) for Pico communication, you CANNOT use USB Serial for debugging!

To debug, you can:
1. Use `Serial1` on GPIO2 (TX only, 1-wire debug)
2. Add LED blink patterns for status indication
3. Monitor the Pico's serial output (shows ESP messages)

## Power Considerations

ESP-01 can draw up to 250mA during WiFi transmission:
- **Don't power from Pico's 3.3V pin** (Pico can only supply ~300mA total)
- Use dedicated 3.3V regulator (AMS1117-3.3 or similar)
- Add 100µF capacitor near ESP-01 VCC/GND
- Use short, thick power wires

## Default Configuration

If no configuration is received from Pico within 10 seconds, firmware uses:

```cpp
Mode:      AP (Access Point)
SSID:      OpenPonyLogger
Password:  mustanggt
IP:        192.168.4.1
Netmask:   255.255.255.0
Gateway:   192.168.4.1
```

## Firmware Behavior

### Boot Sequence
1. Initialize UART @ 115200 baud
2. Send `ESP:config\n` to Pico
3. Wait up to 10 seconds for configuration
4. Setup WiFi (AP or STA mode)
5. Start HTTP server (port 80)
6. Start WebSocket server (port 81)
7. Send `ESP:serving\n` to Pico

### During Operation
- Forward all HTTP requests to Pico: `ESP:get /path\n`
- Wait for Pico response: `FILE:...` or `404\n`
- Stream received content to HTTP client
- Broadcast WebSocket messages from Pico: `WS:{json}\n`
- Send status every 5 seconds: `ESP:status clients=N uptime=SSS\n`

### Error Handling
- STA mode connection failure → Fall back to AP mode
- Page request timeout (5s) → Return 404
- Config timeout → Use defaults
- WiFi disconnect → Auto-reconnect

## Memory Usage

Typical flash/RAM usage for `esp-hybrid-server.ino`:
- **Flash**: ~280KB / 1MB (28%)
- **RAM**: ~25KB / 80KB (31%)

Plenty of headroom for ESP-01's limited resources!

## Next Steps

1. Flash the firmware
2. Test standalone WiFi connectivity
3. Connect to Pico and test full integration
4. Customize configuration in `settings.toml`
5. Access telemetry at http://192.168.4.1/

## References

- Protocol Specification: `../ESP01_PROTOCOL.md`
- ESP8266 Arduino Core: https://arduino-esp8266.readthedocs.io/
- ESPAsyncWebServer: https://github.com/me-no-dev/ESPAsyncWebServer
