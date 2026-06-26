"""Look before steam+json rows for Points INT."""
import struct

STEAM_MIN = 76561197960265728
STEAM_MAX = 76561202255233023
data = open(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd", "rb").read()

samples = []
for i in range(len(data) - 10):
    v = struct.unpack_from(">Q", data, i)[0]
    if not (STEAM_MIN <= v <= STEAM_MAX):
        continue
    if data[i + 8 : i + 10] != b'{"':
        continue
    before = data[max(0, i - 40) : i]
    ints = [struct.unpack_from("<i", before, o)[0] for o in range(0, max(0, len(before) - 3), 4)]
    samples.append((v, ints, before.hex()))

for v, ints, hx in samples[:12]:
    plausible = [x for x in ints if 0 < x <= 5_000_000]
    print(f"{v} plausible_before={plausible} last_ints={ints[-6:]}")
