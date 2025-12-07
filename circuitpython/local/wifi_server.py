"""
wifi_server.py - WiFi AP and Web Server for OpenPonyLogger
Combines WiFi access point setup with gzip-compressed web serving
"""

import wifi
import socketpool
import time
import os

class WiFiAPTask:
    """WiFi Access Point manager"""
    
    def __init__(self, ssid="OpenPonyLogger", password="mustanggt"):
        self.ssid = ssid
        self.password = password
        self.ap_active = False
        self.ip_address = None
        
    def start(self):
        """Start WiFi Access Point"""
        try:
            wifi.radio.start_ap(ssid=self.ssid, password=self.password)
            self.ap_active = True
            self.ip_address = str(wifi.radio.ipv4_address_ap)
            print(f"[WiFi] AP Started: {self.ssid}")
            print(f"[WiFi] IP: {self.ip_address}")
            return True
        except Exception as e:
            print(f"[WiFi] Failed to start AP: {e}")
            return False
    
    def stop(self):
        """Stop WiFi Access Point"""
        if self.ap_active:
            wifi.radio.stop_ap()
            self.ap_active = False
            print("[WiFi] AP Stopped")


class WebServerTask:
    """Web server with gzip compression support"""
    
    def __init__(self, data_buffer, wifi_ap, web_root="/web", debug=True):
        self.data_buffer = data_buffer
        self.wifi_ap = wifi_ap
        self.web_root = web_root
        self.debug = debug
        self.server_socket = None
        self.request_count = 0
        
        # Load asset map
        try:
            import sys
            sys.path.append(web_root)
            from asset_map import ASSETS
            self.assets = ASSETS
            if self.debug:
                print(f"[Web] Loaded {len(ASSETS)} assets from map")
        except ImportError:
            self.assets = None
            if self.debug:
                print("[Web] No asset map found")
    
    def start(self, port=80):
        """Start web server"""
        try:
            pool = socketpool.SocketPool(wifi.radio)
            self.server_socket = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            self.server_socket.setsockopt(
                pool.SOL_SOCKET,
                pool.SO_REUSEADDR,
                1
            )
            self.server_socket.bind(('0.0.0.0', port))
            self.server_socket.listen(1)
            self.server_socket.setblocking(False)
            
            if self.debug:
                print(f"[Web] Server started on port {port}")
            return True
        except Exception as e:
            print(f"[Web] Failed to start: {e}")
            return False
    
    def poll(self):
        """Poll for incoming connections (non-blocking)"""
        try:
            client, addr = self.server_socket.accept()
            if self.debug:
                print(f"[Web] Connection from {addr}")
            self._handle_client(client)
            self.request_count += 1
        except OSError:
            pass  # No connection available
    
    def _handle_client(self, client):
        """Handle a client connection"""
        try:
            client.settimeout(2.0)
            
            # Read request
            request = b""
            while True:
                try:
                    chunk = client.recv(1024)
                    if not chunk:
                        break
                    request += chunk
                    if b"\r\n\r\n" in request:
                        break
                except OSError:
                    break
            
            if not request:
                return
            
            # Parse request
            request_str = request.decode('utf-8', errors='ignore')
            path, accepts_gzip = self._parse_request(request_str)
            
            if self.debug:
                print(f"[Web] GET {path} (gzip: {accepts_gzip})")
            
            # Serve file or API
            if path.startswith('/api/'):
                self._serve_api(client, path)
            else:
                self._serve_file(client, path, accepts_gzip)
                
        except Exception as e:
            if self.debug:
                print(f"[Web] Error: {e}")
        finally:
            try:
                client.close()
            except:
                pass
    
    def _parse_request(self, request):
        """Parse HTTP request"""
        lines = request.split('\r\n')
        
        path = "/"
        if lines and lines[0].startswith('GET '):
            parts = lines[0].split(' ')
            if len(parts) >= 2:
                path = parts[1]
                if '?' in path:
                    path = path[:path.index('?')]
        
        accepts_gzip = False
        for line in lines[1:]:
            if line.lower().startswith('accept-encoding:'):
                accepts_gzip = 'gzip' in line.lower()
                break
        
        return path, accepts_gzip
    
    def _serve_file(self, client, path, accepts_gzip):
        """Serve a file with optional gzip compression"""
        
        # Get asset info
        if self.assets and path in self.assets:
            asset = self.assets[path]
            filepath = f"{self.web_root}/{asset['file']}"
            gzippath = f"{self.web_root}/{asset['gzip']}"
            mime_type = asset['mime']
        else:
            if path == "/":
                filepath = f"{self.web_root}/index.html"
                mime_type = "text/html"
            else:
                filepath = f"{self.web_root}{path}"
                mime_type = self._guess_mime_type(path)
            gzippath = filepath + ".gz"
        
        # Try compressed version first
        if accepts_gzip and self._file_exists(gzippath):
            self._send_file(client, gzippath, mime_type, compressed=True)
        elif self._file_exists(filepath):
            self._send_file(client, filepath, mime_type, compressed=False)
        else:
            self._send_404(client)
    
    def _serve_api(self, client, path):
        """Serve API endpoints"""
        import json
        
        response_data = {}
        
        if path == '/api/live':
            accel = self.data_buffer.get('accel', {})
            response_data = {
                'accel': {
                    'gx': accel.get('gx', 0),
                    'gy': accel.get('gy', 0),
                    'gz': accel.get('gz', 0),
                    'g_total': accel.get('g_total', 0)
                },
                'system': {
                    'uptime': int(time.monotonic())
                }
            }
        elif path == '/api/status':
            response_data = {
                'version': 'v1.0.0',
                'git_hash': 'dev',
                'uptime': int(time.monotonic())
            }
        
        json_str = json.dumps(response_data)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(json_str)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            + json_str
        )
        client.send(response.encode('utf-8'))
    
    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _send_file(self, client, filepath, mime_type, compressed=False):
        """Send file to client"""
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
            
            if self.debug:
                encoding = "gzip" if compressed else "plain"
                print(f"[Web] Sent {filepath} ({file_size} bytes, {encoding})")
                
        except Exception as e:
            if self.debug:
                print(f"[Web] Error sending file: {e}")
            self._send_500(client)
    
    def _send_404(self, client):
        """Send 404 Not Found"""
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        )
        client.send(response.encode('utf-8'))
    
    def _send_500(self, client):
        """Send 500 Internal Server Error"""
        response = (
            "HTTP/1.1 500 Internal Server Error\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 21\r\n"
            "Connection: close\r\n"
            "\r\n"
            "500 Internal Error"
        )
        try:
            client.send(response.encode('utf-8'))
        except:
            pass
    
    def _guess_mime_type(self, path):
        """Guess MIME type from file extension"""
        if path.endswith('.html'):
            return 'text/html'
        elif path.endswith('.css'):
            return 'text/css'
        elif path.endswith('.js'):
            return 'application/javascript'
        elif path.endswith('.json'):
            return 'application/json'
        else:
            return 'application/octet-stream'
    
    def stop(self):
        """Stop the web server"""
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            if self.debug:
                print("[Web] Server stopped")
