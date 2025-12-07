#!/usr/bin/env python3
"""
deploy_to_pico.py - Deploy OpenPonyLogger to CircuitPython device

This script automates the complete deployment process:
1. Detects mounted CIRCUITPY drive
2. Compresses web assets
3. Copies all required files to Pico
4. Validates installation
5. Optionally installs dependencies via circup

Usage:
    python3 deploy_to_pico.py                    # Auto-detect and deploy
    python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY
    python3 deploy_to_pico.py --clean            # Clean install
    python3 deploy_to_pico.py --no-web           # Skip web compression
    python3 deploy_to_pico.py --install-deps     # Install CircuitPython libraries
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
import tempfile
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

def compress_web_assets(output_dir):
    """
    Compress web assets for CircuitPython
    
    Args:
        output_dir: Directory to output compressed files
    
    Returns:
        True if successful, False otherwise
    """
    print_info("Compressing web assets...")
    
    web_dir = Path("web")
    if not web_dir.exists():
        print_error(f"Web directory not found: {web_dir}")
        return False
    
    script = Path("tools/prepare_web_assets_cp.py")
    if not script.exists():
        print_error(f"Compression script not found: {script}")
        return False
    
    try:
        result = subprocess.run(
            ["python3", str(script), str(web_dir), str(output_dir)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Print compression results
        for line in result.stdout.split('\n'):
            if 'savings' in line.lower() or 'bytes' in line.lower():
                print(f"  {line}")
        
        print_success("Web assets compressed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Compression failed: {e}")
        if e.stderr:
            print(e.stderr)
        return False

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

def check_mpy_cross():
    """
    Check if mpy-cross is available
    
    Returns:
        True if available, False otherwise
    """
    try:
        result = subprocess.run(
            ["mpy-cross", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def compile_to_mpy(src_file, output_dir):
    """
    Compile Python file to .mpy
    
    Args:
        src_file: Source .py file
        output_dir: Output directory for .mpy
    
    Returns:
        Path to .mpy file or None if failed
    """
    src_path = Path(src_file)
    mpy_file = Path(output_dir) / src_path.with_suffix('.mpy').name
    
    try:
        subprocess.run(
            ["mpy-cross", str(src_path), "-o", str(mpy_file)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Show size comparison
        src_size = src_path.stat().st_size
        mpy_size = mpy_file.stat().st_size
        savings = (1 - mpy_size / src_size) * 100
        print_info(f"  Compiled {src_path.name}: {src_size} → {mpy_size} bytes ({savings:.1f}% savings)")
        
        return mpy_file
        
    except subprocess.CalledProcessError as e:
        print_error(f"  Failed to compile {src_file}: {e}")
        if e.stderr:
            print(f"    {e.stderr}")
        return None

def deploy_python_files(drive_path, backup=True, use_mpy=False):
    """
    Deploy Python source files to CIRCUITPY drive
    
    Args:
        drive_path: Path to CIRCUITPY drive
        backup: If True, backup existing files
        use_mpy: If True, compile to .mpy before deploying
    
    Returns:
        True if successful, False otherwise
    """
    print_info("Deploying Python files...")
    
    files_to_deploy = {
        # Main application
        "circuitpython/code.py": "code.py",

        # Modules from circuitpython/local/
        "circuitpython/local/wifi_server.py": "wifi_server.py",
        "circuitpython/local/scheduler.py": "scheduler.py",

        # Configuration (if exists)
        "circuitpython/settings.toml": "settings.toml",
    }
    NO_COMPILE_FILES = ["code.py", "settings.toml"]
    
    # Check if mpy-cross is available
    if use_mpy:
        if not check_mpy_cross():
            print_warning("  mpy-cross not found, deploying .py files instead")
            print_info("  Install with: pip install mpy-cross")
            use_mpy = False
        else:
            print_success("  Using mpy-cross for bytecode compilation")
    
    success = True
    mpy_temp_dir = None
    
    if use_mpy:
        import tempfile
        mpy_temp_dir = Path(tempfile.mkdtemp(prefix="mpy_"))
    
    for src, dst in files_to_deploy.items():
        src_path = Path(src)
        if not src_path.exists():
            print_warning(f"  File not found, skipping: {src}")
            continue
        
        # Skip non-Python files
        if not src.endswith('.py'):
            dst_path = Path(drive_path) / dst
            try:
                copy_file_with_backup(src_path, dst_path, backup)
            except Exception as e:
                print_error(f"  Failed to copy {src}: {e}")
                success = False
            continue
        # Check if this file should be compiled
        should_compile = use_mpy and dst not in NO_COMPILE_FILES
        
        # Compile to .mpy if requested
        if should_compile:
            mpy_file = compile_to_mpy(src_path, mpy_temp_dir)
            if mpy_file:
                # Deploy .mpy file
                dst_path = Path(drive_path) / dst.replace('.py', '.mpy')
                try:
                    copy_file_with_backup(mpy_file, dst_path, backup)
                except Exception as e:
                    print_error(f"  Failed to copy {mpy_file.name}: {e}")
                    success = False
            else:
                # Fallback to .py
                print_warning(f"  Compilation failed, deploying {src} as .py")
                dst_path = Path(drive_path) / dst
                try:
                    copy_file_with_backup(src_path, dst_path, backup)
                except Exception as e:
                    print_error(f"  Failed to copy {src}: {e}")
                    success = False
        else:
            # Deploy .py file
            dst_path = Path(drive_path) / dst
            try:
                copy_file_with_backup(src_path, dst_path, backup)
            except Exception as e:
                print_error(f"  Failed to copy {src}: {e}")
                success = False
    
    # Cleanup temp directory
    if mpy_temp_dir and mpy_temp_dir.exists():
        import shutil
        shutil.rmtree(mpy_temp_dir)
    
    return success

def deploy_web_assets(drive_path, compressed_dir):
    """
    Deploy compressed web assets
    
    Args:
        drive_path: Path to CIRCUITPY drive
        compressed_dir: Directory containing compressed assets
    
    Returns:
        True if successful, False otherwise
    """
    print_info("Deploying web assets...")
    
    web_dst = Path(drive_path) / "web"
    web_dst.mkdir(exist_ok=True)
    
    # Copy all files from compressed directory
    compressed_path = Path(compressed_dir)
    if not compressed_path.exists():
        print_error(f"Compressed directory not found: {compressed_dir}")
        return False
    
    files_copied = 0
    for file in compressed_path.iterdir():
        if file.is_file():
            dst = web_dst / file.name
            shutil.copy2(file, dst)
            print_info(f"  Copied {file.name}")
            files_copied += 1
    
    print_success(f"Deployed {files_copied} web assets")
    return True

def clean_deployment(drive_path):
    """
    Clean existing deployment (remove old files)
    
    Args:
        drive_path: Path to CIRCUITPY drive
    """
    print_info("Cleaning existing deployment...")
    
    # Files to remove
    files_to_clean = [
        "code.py.backup",
        "wifi_server_gz.py.backup",
        "web_server_gz.py.backup",
    ]
    
    # Directories to clean
    dirs_to_clean = [
        "web",
    ]
    
    for file in files_to_clean:
        file_path = Path(drive_path) / file
        if file_path.exists():
            file_path.unlink()
            print_info(f"  Removed {file}")
    
    for dir in dirs_to_clean:
        dir_path = Path(drive_path) / dir
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print_info(f"  Removed {dir}/")
    
    print_success("Cleanup complete")

def validate_deployment(drive_path, check_mpy=False):
    """
    Validate that deployment was successful
    
    Args:
        drive_path: Path to CIRCUITPY drive
        check_mpy: If True, check for .mpy files instead of .py
    
    Returns:
        True if valid, False otherwise
    """
    print_info("Validating deployment...")
    
    # Adjust file extensions based on deployment type
    py_ext = '.mpy' if check_mpy else '.py'
    
    required_files = [
        f"code{py_ext}",
        f"wifi_server{py_ext}",
#        f"web_server{py_ext}",
        "web/asset_map.py",  # Always .py
        "web/index.html.gz",
        "web/styles.css.gz",
        "web/app.js.gz",
    ]
    
    all_valid = True
    for file in required_files:
        file_path = Path(drive_path) / file
        if file_path.exists():
            size = file_path.stat().st_size
            print_success(f"  {file} ({size:,} bytes)")
        else:
            print_error(f"  Missing: {file}")
            all_valid = False
    
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
        print_info("Or: brew install circup (macOS)")
        return False
    
    # Install/update libraries
    print_info("Installing/updating CircuitPython libraries...")
    
    try:
        # Change to the CIRCUITPY directory first
        import os
        original_dir = os.getcwd()
        os.chdir(drive_path)

        result = subprocess.run(
            ["circup", "install", "-a"],  # Removed --path
            capture_output=True,
            text=True,
            check=True
        )

        os.chdir(original_dir)
        print(result.stdout)
        print_success("Libraries installed/updated")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install libraries: {e}")
        if e.stderr:
            print(e.stderr)
        return False

def show_post_deployment_info(drive_path):
    """Show helpful information after deployment"""
    print_header("Deployment Complete!")
    
    print(f"{Colors.OKGREEN}Next steps:{Colors.ENDC}")
    print(f"  1. Safely eject CIRCUITPY drive")
    print(f"  2. Pico will auto-restart with new code")
    print(f"  3. Connect to WiFi: OpenPonyLogger")
    print(f"  4. Browse to: http://192.168.4.1")
    print()
    
    print(f"{Colors.OKCYAN}Verification:{Colors.ENDC}")
    print(f"  - Check browser DevTools (F12)")
    print(f"  - Network tab → Response Headers")
    print(f"  - Should see: Content-Encoding: gzip")
    print()
    
    print(f"{Colors.WARNING}Troubleshooting:{Colors.ENDC}")
    print(f"  - Serial console: screen /dev/tty.usbmodem* 115200")
    print(f"  - View logs for errors")
    print(f"  - Check web/ directory has .gz files")
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
        """
    )
    
    parser.add_argument('--drive', 
                       help='Path to CIRCUITPY drive (auto-detect if not specified)')
    parser.add_argument('--clean', 
                       action='store_true',
                       help='Clean existing deployment before installing')
    parser.add_argument('--no-web', 
                       action='store_true',
                       help='Skip web asset compression and deployment')
    parser.add_argument('--no-backup', 
                       action='store_true',
                       help='Do not backup existing files')
    parser.add_argument('--install-deps', 
                       action='store_true',
                       help='Install/update CircuitPython libraries via circup')
    parser.add_argument('--mpy', 
                       action='store_true',
                       help='Compile Python files to .mpy bytecode (faster loading, less RAM)')
    
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
    
    # Clean if requested
    if args.clean:
        clean_deployment(drive_path)
    
    # Compress web assets
    compressed_dir = None
    if not args.no_web:
        print_header("Compressing Web Assets")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            compressed_dir = Path(tmpdir) / "web_compressed"
            
            if not compress_web_assets(compressed_dir):
                print_error("Web asset compression failed!")
                return 1
            
            # Deploy web assets
            print_header("Deploying to Pico")
            if not deploy_web_assets(drive_path, compressed_dir):
                print_error("Web asset deployment failed!")
                return 1
    
    # Deploy Python files
    if not deploy_python_files(drive_path, backup=not args.no_backup, use_mpy=args.mpy):
        print_warning("Some Python files failed to deploy")
    
    # Install dependencies if requested
    if args.install_deps:
        print_header("Installing CircuitPython Libraries")
        install_circuitpython_libs(drive_path)
    
    # Validate deployment
    print_header("Validating Deployment")
    if not validate_deployment(drive_path, check_mpy=args.mpy):
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
