# opl-info.py Quick Reference

## Purpose
Inspect and analyze OPL files without converting them. Get detailed information about session data, detect integrity issues, and validate timestamps.

## Basic Usage

```bash
# Full inspection (default)
python3 opl-info.py session_00001.opl

# Brief one-line summary
python3 opl-info.py session_00001.opl --brief

# Check multiple files quickly
python3 opl-info.py *.opl --brief
```

## Default Output

Without any flags, shows:
1. **Session Header** - Name, driver, vehicle, timestamp, weather
2. **Hardware Configuration** - Connected sensors and devices
3. **Data Summary** - Sample counts, rates, duration, time sources
4. **Integrity Check** - Issues like bad timestamps, gaps, errors

## Output Control Flags

### Show/Hide Sections

```bash
# Hide session header
python3 opl-info.py file.opl --no-session

# Hide hardware config
python3 opl-info.py file.opl --no-hardware

# Hide data summary
python3 opl-info.py file.opl --no-summary

# Hide integrity check
python3 opl-info.py file.opl --no-integrity

# Show only integrity issues
python3 opl-info.py file.opl --no-session --no-hardware --no-summary
```

### Special Modes

```bash
# Brief mode (one line per file)
python3 opl-info.py *.opl --brief

# Detailed analysis (time jumps, block info)
python3 opl-info.py file.opl --detailed

# Verify only (only show errors)
python3 opl-info.py file.opl --verify-only

# Verbose (debugging info)
python3 opl-info.py file.opl --verbose
```

## Example Outputs

### Default Full Report

```
======================================================================
SESSION HEADER
======================================================================
Session Name:    Track Day
Driver:          John
Vehicle:         1ZVBP8AM5E5123456
Timestamp:       2025-12-17 15:30:00
Weather:         Clear
Temperature:     18.5°C
Format Version:  2.0
Hardware:        1.0
Session ID:      a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
Config CRC:      0x12345678

======================================================================
HARDWARE CONFIGURATION
======================================================================
Items: 4

Type                 Connection      Identifier                    
----------------------------------------------------------------------
LIS3DH              I2C 0x18        Adafruit LIS3DH               
ATGM336H            UART            ATGM336H GPS Module           
SSD1306             I2C 0x3C        Adafruit SSD1306 128x64       
SD_CARD             SPI             PiCowbell Adalogger           

======================================================================
DATA SUMMARY
======================================================================
Total Samples:   12,583

Sample Types:
  Accelerometer        10,000 samples  ( 100.0 Hz)
  GPS Fixes             2,583 samples  (  25.8 Hz)
  Satellite Data            0 samples  (   0.0 Hz)

Time Information:
  Start Time:      2025-12-17 15:30:45 (verified)
  End Time:        2025-12-17 17:10:15
  Duration:        1:39:30
  Pre-sync Period: 0:00:45 (before RTC sync)

Time Sources:
  Monotonic:            234 samples (  1.9%)
  RTC-synced:        12,349 samples ( 98.1%)

Data Gaps: 2 gap(s) > 1 second
  Gap 1: 5.2s at sample 234
  Gap 2: 2.1s at sample 8451

Data Blocks:     127
  Average Size:  99.1 samples/block

======================================================================
INTEGRITY CHECK
======================================================================
⚠ Found 2 issue(s):

  1. RTC sync detected mid-session (large time jump)
  2. Mixed time sources: 234 monotonic, 12349 RTC-synced samples
```

### Brief Mode (Multiple Files)

```
Filename                         Samples Duration     Accel    GPS Status
----------------------------------------------------------------------
session_00001.opl               12,583   01:40:15  A:10,000 G:2,583  ⚠2    
session_00002.opl               45,291   05:23:18  A:40,000 G:5,291  OK    
session_00003.opl                  234   00:00:57  A:   234 G:    0  ⚠1    
bad_file.opl                     ERROR: Could not read file
```

### Verify-Only Mode

```
session_00001.opl:
  ⚠ RTC sync detected mid-session (large time jump)
  ⚠ Mixed time sources: 234 monotonic, 12349 RTC-synced samples

session_00003.opl:
  ⚠ Found 3 large data gaps (>5 seconds)
```

### Detailed Mode

```
======================================================================
DETAILED ANALYSIS
======================================================================

Time Jumps: 1

  Jump 1:
    At sample:     234
    From:          57,889,619 µs
    To:            1,765,892,623,000,000 µs
    Difference:    30564502.9 seconds

Data Blocks: 127

Block    Samples    Start Time           Flags   
----------------------------------------------------------------------
0        100        1765892623000000     0x01    
1        99         1765892624000000     0x00    
2        101        1765892625000000     0x00    
3        98         1765892626000000     0x00    
4        100        1765892627000000     0x00    
5        102        1765892628000000     0x02    
6        97         1765892629000000     0x00    
7        100        1765892630000000     0x00    
8        99         1765892631000000     0x00    
9        103        1765892632000000     0x00    
  ... and 117 more blocks
```

## Common Use Cases

### Quick Health Check
```bash
# Check all sessions from today
python3 opl-info.py session_*.opl --brief

# Show only problematic files
python3 opl-info.py *.opl --verify-only
```

### Detailed Investigation
```bash
# Full analysis of specific file
python3 opl-info.py problem_file.opl --detailed

# See what's wrong with timestamps
python3 opl-info.py problem_file.opl --no-hardware
```

### Batch Validation
```bash
# Check entire directory
python3 opl-info.py /sd/sessions/*.opl --verify-only

# Quick stats on all files
python3 opl-info.py /sd/sessions/*.opl --brief > session_stats.txt
```

### Pre-Conversion Check
```bash
# Before converting, check for issues
python3 opl-info.py session.opl --verify-only

# If clean, convert
python3 opl2csv.py session.opl --drop-bad-time --patch-time-jumps
```

## Integrity Issues Detected

The tool automatically detects:

1. **Missing session header** - File is corrupted or incomplete
2. **No data blocks** - Session has header but no data
3. **Backwards time jumps** - Timestamps go backwards (serious error)
4. **RTC sync mid-session** - Large time jump indicating RTC sync
5. **Mixed time sources** - Both monotonic and RTC timestamps present
6. **Large data gaps** - Periods >5 seconds with no samples
7. **Read errors** - File format issues, checksum failures

### Smart Time Handling

The tool intelligently handles mixed monotonic/RTC timestamps:

- **Start Time** shows first RTC-synced sample (verified time), not boot time
- **Duration** calculated from verified time range (ignores pre-sync logging)
- **Pre-sync Period** separately reported if data logged before RTC sync
- **Brief mode** always uses verified duration when RTC sync available

This prevents bogus durations like "20439 days" when file has both monotonic and RTC timestamps.

## Exit Codes

- `0` - Success, no issues found
- `1` - File has integrity issues or read errors
- `130` - Interrupted by user (Ctrl+C)

## Integration with Other Tools

```bash
# Find files with issues, then fix them
python3 opl-info.py *.opl --verify-only | grep "⚠" | cut -d: -f1 | while read f; do
    python3 opl2csv.py "$f" --drop-bad-time --patch-time-jumps
done

# Get duration of all sessions
python3 opl-info.py *.opl --brief | awk '{print $1, $3}'

# Count total samples across all files
python3 opl-info.py *.opl --brief | awk '{sum += $2} END {print sum}'
```

## Sample Output Interpretation

### Brief Mode Fields

```
session_00001.opl    12,583   01:40:15  A:10,000 G:2,583  ⚠2
     ↓                  ↓         ↓          ↓       ↓     ↓
  Filename         Total     Duration   Accel    GPS   Status
                 Samples    HH:MM:SS   Count   Count  (⚠=issues)
```

### Status Codes
- `OK` - No issues detected
- `⚠N` - N issues detected (see --verify-only for details)
- `ERROR` - Could not read file

### Sample Rate Calculation
```
Hz = Sample Count / Duration in Seconds

Example: 10,000 samples / 100 seconds = 100.0 Hz
```

## Tips

1. **Always run opl-info.py before converting** - Catch issues early
2. **Use --brief for batch processing** - Quick overview of many files
3. **Use --verify-only in scripts** - Exit code indicates problems
4. **Check hardware config** - Verify all sensors were detected
5. **Watch for RTC sync jumps** - Consider --drop-bad-time for conversion

## See Also

- `opl2csv.py` - Convert OPL to CSV with timestamp filtering
- `opl2traccar.py` - Upload GPS data to Traccar server
- `TIMESTAMP_FILTERING_GUIDE.md` - How to handle timestamp issues
