#!/usr/bin/env python3
"""Test OPL parsing with real file"""

import sys
sys.path.insert(0, '/mnt/user-data/outputs')

from opl2csv import OPLReader

if len(sys.argv) < 2:
    print("Usage: python3 test_parse.py session.opl")
    sys.exit(1)

filepath = sys.argv[1]
print(f"Testing parse of: {filepath}\n")

try:
    reader = OPLReader(filepath, verbose=True)
    header, blocks = reader.read_all()
    
    print("\n" + "="*60)
    print("SUCCESS!")
    print("="*60)
    print(f"\nSession: {header['session_name']}")
    print(f"Driver: {header['driver_name']}")
    print(f"Vehicle: {header['vehicle_id']}")
    print(f"Blocks: {len(blocks)}")
    
    total_samples = sum(len(b['samples']) for b in blocks)
    print(f"Total samples: {total_samples}")
    
except Exception as e:
    print("\n" + "="*60)
    print("PARSE FAILED!")
    print("="*60)
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
