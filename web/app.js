// OpenPonyLogger Web UI - Application Logic
// Mock data generator for prototyping

class OpenPonyLogger {
    constructor() {
        this.isRecording = false;
        this.currentSession = null;
        this.sessions = this.loadMockSessions();
        this.gauges = {};
        this.animationFrames = {};
        this.additionalPids = [];
        this.fuelLog = this.loadFuelLog();
        this.pidTestResults = {};
        
        this.init();
    }

    init() {
        this.loadConfiguration();
        this.setupTabs();
        this.setupGauges();
        this.setupGForceDisplay();
        this.setupGPSDisplay();
        this.setupSessions();
        this.setupFuelLog();
        this.setupPIDTesting();
        this.setupConfig();
        this.startDataSimulation();
        this.updateConnectionStatus();
        this.applyStartupTab();
    }

    // Tab Navigation
    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.dataset.tab;
                
                // Remove active class from all
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked tab
                button.classList.add('active');
                document.getElementById(tabName).classList.add('active');
                
                // Trigger specific tab initialization
                this.onTabChange(tabName);
            });
        });
    }

    onTabChange(tabName) {
        switch(tabName) {
            case 'gauges':
                this.updateGauges();
                break;
            case 'gforce':
                this.drawGForce();
                break;
            case 'gps':
                this.drawGPS();
                break;
            case 'sessions':
                this.renderSessions();
                break;
        }
    }

    // Canvas-Gauges Setup
    setupGauges() {
        // Speed Gauge
        this.gauges.speed = new RadialGauge({
            renderTo: 'speedGauge',
            width: 250,
            height: 250,
            units: 'MPH',
            minValue: 0,
            maxValue: 180,
            majorTicks: ['0', '20', '40', '60', '80', '100', '120', '140', '160', '180'],
            minorTicks: 2,
            strokeTicks: true,
            highlights: [
                { from: 0, to: 80, color: 'rgba(76, 175, 80, .3)' },
                { from: 80, to: 120, color: 'rgba(255, 193, 7, .3)' },
                { from: 120, to: 180, color: 'rgba(244, 67, 54, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#ff6b35',
            colorNeedleEnd: '#ff6b35',
            needleCircleSize: 10,
            needleCircleOuter: false,
            animationDuration: 500,
            animationRule: 'linear',
            fontNumbersSize: 20,
            borders: false
        }).draw();

        // RPM Gauge
        this.gauges.rpm = new RadialGauge({
            renderTo: 'rpmGauge',
            width: 250,
            height: 250,
            units: 'x1000',
            minValue: 0,
            maxValue: 8,
            majorTicks: ['0', '1', '2', '3', '4', '5', '6', '7', '8'],
            minorTicks: 5,
            strokeTicks: true,
            highlights: [
                { from: 0, to: 5, color: 'rgba(76, 175, 80, .3)' },
                { from: 5, to: 6.5, color: 'rgba(255, 193, 7, .3)' },
                { from: 6.5, to: 8, color: 'rgba(244, 67, 54, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#ff6b35',
            colorNeedleEnd: '#ff6b35',
            needleCircleSize: 10,
            animationDuration: 500,
            animationRule: 'linear',
            fontNumbersSize: 20,
            borders: false
        }).draw();

        // Temperature Gauge
        this.gauges.temp = new RadialGauge({
            renderTo: 'tempGauge',
            width: 250,
            height: 250,
            units: '°F',
            minValue: 100,
            maxValue: 250,
            majorTicks: ['100', '125', '150', '175', '200', '225', '250'],
            minorTicks: 5,
            strokeTicks: true,
            highlights: [
                { from: 100, to: 195, color: 'rgba(76, 175, 80, .3)' },
                { from: 195, to: 220, color: 'rgba(255, 193, 7, .3)' },
                { from: 220, to: 250, color: 'rgba(244, 67, 54, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#2196f3',
            colorNeedleEnd: '#2196f3',
            needleCircleSize: 10,
            animationDuration: 1000,
            fontNumbersSize: 18,
            borders: false
        }).draw();

        // Oil Pressure Gauge
        this.gauges.oilPressure = new RadialGauge({
            renderTo: 'oilPressureGauge',
            width: 250,
            height: 250,
            units: 'PSI',
            minValue: 0,
            maxValue: 100,
            majorTicks: ['0', '20', '40', '60', '80', '100'],
            minorTicks: 4,
            strokeTicks: true,
            highlights: [
                { from: 0, to: 20, color: 'rgba(244, 67, 54, .3)' },
                { from: 20, to: 80, color: 'rgba(76, 175, 80, .3)' },
                { from: 80, to: 100, color: 'rgba(255, 193, 7, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#4caf50',
            colorNeedleEnd: '#4caf50',
            needleCircleSize: 10,
            animationDuration: 1000,
            fontNumbersSize: 20,
            borders: false
        }).draw();

        // Boost Gauge
        this.gauges.boost = new RadialGauge({
            renderTo: 'boostGauge',
            width: 250,
            height: 250,
            units: 'PSI',
            minValue: -5,
            maxValue: 20,
            majorTicks: ['-5', '0', '5', '10', '15', '20'],
            minorTicks: 5,
            strokeTicks: true,
            highlights: [
                { from: -5, to: 0, color: 'rgba(33, 150, 243, .3)' },
                { from: 0, to: 12, color: 'rgba(76, 175, 80, .3)' },
                { from: 12, to: 20, color: 'rgba(255, 193, 7, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#f7931e',
            colorNeedleEnd: '#f7931e',
            needleCircleSize: 10,
            animationDuration: 500,
            fontNumbersSize: 20,
            borders: false
        }).draw();

        // Throttle Position Gauge
        this.gauges.throttle = new RadialGauge({
            renderTo: 'throttleGauge',
            width: 250,
            height: 250,
            units: '%',
            minValue: 0,
            maxValue: 100,
            majorTicks: ['0', '20', '40', '60', '80', '100'],
            minorTicks: 4,
            strokeTicks: true,
            highlights: [
                { from: 0, to: 100, color: 'rgba(76, 175, 80, .3)' }
            ],
            colorPlate: '#1a1a1a',
            colorMajorTicks: '#ffffff',
            colorMinorTicks: '#808080',
            colorNumbers: '#ffffff',
            colorNeedle: '#ffc107',
            colorNeedleEnd: '#ffc107',
            needleCircleSize: 10,
            animationDuration: 300,
            fontNumbersSize: 20,
            borders: false
        }).draw();
    }

    updateGauges() {
        // Simulate realistic driving data
        const speed = 45 + Math.random() * 30;
        const rpm = 2.5 + Math.random() * 2;
        const temp = 185 + Math.random() * 10;
        const oilPressure = 40 + Math.random() * 20;
        const boost = -2 + Math.random() * 8;
        const throttle = Math.random() * 100;

        this.gauges.speed.value = speed;
        this.gauges.rpm.value = rpm;
        this.gauges.temp.value = temp;
        this.gauges.oilPressure.value = oilPressure;
        this.gauges.boost.value = boost;
        this.gauges.throttle.value = throttle;
    }

    // G-Force Display
    setupGForceDisplay() {
        const canvas = document.getElementById('gforceCanvas');
        canvas.width = 600;
        canvas.height = 600;
        this.gforceCtx = canvas.getContext('2d');
        this.gforceData = { lat: 0, long: 0, vert: 1.0 };
        this.gforcePeaks = { maxAccel: 0, maxBrake: 0, maxCorner: 0 };
    }

    drawGForce() {
        const ctx = this.gforceCtx;
        const canvas = ctx.canvas;
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 40;

        // Clear canvas
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw concentric circles (0.5g increments)
        ctx.strokeStyle = '#404040';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 4; i++) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius * i / 4, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw crosshairs
        ctx.strokeStyle = '#808080';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY - radius);
        ctx.lineTo(centerX, centerY + radius);
        ctx.moveTo(centerX - radius, centerY);
        ctx.lineTo(centerX + radius, centerY);
        ctx.stroke();

        // Draw labels
        ctx.fillStyle = '#b0b0b0';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('1.0g', centerX, centerY - radius - 10);
        ctx.fillText('1.0g', centerX, centerY + radius + 25);
        ctx.textAlign = 'right';
        ctx.fillText('1.0g', centerX - radius - 10, centerY + 5);
        ctx.textAlign = 'left';
        ctx.fillText('1.0g', centerX + radius + 10, centerY + 5);

        // Draw current G-force position
        const gX = this.gforceData.lat * radius;
        const gY = -this.gforceData.long * radius; // Negative for forward=up

        // Trail effect
        ctx.strokeStyle = 'rgba(255, 107, 53, 0.3)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(centerX + gX, centerY + gY);
        ctx.stroke();

        // Current position
        ctx.fillStyle = '#ff6b35';
        ctx.beginPath();
        ctx.arc(centerX + gX, centerY + gY, 12, 0, Math.PI * 2);
        ctx.fill();

        // Outer ring
        ctx.strokeStyle = '#ff6b35';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(centerX + gX, centerY + gY, 18, 0, Math.PI * 2);
        ctx.stroke();

        // Request next frame
        requestAnimationFrame(() => this.drawGForce());
    }

    updateGForceData() {
        // Simulate realistic G-forces
        this.gforceData.lat = (Math.random() - 0.5) * 0.6;
        this.gforceData.long = (Math.random() - 0.3) * 0.8;
        this.gforceData.vert = 0.95 + Math.random() * 0.1;

        // Update display values
        document.getElementById('gforceLat').textContent = this.gforceData.lat.toFixed(2) + 'g';
        document.getElementById('gforceLong').textContent = this.gforceData.long.toFixed(2) + 'g';
        document.getElementById('gforceVert').textContent = this.gforceData.vert.toFixed(2) + 'g';

        // Update peaks
        if (this.gforceData.long > this.gforcePeaks.maxAccel) {
            this.gforcePeaks.maxAccel = this.gforceData.long;
            document.getElementById('maxAccel').textContent = this.gforcePeaks.maxAccel.toFixed(2) + 'g';
        }
        if (this.gforceData.long < -this.gforcePeaks.maxBrake) {
            this.gforcePeaks.maxBrake = -this.gforceData.long;
            document.getElementById('maxBrake').textContent = this.gforcePeaks.maxBrake.toFixed(2) + 'g';
        }
        const cornerG = Math.abs(this.gforceData.lat);
        if (cornerG > this.gforcePeaks.maxCorner) {
            this.gforcePeaks.maxCorner = cornerG;
            document.getElementById('maxCorner').textContent = this.gforcePeaks.maxCorner.toFixed(2) + 'g';
        }
    }

    // GPS Display
    setupGPSDisplay() {
        const canvas = document.getElementById('gpsCanvas');
        canvas.width = 800;
        canvas.height = 600;
        this.gpsCtx = canvas.getContext('2d');
        this.gpsData = {
            lat: 42.2793,
            lon: -71.4162,
            alt: 525,
            heading: 0,
            speed: 0,
            maxSpeed: 0,
            satellites: this.generateMockSatellites()
        };
    }

    drawGPS() {
        const ctx = this.gpsCtx;
        const canvas = ctx.canvas;
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 40;

        // Clear canvas
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw sky circle
        ctx.fillStyle = '#1a1a1a';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();

        // Draw compass rings
        ctx.strokeStyle = '#404040';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 3; i++) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius * i / 3, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw cardinal directions
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 24px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('N', centerX, centerY - radius - 15);
        ctx.fillText('S', centerX, centerY + radius + 30);
        ctx.textAlign = 'right';
        ctx.fillText('W', centerX - radius - 15, centerY + 8);
        ctx.textAlign = 'left';
        ctx.fillText('E', centerX + radius + 15, centerY + 8);

        // Draw satellites
        this.gpsData.satellites.forEach(sat => {
            const angle = (sat.azimuth - 90) * Math.PI / 180;
            const distance = radius * (1 - sat.elevation / 90);
            const x = centerX + distance * Math.cos(angle);
            const y = centerY + distance * Math.sin(angle);

            // Satellite color based on SNR
            let color;
            if (sat.snr > 35) color = '#4caf50';
            else if (sat.snr > 25) color = '#ffc107';
            else color = '#f44336';

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();

            // Satellite ID
            ctx.fillStyle = '#ffffff';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(sat.id, x, y - 12);
        });

        // Draw heading indicator
        const headingAngle = (this.gpsData.heading - 90) * Math.PI / 180;
        ctx.strokeStyle = '#ff6b35';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(
            centerX + radius * 0.7 * Math.cos(headingAngle),
            centerY + radius * 0.7 * Math.sin(headingAngle)
        );
        ctx.stroke();

        requestAnimationFrame(() => this.drawGPS());
    }

    generateMockSatellites() {
        const satellites = [];
        for (let i = 1; i <= 12; i++) {
            satellites.push({
                id: i,
                azimuth: Math.random() * 360,
                elevation: 15 + Math.random() * 75,
                snr: 20 + Math.random() * 30
            });
        }
        return satellites;
    }

    updateGPSData() {
        this.gpsData.heading = (this.gpsData.heading + 1) % 360;
        this.gpsData.speed = 45 + Math.random() * 20;
        if (this.gpsData.speed > this.gpsData.maxSpeed) {
            this.gpsData.maxSpeed = this.gpsData.speed;
        }

        // Update display
        document.getElementById('gpsLat').textContent = this.gpsData.lat.toFixed(6) + '°';
        document.getElementById('gpsLon').textContent = this.gpsData.lon.toFixed(6) + '°';
        document.getElementById('gpsAlt').textContent = this.gpsData.alt.toFixed(0) + ' ft';
        document.getElementById('gpsHeading').textContent = this.gpsData.heading.toFixed(0) + '°';
        document.getElementById('gpsSpeed').textContent = this.gpsData.speed.toFixed(1) + ' MPH';
        document.getElementById('gpsMaxSpeed').textContent = this.gpsData.maxSpeed.toFixed(1) + ' MPH';

        // Update satellite list
        const satList = document.getElementById('satList');
        satList.innerHTML = this.gpsData.satellites.slice(0, 8).map(sat => `
            <div class="satellite-item">
                <span class="sat-id">PRN ${sat.id}</span>
                <span class="sat-snr">${sat.snr.toFixed(0)} dB</span>
            </div>
        `).join('');
    }

    // Sessions Management
    loadMockSessions() {
        return [
            {
                id: 1,
                name: 'Morning Commute',
                date: '2024-12-02',
                time: '08:15 AM',
                duration: '25:42',
                distance: '18.3 mi',
                maxSpeed: '68 MPH',
                maxGForce: '0.52g',
                avgSpeed: '42 MPH'
            },
            {
                id: 2,
                name: 'Track Day - Session 1',
                date: '2024-12-01',
                time: '10:30 AM',
                duration: '15:20',
                distance: '12.8 mi',
                maxSpeed: '128 MPH',
                maxGForce: '1.24g',
                avgSpeed: '75 MPH'
            },
            {
                id: 3,
                name: 'Evening Drive',
                date: '2024-11-30',
                time: '06:45 PM',
                duration: '42:15',
                distance: '31.2 mi',
                maxSpeed: '75 MPH',
                maxGForce: '0.68g',
                avgSpeed: '48 MPH'
            }
        ];
    }

    setupSessions() {
        const startButton = document.getElementById('startSession');
        const exportButton = document.getElementById('exportSessions');

        startButton.addEventListener('click', () => {
            this.toggleRecording();
        });

        exportButton.addEventListener('click', () => {
            this.exportSessions();
        });

        this.renderSessions();
    }

    toggleRecording() {
        this.isRecording = !this.isRecording;
        const button = document.getElementById('startSession');
        const buttonText = document.getElementById('sessionButtonText');

        if (this.isRecording) {
            button.classList.add('recording');
            buttonText.textContent = '⏹ Stop Recording';
            this.currentSession = {
                startTime: new Date(),
                name: `Session ${this.sessions.length + 1}`
            };
        } else {
            button.classList.remove('recording');
            buttonText.textContent = 'Start Recording';
            if (this.currentSession) {
                // Save session
                const duration = Math.floor((new Date() - this.currentSession.startTime) / 1000);
                this.sessions.unshift({
                    id: this.sessions.length + 1,
                    name: this.currentSession.name,
                    date: new Date().toISOString().split('T')[0],
                    time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
                    duration: this.formatDuration(duration),
                    distance: (Math.random() * 30 + 5).toFixed(1) + ' mi',
                    maxSpeed: (Math.random() * 50 + 60).toFixed(0) + ' MPH',
                    maxGForce: (Math.random() * 0.8 + 0.3).toFixed(2) + 'g',
                    avgSpeed: (Math.random() * 30 + 35).toFixed(0) + ' MPH'
                });
                this.renderSessions();
            }
        }
    }

    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    renderSessions() {
        const sessionsList = document.getElementById('sessionsList');
        
        if (this.sessions.length === 0) {
            sessionsList.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 2rem;">No sessions recorded yet.</p>';
            return;
        }

        sessionsList.innerHTML = this.sessions.map(session => `
            <div class="session-card">
                <div class="session-info">
                    <h3>${session.name}</h3>
                    <div class="session-meta">
                        <span>📅 ${session.date}</span>
                        <span>🕐 ${session.time}</span>
                        <span>⏱️ ${session.duration}</span>
                    </div>
                    <div class="session-stats">
                        <div class="stat">
                            <div class="stat-value">${session.distance}</div>
                            <div class="stat-label">Distance</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${session.maxSpeed}</div>
                            <div class="stat-label">Max Speed</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${session.maxGForce}</div>
                            <div class="stat-label">Max G-Force</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${session.avgSpeed}</div>
                            <div class="stat-label">Avg Speed</div>
                        </div>
                    </div>
                </div>
                <div class="session-actions">
                    <button class="btn btn-secondary btn-sm" onclick="app.viewSession(${session.id})">View</button>
                    <button class="btn btn-secondary btn-sm" onclick="app.exportSession(${session.id})">Export</button>
                    <button class="btn btn-danger btn-sm" onclick="app.deleteSession(${session.id})">Delete</button>
                </div>
            </div>
        `).join('');
    }

    viewSession(id) {
        alert(`Viewing session ${id} (functionality to be implemented)`);
    }

    exportSession(id) {
        alert(`Exporting session ${id} to CSV (functionality to be implemented)`);
    }

    deleteSession(id) {
        if (confirm('Are you sure you want to delete this session?')) {
            this.sessions = this.sessions.filter(s => s.id !== id);
            this.renderSessions();
        }
    }

    exportSessions() {
        alert('Exporting all sessions to CSV (functionality to be implemented)');
    }

    // Configuration
    setupConfig() {
        const saveButton = document.getElementById('saveConfig');
        const resetButton = document.getElementById('resetConfig');
        const factoryResetButton = document.getElementById('factoryReset');
        const brightnessSlider = document.getElementById('brightness');
        const brightnessValue = document.getElementById('brightnessValue');
        const addPidButton = document.getElementById('addPidButton');

        brightnessSlider.addEventListener('input', (e) => {
            brightnessValue.textContent = e.target.value + '%';
        });

        saveButton.addEventListener('click', () => {
            this.saveConfiguration();
        });

        resetButton.addEventListener('click', () => {
            if (confirm('Reset all settings to defaults?')) {
                this.resetConfiguration();
            }
        });

        factoryResetButton.addEventListener('click', () => {
            if (confirm('WARNING: This will delete all data and reset to factory settings. Continue?')) {
                this.factoryReset();
            }
        });

        // Additional PIDs management
        addPidButton.addEventListener('click', () => {
            this.addPidEntry();
        });

        // WiFi mode change handler
        document.getElementById('wifiMode').addEventListener('change', (e) => {
            this.toggleClientNetworkSettings(e.target.value === 'client');
        });

        // DHCP checkbox handler
        document.getElementById('useDHCP').addEventListener('change', (e) => {
            this.toggleStaticIPSettings(!e.target.checked);
        });

        // Bluetooth scan button
        document.getElementById('scanBluetoothButton').addEventListener('click', () => {
            this.scanBluetoothDevices();
        });

        // Bluetooth refresh button
        document.getElementById('refreshBluetoothButton').addEventListener('click', () => {
            this.scanBluetoothDevices();
        });

        // Bluetooth pair button
        document.getElementById('pairBluetoothButton').addEventListener('click', () => {
            this.pairBluetoothDevice();
        });

        // Bluetooth unpair button
        document.getElementById('unpairBluetoothButton').addEventListener('click', () => {
            this.unpairBluetoothDevice();
        });

        // Bluetooth device selection change
        document.getElementById('btDeviceSelect').addEventListener('change', (e) => {
            document.getElementById('pairBluetoothButton').disabled = !e.target.value;
        });

        // Initialize WiFi settings visibility
        this.toggleClientNetworkSettings(document.getElementById('wifiMode').value === 'client');

        this.renderAdditionalPids();
    }

    loadConfiguration() {
        // Load configuration from localStorage
        const saved = localStorage.getItem('openPonyLoggerConfig');
        if (saved) {
            try {
                const config = JSON.parse(saved);
                this.additionalPids = config.additionalPids || [];
                
                // Apply startup tab preference
                if (config.startupTab) {
                    localStorage.setItem('startupTab', config.startupTab);
                }
            } catch (e) {
                console.error('Failed to load configuration:', e);
            }
        }
    }

    applyStartupTab() {
        const startupTab = localStorage.getItem('startupTab') || 'about';
        
        // Deactivate all tabs
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        // Activate startup tab
        const tabButton = document.querySelector(`[data-tab="${startupTab}"]`);
        const tabContent = document.getElementById(startupTab);
        
        if (tabButton && tabContent) {
            tabButton.classList.add('active');
            tabContent.classList.add('active');
            this.onTabChange(startupTab);
        }
    }

    addPidEntry(pid = '', hz = '1') {
        const entry = {
            id: Date.now(),
            pid: pid,
            hz: hz
        };
        this.additionalPids.push(entry);
        this.renderAdditionalPids();
    }

    removePidEntry(id) {
        this.additionalPids = this.additionalPids.filter(p => p.id !== id);
        this.renderAdditionalPids();
    }

    renderAdditionalPids() {
        const container = document.getElementById('additionalPidsList');
        
        if (this.additionalPids.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 1rem;">No additional PIDs configured. Click "Add PID" to monitor custom parameters.</p>';
            return;
        }

        container.innerHTML = this.additionalPids.map(pid => `
            <div class="pid-entry" data-pid-id="${pid.id}">
                <div>
                    <label>PID (Hex)</label>
                    <input 
                        type="text" 
                        class="pid-hex" 
                        value="${pid.pid}" 
                        placeholder="e.g., 010C"
                        maxlength="4"
                        data-pid-id="${pid.id}">
                </div>
                <div style="grid-column: span 1;">
                    <label>Sample Rate</label>
                    <select class="pid-hz" data-pid-id="${pid.id}">
                        <option value="10" ${pid.hz === '10' ? 'selected' : ''}>10 Hz</option>
                        <option value="5" ${pid.hz === '5' ? 'selected' : ''}>5 Hz</option>
                        <option value="1" ${pid.hz === '1' ? 'selected' : ''}>1 Hz</option>
                        <option value="0.5" ${pid.hz === '0.5' ? 'selected' : ''}>0.5 Hz</option>
                        <option value="0.25" ${pid.hz === '0.25' ? 'selected' : ''}>0.25 Hz</option>
                        <option value="0.2" ${pid.hz === '0.2' ? 'selected' : ''}>0.2 Hz</option>
                        <option value="0.1" ${pid.hz === '0.1' ? 'selected' : ''}>0.1 Hz</option>
                    </select>
                </div>
                <button class="btn btn-danger btn-sm" onclick="app.removePidEntry(${pid.id})">Remove</button>
            </div>
        `).join('');

        // Add event listeners for input changes
        container.querySelectorAll('.pid-hex').forEach(input => {
            input.addEventListener('input', (e) => {
                const id = parseInt(e.target.dataset.pidId);
                const entry = this.additionalPids.find(p => p.id === id);
                if (entry) {
                    entry.pid = e.target.value.toUpperCase();
                }
            });
        });

        container.querySelectorAll('.pid-hz').forEach(select => {
            select.addEventListener('change', (e) => {
                const id = parseInt(e.target.dataset.pidId);
                const entry = this.additionalPids.find(p => p.id === id);
                if (entry) {
                    entry.hz = e.target.value;
                }
            });
        });
    }

    saveConfiguration() {
        // Collect all configuration values
        const config = {
            deviceName: document.getElementById('deviceName').value,
            timezone: document.getElementById('timezone').value,
            units: document.getElementById('units').value,
            sampleRate: document.getElementById('sampleRate').value,
            autoRecord: document.getElementById('autoRecord').checked,
            recordGPS: document.getElementById('recordGPS').checked,
            recordAccel: document.getElementById('recordAccel').checked,
            wifiMode: document.getElementById('wifiMode').value,
            wifiSSID: document.getElementById('wifiSSID').value,
            // Network settings for client mode
            useDHCP: document.getElementById('useDHCP').checked,
            staticIP: document.getElementById('staticIP').value,
            subnetMask: document.getElementById('subnetMask').value,
            gateway: document.getElementById('gateway').value,
            dnsServer: document.getElementById('dnsServer').value,
            obdProtocol: document.getElementById('obdProtocol').value,
            obdTimeout: document.getElementById('obdTimeout').value,
            startupTab: document.getElementById('startupTab').value,
            darkMode: document.getElementById('darkMode').checked,
            brightness: document.getElementById('brightness').value,
            additionalPids: this.additionalPids
        };

        // Save to localStorage
        localStorage.setItem('openPonyLoggerConfig', JSON.stringify(config));
        localStorage.setItem('startupTab', config.startupTab);

        console.log('Saving configuration:', config);
        alert('Configuration saved successfully!');
    }

    resetConfiguration() {
        document.getElementById('deviceName').value = 'OpenPonyLogger-01';
        document.getElementById('timezone').value = 'America/New_York';
        document.getElementById('units').value = 'imperial';
        document.getElementById('sampleRate').value = '100';
        document.getElementById('autoRecord').checked = true;
        document.getElementById('recordGPS').checked = true;
        document.getElementById('recordAccel').checked = true;
        document.getElementById('startupTab').value = 'about';
        document.getElementById('brightness').value = '80';
        document.getElementById('brightnessValue').textContent = '80%';
        this.additionalPids = [];
        this.renderAdditionalPids();
        localStorage.removeItem('openPonyLoggerConfig');
        localStorage.setItem('startupTab', 'about');
        alert('Configuration reset to defaults');
    }

    factoryReset() {
        this.sessions = [];
        this.resetConfiguration();
        this.renderSessions();
        localStorage.clear();
        alert('Factory reset complete');
    }

    // Status Updates
    updateStatus() {
        // System status
        document.getElementById('cpuTemp').textContent = (40 + Math.random() * 15).toFixed(1) + '°C';
        document.getElementById('memUsed').textContent = (50 + Math.random() * 30).toFixed(0) + '%';
        document.getElementById('uptime').textContent = '3h 42m';
        document.getElementById('wifiSignal').textContent = '-' + (40 + Math.random() * 20).toFixed(0) + ' dBm';

        // OBD-II status
        const obdConnected = Math.random() > 0.3;
        const obdStatus = document.getElementById('obdStatus');
        obdStatus.textContent = obdConnected ? 'Connected' : 'Disconnected';
        obdStatus.className = 'status-badge ' + (obdConnected ? 'connected' : 'disconnected');
        
        if (obdConnected) {
            document.getElementById('obdProtocol').textContent = 'CAN (ISO 15765-4)';
            document.getElementById('obdVin').textContent = '1ZVBP8AM5E5******';
            document.getElementById('obdDataRate').textContent = (80 + Math.random() * 20).toFixed(0) + ' Hz';
        }

        // GPS status
        const gpsConnected = Math.random() > 0.2;
        const gpsStatus = document.getElementById('gpsStatus');
        gpsStatus.textContent = gpsConnected ? '3D Fix' : 'No Fix';
        gpsStatus.className = 'status-badge ' + (gpsConnected ? 'connected' : 'disconnected');
        
        if (gpsConnected) {
            document.getElementById('gpsSats').textContent = (8 + Math.floor(Math.random() * 5)).toString();
            document.getElementById('gpsFixQuality').textContent = 'GPS + GLONASS';
            document.getElementById('gpsHdop').textContent = (0.8 + Math.random() * 0.5).toFixed(1);
        }

        // Storage
        const storagePercent = 35 + Math.random() * 5;
        document.getElementById('storageBar').style.width = storagePercent + '%';
    }

    updateConnectionStatus() {
        const statusDot = document.getElementById('connectionStatus');
        const statusText = document.getElementById('connectionText');
        
        // Simulate connection after 2 seconds
        setTimeout(() => {
            statusDot.classList.add('connected');
            statusText.textContent = 'Connected';
        }, 2000);
    }

    // Data Simulation
    startDataSimulation() {
        // Update gauges every 500ms
        setInterval(() => {
            if (document.querySelector('.tab-button.active').dataset.tab === 'gauges') {
                this.updateGauges();
            }
        }, 500);

        // Update G-force data every 100ms
        setInterval(() => {
            this.updateGForceData();
        }, 100);

        // Update GPS data every 1000ms
        setInterval(() => {
            this.updateGPSData();
        }, 1000);

        // Update status every 2000ms
        setInterval(() => {
            if (document.querySelector('.tab-button.active').dataset.tab === 'status') {
                this.updateStatus();
            }
        }, 2000);

        // Initial status update
        this.updateStatus();
    }

    // Fuel Log Management
    setupFuelLog() {
        // Initialize fuel log display
        this.renderFuelLog();
        this.updateFuelStats();

        // Add Fill-Up button
        document.getElementById('addFuelEntry').addEventListener('click', () => {
            this.showFuelEntryForm();
        });

        // Cancel button
        document.getElementById('cancelFuelEntry').addEventListener('click', () => {
            this.hideFuelEntryForm();
        });

        // Save button
        document.getElementById('saveFuelEntry').addEventListener('click', () => {
            this.saveFuelEntry();
        });

        // Export button
        document.getElementById('exportFuelLog').addEventListener('click', () => {
            this.exportFuelLog();
        });
    }

    loadFuelLog() {
        const stored = localStorage.getItem('openPonyLoggerFuelLog');
        return stored ? JSON.parse(stored) : [];
    }

    saveFuelLogToStorage() {
        localStorage.setItem('openPonyLoggerFuelLog', JSON.stringify(this.fuelLog));
    }

    showFuelEntryForm() {
        const form = document.getElementById('fuelEntryForm');
        form.style.display = 'block';
        
        // Set current date and time
        const now = new Date();
        document.getElementById('fuelDate').value = now.toISOString().split('T')[0];
        document.getElementById('fuelTime').value = now.toTimeString().slice(0, 5);
        
        // Clear other fields
        document.getElementById('fuelOdometer').value = '';
        document.getElementById('fuelGallons').value = '';
        document.getElementById('fuelPricePerGallon').value = '';
        document.getElementById('fuelLocation').value = '';
        document.getElementById('fuelNotes').value = '';
    }

    hideFuelEntryForm() {
        document.getElementById('fuelEntryForm').style.display = 'none';
    }

    saveFuelEntry() {
        const odometer = parseFloat(document.getElementById('fuelOdometer').value);
        const gallons = parseFloat(document.getElementById('fuelGallons').value);
        const pricePerGallon = parseFloat(document.getElementById('fuelPricePerGallon').value) || 0;
        const location = document.getElementById('fuelLocation').value;
        const notes = document.getElementById('fuelNotes').value;
        const date = document.getElementById('fuelDate').value;
        const time = document.getElementById('fuelTime').value;

        if (!odometer || !gallons) {
            alert('Please enter odometer reading and gallons added');
            return;
        }

        // Calculate MPG if previous entry exists
        let mpg = null;
        let milesDriven = null;
        if (this.fuelLog.length > 0) {
            const previousEntry = this.fuelLog[this.fuelLog.length - 1];
            milesDriven = odometer - previousEntry.odometer;
            if (milesDriven > 0) {
                mpg = milesDriven / gallons;
            }
        }

        const entry = {
            id: Date.now(),
            timestamp: `${date}T${time}`,
            odometer: odometer,
            gallons: gallons,
            pricePerGallon: pricePerGallon,
            totalCost: gallons * pricePerGallon,
            location: location,
            notes: notes,
            mpg: mpg,
            milesDriven: milesDriven
        };

        this.fuelLog.push(entry);
        this.saveFuelLogToStorage();
        this.renderFuelLog();
        this.updateFuelStats();
        this.hideFuelEntryForm();
    }

    deleteFuelEntry(id) {
        if (confirm('Delete this fuel entry? This cannot be undone.')) {
            this.fuelLog = this.fuelLog.filter(entry => entry.id !== id);
            this.saveFuelLogToStorage();
            this.renderFuelLog();
            this.updateFuelStats();
        }
    }

    renderFuelLog() {
        const container = document.getElementById('fuelLogList');
        
        if (this.fuelLog.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">No fuel entries yet. Click "Add Fill-Up" to start tracking.</p>';
            return;
        }

        // Sort by timestamp, newest first
        const sortedLog = [...this.fuelLog].sort((a, b) => 
            new Date(b.timestamp) - new Date(a.timestamp)
        );

        container.innerHTML = sortedLog.map(entry => {
            const date = new Date(entry.timestamp);
            const dateStr = date.toLocaleDateString();
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            return `
                <div class="fuel-entry-card">
                    <div class="fuel-entry-header">
                        <div>
                            <div class="fuel-entry-date">${dateStr} ${timeStr}</div>
                            ${entry.location ? `<div style="font-size: 0.9rem; color: var(--text-secondary);">${entry.location}</div>` : ''}
                        </div>
                        ${entry.mpg ? `<div class="fuel-entry-mpg">${entry.mpg.toFixed(1)} MPG</div>` : '<div style="color: var(--text-secondary);">First Entry</div>'}
                    </div>
                    <div class="fuel-entry-details">
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Odometer:</span>
                            <span class="fuel-detail-value">${entry.odometer.toFixed(1)} mi</span>
                        </div>
                        ${entry.milesDriven ? `
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Miles Driven:</span>
                            <span class="fuel-detail-value">${entry.milesDriven.toFixed(1)} mi</span>
                        </div>
                        ` : ''}
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Gallons:</span>
                            <span class="fuel-detail-value">${entry.gallons.toFixed(2)} gal</span>
                        </div>
                        ${entry.pricePerGallon > 0 ? `
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Price/Gal:</span>
                            <span class="fuel-detail-value">$${entry.pricePerGallon.toFixed(2)}</span>
                        </div>
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Total Cost:</span>
                            <span class="fuel-detail-value">$${entry.totalCost.toFixed(2)}</span>
                        </div>
                        ${entry.mpg ? `
                        <div class="fuel-detail-item">
                            <span class="fuel-detail-label">Cost/Mile:</span>
                            <span class="fuel-detail-value">$${(entry.totalCost / entry.milesDriven).toFixed(3)}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                    </div>
                    ${entry.notes ? `<div class="fuel-entry-notes">${entry.notes}</div>` : ''}
                    <div class="fuel-entry-actions">
                        <button class="btn btn-sm btn-danger" onclick="app.deleteFuelEntry(${entry.id})">Delete</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateFuelStats() {
        // Last fill-up
        if (this.fuelLog.length > 0) {
            const lastEntry = this.fuelLog[this.fuelLog.length - 1];
            document.getElementById('lastMpg').textContent = lastEntry.mpg ? `${lastEntry.mpg.toFixed(1)} MPG` : 'N/A';
            if (lastEntry.mpg && lastEntry.pricePerGallon > 0) {
                const costPerMile = lastEntry.totalCost / lastEntry.milesDriven;
                document.getElementById('lastCostPerMile').textContent = `$${costPerMile.toFixed(3)}`;
            } else {
                document.getElementById('lastCostPerMile').textContent = 'N/A';
            }
        } else {
            document.getElementById('lastMpg').textContent = '--';
            document.getElementById('lastCostPerMile').textContent = '--';
        }

        // Last 3 fills average
        const recentEntries = this.fuelLog.slice(-3).filter(e => e.mpg !== null);
        if (recentEntries.length > 0) {
            const avgMpg = recentEntries.reduce((sum, e) => sum + e.mpg, 0) / recentEntries.length;
            document.getElementById('avg3Mpg').textContent = `${avgMpg.toFixed(1)} MPG`;
            
            const entriesWithCost = recentEntries.filter(e => e.pricePerGallon > 0);
            if (entriesWithCost.length > 0) {
                const avgCost = entriesWithCost.reduce((sum, e) => sum + (e.totalCost / e.milesDriven), 0) / entriesWithCost.length;
                document.getElementById('avg3CostPerMile').textContent = `$${avgCost.toFixed(3)}`;
            } else {
                document.getElementById('avg3CostPerMile').textContent = 'N/A';
            }
        } else {
            document.getElementById('avg3Mpg').textContent = '--';
            document.getElementById('avg3CostPerMile').textContent = '--';
        }

        // Overall average
        const validEntries = this.fuelLog.filter(e => e.mpg !== null);
        if (validEntries.length > 0) {
            const totalMiles = validEntries.reduce((sum, e) => sum + e.milesDriven, 0);
            const totalGallons = validEntries.reduce((sum, e) => sum + e.gallons, 0);
            const totalCost = this.fuelLog.reduce((sum, e) => sum + e.totalCost, 0);
            
            document.getElementById('overallMpg').textContent = `${(totalMiles / totalGallons).toFixed(1)} MPG`;
            document.getElementById('totalMiles').textContent = `${totalMiles.toFixed(0)} mi`;
            document.getElementById('totalGallons').textContent = `${totalGallons.toFixed(1)} gal`;
            document.getElementById('totalCost').textContent = totalCost > 0 ? `$${totalCost.toFixed(2)}` : 'N/A';
        } else {
            document.getElementById('overallMpg').textContent = '--';
            document.getElementById('totalMiles').textContent = '--';
            document.getElementById('totalGallons').textContent = '--';
            document.getElementById('totalCost').textContent = '--';
        }
    }

    exportFuelLog() {
        if (this.fuelLog.length === 0) {
            alert('No fuel entries to export');
            return;
        }

        // Create CSV
        const headers = ['Date', 'Time', 'Odometer', 'Miles Driven', 'Gallons', 'MPG', 'Price/Gal', 'Total Cost', 'Cost/Mile', 'Location', 'Notes'];
        const rows = this.fuelLog.map(entry => {
            const date = new Date(entry.timestamp);
            return [
                date.toLocaleDateString(),
                date.toLocaleTimeString(),
                entry.odometer.toFixed(1),
                entry.milesDriven ? entry.milesDriven.toFixed(1) : '',
                entry.gallons.toFixed(2),
                entry.mpg ? entry.mpg.toFixed(2) : '',
                entry.pricePerGallon ? entry.pricePerGallon.toFixed(2) : '',
                entry.totalCost ? entry.totalCost.toFixed(2) : '',
                (entry.mpg && entry.pricePerGallon > 0) ? (entry.totalCost / entry.milesDriven).toFixed(3) : '',
                entry.location || '',
                entry.notes || ''
            ];
        });

        const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fuel-log-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // PID Testing
    setupPIDTesting() {
        document.getElementById('testAllPidsButton').addEventListener('click', () => {
            this.testAllPIDs();
        });

        document.getElementById('testCustomPidsButton').addEventListener('click', () => {
            this.testCustomPIDs();
        });
    }

    async testAllPIDs() {
        const resultsDiv = document.getElementById('pidTestResults');
        const progressDiv = document.getElementById('pidTestProgress');
        const outputDiv = document.getElementById('pidTestOutput');
        const summaryDiv = document.getElementById('pidTestSummary');

        resultsDiv.style.display = 'block';
        progressDiv.textContent = 'Testing PIDs...';
        outputDiv.innerHTML = '';
        summaryDiv.textContent = '';

        // Standard PIDs to test
        const standardPids = [
            { pid: '0C', name: 'Engine RPM' },
            { pid: '0D', name: 'Vehicle Speed' },
            { pid: '04', name: 'Engine Load' },
            { pid: '05', name: 'Coolant Temperature' },
            { pid: '0F', name: 'Intake Air Temperature' },
            { pid: '11', name: 'Throttle Position' },
            { pid: '2F', name: 'Fuel Level' },
            { pid: 'A6', name: 'Odometer' }
        ];

        let tested = 0;
        let supported = 0;
        const total = standardPids.length + this.additionalPids.length;

        // Test standard PIDs
        for (const pidInfo of standardPids) {
            const result = await this.testPID(pidInfo.pid);
            tested++;
            
            if (result.supported) {
                supported++;
                outputDiv.innerHTML += `<div class="pid-test-supported">✓ PID ${pidInfo.pid} (${pidInfo.name}): Supported - ${result.value}</div>`;
            } else {
                outputDiv.innerHTML += `<div class="pid-test-unsupported">✗ PID ${pidInfo.pid} (${pidInfo.name}): Not Supported</div>`;
            }
            
            progressDiv.textContent = `Testing... ${tested}/${total}`;
            await new Promise(resolve => setTimeout(resolve, 100)); // Small delay for readability
        }

        // Test custom PIDs
        for (const customPid of this.additionalPids) {
            const result = await this.testPID(customPid.pid);
            tested++;
            
            if (result.supported) {
                supported++;
                outputDiv.innerHTML += `<div class="pid-test-supported">✓ PID ${customPid.pid} (Custom): Supported - ${result.value}</div>`;
            } else {
                outputDiv.innerHTML += `<div class="pid-test-unsupported">✗ PID ${customPid.pid} (Custom): Not Supported</div>`;
            }
            
            progressDiv.textContent = `Testing... ${tested}/${total}`;
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        progressDiv.textContent = 'Test Complete!';
        summaryDiv.textContent = `Results: ${supported}/${total} PIDs supported (${((supported/total)*100).toFixed(0)}%)`;
    }

    async testCustomPIDs() {
        if (this.additionalPids.length === 0) {
            alert('No custom PIDs configured. Add custom PIDs in the Additional PIDs section below.');
            return;
        }

        const resultsDiv = document.getElementById('pidTestResults');
        const progressDiv = document.getElementById('pidTestProgress');
        const outputDiv = document.getElementById('pidTestOutput');
        const summaryDiv = document.getElementById('pidTestSummary');

        resultsDiv.style.display = 'block';
        progressDiv.textContent = 'Testing custom PIDs...';
        outputDiv.innerHTML = '';
        summaryDiv.textContent = '';

        let tested = 0;
        let supported = 0;

        for (const customPid of this.additionalPids) {
            const result = await this.testPID(customPid.pid);
            tested++;
            
            if (result.supported) {
                supported++;
                outputDiv.innerHTML += `<div class="pid-test-supported">✓ PID ${customPid.pid}: Supported - ${result.value}</div>`;
            } else {
                outputDiv.innerHTML += `<div class="pid-test-unsupported">✗ PID ${customPid.pid}: Not Supported</div>`;
            }
            
            progressDiv.textContent = `Testing... ${tested}/${this.additionalPids.length}`;
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        progressDiv.textContent = 'Test Complete!';
        summaryDiv.textContent = `Results: ${supported}/${tested} custom PIDs supported (${((supported/tested)*100).toFixed(0)}%)`;
    }

    async testPID(pid) {
        // Simulate PID testing (in real implementation, this would query OBD-II)
        // For demo purposes, randomly determine support
        await new Promise(resolve => setTimeout(resolve, 50)); // Simulate query delay
        
        // Mock: Standard PIDs are "supported", PID 2F and A6 are "not supported"
        const unsupportedPids = ['2F', 'A6'];
        const isSupported = !unsupportedPids.includes(pid.toUpperCase());
        
        let value = 'N/A';
        if (isSupported) {
            // Generate mock value based on PID
            switch(pid.toUpperCase()) {
                case '0C': value = '847 RPM'; break;
                case '0D': value = '0 km/h'; break;
                case '04': value = '23.5%'; break;
                case '05': value = '89°C'; break;
                case '0F': value = '24°C'; break;
                case '11': value = '14.5%'; break;
                default: value = '-- (mock data)';
            }
        }
        
        return { supported: isSupported, value: value };
    }

    // WiFi Network Configuration
    toggleClientNetworkSettings(show) {
        const clientSettings = document.getElementById('clientNetworkSettings');
        clientSettings.style.display = show ? 'block' : 'none';
    }

    toggleStaticIPSettings(show) {
        const staticSettings = document.getElementById('staticIPSettings');
        staticSettings.style.display = show ? 'block' : 'none';
    }

    // Bluetooth Device Management
    async scanBluetoothDevices() {
        const scanButton = document.getElementById('scanBluetoothButton');
        const scanButtonText = document.getElementById('btScanButtonText');
        const refreshButton = document.getElementById('refreshBluetoothButton');
        const deviceList = document.getElementById('bluetoothDeviceList');
        const deviceSelect = document.getElementById('btDeviceSelect');

        // Show scanning state
        scanButton.disabled = true;
        scanButtonText.textContent = 'Scanning...';

        // Simulate Bluetooth scan (in real implementation, this would use Bluetooth API)
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Mock devices (replace with real Bluetooth scan results)
        const mockDevices = [
            { id: 'bt:01', name: 'iPhone 13 Pro', rssi: -45 },
            { id: 'bt:02', name: 'Galaxy Buds', rssi: -65 },
            { id: 'bt:03', name: 'iPad Air', rssi: -70 },
            { id: 'bt:04', name: 'MacBook Pro', rssi: -55 },
            { id: 'bt:05', name: 'Pixel 7', rssi: -80 }
        ];

        // Sort by signal strength (RSSI)
        mockDevices.sort((a, b) => b.rssi - a.rssi);

        // Populate dropdown
        deviceSelect.innerHTML = mockDevices.map(device => 
            `<option value="${device.id}">${device.name} (${device.rssi} dBm)</option>`
        ).join('');

        // Show device list and refresh button
        deviceList.style.display = 'block';
        refreshButton.style.display = 'inline-block';

        // Reset scan button
        scanButton.disabled = false;
        scanButtonText.textContent = 'Scan for Devices';

        // Enable pair button if device selected
        document.getElementById('pairBluetoothButton').disabled = false;

        console.log(`Found ${mockDevices.length} Bluetooth devices`);
    }

    async pairBluetoothDevice() {
        const deviceSelect = document.getElementById('btDeviceSelect');
        const selectedId = deviceSelect.value;
        const selectedName = deviceSelect.options[deviceSelect.selectedIndex].text;

        if (!selectedId) {
            alert('Please select a device to pair');
            return;
        }

        const pairButton = document.getElementById('pairBluetoothButton');
        pairButton.disabled = true;
        pairButton.textContent = 'Pairing...';

        // Simulate pairing process
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Update paired device status
        const pairedStatus = document.getElementById('pairedDeviceStatus');
        const pairedDeviceName = document.getElementById('pairedDeviceName');
        const connectionStatus = document.getElementById('btConnectionStatus');
        const signalStrength = document.getElementById('btSignalStrength');

        pairedDeviceName.textContent = selectedName.split(' (')[0]; // Remove RSSI from display
        connectionStatus.textContent = 'Connected';
        connectionStatus.className = 'status-badge status-connected';
        signalStrength.textContent = selectedName.match(/\(.*\)/)[0]; // Extract RSSI

        pairedStatus.style.display = 'block';

        // Show unpair button, hide pair button
        pairButton.style.display = 'none';
        document.getElementById('unpairBluetoothButton').style.display = 'inline-block';

        // Save to localStorage
        localStorage.setItem('pairedBluetoothDevice', JSON.stringify({
            id: selectedId,
            name: selectedName.split(' (')[0]
        }));

        alert(`Successfully paired with ${selectedName.split(' (')[0]}`);
    }

    unpairBluetoothDevice() {
        if (!confirm('Unpair this Bluetooth device?')) {
            return;
        }

        // Hide paired status
        document.getElementById('pairedDeviceStatus').style.display = 'none';

        // Show pair button, hide unpair button
        document.getElementById('pairBluetoothButton').style.display = 'inline-block';
        document.getElementById('unpairBluetoothButton').style.display = 'none';
        document.getElementById('pairBluetoothButton').textContent = 'Pair Device';

        // Clear from localStorage
        localStorage.removeItem('pairedBluetoothDevice');

        alert('Device unpaired successfully');
    }
}



// Initialize the application
let app;
document.addEventListener('DOMContentLoaded', () => {
    // Check if gauge library is already loaded
    if (window.gaugeLibraryLoaded && typeof RadialGauge !== 'undefined') {
        console.log('Initializing OpenPonyLogger...');
        app = new OpenPonyLogger();
    } else {
        // Wait for gauge library to load
        console.log('Waiting for gauge library to load...');
        window.addEventListener('gaugeLibraryReady', () => {
            console.log('Initializing OpenPonyLogger...');
            app = new OpenPonyLogger();
        });
        
        // Fallback: If library doesn't load within 5 seconds, show error
        setTimeout(() => {
            if (!window.gaugeLibraryLoaded) {
                console.error('❌ Gauge library failed to load!');
                console.error('Download gauge.min.js from:');
                console.error('https://github.com/Mikhus/canvas-gauges/releases/download/v2.1.7/gauge.min.js');
                
                // Show error message to user
                document.body.innerHTML = `
                    <div style="padding: 2rem; max-width: 800px; margin: 0 auto; font-family: sans-serif;">
                        <h1 style="color: #f44336;">⚠️ Gauge Library Not Found</h1>
                        <p style="font-size: 1.1rem; line-height: 1.6;">
                            OpenPonyLogger requires the <strong>canvas-gauges</strong> library to display instruments.
                        </p>
                        <h2>Quick Fix:</h2>
                        <ol style="font-size: 1.1rem; line-height: 1.8;">
                            <li>Download <code>gauge.min.js</code> from:<br>
                                <a href="https://github.com/Mikhus/canvas-gauges/releases/download/v2.1.7/gauge.min.js" 
                                   style="color: #2196f3;">
                                    https://github.com/Mikhus/canvas-gauges/releases/download/v2.1.7/gauge.min.js
                                </a>
                            </li>
                            <li>Place it in the same directory as <code>index.html</code></li>
                            <li>Refresh this page (Ctrl+F5)</li>
                        </ol>
                        <h2>Or Use Helper Script:</h2>
                        <pre style="background: #1a1a1a; color: #4caf50; padding: 1rem; border-radius: 4px;">
# Linux/Mac
./download-gauge-library.sh

# Windows
download-gauge-library.bat</pre>
                        <p style="margin-top: 2rem; padding: 1rem; background: #fff3cd; border-left: 4px solid #ffc107;">
                            <strong>Note:</strong> This is required for offline operation at the track!
                            See <code>OFFLINE_SETUP.md</code> for details.
                        </p>
                    </div>
                `;
            }
        }, 5000);
    }
});
