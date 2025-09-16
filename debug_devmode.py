"""
Debug script to analyze DEVMODE structure
"""
import struct

# Raw data from the log - first 100 bytes
hex_data = "4500500053004f004e005f00460058005f0032003100390030005f004f0044004f004f00000000000000000000000000000000000000000000000000000000000001040306dc00500343ef81050100a6006f08ea0a640001000f00f0000200010090000200"

# Convert hex to bytes
print(f"Hex string length: {len(hex_data)}")
print(f"First 50 chars: {hex_data[:50]}")

try:
    data = bytes.fromhex(hex_data)
except ValueError as e:
    print(f"Error: {e}")
    # Try to find the problematic character
    for i, char in enumerate(hex_data):
        if char not in '0123456789abcdefABCDEF':
            print(f"Invalid character '{char}' at position {i}")
    exit(1)

print(f"Total data length: {len(data)} bytes")
print(f"Raw hex: {data.hex()}")
print()

# Parse DEVMODE structure
# Device name (first 32 wide chars = 64 bytes)
device_name = data[0:64]
print(f"Device name (raw): {device_name}")
try:
    # Decode as UTF-16LE (Windows wide chars)
    device_name_str = device_name.decode('utf-16le').rstrip('\x00')
    print(f"Device name: {device_name_str}")
except:
    print("Failed to decode device name")

print()

# dmSpecVersion (offset 64, 2 bytes)
if len(data) >= 66:
    spec_version = struct.unpack('<H', data[64:66])[0]
    print(f"dmSpecVersion (offset 64): {spec_version} (0x{spec_version:04x})")

# dmDriverVersion (offset 66, 2 bytes) 
if len(data) >= 68:
    driver_version = struct.unpack('<H', data[66:68])[0]
    print(f"dmDriverVersion (offset 66): {driver_version} (0x{driver_version:04x})")

# dmSize (offset 68, 2 bytes)
if len(data) >= 70:
    dm_size = struct.unpack('<H', data[68:70])[0]
    print(f"dmSize (offset 68): {dm_size}")

# dmDriverExtra (offset 70, 2 bytes)
if len(data) >= 72:
    driver_extra = struct.unpack('<H', data[70:72])[0]
    print(f"dmDriverExtra (offset 70): {driver_extra}")

# dmFields (offset 72, 4 bytes)
if len(data) >= 76:
    dm_fields = struct.unpack('<L', data[72:76])[0]
    print(f"dmFields (offset 72): 0x{dm_fields:08x}")
    
    # Parse field flags
    DM_ORIENTATION = 0x00000001
    DM_PAPERSIZE = 0x00000002
    DM_PAPERLENGTH = 0x00000004
    DM_PAPERWIDTH = 0x00000008
    DM_SCALE = 0x00000010
    DM_COPIES = 0x00000100
    DM_DEFAULTSOURCE = 0x00000200
    DM_PRINTQUALITY = 0x00000400
    DM_COLOR = 0x00000800
    DM_DUPLEX = 0x00001000
    
    print("  Active fields:")
    if dm_fields & DM_ORIENTATION: print("  - DM_ORIENTATION")
    if dm_fields & DM_PAPERSIZE: print("  - DM_PAPERSIZE")
    if dm_fields & DM_PAPERLENGTH: print("  - DM_PAPERLENGTH")
    if dm_fields & DM_PAPERWIDTH: print("  - DM_PAPERWIDTH")
    if dm_fields & DM_SCALE: print("  - DM_SCALE")
    if dm_fields & DM_COPIES: print("  - DM_COPIES")
    if dm_fields & DM_DEFAULTSOURCE: print("  - DM_DEFAULTSOURCE")
    if dm_fields & DM_PRINTQUALITY: print("  - DM_PRINTQUALITY")
    if dm_fields & DM_COLOR: print("  - DM_COLOR")
    if dm_fields & DM_DUPLEX: print("  - DM_DUPLEX")

print()

# Now parse the actual values based on the correct offsets
# dmOrientation (offset 76, 2 bytes)
if len(data) >= 78:
    orientation = struct.unpack('<h', data[76:78])[0]  # signed short
    print(f"dmOrientation (offset 76): {orientation} ({'Portrait' if orientation == 1 else 'Landscape' if orientation == 2 else 'Unknown'})")

# dmPaperSize (offset 78, 2 bytes)
if len(data) >= 80:
    paper_size = struct.unpack('<h', data[78:80])[0]
    print(f"dmPaperSize (offset 78): {paper_size}")

# dmPaperLength (offset 80, 2 bytes)
if len(data) >= 82:
    paper_length = struct.unpack('<h', data[80:82])[0]
    print(f"dmPaperLength (offset 80): {paper_length} (1/10 mm)")

# dmPaperWidth (offset 82, 2 bytes)
if len(data) >= 84:
    paper_width = struct.unpack('<h', data[82:84])[0]
    print(f"dmPaperWidth (offset 82): {paper_width} (1/10 mm)")

# dmScale (offset 84, 2 bytes)
if len(data) >= 86:
    scale = struct.unpack('<h', data[84:86])[0]
    print(f"dmScale (offset 84): {scale}%")

# dmCopies (offset 86, 2 bytes)
if len(data) >= 88:
    copies = struct.unpack('<h', data[86:88])[0]
    print(f"dmCopies (offset 86): {copies}")

# dmDefaultSource (offset 88, 2 bytes)
if len(data) >= 90:
    default_source = struct.unpack('<h', data[88:90])[0]
    print(f"dmDefaultSource (offset 88): {default_source}")

# dmPrintQuality (offset 90, 2 bytes)
if len(data) >= 92:
    print_quality = struct.unpack('<h', data[90:92])[0]
    print(f"dmPrintQuality (offset 90): {print_quality}")

# dmColor (offset 92, 2 bytes)
if len(data) >= 94:
    color = struct.unpack('<h', data[92:94])[0]
    print(f"dmColor (offset 92): {color} ({'Monochrome' if color == 1 else 'Color' if color == 2 else 'Unknown'})")

# dmDuplex (offset 94, 2 bytes)
if len(data) >= 96:
    duplex = struct.unpack('<h', data[94:96])[0]
    print(f"dmDuplex (offset 94): {duplex} ({'Simplex' if duplex == 1 else 'Duplex Vertical' if duplex == 2 else 'Duplex Horizontal' if duplex == 3 else 'Unknown'})")

print()
print("Raw bytes at key positions:")
for i in range(0, min(len(data), 100), 16):
    chunk = data[i:i+16]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
    print(f"{i:04x}: {hex_str:<48} {ascii_str}")