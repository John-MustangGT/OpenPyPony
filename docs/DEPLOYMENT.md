# Deployment Guide - TOML-Based System

## Overview

The new deployment system uses `deploy.toml` for configuration-driven deployments. This replaces the old command-line argument approach with a declarative configuration file.

## Quick Start

### 1. Install Dependencies

```bash
pip install toml circup mpy-cross
```

Or use the Makefile:
```bash
make install-tools
```

### 2. Configure Deployment

Edit `deploy.toml` to specify what files to deploy:

```toml
[files.core]
source_dir = "refactored_core"
files = ["code.py", "config.py", "hardware.py", ...]
destination = "/"

[options]
backup = true
use_mpy = false
warn_orphans = true
```

### 3. Deploy

```bash
# Auto-detect drive and deploy
python3 deploy_to_pico.py

# Or use Makefile
make deploy
```

## Configuration File (deploy.toml)

### Targets Section
```toml
[targets]
auto_detect = true  # Auto-find CIRCUITPY drive

# Manual mount points (OS-specific)
# macos = "/Volumes/CIRCUITPY"
# linux = "/media/CIRCUITPY"
# windows = "D:/CIRCUITPY"
```

### File Groups

Define what files to deploy:

```toml
[files.core]
source_dir = "refactored_core"
files = ["code.py", "config.py", ...]
destination = "/"
optional = false

[files.web]
source_dir = "web"
files = ["index.html.gz", "styles.css.gz", ...]
destination = "/web"
optional = true

[files.lib]
source_dir = "lib"
destination = "/lib"
copy_tree = true  # Copy entire directory
```

**File Group Options:**
- `source_dir` - Source directory (relative to repo root)
- `files` - List of files to copy
- `destination` - Destination on Pico (`/` = root)
- `optional` - Don't fail if files missing
- `copy_tree` - Copy entire directory structure

### Deployment Options

```toml
[options]
backup = true                  # Create backup before deploy
verify = true                  # Verify after copying
use_mpy = false                # Compile to .mpy bytecode
warn_orphans = true            # Warn about extra files on Pico
delete_orphans = false         # Auto-delete orphans (dangerous!)

exclude = [                    # Files to never copy
    "*.pyc",
    "__pycache__",
    ".DS_Store",
]
```

### Validation

```toml
[validation]
required = [                   # Must exist after deployment
    "code.py",
    "config.py",
    "settings.toml",
]

required_libs = [              # Must exist in lib/
    "adafruit_lis3dh.mpy",
    "adafruit_gps.mpy",
]

min_free_space = 1048576       # Warn if <1MB free
```

### CircuitPython Libraries

```toml
[circup]
enabled = true

requirements = [               # Auto-install with circup
    "adafruit_lis3dh",
    "adafruit_gps",
    "adafruit_pcf8523",
]
```

### Platform-Specific Settings

```toml
[platform.macos]
mount_points = ["/Volumes/CIRCUITPY", "/Volumes/PICO"]
serial_pattern = "/dev/tty.usbmodem*"

[platform.linux]
mount_points = ["/media/CIRCUITPY", "/media/$USER/CIRCUITPY"]
serial_pattern = "/dev/ttyACM*"

[platform.windows]
mount_points = ["D:/CIRCUITPY", "E:/CIRCUITPY"]
serial_pattern = "COM*"
```

## Usage

### Command Line

```bash
# Basic deployment
python3 deploy_to_pico.py

# Specify config file
python3 deploy_to_pico.py --config custom.toml

# Manual drive path
python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY

# Compile to .mpy (faster boot, less RAM)
python3 deploy_to_pico.py --mpy

# Clean orphaned files
python3 deploy_to_pico.py --clean

# Skip backup
python3 deploy_to_pico.py --no-backup
```

### Makefile Targets

```bash
# Deploy with defaults
make deploy

# Deploy with .mpy compilation
make deploy-mpy

# Deploy and clean orphans
make clean-deploy

# Manual drive override
make deploy DRIVE=/Volumes/CIRCUITPY

# Custom config
make deploy CONFIG=custom.toml

# Validate existing deployment
make validate

# Create backup only
make backup

# Install CircuitPython libraries
make install-deps

# Check for drive
make check

# Connect to serial console
make serial
```

## Features

### ✅ Auto-Detection

Automatically finds CIRCUITPY drive on:
- macOS: `/Volumes/CIRCUITPY`
- Linux: `/media/CIRCUITPY`, `/media/$USER/CIRCUITPY`, etc.
- Windows: `D:`, `E:`, `F:`, etc.

### ✅ Backup Creation

Automatic backups before deployment:
```
backups/
  backup_20241227_143022/
  backup_20241227_145533/
```

### ✅ Orphan Detection

Warns about files on Pico that aren't in deployment config:

```
⚠ Found 3 orphaned file(s) on drive:
  - old_code.py
  - test.txt
  - unused_lib.mpy

To auto-delete orphans, use --clean flag
```

### ✅ .mpy Compilation

Optional bytecode compilation for:
- Faster imports
- Lower RAM usage
- Smaller file size

```bash
python3 deploy_to_pico.py --mpy
```

Before:
```
code.py: 12,456 bytes
```

After:
```
code.mpy: 8,234 bytes (33.9% savings)
```

### ✅ Validation

Checks after deployment:
- Required files exist
- Required libraries present
- Minimum free space available

### ✅ Platform Detection

Automatically adapts to:
- macOS (Darwin)
- Linux
- Windows

## Comparison: Old vs New

### Old System (Command-Line Args)

```bash
python3 deploy_to_pico.py \
  --drive /Volumes/CIRCUITPY \
  --clean \
  --no-web \
  --install-deps \
  --mpy
```

**Problems:**
- Long command lines
- Hard to replicate deploys
- No record of what was deployed
- Difficult to customize per-project

### New System (TOML Config)

```bash
python3 deploy_to_pico.py
```

**Benefits:**
- ✅ Configuration as code
- ✅ Repeatable deployments
- ✅ Version controlled
- ✅ Self-documenting
- ✅ Easy to customize

## Troubleshooting

### Drive Not Found

```
✗ Could not auto-detect CIRCUITPY drive!
```

**Solution:**
1. Check Pico is plugged in
2. Verify CIRCUITPY appears in file manager
3. Manually specify: `--drive /path/to/CIRCUITPY`
4. Update mount points in `deploy.toml`

### Missing Files

```
✗ Required file not found: refactored_core/code.py
```

**Solution:**
1. Check `source_dir` is correct
2. Verify file exists: `ls refactored_core/code.py`
3. Make optional: `optional = true` in `deploy.toml`

### Compilation Failed

```
✗ Compilation failed for sensors.py
```

**Solution:**
1. Check `mpy-cross` is installed: `pip install mpy-cross`
2. Verify Python syntax is valid
3. Deploy .py instead: omit `--mpy` flag

### Low Free Space

```
⚠ Low free space: 512,000 bytes (min: 1,048,576)
```

**Solution:**
1. Delete old session files on SD card
2. Remove unused libraries
3. Use `--clean` to delete orphans
4. Lower `min_free_space` in `deploy.toml`

## Advanced Usage

### Multiple Configurations

Create config variants:

```bash
# deploy-dev.toml (more verbose, skip optimizations)
[options]
use_mpy = false
warn_orphans = true

# deploy-production.toml (optimized)
[options]
use_mpy = true
delete_orphans = true
```

Deploy:
```bash
make deploy CONFIG=deploy-dev.toml
make deploy CONFIG=deploy-production.toml
```

### Custom Exclusions

Exclude test files, docs, etc:

```toml
[options]
exclude = [
    "*.pyc",
    "__pycache__",
    "test_*.py",
    "*.md",
    ".git",
    "*.example",
]
```

### Pre/Post Actions

Run scripts before/after deployment:

```toml
[actions]
pre_deploy = [
    "python3 tools/compress_web.py",
    "python3 tools/generate_version.py",
]

post_deploy = [
    "python3 tools/verify_deployment.py",
]
```

## Best Practices

1. **Version Control** - Commit `deploy.toml` to git
2. **Test Deploys** - Use `--no-backup` for quick iteration
3. **Production Deploys** - Always keep backups enabled
4. **Orphan Management** - Review orphans before `--clean`
5. **Library Updates** - Run `make install-deps` periodically
6. **Validation** - Always check `make validate` after deploy

## Migration from Old System

If you have an existing deployment:

1. Create `deploy.toml` from example
2. List current files: `ls /Volumes/CIRCUITPY`
3. Add files to appropriate `[files.*]` sections
4. Test: `python3 deploy_to_pico.py --no-backup`
5. Verify: `make validate`
6. Deploy for real: `make deploy`

## See Also

- `deploy.toml` - Configuration file
- `Makefile` - Convenience targets
- `README.md` - Project documentation
