import json
import ssl
import socketpool
import wifi
from adafruit_httpserver.server import Server
from adafruit_httpserver.request import HTTPRequest as Request
from adafruit_httpserver.response import HTTPResponse as Response
from adafruit_httpserver.status import HTTPStatus as Status

class WiFiAPTask:
    """A task to manage a WiFi Access Point."""
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.ap_active = False
        self.ip_address = None

    def start(self):
        """Start the WiFi AP"""
        try:
            wifi.radio.start_ap(ssid=self.ssid, password=self.password)
            self.ap_active = True
            self.ip_address = wifi.radio.ipv4_address_ap
            print(f"✓ WiFi AP '{self.ssid}' started on {self.ip_address}")
            return True
        except Exception as e:
            print(f"✗ Failed to start WiFi AP: {e}")
            return False

class WebServerTask:
    """A task to manage the web server."""
    def __init__(self, data_buffer, wifi_ap_task):
        self.data_buffer = data_buffer
        self.wifi_ap = wifi_ap_task
        self.request_count = 0
        
        pool = socketpool.SocketPool(wifi.radio)
        self.server = Server(pool, "/static", debug=True)
        
        self._add_routes()

    def _add_routes(self):
        @self.server.route("/")
        def base(request: Request):
            """Serve a simple hello world page"""
            self.request_count += 1
            return Response(request, f"Hello from the {self.data_buffer['system']['device_name']}!", content_type='text/html')

        @self.server.route("/api")
        def api(request: Request):
            """Return a subset of data for the simple dashboard"""
            self.request_count += 1
            
            # Extract relevant data for dashboard
            gps_data = self.data_buffer.get('gps', {})
            accel_data = self.data_buffer.get('accel', {})
            
            data = {
                "lat": gps_data.get('lat', 0),
                "lon": gps_data.get('lon', 0),
                "speed": gps_data.get('speed_mph', 0),
                "track_angle": gps_data.get('heading', 0),
                "satellites": gps_data.get('sats', 0),
                "g": {
                    "x": accel_data.get('gx', 0),
                    "y": accel_data.get('gy', 0),
                    "z": accel_data.get('gz', 0)
                },
                "ms": self.data_buffer['system'].get('uptime', 0) * 1000
            }
            return Response(request, json.dumps(data), content_type='application/json')

        @self.server.route("/api/live")
        def api_live(request: Request):
            """Return all available data from the shared buffer, making it JSON serializable"""
            self.request_count += 1
            
            import time
            import copy

            # Deep copy to avoid modifying the original buffer
            live_data = copy.deepcopy(self.data_buffer)

            # Convert non-serializable parts
            if live_data.get('gps') and live_data['gps'].get('timestamp'):
                ts = live_data['gps']['timestamp']
                if isinstance(ts, time.struct_time):
                    live_data['gps']['timestamp'] = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
                        ts.tm_year, ts.tm_mon, ts.tm_mday, ts.tm_hour, ts.tm_min, ts.tm_sec
                    )

            return Response(request, json.dumps(live_data), content_type='application/json')

    def start(self):
        """Start the web server"""
        try:
            self.server.start(str(self.wifi_ap.ip_address))
            return True
        except Exception as e:
            print(f"✗ Web server failed to start: {e}")
            return False

    def poll(self):
        """Poll the web server for incoming requests"""
        try:
            self.server.poll()
        except Exception as e:
            print(f"✗ Web server poll error: {e}")