"""
I2C Pin Diagnostic for Pico 2W
Helps identify which I2C pins are available
"""

import board
import busio

print("\n" + "="*50)
print("I2C Pin Diagnostic Tool")
print("="*50)

# List all possible I2C pin combinations for Pico
i2c_configs = [
    ("I2C0", board.GP1, board.GP0),   # I2C0: SCL=GP1, SDA=GP0
    ("I2C0", board.GP5, board.GP4),   # I2C0: SCL=GP5, SDA=GP4
    ("I2C0", board.GP9, board.GP8),   # I2C0: SCL=GP9, SDA=GP8
    ("I2C0", board.GP13, board.GP12), # I2C0: SCL=GP13, SDA=GP12
    ("I2C0", board.GP17, board.GP16), # I2C0: SCL=GP17, SDA=GP16
    ("I2C0", board.GP21, board.GP20), # I2C0: SCL=GP21, SDA=GP20
    ("I2C1", board.GP3, board.GP2),   # I2C1: SCL=GP3, SDA=GP2
    ("I2C1", board.GP7, board.GP6),   # I2C1: SCL=GP7, SDA=GP6
    ("I2C1", board.GP11, board.GP10), # I2C1: SCL=GP11, SDA=GP10
    ("I2C1", board.GP15, board.GP14), # I2C1: SCL=GP15, SDA=GP14
    ("I2C1", board.GP19, board.GP18), # I2C1: SCL=GP19, SDA=GP18
    ("I2C1", board.GP27, board.GP26), # I2C1: SCL=GP27, SDA=GP26
]

print("\nTesting I2C pin combinations...\n")

available = []

for name, scl, sda in i2c_configs:
    try:
        i2c = busio.I2C(scl, sda)
        i2c.deinit()
        status = "✓ AVAILABLE"
        available.append((name, scl, sda))
        print(f"{name} - SCL={scl}, SDA={sda}: {status}")
    except ValueError as e:
        print(f"{name} - SCL={scl}, SDA={sda}: ✗ IN USE ({e})")
    except Exception as e:
        print(f"{name} - SCL={scl}, SDA={sda}: ✗ ERROR ({e})")

print("\n" + "="*50)
print("AVAILABLE I2C CONFIGURATIONS:")
print("="*50)
if available:
    for name, scl, sda in available:
        print(f"  {name}: SCL={scl}, SDA={sda}")
else:
    print("  No I2C pins available!")

print("\n" + "="*50)
print("RECOMMENDATION:")
print("="*50)

if available:
    name, scl, sda = available[0]
    print(f"Use: i2c = busio.I2C({scl}, {sda})")
    print(f"     # {name}: SCL={scl}, SDA={sda}")
else:
    print("Check your existing code.py - something is holding I2C pins")
    print("You may need to use i2c.deinit() on existing I2C objects")

print()
