"""
wifi_server.py - WiFi server with real-time telemetry API for OpenPonyLogger

Provides HTTP endpoints that serve actual sensor data to the web interface.
Implements GPS time synchronization and binary logging support.
"""

import time
import json
import wifi
import socketpool
import rtc
import struct
import os
from scheduler import Task

# Import version info if available
try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

# GPS time sync state
gps_time_synced = False
last_gps_sync = 0

# Binary log state
binary_logging_enabled = False
binary_log_file = None
log_start_time = 0
LOG_ROTATION_INTERVAL = 900  # 15 minutes in seconds

# Time source constants
TIME_SOURCE_NONE = 0
TIME_SOURCE_RTC = 1
TIME_SOURCE_GPS = 2

# Sensor identifiers
SENSOR_ACCELEROMETER = 1
SENSOR_GPS = 2
SENSOR_OBD2 = 3

# Data type identifiers
DATA_ACCEL_XYZ = 1
DATA_GPS_FIX = 2
DATA_GPS_SATS = 3
DATA_OBD_PID = 4


class WiFiAPTask(Task):
    """WiFi Access Point management task"""
    
    def __init__(self, ssid="OpenPonyLogger", password="mustanggt", no_default_route=True):
        super().__init__("WiFi AP", 5000)  # Check every 5 seconds
        self.ssid = ssid
        self.password = password
        self.no_default_route = no_default_route
        self.ap_active = False
        self.ip_address = None
        
    def start(self):
        """Start the WiFi Access Point"""
        try:
            print("\n[WiFi] Starting Access Point...")
            print(f"  SSID: {self.ssid}")
            print(f"  No Default Route: {self.no_default_route}")
            
            # Note: CircuitPython doesn't support custom gateway configuration
            # for AP mode, so "no default route" mode is not fully implemented.
            # Setting AP_NO_DEFAULT_ROUTE to true will just add a warning message.
            # Clients will still get the AP as their default gateway.
            
            if self.no_default_route:
                print(f"  ⚠ No Default Route requested but not supported in CircuitPython")
                print(f"  ⚠ Clients will route through AP (may show 'No Internet')")
            
            # Start AP mode (only ssid and password are supported)
            wifi.radio.start_ap(self.ssid, self.password)
            
            self.ap_active = True
            self.ip_address = str(wifi.radio.ipv4_address_ap)
            
            print(f"  IP Address: {self.ip_address}")
            print(f"  ✓ Access Point started")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to start AP: {e}")
            self.ap_active = False
            return False
    
    def run(self):
        """Monitor WiFi AP status"""
        if not self.ap_active:
            print("[WiFi] AP inactive, attempting restart...")
            self.start()
    
    def stop(self):
        """Stop the WiFi Access Point"""
        if self.ap_active:
            wifi.radio.stop_ap()
            self.ap_active = False
            print("[WiFi] Access Point stopped")


class WebServerTask(Task):
    """Web server task that serves real-time telemetry data"""
    
    def __init__(self, data_buffer, wifi_ap):
        super().__init__("WebServer", 10)  # Poll every 10ms
        self.data_buffer = data_buffer
        self.wifi_ap = wifi_ap
        self.pool = None
        self.server_socket = None
        self.request_count = 0
        
    def start(self):
        """Start the web server"""
        if not self.wifi_ap.ap_active:
            print("[Web] Cannot start - WiFi AP not active")
            return False
        
        try:
            print("\n[Web] Starting web server...")
            self.pool = socketpool.SocketPool(wifi.radio)
            
            self.server_socket = self.pool.socket(
                self.pool.AF_INET,
                self.pool.SOCK_STREAM
            )
            self.server_socket.setsockopt(
                self.pool.SOL_SOCKET,
                self.pool.SO_REUSEADDR,
                1
            )
            self.server_socket.bind(('0.0.0.0', 80))
            self.server_socket.listen(1)
            self.server_socket.setblocking(False)
            
            print(f"  ✓ Server listening on http://{self.wifi_ap.ip_address}")
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to start server: {e}")
            return False
    
    def run(self):
        """Poll for incoming HTTP requests"""
        self.poll()
    
    def poll(self):
        """Non-blocking poll for connections"""
        try:
            client, addr = self.server_socket.accept()
            self.request_count += 1
            self._handle_request(client, addr)
        except OSError:
            # No connection available
            pass
        except Exception as e:
            print(f"[Web] Error: {e}")
    
    def _handle_request(self, client, addr):
        """Handle an HTTP request"""
        try:
            client.settimeout(2.0)
            
            # Read request using recv_into (CircuitPython compatible)
            request = bytearray()
            buffer = bytearray(1024)
            
            while True:
                try:
                    nbytes = client.recv_into(buffer)
                    if nbytes == 0:
                        break
                    request.extend(buffer[:nbytes])
                    if b"\r\n\r\n" in request:
                        break
                except OSError:
                    break
            
            if not request:
                return
            
            # Parse request line
            try:
                request_str = bytes(request).decode('utf-8')
            except:
                # If decode fails, try latin-1 which accepts all byte values
                request_str = bytes(request).decode('latin-1')
            lines = request_str.split('\r\n')
            
            if not lines[0].startswith('GET '):
                self._send_error(client, 400, "Bad Request")
                return
            
            path = lines[0].split(' ')[1]
            
            # Remove query string
            if '?' in path:
                path = path[:path.index('?')]
            
            # Route the request
            if path.startswith('/api/'):
                self._handle_api(client, path)
            else:
                self._handle_static(client, path)
                
        except Exception as e:
            import sys
            import io
            buf = io.StringIO()
            sys.print_exception(e, buf)
            print(f"[Web] Request error: {e}")
            print(buf.getvalue())
            try:
                self._send_error(client, 500, "Internal Server Error")
            except:
                pass
        finally:
            try:
                client.close()
            except:
                pass
    
    def _handle_api(self, client, path):
        """Handle API endpoints"""
        if path == '/api/status':
            self._api_status(client)
        elif path == '/api/live':
            self._api_live(client)
        elif path == '/api/gps':
            self._api_gps(client)
        elif path == '/api/recording':
            self._api_recording(client)
        else:
            self._send_error(client, 404, "Not Found")
    
    def _api_status(self, client):
        """Return system status"""
        data = {
            'version': VERSION,
            'git_hash': GIT_HASH,
            'build_date': BUILD_DATE,
            'uptime': int(time.monotonic()),
            'gps_time_synced': gps_time_synced,
            'binary_logging': binary_logging_enabled,
            'requests': self.request_count
        }
        self._send_json(client, data)
    
    def _api_live(self, client):
        """Return live telemetry data"""
        accel = self.data_buffer.get('accel') or {}
        gps = self.data_buffer.get('gps') or {}
        
        data = {
            'accel': {
                'gx': accel.get('gx') or 0,
                'gy': accel.get('gy') or 0,
                'gz': accel.get('gz') or 0,
                'g_total': accel.get('g_total') or 1.0,
                'timestamp': accel.get('timestamp') or 0
            },
            'gps': {
                'lat': gps.get('lat') or 0,
                'lon': gps.get('lon') or 0,
                'alt': gps.get('alt') or 0,
                'speed': gps.get('speed') or 0,
                'heading': gps.get('heading') or 0,
                'satellites': gps.get('satellites') or 0,
                'fix_quality': gps.get('fix_quality') or 0,
                'hdop': gps.get('hdop') or 99.9
            },
            'system': {
                'uptime': int(time.monotonic()),
                'time_source': 'GPS' if gps_time_synced else 'RTC'
            }
        }
        self._send_json(client, data)
    
    def _api_gps(self, client):
        """Return GPS-specific data"""
        gps = self.data_buffer.get('gps') or {}
        satellites = self.data_buffer.get('gps_satellites') or []
        
        data = {
            'position': {
                'lat': gps.get('lat') or 0,
                'lon': gps.get('lon') or 0,
                'alt': gps.get('alt') or 0
            },
            'velocity': {
                'speed': gps.get('speed') or 0,
                'heading': gps.get('heading') or 0
            },
            'quality': {
                'fix': gps.get('fix_quality') or 0,
                'satellites': gps.get('satellites') or 0,
                'hdop': gps.get('hdop') or 99.9,
                'pdop': gps.get('pdop') or 99.9
            },
            'satellites': satellites,
            'time_synced': gps_time_synced,
            'last_update': gps.get('timestamp') or 0
        }
        self._send_json(client, data)
    
    def _api_recording(self, client):
        """Return recording status"""
        data = {
            'active': binary_logging_enabled,
            'format': 'binary' if binary_logging_enabled else 'none',
            'file': binary_log_file.name if binary_log_file else None,
            'duration': int(time.monotonic() - log_start_time) if binary_logging_enabled else 0
        }
        self._send_json(client, data)
    
    def _handle_static(self, client, path):
        """Serve static files"""
        if path == '/':
            path = '/index.html'
        
        # Try compressed version first
        file_path = '/web' + path
        gzip_path = file_path + '.gz'
        
        # Check if compressed version exists
        try:
            os.stat(gzip_path)
            self._send_file(client, gzip_path, compressed=True)
            return
        except OSError:
            pass
        
        # Try uncompressed
        try:
            os.stat(file_path)
            self._send_file(client, file_path, compressed=False)
        except OSError:
            self._send_error(client, 404, "Not Found")
    
    def _send_json(self, client, data):
        """Send JSON response"""
        json_str = json.dumps(data)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(json_str)}\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{json_str}"
        )
        client.send(response.encode('utf-8'))
    
    def _send_file(self, client, path, compressed=False):
        """Send file response"""
        try:
            file_size = os.stat(path)[6]
            
            # Determine MIME type
            if path.endswith('.html') or path.endswith('.html.gz'):
                mime_type = 'text/html'
            elif path.endswith('.css') or path.endswith('.css.gz'):
                mime_type = 'text/css'
            elif path.endswith('.js') or path.endswith('.js.gz'):
                mime_type = 'application/javascript'
            else:
                mime_type = 'application/octet-stream'
            
            # Send headers
            headers = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Type: {mime_type}\r\n"
                f"Content-Length: {file_size}\r\n"
            )
            
            if compressed:
                headers += "Content-Encoding: gzip\r\n"
            
            headers += (
                "Cache-Control: max-age=3600\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            
            client.send(headers.encode('utf-8'))
            
            # Send file in chunks
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    client.send(chunk)
                    
        except Exception as e:
            print(f"[Web] Error sending file {path}: {e}")
            self._send_error(client, 500, "Internal Server Error")
    
    def _send_error(self, client, code, message):
        """Send error response"""
        response = (
            f"HTTP/1.1 {code} {message}\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{message}"
        )
        try:
            client.send(response.encode('utf-8'))
        except:
            pass


def sync_gps_time(gps_data, timezone_offset=0, dst_enabled=False):
    """
    Synchronize RTC with GPS time
    
    Args:
        gps_data: Dict with GPS time data (year, month, day, hour, minute, second)
        timezone_offset: Hours offset from UTC (e.g., -5 for EST, -4 for EDT)
        dst_enabled: Whether DST is currently active
    
    Returns:
        True if sync successful
    """
    global gps_time_synced, last_gps_sync
    
    try:
        # GPS provides UTC time
        year = gps_data.get('year') or 2025
        month = gps_data.get('month') or 1
        day = gps_data.get('day') or 1
        hour = gps_data.get('hour') or 0
        minute = gps_data.get('minute') or 0
        second = gps_data.get('second') or 0
        
        # Apply timezone offset
        hour += timezone_offset
        if dst_enabled:
            hour += 1
        
        # Handle hour overflow/underflow
        if hour >= 24:
            hour -= 24
            day += 1  # Simplified - doesn't handle month/year rollover
        elif hour < 0:
            hour += 24
            day -= 1  # Simplified - doesn't handle month/year rollunder
        
        # Set RTC
        r = rtc.RTC()
        r.datetime = time.struct_time((
            year, month, day,
            hour, minute, second,
            0, -1, -1  # weekday, yearday, isdst
        ))
        
        gps_time_synced = True
        last_gps_sync = time.monotonic()
        
        print(f"[GPS] Time synced: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
        return True
        
    except Exception as e:
        print(f"[GPS] Time sync failed: {e}")
        return False


def start_binary_log(session_id=None):
    """
    Start binary logging to SD card
    
    Args:
        session_id: Optional session identifier (default: timestamp)
    
    Returns:
        File handle or None on error
    """
    global binary_logging_enabled, binary_log_file, log_start_time
    
    try:
        if session_id is None:
            session_id = f"{int(time.monotonic())}"
        
        filename = f"/sd/session_{session_id}.bin"
        binary_log_file = open(filename, 'wb')
        
        # Write file header
        header = struct.pack(
            '<4sHHI',
            b'OPLO',  # Magic number "OpenPonyLogger"
            1,         # Format version
            0,         # Flags (reserved)
            int(time.monotonic())  # Start timestamp
        )
        binary_log_file.write(header)
        
        binary_logging_enabled = True
        log_start_time = time.monotonic()
        
        print(f"[Log] Binary logging started: {filename}")
        return binary_log_file
        
    except Exception as e:
        print(f"[Log] Failed to start binary logging: {e}")
        binary_logging_enabled = False
        return None


def write_binary_message(sensor, data_type, payload):
    """
    Write a binary message to the log file
    
    Args:
        sensor: Sensor identifier (SENSOR_*)
        data_type: Data type identifier (DATA_*)
        payload: bytes object containing the payload
    
    Returns:
        True if written successfully
    """
    global binary_log_file
    
    if not binary_logging_enabled or binary_log_file is None:
        return False
    
    try:
        # Determine time source
        time_source = TIME_SOURCE_GPS if gps_time_synced else TIME_SOURCE_RTC
        
        # Get timestamp in microseconds
        timestamp_us = int(time.monotonic() * 1_000_000)
        
        # Pack message header (14 bytes total)
        # Q = 8 bytes (timestamp)
        # B = 1 byte (time_source)
        # B = 1 byte (sensor)
        # B = 1 byte (data_type)
        # x = 1 byte (padding for alignment)
        # H = 2 bytes (length)
        header = struct.pack(
            '<QBBBxH',
            timestamp_us,  # 8 bytes
            time_source,   # 1 byte
            sensor,        # 1 byte
            data_type,     # 1 byte
            # x = padding (1 byte automatic)
            len(payload)   # 2 bytes
        )
        
        # Write header + payload
        binary_log_file.write(header)
        binary_log_file.write(payload)
        
        # Check if we should rotate the log file
        if time.monotonic() - log_start_time > LOG_ROTATION_INTERVAL:
            rotate_binary_log()
        
        return True
        
    except Exception as e:
        print(f"[Log] Failed to write message: {e}")
        return False


def rotate_binary_log():
    """Rotate to a new log file"""
    global binary_log_file, log_start_time
    
    try:
        if binary_log_file:
            binary_log_file.flush()
            binary_log_file.close()
        
        start_binary_log()
        
    except Exception as e:
        print(f"[Log] Log rotation failed: {e}")


def stop_binary_log():
    """Stop binary logging and close file"""
    global binary_logging_enabled, binary_log_file
    
    if binary_log_file:
        try:
            binary_log_file.flush()
            binary_log_file.close()
            print("[Log] Binary logging stopped")
        except Exception as e:
            print(f"[Log] Error closing log: {e}")
        finally:
            binary_log_file = None
            binary_logging_enabled = False
