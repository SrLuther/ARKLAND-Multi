from pathlib import Path

path = Path(r'c:\Users\Ciano\Documents\arkland-multi\src\app.py')
raw = path.read_bytes()

# Verify cp1252 is fully bijective for all 256 bytes
for b in range(256):
    ch = bytes([b]).decode('cp1252')
    back = ch.encode('cp1252')
    assert back == bytes([b]), f"cp1252 not bijective at byte {b:#x}"
print("cp1252 round-trip OK for all 256 bytes")

# Preserve BOM
if raw[:3] == b'\xef\xbb\xbf':
    bom = b'\xef\xbb\xbf'
    raw = raw[3:]
else:
    bom = b''

# Decode current mojibake content as UTF-8
content = raw.decode('utf-8')

# Fix: for each character, encode as cp1252 (recovers original UTF-8 byte)
# Characters outside cp1252 range (correctly-added emoji like U+1F7E1) are kept as UTF-8
fixed_bytes = bytearray()
for char in content:
    try:
        fixed_bytes.extend(char.encode('cp1252'))
    except UnicodeEncodeError:
        fixed_bytes.extend(char.encode('utf-8'))

# Decode the resulting byte stream as UTF-8 to get correct Unicode
fixed = fixed_bytes.decode('utf-8')

# Write back with BOM
path.write_bytes(bom + fixed.encode('utf-8'))
print(f"Done: {len(content)} chars (mojibake) -> {len(fixed)} chars (fixed)")

# Verify a known string
check = path.read_text(encoding='utf-8-sig')
if 'é uma subpasta' in check:
    print("Verification OK: 'é uma subpasta' found")
elif 'Ã©' in check:
    print("STILL MOJIBAKE: 'Ã©' still present")
else:
    print("WARNING: neither pattern found")
