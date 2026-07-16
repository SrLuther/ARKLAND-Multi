#!/usr/bin/env python3
"""Compose all bust PNGs from assets/ (or --assets-dir) matching _dino_icon_queue.json."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = Path(r"C:\Users\Ciano\.cursor\projects\c-Users-Ciano-Documents-arkland-multi\assets")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    p.add_argument("--queue", type=Path, default=ROOT / "_dino_icon_queue.json")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    done = skipped = 0
    for row in queue:
        if args.limit and done >= args.limit:
            break
        sk = row["species_key"]
        bust = args.assets_dir / f"{sk}_bust.png"
        webp = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated" / f"{sk}.webp"
        if webp.is_file():
            continue
        if not bust.is_file():
            skipped += 1
            continue
        cmd = [
            sys.executable,
            str(ROOT / "tools" / "_compose_dino_icon.py"),
            "--species",
            sk,
            "--bust",
            str(bust),
            "--name",
            str(row["display_name"]),
            "--tier",
            str(row["tier"]),
        ]
        subprocess.run(cmd, check=True, cwd=ROOT)
        done += 1
        print(f"OK {sk}")
    print(f"composed={done} skipped_missing_bust={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
