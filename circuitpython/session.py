"""
session.py - Session Management

Handles session numbering, file naming, and session lifecycle.
Maintains session_last.txt for sequential numbering.
"""

import os


class SessionManager:
    """
    Manages logging sessions
    
    Handles:
    - Sequential session numbering
    - Session file creation (session_XXXXX.opl)
    - Persistence of last session number
    """
    
    def __init__(self, storage, base_path='/sd'):
        """
        Initialize session manager
        
        Args:
            storage: StorageInterface object
            base_path: Base path for session files
        """
        self.storage = storage
        self.base_path = base_path
        self.session_file_path = f"{base_path}/session_last.txt"
        
        self.current_session = 0
        self.current_filename = None
        
        print("[Session] Initialized")
    
    def load_last_session(self):
        """
        Load last session number from persistent storage
        
        Returns:
            int: Last session number (0 if none)
        """
        if not self.storage or not self.storage.is_mounted():
            print("[Session] Warning: Storage not available")
            return 0
        
        try:
            with open(self.session_file_path, 'r') as f:
                last = int(f.read().strip())
                print(f"[Session] Loaded last session: {last}")
                return last
        except (OSError, ValueError):
            print("[Session] No previous session found, starting at 0")
            return 0
    
    def save_session_number(self, session_num):
        """
        Save session number to persistent storage
        
        Args:
            session_num: Session number to save
        """
        if not self.storage or not self.storage.is_mounted():
            print("[Session] Warning: Cannot save session number (no storage)")
            return
        
        try:
            with open(self.session_file_path, 'w') as f:
                f.write(str(session_num))
            print(f"[Session] Saved session number: {session_num}")
        except OSError as e:
            print(f"[Session] Error saving session number: {e}")
    
    def start_new_session(self):
        """
        Start a new session
        
        Increments session counter and creates new filename.
        
        Returns:
            str: Session filename (e.g., 'session_00042.opl')
        """
        # Load last session and increment
        last_session = self.load_last_session()
        self.current_session = last_session + 1
        
        # Generate filename
        self.current_filename = f"session_{self.current_session:05d}.opl"
        
        # Save new session number
        self.save_session_number(self.current_session)
        
        print(f"[Session] Started new session: {self.current_filename}")
        
        return self.current_filename
    
    def get_session_path(self):
        """
        Get full path to current session file
        
        Returns:
            str: Full path (e.g., '/sd/session_00042.opl')
        """
        if not self.current_filename:
            return None
        return f"{self.base_path}/{self.current_filename}"
    
    def get_session_number(self):
        """
        Get current session number
        
        Returns:
            int: Current session number
        """
        return self.current_session
    
    def list_sessions(self, limit=10):
        """
        List recent session files
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            list: List of session filenames (most recent first)
        """
        if not self.storage or not self.storage.is_mounted():
            return []
        
        try:
            files = os.listdir(self.base_path)
            session_files = [f for f in files if f.startswith('session_') and f.endswith('.opl')]
            session_files.sort(reverse=True)
            return session_files[:limit]
        except OSError:
            return []
    
    def get_session_info(self, filename):
        """
        Get information about a session file
        
        Args:
            filename: Session filename
            
        Returns:
            dict: Session info (size, etc.) or None
        """
        if not self.storage or not self.storage.is_mounted():
            return None
        
        try:
            path = f"{self.base_path}/{filename}"
            stat = os.stat(path)
            
            return {
                'filename': filename,
                'size': stat[6],  # File size in bytes
                'session_num': self._extract_session_number(filename)
            }
        except OSError:
            return None
    
    def _extract_session_number(self, filename):
        """
        Extract session number from filename
        
        Args:
            filename: Session filename (e.g., 'session_00042.opl')
            
        Returns:
            int: Session number or 0
        """
        try:
            # Extract number from 'session_XXXXX.opl'
            num_str = filename.replace('session_', '').replace('.opl', '')
            return int(num_str)
        except ValueError:
            return 0
    
    def delete_session(self, filename):
        """
        Delete a session file
        
        Args:
            filename: Session filename to delete
            
        Returns:
            bool: True if deleted successfully
        """
        if not self.storage or not self.storage.is_mounted():
            return False
        
        try:
            path = f"{self.base_path}/{filename}"
            os.remove(path)
            print(f"[Session] Deleted: {filename}")
            return True
        except OSError as e:
            print(f"[Session] Delete failed: {e}")
            return False
