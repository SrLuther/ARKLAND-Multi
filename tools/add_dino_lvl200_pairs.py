"""Cria item avulso nivel 200 para cada dino nivel 1 sem par (mesmo blueprint)."""
from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG = Path("docs/config.json")
LEVEL_RE = re.compile(r"N[ií]vel\s+(\d+)", re.I)

SKIP_IDS = frozenset()  # pares ja existentes por outro id


def desc_level(entry: dict) -> int | None:
    desc = str(entry.get("Description") or entry.get("Name") or "")
    m = LEVEL_RE.search(desc)
    return int(m.group(1)) if m else None


def primary_dino(entry: dict) -> dict | None:
    dinos = entry.get("Dinos") or []
    return dinos[0] if dinos else None


def target_id(lvl1_id: str) -> str:
    if lvl1_id.endswith("_femea"):
        return lvl1_id[: -len("_femea")]
    if lvl1_id.startswith("sb_"):
        return f"{lvl1_id}_200"
    return f"{lvl1_id}_200"


def description_200(desc1: str) -> str:
    d = desc1.replace("Nível 1", "Nível 200").replace("Nivel 1", "Nível 200")
    d = d.replace("Fêmea ", "").replace("Fêmea", "")
    d = re.sub(r"\s+", " ", d).strip()
    return d


def price_200(lvl1_id: str, price1: int) -> int:
    if lvl1_id.startswith("sb_"):
        return price1
    if price1 >= 35_000:
        mult = 1.43
    elif price1 >= 20_000:
        mult = 1.75
    elif price1 >= 8_000:
        mult = 2.5
    else:
        mult = 3.0
    raw = max(int(price1 * mult), price1 + 3_000)
    return int(round(raw / 500) * 500)


def build_entry(lvl1_id: str, src: dict) -> dict:
    d0 = primary_dino(src)
    if not d0:
        raise ValueError(f"sem dino: {lvl1_id}")
    bp = d0["Blueprint"]
    desc = description_200(str(src.get("Description") or lvl1_id))
    entry: dict = {
        "Description": desc,
        "Dinos": [
            {
                "Blueprint": bp,
                "ForceTame": True,
                "Level": 200,
                "Neutered": False,
            }
        ],
        "Price": price_200(lvl1_id, int(src.get("Price") or 0)),
        "Type": "dino",
    }
    if src.get("Name"):
        entry["Name"] = description_200(str(src["Name"]))
    return entry


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = data.setdefault("Items", {})

    lvl200_bps = {
        primary_dino(e)["Blueprint"]
        for e in items.values()
        if e.get("Type") == "dino" and desc_level(e) == 200 and primary_dino(e)
    }

    created: list[str] = []
    skipped: list[str] = []

    for item_id, entry in list(items.items()):
        if entry.get("Type") != "dino" or desc_level(entry) != 1:
            continue
        d0 = primary_dino(entry)
        if not d0:
            continue
        bp = d0["Blueprint"]
        if bp in lvl200_bps:
            skipped.append(item_id)
            continue

        new_id = target_id(item_id)
        if new_id in items:
            skipped.append(f"{item_id}->{new_id} exists")
            continue
        if new_id in SKIP_IDS:
            continue

        items[new_id] = build_entry(item_id, entry)
        lvl200_bps.add(bp)
        created.append(f"{item_id} -> {new_id} ({items[new_id]['Price']})")

    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Criados: {len(created)}")
    for line in created:
        print(f"  {line}")
    print(f"Pulados (ja tinham par): {len(skipped)}")


if __name__ == "__main__":
    main()
