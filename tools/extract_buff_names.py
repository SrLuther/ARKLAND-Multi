import struct, zlib, re

src = r'C:\Program Files (x86)\Steam\steamapps\workshop\content\346110\2693727499\WindowsNoEditor\Assets\ArkShopUI_Buff_FCAS.uasset.z'
data = open(src, 'rb').read()
raw = zlib.decompress(data[50:], -15)

print(f"Decompressed: {len(raw)} bytes\n")

# Extract length-prefixed UE4 strings (int32 len + utf8/ascii + null)
pos = 0
found = []
while pos < len(raw) - 5:
    try:
        slen = struct.unpack_from('<i', raw, pos)[0]
        if 3 <= slen <= 100:
            s = raw[pos+4:pos+4+slen]
            if s[-1:] == b'\x00':
                try:
                    t = s[:-1].decode('ascii')
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_\-\.]*$', t):
                        found.append((pos, t))
                except Exception:
                    pass
    except Exception:
        pass
    pos += 1

unique = sorted(set(t for _, t in found))

print("=== ALL FUNCTION/PROPERTY NAMES ===")
for s in unique:
    lower = s.lower()
    if any(k in lower for k in ['shop','item','point','kit','config','key','sell','buy','trade','data','json','permission','group','receive','callback','init','server','stash']):
        print(f"  {s}")

print("\n=== KEY FUNCTIONS (candidates to call via ProcessEvent) ===")
for s in unique:
    if s.startswith(('ROC_', 'ROS_', 'FCAS_', 'OnServer', 'SetConfig', 'SetUi', 'ForceUpdate', 'Init')):
        print(f"  {s}")
