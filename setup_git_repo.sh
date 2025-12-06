#!/bin/bash
# setup_git_repo.sh - Initialize OpenPonyLogger Git repository
#
# This script sets up the proper Git repository structure and
# creates example files.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if we're in a git repo
if [ -d .git ]; then
    print_warning "This is already a git repository!"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

print_header "Setting up OpenPonyLogger Git Repository"

# Create directory structure
print_success "Creating directory structure..."

mkdir -p circuitpython/lib
mkdir -p circuitpython/local
mkdir -p src
mkdir -p web
mkdir -p tools
mkdir -p docs/images/{hardware,screenshots,diagrams}
mkdir -p hardware/{enclosure,schematics,datasheets}
mkdir -p tests/fixtures
mkdir -p scripts
mkdir -p examples/{basic_telemetry,custom_pids,fuel_logging}

# Create .gitignore if it doesn't exist
if [ ! -f .gitignore ]; then
    print_success "Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Compiled Python files
*.pyc
*.pyo
*.mpy
__pycache__/

# Build artifacts
build/
dist/
*.uf2
*.elf
*.o

# Generated web assets
web_compressed/
*.gz
src/web_assets.h

# Third-party CircuitPython libraries (installed by circup)
circuitpython/lib/
!circuitpython/lib/README.md

# Note: Your custom libraries go in circuitpython/local/ (committed)

# User configuration
settings.toml
secrets.py

# Backups
backups/
*.backup

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Test outputs
.pytest_cache/
test_output/
EOF
else
    print_warning ".gitignore already exists, skipping..."
fi

# Create .gitattributes
if [ ! -f .gitattributes ]; then
    print_success "Creating .gitattributes..."
    cat > .gitattributes << 'EOF'
* text=auto

*.py text eol=lf
*.c text eol=lf
*.h text eol=lf
*.html text eol=lf
*.css text eol=lf
*.js text eol=lf
*.md text eol=lf
*.sh text eol=lf

*.png binary
*.jpg binary
*.stl binary
*.pdf binary
EOF
else
    print_warning ".gitattributes already exists, skipping..."
fi

# Create settings.toml.example
if [ ! -f circuitpython/settings.toml.example ]; then
    print_success "Creating settings.toml.example..."
    cat > circuitpython/settings.toml.example << 'EOF'
# OpenPonyLogger Configuration Example
# Copy this file to settings.toml and customize

# WiFi Settings
WIFI_SSID = "YourNetworkName"
WIFI_PASSWORD = "YourPassword"

# Device Settings
DEVICE_NAME = "OpenPonyLogger-01"
TIMEZONE = "America/New_York"

# Logging Settings
AUTO_RECORD = true
SAMPLE_RATE_HZ = 100

# Web Interface
WEB_PORT = 80
EOF
fi

# Create CircuitPython requirements.txt
if [ ! -f circuitpython/requirements.txt ]; then
    print_success "Creating circuitpython/requirements.txt..."
    cat > circuitpython/requirements.txt << 'EOF'
# CircuitPython Library Requirements
# Install with: circup install -r requirements.txt

# Core libraries (usually included in CircuitPython)
# - wifi
# - socketpool
# - ssl

# Optional libraries (install if needed)
# adafruit_requests
# adafruit_ntp
EOF
fi

# Create tools/requirements.txt
if [ ! -f tools/requirements.txt ]; then
    print_success "Creating tools/requirements.txt..."
    cat > tools/requirements.txt << 'EOF'
# Development Tools Requirements
# Install with: pip install -r requirements.txt

# CircuitPython tools
circup>=1.5.0
mpy-cross>=1.19.0

# Testing
pytest>=7.0.0
pytest-cov>=4.0.0

# Code quality
black>=23.0.0
flake8>=6.0.0
EOF
fi

# Create README files
if [ ! -f README.md ]; then
    print_success "Creating README.md..."
    cat > README.md << 'EOF'
# OpenPonyLogger 🐎

Open-source automotive telemetry system for track day data logging.

## Quick Start

```bash
# Install dependencies
pip install circup mpy-cross

# Deploy to Pico
make deploy-mpy
```

See [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md) for complete instructions.

## Documentation

- [Build Guide](docs/BUILD_GUIDE.md)
- [User Guide](docs/USER_GUIDE.md)  
- [Deployment Tools](tools/README.md)

## License

MIT License - See [LICENSE](LICENSE)
EOF
fi

# Create lib/README.md
if [ ! -f lib/README.md ]; then
    print_success "Creating lib/README.md..."
    cat > lib/README.md << 'EOF'
# External Libraries

This directory contains external libraries (git submodules).

## C/C++ Libraries

- FatFS: SD card filesystem support

## Installation

```bash
git submodule update --init --recursive
```
EOF
fi

# Create circuitpython/lib/README.md
if [ ! -f circuitpython/lib/README.md ]; then
    print_success "Creating circuitpython/lib/README.md..."
    cat > circuitpython/lib/README.md << 'EOF'
# Third-Party CircuitPython Libraries

This directory contains libraries installed by `circup`.

## Installation

Install all required libraries:
```bash
circup install -r ../requirements.txt
```

Or install individually:
```bash
circup install adafruit_requests
circup install adafruit_lis3dh
```

## Important

⚠️ This directory is **git-ignored** because libraries are installed
automatically by `circup`.

**For your custom libraries, use `../local/` instead.**

## Updating Libraries

```bash
# Update all libraries
circup update

# Update specific library
circup update adafruit_requests
```
EOF
fi

# Create circuitpython/local/README.md
if [ ! -f circuitpython/local/README.md ]; then
    print_success "Creating circuitpython/local/README.md..."
    cat > circuitpython/local/README.md << 'EOF'
# Custom Local Libraries

This directory contains **your custom CircuitPython libraries**.

Unlike `../lib/` (which is git-ignored), files here **are committed to git**.

## Usage

```python
# In code.py
from local import telemetry
from local import gps_parser
from local.obd_helper import OBD
```

## Organization

Create logical modules:
- `telemetry.py` - Data collection
- `gps_parser.py` - GPS parsing
- `obd_helper.py` - OBD-II utilities
- `display.py` - OLED display logic

## Why Separate from lib/?

✅ Clear separation: yours vs third-party  
✅ Git-friendly: no risk of ignoring your code  
✅ Standard practice: common in Python projects
EOF
fi

# Create docs/README.md
if [ ! -f docs/README.md ]; then
    print_success "Creating docs/README.md..."
    cat > docs/README.md << 'EOF'
# OpenPonyLogger Documentation

## Contents

- [BUILD_GUIDE.md](BUILD_GUIDE.md) - Hardware assembly
- [USER_GUIDE.md](USER_GUIDE.md) - End-user manual
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [API.md](API.md) - API documentation

## Images

- `images/hardware/` - Hardware photos
- `images/screenshots/` - UI screenshots
- `images/diagrams/` - Architecture diagrams
EOF
fi

# Initialize git if needed
if [ ! -d .git ]; then
    print_success "Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: OpenPonyLogger repository structure"
else
    print_warning "Git already initialized, skipping..."
fi

print_header "Setup Complete!"

echo "Repository structure created:"
echo ""
echo "  circuitpython/       CircuitPython source"
echo "  src/                 C/C++ source (future)"
echo "  web/                 Web interface source"
echo "  tools/               Deployment tools"
echo "  docs/                Documentation"
echo "  hardware/            Hardware files"
echo "  tests/               Test suite"
echo "  examples/            Example code"
echo ""
echo "Next steps:"
echo ""
echo "  1. Review and customize settings.toml.example"
echo "  2. Add your code to circuitpython/"
echo "  3. Add web files to web/"
echo "  4. Install tools: pip install -r tools/requirements.txt"
echo "  5. Deploy: make deploy-mpy"
echo ""
echo "Don't forget to:"
echo "  - Update README.md with your project details"
echo "  - Add LICENSE file (MIT recommended)"
echo "  - Create remote repository and push:"
echo "      git remote add origin <your-repo-url>"
echo "      git push -u origin main"
echo ""
