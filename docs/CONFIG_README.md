# Configuration Directory

This directory contains configuration files that will be automatically deployed to your Pico.

## Quick Start

1. **Copy example files:**
   ```bash
   cp settings.toml.example settings.toml
   cp hardware.toml.example hardware.toml
   ```

2. **Edit to match your setup:**
   ```bash
   nano settings.toml    # Application settings
   nano hardware.toml    # Hardware pin assignments
   ```

3. **Deploy:**
   ```bash
   make deploy
   # or
   python3 tools/deploy_to_pico.py
   ```

The deployment script will automatically copy `settings.toml` and `hardware.toml` (if they exist) to your Pico.

## Configuration Files

### settings.toml (Optional)
Application configuration - logging format, network settings, units, etc.

**If missing:** OpenPonyLogger uses built-in defaults from `config.py`

**To customize:**
1. Copy `settings.toml.example` → `settings.toml`
2. Edit values
3. Run `make deploy`

### hardware.toml (Optional)
Hardware configuration - pin assignments, I2C addresses, sample rates, etc.

**If missing:** OpenPonyLogger uses default hardware configuration

**To customize:**
1. Copy `hardware.toml.example` → `hardware.toml`
2. Edit pin assignments and peripheral settings
3. Run `make deploy`
4. **Important:** Make sure your physical wiring matches!

## Directory Structure

```
config/
├── README.md                 # This file
├── settings.toml.example     # Example application config
├── hardware.toml.example     # Example hardware config
├── settings.toml            # Your settings (ignored by git)
└── hardware.toml            # Your hardware config (ignored by git)
```

## What Gets Deployed?

When you run `make deploy`:

1. ✅ All Python modules from `circuitpython/`
2. ✅ `settings.toml` from `config/` (if exists)
3. ✅ `hardware.toml` from `config/` (if exists)
4. ✅ Validates deployment
5. ✅ Shows status

**Note:** Your personal `settings.toml` and `hardware.toml` files are in `.gitignore` so they won't be committed to git.

## Common Scenarios

### Scenario 1: First Time Setup

```bash
# Use all defaults
make deploy
# → Uses built-in defaults, no config files needed
```

### Scenario 2: Custom Settings Only

```bash
# Customize app behavior but use default hardware
cp settings.toml.example settings.toml
nano settings.toml  # Edit WiFi, logging, etc.
make deploy
```

### Scenario 3: Custom Hardware Wiring

```bash
# Different pin assignments
cp hardware.toml.example hardware.toml
nano hardware.toml  # Edit pin numbers
make deploy
```

### Scenario 4: Full Customization

```bash
# Both files
cp settings.toml.example settings.toml
cp hardware.toml.example hardware.toml
nano settings.toml
nano hardware.toml
make deploy
```

## Validating Configuration

Check what's deployed:

```bash
make validate

# Output shows:
# ✓ code.py (12,345 bytes)
# ✓ settings.toml (890 bytes)
# ✓ hardware.toml (2,341 bytes)
```

## Troubleshooting

### Config file not copying?

**Check:**
```bash
# Verify file exists
ls -la config/

# Verify in config/ directory (not circuitpython/)
pwd  # Should show: .../OpenPyPony
```

### Wrong settings after deploy?

**Fix:**
1. Edit `config/settings.toml` (not `circuitpython/settings.toml`)
2. Run `make deploy` again
3. Check serial output for errors

### Hardware not working after config change?

**Verify:**
1. Pin assignments in `hardware.toml` match your wiring
2. I2C addresses are correct (use i2c scan)
3. Peripherals are enabled: `enabled = true`
4. Check serial output: `screen /dev/tty.usbmodem* 115200`

## Advanced

### Multiple Configurations

Keep different configs for different builds:

```bash
# Track day config
cp settings.toml settings.toml.trackday

# Daily driving config  
cp settings.toml settings.toml.daily

# Switch configs
cp settings.toml.trackday settings.toml
make deploy
```

### Version Control

The `.example` files are tracked in git. Your personal configs are not:

```bash
# Tracked (committed to git)
settings.toml.example
hardware.toml.example

# Ignored (not committed)
settings.toml
hardware.toml
```

This lets you:
- ✅ Share example configs
- ✅ Keep personal settings private
- ✅ Update examples without affecting your configs

## Documentation

- **Application Settings:** See `settings.toml.example` for all options
- **Hardware Config:** See `HARDWARE_CONFIG.md` for pin assignments
- **Deployment:** See `tools/README.md` for deployment options

## Need Help?

1. Check example files for available options
2. Read `HARDWARE_CONFIG.md` for hardware details
3. Check serial console for errors: `make serial`
4. Open an issue on GitHub

---

**Questions?** See the main [README](../README.md) or [HARDWARE_CONFIG.md](../HARDWARE_CONFIG.md)
