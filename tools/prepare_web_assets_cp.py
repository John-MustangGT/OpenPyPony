#!/usr/bin/env python3
"""
prepare_web_assets_cp.py - Prepare compressed web assets for CircuitPython

This script creates gzip-compressed versions of web files that can be
copied directly to the CIRCUITPY drive and served with proper headers.

Usage:
    python3 prepare_web_assets_cp.py web/ output/
    
Then copy output/* to CIRCUITPY:/web/
"""

import gzip
import sys
import os
import shutil
from pathlib import Path

def compress_file(input_path, output_path):
    """Compress a file using gzip level 9"""
    with open(input_path, 'rb') as f_in:
        with gzip.open(output_path, 'wb', compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    original_size = os.path.getsize(input_path)
    compressed_size = os.path.getsize(output_path)
    ratio = (1 - compressed_size / original_size) * 100
    
    print(f"  {input_path.name}:")
    print(f"    Original:    {original_size:6,d} bytes")
    print(f"    Compressed:  {compressed_size:6,d} bytes")
    print(f"    Savings:     {ratio:5.1f}%")
    
    return original_size, compressed_size

def prepare_web_assets(input_dir, output_dir):
    """Prepare all web assets for CircuitPython"""
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Files to process
    web_files = [
        'index.html',
        'styles.css',
        'app.js',
    ]
    
    print("Preparing web assets for CircuitPython...")
    print()
    
    total_original = 0
    total_compressed = 0
    
    for filename in web_files:
        input_file = input_path / filename
        
        if not input_file.exists():
            print(f"Warning: {input_file} not found, skipping")
            continue
        
        # Copy original (for fallback)
        output_original = output_path / filename
        shutil.copy2(input_file, output_original)
        
        # Create compressed version
        output_compressed = output_path / f"{filename}.gz"
        orig_size, comp_size = compress_file(input_file, output_compressed)
        
        total_original += orig_size
        total_compressed += comp_size
        print()
    
    # Create asset mapping file for CircuitPython
    create_asset_map(output_path, web_files)
    
    # Summary
    print("=" * 60)
    print(f"Total original:    {total_original:6,d} bytes")
    print(f"Total compressed:  {total_compressed:6,d} bytes")
    print(f"Total savings:     {(1 - total_compressed/total_original)*100:5.1f}%")
    print(f"Space saved:       {total_original - total_compressed:6,d} bytes")
    print("=" * 60)
    print()
    print(f"✅ Assets prepared in: {output_path}")
    print()
    print("Next steps:")
    print(f"  1. Copy {output_path}/* to CIRCUITPY:/web/")
    print("  2. Copy web_server_gz.py to CIRCUITPY:/")
    print("  3. Restart Pico (auto-reloads code.py)")
    
def create_asset_map(output_path, web_files):
    """Create Python module with asset mappings"""
    
    map_file = output_path / 'asset_map.py'
    
    with open(map_file, 'w') as f:
        f.write('"""Asset mapping for web server"""\n\n')
        f.write('ASSETS = {\n')
        
        for filename in web_files:
            # Determine MIME type
            if filename.endswith('.html'):
                mime = 'text/html'
            elif filename.endswith('.css'):
                mime = 'text/css'
            elif filename.endswith('.js'):
                mime = 'application/javascript'
            else:
                mime = 'application/octet-stream'
            
            # Add entries for both / paths
            if filename == 'index.html':
                f.write(f'    "/": {{\n')
                f.write(f'        "file": "{filename}",\n')
                f.write(f'        "mime": "{mime}",\n')
                f.write(f'        "gzip": "{filename}.gz"\n')
                f.write(f'    }},\n')
            
            f.write(f'    "/{filename}": {{\n')
            f.write(f'        "file": "{filename}",\n')
            f.write(f'        "mime": "{mime}",\n')
            f.write(f'        "gzip": "{filename}.gz"\n')
            f.write(f'    }},\n')
        
        f.write('}\n')
    
    print(f"Created asset map: {map_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 prepare_web_assets_cp.py <input_dir> <output_dir>")
        print("Example: python3 prepare_web_assets_cp.py web/ web_compressed/")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)
    
    prepare_web_assets(input_dir, output_dir)
