"""Verify points offset after Kits JSON."""
import struct

STEAM_MIN = 76561197960265728
STEAM_MAX = 76561202255233023
data = open(r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd", "rb").read()


def json_end(start: int) -> int | None:
    depth = 0
    for j in range(start, min(start + 8000, len(data))):
        if data[j] == ord("{"):
            depth += 1
        elif data[j] == ord("}"):
            depth -= 1
            if depth == 0:
                return j + 1
    return None


rows = []
for i in range(len(data) - 10):
    v = struct.unpack_from(">Q", data, i)[0]
    if not (STEAM_MIN <= v <= STEAM_MAX):
        continue
    if data[i + 8 : i + 10] != b'{"':
        continue
    e = json_end(i + 8)
    if not e:
        continue
    tail = data[e : e + 20]
    pts = struct.unpack_from("<i", tail, 0)[0]
    spent = struct.unpack_from("<i", tail, 4)[0]
    rows.append((v, pts, spent, e - (i + 8)))

from collections import defaultdict

merged = {}
for sid, pts, spent, klen in rows:
    prev = merged.get(sid)
    if prev is None or pts > prev[0]:
        merged[sid] = (pts, spent, klen)

positive = [(s, p, sp) for s, (p, sp, _) in merged.items() if p > 0]
print("rows with steam+json:", len(rows))
print("unique:", len(merged), "positive:", len(positive))
print("total points:", sum(p for _, p, _ in positive))
for s, p, sp in sorted(positive, key=lambda x: -x[1])[:25]:
    print(f"{s}  points={p}  total_spent={sp}")
