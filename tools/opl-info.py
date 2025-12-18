#!/usr/bin/env python3
"""
opl-info.py - OpenPonyLogger Binary File Inspector

Analyze and validate .opl binary files without converting them.
Provides detailed information about session headers, data integrity,
timestamps, and sample statistics.

Usage:
    python3 opl-info.py session_00001.opl
    python3 opl-info.py session_00001.opl --no-session
    python3 opl-info.py session_00001.opl --no-hardware
    python3 opl-info.py session_00001.opl --verify-checksums
    python3 opl-info.py session_00001.opl --detailed
    python3 opl-info.py *.opl --brief
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import struct

# Import from shared opl_types module
from opl_types import (
    WEATHER_MAP,
    SAMPLE_TYPE_ACCELEROMETER,
    SAMPLE_TYPE_GPS_FIX,
    SAMPLE_TYPE_GPS_SATELLITES,
    SAMPLE_TYPE_OBD_PID,
    SAMPLE_TYPE_EVENT_MARKER,
    OPLTimestamp,
    format_duration
)

# Import OPL reader from opl2csv
try:
    from opl2csv import OPLReader
except ImportError:
    print("Error: opl2csv.py must be in the same directory")
    sys.exit(1)


class OPLInspector:
    """Inspect and analyze OPL files"""
    
    def __init__(self, filepath, verbose=False):
        self.filepath = Path(filepath)
        self.reader = OPLReader(filepath, verbose=verbose)
        self.verbose = verbose
        
        # Analysis results
        self.header = None
        self.blocks = None
        self.sample_stats = None
        self.time_stats = None
        self.integrity_issues = []
        
    def analyze(self):
        """Perform complete file analysis"""
        try:
            # Read file
            self.header, self.blocks = self.reader.read_all()
            
            # Analyze samples
            self._analyze_samples()
            
            # Analyze timestamps
            self._analyze_timestamps()
            
            # Check integrity
            self._check_integrity()
            
            return True
            
        except Exception as e:
            self.integrity_issues.append(f"Fatal error reading file: {e}")
            return False
    
    def _analyze_samples(self):
        """Analyze sample types and counts"""
        all_samples = []
        for block in self.blocks:
            all_samples.extend(block['samples'])
        
        # Count by type
        type_counts = Counter(s['type'] for s in all_samples)
        
        # Calculate sample rates (samples per second)
        total_time = self._get_session_duration_seconds()
        sample_rates = {}
        if total_time > 0:
            for sample_type, count in type_counts.items():
                sample_rates[sample_type] = count / total_time
        
        # Find data gaps
        gaps = self._find_data_gaps(all_samples)
        
        self.sample_stats = {
            'total': len(all_samples),
            'by_type': type_counts,
            'sample_rates': sample_rates,
            'gaps': gaps
        }
    
    def _analyze_timestamps(self):
        """Analyze timestamp validity and consistency"""
        all_samples = []
        for block in self.blocks:
            all_samples.extend(block['samples'])
        
        if not all_samples:
            self.time_stats = {'valid': False, 'reason': 'No samples'}
            return
        
        # Sort by timestamp
        all_samples.sort(key=lambda s: s['timestamp_us'])
        
        timestamps = [s['timestamp_us'] for s in all_samples]
        
        # Classify timestamps using OPLTimestamp
        classification = OPLTimestamp.classify_timestamps(timestamps)
        
        monotonic_samples = classification['monotonic']
        rtc_samples = classification['rtc']
        mixed_samples = classification['invalid']
        
        # Find jumps
        jumps = []
        for i in range(1, len(timestamps)):
            diff = timestamps[i] - timestamps[i-1]
            if diff > 60_000_000:  # > 60 seconds
                jumps.append({
                    'sample': i,
                    'from': timestamps[i-1],
                    'to': timestamps[i],
                    'diff_us': diff,
                    'diff_sec': diff / 1_000_000
                })
        
        # Check for backwards jumps
        backwards = sum(1 for i in range(1, len(timestamps)) 
                       if timestamps[i] < timestamps[i-1])
        
        self.time_stats = {
            'valid': True,
            'first_timestamp': timestamps[0],
            'last_timestamp': timestamps[-1],
            'duration_us': timestamps[-1] - timestamps[0],
            'monotonic_samples': monotonic_samples,
            'rtc_samples': rtc_samples,
            'mixed_samples': mixed_samples,
            'time_jumps': jumps,
            'backwards_jumps': backwards,
            'has_rtc_sync_jump': len(jumps) > 0 and max(j['diff_sec'] for j in jumps) > 1000
        }
    
    def _check_integrity(self):
        """Check file integrity"""
        # Check for missing session header
        if not self.header:
            self.integrity_issues.append("Missing session header")
            return
        
        # Check for empty session
        if not self.blocks:
            self.integrity_issues.append("No data blocks found")
        
        # Check for timestamp issues
        if self.time_stats and self.time_stats.get('backwards_jumps', 0) > 0:
            self.integrity_issues.append(
                f"Found {self.time_stats['backwards_jumps']} backwards time jumps"
            )
        
        # Check for RTC sync jump
        if self.time_stats and self.time_stats.get('has_rtc_sync_jump'):
            self.integrity_issues.append(
                "RTC sync detected mid-session (large time jump)"
            )
        
        # Check for mixed time sources
        if self.time_stats:
            mono = self.time_stats.get('monotonic_samples', 0)
            rtc = self.time_stats.get('rtc_samples', 0)
            if mono > 0 and rtc > 0:
                self.integrity_issues.append(
                    f"Mixed time sources: {mono} monotonic, {rtc} RTC-synced samples"
                )
        
        # Check for data gaps
        if self.sample_stats and self.sample_stats['gaps']:
            large_gaps = [g for g in self.sample_stats['gaps'] if g['duration_sec'] > 5.0]
            if large_gaps:
                self.integrity_issues.append(
                    f"Found {len(large_gaps)} large data gaps (>5 seconds)"
                )
    
    def _find_data_gaps(self, samples):
        """Find gaps in data stream"""
        if len(samples) < 2:
            return []
        
        # Sort by timestamp
        samples = sorted(samples, key=lambda s: s['timestamp_us'])
        
        gaps = []
        for i in range(1, len(samples)):
            diff = samples[i]['timestamp_us'] - samples[i-1]['timestamp_us']
            # Gap if > 1 second between samples
            if diff > 1_000_000:
                gaps.append({
                    'sample': i,
                    'duration_us': diff,
                    'duration_sec': diff / 1_000_000
                })
        
        return gaps
    
    def _get_session_duration_seconds(self):
        """Get session duration in seconds"""
        if not self.time_stats or not self.time_stats.get('valid'):
            return 0
        return self.time_stats['duration_us'] / 1_000_000
    
    def print_session_header(self):
        """Print session header information"""
        if not self.header:
            print("No session header found")
            return
        
        h = self.header
        print(f"\n{'='*70}")
        print(f"SESSION HEADER")
        print(f"{'='*70}")
        print(f"Session Name:    {h['session_name']}")
        print(f"Driver:          {h['driver_name']}")
        print(f"Vehicle:         {h['vehicle_id']}")
        print(f"Timestamp:       {OPLTimestamp.format_for_display(h['timestamp_us'])}")
        print(f"Weather:         {h['weather']}")
        print(f"Temperature:     {h['ambient_temp']:.1f}°C")
        print(f"Format Version:  {h['format_version']}")
        print(f"Hardware:        {h['hw_version']}")
        print(f"Session ID:      {h['session_id']}")
        print(f"Config CRC:      {h['config_crc']:#010x}")
    
    def print_hardware_config(self):
        """Print hardware configuration if present"""
        if not hasattr(self.reader, 'hardware_config') or not self.reader.hardware_config:
            print(f"\n{'='*70}")
            print(f"HARDWARE CONFIGURATION")
            print(f"{'='*70}")
            print("No hardware configuration in file")
            return
        
        hw = self.reader.hardware_config
        print(f"\n{'='*70}")
        print(f"HARDWARE CONFIGURATION")
        print(f"{'='*70}")
        print(f"Items: {hw['count']}")
        print()
        print(f"{'Type':<20} {'Connection':<15} {'Identifier':<30}")
        print(f"{'-'*70}")
        for item in hw['items']:
            print(f"{item['type']:<20} {item['connection']:<15} {item['identifier']:<30}")
    
    def print_summary(self):
        """Print data summary"""
        if not self.sample_stats:
            print("\nNo sample data to summarize")
            return
        
        stats = self.sample_stats
        
        print(f"\n{'='*70}")
        print(f"DATA SUMMARY")
        print(f"{'='*70}")
        print(f"Total Samples:   {stats['total']:,}")
        print()
        
        # Sample counts by type
        print("Sample Types:")
        type_names = {
            'accel': 'Accelerometer',
            'gps': 'GPS Fixes',
            'satellites': 'Satellite Data',
            'obd': 'OBD-II PIDs',
            'event': 'Event Markers'
        }
        for sample_type, count in stats['by_type'].items():
            name = type_names.get(sample_type, sample_type.capitalize())
            rate = stats['sample_rates'].get(sample_type, 0)
            print(f"  {name:<20} {count:>8,} samples  ({rate:>6.1f} Hz)")
        
        # Time information
        if self.time_stats and self.time_stats.get('valid'):
            print()
            print("Time Information:")
            ts = self.time_stats
            
            # Separate monotonic and RTC timestamps
            RTC_THRESHOLD = 946684800000000  # Jan 1, 2000 in µs since Unix epoch (1970)
            first_rtc_ts = None
            last_rtc_ts = None
            first_mono_ts = None
            
            # Find first and last RTC timestamps
            all_samples = []
            for block in self.blocks:
                all_samples.extend(block['samples'])
            all_samples.sort(key=lambda s: s['timestamp_us'])
            
            for sample in all_samples:
                t = sample['timestamp_us']
                if OPLTimestamp.is_rtc_synced(t):
                    if first_rtc_ts is None:
                        first_rtc_ts = t
                    last_rtc_ts = t
                elif first_mono_ts is None:
                    first_mono_ts = t
            
            # Show RTC-synced time range (verified time)
            if first_rtc_ts is not None:
                # Timestamps are in microseconds since Unix epoch (1970-01-01)
                start_dt = OPLTimestamp.to_datetime(first_rtc_ts)
                end_dt = OPLTimestamp.to_datetime(last_rtc_ts)
                print(f"  Start Time:      {start_dt.strftime('%Y-%m-%d %H:%M:%S')} (verified)")
                print(f"  End Time:        {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Calculate actual duration
                duration_us = last_rtc_ts - first_rtc_ts
                duration = timedelta(microseconds=duration_us)
                print(f"  Duration:        {duration}")
                
                # Show pre-sync period if exists
                if ts.get('monotonic_samples', 0) > 0 and first_mono_ts is not None:
                    # Find last monotonic sample before first RTC sample
                    last_mono_before_sync = None
                    for sample in all_samples:
                        t = sample['timestamp_us']
                        if t < RTC_THRESHOLD:
                            last_mono_before_sync = t
                        else:
                            break
                    
                    if last_mono_before_sync:
                        presync_duration = timedelta(microseconds=last_mono_before_sync - first_mono_ts)
                        print(f"  Pre-sync Period: {presync_duration} (before RTC sync)")
            else:
                # All monotonic time (no RTC sync)
                print(f"  Start Time:      {ts['first_timestamp']:,} µs (monotonic - no RTC sync)")
                print(f"  End Time:        {ts['last_timestamp']:,} µs (monotonic)")
                duration = timedelta(microseconds=ts['duration_us'])
                print(f"  Duration:        {duration}")
            
            # Time source breakdown
            if ts.get('monotonic_samples', 0) > 0 or ts.get('rtc_samples', 0) > 0:
                print()
                print("Time Sources:")
                if ts['monotonic_samples'] > 0:
                    pct = ts['monotonic_samples'] / stats['total'] * 100
                    print(f"  Monotonic:       {ts['monotonic_samples']:>8,} samples ({pct:>5.1f}%)")
                if ts['rtc_samples'] > 0:
                    pct = ts['rtc_samples'] / stats['total'] * 100
                    print(f"  RTC-synced:      {ts['rtc_samples']:>8,} samples ({pct:>5.1f}%)")
                if ts.get('mixed_samples', 0) > 0:
                    pct = ts['mixed_samples'] / stats['total'] * 100
                    print(f"  Mixed/Invalid:   {ts['mixed_samples']:>8,} samples ({pct:>5.1f}%)")
        
        # Data gaps
        if stats['gaps']:
            large_gaps = [g for g in stats['gaps'] if g['duration_sec'] > 1.0]
            if large_gaps:
                print()
                print(f"Data Gaps: {len(large_gaps)} gap(s) > 1 second")
                for i, gap in enumerate(large_gaps[:5], 1):  # Show max 5
                    print(f"  Gap {i}: {gap['duration_sec']:.1f}s at sample {gap['sample']}")
                if len(large_gaps) > 5:
                    print(f"  ... and {len(large_gaps) - 5} more")
        
        # Block information
        print()
        print(f"Data Blocks:     {len(self.blocks)}")
        if self.blocks:
            total_size = sum(len(b['samples']) for b in self.blocks)
            avg_size = total_size / len(self.blocks)
            print(f"  Average Size:  {avg_size:.1f} samples/block")
    
    def print_integrity_report(self):
        """Print integrity check results"""
        print(f"\n{'='*70}")
        print(f"INTEGRITY CHECK")
        print(f"{'='*70}")
        
        if not self.integrity_issues:
            print("✓ No issues found")
            return
        
        print(f"⚠ Found {len(self.integrity_issues)} issue(s):\n")
        for i, issue in enumerate(self.integrity_issues, 1):
            print(f"  {i}. {issue}")
    
    def print_detailed_info(self):
        """Print detailed analysis information"""
        print(f"\n{'='*70}")
        print(f"DETAILED ANALYSIS")
        print(f"{'='*70}")
        
        # Time jumps
        if self.time_stats and self.time_stats.get('time_jumps'):
            jumps = self.time_stats['time_jumps']
            print(f"\nTime Jumps: {len(jumps)}")
            for i, jump in enumerate(jumps, 1):
                print(f"\n  Jump {i}:")
                print(f"    At sample:     {jump['sample']}")
                print(f"    From:          {jump['from']:,} µs")
                print(f"    To:            {jump['to']:,} µs")
                print(f"    Difference:    {jump['diff_sec']:.1f} seconds")
        
        # Block details
        if self.blocks:
            print(f"\nData Blocks: {len(self.blocks)}")
            print(f"\n{'Block':<8} {'Samples':<10} {'Start Time':<20} {'Flags':<8}")
            print(f"{'-'*70}")
            for block in self.blocks[:10]:  # Show first 10
                flags = f"{block['flush_flags']:#04x}"
                timestamp = block['timestamp_start']
                print(f"{block['block_seq']:<8} {len(block['samples']):<10} "
                      f"{timestamp:<20} {flags:<8}")
            if len(self.blocks) > 10:
                print(f"  ... and {len(self.blocks) - 10} more blocks")
    
    def print_brief_summary(self):
        """Print one-line brief summary"""
        filename = self.filepath.name
        
        if not self.sample_stats:
            print(f"{filename:<30} ERROR: Could not read file")
            return
        
        stats = self.sample_stats
        total = stats['total']
        accel = stats['by_type'].get('accel', 0)
        gps = stats['by_type'].get('gps', 0)
        
        duration = "???"
        if self.time_stats and self.time_stats.get('valid'):
            # Use RTC-synced duration if available
            all_samples = []
            for block in self.blocks:
                all_samples.extend(block['samples'])
            
            first_rtc = None
            last_rtc = None
            for sample in sorted(all_samples, key=lambda s: s['timestamp_us']):
                t = sample['timestamp_us']
                if OPLTimestamp.is_rtc_synced(t):
                    if first_rtc is None:
                        first_rtc = t
                    last_rtc = t
            
            if first_rtc is not None:
                # Use verified RTC duration
                dur_sec = (last_rtc - first_rtc) / 1_000_000
            else:
                # Fall back to total duration (all monotonic)
                dur_sec = self.time_stats['duration_us'] / 1_000_000
            
            minutes = int(dur_sec // 60)
            seconds = int(dur_sec % 60)
            duration = f"{minutes:02d}:{seconds:02d}"
        
        issues = len(self.integrity_issues)
        status = "OK" if issues == 0 else f"⚠{issues}"
        
        print(f"{filename:<30} {total:>8,} samples  {duration:>8}  "
              f"A:{accel:>6,} G:{gps:>5,}  {status:<6}")


def main():
    parser = argparse.ArgumentParser(
        description='Inspect and analyze OpenPonyLogger binary files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full inspection (default)
  %(prog)s session_00001.opl
  
  # Brief summary (one line per file)
  %(prog)s *.opl --brief
  
  # Hide specific sections
  %(prog)s session_00001.opl --no-session --no-hardware
  
  # Detailed analysis
  %(prog)s session_00001.opl --detailed
  
  # Verify only (show errors, no other output)
  %(prog)s session_00001.opl --verify-only
  
  # Multiple files
  %(prog)s *.opl --brief
        """
    )
    
    parser.add_argument('input', nargs='+', help='Input .opl file(s)')
    
    # Output control
    parser.add_argument('--brief', action='store_true',
                       help='Brief one-line summary per file')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed analysis (time jumps, blocks)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only show integrity issues (suppress other output)')
    
    # Section toggles
    parser.add_argument('--no-session', action='store_true',
                       help='Hide session header')
    parser.add_argument('--no-hardware', action='store_true',
                       help='Hide hardware configuration')
    parser.add_argument('--no-summary', action='store_true',
                       help='Hide data summary')
    parser.add_argument('--no-integrity', action='store_true',
                       help='Hide integrity check')
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output (for debugging)')
    
    args = parser.parse_args()
    
    # Brief mode header
    if args.brief and len(args.input) > 1:
        print(f"\n{'Filename':<30} {'Samples':<8} {'Duration':<8} "
              f"{'Accel':<8} {'GPS':<6} {'Status':<6}")
        print(f"{'-'*70}")
    
    # Process each file
    exit_code = 0
    for input_file in args.input:
        input_path = Path(input_file)
        
        if not input_path.exists():
            print(f"✗ File not found: {input_path}")
            exit_code = 1
            continue
        
        try:
            # Create inspector
            inspector = OPLInspector(input_path, verbose=args.verbose)
            
            # Analyze file
            if not inspector.analyze():
                if not args.brief:
                    print(f"\n✗ Error analyzing {input_path}")
                    print(f"  {inspector.integrity_issues[0]}")
                else:
                    print(f"{input_path.name:<30} ERROR")
                exit_code = 1
                continue
            
            # Brief mode
            if args.brief:
                inspector.print_brief_summary()
                continue
            
            # Verify-only mode
            if args.verify_only:
                if inspector.integrity_issues:
                    print(f"\n{input_path.name}:")
                    for issue in inspector.integrity_issues:
                        print(f"  ⚠ {issue}")
                    exit_code = 1
                continue
            
            # Full report
            if len(args.input) > 1:
                print(f"\n{'='*70}")
                print(f"FILE: {input_path}")
                print(f"{'='*70}")
            
            # Print sections based on flags
            if not args.no_session:
                inspector.print_session_header()
            
            if not args.no_hardware:
                inspector.print_hardware_config()
            
            if not args.no_summary:
                inspector.print_summary()
            
            if not args.no_integrity:
                inspector.print_integrity_report()
                if inspector.integrity_issues:
                    exit_code = 1
            
            if args.detailed:
                inspector.print_detailed_info()
            
        except KeyboardInterrupt:
            print("\n\n⚠ Interrupted by user")
            return 130
        except Exception as e:
            print(f"\n✗ Error processing {input_path}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            exit_code = 1
            continue
    
    # Final newline
    if not args.brief:
        print()
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
