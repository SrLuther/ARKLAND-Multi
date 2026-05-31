"""Extract readable strings from ARK mod .uasset.z files to map the MX-E protocol."""
import zlib, struct, re, os, sys

MOD_PATH = r"C:\Users\Ciano\Documents\TESTE SERVER\01\ShooterGame\Content\Mods\2693727499\WindowsNoEditor"

KEYWORDS = [
    'Kit', 'Shop', 'Buy', 'Sell', 'Get', 'Redeem', 'Claim', 'Use',
    'Point', 'Config', 'Item', 'Command', 'Receive', 'Send', 'console',
    'exec', 'Client', 'Server', 'Callback', 'Notify', 'Request',
]

def decompress_ark_z(path):
    with open(path, "rb") as f:
        data = f.read()

    magic = data[:4]
    if magic != b'\xC1\x83\x2A\x9E':
        return None

    out = b""
    pos = 32  # skip 32-byte header
    while pos < len(data):
        try:
            chunk_comp   = struct.unpack_from("<q", data, pos)[0]; pos += 8
            chunk_uncomp = struct.unpack_from("<q", data, pos)[0]; pos += 8
            if chunk_comp <= 0 or pos + chunk_comp > len(data):
                break
            out += zlib.decompress(data[pos:pos+chunk_comp])
            pos += chunk_comp
        except Exception:
            break
    return out

all_strings = {}

for root, dirs, files in os.walk(MOD_PATH):
    for fname in files:
        if not fname.endswith('.uasset.z'):
            continue
        fpath = os.path.join(root, fname)
        data = decompress_ark_z(fpath)
        if not data:
            continue
        strings = re.findall(rb'[A-Za-z][A-Za-z0-9_]{3,}', data)
        strings = [s.decode('ascii', errors='ignore') for s in strings]
        hits = sorted(set(
            s for s in strings
            if any(k.lower() in s.lower() for k in KEYWORDS)
        ))
        if hits:
            all_strings[fname] = hits

for fname, hits in sorted(all_strings.items()):
    print(f"\n=== {fname} ===")
    for s in hits:
        print(f"  {s}")
