"""
web_server_gz.py - CircuitPython web server with gzip compression support

This module extends the basic web server to serve pre-compressed .gz files
with proper Content-Encoding headers for maximum flash savings.

Usage in code.py:
    from web_server_gz import WebServerGzip
    
    server = WebServerGzip(pool, debug=True)
    server.start(port=80)
    
    while True:
        server.poll()
        time.sleep(0.01)
"""

import time
import os

class WebServerGzip:
    """Web server that serves pre-compressed gzip files"""
    
    def __init__(self, socket_pool, web_root="/web", debug=False):
        """
        Initialize web server with gzip support
        
        Args:
            socket_pool: socketpool from wifi
            web_root: Directory containing web files (default: /web)
            debug: Enable debug logging
        """
        self.pool = socket_pool
        self.web_root = web_root
        self.debug = debug
        self.server_socket = None
        
        # Load asset map if available
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
                print("[Web] No asset map found, using file discovery")
    
    def start(self, port=80, max_connections=1):
        """Start the web server"""
        import socketpool
        
        self.server_socket = self.pool.socket(
            self.pool.AF_INET, 
            self.pool.SOCK_STREAM
        )
        self.server_socket.setsockopt(
            self.pool.SOL_SOCKET,
            self.pool.SO_REUSEADDR,
            1
        )
        self.server_socket.bind(('0.0.0.0', port))
        self.server_socket.listen(max_connections)
        self.server_socket.setblocking(False)
        
        if self.debug:
            print(f"[Web] Server started on port {port}")
    
    def poll(self):
        """Poll for incoming connections (non-blocking)"""
        try:
            client, addr = self.server_socket.accept()
            if self.debug:
                print(f"[Web] Connection from {addr}")
            self._handle_client(client)
        except OSError:
            # No connection available (non-blocking)
            pass
    
    def _handle_client(self, client):
        """Handle a client connection"""
        try:
            client.settimeout(2.0)  # 2 second timeout
            
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
            
            # Serve file
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
        """
        Parse HTTP request
        
        Returns:
            (path, accepts_gzip)
        """
        lines = request.split('\r\n')
        
        # Parse request line
        path = "/"
        if lines and lines[0].startswith('GET '):
            parts = lines[0].split(' ')
            if len(parts) >= 2:
                path = parts[1]
                # Remove query string
                if '?' in path:
                    path = path[:path.index('?')]
        
        # Check for gzip support
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
            # Fallback: try to serve file directly
            if path == "/":
                filepath = f"{self.web_root}/index.html"
                mime_type = "text/html"
            else:
                filepath = f"{self.web_root}{path}"
                mime_type = self._guess_mime_type(path)
            gzippath = filepath + ".gz"
        
        # Try compressed version first if client accepts gzip
        if accepts_gzip and self._file_exists(gzippath):
            self._send_file(client, gzippath, mime_type, compressed=True)
        elif self._file_exists(filepath):
            self._send_file(client, filepath, mime_type, compressed=False)
        else:
            self._send_404(client)
    
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
            # Get file size
            file_size = os.stat(filepath)[6]
            
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
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(512)  # 512 byte chunks
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
        
        if self.debug:
            print("[Web] Sent 404")
    
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
        
        if self.debug:
            print("[Web] Sent 500")
    
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
        elif path.endswith('.png'):
            return 'image/png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            return 'image/jpeg'
        elif path.endswith('.svg'):
            return 'image/svg+xml'
        else:
            return 'application/octet-stream'
    
    def stop(self):
        """Stop the web server"""
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            if self.debug:
                print("[Web] Server stopped")


# Example usage in code.py:
"""
import wifi
import socketpool
from web_server_gz import WebServerGzip

# Connect to WiFi or start AP
# ... (your existing WiFi setup)

# Create web server
pool = socketpool.SocketPool(wifi.radio)
server = WebServerGzip(pool, web_root="/web", debug=True)
server.start(port=80)

print("Web server running!")

# Main loop
while True:
    server.poll()
    # ... (your other tasks)
    time.sleep(0.01)
"""
