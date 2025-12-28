#!/usr/bin/env python3
"""
deploy_to_pico.py - OpenPonyLogger Deployment Tool (TOML-based)

Reads deploy.toml for configuration and deploys files to CIRCUITPY drive.
Handles platform detection, file verification, and orphan warnings.

Usage:
    python3 deploy_to_pico.py                    # Use deploy.toml settings
    python3 deploy_to_pico.py --config custom.toml
    python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY
    python3 deploy_to_pico.py --clean            # Clean orphans
    python3 deploy_to_pico.py --mpy              # Force .mpy compilation
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

# Try to use tomllib (Python 3.11+) or fallback to toml
try:
    import tomllib
    def load_toml(path):
        with open(path, 'rb') as f:
            return tomllib.load(f)
except ImportError:
    try:
        import toml
        def load_toml(path):
            with open(path, 'r') as f:
                return toml.load(f)
    except ImportError:
        print("ERROR: Neither tomllib nor toml module available!")
        print("Install with: pip install toml")
        sys.exit(1)


class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def print_info(msg):
    print(f"{Colors.OKCYAN}→ {msg}{Colors.ENDC}")


class DeploymentConfig:
    """Deployment configuration from deploy.toml"""
    
    def __init__(self, config_path='deploy.toml'):
        """Load deployment configuration"""
        self.config_path = config_path
        
        if not os.path.exists(config_path):
            print_error(f"Config file not found: {config_path}")
            sys.exit(1)
        
        self.config = load_toml(config_path)
        print_success(f"Loaded config from {config_path}")
    
    def get(self, key, default=None):
        """Get config value using dot notation"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_file_groups(self):
        """Get all file groups to deploy"""
        return self.config.get('files', {})
    
    def get_mount_points(self):
        """Get mount points for current platform"""
        system = platform.system()
        
        if system == 'Darwin':
            return self.get('platform.macos.mount_points', ['/Volumes/CIRCUITPY'])
        elif system == 'Linux':
            # Expand $USER variable
            points = self.get('platform.linux.mount_points', ['/media/CIRCUITPY'])
            user = os.environ.get('USER', '')
            return [p.replace('$USER', user) for p in points]
        elif system == 'Windows':
            return self.get('platform.windows.mount_points', ['D:/CIRCUITPY'])
        else:
            return []


class CircuitPyDrive:
    """Represents a CIRCUITPY drive"""
    
    def __init__(self, path):
        """Initialize drive"""
        self.path = Path(path)
        
        if not self.path.exists():
            raise FileNotFoundError(f"Drive not found: {path}")
        
        # Verify it's a CircuitPython device
        boot_out = self.path / "boot_out.txt"
        if not boot_out.exists():
            raise ValueError(f"Not a CircuitPython drive: {path}")
        
        # Read boot info
        self.boot_info = boot_out.read_text().strip()
    
    def get_free_space(self):
        """Get free space in bytes"""
        if sys.platform == 'win32':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                str(self.path), None, None, ctypes.pointer(free_bytes)
            )
            return free_bytes.value
        else:
            stat = os.statvfs(self.path)
            return stat.f_bavail * stat.f_frsize
    
    def list_files(self, relative=True):
        """
        List all files on drive
        
        Args:
            relative: Return paths relative to drive root
            
        Returns:
            set: Set of file paths
        """
        files = set()
        
        for root, dirs, filenames in os.walk(self.path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in filenames:
                # Skip hidden files
                if filename.startswith('.'):
                    continue
                
                filepath = Path(root) / filename
                
                if relative:
                    files.add(str(filepath.relative_to(self.path)))
                else:
                    files.add(str(filepath))
        
        return files


class Deployer:
    """Handles deployment to CircuitPython device"""
    
    def __init__(self, config, drive_path=None):
        """
        Initialize deployer
        
        Args:
            config: DeploymentConfig object
            drive_path: Optional manual drive path
        """
        self.config = config
        self.drive = None
        self.stats = {
            'copied': 0,
            'skipped': 0,
            'failed': 0,
            'compiled': 0,
        }
        
        # Find or verify drive
        if drive_path:
            print_info(f"Using specified drive: {drive_path}")
            self.drive = CircuitPyDrive(drive_path)
        elif config.get('targets.auto_detect', True):
            print_info("Auto-detecting CIRCUITPY drive...")
            self.drive = self._auto_detect_drive()
        else:
            print_error("Auto-detect disabled and no drive specified!")
            sys.exit(1)
        
        print_success(f"Found drive: {self.drive.path}")
        print_info(f"  {self.drive.boot_info}")
    
    def _auto_detect_drive(self):
        """Auto-detect CIRCUITPY drive"""
        mount_points = self.config.get_mount_points()
        
        for point in mount_points:
            try:
                drive = CircuitPyDrive(point)
                return drive
            except (FileNotFoundError, ValueError):
                continue
        
        print_error("Could not auto-detect CIRCUITPY drive!")
        print_info("Available mount points checked:")
        for point in mount_points:
            print(f"  - {point}")
        sys.exit(1)
    
    def create_backup(self):
        """Create backup of current drive contents"""
        if not self.config.get('options.backup', True):
            return
        
        print_header("Creating Backup")
        
        backup_dir = Path(self.config.get('options.backup_dir', 'backups'))
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"backup_{timestamp}"
        
        try:
            shutil.copytree(self.drive.path, backup_path, 
                          ignore=shutil.ignore_patterns('.*'))
            print_success(f"Backup created: {backup_path}")
        except Exception as e:
            print_warning(f"Backup failed: {e}")
    
    def check_mpy_cross(self):
        """Check if mpy-cross is available"""
        try:
            subprocess.run(['mpy-cross', '--version'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def compile_to_mpy(self, py_file):
        """
        Compile .py to .mpy
        
        Args:
            py_file: Path to .py file
            
        Returns:
            Path to .mpy file or None if failed
        """
        mpy_file = py_file.with_suffix('.mpy')
        
        try:
            subprocess.run(['mpy-cross', str(py_file), '-o', str(mpy_file)],
                         capture_output=True, check=True)
            
            py_size = py_file.stat().st_size
            mpy_size = mpy_file.stat().st_size
            savings = (1 - mpy_size / py_size) * 100
            
            print_info(f"  Compiled {py_file.name}: "
                      f"{py_size} → {mpy_size} bytes ({savings:.1f}% savings)")
            self.stats['compiled'] += 1
            
            return mpy_file
        except subprocess.CalledProcessError as e:
            print_error(f"  Compilation failed for {py_file.name}")
            return None
    
    def should_exclude(self, filename):
        """Check if file should be excluded"""
        exclude_patterns = self.config.get('options.exclude', [])
        
        for pattern in exclude_patterns:
            if pattern.startswith('*.'):
                # Extension pattern
                if filename.endswith(pattern[1:]):
                    return True
            elif pattern in str(filename):
                return True
        
        return False
    
    def deploy_files(self, use_mpy=False):
        """
        Deploy all file groups
        
        Args:
            use_mpy: Force .mpy compilation
        """
        print_header("Deploying Files")
        
        # Check mpy-cross availability
        if use_mpy and not self.check_mpy_cross():
            print_warning("mpy-cross not found, deploying .py files instead")
            use_mpy = False
        
        deployed_files = set()
        file_groups = self.config.get_file_groups()
        
        for group_name, group_config in file_groups.items():
            print(f"\n[{group_name}]")
            
            # Check if group is optional
            optional = group_config.get('optional', False)
            
            # Handle copy_tree (entire directory)
            if group_config.get('copy_tree', False):
                self._deploy_tree(group_config, deployed_files)
                continue
            
            # Deploy individual files
            source_dir = Path(group_config.get('source_dir', '.'))
            destination = group_config.get('destination', '/')
            files = group_config.get('files', [])
            
            for filename in files:
                source = source_dir / filename
                
                # Check if file exists
                if not source.exists():
                    if optional:
                        print_info(f"  Skipped {filename} (optional, not found)")
                        self.stats['skipped'] += 1
                        continue
                    else:
                        print_error(f"  Required file not found: {source}")
                        self.stats['failed'] += 1
                        continue
                
                # Check exclusions
                if self.should_exclude(filename):
                    print_info(f"  Excluded {filename}")
                    self.stats['skipped'] += 1
                    continue
                
                # Determine destination path
                if destination == '/':
                    dest_path = self.drive.path / filename
                else:
                    dest_dir = self.drive.path / destination.lstrip('/')
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / filename
                
                # Compile to .mpy if requested
                if use_mpy and source.suffix == '.py':
                    mpy_file = self.compile_to_mpy(source)
                    if mpy_file:
                        source = mpy_file
                        dest_path = dest_path.with_suffix('.mpy')
                
                # Copy file
                try:
                    shutil.copy2(source, dest_path)
                    print_success(f"  Copied {filename} → {dest_path.relative_to(self.drive.path)}")
                    deployed_files.add(str(dest_path.relative_to(self.drive.path)))
                    self.stats['copied'] += 1
                except Exception as e:
                    print_error(f"  Failed to copy {filename}: {e}")
                    self.stats['failed'] += 1
        
        return deployed_files
    
    def _deploy_tree(self, group_config, deployed_files):
        """Deploy entire directory tree"""
        source_dir = Path(group_config.get('source_dir', '.'))
        destination = group_config.get('destination', '/')
        
        if not source_dir.exists():
            if group_config.get('optional', False):
                print_info(f"  Skipped (directory not found)")
                self.stats['skipped'] += 1
                return
            else:
                print_error(f"  Directory not found: {source_dir}")
                self.stats['failed'] += 1
                return
        
        # Destination directory
        if destination == '/':
            dest_dir = self.drive.path
        else:
            dest_dir = self.drive.path / destination.lstrip('/')
        
        # Copy tree
        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            
            shutil.copytree(source_dir, dest_dir,
                          ignore=shutil.ignore_patterns('.*'))
            
            # Count files copied
            file_count = sum(1 for _ in dest_dir.rglob('*') if _.is_file())
            
            print_success(f"  Copied directory tree: {source_dir} → {dest_dir.relative_to(self.drive.path)} ({file_count} files)")
            
            # Add all files to deployed set
            for filepath in dest_dir.rglob('*'):
                if filepath.is_file():
                    deployed_files.add(str(filepath.relative_to(self.drive.path)))
            
            self.stats['copied'] += file_count
            
        except Exception as e:
            print_error(f"  Failed to copy tree: {e}")
            self.stats['failed'] += 1
    
    def check_orphans(self, deployed_files, delete=False):
        """
        Check for orphaned files on drive
        
        Args:
            deployed_files: Set of files that were deployed
            delete: Delete orphaned files if True
        """
        if not self.config.get('options.warn_orphans', True):
            return
        
        print_header("Checking for Orphaned Files")
        
        drive_files = self.drive.list_files()
        orphans = drive_files - deployed_files
        
        # Filter out system files
        system_patterns = ['boot_out.txt', 'System Volume Information', '.Trashes']
        orphans = {f for f in orphans if not any(p in f for p in system_patterns)}
        
        if not orphans:
            print_success("No orphaned files found")
            return
        
        print_warning(f"Found {len(orphans)} orphaned file(s) on drive:")
        for orphan in sorted(orphans):
            print(f"  - {orphan}")
        
        if delete or self.config.get('options.delete_orphans', False):
            print("\n" + Colors.WARNING + "Deleting orphaned files..." + Colors.ENDC)
            for orphan in orphans:
                try:
                    orphan_path = self.drive.path / orphan
                    orphan_path.unlink()
                    print_info(f"  Deleted: {orphan}")
                except Exception as e:
                    print_error(f"  Failed to delete {orphan}: {e}")
        else:
            print_info("\nTo auto-delete orphans, set delete_orphans=true in deploy.toml")
            print_info("or use --clean flag")
    
    def validate_deployment(self):
        """Validate that required files are present"""
        print_header("Validating Deployment")
        
        required = self.config.get('validation.required', [])
        missing = []
        
        for filename in required:
            filepath = self.drive.path / filename
            if filepath.exists():
                size = filepath.stat().st_size
                print_success(f"  {filename} ({size:,} bytes)")
            else:
                print_error(f"  Missing: {filename}")
                missing.append(filename)
        
        # Check required libraries
        lib_dir = self.drive.path / 'lib'
        if lib_dir.exists():
            required_libs = self.config.get('validation.required_libs', [])
            for lib in required_libs:
                lib_path = lib_dir / lib
                if lib_path.exists() or (lib_path.parent / f"{lib_path.stem}.mpy").exists():
                    print_success(f"  lib/{lib}")
                else:
                    print_warning(f"  Missing lib: {lib}")
        
        # Check free space
        free_space = self.drive.get_free_space()
        min_space = self.config.get('validation.min_free_space', 1048576)
        
        if free_space < min_space:
            print_warning(f"  Low free space: {free_space:,} bytes (min: {min_space:,})")
        else:
            print_success(f"  Free space: {free_space:,} bytes")
        
        if missing:
            print_error(f"\n{len(missing)} required file(s) missing!")
            return False
        
        return True
    
    def print_stats(self):
        """Print deployment statistics"""
        print_header("Deployment Statistics")
        
        print(f"  Files copied:    {self.stats['copied']}")
        print(f"  Files skipped:   {self.stats['skipped']}")
        print(f"  Files failed:    {self.stats['failed']}")
        print(f"  Files compiled:  {self.stats['compiled']}")
        
        if self.stats['failed'] > 0:
            print_warning(f"\n{self.stats['failed']} file(s) failed to copy!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Deploy OpenPonyLogger to CircuitPython device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 deploy_to_pico.py                    # Use deploy.toml
  python3 deploy_to_pico.py --drive /Volumes/CIRCUITPY
  python3 deploy_to_pico.py --clean            # Delete orphaned files
  python3 deploy_to_pico.py --mpy              # Compile to .mpy
  python3 deploy_to_pico.py --config custom.toml
        """
    )
    
    parser.add_argument('--config', default='deploy.toml',
                       help='Path to deployment config file')
    parser.add_argument('--drive',
                       help='Path to CIRCUITPY drive (auto-detect if not specified)')
    parser.add_argument('--clean', action='store_true',
                       help='Delete orphaned files on drive')
    parser.add_argument('--mpy', action='store_true',
                       help='Compile Python files to .mpy bytecode')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip backup creation')
    
    args = parser.parse_args()
    
    print_header("OpenPonyLogger - CircuitPython Deployment Tool")
    
    # Load configuration
    config = DeploymentConfig(args.config)
    
    # Initialize deployer
    deployer = Deployer(config, drive_path=args.drive)
    
    # Create backup
    if not args.no_backup:
        deployer.create_backup()
    
    # Deploy files
    deployed_files = deployer.deploy_files(use_mpy=args.mpy)
    
    # Check for orphans
    deployer.check_orphans(deployed_files, delete=args.clean)
    
    # Validate deployment
    deployer.validate_deployment()
    
    # Print statistics
    deployer.print_stats()
    
    # Success message
    print_header("Deployment Complete!")
    print_success("Next steps:")
    print("  1. Safely eject CIRCUITPY drive")
    print("  2. Pico will auto-restart with new code")
    print("  3. Check serial console for boot messages")
    
    return 0 if deployer.stats['failed'] == 0 else 1


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
