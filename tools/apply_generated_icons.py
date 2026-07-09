#!/usr/bin/env python3
"""Move generated PNGs from Cursor assets staging into raw/ and optionally compress."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated" / "raw"
ASSETS_DIR = Path.home() / ".cursor" / "projects" / "c-Users-Ciano-Documents-arkland-multi" / "assets"
QUEUE_PATH = ROOT / "tools" / "_batch_regen_queue.json"
STATE_PATH = ROOT / "tools" / "_batch_regen_state.json"


def _allowed_keys() -> set[str]:
    if QUEUE_PATH.is_file():
        items = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        return {str(i["species_key"]).lower() for i in items}
    return set()


def load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"done": [], "failed": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply(keys: list[str] | None = None, *, from_assets: bool = True) -> int:
    state = load_state()
    done_set = set(state.get("done") or [])
    moved = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    allowed = _allowed_keys()
    want = {k.lower() for k in keys} if keys else None
    sources: list[tuple[str, Path]] = []
    if from_assets and ASSETS_DIR.is_dir():
        for p in sorted(ASSETS_DIR.glob("*.png")):
            sk = p.stem.lower()
            if allowed and sk not in allowed:
                continue
            if want is not None and sk not in want:
                continue
            sources.append((sk, p))

    for sk, src in sources:
        dest = RAW_DIR / f"{sk}.png"
        shutil.copy2(src, dest)
        if sk not in done_set:
            done_set.add(sk)
        moved += 1
        print(f"  applied {sk}.png -> {dest.relative_to(ROOT)}")

    state["done"] = sorted(done_set)
    save_state(state)
    return moved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", nargs="*", help="Subset of species_key (default: all in assets)")
    parser.add_argument("--compress", action="store_true", help="Run compress after apply")
    args = parser.parse_args()

    n = apply(args.keys)
    print(f"Applied {n} icon(s)")
    if args.compress and n:
        sys.path.insert(0, str(ROOT / "tools"))
        import importlib.util

        spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        c = gen.compress_all_raw(force=True)
        print(f"Compressed {c} webp(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
