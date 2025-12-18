#!/usr/bin/env python3
"""
opl2traccar.py - Upload OpenPonyLogger binary data to Traccar GPS tracking server

Reads .opl binary files and sends GPS positions to a Traccar server in real-time
or batch mode using the Traccar HTTP API (OsmAnd protocol).

Usage:
    python3 opl2traccar.py session_00001.opl
    python3 opl2traccar.py session_00001.opl --server traccar.example.com
    python3 opl2traccar.py session_00001.opl --device-id mustang-gt
    python3 opl2traccar.py session_00001.opl --realtime --speed 10
    python3 opl2traccar.py session_00001.opl --batch --batch-size 50

Traccar Setup:
    1. Install Traccar server: https://www.traccar.org/download/
    2. Default port: 5055 (OsmAnd protocol)
    3. Add device in Traccar web UI with unique identifier
    4. Use that identifier as --device-id
"""

import argparse
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Import from shared modules
from opl_types import (
    SAMPLE_TYPE_GPS_FIX,
    OPLTimestamp,
    UnitConverter
)
from opl2csv import OPLReader

class TraccarUploader:
    """Upload GPS data to Traccar server"""
    
    def __init__(self, server='localhost', port=5055, device_id='openponylogger', 
                 use_https=False, verbose=False):
        """
        Initialize Traccar uploader
        
        Args:
            server: Traccar server hostname or IP
            port: Traccar port (default 5055 for OsmAnd protocol)
            device_id: Unique device identifier
            use_https: Use HTTPS instead of HTTP
            verbose: Enable debug output
        """
        self.server = server
        self.port = port
        self.device_id = device_id
        self.protocol = 'https' if use_https else 'http'
        self.verbose = verbose
        self.base_url = f"{self.protocol}://{self.server}:{self.port}"
        
        # Track statistics
        self.points_sent = 0
        self.points_failed = 0
        self.start_time = None
        
    def log(self, msg):
        """Print message if verbose enabled"""
        if self.verbose:
            print(f"[Traccar] {msg}")
    
    def test_connection(self):
        """Test connection to Traccar server"""
        try:
            # Try to connect to the server
            response = requests.get(f"{self.protocol}://{self.server}:{self.port}", timeout=5)
            self.log(f"✓ Connected to Traccar server at {self.server}:{self.port}")
            return True
        except requests.exceptions.ConnectionError:
            print(f"✗ Cannot connect to Traccar server at {self.server}:{self.port}")
            print(f"  Make sure Traccar is running and accessible")
            return False
        except requests.exceptions.Timeout:
            print(f"✗ Connection timeout to {self.server}:{self.port}")
            return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def send_position(self, lat, lon, timestamp_dt, altitude=0, speed=0, heading=0, hdop=0):
        """
        Send a single GPS position to Traccar using OsmAnd protocol
        
        OsmAnd protocol URL format:
        http://server:port/?id=device_id&timestamp=unix_timestamp&lat=latitude&lon=longitude
        &altitude=meters&speed=knots&bearing=degrees&hdop=value
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            timestamp_dt: datetime object (with timezone)
            altitude: Altitude in meters
            speed: Speed in knots (Traccar uses knots)
            heading: Heading in degrees (0-360)
            hdop: Horizontal dilution of precision
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert timestamp to Unix timestamp (seconds since 1970-01-01)
            unix_timestamp = int(timestamp_dt.timestamp())
            
            # Build parameters (OsmAnd protocol)
            params = {
                'id': self.device_id,
                'timestamp': unix_timestamp,
                'lat': f"{lat:.8f}",
                'lon': f"{lon:.8f}",
                'altitude': f"{altitude:.1f}",
                'speed': f"{speed:.2f}",  # Should be in knots
                'bearing': f"{heading:.1f}",
                'hdop': f"{hdop:.2f}",
            }
            
            # Send HTTP GET request
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                self.points_sent += 1
                self.log(f"✓ Sent position: {lat:.6f}, {lon:.6f} @ {timestamp_dt.isoformat()}")
                return True
            else:
                self.points_failed += 1
                self.log(f"✗ Failed (HTTP {response.status_code}): {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.points_failed += 1
            self.log(f"✗ Network error: {e}")
            return False
        except Exception as e:
            self.points_failed += 1
            self.log(f"✗ Error: {e}")
            return False
    
    def upload_opl_file(self, opl_file, realtime=False, playback_speed=1.0, 
                       batch_mode=False, batch_size=10, drop_bad_time=False,
                       patch_time_jumps=False, time_threshold=946684800000000,
                       jump_threshold=60.0):
        """
        Upload all GPS positions from an OPL file to Traccar
        
        Args:
            opl_file: Path to .opl file
            realtime: Simulate realtime playback with delays
            playback_speed: Speed multiplier (1.0=realtime, 2.0=2x speed, 0.5=half speed)
            batch_mode: Send positions in batches with progress updates
            batch_size: Number of positions per batch
            drop_bad_time: Drop samples with timestamps below threshold
            patch_time_jumps: Smooth out large time jumps
            time_threshold: Minimum valid timestamp (microseconds)
            jump_threshold: Maximum time jump to allow (seconds)
        
        Returns:
            Number of positions successfully uploaded
        """
        self.start_time = time.time()
        
        # Read OPL file
        print(f"\nReading: {opl_file}")
        reader = OPLReader(opl_file, verbose=self.verbose)
        header, blocks = reader.read_all()
        
        print(f"\nSession: {header['session_name']}")
        print(f"Driver: {header['driver_name']}")
        print(f"Vehicle: {header['vehicle_id']}")
        print(f"Date: {header['timestamp']}")
        print(f"Device ID: {self.device_id}")
        print(f"Server: {self.base_url}")
        print()
        
        # Extract all GPS samples
        gps_samples = []
        for block in blocks:
            for sample in block['samples']:
                if sample['type'] == 'gps':
                    gps_samples.append(sample)
        
        if not gps_samples:
            print("✗ No GPS data found in file")
            return 0
        
        print(f"Found {len(gps_samples)} GPS positions")
        
        # Filter and patch timestamps if requested
        if drop_bad_time or patch_time_jumps:
            gps_samples = self._process_timestamps(
                gps_samples, drop_bad_time, patch_time_jumps,
                time_threshold, jump_threshold
            )
            print(f"After filtering: {len(gps_samples)} GPS positions to upload")
        
        print()
        
        # Upload positions
        last_timestamp = None
        batch_count = 0
        
        for i, sample in enumerate(gps_samples, 1):
            # Convert microseconds to datetime (Unix epoch 1970-01-01)
            timestamp_us = sample['timestamp_us']
            timestamp_dt = OPLTimestamp.to_datetime(timestamp_us, tz=timezone.utc)
            
            # Convert speed from MPH to knots (Traccar expects knots)
            speed_mph = sample['speed']
            speed_knots = UnitConverter.mph_to_knots(speed_mph)
            
            # Send position
            success = self.send_position(
                lat=sample['lat'],
                lon=sample['lon'],
                timestamp_dt=timestamp_dt,
                altitude=sample['alt'],
                speed=speed_knots,
                heading=sample['heading'],
                hdop=sample['hdop']
            )
            
            # Progress update in batch mode
            if batch_mode and i % batch_size == 0:
                batch_count += 1
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(gps_samples) - i) / rate if rate > 0 else 0
                print(f"Progress: {i}/{len(gps_samples)} ({i*100//len(gps_samples)}%) - "
                      f"{rate:.1f} pts/sec - ETA: {remaining:.0f}s")
            
            # Realtime playback simulation
            if realtime and last_timestamp is not None:
                # Calculate time difference
                time_diff_us = timestamp_us - last_timestamp
                time_diff_sec = time_diff_us / 1_000_000
                
                # Apply playback speed and sleep
                sleep_time = time_diff_sec / playback_speed
                if sleep_time > 0:
                    time.sleep(min(sleep_time, 10))  # Cap at 10 seconds
            
            last_timestamp = timestamp_us
        
        # Final statistics
        elapsed = time.time() - self.start_time
        print(f"\n{'='*60}")
        print(f"Upload Complete!")
        print(f"{'='*60}")
        print(f"Sent:     {self.points_sent} positions")
        print(f"Failed:   {self.points_failed} positions")
        print(f"Time:     {elapsed:.1f} seconds")
        print(f"Rate:     {self.points_sent/elapsed:.1f} positions/second")
        print(f"\nView track in Traccar web UI:")
        print(f"  {self.protocol}://{self.server}:8082")
        print(f"  (Default login: admin / admin)")
        print()
        
        return self.points_sent
    
    def _process_timestamps(self, samples, drop_bad_time, patch_time_jumps,
                           time_threshold, jump_threshold):
        """
        Filter and patch timestamps (same as opl2csv.py)
        
        Args:
            samples: List of sample dictionaries
            drop_bad_time: Drop samples below threshold
            patch_time_jumps: Smooth out time jumps
            time_threshold: Minimum valid timestamp (microseconds)
            jump_threshold: Maximum time jump (seconds)
        
        Returns:
            Processed list of samples
        """
        if not samples:
            return samples
        
        processed = []
        dropped_count = 0
        patched_count = 0
        
        # Step 1: Drop samples with bad timestamps
        if drop_bad_time:
            for sample in samples:
                if OPLTimestamp.is_rtc_synced(sample['timestamp_us']):
                    processed.append(sample)
                else:
                    dropped_count += 1
            
            if dropped_count > 0:
                print(f"  Dropped {dropped_count} GPS positions with bad timestamps")
            
            samples = processed
            processed = []
        
        # Step 2: Patch time jumps
        if patch_time_jumps and len(samples) > 0:
            # Convert jump threshold to microseconds
            jump_threshold_us = jump_threshold * 1_000_000
            
            last_timestamp = samples[0]['timestamp_us']
            time_offset = 0  # Accumulated offset from patching
            
            for sample in samples:
                current_timestamp = sample['timestamp_us']
                time_diff = current_timestamp - last_timestamp
                
                # Detect large forward jump (RTC sync)
                if time_diff > jump_threshold_us:
                    # Calculate offset needed to smooth this jump
                    time_offset = last_timestamp - current_timestamp
                    patched_count += 1
                    
                    if self.verbose:
                        jump_sec = time_diff / 1_000_000
                        print(f"  Detected time jump: {jump_sec:.1f}s at position {len(processed)}")
                
                # Apply accumulated offset
                patched_sample = sample.copy()
                patched_sample['timestamp_us'] = current_timestamp + time_offset
                processed.append(patched_sample)
                
                last_timestamp = patched_sample['timestamp_us']
            
            if patched_count > 0:
                print(f"  Patched {patched_count} time jumps > {jump_threshold}s")
        else:
            processed = samples
        
        return processed


def main():
    parser = argparse.ArgumentParser(
        description='Upload OpenPonyLogger GPS data to Traccar server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to local Traccar server
  %(prog)s session_00001.opl
  
  # Upload to remote server
  %(prog)s session_00001.opl --server gps.example.com --device-id mustang-gt
  
  # Realtime playback (1x speed)
  %(prog)s session_00001.opl --realtime
  
  # Fast playback (10x speed)
  %(prog)s session_00001.opl --realtime --speed 10
  
  # Batch upload with progress
  %(prog)s session_00001.opl --batch --batch-size 100
  
  # Use HTTPS
  %(prog)s session_00001.opl --server secure.example.com --https

Traccar Server Setup:
  1. Install: https://www.traccar.org/download/
  2. Start server: sudo systemctl start traccar
  3. Web UI: http://localhost:8082 (admin/admin)
  4. Add device with unique identifier
  5. Note: OsmAnd protocol uses port 5055 by default
        """
    )
    
    parser.add_argument('input', help='Input .opl file')
    parser.add_argument('-s', '--server', default='localhost',
                       help='Traccar server hostname/IP (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=5055,
                       help='Traccar port (default: 5055 for OsmAnd protocol)')
    parser.add_argument('-d', '--device-id', default='openponylogger',
                       help='Device identifier (default: openponylogger)')
    parser.add_argument('--https', action='store_true',
                       help='Use HTTPS instead of HTTP')
    parser.add_argument('-r', '--realtime', action='store_true',
                       help='Simulate realtime playback with delays')
    parser.add_argument('--speed', type=float, default=1.0,
                       help='Playback speed multiplier (default: 1.0)')
    parser.add_argument('-b', '--batch', action='store_true',
                       help='Batch mode with progress updates')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Positions per batch update (default: 10)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output (show each position sent)')
    parser.add_argument('--test', action='store_true',
                       help='Test connection to Traccar server only')
    parser.add_argument('--drop-bad-time', action='store_true',
                       help='Drop GPS positions with unrealistic timestamps (before RTC sync)')
    parser.add_argument('--patch-time-jumps', action='store_true',
                       help='Smooth out large timestamp jumps (e.g., RTC sync during session)')
    parser.add_argument('--time-threshold', type=int, default=946684800000000,
                       help='Minimum valid timestamp in microseconds since Unix epoch (default: Jan 1 2000)')
    parser.add_argument('--jump-threshold', type=float, default=60.0,
                       help='Time jump threshold in seconds for patching (default: 60.0)')
    
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ File not found: {input_path}")
        return 1
    
    # Create uploader
    uploader = TraccarUploader(
        server=args.server,
        port=args.port,
        device_id=args.device_id,
        use_https=args.https,
        verbose=args.verbose
    )
    
    # Test connection
    print(f"Testing connection to Traccar server...")
    if not uploader.test_connection():
        print("\nTroubleshooting:")
        print("  1. Is Traccar server running?")
        print("  2. Check firewall (port 5055 must be open)")
        print("  3. Verify server address and port")
        print("  4. Try: sudo systemctl status traccar")
        return 1
    
    if args.test:
        print("✓ Connection test successful")
        return 0
    
    # Upload file
    try:
        points_sent = uploader.upload_opl_file(
            input_path,
            realtime=args.realtime,
            playback_speed=args.speed,
            batch_mode=args.batch,
            batch_size=args.batch_size,
            drop_bad_time=args.drop_bad_time,
            patch_time_jumps=args.patch_time_jumps,
            time_threshold=args.time_threshold,
            jump_threshold=args.jump_threshold
        )
        
        return 0 if points_sent > 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠ Upload cancelled by user")
        print(f"Sent {uploader.points_sent} positions before cancellation")
        return 130
    except Exception as e:
        print(f"\n✗ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
