#!/usr/bin/env python3
"""Lock isolated dino Items that match license-gated kit contents.

Rule: map each dino shop SKU to the lowest gated kit (kit_gamma < kit_beta <
kit_alfa) that contains the same blueprint, then copy that kit's Permissions
string. Leave abyss/open dinos untouched. Also locks matching pack10 kits
that bundle the same BPs (same Permissions), so pack10 cannot bypass the gate.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
BIN_CONFIG = ROOT / "plugin" / "CustomShop" / "bin" / "config.json"
EDIT_CONFIG = ROOT / ".edit" / "config.json"

# Lowest-first: entry tier wins when BP appears in multiple kits.
GATED_DINO_KITS = ("kit_gamma", "kit_beta", "kit_alfa")


def bp_short(bp: str) -> str:
    if not bp:
        return ""
    name = bp.rstrip("/").split("/")[-1]
    if "." in name:
        name = name.split(".")[-1]
    return name.lower()


def collect_bps(entry: dict) -> list[str]:
    out: list[str] = []
    for d in entry.get("Dinos") or []:
        if isinstance(d, dict) and d.get("Blueprint"):
            out.append(str(d["Blueprint"]))
    if entry.get("Blueprint"):
        out.append(str(entry["Blueprint"]))
    return out


def build_bp_to_perms(kits: dict) -> dict[str, str]:
    """BP short name -> Permissions of lowest gated kit that contains it."""
    mapping: dict[str, str] = {}
    for kid in GATED_DINO_KITS:
        kit = kits.get(kid) or {}
        perms = str(kit.get("Permissions") or "").strip()
        if not perms:
            continue
        for bp in collect_bps(kit):
            short = bp_short(bp)
            if short and short not in mapping:
                mapping[short] = perms
    return mapping


def apply(data: dict, *, lock_pack10: bool) -> dict:
    kits = data.get("Kits") or {}
    items = data.get("Items") or {}
    bp_perms = build_bp_to_perms(kits)

    stats = {
        "dinos_locked": 0,
        "dinos_already": 0,
        "dinos_skipped": 0,
        "pack10_locked": 0,
        "pack10_already": 0,
        "samples": [],
        "by_perms": {},
    }

    for key, item in items.items():
        if not isinstance(item, dict) or item.get("Type") != "dino":
            continue
        shorts = {bp_short(b) for b in collect_bps(item) if b}
        match = next((bp_perms[s] for s in shorts if s in bp_perms), None)
        if not match:
            stats["dinos_skipped"] += 1
            continue
        cur = str(item.get("Permissions") or "").strip()
        if cur == match:
            stats["dinos_already"] += 1
            continue
        if cur and cur != match:
            # Keep existing explicit gate; report
            stats["dinos_already"] += 1
            continue
        item["Permissions"] = match
        stats["dinos_locked"] += 1
        stats["by_perms"].setdefault(match, []).append(key)
        if len(stats["samples"]) < 12:
            stats["samples"].append((key, match))

    if lock_pack10:
        for key, kit in kits.items():
            if not isinstance(kit, dict):
                continue
            if "pack10" not in key.lower():
                continue
            # Never touch abyss packs
            if "abyss" in key.lower():
                continue
            shorts = {bp_short(b) for b in collect_bps(kit) if b}
            match = next((bp_perms[s] for s in shorts if s in bp_perms), None)
            if not match:
                continue
            cur = str(kit.get("Permissions") or "").strip()
            if cur == match:
                stats["pack10_already"] += 1
                continue
            if cur and cur != match:
                stats["pack10_already"] += 1
                continue
            kit["Permissions"] = match
            stats["pack10_locked"] += 1
            stats["by_perms"].setdefault(match, []).append(f"KIT:{key}")

    return stats


def main() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    data = json.loads(raw)

    # Dry-run first printed; then write.
    # lock_pack10=True: same BPs in pack10 would bypass isolated dino gates.
    stats = apply(data, lock_pack10=True)

    CONFIG.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(CONFIG, BIN_CONFIG)

    edit_note = "skipped (no Kits/Items dinos expected)"
    if EDIT_CONFIG.exists():
        try:
            edit = json.loads(EDIT_CONFIG.read_text(encoding="utf-8"))
            if edit.get("Kits") or edit.get("Items"):
                # Only touch if it actually has catalog
                has_dino = any(
                    isinstance(v, dict) and v.get("Type") == "dino"
                    for v in (edit.get("Items") or {}).values()
                )
                if has_dino:
                    st2 = apply(edit, lock_pack10=True)
                    EDIT_CONFIG.write_text(
                        json.dumps(edit, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    edit_note = f"updated dinos={st2['dinos_locked']} pack10={st2['pack10_locked']}"
                else:
                    edit_note = "no Type=dino Items — left untouched"
            else:
                edit_note = "no Kits/Items — left untouched"
        except Exception as exc:  # noqa: BLE001
            edit_note = f"error: {exc}"

    print("=== RESULT ===")
    print(f"dinos locked: {stats['dinos_locked']}")
    print(f"dinos already: {stats['dinos_already']}")
    print(f"dinos skipped (open): {stats['dinos_skipped']}")
    print(f"pack10 locked: {stats['pack10_locked']}")
    print(f"bin mirrored: {BIN_CONFIG}")
    print(f".edit: {edit_note}")
    print("\nBy Permissions:")
    for perms, keys in sorted(stats["by_perms"].items(), key=lambda x: -len(x[1])):
        print(f"  {perms} ({len(keys)})")
        for k in keys:
            print(f"    - {k}")
    print("\nSamples:")
    for k, p in stats["samples"]:
        print(f"  {k} -> {p}")


if __name__ == "__main__":
    main()
