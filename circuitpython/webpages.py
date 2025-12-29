"""
webpages.py - Embedded HTML/JS pages for ESP-01 web server

Contains the HTML/JavaScript for the real-time telemetry display.
Pages are stored as strings and served via ESP-01 when requested.
"""

# Main telemetry page
INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenPony Logger - Live Telemetry</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header h1 {
            color: white;
            font-size: 2em;
            margin-bottom: 5px;
        }
        .header .subtitle {
            color: rgba(255,255,255,0.9);
            font-size: 1em;
        }
        .status {
            text-align: center;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 5px;
            font-weight: bold;
        }
        .status.connected { background: #2d5016; color: #7dff7d; }
        .status.disconnected { background: #501616; color: #ff7d7d; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .card h2 {
            color: #667eea;
            font-size: 1.2em;
            margin-bottom: 15px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #3a3a3a;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label {
            color: #999;
            font-size: 0.9em;
        }
        .metric-value {
            color: #e0e0e0;
            font-weight: bold;
            font-family: 'Courier New', monospace;
        }
        .large-value {
            font-size: 3em;
            text-align: center;
            font-weight: bold;
            color: #667eea;
            margin: 20px 0;
            font-family: 'Courier New', monospace;
        }
        .gforce-display {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }
        .gforce-item {
            text-align: center;
        }
        .gforce-label {
            color: #999;
            font-size: 0.8em;
            margin-bottom: 5px;
        }
        .gforce-value {
            font-size: 2em;
            font-weight: bold;
            font-family: 'Courier New', monospace;
        }
        .gforce-x { color: #ff6b6b; }
        .gforce-y { color: #4ecdc4; }
        .gforce-z { color: #ffe66d; }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 1.5em; }
            .large-value { font-size: 2em; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏎️ OpenPony Logger</h1>
        <div class="subtitle">Real-Time Telemetry</div>
    </div>

    <div id="status" class="status disconnected">Connecting to WebSocket...</div>

    <div class="grid">
        <!-- Speed Card -->
        <div class="card">
            <h2>Speed</h2>
            <div class="large-value" id="speed">0.0</div>
            <div style="text-align: center; color: #999;">MPH</div>
        </div>

        <!-- GPS Card -->
        <div class="card">
            <h2>GPS Position</h2>
            <div class="metric">
                <span class="metric-label">Latitude</span>
                <span class="metric-value" id="lat">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Longitude</span>
                <span class="metric-value" id="lon">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Altitude</span>
                <span class="metric-value" id="alt">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Satellites</span>
                <span class="metric-value" id="sats">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Fix Type</span>
                <span class="metric-value" id="fix_type">No Fix</span>
            </div>
            <div class="metric">
                <span class="metric-label">HDOP</span>
                <span class="metric-value" id="hdop">--</span>
            </div>
        </div>

        <!-- G-Forces Card -->
        <div class="card">
            <h2>G-Forces</h2>
            <div class="gforce-display">
                <div class="gforce-item">
                    <div class="gforce-label">X (Lateral)</div>
                    <div class="gforce-value gforce-x" id="gx">+0.0</div>
                </div>
                <div class="gforce-item">
                    <div class="gforce-label">Y (Longitudinal)</div>
                    <div class="gforce-value gforce-y" id="gy">+0.0</div>
                </div>
                <div class="gforce-item">
                    <div class="gforce-label">Z (Vertical)</div>
                    <div class="gforce-value gforce-z" id="gz">+1.0</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let reconnectInterval = null;

        function connect() {
            ws = new WebSocket('ws://' + window.location.hostname + '/ws');

            ws.onopen = function() {
                console.log('WebSocket connected');
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('status').className = 'status connected';
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            };

            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    updateTelemetry(data);
                } catch (e) {
                    console.error('Parse error:', e);
                }
            };

            ws.onclose = function() {
                console.log('WebSocket disconnected');
                document.getElementById('status').textContent = 'Disconnected - Reconnecting...';
                document.getElementById('status').className = 'status disconnected';

                if (!reconnectInterval) {
                    reconnectInterval = setInterval(connect, 2000);
                }
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                ws.close();
            };
        }

        function updateTelemetry(data) {
            // Speed (convert m/s to MPH if needed, or use as-is if already MPH)
            if ('speed' in data) {
                document.getElementById('speed').textContent = data.speed.toFixed(1);
            }

            // GPS Position
            if ('lat' in data) {
                document.getElementById('lat').textContent = data.lat.toFixed(6);
            }
            if ('lon' in data) {
                document.getElementById('lon').textContent = data.lon.toFixed(6);
            }
            if ('alt' in data) {
                document.getElementById('alt').textContent = data.alt.toFixed(1) + ' m';
            }
            if ('satellites' in data) {
                document.getElementById('sats').textContent = data.satellites;
            }
            if ('fix_type' in data) {
                document.getElementById('fix_type').textContent = data.fix_type;
            }
            if ('hdop' in data) {
                const hdop = data.hdop;
                document.getElementById('hdop').textContent = hdop < 99 ? hdop.toFixed(1) : '--';
            }

            // G-Forces
            if ('gx' in data) {
                const gx = data.gx;
                document.getElementById('gx').textContent = (gx >= 0 ? '+' : '') + gx.toFixed(2);
            }
            if ('gy' in data) {
                const gy = data.gy;
                document.getElementById('gy').textContent = (gy >= 0 ? '+' : '') + gy.toFixed(2);
            }
            if ('gz' in data) {
                const gz = data.gz;
                document.getElementById('gz').textContent = (gz >= 0 ? '+' : '') + gz.toFixed(2);
            }
        }

        // Start connection
        connect();
    </script>
</body>
</html>
"""

# Simple 404 page
NOT_FOUND_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>404 - Not Found</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
        }
        h1 { font-size: 4em; color: #667eea; }
        p { font-size: 1.2em; }
        a { color: #667eea; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <p>Page not found</p>
        <p><a href="/">Return to telemetry</a></p>
    </div>
</body>
</html>
"""

def get_page(filename):
    """
    Get page content by filename

    Args:
        filename: Requested filename (e.g., '/', '/index.html')

    Returns:
        str: Page content or None if not found
    """
    # Normalize filename
    if filename == '/':
        filename = '/index.html'

    # Map filenames to pages
    pages = {
        '/index.html': INDEX_HTML,
        '/404.html': NOT_FOUND_HTML
    }

    return pages.get(filename, None)
