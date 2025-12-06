"""
wifi_server.py - WiFi Access Point and HTTP Server with Debug Logging
"""

import wifi
import socketpool
import time
import json
import os
from adafruit_httpserver import Server, Request, Response

class WiFiAPTask:
    """WiFi Access Point manager"""
    def __init__(self, ssid="OpenPonyLogger", password=None):
        self.ssid = ssid
        self.password = password
        self.ap_active = False
        self.ip_address = None
        
    def start(self):
        """Start WiFi Access Point"""
        print("\n[WiFi] Starting Access Point...")
        print(f"  SSID: {self.ssid}")
        
        try:
            # Start AP mode
            if self.password:
                print(f"  Password: {'*' * len(self.password)}")
                wifi.radio.start_ap(self.ssid, self.password)
            else:
                print("  No password (open network)")
                wifi.radio.start_ap(self.ssid)
            
            self.ap_active = True
            self.ip_address = str(wifi.radio.ipv4_address_ap)
            
            print("  ✓ AP started")
            print("  IP Address: {self.ip_address}")
            print("  Gateway: {wifi.radio.ipv4_gateway_ap}")
            print("  Subnet: {wifi.radio.ipv4_subnet_ap}")
            print("  Channel: {wifi.radio.ap_info.channel if hasattr(wifi.radio, 'ap_info') else 'N/A'}")
            print("  Connect to: http://{self.ip_address}")
            
            return True
            
        except Exception as e:
            print("  ✗ Failed to start AP: {e}")
            import traceback
            traceback.print_exception(e)
            return False
    
    def stop(self):
        """Stop WiFi Access Point"""
        if self.ap_active:
            wifi.radio.stop_ap()
            self.ap_active = False
            print("[WiFi] Access Point stopped")


class WebServerTask:
    """HTTP server for web interface and API"""
    def __init__(self, data_buffer, wifi_ap):
        self.data_buffer = data_buffer
        self.wifi_ap = wifi_ap
        self.server = None
        self.pool = None
        self.request_count = 0
        self.last_request_time = 0
        
    def check_web_files(self):
        """Check if web files exist and are readable"""
        print("\n[WebServer] Checking web files...")
        web_dir = "/web"
    
        try:
            # Check if directory exists
            sd_contents = os.listdir("/sd")
            print(f"  Contents of /sd: {sd_contents}")
        
            if "web" not in sd_contents:
                print(f"  ✗ Directory 'web' not found in /sd")
                return False
        
            print(f"  ✓ Directory 'web' found")
        
            # List files in web directory
            try:
                files = os.listdir(web_dir)
                print(f"  Files in {web_dir}: {files}")
            except Exception as e:
                print(f"  ✗ Cannot list {web_dir}: {e}")
                return False
        
            # Check for index.html
            if "index.html" in files:
                print("  ✓ index.html found")
                # Try to read it
                try:
                    with open(f"{web_dir}/index.html", "r") as f:
                        content = f.read(100)  # Read first 100 chars
                        print(f"  ✓ index.html readable ({len(content)} chars preview)")
                except Exception as e:
                    print(f"  ✗ Cannot read index.html: {e}")
                    return False
            else:
                print("  ⚠ index.html not found in web directory")
                print(f"  Available files: {files}")
            
            # Check other important files
            for filename in ['styles.css', 'app.js', 'gauge.min.js']:
                if filename in files:
                    print(f"  ✓ {filename} found")
                else:
                    print(f"  ⚠ {filename} not found")
        
            return True
        
        except Exception as e:
            print(f"  ✗ Error checking files: {e}")
            import traceback
            traceback.print_exception(e)
            return False

    def start(self):
        """Initialize HTTP server"""
        if not self.wifi_ap.ap_active:
            print("[WebServer] Error: WiFi AP not active")
            return False
        
        print("\n[WebServer] Starting HTTP server...")
        
        # Check web files first
        if not self.check_web_files():
            print("  ⚠ Warning: Web files may not be accessible")
        
        try:
            # Create socket pool
            self.pool = socketpool.SocketPool(wifi.radio)
            print("  ✓ Socket pool created")
            
            # Create server with root directory for static files
            self.server = Server(self.pool, "/web", debug=True)
            print("  ✓ Server object created")
            
            # Register route handlers using decorators
            @self.server.route("/api/live")
            def live_data(request: Request):
                print(f"[API] /api/live requested from {request.client_address}")
                return self.serve_live_data(request)
            
            @self.server.route("/api/status")
            def status(request: Request):
                print(f"[API] /api/status requested from {request.client_address}")
                return self.serve_status(request)
            
            @self.server.route("/")
            def index(request: Request):
                print(f"[HTTP] / requested from {request.client_address}")
                return self.serve_index(request)
            
            print("  ✓ Routes registered")
            
            # Start server
            ip = str(wifi.radio.ipv4_address_ap)
            self.server.start(ip, port=80)
            
            print(f"  ✓ Server started on http://{ip}:80")
            print(f"  Serving files from: /web/")
            print(f"  Registered routes:")
            print(f"    - http://{ip}/")
            print(f"    - http://{ip}/api/live")
            print(f"    - http://{ip}/api/status")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to start server: {e}")
            import traceback
            traceback.print_exception(e)
            return False
    
    def serve_index(self, request: Request):
        """Serve main index.html"""
        try:
            print("[HTTP] Serving index.html...")
            with open("/web/index.html", "r") as f:
                html = f.read()
            print(f"[HTTP] Loaded {len(html)} bytes")
            return Response(request, html, content_type="text/html")
        except Exception as e:
            print(f"[HTTP] Error loading index.html: {e}")
            error_html = f"""
            <html>
            <body>
            <h1>Error</h1>
            <p>Could not load index.html: {e}</p>
            <p>Files available: {os.listdir('/web')}</p>
            </body>
            </html>
            """
            return Response(request, error_html, content_type="text/html", status=500)
    
    def serve_live_data(self, request: Request):
        """Serve live telemetry data as JSON"""
        accel = self.data_buffer.get('accel', {})
        gps = self.data_buffer.get('gps', {})
        
        # Build JSON response
        data = {
            "timestamp": int(time.monotonic() * 1000),
            "accel": {
                "x": round(accel.get('x', 0), 3),
                "y": round(accel.get('y', 0), 3),
                "z": round(accel.get('z', 0), 3),
                "gx": round(accel.get('gx', 0), 2),
                "gy": round(accel.get('gy', 0), 2),
                "gz": round(accel.get('gz', 0), 2),
                "g_total": round(accel.get('g_total', 1.0), 2)
            },
            "gps": {
                "speed": round(gps.get('speed', 0), 1),
                "latitude": gps.get('lat', 0),
                "longitude": gps.get('lon', 0),
                "altitude": round(gps.get('alt', 0), 1),
                "satellites": gps.get('sats', 0),
                "fix": gps.get('fix', 0)
            },
            "system": {
                "recording": True,
                "uptime": int(time.monotonic())
            }
        }
        
        # Convert to JSON string
        json_str = json.dumps(data)
        print(f"[API] Sending {len(json_str)} bytes of JSON")
        
        return Response(request, json_str, content_type="application/json")
    
    def serve_status(self, request: Request):
        """Serve system status"""
        import gc

        # Import version info
        try:
            from version import VERSION, GIT_HASH, BUILD_DATE
        except ImportError:
            VERSION = "unknown"
            GIT_HASH = "dev"
            BUILD_DATE = "unknown"
        
        status = {
            "version": VERSION,
            "git_hash": GIT_HASH,
            "build_date": BUILD_DATE,
            "uptime": int(time.monotonic()),
            "memory_free": gc.mem_free(),
            "wifi_connected": self.wifi_ap.ap_active,
            "ip_address": str(wifi.radio.ipv4_address_ap) if self.wifi_ap.ap_active else None,
            "requests_served": self.request_count
        }
        
        json_str = json.dumps(status)
        
        return Response(request, json_str, content_type="application/json")
    
    def poll(self):
        """Poll for incoming HTTP requests (call this regularly)"""
        if self.server:
            try:
                self.server.poll()
                
                # Log when we get requests
                current_time = time.monotonic()
                if current_time - self.last_request_time > 0.1:  # Debounce
                    # Check if we got a request (request_count would increment)
                    pass
                    
            except Exception as e:
                # Ignore timeout errors, they're normal
                error_str = str(e)
                if "ETIMEDOUT" not in error_str and "timed out" not in error_str and "timeout" not in error_str.lower():
                    print(f"[WebServer] Poll error: {e}")
                    import traceback
                    traceback.print_exception(e)
