#!/usr/bin/env python3
"""
opl2csv.py - OpenPonyLogger Binary Format to CSV Converter

Converts .opl binary session files to human-readable CSV format.

Usage:
    python3 opl2csv.py session_00001.opl
    python3 opl2csv.py session_00001.opl -o output.csv
    python3 opl2csv.py session_00001.opl --verbose
"""

import struct
import sys
import argparse
from pathlib import Path
from datetime import datetime
import hashlib

# Magic bytes and constants
MAGIC_BYTES = b'OPNY'
FORMAT_VERSION_MAJOR = 2
FORMAT_VERSION_MINOR = 0

# Block types
BLOCK_TYPE_SESSION_HEADER = 0x01
BLOCK_TYPE_DATA_BLOCK = 0x02
BLOCK_TYPE_SESSION_END = 0x03
BLOCK_TYPE_HARDWARE_CONFIG = 0x04

# Hardware types
HW_TYPE_MAP = {
    0x01: "Accelerometer",
    0x02: "GPS",
    0x03: "Display",
    0x04: "Storage",
    0x05: "RTC",
    0x06: "LED",
    0x07: "NeoPixel",
    0x08: "Radio",
    0x09: "OBD",
    0x0A: "CAN"
}

# Connection types
CONN_TYPE_MAP = {
    0x01: "I2C",
    0x02: "SPI",
    0x03: "UART",
    0x04: "GPIO",
    0x05: "STEMMA QT",
    0x06: "Built-in"
}

# Sample types
SAMPLE_TYPE_ACCELEROMETER = 0x01
SAMPLE_TYPE_GPS_FIX = 0x02
SAMPLE_TYPE_GPS_SATELLITES = 0x03
SAMPLE_TYPE_OBD_PID = 0x10
SAMPLE_TYPE_EVENT_MARKER = 0x20

# Weather conditions
WEATHER_MAP = {
    0: "Unknown",
    1: "Clear",
    2: "Cloudy",
    3: "Rain",
    4: "Snow",
    5: "Fog"
}

# Flush flags
FLUSH_FLAG_TIME = 0x01
FLUSH_FLAG_SIZE = 0x02
FLUSH_FLAG_EVENT = 0x04
FLUSH_FLAG_MANUAL = 0x08
FLUSH_FLAG_SHUTDOWN = 0x10


class OPLReader:
    """OpenPonyLogger binary file reader"""
    
    def __init__(self, filepath, verbose=False):
        self.filepath = Path(filepath)
        self.verbose = verbose
        self.file = None
        self.session_header = None
        self.hardware_config = None
        self.data_blocks = []
        
    def log(self, msg):
        """Print message if verbose enabled"""
        if self.verbose:
            print(f"[OPL] {msg}")
    
    def read_session_header(self):
        """Read and parse session header block"""
        # Read magic bytes FIRST (this matches binary_logger.py write order)
        magic = self.file.read(4)
        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes: {magic.hex()} (expected {MAGIC_BYTES.hex()})")
        
        # Read block type SECOND
        block_type = struct.unpack('<B', self.file.read(1))[0]
        if block_type != BLOCK_TYPE_SESSION_HEADER:
            raise ValueError(f"Expected session header block, got {block_type:#x}")
        
        # Read format version (2 bytes: major, minor)
        major, minor = struct.unpack('<BB', self.file.read(2))
        self.log(f"Format version: {major}.{minor}")
        
        # Read hardware version (2 bytes: major, minor)
        hw_major, hw_minor = struct.unpack('<BB', self.file.read(2))
        hw_version = f"{hw_major}.{hw_minor}"
        self.log(f"Hardware version: {hw_version}")
        
        # Read timestamp (microseconds since epoch)
        timestamp_us = struct.unpack('<Q', self.file.read(8))[0]
        # Convert to datetime (CircuitPython epoch is 2000-01-01)
        epoch_2000 = datetime(2000, 1, 1)
        timestamp = epoch_2000.timestamp() + (timestamp_us / 1_000_000)
        timestamp_dt = datetime.fromtimestamp(timestamp)
        self.log(f"Session start: {timestamp_dt}")
        
        # Read session ID (16 bytes UUID)
        session_id = self.file.read(16).hex()
        self.log(f"Session ID: {session_id}")
        
        # Read session name (1 byte length + string)
        name_len = struct.unpack('<B', self.file.read(1))[0]
        session_name = self.file.read(name_len).decode('utf-8')
        
        # Read driver name (1 byte length + string)
        driver_len = struct.unpack('<B', self.file.read(1))[0]
        driver_name = self.file.read(driver_len).decode('utf-8')
        
        # Read vehicle ID (1 byte length + string)
        vehicle_len = struct.unpack('<B', self.file.read(1))[0]
        vehicle_id = self.file.read(vehicle_len).decode('utf-8')
        
        # Read weather condition
        weather_code = struct.unpack('<B', self.file.read(1))[0]
        weather = WEATHER_MAP.get(weather_code, "Unknown")
        
        # Read ambient temperature (0.1°C resolution)
        temp_raw = struct.unpack('<h', self.file.read(2))[0]
        ambient_temp = temp_raw / 10.0
        
        # Read config CRC32
        config_crc = struct.unpack('<I', self.file.read(4))[0]
        
        # Read header CRC32 (checksum of all header data)
        header_crc = struct.unpack('<I', self.file.read(4))[0]
        self.log(f"Header CRC: {header_crc:#010x}")
        
        # Debug: show file position
        file_pos = self.file.tell()
        self.log(f"File position after header: {file_pos} bytes")
        
        self.session_header = {
            'format_version': f"{major}.{minor}",
            'hw_version': hw_version,
            'timestamp': timestamp_dt,
            'session_id': session_id,
            'session_name': session_name,
            'driver_name': driver_name,
            'vehicle_id': vehicle_id,
            'weather': weather,
            'ambient_temp': ambient_temp,
            'config_crc': config_crc
        }
        
        return self.session_header
    
    def read_hardware_config(self):
        """
        Read hardware configuration block (optional)
        
        Returns:
            dict with hardware items or None if not present
        """
        # Peek at next block type
        pos = self.file.tell()
        magic = self.file.read(4)
        
        if magic != MAGIC_BYTES:
            # Restore position and return
            self.file.seek(pos)
            return None
        
        block_type = struct.unpack('B', self.file.read(1))[0]
        
        if block_type != BLOCK_TYPE_HARDWARE_CONFIG:
            # Not a hardware config block, restore position
            self.file.seek(pos)
            return None
        
        self.log("Reading hardware config block...")
        
        # Read number of items
        item_count = struct.unpack('B', self.file.read(1))[0]
        
        hardware_items = []
        for i in range(item_count):
            hw_type = struct.unpack('B', self.file.read(1))[0]
            conn_type = struct.unpack('B', self.file.read(1))[0]
            id_len = struct.unpack('B', self.file.read(1))[0]
            identifier = self.file.read(id_len).decode('utf-8')
            
            hardware_items.append({
                'type': HW_TYPE_MAP.get(hw_type, f"Unknown(0x{hw_type:02X})"),
                'connection': CONN_TYPE_MAP.get(conn_type, f"Unknown(0x{conn_type:02X})"),
                'identifier': identifier
            })
            
            self.log(f"  {hardware_items[-1]['type']}: {hardware_items[-1]['identifier']} ({hardware_items[-1]['connection']})")
        
        # Read and verify CRC
        crc_expected = struct.unpack('<I', self.file.read(4))[0]
        
        return {
            'items': hardware_items,
            'count': item_count,
            'crc': crc_expected
        }
        
        return self.session_header
    
    def read_data_block(self):
        """Read and parse a data block"""
        # Debug: show file position
        file_pos = self.file.tell()
        self.log(f"Attempting to read data block at position {file_pos}")
        
        # Read magic bytes
        magic_bytes = self.file.read(4)
        if not magic_bytes:
            self.log("EOF reached")
            return None  # EOF
        
        self.log(f"Read magic bytes: {magic_bytes.hex()}")
        
        if magic_bytes != MAGIC_BYTES:
            self.log(f"Invalid magic bytes in data block: {magic_bytes.hex()} (expected {MAGIC_BYTES.hex()})")
            return None
        
        # Read block type
        block_type = struct.unpack('<B', self.file.read(1))[0]
        
        if block_type == BLOCK_TYPE_SESSION_END:
            self.log("Reached session end block")
            return None
        
        if block_type != BLOCK_TYPE_DATA_BLOCK:
            self.log(f"Unknown block type: {block_type:#x}")
            return None
        
        # Read session ID
        session_id = self.file.read(16).hex()
        
        # Read block sequence number
        block_seq = struct.unpack('<I', self.file.read(4))[0]
        
        # Read timestamps
        timestamp_start_us = struct.unpack('<Q', self.file.read(8))[0]
        timestamp_end_us = struct.unpack('<Q', self.file.read(8))[0]
        
        # Read flush flags
        flush_flags = struct.unpack('<B', self.file.read(1))[0]
        
        # Read sample count and data size (both are 2 bytes)
        sample_count = struct.unpack('<H', self.file.read(2))[0]
        data_size = struct.unpack('<H', self.file.read(2))[0]
        
        # Read sample data
        sample_data = self.file.read(data_size)
        
        # Read checksum (CRC32 = 4 bytes, not SHA-256 = 32 bytes)
        checksum = self.file.read(4)
        checksum_value = struct.unpack('<I', checksum)[0] if len(checksum) == 4 else 0
        self.log(f"Block checksum: {checksum_value:#010x}")
        
        self.log(f"Block {block_seq}: {sample_count} samples, {data_size} bytes")
        
        # Parse samples
        samples = self.parse_samples(sample_data, timestamp_start_us)
        
        return {
            'block_seq': block_seq,
            'timestamp_start': timestamp_start_us,
            'timestamp_end': timestamp_end_us,
            'flush_flags': flush_flags,
            'samples': samples
        }
    
    def parse_samples(self, data, base_timestamp_us):
        """Parse packed sample data"""
        samples = []
        offset = 0
        
        while offset < len(data):
            if offset + 4 > len(data):
                break  # Not enough data for header
            
            # Read sample header: type (1) + timestamp_offset (2) + length (1)
            sample_type = struct.unpack('<B', data[offset:offset+1])[0]
            timestamp_offset = struct.unpack('<H', data[offset+1:offset+3])[0]
            sample_len = struct.unpack('<B', data[offset+3:offset+4])[0]
            offset += 4
            
            if offset + sample_len > len(data):
                break  # Not enough data for sample
            
            sample_data = data[offset:offset+sample_len]
            offset += sample_len
            
            # Calculate absolute timestamp
            timestamp_us = base_timestamp_us + timestamp_offset
            
            # Parse based on type
            if sample_type == SAMPLE_TYPE_ACCELEROMETER:
                # 3x float32 (12 bytes)
                if sample_len >= 12:
                    gx, gy, gz = struct.unpack('<fff', sample_data[:12])
                    samples.append({
                        'type': 'accel',
                        'timestamp_us': timestamp_us,
                        'gx': gx,
                        'gy': gy,
                        'gz': gz
                    })
            
            elif sample_type == SAMPLE_TYPE_GPS_FIX:
                # lat, lon, alt, speed, heading, hdop (6x float32 = 24 bytes)
                if sample_len >= 24:
                    lat, lon, alt, speed, heading, hdop = struct.unpack('<ffffff', sample_data[:24])
                    samples.append({
                        'type': 'gps',
                        'timestamp_us': timestamp_us,
                        'lat': lat,
                        'lon': lon,
                        'alt': alt,
                        'speed': speed,
                        'heading': heading,
                        'hdop': hdop
                    })
            
            elif sample_type == SAMPLE_TYPE_GPS_SATELLITES:
                # Variable length satellite data
                sat_count = sample_len // 3  # Each sat: id (1) + snr (1) + flags (1)
                satellites = []
                for i in range(sat_count):
                    sat_id, snr, flags = struct.unpack('<BBB', sample_data[i*3:i*3+3])
                    satellites.append({'id': sat_id, 'snr': snr, 'flags': flags})
                samples.append({
                    'type': 'satellites',
                    'timestamp_us': timestamp_us,
                    'satellites': satellites
                })
        
        return samples
    
    def read_all(self):
        """Read entire OPL file"""
        with open(self.filepath, 'rb') as f:
            self.file = f
            
            # Read session header
            self.session_header = self.read_session_header()
            
            # Try to read hardware config block (optional)
            self.hardware_config = self.read_hardware_config()
            
            # Read all data blocks
            while True:
                block = self.read_data_block()
                if block is None:
                    break
                self.data_blocks.append(block)
        
        self.log(f"Read {len(self.data_blocks)} data blocks")
        return self.session_header, self.data_blocks
    
    def to_csv(self, output_path=None):
        """Convert to CSV format"""
        if output_path is None:
            output_path = self.filepath.with_suffix('.csv')
        
        # Read file if not already read
        if not self.session_header:
            self.read_all()
        
        # Collect all samples
        all_samples = []
        for block in self.data_blocks:
            all_samples.extend(block['samples'])
        
        # Sort by timestamp
        all_samples.sort(key=lambda s: s['timestamp_us'])
        
        # Write CSV
        with open(output_path, 'w') as f:
            # Write header comments
            h = self.session_header
            f.write(f"# OpenPonyLogger Session Export\n")
            f.write(f"# Session: {h['session_name']}\n")
            f.write(f"# Driver: {h['driver_name']}\n")
            f.write(f"# Vehicle: {h['vehicle_id']}\n")
            f.write(f"# Date: {h['timestamp']}\n")
            f.write(f"# Weather: {h['weather']}, {h['ambient_temp']}°C\n")
            f.write(f"# Format: {h['format_version']}\n")
            f.write(f"# Hardware: {h['hw_version']}\n")
            
            # Write hardware configuration if present
            if self.hardware_config:
                f.write(f"#\n")
                f.write(f"# Hardware Configuration ({self.hardware_config['count']} items):\n")
                for item in self.hardware_config['items']:
                    f.write(f"#   {item['type']:<15} {item['connection']:<12} {item['identifier']}\n")
            
            f.write(f"#\n")
            
            # Write CSV header
            f.write("timestamp_us,type,gx,gy,gz,lat,lon,alt,speed,heading,hdop,satellites\n")
            
            # Write samples
            for sample in all_samples:
                timestamp = sample['timestamp_us']
                sample_type = sample['type']
                
                if sample_type == 'accel':
                    f.write(f"{timestamp},accel,{sample['gx']:.6f},{sample['gy']:.6f},{sample['gz']:.6f},,,,,,,\n")
                
                elif sample_type == 'gps':
                    f.write(f"{timestamp},gps,,,{sample['lat']:.8f},{sample['lon']:.8f},"
                           f"{sample['alt']:.2f},{sample['speed']:.2f},{sample['heading']:.2f},{sample['hdop']:.2f},\n")
                
                elif sample_type == 'satellites':
                    sat_list = ';'.join([f"{s['id']}:{s['snr']}" for s in sample['satellites']])
                    f.write(f"{timestamp},satellites,,,,,,,,,{sat_list}\n")
        
        print(f"✓ Converted to CSV: {output_path}")
        print(f"  Total samples: {len(all_samples)}")
        print(f"  Accelerometer: {sum(1 for s in all_samples if s['type'] == 'accel')}")
        print(f"  GPS fixes: {sum(1 for s in all_samples if s['type'] == 'gps')}")
        print(f"  Satellite data: {sum(1 for s in all_samples if s['type'] == 'satellites')}")
        
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Convert OpenPonyLogger binary (.opl) files to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s session_00001.opl
  %(prog)s session_00001.opl -o output.csv
  %(prog)s session_00001.opl --verbose
  %(prog)s *.opl  # Convert all OPL files
        """
    )
    
    parser.add_argument('input', nargs='+', help='Input .opl file(s)')
    parser.add_argument('-o', '--output', help='Output CSV file (default: same name as input)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Process each input file
    for input_file in args.input:
        input_path = Path(input_file)
        
        if not input_path.exists():
            print(f"✗ File not found: {input_path}")
            continue
        
        if not input_path.suffix == '.opl':
            print(f"⚠ Warning: {input_path} doesn't have .opl extension")
        
        print(f"\n{'='*60}")
        print(f"Converting: {input_path}")
        print(f"{'='*60}")
        
        try:
            reader = OPLReader(input_path, verbose=args.verbose)
            
            # Read and display header
            header, blocks = reader.read_all()
            
            print(f"\nSession Information:")
            print(f"  Name:     {header['session_name']}")
            print(f"  Driver:   {header['driver_name']}")
            print(f"  Vehicle:  {header['vehicle_id']}")
            print(f"  Date:     {header['timestamp']}")
            print(f"  Weather:  {header['weather']}, {header['ambient_temp']}°C")
            print(f"  Blocks:   {len(blocks)}")
            
            # Convert to CSV
            output_path = args.output if args.output else None
            reader.to_csv(output_path)
            
        except Exception as e:
            print(f"✗ Error processing {input_path}: {e}")
            import traceback
            if args.verbose:
                traceback.print_exc()
            else:
                print(f"  Run with --verbose for full traceback")
            continue
    
    print()


if __name__ == '__main__':
    main()
