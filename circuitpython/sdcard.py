"""
sdcard.py - SD Card management for OpenPonyLogger

Handles SD card initialization, session file management with sequential numbering
"""

import os
import storage
import sdcardio
import busio
import board

class SDCard:
    """SD Card manager"""
    
    def __init__(self, spi_sck=board.GP18, spi_mosi=board.GP19, spi_miso=board.GP16, cs=board.GP17):
        """
        Initialize SD card
        
        Args:
            spi_sck: SPI clock pin
            spi_mosi: SPI MOSI pin
            spi_miso: SPI MISO pin
            cs: Chip select pin
        """
        self.spi = busio.SPI(spi_sck, spi_mosi, spi_miso)
        self.cs = cs
        self.sdcard = None
        self.vfs = None
        self.mounted = False
        self.mount_point = "/sd"
        
    def mount(self):
        """Mount SD card"""
        try:
            self.sdcard = sdcardio.SDCard(self.spi, self.cs)
            self.vfs = storage.VfsFat(self.sdcard)
            storage.mount(self.vfs, self.mount_point)
            self.mounted = True
            print(f"[SD] ✓ Mounted at {self.mount_point}")
            return True
        except Exception as e:
            print(f"[SD] ✗ Mount failed: {e}")
            self.mounted = False
            return False
    
    def unmount(self):
        """Unmount SD card"""
        try:
            if self.mounted:
                storage.umount(self.mount_point)
                self.mounted = False
                print("[SD] Unmounted")
            return True
        except Exception as e:
            print(f"[SD] Unmount error: {e}")
            return False
    
    def get_capacity(self):
        """
        Get SD card capacity info
        
        Returns:
            tuple: (total_bytes, free_bytes) or (0, 0) on error
        """
        if not self.mounted:
            return (0, 0)
        
        try:
            stat = os.statvfs(self.mount_point)
            total_bytes = stat[0] * stat[2]
            free_bytes = stat[0] * stat[3]
            return (total_bytes, free_bytes)
        except Exception as e:
            print(f"[SD] Capacity check error: {e}")
            return (0, 0)
    
    def get_free_space_gb(self):
        """Get free space in GB"""
        _, free_bytes = self.get_capacity()
        return free_bytes / (1024 ** 3)
    
    def list_sessions(self, pattern="session_"):
        """
        List all session files
        
        Args:
            pattern: Filename pattern to match (default: "session_")
        
        Returns:
            list: List of session filenames
        """
        if not self.mounted:
            return []
        
        try:
            files = os.listdir(self.mount_point)
            sessions = [f for f in files if f.startswith(pattern)]
            return sorted(sessions)
        except Exception as e:
            print(f"[SD] List sessions error: {e}")
            return []
    
    def get_next_session_number(self):
        """
        Get next session number by scanning existing files
        
        Returns:
            int: Next available session number (starting from 1)
        """
        if not self.mounted:
            return 1
        
        try:
            files = os.listdir(self.mount_point)
            
            # Find all session files (both .csv and .opl)
            session_numbers = []
            for f in files:
                if f.startswith("session_") and (f.endswith(".csv") or f.endswith(".opl")):
                    # Extract number from "session_NNNNN.ext"
                    try:
                        # Split by underscore and dot
                        parts = f.replace(".csv", "").replace(".opl", "").split("_")
                        if len(parts) >= 2:
                            num = int(parts[1])
                            session_numbers.append(num)
                    except (ValueError, IndexError):
                        continue
            
            # Return next number
            if session_numbers:
                return max(session_numbers) + 1
            else:
                return 1
                
        except Exception as e:
            print(f"[SD] Get next session number error: {e}")
            return 1
    
    def create_session_filename(self, extension="csv"):
        """
        Create next session filename with sequential numbering
        
        Args:
            extension: File extension ('csv' or 'opl')
        
        Returns:
            str: Full path to session file (e.g., "/sd/session_00001.csv")
        """
        if not self.mounted:
            raise OSError("SD card not mounted")
        
        # Get next session number
        session_num = self.get_next_session_number()
        
        # Format with leading zeros (5 digits)
        filename = f"session_{session_num:05d}.{extension}"
        full_path = f"{self.mount_point}/{filename}"
        
        print(f"[SD] Next session: {filename}")
        return full_path
    
    def delete_session(self, filename):
        """
        Delete a session file
        
        Args:
            filename: Session filename (not full path)
        
        Returns:
            bool: True if deleted successfully
        """
        if not self.mounted:
            return False
        
        try:
            full_path = f"{self.mount_point}/{filename}"
            os.remove(full_path)
            print(f"[SD] Deleted: {filename}")
            return True
        except Exception as e:
            print(f"[SD] Delete error: {e}")
            return False
    
    def file_exists(self, filename):
        """
        Check if a file exists
        
        Args:
            filename: Filename (not full path)
        
        Returns:
            bool: True if file exists
        """
        if not self.mounted:
            return False
        
        try:
            full_path = f"{self.mount_point}/{filename}"
            os.stat(full_path)
            return True
        except OSError:
            return False
    
    def get_file_size(self, filename):
        """
        Get file size in bytes
        
        Args:
            filename: Filename (not full path)
        
        Returns:
            int: File size in bytes, or 0 on error
        """
        if not self.mounted:
            return 0
        
        try:
            full_path = f"{self.mount_point}/{filename}"
            stat = os.stat(full_path)
            return stat[6]  # Size in bytes
        except Exception as e:
            return 0
    
    def get_session_info(self):
        """
        Get summary of all sessions
        
        Returns:
            dict: Session statistics
        """
        sessions = self.list_sessions()
        
        total_size = 0
        csv_count = 0
        opl_count = 0
        
        for session in sessions:
            size = self.get_file_size(session)
            total_size += size
            
            if session.endswith('.csv'):
                csv_count += 1
            elif session.endswith('.opl'):
                opl_count += 1
        
        return {
            'total_sessions': len(sessions),
            'csv_sessions': csv_count,
            'opl_sessions': opl_count,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 ** 2),
            'sessions': sessions
        }


# Convenience functions for backward compatibility
_sd_card = None

def init_sdcard():
    """Initialize and mount SD card"""
    global _sd_card
    _sd_card = SDCard()
    return _sd_card.mount()

def get_sdcard():
    """Get global SD card instance"""
    return _sd_card

def create_log_file(extension="csv"):
    """
    Create a new log file with sequential numbering
    
    Args:
        extension: File extension ('csv' or 'opl')
    
    Returns:
        tuple: (file_object, filename) or (None, None) on error
    """
    if not _sd_card or not _sd_card.mounted:
        print("[SD] Cannot create log file - SD card not mounted")
        return (None, None)
    
    try:
        filepath = _sd_card.create_session_filename(extension)
        
        # Open file for writing
        log_file = open(filepath, 'w' if extension == 'csv' else 'wb')
        
        # Extract just the filename
        filename = filepath.split('/')[-1]
        
        print(f"[SD] ✓ Created: {filename}")
        return (log_file, filename)
        
    except Exception as e:
        print(f"[SD] ✗ Create log file error: {e}")
        import traceback
        traceback.print_exception(e)
        return (None, None)


# Example usage:
"""
from sdcard import init_sdcard, create_log_file, get_sdcard

# Initialize
if init_sdcard():
    sd = get_sdcard()
    
    # Show info
    print(f"Free space: {sd.get_free_space_gb():.2f} GB")
    
    # List existing sessions
    sessions = sd.list_sessions()
    print(f"Found {len(sessions)} sessions")
    
    # Create new CSV log
    log_file, filename = create_log_file('csv')
    if log_file:
        log_file.write("timestamp,data\n")
        log_file.close()
    
    # Or create binary log
    log_file, filename = create_log_file('opl')
    if log_file:
        log_file.write(b'OPNY')
        log_file.close()
    
    # Get session statistics
    info = sd.get_session_info()
    print(f"Total sessions: {info['total_sessions']}")
    print(f"Total size: {info['total_size_mb']:.1f} MB")
"""
