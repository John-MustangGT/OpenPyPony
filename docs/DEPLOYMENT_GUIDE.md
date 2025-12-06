# CircuitPython Deployment System

## Overview

The deployment system automates the complete workflow from git checkout to running code on your Pico 2W:

1. ✅ **Auto-detect** CIRCUITPY drive
2. ✅ **Compress** web assets (gzip)
3. ✅ **Copy** all files to Pico
4. ✅ **Validate** installation
5. ✅ **Optional** library management via circup

---

## Quick Start

### One-Command Deployment

```bash
# From OpenPonyLogger repository root
make deploy
```

That's it! The system will:
- Find your Pico automatically
- Compress web assets
- Copy everything to the right place
- Validate the installation

---

## Installation

### Prerequisites

```bash
# Python 3.7+
python3 --version

# Optional: circup for library management
pip install circup
# or
brew install circup  # macOS
```

### Setup

```bash
# Clone repository (if you haven't already)
git clone https://github.com/john-mustanggt/OpenPonyLogger.git
cd OpenPonyLogger

# Make scripts executable
chmod +x deploy_to_pico.py
```

---

## Usage

### Using Make (Recommended)

```bash
# Show help
make help

# Deploy to Pico (auto-detect)
make deploy

# Clean install (removes old files first)
make clean-deploy

# Deploy just web assets
make web

# Install CircuitPython libraries
make install-deps

# Check if Pico is connected
make check

# Backup current deployment
make backup

# Validate deployment
make validate

# Connect to serial console
make serial
```

### Using Python Script Directly

```bash
# Auto-detect and deploy
python3 deploy_to_pico.py

# Specify drive manually
python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY

# Clean install
python3 deploy_to_pico.py --clean

# Skip web compression
python3 deploy_to_pico.py --no-web

# Don't backup existing files
python3 deploy_to_pico.py --no-backup

# Install libraries
python3 deploy_to_pico.py --install-deps

# Show help
python3 deploy_to_pico.py --help
```

---

## How It Works

### Deployment Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. Auto-Detect CIRCUITPY Drive                         │
│    ├── macOS:   /Volumes/CIRCUITPY                     │
│    ├── Linux:   /media/CIRCUITPY                       │
│    └── Windows: D:/CIRCUITPY (tries all drives)        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Compress Web Assets                                  │
│    ├── web/index.html  → web/index.html.gz  (80%)     │
│    ├── web/styles.css  → web/styles.css.gz  (80%)     │
│    ├── web/app.js      → web/app.js.gz      (72%)     │
│    └── Generate asset_map.py                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Copy Files to Pico                                   │
│    ├── code.py                                          │
│    ├── web_server_gz.py                                │
│    ├── web/                                             │
│    │   ├── asset_map.py                                │
│    │   ├── index.html.gz                               │
│    │   ├── styles.css.gz                               │
│    │   └── app.js.gz                                   │
│    └── settings.toml (if exists)                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Validate Deployment                                  │
│    ✓ Check all required files present                  │
│    ✓ Verify file sizes                                 │
│    ✓ Report missing files                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Optional: Install Libraries (circup)                │
│    └── Auto-installs required CircuitPython libs       │
└─────────────────────────────────────────────────────────┘
```

### What Gets Deployed

```
CIRCUITPY:/
├── code.py                    ← Main program
├── web_server_gz.py           ← Web server module
├── settings.toml              ← Configuration (optional)
│
├── web/                       ← Web assets
│   ├── asset_map.py           ← Asset metadata
│   ├── index.html.gz          ← Compressed HTML (5 KB)
│   ├── index.html             ← Fallback (25 KB, optional)
│   ├── styles.css.gz          ← Compressed CSS (3 KB)
│   ├── styles.css             ← Fallback (15 KB, optional)
│   ├── app.js.gz              ← Compressed JS (10 KB)
│   └── app.js                 ← Fallback (35 KB, optional)
│
└── lib/                       ← CircuitPython libraries
    └── (installed by circup)
```

---

## Features

### Auto-Detection

The system automatically finds your Pico across platforms:

**macOS:**
- `/Volumes/CIRCUITPY`
- `/Volumes/PICO`

**Linux:**
- `/media/CIRCUITPY`
- `/media/$USER/CIRCUITPY`
- `/run/media/$USER/CIRCUITPY`
- `/mnt/CIRCUITPY`

**Windows:**
- Scans all drive letters (D: through Z:)
- Looks for `boot_out.txt` to verify

### Compression Pipeline

```bash
# Automatic during deployment
web/index.html (25 KB) → web/index.html.gz (5 KB)  # 80% savings
web/styles.css (15 KB) → web/styles.css.gz (3 KB)  # 80% savings
web/app.js     (35 KB) → web/app.js.gz     (10 KB) # 72% savings

Total: 76 KB → 18 KB (76% reduction)
```

### File Backup

When deploying, existing files are automatically backed up:

```
CIRCUITPY:/
├── code.py
├── code.py.backup          ← Previous version
├── web_server_gz.py
└── web_server_gz.py.backup ← Previous version
```

Disable with `--no-backup` flag.

### Validation

Checks for required files and reports:

```
✓ code.py (5,234 bytes)
✓ web_server_gz.py (9,124 bytes)
✓ web/asset_map.py (515 bytes)
✓ web/index.html.gz (5,023 bytes)
✓ web/styles.css.gz (3,156 bytes)
✓ web/app.js.gz (9,847 bytes)

All required files present!
```

---

## CircuitPython Library Management

### Using circup

[circup](https://github.com/adafruit/circup) is the official CircuitPython library manager.

**Install:**
```bash
pip install circup
# or
brew install circup  # macOS
```

**Usage with deployment system:**
```bash
# Install/update all required libraries
make install-deps

# Or directly
circup install --path /Volumes/CIRCUITPY
```

**Manual library management:**
```bash
# List installed libraries
circup list

# Install specific library
circup install adafruit_requests

# Update all libraries
circup update

# Show outdated libraries
circup show
```

### Required Libraries (Auto-Installed)

The deployment system will install these automatically with `make install-deps`:

- `adafruit_requests` - HTTP requests (if using external APIs)
- `adafruit_ntp` - Time sync via NTP (optional)

**Note:** CircuitPython includes built-in modules for:
- `wifi` - WiFi connectivity ✓
- `socketpool` - TCP/IP sockets ✓
- `ssl` - SSL/TLS support ✓

---

## Development Workflow

### Typical Day-to-Day

```bash
# 1. Edit code
vim code.py

# 2. Edit web interface
vim web/app.js

# 3. Deploy (one command!)
make deploy

# 4. Test
# Browse to http://192.168.4.1

# 5. Check serial output (if needed)
make serial
```

### Rapid Iteration

```bash
# Watch for changes and auto-deploy (requires fswatch)
make watch

# Or manually after each change
make deploy
```

### Testing Changes

```bash
# Deploy to test
make deploy

# Check serial console for errors
make serial

# If issues, restore backup
cp /Volumes/CIRCUITPY/code.py.backup /Volumes/CIRCUITPY/code.py
```

---

## Troubleshooting

### Pico Not Detected

**Problem:** `Could not find CIRCUITPY drive`

**Solutions:**
```bash
# 1. Check Pico is mounted
ls /Volumes/CIRCUITPY  # macOS
ls /media/CIRCUITPY    # Linux

# 2. Specify drive manually
make deploy DRIVE=/Volumes/CIRCUITPY

# 3. Check boot_out.txt exists
cat /Volumes/CIRCUITPY/boot_out.txt
```

### Compression Fails

**Problem:** `Web asset compression failed`

**Solutions:**
```bash
# 1. Check web/ directory exists
ls web/

# 2. Check files present
ls web/index.html web/styles.css web/app.js

# 3. Run compression manually
python3 prepare_web_assets_cp.py web/ test_output/

# 4. Check Python version
python3 --version  # Need 3.7+
```

### Deployment Fails

**Problem:** `Failed to copy files`

**Solutions:**
```bash
# 1. Check drive is writable
touch /Volumes/CIRCUITPY/test.txt

# 2. Check disk space
df -h /Volumes/CIRCUITPY

# 3. Safely eject and remount
# (Unplug and replug Pico)

# 4. Try clean deployment
make clean-deploy
```

### Serial Console Issues

**Problem:** `No serial port found`

**Solutions:**
```bash
# macOS
ls /dev/tty.usbmodem*

# Linux
ls /dev/ttyACM*

# Connect manually
screen /dev/tty.usbmodem14201 115200  # Use your port
```

---

## Platform-Specific Notes

### macOS

```bash
# Drive typically at
/Volumes/CIRCUITPY

# Serial port typically at
/dev/tty.usbmodem*

# Use screen for serial
screen /dev/tty.usbmodem14201 115200
```

### Linux

```bash
# Drive typically at
/media/CIRCUITPY
/media/$USER/CIRCUITPY

# Serial port typically at
/dev/ttyACM0

# May need permissions
sudo usermod -a -G dialout $USER
# (Log out and back in)

# Use screen for serial
screen /dev/ttyACM0 115200
```

### Windows

```bash
# Drive typically at
D:\CIRCUITPY
E:\CIRCUITPY
# (varies by system)

# Use PuTTY for serial
# COM port in Device Manager

# Or Git Bash + script
python3 deploy_to_pico.py
```

---

## Advanced Usage

### Custom Drive Location

```bash
# Specify drive explicitly
make deploy DRIVE=/custom/path/CIRCUITPY
```

### Partial Deployments

```bash
# Only web assets
make web

# Only Python files (manual)
cp code.py /Volumes/CIRCUITPY/
cp web_server_gz.py /Volumes/CIRCUITPY/
```

### Backup Management

```bash
# Create backup
make backup

# List backups
ls -la backups/

# Restore from backup
cp -r backups/backup_20250102_143027/* /Volumes/CIRCUITPY/
```

### Compression Statistics

```bash
# Show detailed compression stats
make stats

# Output:
# web_compressed/index.html.gz: 5.0K
# web_compressed/styles.css.gz: 3.1K
# web_compressed/app.js.gz: 9.8K
```

---

## Integration with Git

### Recommended .gitignore

```gitignore
# Compiled files
*.pyc
__pycache__/

# Compressed assets (regenerated)
web_compressed/

# Backups
backups/

# Test outputs
test_output.h
test_cp_output/

# OS files
.DS_Store
Thumbs.db
```

### Pre-Commit Hook (Optional)

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Validate Python syntax
python3 -m py_compile code.py web_server_gz.py

# Run tests
python3 -m pytest tests/

# Compress web assets as a check
python3 prepare_web_assets_cp.py web/ /tmp/test_compress/
```

---

## Comparison with Other Tools

### vs Manual Copy-Paste

| Feature | Manual | This System |
|---------|--------|-------------|
| Speed | Slow | Fast (1 command) |
| Compression | Manual | Automatic |
| Validation | None | Built-in |
| Backup | Manual | Automatic |
| Cross-platform | Varies | Consistent |

### vs circup alone

| Feature | circup | This System |
|---------|--------|-------------|
| Library management | ✓ | ✓ (integrated) |
| App deployment | ✗ | ✓ |
| Web compression | ✗ | ✓ |
| Validation | ✗ | ✓ |
| Auto-detection | ✗ | ✓ |

### vs Separate Scripts

| Feature | Separate | This System |
|---------|----------|-------------|
| Single command | ✗ | ✓ |
| Consistent | ✗ | ✓ |
| Documented | Varies | ✓ |
| Maintained | Varies | ✓ |

---

## Best Practices

### Before Deployment

1. ✅ **Test locally** - Run code in REPL if possible
2. ✅ **Check syntax** - `python3 -m py_compile code.py`
3. ✅ **Commit changes** - `git commit -m "Update"`
4. ✅ **Backup current** - `make backup`

### During Development

1. ✅ **Use serial console** - `make serial` for debugging
2. ✅ **Deploy incrementally** - Test after each major change
3. ✅ **Keep backups** - Multiple versions for rollback
4. ✅ **Validate often** - `make validate` after deployment

### For Production

1. ✅ **Clean deployment** - `make clean-deploy`
2. ✅ **Full validation** - Check all features
3. ✅ **Document version** - Tag in git
4. ✅ **Test thoroughly** - All use cases

---

## Next Steps

1. **Try it out:**
   ```bash
   make deploy
   ```

2. **Verify in browser:**
   - http://192.168.4.1
   - F12 → Network → Check `Content-Encoding: gzip`

3. **Check serial output:**
   ```bash
   make serial
   ```

4. **Customize workflow:**
   - Edit `Makefile` for your needs
   - Add custom targets
   - Integrate with CI/CD

---

## Summary

**You now have a professional deployment system that:**

✅ **Automates** compression, copying, validation  
✅ **Works** cross-platform (macOS/Linux/Windows)  
✅ **Integrates** with circup for library management  
✅ **Validates** deployments automatically  
✅ **Backs up** existing files  
✅ **Simple** - one command to deploy  

**Result: Git → Pico in seconds!** 🚀
