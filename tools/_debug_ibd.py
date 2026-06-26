"""Temporary debug helper — pair BE steam IDs with points."""
import struct
from collections import defaultdict

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


steams: list[tuple[int, int]] = []
for i in range(len(data) - 7):
    v = struct.unpack_from(">Q", data, i)[0]
    if STEAM_MIN <= v <= STEAM_MAX:
        steams.append((i, v))

jsons: list[tuple[int, int]] = []
for marker in (b'{"starter', b'{"diamante', b'{"acro_pack10'):
    s = 0
    while True:
        idx = data.find(marker, s)
        if idx < 0:
            break
        b = idx
        while b > 0 and data[b] != ord("{"):
            b -= 1
        e = json_end(b)
        if e:
            jsons.append((b, e))
        s = idx + 1

print("steams", len(steams), "jsons", len(jsons))

rows: list[tuple[int, int]] = []
for b, e in jsons:
    best: tuple[int, int] | None = None
    for sp, sv in steams:
        if sp < b and b - sp < 200:
            if best is None or sp > best[0]:
                best = (sp, sv)
    if not best:
        continue
    points = 0
    for o in range(0, 32):
        if e + o + 4 > len(data):
            break
        v = struct.unpack_from("<i", data, e + o)[0]
        if 0 <= v <= 5_000_000:
            points = v
            break
    rows.append((best[1], points))

merged: dict[int, int] = defaultdict(int)
for sid, pts in rows:
    merged[sid] = max(merged[sid], pts)

positive = [(s, p) for s, p in merged.items() if p > 0]
print("unique steam", len(merged), "positive", len(positive), "total", sum(p for _, p in positive))
for s, p in sorted(positive, key=lambda x: -x[1])[:20]:
    print(s, p)

# also dump zero points count
zeros = sum(1 for p in merged.values() if p == 0)
print("zero points rows:", zeros)
