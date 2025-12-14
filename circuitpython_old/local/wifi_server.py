"""
wifi_server.py - WiFi Access Point and Web Server for OpenPonyLogger

This module provides:
- WiFi Access Point setup
- HTTP web server with API endpoints for live data
- Integration with binary logging v2 format
- GPS time synchronization

API Endpoints:
    GET  /              - Serve index.html
    GET  /api/live      - Live sensor data (accel, GPS)
    GET  /api/status    - System status and version
    GET  /api/gps       - Detailed GPS info with satellites
    GET  /api/sessions  - List recorded sessions
    POST /api/session/restart - Restart logging session
    POST /api/session/start   - Start new session with metadata
    POST /api/session/stop    - Stop current session
    GET  /api/log/stats - Binary logging statistics
"""

import wifi
import socketpool
import time
import os
import json

try:
    import rtc
    HAS_RTC = True
except ImportError:
    HAS_RTC = False

try:
    from binary_format import (
        BinaryLogger, 
        SAMPLE_TYPE_ACCELEROMETER, 
        SAMPLE_TYPE_GPS_FIX,
        SAMPLE_TYPE_GPS_SATELLITES,
        SAMPLE_TYPE_OBD_PID,
        SAMPLE_TYPE_EVENT_MARKER,
        WEATHER_UNKNOWN, WEATHER_CLEAR, WEATHER_CLOUDY, WEATHER_RAIN
    )
    HAS_BINARY_FORMAT = True
except ImportError:
    HAS_BINARY_FORMAT = False
    print("[WiFi] Warning: binary_format module not found")

try:
    from version import VERSION, GIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    GIT_HASH = "dev"
    BUILD_DATE = "unknown"

# Re-export constants for backward compatibility
SENSOR_ACCELEROMETER = 0x01
SENSOR_GPS = 0x02
DATA_ACCEL_XYZ = 0x01
DATA_GPS_FIX = 0x01

# Global binary logger instance
_binary_logger = None
_gps_time_synced = False


# =============================================================================
# GPS Time Synchronization
# =============================================================================

def sync_gps_time(gps_time, timezone_offset=0, dst_enabled=False):
    """
    Sync RTC to GPS time with timezone adjustment
    
    Args:
        gps_time: dict with year, month, day, hour, minute, second
        timezone_offset: hours offset from UTC (e.g., -5 for EST)
        dst_enabled: True if daylight saving time is active
    
    Returns:
        True if sync successful
    """
    global _gps_time_synced
    
    if not HAS_RTC:
        return False
    
    try:
        # Validate GPS time - must have valid year (2020+)
        year = gps_time.get('year', 0)
        if year < 2020:
            # GPS doesn't have valid time yet
            print(f"[GPS] Invalid year {year}, skipping time sync")
            return False
        
        month = gps_time.get('month', 1)
        day = gps_time.get('day', 1)
        hour = gps_time.get('hour', 0)
        minute = gps_time.get('minute', 0)
        second = gps_time.get('second', 0)
        
        # Validate ranges
        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23):
            print(f"[GPS] Invalid date/time: {year}-{month}-{day} {hour}:{minute}:{second}")
            return False
        
        # Calculate total offset
        total_offset = timezone_offset
        if dst_enabled:
            total_offset += 1
        
        # Adjust hour for timezone
        hour = hour + total_offset
        
        # Handle hour overflow/underflow (changes day)
        if hour >= 24:
            hour -= 24
            day += 1
            # Simple month overflow handling
            days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            # Leap year check
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                days_in_month[1] = 29
            if day > days_in_month[month - 1]:
                day = 1
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        elif hour < 0:
            hour += 24
            day -= 1
            if day < 1:
                month -= 1
                if month < 1:
                    month = 12
                    year -= 1
                days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    days_in_month[1] = 29
                day = days_in_month[month - 1]
        
        # Set RTC
        import time
        r = rtc.RTC()
        r.datetime = time.struct_time((
            year,
            month,
            day,
            hour,
            minute,
            second,
            0, 0, -1
        ))
        
        _gps_time_synced = True
        print(f"[GPS] RTC synced to {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
        return True
        
    except Exception as e:
        print(f"[GPS] Time sync failed: {e}")
        return False


def is_gps_time_synced():
    """Check if GPS time has been synced"""
    return _gps_time_synced


# =============================================================================
# Binary Logging Interface
# =============================================================================

def start_binary_log(session_name="", driver_name="", vehicle_id="", 
                     weather=0, ambient_temp_c=None):
    """
    Start a new binary logging session
    
    Args:
        session_name: Name for this session (e.g., "Track Day Session 1")
        driver_name: Driver's name
        vehicle_id: VIN or vehicle identifier
        weather: Weather condition enum
        ambient_temp_c: Ambient temperature in Celsius
    
    Returns:
        Session ID (hex string) or None on failure
    """
    global _binary_logger
    
    if not HAS_BINARY_FORMAT:
        print("[BinaryLog] Binary format module not available")
        return None
    
    try:
        if _binary_logger is None:
            _binary_logger = BinaryLogger()
        
        session_id = _binary_logger.start_session(
            session_name=session_name,
            driver_name=driver_name,
            vehicle_id=vehicle_id,
            weather=weather,
            ambient_temp_c=ambient_temp_c
        )
        
        return session_id.hex() if session_id else None
        
    except Exception as e:
        print(f"[BinaryLog] Failed to start session: {e}")
        return None


def restart_binary_log(**kwargs):
    """
    Restart binary logging session (preserves metadata if not provided)
    
    Called when:
    - Settings are changed
    - "Restart Session" pressed in WebUI
    - System detects configuration change
    
    Returns:
        New session ID (hex string) or None on failure
    """
    global _binary_logger
    
    if not HAS_BINARY_FORMAT or _binary_logger is None:
        return start_binary_log(**kwargs)
    
    try:
        session_id = _binary_logger.restart_session(**kwargs)
        return session_id.hex() if session_id else None
        
    except Exception as e:
        print(f"[BinaryLog] Failed to restart session: {e}")
        return None


def stop_binary_log():
    """Stop current binary logging session"""
    global _binary_logger
    
    if _binary_logger is not None:
        try:
            _binary_logger.stop_session()
        except Exception as e:
            print(f"[BinaryLog] Error stopping session: {e}")


def write_binary_message(sensor_type, data_type, payload):
    """
    Write a message to binary log (backward compatibility wrapper)
    
    Args:
        sensor_type: SENSOR_* constant
        data_type: DATA_* constant  
        payload: bytes of data
    """
    global _binary_logger
    
    if _binary_logger is None:
        return
    
    try:
        # Map old format to new format
        if sensor_type == SENSOR_ACCELEROMETER:
            # Payload is struct '<fff' for gx, gy, gz
            import struct
            gx, gy, gz = struct.unpack('<fff', payload)
            _binary_logger.write_accelerometer(gx, gy, gz)
            
        elif sensor_type == SENSOR_GPS:
            # Payload is struct '<iiifff' for lat, lon, alt, speed, heading, hdop
            import struct
            lat, lon, alt, speed, heading, hdop = struct.unpack('<iiifff', payload)
            _binary_logger.write_gps(lat / 1e7, lon / 1e7, alt, speed, heading, hdop)
            
    except Exception as e:
        print(f"[BinaryLog] Write error: {e}")


def get_binary_log_stats():
    """Get binary logging statistics"""
    global _binary_logger
    
    if _binary_logger is None:
        return None
    
    return _binary_logger.get_stats()


# =============================================================================
# WiFi Access Point
# =============================================================================

class WiFiAPTask:
    """Manages WiFi Access Point"""
    
    def __init__(self, ssid="OpenPonyLogger", password="mustanggt", 
                 channel=6, no_default_route=True):
        self.ssid = ssid
        self.password = password
        self.channel = channel
        self.no_default_route = no_default_route
        self.ap_active = False
        self.ip_address = None
    
    def start(self):
        """Start WiFi Access Point with DHCP server"""
        try:
            import time
            
            # IMPORTANT: On Pico W, AP can only be started once per reboot!
            try:
                wifi.radio.stop_station()
            except:
                pass
            
            time.sleep(0.2)
            
            print(f"[WiFi] Starting AP: {self.ssid} (channel {self.channel})")
            
            # Start access point - keep it simple!
            wifi.radio.start_ap(
                ssid=self.ssid,
                password=self.password,
                channel=self.channel
            )
            
            # Wait for AP to initialize
            time.sleep(1.0)
            
            # Check if AP is active
            if not wifi.radio.ap_active:
                print("[WiFi] ✗ AP failed to start")
                return False
            
            # Get IP address
            self.ip_address = str(wifi.radio.ipv4_address_ap)
            self.ap_active = True
            
            print(f"[WiFi] ✓ AP active: {self.ssid}")
            print(f"[WiFi] ✓ AP IP: {self.ip_address}")
            print(f"[WiFi] Connect to WiFi '{self.ssid}' password '{self.password}'")
            print(f"[WiFi] Then browse to: http://{self.ip_address}")
            
            return True
            
        except Exception as e:
            print(f"[WiFi] ✗ AP start failed: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            return False
    
    def stop(self):
        """Stop WiFi Access Point
        
        WARNING: On Pico W, the AP can only be started ONCE per reboot!
        After calling stop(), you cannot start the AP again without resetting.
        """
        try:
            wifi.radio.stop_ap()
            self.ap_active = False
            print("[WiFi] AP stopped (restart requires reboot)")
        except Exception as e:
            print(f"[WiFi] AP stop failed: {e}")


# =============================================================================
# Web Server
# =============================================================================

class WebServerTask:
    """HTTP Web Server for OpenPonyLogger"""
    
    def __init__(self, data_buffer, wifi_ap, web_root="/web", debug=False):
        """
        Initialize web server
        
        Args:
            data_buffer: Shared dict for sensor data
            wifi_ap: WiFiAPTask instance
            web_root: Directory for web files
            debug: Enable debug logging
        """
        self.data_buffer = data_buffer
        self.wifi_ap = wifi_ap
        self.web_root = web_root
        self.debug = debug
        self.pool = None
        self.server_socket = None
        self.request_count = 0
        
        # Asset map for gzip support
        try:
            import sys
            if web_root not in sys.path:
                sys.path.append(web_root)
            from asset_map import ASSETS
            self.assets = ASSETS
        except ImportError:
            self.assets = None
    
    def start(self, port=80):
        """Start the web server"""
        try:
            print(f"[Web] Creating socket pool...")
            self.pool = socketpool.SocketPool(wifi.radio)
            
            print(f"[Web] Creating server socket...")
            self.server_socket = self.pool.socket(
                self.pool.AF_INET,
                self.pool.SOCK_STREAM
            )
            
            print(f"[Web] Setting SO_REUSEADDR...")
            self.server_socket.setsockopt(
                self.pool.SOL_SOCKET,
                self.pool.SO_REUSEADDR,
                1
            )
            
            print(f"[Web] Binding to 0.0.0.0:{port}...")
            self.server_socket.bind(('0.0.0.0', port))
            
            print(f"[Web] Starting listen(2)...")
            self.server_socket.listen(2)
            
            print(f"[Web] Setting non-blocking...")
            self.server_socket.setblocking(False)
            
            print(f"[Web] ✓ Server READY on port {port}")
            return True
            
        except Exception as e:
            print(f"[Web] Server start failed: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            return False
    
    def poll(self):
        """Poll for incoming connections (non-blocking)"""
        try:
            client, addr = self.server_socket.accept()
            self.request_count += 1
            if self.debug:
                print(f"[Web] Request #{self.request_count} from {addr}")
            self._handle_request(client)
        except OSError:
            pass  # No connection waiting
    
    def _handle_request(self, client):
        """Handle HTTP request"""
        try:
            client.settimeout(2.0)
            
            # Read request using recv_into (CircuitPython compatible)
            request = b""
            buffer = bytearray(1024)
            while True:
                try:
                    bytes_read = client.recv_into(buffer)
                    if bytes_read == 0:
                        break
                    request += bytes(buffer[:bytes_read])
                    if b"\r\n\r\n" in request:
                        break
                except OSError:
                    break
            
            if not request:
                client.close()
                return
            
            # Parse request - CircuitPython decode() doesn't take keyword args
            try:
                request_str = request.decode('utf-8')
            except UnicodeError:
                # Fallback: decode as latin-1 which accepts any byte
                request_str = request.decode('latin-1')
            method, path, accepts_gzip = self._parse_request(request_str)
            
            if self.debug:
                print(f"[Web] {method} {path}")
            
            # Route request
            if method == "GET":
                if path == "/api/live":
                    self._send_api_live(client)
                elif path == "/api/status":
                    self._send_api_status(client)
                elif path == "/api/gps":
                    self._send_api_gps(client)
                elif path == "/api/sessions":
                    self._send_api_sessions(client)
                elif path == "/api/log/stats":
                    self._send_api_log_stats(client)
                else:
                    self._serve_file(client, path, accepts_gzip)
                    
            elif method == "POST":
                # Parse POST body
                body = self._get_post_body(request_str)
                
                if path == "/api/session/restart":
                    self._handle_session_restart(client, body)
                elif path == "/api/session/start":
                    self._handle_session_start(client, body)
                elif path == "/api/session/stop":
                    self._handle_session_stop(client)
                else:
                    self._send_404(client)
            else:
                self._send_405(client)
                
        except Exception as e:
            # Always print errors for debugging
            print(f"[Web] Request error: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            self._send_500(client)
        finally:
            try:
                client.close()
            except:
                pass
    
    def _parse_request(self, request):
        """Parse HTTP request, returns (method, path, accepts_gzip)"""
        lines = request.split('\r\n')
        method = "GET"
        path = "/"
        accepts_gzip = False
        
        if lines:
            parts = lines[0].split(' ')
            if len(parts) >= 2:
                method = parts[0]
                path = parts[1]
                if '?' in path:
                    path = path[:path.index('?')]
        
        for line in lines[1:]:
            if line.lower().startswith('accept-encoding:'):
                accepts_gzip = 'gzip' in line.lower()
                break
        
        return method, path, accepts_gzip
    
    def _get_post_body(self, request):
        """Extract POST body from request"""
        if '\r\n\r\n' in request:
            return request.split('\r\n\r\n', 1)[1]
        return ""
    
    # =========================================================================
    # API Endpoints
    # =========================================================================
    
    def _send_api_live(self, client):
        """Send live sensor data"""
        accel = self.data_buffer.get('accel', {})
        gps = self.data_buffer.get('gps', {})
        
        response = {
            'accel': {
                'gx': accel.get('gx', 0),
                'gy': accel.get('gy', 0),
                'gz': accel.get('gz', 0),
                'g_total': accel.get('g_total', 1.0)
            },
            'gps': {
                'lat': gps.get('lat', 0),
                'lon': gps.get('lon', 0),
                'alt': gps.get('alt', 0),
                'speed': gps.get('speed', 0),
                'heading': gps.get('heading', 0),
                'satellites': gps.get('satellites', 0),
                'fix_quality': gps.get('fix_quality', 0),
                'hdop': gps.get('hdop', 99.9)
            },
            'system': {
                'uptime': int(time.monotonic()),
                'time_source': 'GPS' if _gps_time_synced else 'RTC'
            }
        }
        
        self._send_json(client, response)
    
    def _send_api_status(self, client):
        """Send system status"""
        # Get memory info if available
        try:
            import gc
            gc.collect()
            free_mem = gc.mem_free()
            total_mem = gc.mem_alloc() + free_mem
            mem_percent = (gc.mem_alloc() / total_mem) * 100
        except:
            mem_percent = 0
        
        response = {
            'version': VERSION,
            'git_hash': GIT_HASH,
            'build_date': BUILD_DATE,
            'uptime': int(time.monotonic()),
            'memory_percent': mem_percent,
            'gps_time_synced': _gps_time_synced,
            'binary_logging': _binary_logger is not None
        }
        
        self._send_json(client, response)
    
    def _send_api_gps(self, client):
        """Send detailed GPS info"""
        gps = self.data_buffer.get('gps', {})
        satellites = self.data_buffer.get('gps_satellites', [])
        
        response = {
            'lat': gps.get('lat', 0),
            'lon': gps.get('lon', 0),
            'alt': gps.get('alt', 0),
            'speed': gps.get('speed', 0),
            'heading': gps.get('heading', 0),
            'satellites': gps.get('satellites', 0),
            'fix_quality': gps.get('fix_quality', 0),
            'hdop': gps.get('hdop', 99.9),
            'satellite_list': satellites
        }
        
        self._send_json(client, response)
    
    def _send_api_sessions(self, client):
        """Send list of recorded sessions"""
        sessions = []
        
        try:
            log_dir = "/sd/logs"
            for filename in os.listdir(log_dir):
                if filename.endswith('.opl'):
                    filepath = f"{log_dir}/{filename}"
                    stat = os.stat(filepath)
                    sessions.append({
                        'filename': filename,
                        'size': stat[6],
                        'modified': stat[8]
                    })
        except:
            pass
        
        self._send_json(client, {'sessions': sessions})
    
    def _send_api_log_stats(self, client):
        """Send binary logging statistics"""
        stats = get_binary_log_stats()
        
        if stats:
            self._send_json(client, stats)
        else:
            self._send_json(client, {'error': 'No active logging session'})
    
    def _handle_session_restart(self, client, body):
        """Handle session restart request"""
        # Parse JSON body if present
        kwargs = {}
        if body:
            try:
                data = json.loads(body)
                kwargs = {
                    'session_name': data.get('session_name'),
                    'driver_name': data.get('driver_name'),
                    'vehicle_id': data.get('vehicle_id'),
                    'weather': data.get('weather', 0),
                    'ambient_temp_c': data.get('ambient_temp_c')
                }
                # Remove None values
                kwargs = {k: v for k, v in kwargs.items() if v is not None}
            except:
                pass
        
        session_id = restart_binary_log(**kwargs)
        
        if session_id:
            self._send_json(client, {
                'status': 'ok',
                'session_id': session_id,
                'message': 'Session restarted'
            })
        else:
            self._send_json(client, {
                'status': 'error',
                'message': 'Failed to restart session'
            }, status=500)
    
    def _handle_session_start(self, client, body):
        """Handle session start request"""
        kwargs = {}
        if body:
            try:
                data = json.loads(body)
                kwargs = {
                    'session_name': data.get('session_name', ''),
                    'driver_name': data.get('driver_name', ''),
                    'vehicle_id': data.get('vehicle_id', ''),
                    'weather': data.get('weather', 0),
                    'ambient_temp_c': data.get('ambient_temp_c')
                }
            except:
                pass
        
        session_id = start_binary_log(**kwargs)
        
        if session_id:
            self._send_json(client, {
                'status': 'ok',
                'session_id': session_id,
                'message': 'Session started'
            })
        else:
            self._send_json(client, {
                'status': 'error',
                'message': 'Failed to start session'
            }, status=500)
    
    def _handle_session_stop(self, client):
        """Handle session stop request"""
        stop_binary_log()
        self._send_json(client, {
            'status': 'ok',
            'message': 'Session stopped'
        })
    
    # =========================================================================
    # HTTP Response Helpers
    # =========================================================================
    
    def _send_json(self, client, data, status=200):
        """Send JSON response"""
        body = json.dumps(data)
        
        status_text = "OK" if status == 200 else "Error"
        response = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        
        client.send(response.encode('utf-8'))
        client.send(body.encode('utf-8'))
    
    def _serve_file(self, client, path, accepts_gzip):
        """Serve static file"""
        # Determine file path
        if path == "/":
            path = "/index.html"
        
        print(f"[Web] Serving: {path} (gzip={accepts_gzip})")
        
        # Check asset map first
        if self.assets and path in self.assets:
            asset = self.assets[path]
            filepath = f"{self.web_root}/{asset['file']}"
            gzip_path = f"{self.web_root}/{asset['gzip']}"
            mime_type = asset['mime']
            print(f"[Web] Asset map: {filepath}")
        else:
            filepath = f"{self.web_root}{path}"
            gzip_path = f"{filepath}.gz"
            mime_type = self._get_mime_type(path)
            print(f"[Web] Direct path: {filepath}")
        
        # Try gzip version first
        if accepts_gzip and self._file_exists(gzip_path):
            print(f"[Web] Sending gzip: {gzip_path}")
            self._send_file(client, gzip_path, mime_type, compressed=True)
        elif self._file_exists(filepath):
            print(f"[Web] Sending plain: {filepath}")
            self._send_file(client, filepath, mime_type, compressed=False)
        else:
            print(f"[Web] File not found: {filepath} or {gzip_path}")
            self._send_404(client)
    
    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _send_file(self, client, filepath, mime_type, compressed=False):
        """Send file response"""
        try:
            file_size = os.stat(filepath)[6]
            
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
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    client.send(chunk)
                    
        except Exception as e:
            print(f"[Web] File send error for {filepath}: {e}")
            self._send_500(client)
    
    def _get_mime_type(self, path):
        """Get MIME type from file extension"""
        if path.endswith('.html'):
            return 'text/html'
        elif path.endswith('.css'):
            return 'text/css'
        elif path.endswith('.js'):
            return 'application/javascript'
        elif path.endswith('.json'):
            return 'application/json'
        elif path.endswith('.png'):
            return 'image/png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            return 'image/jpeg'
        elif path.endswith('.svg'):
            return 'image/svg+xml'
        else:
            return 'application/octet-stream'
    
    def _send_404(self, client):
        """Send 404 response"""
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 9\r\n"
            "Connection: close\r\n"
            "\r\n"
            "Not Found"
        )
        client.send(response.encode('utf-8'))
    
    def _send_405(self, client):
        """Send 405 response"""
        response = (
            "HTTP/1.1 405 Method Not Allowed\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 18\r\n"
            "Connection: close\r\n"
            "\r\n"
            "Method Not Allowed"
        )
        client.send(response.encode('utf-8'))
    
    def _send_500(self, client):
        """Send 500 response"""
        response = (
            "HTTP/1.1 500 Internal Server Error\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 21\r\n"
            "Connection: close\r\n"
            "\r\n"
            "Internal Server Error"
        )
        try:
            client.send(response.encode('utf-8'))
        except:
            pass
    
    def stop(self):
        """Stop the web server"""
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            print("[Web] Server stopped")
