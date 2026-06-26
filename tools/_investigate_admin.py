#!/usr/bin/env python3
"""Deep investigation for admin steam 76561198171864983 legacy points."""
import re
import struct
from collections import defaultdict
from pathlib import Path

STEAM = "76561198171864983"
STEAM_INT = 76561198171864983
DATA = Path(r"C:\Users\Ciano\Pictures\data")


def analyze_arkshopplayers():
    path = DATA / "arkshop" / "arkshopplayers.ibd"
    data = path.read_bytes()
    steam_min, steam_max = 76561197960265728, 76561202255233023

    rows_empty, rows_json, rows_other = [], [], []
    for i in range(len(data) - 10):
        steam_val = struct.unpack_from(">Q", data, i)[0]
        if not (steam_min <= steam_val <= steam_max):
            continue
        kits = data[i + 8 : i + 10]
        pts = struct.unpack_from("<i", data, i - 8)[0]
        if pts < 0 or pts > 500_000:
            continue
        sid = str(steam_val)
        if kits == b"{}":
            rows_empty.append((sid, pts, i))
        elif kits == b'{"':
            rows_json.append((sid, pts, i))
        else:
            rows_other.append((sid, pts, i, kits))

    print("=== arkshopplayers.ibd row analysis ===")
    print(f"empty kits: {len(rows_empty)}")
    print(f"json kits:  {len(rows_json)}")
    print(f"other:      {len(rows_other)}")

    print("\nTop empty_kits (suspected false positives):")
    for sid, pts, off in sorted(rows_empty, key=lambda x: -x[1])[:12]:
        print(f"  {sid}: {pts:,} @0x{off:x}")

    by_steam = defaultdict(list)
    for sid, pts, off in rows_empty:
        by_steam[sid].append(("empty", pts, off))
    for sid, pts, off in rows_json:
        by_steam[sid].append(("json", pts, off))

    both = {s: v for s, v in by_steam.items() if len({x[0] for x in v}) > 1}
    print(f"\nSteam with BOTH empty+json: {len(both)}")
    for sid in sorted(both, key=lambda s: -max(x[1] for x in both[s]))[:8]:
        print(f"  {sid}: {both[sid]}")

    print(f"\nAdmin {STEAM}:")
    for kind, pts, off in sorted(by_steam.get(STEAM, []), key=lambda x: -x[1]):
        print(f"  {kind}: {pts:,} @0x{off:x}")

  # other marker hits for admin
    steam_be = struct.pack(">Q", STEAM_INT)
    for i in range(len(data) - 8):
        if data[i : i + 8] != steam_be:
            continue
        pts = struct.unpack_from("<i", data, i - 8)[0]
        kits = data[i + 8 : i + 24]
        print(f"  raw@0x{i:x}: pts@-8={pts:,} kits={kits[:12]!r}")


def analyze_customshop_players():
    path = DATA / "arkshop" / "players.ibd"
    data = path.read_bytes()
    print("\n=== customshop players.ibd ===")
    for m in re.finditer(STEAM, data.decode("latin-1", errors="ignore")):
        pos = m.start()
        end = pos + len(STEAM)
        if end < len(data) and data[end] == 0:
            end += 1
        pts = struct.unpack_from("<i", data, end)[0] if end + 4 <= len(data) else None
        ctx = data[max(0, pos - 16) : pos + 48]
        print(f"  @0x{pos:x}: points after null={pts}")
        print(f"    hex: {ctx.hex()}")


def scan_all_ibd_for_admin():
    print("\n=== ALL .ibd files with BE steam match ===")
    steam_be = struct.pack(">Q", STEAM_INT)
    for fp in sorted(DATA.rglob("*.ibd")):
        data = fp.read_bytes()
        hits = []
        start = 0
        while True:
            i = data.find(steam_be, start)
            if i < 0:
                break
            pts = struct.unpack_from("<i", data, i - 8)[0] if i >= 8 else None
            kits = data[i + 8 : i + 12] if i + 12 <= len(data) else b""
            hits.append((i, pts, kits))
            start = i + 1
        ascii_hits = len(re.findall(STEAM, data.decode("latin-1", errors="ignore")))
        if hits or ascii_hits:
            rel = fp.relative_to(DATA)
            print(f"\n{rel}: BE={len(hits)} ASCII={ascii_hits}")
            for i, pts, kits in hits[:5]:
                print(f"  BE@0x{i:x}: pts@-8={pts:,} kits={kits!r}")


def verify_top_33k_rows():
    """Check if top ~33k rows are InnoDB metadata false positives."""
    path = DATA / "arkshop" / "arkshopplayers.ibd"
    data = path.read_bytes()
    steam_min, steam_max = 76561197960265728, 76561202255233023

    print("\n=== Verifying top empty_kits rows (33k suspects) ===")
    suspects = []
    for i in range(len(data) - 10):
        steam_val = struct.unpack_from(">Q", data, i)[0]
        if not (steam_min <= steam_val <= steam_max):
            continue
        if data[i + 8 : i + 10] != b"{}":
            continue
        pts = struct.unpack_from("<i", data, i - 8)[0]
        if pts < 30000:
            continue
        sid = str(steam_val)
        has_json = False
        for j in range(len(data) - 10):
            if struct.unpack_from(">Q", data, j)[0] != steam_val:
                continue
            if data[j + 8 : j + 10] == b'{"':
                has_json = True
                json_pts = struct.unpack_from("<i", data, j - 8)[0]
                break
        suspects.append((sid, pts, i, has_json, json_pts if has_json else None))

    for sid, pts, off, has_json, json_pts in sorted(suspects, key=lambda x: -x[1]):
        status = f"ALSO json@{json_pts:,}" if has_json else "ONLY empty (likely FALSE POSITIVE)"
        print(f"  {sid}: empty={pts:,} @0x{off:x} -> {status}")


def json_only_ranking():
    path = DATA / "arkshop" / "arkshopplayers.ibd"
    data = path.read_bytes()
    steam_min, steam_max = 76561197960265728, 76561202255233023
    rows = []
    for i in range(len(data) - 10):
        if data[i + 8 : i + 10] != b'{"':
            continue
        steam_val = struct.unpack_from(">Q", data, i)[0]
        if not (steam_min <= steam_val <= steam_max):
            continue
        pts = struct.unpack_from("<i", data, i - 8)[0]
        if pts < 0 or pts > 500_000:
            continue
        rows.append((str(steam_val), pts, i))
    rows.sort(key=lambda x: -x[1])
    print("\n=== TOP 20 JSON-only rows (high confidence) ===")
    for sid, pts, off in rows[:20]:
        print(f"  {sid}: {pts} @0x{off:x}")
    admin = [r for r in rows if r[0] == STEAM]
    print(f"Admin: {admin}")
    print(f"Total JSON rows: {len(rows)}")


def parse_customshop_row():
    path = DATA / "arkshop" / "players.ibd"
    data = path.read_bytes()
    pos = data.find(STEAM.encode())
    if pos < 0:
        print("\n=== customshop: admin not found ===")
        return
    print(f"\n=== customshop players.ibd admin @0x{pos:x} ===")
    end = pos + len(STEAM)
    for delta in range(0, 32):
        o = end + delta
        if o + 4 <= len(data):
            v = struct.unpack_from("<i", data, o)[0]
            if 0 < v < 500_000:
                print(f"  INT32 LE @steam+{delta}: {v}")
    chunk = data[pos : pos + 64]
    print(f"  raw: {chunk.hex()}")
    print(f"  ascii: {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")


if __name__ == "__main__":
    analyze_arkshopplayers()
    analyze_customshop_players()
    scan_all_ibd_for_admin()
    verify_top_33k_rows()
    json_only_ranking()
    parse_customshop_row()
