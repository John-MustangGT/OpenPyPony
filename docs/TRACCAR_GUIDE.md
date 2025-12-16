# Traccar Integration Guide

Complete guide for setting up Traccar GPS tracking server and importing OpenPonyLogger data.

## Table of Contents

- [What is Traccar?](#what-is-traccar)
- [Installation](#installation)
  - [Docker (Recommended)](#docker-recommended)
  - [Linux Installation](#linux-installation)
  - [Windows Installation](#windows-installation)
  - [macOS Installation](#macos-installation)
- [Initial Setup](#initial-setup)
- [Adding Your Device](#adding-your-device)
- [Importing OPL Data](#importing-opl-data)
- [Viewing Your Tracks](#viewing-your-tracks)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## What is Traccar?

**Traccar** is a free, open-source GPS tracking platform that provides:

- 📍 **Real-time tracking** - View vehicle locations on a map
- 🗺️ **Route playback** - Replay past trips with speed control
- 📊 **Reports** - Distance, speed, stops, and more
- 🌐 **Web interface** - Access from any browser
- 📱 **Mobile apps** - iOS and Android
- 🔌 **Multiple protocols** - Supports 200+ GPS tracker protocols
- 🆓 **Free & Open Source** - No licensing costs

**Why use Traccar with OpenPonyLogger?**

- Visualize your track day sessions on interactive maps
- Analyze lap times and racing lines
- Compare multiple sessions
- Share tracks with friends
- Export to GPX/KML for Google Earth, Strava, etc.

---

## Installation

### Docker (Recommended)

**Fastest and easiest method for all platforms.**

#### Prerequisites
- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))

#### Installation Steps

```bash
# 1. Pull Traccar image
docker pull traccar/traccar:latest

# 2. Run Traccar container
docker run -d \
  --name traccar \
  --restart unless-stopped \
  -p 8082:8082 \
  -p 5055:5055 \
  -v traccar_data:/opt/traccar/data \
  traccar/traccar:latest
```

#### Port Explanation
- `8082` - Web interface (HTTP)
- `5055` - OsmAnd protocol (used by opl2traccar.py)

#### Verify Installation

```bash
# Check container is running
docker ps | grep traccar

# View logs
docker logs traccar

# Stop server
docker stop traccar

# Start server
docker start traccar
```

---

### Linux Installation

#### Ubuntu/Debian

```bash
# 1. Download Traccar package
wget https://github.com/traccar/traccar/releases/download/v5.12/traccar-linux-64-5.12.zip

# 2. Extract
unzip traccar-linux-64-5.12.zip

# 3. Install
sudo ./traccar.run

# 4. Start service
sudo systemctl start traccar

# 5. Enable autostart
sudo systemctl enable traccar

# 6. Check status
sudo systemctl status traccar
```

#### Fedora/CentOS/RHEL

```bash
# Same as above, but may need to adjust firewall
sudo firewall-cmd --permanent --add-port=8082/tcp
sudo firewall-cmd --permanent --add-port=5055/tcp
sudo firewall-cmd --reload
```

#### Configuration File
- Location: `/opt/traccar/conf/traccar.xml`
- Logs: `/opt/traccar/logs/`
- Database: `/opt/traccar/data/database/`

---

### Windows Installation

#### Steps

1. **Download Installer**
   - Visit: https://www.traccar.org/download/
   - Download: `traccar-windows-64-5.12.exe`

2. **Run Installer**
   - Double-click the installer
   - Follow the installation wizard
   - Accept defaults (installs to `C:\Program Files\Traccar\`)

3. **Start Service**
   - Open Services (`services.msc`)
   - Find "Traccar"
   - Right-click → Start
   - Set Startup Type to "Automatic"

4. **Configure Firewall**
   - Windows Defender Firewall → Allow an app
   - Add Traccar (ports 8082, 5055)

#### Alternative: Run as Application

```batch
cd "C:\Program Files\Traccar"
java -jar tracker-server.jar conf/traccar.xml
```

---

### macOS Installation

#### Using Homebrew (Recommended)

```bash
# 1. Install Java (if not already installed)
brew install openjdk@17

# 2. Download Traccar
wget https://github.com/traccar/traccar/releases/download/v5.12/traccar-other-5.12.zip

# 3. Extract
unzip traccar-other-5.12.zip -d /usr/local/traccar

# 4. Start server
cd /usr/local/traccar
java -jar tracker-server.jar conf/traccar.xml
```

#### Run at Startup (launchd)

Create file: `~/Library/LaunchAgents/org.traccar.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.traccar</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/java</string>
        <string>-jar</string>
        <string>/usr/local/traccar/tracker-server.jar</string>
        <string>/usr/local/traccar/conf/traccar.xml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

```bash
# Load service
launchctl load ~/Library/LaunchAgents/org.traccar.plist

# Unload service
launchctl unload ~/Library/LaunchAgents/org.traccar.plist
```

---

## Initial Setup

### 1. Access Web Interface

Open your browser and navigate to:
```
http://localhost:8082
```

Or for remote access:
```
http://your-server-ip:8082
```

### 2. Default Login

```
Username: admin
Password: admin
```

⚠️ **IMPORTANT:** Change the default password immediately!

### 3. Change Admin Password

1. Click the **User** menu (top right)
2. Select **Settings**
3. Go to **User** tab
4. Change password
5. Click **Save**

### 4. Configure Server Settings (Optional)

**Settings → Server**

- **Map Type**: Choose your preferred map (OpenStreetMap, Google Maps, etc.)
- **Coordinates Format**: Decimal degrees recommended
- **Speed Unit**: MPH or km/h
- **Distance Unit**: Miles or kilometers
- **Timezone**: Your local timezone

---

## Adding Your Device

### Step 1: Create Device

1. Click **Devices** (left sidebar)
2. Click **➕ Add** button
3. Fill in device details:

```
Name:       Mustang GT (or any name)
Identifier: mustang-gt (must match --device-id in opl2traccar.py)
Category:   Car
Model:      OpenPonyLogger
```

4. Click **Save**

### Step 2: Note the Identifier

The **Identifier** is critical - this is what opl2traccar.py uses to send data:

```bash
# Must match the identifier exactly
python3 opl2traccar.py session.opl --device-id mustang-gt
```

### Step 3: (Optional) Set Device Icon

1. Select your device
2. Click **Edit**
3. Choose **Category** to change icon (Car, Truck, Motorcycle, etc.)
4. Click **Save**

---

## Importing OPL Data

### Prerequisites

```bash
# Install Python dependencies
pip install requests

# Verify you have both scripts
ls opl2csv.py opl2traccar.py
```

### Method 1: Quick Batch Upload (Fastest)

Upload all GPS data as fast as possible:

```bash
python3 opl2traccar.py session_141.opl \
  --device-id mustang-gt \
  --batch --batch-size 100
```

**Expected output:**
```
Testing connection to Traccar server...
✓ Connected to Traccar server at localhost:5055

Reading: session_141.opl

Session: Track Day!
Driver: John
Vehicle: 1ZVBP8AM5E5123456
Found 43610 GPS positions to upload

Progress: 10000/43610 (22%) - 342.3 pts/sec - ETA: 98s
Progress: 20000/43610 (45%) - 338.1 pts/sec - ETA: 69s
...

============================================================
Upload Complete!
============================================================
Sent:     43610 positions
Failed:   0 positions
Time:     130.6 seconds
Rate:     334.0 positions/second
```

### Method 2: Realtime Playback

Watch the track appear on the map in real-time:

```bash
# 1x speed (actual session duration)
python3 opl2traccar.py session_141.opl \
  --device-id mustang-gt \
  --realtime

# 10x speed (faster playback)
python3 opl2traccar.py session_141.opl \
  --device-id mustang-gt \
  --realtime --speed 10

# Half speed (slower, detailed)
python3 opl2traccar.py session_141.opl \
  --device-id mustang-gt \
  --realtime --speed 0.5
```

**Use Cases:**
- **Batch mode**: Quick upload for analysis
- **Realtime mode**: Demonstration or live viewing
- **Fast playback**: Quick review of long sessions

### Method 3: Remote Server

Upload to a Traccar server on another machine:

```bash
python3 opl2traccar.py session_141.opl \
  --server gps.example.com \
  --port 5055 \
  --device-id mustang-gt \
  --batch
```

For HTTPS:
```bash
python3 opl2traccar.py session_141.opl \
  --server secure.example.com \
  --port 5055 \
  --device-id mustang-gt \
  --https
```

### Testing Connection

Before uploading, test connectivity:

```bash
python3 opl2traccar.py session_141.opl --test

# Output:
# Testing connection to Traccar server...
# ✓ Connected to Traccar server at localhost:5055
# ✓ Connection test successful
```

---

## Viewing Your Tracks

### Live View

1. Click **Devices** (left sidebar)
2. Select your device
3. Map shows current/last position
4. Device details appear in right panel

### Route Playback

1. Select your device
2. Click **Report** button (top toolbar)
3. Select report type: **Route**
4. Set date/time range
5. Click **Show**
6. Use playback controls:
   - ▶️ Play
   - ⏸️ Pause
   - ⏩ Speed up
   - ⏪ Slow down
   - 📍 Jump to position

### Reports

Available reports:
- **Route** - View path on map with playback
- **Trips** - Start/stop times, distance, duration
- **Stops** - Where and how long stopped
- **Summary** - Overview statistics
- **Chart** - Speed/altitude graphs

### Example: Track Day Analysis

```
Report: Route
From: 2024-12-16 09:00
To:   2024-12-16 10:30

Statistics:
- Distance: 12.8 miles
- Duration: 15m 20s
- Max Speed: 128 MPH
- Avg Speed: 75 MPH
- Stops: 3
```

---

## Advanced Usage

### Multiple Devices

Track multiple vehicles:

```bash
# Mustang
python3 opl2traccar.py session_mustang.opl --device-id mustang-gt

# Corvette
python3 opl2traccar.py session_corvette.opl --device-id corvette-z06
```

Each device appears separately on the map.

### Geofences

Create virtual boundaries:

1. **Settings → Geofences**
2. Click **➕ Add**
3. Draw area on map
4. Set notifications for entry/exit

**Use Cases:**
- Track boundary alerts
- Pit lane entry/exit
- Checkpoint timing

### Notifications

Set up alerts:

1. **Settings → Notifications**
2. Choose event type (speeding, geofence, etc.)
3. Configure delivery (email, SMS, push)

### Custom Attributes

Add metadata to devices:

```javascript
// In device settings
{
  "driver": "John",
  "vehicle": "2014 Mustang GT",
  "tire_pressure_front": "32 PSI",
  "tire_pressure_rear": "30 PSI"
}
```

### API Access

Traccar provides REST API for automation:

```bash
# Get device list
curl -u admin:password http://localhost:8082/api/devices

# Get positions
curl -u admin:password http://localhost:8082/api/positions?deviceId=1

# Export route as GPX
curl -u admin:password "http://localhost:8082/api/reports/route?deviceId=1&from=2024-12-16T00:00:00Z&to=2024-12-16T23:59:59Z&type=gpx"
```

### Exporting Data

Export formats available:
- **GPX** - GPS Exchange Format (Garmin, Strava)
- **KML** - Google Earth
- **CSV** - Excel/spreadsheet
- **XLSX** - Excel workbook

**Export Steps:**
1. Generate report
2. Click **Export** button
3. Choose format
4. Save file

---

## Troubleshooting

### Cannot Connect to Traccar

**Error:**
```
✗ Cannot connect to Traccar server at localhost:5055
```

**Solutions:**

1. **Check if Traccar is running:**
   ```bash
   # Docker
   docker ps | grep traccar
   
   # Linux
   sudo systemctl status traccar
   
   # Windows
   services.msc → check Traccar service
   ```

2. **Verify port 5055 is open:**
   ```bash
   # Linux/Mac
   netstat -an | grep 5055
   
   # Windows
   netstat -an | findstr 5055
   ```

3. **Check firewall:**
   ```bash
   # Linux (Ubuntu/Debian)
   sudo ufw allow 5055/tcp
   
   # Linux (Fedora/CentOS)
   sudo firewall-cmd --add-port=5055/tcp --permanent
   sudo firewall-cmd --reload
   
   # Windows
   # Windows Defender Firewall → Allow an app → Add port 5055
   ```

4. **Test with curl:**
   ```bash
   curl "http://localhost:5055/?id=test&lat=0&lon=0&timestamp=0"
   # Should return HTTP 200 OK
   ```

### Device Not Showing on Map

**Possible causes:**

1. **Wrong device identifier:**
   ```bash
   # Check device ID in Traccar web UI
   # Must match exactly (case-sensitive)
   python3 opl2traccar.py --device-id EXACT_ID_FROM_TRACCAR
   ```

2. **No GPS data in file:**
   ```bash
   # Verify file has GPS data
   python3 opl2csv.py session.opl
   # Check: GPS fixes: XXXX (should be > 0)
   ```

3. **Invalid coordinates:**
   - Check lat/lon are reasonable (lat: -90 to 90, lon: -180 to 180)
   - Verify timestamp is valid

### Upload Fails Partway Through

**Error:**
```
Progress: 5000/43610 (11%)
✗ Network error: Connection reset
```

**Solutions:**

1. **Increase timeout:**
   Edit `opl2traccar.py`, find:
   ```python
   response = requests.get(self.base_url, params=params, timeout=10)
   ```
   Change `timeout=10` to `timeout=30`

2. **Reduce batch size:**
   ```bash
   python3 opl2traccar.py session.opl --batch-size 10
   ```

3. **Check server resources:**
   ```bash
   # Docker
   docker stats traccar
   
   # Linux
   top
   htop
   ```

### Traccar Web UI Not Loading

1. **Check port 8082:**
   ```bash
   netstat -an | grep 8082
   ```

2. **Try different browser**

3. **Clear browser cache**

4. **Check logs:**
   ```bash
   # Docker
   docker logs traccar
   
   # Linux
   tail -f /opt/traccar/logs/tracker-server.log
   ```

### Slow Upload Speed

**Typical rates:**
- Local server: 200-500 positions/sec
- Remote server: 50-200 positions/sec
- Slow network: 10-50 positions/sec

**Improvements:**

1. **Use batch mode:**
   ```bash
   python3 opl2traccar.py session.opl --batch --batch-size 100
   ```

2. **Upload to local Traccar, then sync to remote**

3. **Check network latency:**
   ```bash
   ping gps.example.com
   ```

### Database Errors

If Traccar database becomes corrupted:

```bash
# Stop Traccar
docker stop traccar  # or: sudo systemctl stop traccar

# Backup database
cp /opt/traccar/data/database/database.mv.db ~/traccar-backup.mv.db

# Restart Traccar (will repair database)
docker start traccar  # or: sudo systemctl start traccar
```

---

## Performance Tips

### Large Files (>50,000 positions)

For files with >50,000 GPS positions:

1. **Split into chunks:**
   ```python
   # Custom script to split OPL file
   # Upload each chunk separately
   ```

2. **Use batch mode with large batch sizes:**
   ```bash
   python3 opl2traccar.py huge_session.opl \
     --batch --batch-size 500
   ```

3. **Upload off-peak hours** if using shared server

### Server Optimization

For better Traccar performance:

1. **Allocate more memory:**
   ```xml
   <!-- /opt/traccar/conf/traccar.xml -->
   <entry key='database.initializationFailTimeout'>0</entry>
   <entry key='database.maximumPoolSize'>15</entry>
   ```

2. **Use PostgreSQL instead of H2:**
   - Better for large datasets
   - See: https://www.traccar.org/database-migration/

3. **Regular maintenance:**
   ```sql
   -- Clean old positions (keep 30 days)
   DELETE FROM tc_positions WHERE fixtime < NOW() - INTERVAL 30 DAY;
   ```

---

## FAQ

### Q: Can I upload multiple sessions for the same device?

**A:** Yes! Each upload with different timestamps will appear as a separate track. Use the date range selector in reports to view specific sessions.

### Q: What's the maximum file size?

**A:** No hard limit. Successfully tested with files up to 1GB (500,000+ positions). Upload time scales linearly.

### Q: Can I upload while driving?

**A:** Not with this tool. For real-time tracking, configure OpenPonyLogger to send data directly to Traccar via WiFi/cellular.

### Q: Does Traccar support lap timing?

**A:** Not built-in, but you can:
1. Create geofence for start/finish line
2. Use event triggers to mark lap boundaries
3. Export to CSV and calculate lap times

### Q: How do I share tracks with others?

**A:** 
1. **Create limited user account** (view-only)
2. **Export to GPX/KML** and share file
3. **Take screenshots** of route playback
4. **Use Traccar's public link feature** (if enabled)

### Q: Can I compare two different sessions?

**A:** Create two devices (e.g., `session-1`, `session-2`), upload each session to its device, then view both on map simultaneously.

---

## Additional Resources

- **Traccar Documentation:** https://www.traccar.org/documentation/
- **API Reference:** https://www.traccar.org/api-reference/
- **Forum:** https://www.traccar.org/forums/
- **GitHub:** https://github.com/traccar/traccar
- **Demo Server:** https://demo.traccar.org (admin/admin)

---

## Next Steps

1. ✅ Install Traccar
2. ✅ Create device in web UI
3. ✅ Upload your first session
4. 📊 Analyze your track data
5. 🏁 Compare lap times
6. 📈 Track improvements over time

**Happy tracking! 🏎️💨**

---

*Last updated: December 16, 2024*
*OpenPonyLogger + Traccar Integration Guide*
