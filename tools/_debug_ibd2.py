"""Inspect bytes around BE steam IDs."""
import struct

STEAM_MIN = 76561197960265728
STEAM_MAX = 76561202255233023
data = open(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd", "rb").read()

targets = {
    76561198171864983,
    76561198238059824,
    76561198059370951,
}

for i in range(len(data) - 7):
    v = struct.unpack_from(">Q", data, i)[0]
    if v not in targets:
        continue
    chunk = data[i : i + 120]
    ints_le = [struct.unpack_from("<i", chunk, o)[0] for o in range(0, 80, 4)]
    ints_be = [struct.unpack_from(">i", chunk, o)[0] for o in range(0, 80, 4)]
    print(f"\n=== steam {v} @ {i} ===")
    print("hex:", chunk[:64].hex())
    print("LE:", ints_le[:16])
    print("BE:", ints_be[:16])
    j = chunk.find(b'{"')
    print("json offset from steam:", j if j >= 0 else None)
