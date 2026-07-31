"""One-shot: inspect + strip *_pack10 from live ARKLANDSERVER catalogs."""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\ARKLANDSERVER")
REPO = Path(r"c:\Users\Ciano\Documents\arkland-multi")
sys.path.insert(0, str(REPO))
from src.shop_integration import strip_breeding_pack10_kits  # noqa: E402


def analyze(path: Path) -> dict:
    out = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return out
    out["size"] = path.stat().st_size
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        out["error"] = str(e)
        return out
    if not isinstance(data, dict):
        out["top_type"] = type(data).__name__
        return out
    out["top_keys"] = list(data.keys())[:40]
    kits = data.get("Kits")
    if isinstance(kits, dict):
        keys = list(kits.keys())
        pack10 = [k for k in keys if isinstance(k, str) and k.lower().endswith("_pack10")]
        out["kits_total"] = len(keys)
        out["pack10"] = len(pack10)
        out["pack10_sample"] = pack10[:8]
        out["keep"] = sorted(
            k
            for k in keys
            if k.startswith("kit_")
            or "starter" in k.lower()
            or "recurso" in k.lower()
            or k.lower() in ("vip", "kitvip")
        )[:25]
    else:
        out["kits_total"] = None
        out["kits_type"] = type(kits).__name__
    return out


def backup_and_strip(path: Path) -> dict:
    result = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return result
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_pack10_{ts}")
    shutil.copy2(path, bak)
    result["backup"] = str(bak)
    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data.get("Kits") or {}) if isinstance(data.get("Kits"), dict) else None
    removed = strip_breeding_pack10_kits(data)
    after = len(data.get("Kits") or {}) if isinstance(data.get("Kits"), dict) else None
    result["before"] = before
    result["removed"] = removed
    result["after"] = after
    if removed:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["written"] = True
    else:
        result["written"] = False
    return result


def find_candidates() -> list[Path]:
    known = [
        ROOT / "CustomShop" / "catalog.json",
        ROOT / "CustomShop" / "config.json",
        ROOT / "WEBSTORE" / "config.json",
        ROOT / "WEBSTORE" / "catalog.json",
        ROOT / "WEBSTORE" / "CustomShop" / "config.json",
        ROOT / "WEBSTORE" / "CustomShop" / "catalog.json",
    ]
    found: list[Path] = []
    skip_dirs = {
        "ShooterGame",
        "Saved",
        "Binaries",
        "Content",
        "Engine",
        "Logs",
        "steamapps",
        "Steam",
        "Mods",
        "node_modules",
        "__pycache__",
    }
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT)
        depth = len(rel.parts) if str(rel) != "." else 0
        if depth > 5:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if fn.lower() in ("catalog.json", "config.json"):
                found.append(Path(dirpath) / fn)
    # dedupe preserving order, known first
    seen = set()
    out: list[Path] = []
    for p in known + found:
        s = str(p).lower()
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out


def main() -> None:
    print("=== REPO ===")
    repo_cat = REPO / "plugin" / "CustomShop" / "catalog.json"
    print(json.dumps(analyze(repo_cat), indent=2, ensure_ascii=False))

    print("\n=== LIVE DIRS ===")
    for d in [ROOT / "CustomShop", ROOT / "WEBSTORE"]:
        print(d, "exists=", d.is_dir())
        if d.is_dir():
            for x in sorted(d.iterdir()):
                kind = "DIR" if x.is_dir() else x.stat().st_size
                print(" ", x.name, kind)

    candidates = find_candidates()
    dirty: list[Path] = []
    print("\n=== ANALYZE (pack10 presence) ===")
    for p in candidates:
        info = analyze(p)
        pack = info.get("pack10")
        if pack:
            dirty.append(p)
            print(
                f"DIRTY kits={info.get('kits_total')} pack10={pack} :: {p}"
            )
        elif info.get("exists") and info.get("kits_total") is not None:
            print(f"OK    kits={info.get('kits_total')} pack10=0 :: {p}")
        elif info.get("exists") and "Kits" not in (info.get("top_keys") or []):
            # may be map config without Kits
            pass
        elif info.get("exists"):
            print(f"OTHER {info}")

    print(f"\nDirty files with pack10: {len(dirty)}")
    print("\n=== STRIP ===")
    for p in dirty:
        r = backup_and_strip(p)
        print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n=== VERIFY AFTER ===")
    for p in [
        ROOT / "CustomShop" / "catalog.json",
        ROOT / "WEBSTORE" / "config.json",
        ROOT / "WEBSTORE" / "catalog.json",
        ROOT / "CustomShop" / "config.json",
    ] + dirty:
        info = analyze(p)
        if info.get("exists") and info.get("kits_total") is not None:
            print(
                f"kits={info.get('kits_total')} pack10={info.get('pack10')} :: {p}"
            )


if __name__ == "__main__":
    main()
