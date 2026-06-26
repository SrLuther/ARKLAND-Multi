"""Find Points INT in bytes immediately before steam+json."""
import struct
from collections import defaultdict

STEAM_MIN = 76561197960265728
STEAM_MAX = 76561202255233023
data = open(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd", "rb").read()

rows = []
for i in range(len(data) - 10):
    v = struct.unpack_from(">Q", data, i)[0]
    if not (STEAM_MIN <= v <= STEAM_MAX):
        continue
    if data[i + 8 : i + 10] != b'{"':
        continue
  # scan 4-byte LE ints in 32 bytes before steam
    candidates = []
    for off in range(max(0, i - 32), i):
        if off + 4 > i:
            continue
        val = struct.unpack_from("<i", data, off)[0]
        if 1 <= val <= 5_000_000:
            candidates.append((off - i, val))
    rows.append((v, candidates))

merged: dict[int, tuple[int, int]] = {}
for sid, cands in rows:
    if not cands:
        continue
    # prefer offset closest to steam (largest offset, i.e. -4, -8, etc.)
    off, pts = sorted(cands, key=lambda x: x[0], reverse=True)[0]
    prev = merged.get(sid)
    if prev is None or pts > prev[0]:
        merged[sid] = (pts, off)

positive = sorted([(s, p, o) for s, (p, o) in merged.items() if p > 0], key=lambda x: -x[1])
print("unique positive:", len(positive), "total:", sum(p for _, p, _ in positive))
for s, p, o in positive[:30]:
    print(f"{s}  points={p}  offset={o}")

# show distribution of offsets
from collections import Counter

print("offset distribution:", Counter(o for _, _, o in positive))
