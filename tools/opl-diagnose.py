#!/usr/bin/env python3
"""
opl-diagnose.py - Diagnose problematic OPL files

Shows raw hex data and attempts to identify where parsing fails.
"""

import sys
import struct
from pathlib import Path

def diagnose_opl_file(filepath):
    """Diagnose OPL file structure"""
    print(f"\n{'='*60}")
    print(f"Diagnosing: {filepath}")
    print(f"{'='*60}\n")
    
    with open(filepath, 'rb') as f:
        # Check file size
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)
        print(f"File size: {file_size:,} bytes\n")
        
        # Read magic bytes
        print("MAGIC BYTES (offset 0):")
        magic = f.read(4)
        print(f"  Hex:    {magic.hex(' ')}")
        print(f"  ASCII:  {repr(magic)}")
        print(f"  Valid:  {magic == b'OPNY'}")
        print()
        
        if magic != b'OPNY':
            print("✗ Invalid magic bytes - not a valid OPL file!")
            return
        
        # Read block type
        print("BLOCK TYPE (offset 4):")
        block_type = struct.unpack('<B', f.read(1))[0]
        print(f"  Value: {block_type:#04x} ({block_type})")
        print(f"  Expected: 0x01 (SESSION_HEADER)")
        print()
        
        # Read format version
        print("FORMAT VERSION (offset 5):")
        major, minor = struct.unpack('<BB', f.read(2))
        print(f"  Version: {major}.{minor}")
        print()
        
        # Read hardware version
        print("HARDWARE VERSION (offset 7):")
        hw_major, hw_minor = struct.unpack('<BB', f.read(2))
        print(f"  Version: {hw_major}.{hw_minor}")
        print()
        
        # Read timestamp
        print("TIMESTAMP (offset 9):")
        timestamp_us = struct.unpack('<Q', f.read(8))[0]
        print(f"  Microseconds: {timestamp_us:,}")
        if timestamp_us > 946684800000000:  # Year 2000+
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp_us / 1_000_000)
            print(f"  Datetime: {dt}")
        else:
            print(f"  Duration: {timestamp_us / 1_000_000:.1f} seconds (monotonic)")
        print()
        
        # Read session ID
        print("SESSION ID (offset 17):")
        session_id = f.read(16)
        print(f"  Hex: {session_id.hex()}")
        print()
        
        # Read session name
        print("SESSION NAME (offset 33):")
        name_len = struct.unpack('<B', f.read(1))[0]
        print(f"  Length: {name_len} bytes")
        name_bytes = f.read(name_len)
        print(f"  Hex:    {name_bytes.hex(' ')}")
        print(f"  Raw:    {repr(name_bytes)}")
        try:
            name = name_bytes.decode('utf-8')
            print(f"  UTF-8:  '{name}'")
        except UnicodeDecodeError as e:
            print(f"  UTF-8:  ✗ DECODE ERROR: {e}")
            try:
                name = name_bytes.decode('latin-1')
                print(f"  Latin-1: '{name}'")
            except:
                pass
        print()
        
        # Read driver name
        offset = 34 + name_len
        print(f"DRIVER NAME (offset {offset}):")
        driver_len = struct.unpack('<B', f.read(1))[0]
        print(f"  Length: {driver_len} bytes")
        driver_bytes = f.read(driver_len)
        print(f"  Hex:    {driver_bytes.hex(' ')}")
        print(f"  Raw:    {repr(driver_bytes)}")
        try:
            driver = driver_bytes.decode('utf-8')
            print(f"  UTF-8:  '{driver}'")
        except UnicodeDecodeError as e:
            print(f"  UTF-8:  ✗ DECODE ERROR: {e}")
            try:
                driver = driver_bytes.decode('latin-1')
                print(f"  Latin-1: '{driver}'")
            except:
                pass
        print()
        
        # Read vehicle ID
        offset += 1 + driver_len
        print(f"VEHICLE ID (offset {offset}):")
        vehicle_len = struct.unpack('<B', f.read(1))[0]
        print(f"  Length: {vehicle_len} bytes")
        vehicle_bytes = f.read(vehicle_len)
        print(f"  Hex:    {vehicle_bytes.hex(' ')}")
        print(f"  Raw:    {repr(vehicle_bytes)}")
        try:
            vehicle = vehicle_bytes.decode('utf-8')
            print(f"  UTF-8:  '{vehicle}'")
        except UnicodeDecodeError as e:
            print(f"  UTF-8:  ✗ DECODE ERROR: {e}")
            try:
                vehicle = vehicle_bytes.decode('latin-1')
                print(f"  Latin-1: '{vehicle}'")
            except:
                pass
        print()
        
        # Show next 64 bytes for context
        print("NEXT 64 BYTES (weather, temp, CRCs):")
        next_bytes = f.read(64)
        for i in range(0, len(next_bytes), 16):
            chunk = next_bytes[i:i+16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"  {hex_str:48s}  {ascii_str}")
        print()
        
        print(f"Current offset: {f.tell()} / {file_size} bytes")
        print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 opl-diagnose.py session.opl")
        sys.exit(1)
    
    for filepath in sys.argv[1:]:
        try:
            diagnose_opl_file(filepath)
        except Exception as e:
            print(f"\n✗ Error diagnosing {filepath}:")
            print(f"  {e}")
            import traceback
            traceback.print_exc()
