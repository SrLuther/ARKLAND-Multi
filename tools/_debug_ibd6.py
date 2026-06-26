"""Hex dump fixed fields before steam+json."""
import struct

STEAM_MIN = 76561197960265728
STEAM_MAX = 76561202255233023
data = open(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd", "rb").read()

count = 0
for i in range(len(data) - 10):
    v = struct.unpack_from(">Q", data, i)[0]
    if not (STEAM_MIN <= v <= STEAM_MAX):
        continue
    if data[i + 8 : i + 10] != b'{"':
        continue
    chunk = data[i - 16 : i + 8]
    fields = []
    for off in range(0, 24, 4):
        if off + 4 > len(chunk):
            break
        fields.append(struct.unpack_from("<i", chunk, off)[0])
    print(f"steam={v}")
    print(f"  offsets -16..+8 LE: {fields}")
    print(f"  hex: {chunk.hex()}")
    count += 1
    if count >= 8:
        break
