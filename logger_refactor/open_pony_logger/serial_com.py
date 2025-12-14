"""
serial_com.py - JSON Protocol Handler for OpenPonyLogger
"""

import json
import time
from storage import FileManager

class JSONProtocol:
    """Handle JSON commands from ESP-01S"""
    
    def __init__(self, uart, session, gps):
        self.uart = uart
        self.session = session
        self.gps = gps
        self.buffer = ""
        self.chunk_size = 512
    
    def process(self):
        """Check for incoming commands"""
        if self.uart.in_waiting:
            try:
                # Read available bytes
                data = self.uart.read(self.uart.in_waiting)
                
                # Decode with error handling
                try:
                    decoded = data.decode('utf-8')
                except UnicodeError:
                    # Try with 'ignore' error handler
                    decoded = data.decode('utf-8', 'ignore')
                    print("Warning: Ignored invalid UTF-8 bytes")
                
                self.buffer += decoded
                
                # Process complete JSON objects (newline delimited)
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        self.handle_line(line)
                        
            except Exception as e:
                print(f"Serial process error: {e}")
                # Clear buffer on error
                self.buffer = ""
    
    def handle_line(self, line):
        """Process a single line of JSON"""
        try:
            cmd = json.loads(line)
            self.handle_command(cmd)
        except ValueError as e:
            # JSON decode error
            print(f"JSON decode error: {e}")
            print(f"Invalid JSON: {line[:50]}...")  # Show first 50 chars
        except Exception as e:
            print(f"Line handling error: {e}")
    
    def handle_command(self, cmd):
        """Execute command"""
        try:
            cmd_type = cmd.get("cmd", "")
            
            if cmd_type == "LIST":
                self.send_file_list()
            
            elif cmd_type == "GET":
                filename = cmd.get("file", "")
                if filename:
                    self.send_file(filename)
                else:
                    self.send_error("Missing file parameter")
            
            elif cmd_type == "DELETE":
                filename = cmd.get("file", "")
                if filename:
                    success = FileManager.delete_file(filename)
                    if success:
                        self.send_response({"type": "ok", "message": "File deleted"})
                    else:
                        self.send_error("Delete failed")
                else:
                    self.send_error("Missing file parameter")
            
            elif cmd_type == "START_SESSION":
                driver = cmd.get("driver", "Unknown")
                vin = cmd.get("vin", "Unknown")
                filename = self.session.start(driver, vin)
                self.send_response({
                    "type": "ok",
                    "message": "Session started",
                    "file": filename
                })
            
            elif cmd_type == "STOP_SESSION":
                if self.session.active:
                    filename = self.session.stop()
                    self.send_response({
                        "type": "ok",
                        "message": "Session stopped",
                        "file": filename
                    })
                else:
                    self.send_error("No active session")
            
            elif cmd_type == "GET_SATELLITES":
                self.send_satellites()
            
            else:
                print(f"Unknown command: {cmd_type}")
                
        except Exception as e:
            print(f"Command handling error: {e}")
            self.send_error(f"Error: {e}")
    
    def send_file_list(self):
        """Send list of session files"""
        try:
            files = FileManager.list_files()[-5:]
            response = {
                "type": "files",
                "count": len(files),
                "files": files
            }
            self.send_json(response)
        except Exception as e:
            print(f"File list error: {e}")
            self.send_error(f"List error: {e}")
    
    def send_file(self, filename):
        """Send file contents in chunks"""
        filepath = f"/sd/{filename}"
        
        try:
            stat = os.stat(filepath)
            file_size = stat[6]
            
            # Send file start
            self.send_json({
                "type": "file_start",
                "file": filename,
                "size": file_size
            })
            
            # Send file data in chunks
            with open(filepath, 'r') as f:
                chunk_num = 0
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    self.send_json({
                        "type": "file_chunk",
                        "file": filename,
                        "chunk": chunk_num,
                        "data": chunk
                    })
                    chunk_num += 1
                    time.sleep(0.05)  # Small delay between chunks
            
            # Send file end
            self.send_json({
                "type": "file_end",
                "file": filename,
                "chunks": chunk_num
            })
            
        except OSError as e:
            print(f"File error: {e}")
            self.send_error(f"File error: {e}")
        except Exception as e:
            print(f"Send file error: {e}")
            self.send_error(f"Error: {e}")
    
    def send_satellites(self):
        """Send satellite data"""
        try:
            self.send_json(self.gps.get_satellites_json())
        except Exception as e:
            print(f"Satellite send error: {e}")
    
    def send_response(self, response):
        """Send generic response"""
        self.send_json(response)
    
    def send_error(self, message):
        """Send error response"""
        try:
            self.send_json({
                "type": "error",
                "message": str(message)
            })
        except Exception as e:
            print(f"Error sending error: {e}")
    
    def send_json(self, obj):
        """Send JSON object"""
        try:
            json_str = json.dumps(obj) + "\n"
            self.uart.write(json_str.encode('utf-8'))
        except Exception as e:
            print(f"JSON send error: {e}")

    def send_telemetry(self, data):
        """Send JSON update message to ESP"""
        msg = {
            "type": "update",
            "data": data
        }
        self.send_json(msg)
