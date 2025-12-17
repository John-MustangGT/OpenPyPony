# Configuration Deployment - Update Summary

## What Changed

✅ **Updated `deploy_to_pico.py`** to automatically copy configuration files from `config/` directory

## New Directory Structure

```
OpenPyPony/
├── circuitpython/           # Python source code
│   ├── code.py
│   ├── hardware_setup.py
│   └── ...
├── config/                  # Configuration files (NEW!)
│   ├── README.md
│   ├── settings.toml.example
│   ├── hardware.toml.example
│   ├── settings.toml        # Your personal config (git ignored)
│   └── hardware.toml        # Your hardware config (git ignored)
└── tools/
    └── deploy_to_pico.py    # Updated deployment script
```

## Quick Start

### 1. Setup Configuration (First Time)

```bash
cd config/

# Copy example files
cp settings.toml.example settings.toml
cp hardware.toml.example hardware.toml

# Edit to match your setup
nano settings.toml    # WiFi, logging, units, etc.
nano hardware.toml    # Pin assignments, peripherals
```

### 2. Deploy to Pico

```bash
# From project root
make deploy

# Or directly
python3 tools/deploy_to_pico.py
```

**The script now automatically:**
1. ✅ Deploys all Python modules
2. ✅ Copies `config/settings.toml` → `CIRCUITPY:/settings.toml` (if exists)
3. ✅ Copies `config/hardware.toml` → `CIRCUITPY:/hardware.toml` (if exists)
4. ✅ Validates deployment
5. ✅ Shows status

## Example Output

```
============================================================
Deploying to Pico
============================================================

→ Deploying Python modules...
  Copied code.py → code.py
  Copied hardware_setup.py → hardware_setup.py
  Unchanged: utils.py
✓ Deployed 2 module(s)
→ Skipped 8 unchanged module(s)

→ Deploying configuration files...
  Backed up settings.toml → settings.toml.backup
  Copied settings.toml → settings.toml
  Backed up hardware.toml → hardware.toml.backup
  Copied hardware.toml → hardware.toml
✓ Deployed 2 configuration file(s)

============================================================
Validating Deployment
============================================================

→ Validating deployment...
→ Required modules:
✓ code.py (15,234 bytes)
✓ hardware_setup.py (8,901 bytes)
...
→ Configuration files:
✓ settings.toml (456 bytes)
✓ hardware.toml (2,103 bytes)

✓ All required files present!
```

## New Features in deploy_to_pico.py

### 1. Config File Detection

Automatically finds and copies config files:

```python
def deploy_config_files(drive_path, backup=True):
    """Deploy settings.toml and hardware.toml if they exist"""
    config_dir = Path("config")
    config_files = ["settings.toml", "hardware.toml"]
    # ... copies files with change detection
```

### 2. Smart Change Detection

Only copies files that have changed:

```python
if files_differ(src, dst):
    copy_file_with_backup(src, dst, backup)
    files_copied += 1
else:
    print_info(f"  Unchanged: {config_file}")
```

### 3. Config Validation

Shows deployed config files:

```
→ Configuration files:
✓ settings.toml (456 bytes)
✓ hardware.toml (2,103 bytes)
```

Or if missing:

```
→ Configuration files:
→ Not found: settings.toml (will use defaults)
→ Not found: hardware.toml (will use defaults)
→ No config files found - using default settings
```

## Usage Examples

### Example 1: Use All Defaults

```bash
# No config files needed
make deploy
```

Result: Uses built-in defaults from `config.py` and `hardware_setup.py`

### Example 2: Custom Settings Only

```bash
cd config/
cp settings.toml.example settings.toml
nano settings.toml  # Change WiFi SSID, logging format, etc.

make deploy
```

Result: Custom app settings + default hardware config

### Example 3: Custom Hardware Wiring

```bash
cd config/
cp hardware.toml.example hardware.toml
nano hardware.toml  # Change pin assignments

make deploy
```

Result: Default app settings + custom hardware config

### Example 4: Full Customization

```bash
cd config/
cp settings.toml.example settings.toml
cp hardware.toml.example hardware.toml
nano settings.toml
nano hardware.toml

make deploy
```

Result: Everything customized

## Configuration Workflow

### Initial Setup

```bash
# 1. Create config directory
mkdir -p config

# 2. Copy example files
cd config
cp ../path/to/settings.toml.example settings.toml
cp ../path/to/hardware.toml.example hardware.toml

# 3. Edit configs
nano settings.toml
nano hardware.toml

# 4. Deploy
cd ..
make deploy
```

### Update Configuration

```bash
# 1. Edit config
nano config/settings.toml

# 2. Redeploy
make deploy

# 3. Pico automatically reloads
```

### Switch Configurations

```bash
# Track day setup
cp config/settings.toml.trackday config/settings.toml
make deploy

# Daily driving setup
cp config/settings.toml.daily config/settings.toml
make deploy
```

## Files to Create

To use this feature, create these files in your repository:

```bash
# 1. config/README.md
# - Explains config directory usage
# - Quick start guide
# - Troubleshooting

# 2. config/settings.toml.example
# - Example application settings
# - All available options documented
# - Safe defaults

# 3. config/hardware.toml.example  
# - Example hardware configuration
# - Pin assignments
# - Peripheral settings

# 4. config/.gitignore
settings.toml
hardware.toml
# (Personal configs not committed to git)
```

## Integration with Makefile

Update `Makefile` to show config status:

```makefile
.PHONY: config-status
config-status:
	@echo "Configuration Status:"
	@if [ -f config/settings.toml ]; then \
		echo "  ✓ settings.toml (custom)"; \
	else \
		echo "  → settings.toml (using defaults)"; \
	fi
	@if [ -f config/hardware.toml ]; then \
		echo "  ✓ hardware.toml (custom)"; \
	else \
		echo "  → hardware.toml (using defaults)"; \
	fi

.PHONY: config-init
config-init:
	@echo "Creating config files from examples..."
	@mkdir -p config
	@cp config/settings.toml.example config/settings.toml
	@cp config/hardware.toml.example config/hardware.toml
	@echo "✓ Config files created - edit before deploying"
```

## Benefits

1. **Separation of Concerns**
   - Code in `circuitpython/`
   - Config in `config/`
   - Clear organization

2. **Personal Settings**
   - Git ignores `settings.toml` and `hardware.toml`
   - Share examples, keep personal configs private

3. **Easy Switching**
   - Keep multiple configs
   - Switch with simple `cp` command
   - No code changes needed

4. **Automatic Deployment**
   - One command deploys everything
   - Change detection prevents unnecessary writes
   - Backup of existing configs

5. **Validation**
   - Shows what's deployed
   - Warns if files missing
   - Clear status output

## Migration Guide

### Existing Users

If you currently have `settings.toml` in `circuitpython/`:

```bash
# 1. Create config directory
mkdir -p config

# 2. Move existing config
mv circuitpython/settings.toml config/settings.toml

# 3. Deploy (it will copy to Pico automatically)
make deploy
```

### New Users

Just start with the quick start above - no migration needed!

## Troubleshooting

### Config not copying?

**Check file location:**
```bash
# Should be here:
ls config/settings.toml config/hardware.toml

# NOT here:
ls circuitpython/settings.toml  # Wrong location!
```

### Old config still active?

**Force redeploy:**
```bash
make deploy --clean
```

Or manually remove from Pico:
```bash
rm /Volumes/CIRCUITPY/settings.toml
rm /Volumes/CIRCUITPY/hardware.toml
```

Then deploy again.

---

**Ready to deploy!** 🚀

Your configuration files in `config/` directory will now be automatically deployed to the Pico every time you run `make deploy`.
