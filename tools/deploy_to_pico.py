#!/usr/bin/env python3
"""
deploy_to_pico.py - Deploy OpenPonyLogger to CircuitPython device

This script automates the complete deployment process:
1. Detects mounted CIRCUITPY drive
2. Copies logger.py to Pico
3. Optionally installs dependencies via circup
4. Validates installation

Usage:
    python3 deploy_to_pico.py                    # Auto-detect and deploy
    python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY
    python3 deploy_to_pico.py --clean            # Clean install
    python3 deploy_to_pico.py --install-deps     # Install CircuitPython libraries
    python3 deploy_to_pico.py --reset            # Factory reset Pico
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKCYAN}→ {msg}{Colors.ENDC}")

def find_circuitpy_drive():
    """
    Auto-detect CIRCUITPY drive across platforms
    
    Returns:
        Path to CIRCUITPY drive or None if not found
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        possible_paths = [
            "/Volumes/CIRCUITPY",
            "/Volumes/PICO",
        ]
    elif system == "Linux":
        possible_paths = [
            "/media/CIRCUITPY",
            "/media/$USER/CIRCUITPY",
            "/run/media/$USER/CIRCUITPY",
            "/mnt/CIRCUITPY",
        ]
        # Expand $USER
        user = os.environ.get('USER', '')
        possible_paths = [p.replace('$USER', user) for p in possible_paths]
    elif system == "Windows":
        # Check all drive letters
        possible_paths = [f"{chr(d)}:/CIRCUITPY" for d in range(ord('D'), ord('Z')+1)]
    else:
        return None
    
    for path in possible_paths:
        if os.path.isdir(path):
            # Verify it's actually a CircuitPython device
            if os.path.exists(os.path.join(path, "boot_out.txt")):
                return path
    
    return None

def check_git_repo():
    """Verify we're in a git repository"""
    if not os.path.isdir('.git'):
        print_error("Not in a git repository!")
        print_info("Run this script from the OpenPonyLogger root directory")
        return False
    return True

def copy_file_with_backup(src, dst, backup=True):
    """
    Copy file with optional backup
    
    Args:
        src: Source file path
        dst: Destination file path
        backup: If True, backup existing file
    """
    dst_path = Path(dst)
    
    # Backup existing file
    if backup and dst_path.exists():
        backup_path = dst_path.with_suffix(dst_path.suffix + '.backup')
        shutil.copy2(dst_path, backup_path)
        print_info(f"  Backed up {dst_path.name} → {backup_path.name}")
    
    # Copy new file
    shutil.copy2(src, dst)
    print_info(f"  Copied {Path(src).name} → {dst_path.name}")

def files_differ(src, dst):
    """
    Check if two files differ in content
    
    Args:
        src: Source file path
        dst: Destination file path
    
    Returns:
        True if files differ or dst doesn't exist, False if identical
    """
    if not dst.exists():
        return True
    
    # Compare file sizes first (quick check)
    if src.stat().st_size != dst.stat().st_size:
        return True
    
    # Compare content
    with open(src, 'rb') as f1, open(dst, 'rb') as f2:
        return f1.read() != f2.read()

def deploy_python_modules(drive_path, backup=True):
    """
    Deploy all Python modules from circuitpython/ to CIRCUITPY drive
    Only copies files that have changed.
    
    Args:
        drive_path: Path to CIRCUITPY drive
        backup: If True, backup existing files
    
    Returns:
        Tuple of (success, files_copied, files_skipped)
    """
    print_info("Deploying Python modules...")
    
    # List of all Python modules to deploy
    python_modules = [
        "code.py",
        "accelerometer.py",
        "config.py",
        "gps.py",
        "hardware_setup.py",
        "hardware_config.py",
        "neopixel_handler.py",
        "oled.py",
        "rtc_handler.py",
        "sdcard.py",
        "serial_com.py",
        "utils.py",
    ]
    
    src_dir = Path("circuitpython")
    if not src_dir.exists():
        print_error(f"Source directory not found: {src_dir}")
        return False, 0, 0
    
    files_copied = 0
    files_skipped = 0
    all_success = True
    
    for module in python_modules:
        src = src_dir / module
        
        if not src.exists():
            print_warning(f"  Module not found, skipping: {module}")
            continue
        
        dst = Path(drive_path) / module
        
        # Check if file needs updating
        if files_differ(src, dst):
            try:
                copy_file_with_backup(src, dst, backup)
                files_copied += 1
            except Exception as e:
                print_error(f"  Failed to deploy {module}: {e}")
                all_success = False
        else:
            print_info(f"  Unchanged: {module}")
            files_skipped += 1
    
    if files_copied > 0:
        print_success(f"Deployed {files_copied} module(s)")
    if files_skipped > 0:
        print_info(f"Skipped {files_skipped} unchanged module(s)")
    
    return all_success, files_copied, files_skipped

def deploy_config_files(drive_path, backup=True):
    """
    Deploy configuration files from config/ directory to CIRCUITPY drive
    Copies settings.toml and hardware.toml if they exist.
    
    Args:
        drive_path: Path to CIRCUITPY drive
        backup: If True, backup existing files
    
    Returns:
        Tuple of (success, files_copied)
    """
    print_info("Deploying configuration files...")
    
    config_dir = Path("config")
    config_files = ["settings.toml", "hardware.toml"]
    
    files_copied = 0
    all_success = True
    
    for config_file in config_files:
        src = config_dir / config_file
        
        # Check if config file exists
        if not src.exists():
            print_info(f"  {config_file} not found in config/, skipping")
            continue
        
        dst = Path(drive_path) / config_file
        
        # Check if file needs updating
        if files_differ(src, dst):
            try:
                copy_file_with_backup(src, dst, backup)
                files_copied += 1
            except Exception as e:
                print_error(f"  Failed to deploy {config_file}: {e}")
                all_success = False
        else:
            print_info(f"  Unchanged: {config_file}")
    
    if files_copied > 0:
        print_success(f"Deployed {files_copied} config file(s)")
    elif config_dir.exists():
        print_info("No config files to deploy or all unchanged")
    else:
        print_info("No config directory found")
    
    return all_success, files_copied

def clean_deployment(drive_path):
    """
    Clean existing deployment (remove old files)
    
    Args:
        drive_path: Path to CIRCUITPY drive
    """
    print_info("Cleaning existing deployment...")
    
    # Python modules to remove (including backups)
    python_modules = [
        "code.py",
        "accelerometer.py",
        "config.py",
        "gps.py",
        "hardware_setup.py",
        "hardware_config.py",
        "neopixel_handler.py",
        "oled.py",
        "rtc_handler.py",
        "sdcard.py",
        "serial_com.py",
        "utils.py",
    ]
    
    files_removed = 0
    
    for module in python_modules:
        # Remove main file
        file_path = Path(drive_path) / module
        if file_path.exists():
            file_path.unlink()
            print_info(f"  Removed {module}")
            files_removed += 1
        
        # Remove backup if exists
        backup_path = Path(drive_path) / f"{module}.backup"
        if backup_path.exists():
            backup_path.unlink()
            print_info(f"  Removed {module}.backup")
            files_removed += 1
    
    # Remove legacy files
    legacy_files = ["logger.py", "logger.py.backup"]
    for file in legacy_files:
        file_path = Path(drive_path) / file
        if file_path.exists():
            file_path.unlink()
            print_info(f"  Removed {file}")
            files_removed += 1
    
    if files_removed > 0:
        print_success(f"Cleanup complete ({files_removed} file(s) removed)")
    else:
        print_info("No files to clean")

def validate_deployment(drive_path):
    """
    Validate that deployment was successful
    
    Args:
        drive_path: Path to CIRCUITPY drive
    
    Returns:
        True if valid, False otherwise
    """
    print_info("Validating deployment...")
    
    # Required Python modules
    required_files = [
        "code.py",
        "hardware_setup.py",
        "hardware_config.py",
        "utils.py",
    ]
    
    # Optional modules (warn if missing but don't fail)
    optional_files = [
        "accelerometer.py",
        "config.py",
        "gps.py",
        "neopixel_handler.py",
        "oled.py",
        "rtc_handler.py",
        "sdcard.py",
        "serial_com.py",
    ]
    
    # Recommended libraries
    recommended_libs = [
        "lib/adafruit_lis3dh.mpy",
        "lib/adafruit_gps.mpy",
        "lib/adafruit_displayio_ssd1306.mpy",
        "lib/adafruit_display_text",
        "lib/adafruit_bitmap_font",
        "lib/neopixel.mpy",
    ]
    
    all_valid = True
    
    print_info("Required modules:")
    for file in required_files:
        file_path = Path(drive_path) / file
        if file_path.exists():
            size = file_path.stat().st_size
            print_success(f"  {file} ({size:,} bytes)")
        else:
            print_error(f"  Missing: {file}")
            all_valid = False
    
    print_info("Optional modules:")
    optional_found = 0
    for file in optional_files:
        file_path = Path(drive_path) / file
        if file_path.exists():
            size = file_path.stat().st_size
            print_success(f"  {file} ({size:,} bytes)")
            optional_found += 1
        else:
            print_warning(f"  Not found: {file}")
    
    print_info(f"Found {optional_found}/{len(optional_files)} optional modules")
    
    print_info("Recommended libraries (install with --install-deps):")
    libs_found = 0
    for file in recommended_libs:
        file_path = Path(drive_path) / file
        if file_path.exists():
            if file_path.is_dir():
                print_success(f"  {file}/ (directory)")
                libs_found += 1
            else:
                size = file_path.stat().st_size
                print_success(f"  {file} ({size:,} bytes)")
                libs_found += 1
        else:
            print_warning(f"  Not found: {file}")
    
    if libs_found < len(recommended_libs):
        print_warning(f"Only {libs_found}/{len(recommended_libs)} libraries found. Run: make install-deps")
    
    # Check for configuration files (optional but recommended)
    print_info("Configuration files:")
    config_files = ["settings.toml", "hardware.toml"]
    config_found = 0
    for file in config_files:
        file_path = Path(drive_path) / file
        if file_path.exists():
            size = file_path.stat().st_size
            print_success(f"  {file} ({size:,} bytes)")
            config_found += 1
        else:
            print_info(f"  Not found: {file} (will use defaults)")
    
    if config_found == 0:
        print_info("No config files found - using default settings")
        print_info("To customize: copy config/*.toml to config/ directory and redeploy")
    
    return all_valid

def install_circuitpython_libs(drive_path):
    """
    Install CircuitPython libraries using circup
    
    Args:
        drive_path: Path to CIRCUITPY drive
    
    Returns:
        True if successful, False otherwise
    """
    print_info("Checking for circup (CircuitPython library installer)...")
    
    # Check if circup is installed
    try:
        subprocess.run(["circup", "--version"], 
                      capture_output=True, 
                      check=True)
        print_success("circup found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning("circup not installed")
        print_info("Install with: pip install circup")
        return False
    
    # Install/update libraries
    print_info("Installing/updating CircuitPython libraries...")
    
    req_file = Path("circuitpython/requirements.txt")
    if not req_file.exists():
        print_error(f"Requirements file not found: {req_file}")
        return False
    
    try:
        result = subprocess.run(
            ["circup", "install", "-r", str(req_file), "--path", drive_path],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        print_success("Libraries installed/updated")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install libraries: {e}")
        if e.stderr:
            print(e.stderr)
        return False

def reset_pico(drive_path):
    """
    Factory reset the Pico by deploying a filesystem erase script
    
    Args:
        drive_path: Path to CIRCUITPY drive
    """
    print_header("Factory Reset Pico")
    
    print_error("WARNING: This will ERASE ALL DATA on the Pico!")
    print_warning("This includes:")
    print("  - All Python files (code.py, logger.py, etc.)")
    print("  - All libraries (/lib directory)")
    print("  - All settings (settings.toml, boot.py)")
    print("  - All user data")
    print()
    
    confirm = input("Type 'RESET' to confirm: ")
    if confirm != "RESET":
        print_warning("Reset cancelled")
        return False
    
    print()
    print_info("Creating reset script...")
    
    reset_script = """import storage
import os

print("=" * 50)
print("FACTORY RESET - Erasing filesystem...")
print("=" * 50)

try:
    storage.erase_filesystem()
    print("✓ Filesystem erased successfully")
    print("Pico will now reboot with clean filesystem")
except Exception as e:
    print(f"✗ Reset failed: {e}")
"""
    
    reset_path = Path(drive_path) / "code.py"
    with open(reset_path, 'w') as f:
        f.write(reset_script)
    
    print_success("Reset script deployed")
    print()
    print_warning("Please eject and reset your Pico now.")
    print("The Pico will:")
    print("  1. Boot and run the reset script")
    print("  2. Erase the filesystem")
    print("  3. Reboot with a clean filesystem")
    print()
    print_info("After reset, run: make install-deps && make deploy")
    
    return True

def show_post_deployment_info(drive_path):
    """Show helpful information after deployment"""
    print_header("Deployment Complete!")
    
    print(f"{Colors.OKGREEN}Next steps:{Colors.ENDC}")
    print(f"  1. Safely eject CIRCUITPY drive")
    print(f"  2. Pico will auto-restart with new code")
    print(f"  3. Connect via serial to view output")
    print()
    
    print(f"{Colors.OKCYAN}Serial Console:{Colors.ENDC}")
    system = platform.system()
    if system == "Darwin":
        print(f"  screen /dev/tty.usbmodem* 115200")
    elif system == "Linux":
        print(f"  screen /dev/ttyACM0 115200")
    print()
    
    print(f"{Colors.WARNING}Troubleshooting:{Colors.ENDC}")
    print(f"  - Check serial output for errors")
    print(f"  - Verify libraries installed: make validate")
    print(f"  - Install deps if needed: make install-deps")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Deploy OpenPonyLogger to CircuitPython device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 deploy_to_pico.py                 # Auto-detect and deploy
  python3 deploy_to_pico.py --clean         # Clean install
  python3 deploy_to_pico.py --no-backup     # Don't backup existing files
  python3 deploy_to_pico.py --install-deps  # Also install CircuitPython libs
  python3 deploy_to_pico.py --reset         # Factory reset Pico
        """
    )
    
    parser.add_argument('--drive', 
                       help='Path to CIRCUITPY drive (auto-detect if not specified)')
    parser.add_argument('--clean', 
                       action='store_true',
                       help='Clean existing deployment before installing')
    parser.add_argument('--no-backup', 
                       action='store_true',
                       help='Do not backup existing files')
    parser.add_argument('--install-deps', 
                       action='store_true',
                       help='Install/update CircuitPython libraries via circup')
    parser.add_argument('--reset', 
                       action='store_true',
                       help='Factory reset Pico filesystem (DESTRUCTIVE)')
    
    args = parser.parse_args()
    
    print_header("OpenPonyLogger - CircuitPython Deployment")
    
    # Check we're in git repo
    if not check_git_repo():
        return 1
    
    # Find CIRCUITPY drive
    if args.drive:
        drive_path = args.drive
        print_info(f"Using specified drive: {drive_path}")
    else:
        print_info("Auto-detecting CIRCUITPY drive...")
        drive_path = find_circuitpy_drive()
    
    if not drive_path:
        print_error("Could not find CIRCUITPY drive!")
        print_info("Please specify with --drive /path/to/CIRCUITPY")
        return 1
    
    if not os.path.isdir(drive_path):
        print_error(f"Drive path does not exist: {drive_path}")
        return 1
    
    print_success(f"Found CIRCUITPY drive: {drive_path}")
    
    # Show drive info
    boot_out = Path(drive_path) / "boot_out.txt"
    if boot_out.exists():
        with open(boot_out) as f:
            first_line = f.readline().strip()
            print_info(f"  {first_line}")
    
    # Handle reset separately
    if args.reset:
        return 0 if reset_pico(drive_path) else 1
    
    # Clean if requested
    if args.clean:
        clean_deployment(drive_path)
    
    # Deploy Python modules
    print_header("Deploying to Pico")
    success, copied, skipped = deploy_python_modules(drive_path, backup=not args.no_backup)
    if not success:
        print_error("Deployment had errors!")
        return 1
    
    if copied == 0 and skipped > 0:
        print_info("All modules are up to date!")
    elif copied > 0:
        print_success(f"Successfully deployed {copied} updated module(s)")
    
    # Deploy configuration files (settings.toml, hardware.toml)
    config_success, config_copied = deploy_config_files(drive_path, backup=not args.no_backup)
    if config_copied > 0:
        print_success(f"Deployed {config_copied} configuration file(s)")
    
    # Install dependencies if requested
    if args.install_deps:
        print_header("Installing CircuitPython Libraries")
        install_circuitpython_libs(drive_path)
    
    # Validate deployment
    print_header("Validating Deployment")
    if not validate_deployment(drive_path):
        print_warning("Validation found issues - please check manually")
    else:
        print_success("All required files present!")
    
    # Show post-deployment info
    show_post_deployment_info(drive_path)
    
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_error("\nDeployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
